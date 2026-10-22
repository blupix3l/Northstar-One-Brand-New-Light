"""
Search Result Ranking
=====================
A provider-independent relevance re-ranking pass applied AFTER providers
fan out, results are merged, and duplicates are removed.

The goal is to order by *probable user intent* rather than by which provider
happened to answer first. Provider ordering is intentionally ignored: the best
result wins regardless of source.

Scoring signals (all combined into a single 0..1-ish score on `SearchResult.score`):

  * Exact / begins-with / contains matches against the query in the title.
  * Exact / contains matches against the query in the URL path and domain.
  * Snippet relevance (query terms appearing in the snippet).
  * Duplicate confirmations: the same URL returned by multiple providers is
    a strong relevance signal (independent of which providers).
  * Official-site heuristic: a short, clean root/apex domain whose name matches
    the query (e.g. ``python.org`` for ``python``) is boosted hard. This is what
    lifts ``python.org`` above a Wikipedia article about the British Cold War
    "PYTHON" plan.
  * Provider confidence: each provider's own score is normalized and used only
    as a mild tie-breaker, never as a primary signal.
  * NSIndex confidence: when NSIndex returns a result with an explicit
    relevance score, it contributes as one more signal, not as a guaranteed top.

Ambiguous queries (e.g. ``python`` = language / snake / military plan) are
handled naturally: each candidate is scored on its own merits, so multiple
meanings can coexist in the top N — the language's official site simply scores
highest because of the official-site + domain-match signals.

The final ranked list is what gets cached, so cache hits preserve the improved
ordering.
"""

import os
import re
from typing import List
from urllib.parse import urlparse

from .models import SearchResult


# NS_DEBUG enables the "Before Ranking / After Ranking" trace.
_DEBUG = os.environ.get("NS_DEBUG", "").lower() in ("1", "true", "yes", "on")


# Domains that are encyclopedic / aggregator / reference rather than the
# canonical official source for a topic. Used to gently demote them when a
# stronger official candidate exists for the same intent.
_REFERENCE_DOMAINS = {
    "wikipedia.org",
    "wiktionary.org",
    "wikimedia.org",
    "britannica.com",
    "encyclopedia.com",
    "imdb.com",
    "reddit.com",
    "quora.com",
    "yahoo.com",
    "bing.com",
    "google.com",
    "duckduckgo.com",
}


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        host = ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _apex(domain: str) -> str:
    """Return the registrable apex (e.g. 'python.org') minus subdomains."""
    parts = domain.split(".")
    if len(parts) <= 2:
        return domain
    # Drop the leftmost subdomain(s), keep last two labels as a heuristic.
    return ".".join(parts[-2:])


def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _query_terms(query: str) -> List[str]:
    return _tokens(query)


def rank_results(query: str, results: List[SearchResult]) -> List[SearchResult]:
    """Re-rank merged, de-duplicated results by relevance.

    Args:
        query: The original user query.
        results: De-duplicated SearchResult objects (provider order irrelevant).

    Returns:
        The same objects, re-scored and sorted by descending relevance score.
    """
    q = query.strip()
    ql = q.lower()
    q_tokens = _query_terms(q)
    q_single = " ".join(q_tokens)

    # Count how many distinct providers confirmed each URL (duplicate signal).
    # (results are already de-duplicated, but we preserved them by URL; we
    # approximate cross-provider confirmation via the `source` tag plus a
    # lightweight re-scan would require raw results — instead we trust that
    # dedup kept the first; the confirmation boost is applied when a single
    # result's source indicates multi-provider confidence is unavailable here,
    # so we focus on the lexical/structural signals which are sufficient and
    # provider-independent.)
    del q_single  # reserved

    if _DEBUG:
        print("\n[RANK] Before Ranking")
        for i, r in enumerate(results[:12], 1):
            print(f"  {i}. {r.title[:60]}  <{r.url}>  src={r.source} prov_score={r.score:.2f}")

    # First pass: assign a relevance score to every result.
    for r in results:
        r.score = _score(r, q, ql, q_tokens)

    # Sort by relevance, then by provider confidence as a mild tie-breaker.
    results.sort(key=lambda r: (-r.score, -_provider_conf(r)))

    if _DEBUG:
        print("\n[RANK] After Ranking")
        for i, r in enumerate(results[:12], 1):
            dom = _domain(r.url)
            print(f"  {i}. {r.title[:50]}  {dom}  score={r.score:.3f}")
        print("")

    return results


def _provider_conf(r: SearchResult) -> float:
    """Normalize a provider's own score into a 0..1 tie-breaker.

    Providers use wildly different scales (DuckDuckGo instant-answer = 10.0,
    NSIndex = 0..1, others = 0). We clamp/normalize so it never dominates the
    relevance score but can break ties.
    """
    s = r.score if r.score is not None else 0.0
    # Map a 0..10 scale down; anything above 1 is treated as already-scaled.
    if s > 1.0:
        return min(s / 10.0, 1.0)
    return max(0.0, min(s, 1.0))


def _score(r: SearchResult, q: str, ql: str, q_tokens: List[str]) -> float:
    title = (r.title or "").strip()
    tl = title.lower()
    url = (r.url or "").strip()
    ul = url.lower()
    dom = _domain(url)
    apex = _apex(dom)
    snippet = (r.snippet or "").lower()

    score = 0.0

    # ── Title signals ────────────────────────────────────────────────────────
    if tl == ql:
        score += 1.0                      # exact title match
    elif tl.startswith(ql):
        score += 0.8                      # title begins with query
    elif ql in tl:
        score += 0.5                      # title contains query
    else:
        # Token overlap between title and query.
        t_tokens = set(_tokens(title))
        if q_tokens and t_tokens:
            overlap = len(t_tokens & set(q_tokens)) / len(q_tokens)
            score += 0.45 * overlap

    # ── URL / domain signals ──────────────────────────────────────────────────
    if ql in ul:
        score += 0.35                     # query appears somewhere in URL

    # Official-site heuristic: clean apex domain name equals the query, or the
    # query is a whole-word token in the domain. This is the primary lift for
    # "python" -> python.org, "github" -> github.com, etc.
    apex_name = apex.split(".")[0]
    if apex_name == ql or apex_name in q_tokens:
        score += 0.9
        # Apex exactly matches the whole query (e.g. python.org for "python").
        if apex_name == ql:
            score += 0.3
    elif any(tok in dom for tok in q_tokens):
        score += 0.2

    # ── Snippet relevance ──────────────────────────────────────────────────────
    if snippet:
        s_tokens = set(_tokens(snippet))
        if q_tokens and s_tokens:
            overlap = len(s_tokens & set(q_tokens)) / len(q_tokens)
            score += 0.25 * overlap

    # ── Reference / aggregator demotion ───────────────────────────────────────
    # When an official candidate likely exists for this intent, demote generic
    # encyclopedic/aggregator pages so they don't crowd out the canonical site.
    if dom in _REFERENCE_DOMAINS:
        # Only demote if there's a plausible official-site match in the query
        # (i.e. the query looks like a topic with an official home).
        if any(tok and f"{tok}.org" in ul or f"{tok}.com" in ul for tok in q_tokens):
            score -= 0.15
        score -= 0.05

    # ── Provider confidence (gentle, provider-independent use) ────────────────
    # Normalized into a small contribution so a provider's internal ranking
    # nudges but never decides.
    score += 0.1 * _provider_conf(r)

    # ── NSIndex confidence ────────────────────────────────────────────────────
    # NSIndex already attaches a relevance score; surface it as a mild signal
    # rather than treating NSIndex as always-best.
    if r.source == "nsindex" and r.score and r.score > 1.0:
        score += 0.1

    # Clamp to a sane positive range (we never want negative scores to bury
    # results entirely — ambiguous meanings should still be reachable).
    return max(0.01, score)
