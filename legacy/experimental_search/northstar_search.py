"""
northstar_search.py — NorthStar Search System V2 (Hybrid Edition)
======================================================================
Provides a hybrid pipeline (Web / Multi-Provider).
The public interface is identical to V1.

Public surface
--------------
  NorthStarSearch.is_url(text)          → bool
  NorthStarSearch.format_url(text)      → str
  NorthStarSearch.build_search_url(q)   → str   (Web search fallback URL)
  NorthStarSearch.handle_query(text)    → str
  NorthStarSearch.fetch_opal_results(q) → list[dict]

Result dict keys
----------------
  title       str   Page title
  url         str   Target URL
  snippet     str   Description snippet
  display_url str   Formatted URL for display
  domain      str   Root domain
  favicon     str   Favicon URL
  thumbnail   str   Thumbnail image URL, or "" if none
  pageid      int   Source ID (0 if unknown)
"""

from __future__ import annotations

import os
import re
import threading
import json
import time
from abc import ABC, abstractmethod
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, quote_plus, urlparse, unquote
from pathlib import Path
from difflib import SequenceMatcher

def _load_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

_load_env()

import requests
from PIL import Image
import io

# ── Debug toggle ──────────────────────────────────────────────────────────────
_DEBUG: bool = os.environ.get("NS_DEBUG", "").lower() in ("1", "true", "yes")

def _log(tag: str, msg: str) -> None:
    if _DEBUG:
        print(f"[OPAL:SEARCH:{tag}] {msg}", flush=True)


# ── Query Type Config ────────────────────────────────────────────────────────
def _load_query_type_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "opal_query_types.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _log("CONFIG", f"Failed to load query types config: {e}")
        return {"query_types": {}, "default_type": "concept"}

_QUERY_TYPE_CONFIG = _load_query_type_config()


def detect_query_type(query: str) -> dict:
    """Lightweight JSON-driven query type detection!
    Uses weighted keyword and pattern scoring!
    """
    q_lower = query.lower()
    query_types = _QUERY_TYPE_CONFIG.get("query_types", {})
    default_type = _QUERY_TYPE_CONFIG.get("default_type", "concept")
    pattern_score_weight = _QUERY_TYPE_CONFIG.get("pattern_score", 5.0)
    keyword_score_weight = _QUERY_TYPE_CONFIG.get("keyword_score", 1.0)
    
    best_type = default_type
    best_score = 0.0
    
    for type_name, type_data in query_types.items():
        score = 0.0
        
        # Check keywords
        keywords = type_data.get("keywords", [])
        for kw in keywords:
            if kw in q_lower:
                score += keyword_score_weight
                
        # Check patterns (regex)
        patterns = type_data.get("patterns", [])
        for pat in patterns:
            try:
                if re.search(pat, q_lower):
                    score += pattern_score_weight
            except Exception as e:
                _log("PATTERN", f"Pattern error {pat}: {e}")
                
        # Update best type if score is higher
        if score > best_score:
            best_score = score
            best_type = type_name
            
    return {
        "type": best_type,
        "data": query_types.get(best_type, {}),
        "config": _QUERY_TYPE_CONFIG
    }


# ── Search Constants ─────────────────────────────────────────────────────────
_DDG_API       = "https://api.duckduckgo.com/"
_DDG_ICON_SRV  = "https://icons.duckduckgo.com/ip3/"
_DDG_SEARCH    = "https://duckduckgo.com/?q="

_WEB_TIMEOUT     = 4   # seconds — general web search (reduced for speed)
_SUMMARY_TIMEOUT = 2   # seconds — per-article summary REST call (reduced for speed)
_MAX_WORKERS     = 10  # parallel fetches
_IMG_RESIZE_VAL  = 400 # Fixed width/height for forced resizer
ENABLE_MEDIA_FETCH: bool = False # Temporarily disable media fetching entirely

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive"
}

def _safe_request(url: str, method: str = "GET", params: dict = None, headers: dict = None, timeout: int = _WEB_TIMEOUT, retries: int = 1) -> requests.Response | None:
    """Make a safe HTTP request with validation and retries!"""
    session = requests.Session()
    session.headers.update(headers or _HEADERS)
    
    for attempt in range(retries + 1):
        try:
            resp = session.request(
                method=method,
                url=url,
                params=params,
                timeout=timeout,
                allow_redirects=True
            )
            
            if resp.status_code == 202:
                _log("SAFE_REQ", f"Got 202 for {url}, retrying in 0.5s...")
                time.sleep(0.5)
                continue
                
            if not resp.ok:
                _log("SAFE_REQ", f"Request failed for {url}: {resp.status_code}")
                return None
                
            return resp
        except Exception as e:
            _log("SAFE_REQ", f"Request exception for {url}: {str(e)}")
            if attempt < retries:
                time.sleep(0.3)
                continue
            return None
    return None

def _safe_json_parse(resp: requests.Response | None) -> dict | None:
    """Safely parse JSON from a response!"""
    if not resp:
        return None
    try:
        return resp.json()
    except Exception as e:
        _log("SAFE_JSON", f"JSON parse failed: {str(e)}")
        return None

_CANONICAL_MAPPINGS = {
    # Social & Video
    "youtube": "https://youtube.com",
    "youtube studio": "https://studio.youtube.com",
    "youtube music": "https://music.youtube.com",
    "twitch": "https://twitch.tv",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "instagram": "https://instagram.com",
    "tiktok": "https://tiktok.com",
    "facebook": "https://facebook.com",
    "reddit": "https://reddit.com",
    "linkedin": "https://linkedin.com",
    
    # Google Products
    "google": "https://google.com",
    "google search": "https://google.com",
    "google docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "google slides": "https://slides.google.com",
    "google drive": "https://drive.google.com",
    "google meet": "https://meet.google.com",
    "google calendar": "https://calendar.google.com",
    "gmail": "https://gmail.com",
    "google maps": "https://maps.google.com",
    "google photos": "https://photos.google.com",
    "google play": "https://play.google.com",
    "chrome": "https://google.com/chrome",
    "google chrome": "https://google.com/chrome",
    
    # Microsoft Products
    "microsoft": "https://microsoft.com",
    "windows": "https://microsoft.com/windows",
    "office": "https://office.com",
    "microsoft office": "https://office.com",
    "word": "https://office.com",
    "excel": "https://office.com",
    "powerpoint": "https://office.com",
    "outlook": "https://outlook.com",
    "teams": "https://teams.microsoft.com",
    "microsoft teams": "https://teams.microsoft.com",
    "onedrive": "https://onedrive.com",
    "edge": "https://microsoft.com/edge",
    "bing": "https://bing.com",
    "github": "https://github.com",
    "github copilot": "https://github.com/copilot",
    
    # Development & Tech
    "stack overflow": "https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "gitlab": "https://gitlab.com",
    "bitbucket": "https://bitbucket.org",
    "npm": "https://npmjs.com",
    "npmjs": "https://npmjs.com",
    "pypi": "https://pypi.org",
    "python": "https://python.org",
    "nodejs": "https://nodejs.org",
    "node.js": "https://nodejs.org",
    "react": "https://react.dev",
    "reactjs": "https://react.dev",
    "vue": "https://vuejs.org",
    "vue.js": "https://vuejs.org",
    "angular": "https://angular.io",
    "docker": "https://docker.com",
    "kubernetes": "https://kubernetes.io",
    "aws": "https://aws.amazon.com",
    "amazon web services": "https://aws.amazon.com",
    "azure": "https://azure.microsoft.com",
    "gcp": "https://cloud.google.com",
    "google cloud": "https://cloud.google.com",
    "vercel": "https://vercel.com",
    "netlify": "https://netlify.com",
    
    # Apple Products
    "apple": "https://apple.com",
    "iphone": "https://apple.com/iphone",
    "mac": "https://apple.com/mac",
    "macbook": "https://apple.com/macbook",
    "ipad": "https://apple.com/ipad",
    "watch": "https://apple.com/watch",
    "apple watch": "https://apple.com/watch",
    "safari": "https://apple.com/safari",
    "icloud": "https://icloud.com",
    
    # Other Products & Services
    "spotify": "https://spotify.com",
    "netflix": "https://netflix.com",
    "hulu": "https://hulu.com",
    "disney+": "https://disneyplus.com",
    "disney plus": "https://disneyplus.com",
    "amazon": "https://amazon.com",
    "amazon prime": "https://primevideo.com",
    "ebay": "https://ebay.com",
    "wikipedia": "https://wikipedia.org",
    "wikimedia": "https://wikimedia.org",
    "duckduckgo": "https://duckduckgo.com",
    "ddg": "https://duckduckgo.com",
}

_DOMAIN_REPUTATION = {
    # High Authority / Docs
    "github.com":          "high",
    "stackoverflow.com":   "high",
    "developer.mozilla.org": "high",
    "docs.python.org":     "high",
    "w3schools.com":       "medium",
    "geeksforgeeks.org":   "medium",
    "reddit.com":          "medium",
    "medium.com":          "medium",
    "dev.to":              "medium",
    "youtube.com":         "medium",
    "twitter.com":         "medium",
    "news.ycombinator.com": "high",
    "microsoft.com":       "high",
    "apple.com":           "high",
    "google.com":          "high",
    
    # News
    "reuters.com":         "high",
    "apnews.com":          "high",
    "bbc.com":             "high",
    "nytimes.com":         "high",
    "theguardian.com":     "high",
    "bloomberg.com":       "high",
    "wsj.com":             "high",
    
    # Low Quality / Often Unrelated / Legal disputes noise
    "justia.com":          "low",
    "law.cornell.edu":     "low",
    "courtlistener.com":   "low",
    "caselaw.findlaw.com": "low",
    "pacer.gov":           "ignore",
    "leagle.com":          "low",
    "trellis.law":         "low",
    "docketalarm.com":     "low",
    
    # Generic search aggregators / low value links
    "duckduckgo.com":      "ignore",
    "search.duckduckgo.com": "ignore",
    "bing.com":            "ignore",
    "google.com":          "ignore",
    "yahoo.com":           "ignore",
    "ask.com":             "ignore",
    "aol.com":             "ignore",
}

_REPUTATION_BOOST = {
    "high": 10.0,
    "medium": 3.0,
    "low": -5.0,
    "ignore": -20.0
}

_PROVIDER_WEIGHTS = {
    "ddg-api": 15.0,
    "ddg-lite": 10.0,
    "ddg": 8.0,
    "bing": 7.0,
    "google": 6.0,
    "direct-domain": 20.0,
    "related_links": 25.0,
    "serpapi": 20.0
}
# NSIndex providers get the highest weight through the explicit boost in fetch_opal_results

# ─────────────────────────────────────────────────────────────────────────────
#  PROVIDER SYSTEM (Abstraction Layer)
# ─────────────────────────────────────────────────────────────────────────────

class SearchProvider(ABC):
    """Abstract base class for search providers."""
    def __init__(self, name: str, timeout: int = _WEB_TIMEOUT):
        self.name = name
        self.timeout = timeout

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Execute search and return normalized results."""
        pass

    def image_search(self, query: str, limit: int = 8) -> list[dict]:
        """Execute image search and return normalized results (optional)."""
        return []

    def _normalize_result(self, title: str, url: str, snippet: str = "") -> dict | None:
        """Helper to create a standard result dictionary."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if not domain:
                return None
            
            return {
                "title": re.sub(r'<[^>]+>', '', title).strip(),
                "url": url,
                "snippet": re.sub(r'<[^>]+>', '', snippet).strip(),
                "display_url": domain,
                "domain": domain,
                "favicon": f"{_DDG_ICON_SRV}{domain}.ico",
                "thumbnail": "",
                "pageid": 0,
                "provider": self.name
            }
        except Exception:
            return None

class DDGProvider(SearchProvider):
    """DuckDuckGo scraper (HTML/Lite)."""
    def __init__(self, endpoint: str = "https://duckduckgo.com/html/"):
        super().__init__("ddg")
        self.endpoint = endpoint

    def search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            resp = _safe_request(
                self.endpoint,
                params={"q": query},
                timeout=self.timeout
            )
            if not resp:
                return []
            
            html = resp.text
            results = []
            
            title_matches = list(re.finditer(r'<a\s+class="result__a|result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL))
            snippet_matches = list(re.finditer(r'<(a|td)\s+class="result__snippet|result-snippet"[^>]*>(.*?)</\1>', html, re.DOTALL))
            
            for i in range(min(len(title_matches), limit)):
                match_t = title_matches[i]
                raw_url = match_t.group(1)
                
                if "/l/?uddg=" in raw_url:
                    try: url = unquote(raw_url.split("uddg=")[1].split("&")[0])
                    except Exception: url = raw_url
                else: url = raw_url
                
                title = match_t.group(2)
                snippet = ""
                if i < len(snippet_matches):
                    snippet = snippet_matches[i].group(2)
                
                res = self._normalize_result(title, url, snippet)
                if res: results.append(res)
                
            return results
        except Exception as exc:
            _log("DDG_EXC", str(exc))
            return []

class DDGLiteProvider(SearchProvider):
    """DuckDuckGo Lite scraper (FASTER!)."""
    def __init__(self):
        super().__init__("ddg-lite")
        self.endpoint = "https://lite.duckduckgo.com/lite/"

    def search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            session = requests.Session()
            session.headers.update(_HEADERS)
            session.get("https://duckduckgo.com/", timeout=2)
            
            resp = _safe_request(
                self.endpoint,
                params={"q": query},
                headers=_HEADERS,
                timeout=self.timeout
            )
            if not resp:
                return []
            
            html = resp.text
            results = []
            
            link_matches = list(re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL))
            snippet_matches = list(re.finditer(r'<td[^>]*>(.*?)</td>', html, re.DOTALL))
            
            for i in range(min(len(link_matches), limit)):
                match = link_matches[i]
                raw_url = match.group(1)
                title = match.group(2)
                
                if not title or "duckduckgo" in title.lower():
                    continue
                
                if "/l/?uddg=" in raw_url:
                    try: url = unquote(raw_url.split("uddg=")[1].split("&")[0])
                    except Exception: url = raw_url
                else: url = raw_url
                
                snippet = ""
                if i < len(snippet_matches):
                    snippet = snippet_matches[i].group(1)
                
                res = self._normalize_result(title, url, snippet)
                if res: results.append(res)
                
            return results
        except Exception as exc:
            _log("DDG_LITE_EXC", str(exc))
            return []

class DirectDomainGuesserProvider(SearchProvider):
    """Direct domain guesser: tries common TLDs for the query (super fast!)."""
    def __init__(self):
        super().__init__("direct-domain")
        self.tlds = [".com", ".org", ".net", ".io", ".co", ".ai", ".app"]
    
    def search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            # Clean query for domain: remove spaces, special chars
            clean_query = re.sub(r'[^a-zA-Z0-9]', '', query.lower().replace(" ", ""))
            if not clean_query:
                return []
            
            results = []
            for tld in self.tlds:
                domain = clean_query + tld
                url = "https://" + domain
                results.append({
                    "title": f"{query} - {domain}",
                    "url": url,
                    "snippet": f"Direct domain guess for {query}",
                    "domain": domain,
                    "favicon": f"{_DDG_ICON_SRV}{domain}.ico",
                    "thumbnail": "",
                    "pageid": 0,
                    "provider": "direct-domain"
                })
                if len(results) >= limit:
                    break
            
            return results
        except Exception as exc:
            _log("DOMAIN_GUESSER_EXC", str(exc))
            return []



class BingProvider(SearchProvider):
    """Bing Search scraper."""
    def __init__(self):
        super().__init__("bing")
        self.endpoint = "https://www.bing.com/search"

    def search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            resp = _safe_request(self.endpoint, params={"q": query}, timeout=self.timeout)
            if not resp:
                return []
            
            matches = re.finditer(r'<li class="b_algo"><h2><a href="([^"]+)"[^>]*>(.*?)</a>', resp.text)
            results = []
            for match in matches:
                res = self._normalize_result(match.group(2), match.group(1))
                if res: results.append(res)
                if len(results) >= limit: break
            return results
        except Exception:
            return []

class GoogleProvider(SearchProvider):
    """Google Search scraper (fallback)."""
    def __init__(self):
        super().__init__("google")
        self.endpoint = "https://www.google.com/search"

    def search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            resp = _safe_request(self.endpoint, params={"q": query, "gbv": "1"}, timeout=self.timeout)
            if not resp:
                return []
            
            matches = re.finditer(r'<a href="/url\?q=([^&"]+)[^>]*><div[^>]*>(.*?)</div>', resp.text)
            results = []
            for match in matches:
                url = unquote(match.group(1))
                if url.startswith("/"): continue
                res = self._normalize_result(match.group(2), url)
                if res: results.append(res)
                if len(results) >= limit: break
            
            if not results:
                matches = re.finditer(r'<a[^>]*href="/url\?q=([^&"]+)[^>]*><h3[^>]*>(.*?)</h3>', resp.text)
                for match in matches:
                    url = unquote(match.group(1))
                    if url.startswith("/"): continue
                    res = self._normalize_result(match.group(2), url)
                    if res: results.append(res)
                    if len(results) >= limit: break
                    
            return results
        except Exception:
            return []

class DDGAPIProvider(SearchProvider):
    """DuckDuckGo Instant Answer API (Official)."""
    def __init__(self):
        super().__init__("ddg-api", timeout=4)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            params = {
                "q":      query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1"
            }
            resp = _safe_request(_DDG_API, params=params, timeout=self.timeout)
            data = _safe_json_parse(resp)
            if not data:
                return []
            
            results = []
            
            if data.get("AbstractURL"):
                res = self._normalize_result(
                    data.get("Heading", query),
                    data.get("AbstractURL"),
                    data.get("AbstractText", "")
                )
                if res: results.append(res)
            
            for topic in data.get("RelatedTopics", []):
                if "FirstURL" in topic:
                    res = self._normalize_result(
                        topic.get("Text", "").split(" - ")[0],
                        topic.get("FirstURL"),
                        topic.get("Text", "")
                    )
                    if res: results.append(res)
                if len(results) >= limit: break
                
            return results
        except Exception:
            return []


class SerpAPIProvider(SearchProvider):
    """SerpAPI Search Provider - Google Search API."""
    SERPAPI_ENDPOINT = "https://serpapi.com/search.json"

    def __init__(self):
        super().__init__("serpapi", timeout=10)
        self.api_key = os.environ.get("SERPAPI_API_KEY", "")

    def search(self, query: str, limit: int = 10) -> list[dict]:
        if not self.api_key:
            _log("SERPAPI", "No API key configured, skipping")
            return []
        try:
            params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google",
                "num": min(limit, 20),
                "hl": "en",
                "gl": "us"
            }
            resp = _safe_request(self.SERPAPI_ENDPOINT, params=params, timeout=self.timeout)
            data = _safe_json_parse(resp)
            if not data:
                return []
            results = []
            for r in data.get("organic_results", []):
                res = self._normalize_result(
                    r.get("title", ""),
                    r.get("link", ""),
                    r.get("snippet", "")
                )
                if res:
                    results.append(res)
                if len(results) >= limit:
                    break
            return results
        except Exception as exc:
            _log("SERPAPI_ERR", f"SerpAPI search failed: {exc}")
            return []

    def image_search(self, query: str, limit: int = 8) -> list[dict]:
        if not self.api_key:
            return []
        try:
            params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google",
                "tbm": "isch",
                "num": min(limit, 20)
            }
            resp = _safe_request(self.SERPAPI_ENDPOINT, params=params, timeout=self.timeout)
            data = _safe_json_parse(resp)
            if not data:
                return []
            results = []
            for r in data.get("images_results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "img_src": r.get("original", ""),
                    "thumbnail": r.get("thumbnail", ""),
                    "source": r.get("source", "")
                })
                if len(results) >= limit:
                    break
            return results
        except Exception as exc:
            _log("SERPAPI_IMG_ERR", f"SerpAPI image search failed: {exc}")
            return []

    def video_search(self, query: str, limit: int = 8) -> list[dict]:
        if not self.api_key:
            return []
        try:
            params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google",
                "tbm": "vid",
                "num": min(limit, 20)
            }
            resp = _safe_request(self.SERPAPI_ENDPOINT, params=params, timeout=self.timeout)
            data = _safe_json_parse(resp)
            if not data:
                return []
            results = []
            for r in data.get("video_results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "img_src": r.get("thumbnail", ""),
                    "thumbnail": r.get("thumbnail", ""),
                    "source": r.get("source", ""),
                    "duration": r.get("duration", "")
                })
                if len(results) >= limit:
                    break
            return results
        except Exception as exc:
            _log("SERPAPI_VID_ERR", f"SerpAPI video search failed: {exc}")
            return []


class CuratedSerpAPIProvider(SerpAPIProvider):
    """Curated SerpAPI provider with health tracking."""
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.name = config["name"]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        import time
        try:
            start = time.time()
            results = super().search(query, limit)
            elapsed = (time.time() - start) * 1000
            if results:
                _mark_provider_success(self.name)
                _log("CORAL-009", f"Provider Selected: {self.name}")
                _log("CORAL-009", f"Search Time: {elapsed:.0f}ms")
                _log("CORAL-009", f"Results Returned: {len(results)}")
            else:
                _mark_provider_failure(self.name)
            return results
        except Exception:
            _mark_provider_failure(self.name)
            return []

    def image_search(self, query: str, limit: int = 8) -> list[dict]:
        try:
            results = super().image_search(query, limit)
            if results:
                _mark_provider_success(self.name)
            else:
                _mark_provider_failure(self.name)
            return results
        except Exception:
            _mark_provider_failure(self.name)
            return []

    def video_search(self, query: str, limit: int = 8) -> list[dict]:
        try:
            results = super().video_search(query, limit)
            if results:
                _mark_provider_success(self.name)
            else:
                _mark_provider_failure(self.name)
            return results
        except Exception:
            _mark_provider_failure(self.name)
            return []


class SearXNGProvider(SearchProvider):
    """SearXNG Search (Privacy-focused aggregator)."""
    def __init__(self, instance: str = "https://searx.work"):
        super().__init__("searxng")
        self.endpoint = f"{instance}/search"

    def search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            params = {
                "q": query,
                "format": "json",
                "categories": "general"
            }
            resp = _safe_request(self.endpoint, params=params, timeout=self.timeout)
            data = _safe_json_parse(resp)
            if not data:
                return []
            
            results = []
            for r in data.get("results", []):
                res = self._normalize_result(r.get("title", ""), r.get("url", ""), r.get("content", ""))
                if res: results.append(res)
                if len(results) >= limit: break
            return results
        except Exception:
            return []

    def image_search(self, query: str, limit: int = 8) -> list[dict]:
        try:
            params = {
                "q": query,
                "format": "json",
                "categories": "images"
            }
            resp = _safe_request(self.endpoint, params=params, timeout=self.timeout)
            data = _safe_json_parse(resp)
            if not data:
                return []
            
            results = []
            for r in data.get("results", []):
                if not r.get("img_src"): continue
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "img_src": r.get("img_src", ""),
                    "thumbnail": r.get("thumbnail", ""),
                    "source": r.get("source", "")
                })
                if len(results) >= limit: break
            return results
        except Exception as e:
            _log("SEARX_IMG_ERR", f"Image search failed: {e}")
            return []
            
    def video_search(self, query: str, limit: int = 8) -> list[dict]:
        try:
            params = {
                "q": query,
                "format": "json",
                "categories": "videos"
            }
            resp = _safe_request(self.endpoint, params=params, timeout=self.timeout)
            data = _safe_json_parse(resp)
            if not data:
                return []
            
            results = []
            for r in data.get("results", []):
                if not (r.get("img_src") or r.get("thumbnail")):
                    continue
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "img_src": r.get("img_src", "") or r.get("thumbnail", ""),
                    "thumbnail": r.get("thumbnail", ""),
                    "source": r.get("source", ""),
                    "duration": r.get("duration", "")
                })
                if len(results) >= limit: break
            return results
        except Exception as e:
            _log("SEARX_VID_ERR", f"Video search failed: {e}")
            return []

# ── Curated Provider Registry ───────────────────────────────────────────────
_CURATED_PROVIDERS = [
    {
        "name": "privacyredirect",
        "type": "searxng",
        "endpoint": "https://search.privacyredirect.com/",
        "weight": 10.0,
        "enabled": True,
        "health_score": 1.0,
        "last_used": 0.0,
        "failures": 0,
        "cooldown_until": 0.0
    },
    {
        "name": "ddg-lite",
        "type": "ddg-lite",
        "endpoint": "https://lite.duckduckgo.com/lite/",
        "weight": 8.0,
        "enabled": True,
        "health_score": 1.0,
        "last_used": 0.0,
        "failures": 0,
        "cooldown_until": 0.0
    },
    {
        "name": "ddg",
        "type": "ddg",
        "endpoint": "https://duckduckgo.com/html/",
        "weight": 7.0,
        "enabled": True,
        "health_score": 1.0,
        "last_used": 0.0,
        "failures": 0,
        "cooldown_until": 0.0
    },
    {
        "name": "serpapi",
        "type": "serpapi",
        "endpoint": "https://serpapi.com/search.json",
        "weight": 20.0,
        "enabled": True,
        "health_score": 1.0,
        "last_used": 0.0,
        "failures": 0,
        "cooldown_until": 0.0
    }
]

_PROVIDER_FAILURE_THRESHOLD = 3
_PROVIDER_COOLDOWN_SECONDS = 60

def _get_enabled_providers() -> list[dict]:
    """Get list of enabled, non-cooldown providers, sorted by health score and weight."""
    now = time.time()
    enabled = []
    for p in _CURATED_PROVIDERS:
        if not p["enabled"]:
            continue
        if p["cooldown_until"] > now:
            continue
        enabled.append(p)
    
    enabled.sort(key=lambda x: (-x["health_score"], -x["weight"], x["failures"]))
    return enabled

def _mark_provider_failure(provider_name: str) -> None:
    """Mark a provider as failed and apply cooldown if needed."""
    for p in _CURATED_PROVIDERS:
        if p["name"] == provider_name:
            p["failures"] += 1
            p["health_score"] = max(0.0, p["health_score"] - 0.2)
            if p["failures"] >= _PROVIDER_FAILURE_THRESHOLD:
                p["cooldown_until"] = time.time() + _PROVIDER_COOLDOWN_SECONDS
                p["failures"] = 0
            break

def _mark_provider_success(provider_name: str) -> None:
    """Mark a provider as successful and improve health score."""
    for p in _CURATED_PROVIDERS:
        if p["name"] == provider_name:
            p["last_used"] = time.time()
            p["failures"] = max(0, p["failures"] - 1)
            p["health_score"] = min(1.0, p["health_score"] + 0.1)
            break

class CuratedSearXNGProvider(SearXNGProvider):
    """Curated SearXNG provider with health tracking."""
    def __init__(self, config: dict):
        super().__init__(config["endpoint"])
        self.config = config
        self.name = config["name"]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            results = super().search(query, limit)
            if results:
                _mark_provider_success(self.name)
            else:
                _mark_provider_failure(self.name)
            return results
        except Exception:
            _mark_provider_failure(self.name)
            return []

    def image_search(self, query: str, limit: int = 8) -> list[dict]:
        try:
            results = super().image_search(query, limit)
            if results:
                _mark_provider_success(self.name)
            else:
                _mark_provider_failure(self.name)
            return results
        except Exception:
            _mark_provider_failure(self.name)
            return []
            
    def video_search(self, query: str, limit: int = 8) -> list[dict]:
        try:
            results = super().video_search(query, limit)
            if results:
                _mark_provider_success(self.name)
            else:
                _mark_provider_failure(self.name)
            return results
        except Exception:
            _mark_provider_failure(self.name)
            return []

class CuratedDDGLiteProvider(DDGLiteProvider):
    """Curated DDG Lite provider with health tracking."""
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.name = config["name"]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            results = super().search(query, limit)
            if results:
                _mark_provider_success(self.name)
            else:
                _mark_provider_failure(self.name)
            return results
        except Exception:
            _mark_provider_failure(self.name)
            return []

class CuratedDDGProvider(DDGProvider):
    """Curated DDG provider with health tracking."""
    def __init__(self, config: dict):
        super().__init__(config["endpoint"])
        self.config = config
        self.name = config["name"]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            results = super().search(query, limit)
            if results:
                _mark_provider_success(self.name)
            else:
                _mark_provider_failure(self.name)
            return results
        except Exception:
            _mark_provider_failure(self.name)
            return []

class CuratedProviderEngine:
    """Executes curated providers in priority order with failover."""
    def __init__(self):
        self.providers = {}
        for p_config in _CURATED_PROVIDERS:
            if p_config["type"] == "searxng":
                self.providers[p_config["name"]] = CuratedSearXNGProvider(p_config)
            elif p_config["type"] == "ddg-lite":
                self.providers[p_config["name"]] = CuratedDDGLiteProvider(p_config)
            elif p_config["type"] == "ddg":
                self.providers[p_config["name"]] = CuratedDDGProvider(p_config)
            elif p_config["type"] == "serpapi":
                self.providers[p_config["name"]] = CuratedSerpAPIProvider(p_config)

    def execute(self, query: str, limit: int = 10, on_result=None) -> list[dict]:
        all_results = []
        seen_urls = set()
        
        enabled_providers = _get_enabled_providers()
        _log("ENGINE", f"Executing {len(enabled_providers)} curated providers for {query!r}")
        
        for p_config in enabled_providers:
            provider = self.providers.get(p_config["name"])
            if not provider:
                continue
                
            try:
                results = provider.search(query, limit)
                if results:
                    _log("ENGINE", f"Provider {p_config['name']} returned {len(results)} results")
                    for r in results:
                        url = r["url"].rstrip("/")
                        if url not in seen_urls:
                            all_results.append(r)
                            seen_urls.add(url)
                            if on_result:
                                on_result(r)
                else:
                    _log("ENGINE", f"Provider {p_config['name']} returned 0 results")
            except Exception as exc:
                _log("ENGINE_ERR", f"Provider {p_config['name']} failed: {exc}")
                continue
        
        _log("ENGINE", f"Total results found: {len(all_results)}")
        return all_results

    def execute_images(self, query: str, limit: int = 12) -> list[dict]:
        all_images = []
        seen_imgs = set()
        
        enabled_providers = [p for p in _get_enabled_providers() if p["type"] == "searxng"]
        
        _log("ENGINE", f"Executing image search for {query!r} with {len(enabled_providers)} providers")
        
        for p_config in enabled_providers:
            provider = self.providers.get(p_config["name"])
            if not provider or not hasattr(provider, "image_search"):
                continue
                
            try:
                results = provider.image_search(query, limit)
                if results:
                    _log("ENGINE", f"Provider {p_config['name']} returned {len(results)} images")
                    for r in results:
                        src = r["img_src"]
                        if src not in seen_imgs:
                            all_images.append(r)
                            seen_imgs.add(src)
            except Exception as exc:
                _log("ENGINE_ERR", f"Image provider {p_config['name']} failed: {exc}")
                continue
        
        return all_images[:limit]
        
    def execute_videos(self, query: str, limit: int = 12) -> list[dict]:
        all_videos = []
        seen_urls = set()
        
        enabled_providers = [p for p in _get_enabled_providers() if p["type"] == "searxng"]
        
        _log("ENGINE", f"Executing video search for {query!r} with {len(enabled_providers)} providers")
        
        for p_config in enabled_providers:
            provider = self.providers.get(p_config["name"])
            if not provider or not hasattr(provider, "video_search"):
                continue
                
            try:
                results = provider.video_search(query, limit)
                if results:
                    _log("ENGINE", f"Provider {p_config['name']} returned {len(results)} videos")
                    for r in results:
                        url = r.get("url", "").lower()
                        if url and url not in seen_urls:
                            all_videos.append(r)
                            seen_urls.add(url)
            except Exception as exc:
                _log("ENGINE_ERR", f"Video provider {p_config['name']} failed: {exc}")
                continue
        
        return all_videos[:limit]

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN CLASS
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_data_uri(url: str) -> str:
    """Download an image, resize it to a fixed value, and return it as a base64 data URI."""
    if not url or url.startswith("data:"):
        return url
    try:
        img_headers = _HEADERS.copy()
        img_headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        
        if "raw.githubusercontent.com" in url:
            img_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            img_headers["Accept"] = "image/*"
        
        resp = requests.get(url, headers=img_headers, timeout=5, allow_redirects=True, stream=True)
        if resp.status_code == 200:
            # Read with a hard cap to avoid unbounded memory use from a hostile/large body
            MAX_BYTES = 5 * 1024 * 1024
            chunks = []
            downloaded = 0
            for chunk in resp.iter_content(chunk_size=65536):
                downloaded += len(chunk)
                if downloaded > MAX_BYTES:
                    _log("IMG_PROXY_WARN", f"Image too large (>5MB), aborting proxy for {url}")
                    resp.close()
                    return url
                chunks.append(chunk)
            content = b"".join(chunks)

            # Load image with PIL for 'force resizing'
            try:
                img = Image.open(io.BytesIO(content))
                
                # Convert to RGB if necessary (handles RGBA -> RGB for JPEG/WebP compatibility)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # Force Resize (Fixed value: _IMG_RESIZE_VAL x _IMG_RESIZE_VAL)
                # We use thumbnail or resize. thumbnail maintains aspect ratio. 
                # User asked for 'fixed value', so we'll use a high-quality resize to exactly that.
                img = img.resize((_IMG_RESIZE_VAL, _IMG_RESIZE_VAL), Image.Resampling.LANCZOS)
                
                # Save to buffer as WebP for extreme optimisation
                buf = io.BytesIO()
                img.save(buf, format="WEBP", quality=80, method=6)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                return f"data:image/webp;base64,{b64}"
                
            except Exception as e:
                _log("IMG_PIL_ERR", f"PIL processing failed for {url}: {e}")
                # Fallback to original content if PIL fails
                b64 = base64.b64encode(content).decode("utf-8")
                ctype = resp.headers.get("Content-Type", "image/jpeg")
                return f"data:{ctype};base64,{b64}"
        else:
            _log("IMG_PROXY_WARN", f"Status {resp.status_code} for {url}")
    except Exception as e:
        _log("IMG_PROXY_ERR", f"Failed to proxy {url}: {e}")
    return url

def _is_url(text: str) -> bool:
    """Heuristic: does *text* look like a URL to navigate to (vs. a search)?"""
    text = text.strip()
    if not text or " " in text:
        return False
    # Any scheme:// pattern (http, https, chrome, northstar, file, ftp, opal, …)
    if re.match(r"[A-Za-z][A-Za-z0-9+.-]*://", text):
        return True
    if text == "localhost":
        return True
    # IPv4 literal, e.g. 127.0.0.1
    if re.fullmatch(r"(\d{1,3}\.){3}\d{1,3}", text):
        return True
    # Host with a recognised TLD, e.g. example.com / sub.example.co.uk
    if re.fullmatch(r"[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", text):
        return True
    return False

class NorthStarSearch:
    """Hybrid discovery backend for Opal Discovery with NSIndex integration.
    Now with fast path/smart path distinction, confidence gating, timing, AND caching!
    """

    def __init__(self):
        import uuid
        
        # Initialize the curated provider engine
        self.engine = CuratedProviderEngine()
        
        # Direct domain guesser for preprocessing/omnibox intelligence
        self._domain_guesser = DirectDomainGuesserProvider()
        
        # Initialize NorthStar Runtime!
        from .northstar_runtime import get_runtime
        self.runtime = get_runtime()
        
        # Initialize NSIndex for fast categorized local search
        try:
            from .nsindex.api import get_nsindex
            from .nsindex.cache import LRUCache
            self.nsindex = get_nsindex()
            _log("NSINDEX", "NSIndex system initialized successfully!")
            # Initialize all our caches!
            # Ranking cache (key: normalized_query|domain)
            self.ranking_cache = LRUCache(max_size=5000, ttl_seconds=600)  # 10 mins
            # Load cache for full Phase1 payload (key: normalized_query)
            self.load_cache = LRUCache(max_size=1000, ttl_seconds=300)  #5 mins
            # Domain analysis cache (key: domain)
            self.domain_analysis_cache = LRUCache(max_size=2000, ttl_seconds=3600)  #1hr
        except Exception as e:
            _log("NSINDEX_ERR", f"Failed to initialize NSIndex/caches: {e}")
            self.nsindex = None
            self.ranking_cache = None
            self.load_cache = None
            self.domain_analysis_cache = None
        
        # Track scoring pass count per query
        self._scoring_pass_count = 0

    # ── URL routing ───────────────────────────────────────────────────────────

    def is_url(self, text: str) -> bool:
        return _is_url(text)

    def format_url(self, text: str) -> str:
        """Ensure the URL carries a scheme."""
        text = text.strip()
        if re.match(r"[A-Za-z][A-Za-z0-9+.-]*://", text):
            return text
        return "https://" + text

    def build_search_url(self, query: str) -> str:
        """Return a general web search URL for *query* (used as Opal fallback)."""
        return _DDG_SEARCH + quote_plus(query.strip())

    def handle_query(self, text: str) -> str:
        """Route user input: URL → formatted URL, text → search engine URL."""
        text = text.strip()
        if not text:
            return ""
        if self.is_url(text):
            return self.format_url(text)
        return self.build_search_url(text)

    def _detect_query_intent(self, query: str) -> str:
        """Heuristically categorize the query to influence ranking."""
        q = query.lower()
        
        # Wallpaper / Aesthetic (High priority for image searches)
        wallpaper_keywords = [
            "wallpaper", "background", "4k", "8k", "desktop", "aesthetic", "scenery", 
            "landscape", "portrait", "lockscreen", "minimalist", "wide", "ultrawide", 
            "dual monitor", "setup", "pc", "iphone", "android", "uhd"
        ]
        if any(w in q for w in wallpaper_keywords):
            return "wallpaper"

        # Coding / Tech
        if any(w in q for w in ["how to", "python", "javascript", "code", "error", "install", "git", "api", "doc", "rust", "cpp"]):
            return "tech"
            
        # Factual / Encyclopedic
        if any(q.startswith(w) for w in ["who is", "what is", "where is", "when did", "history of", "definition of"]):
            return "factual"
            
        # News / Recent
        if any(w in q for w in ["news", "latest", "today", "current", "update"]):
            return "news"
            
        return "general"

    # ── Main fetch (called by OpalSearchWorker) ───────────────────────────────

    def _format_nsindex_result(self, site: dict, category: str, source: str = "") -> dict:
        return {
            "title": site["title"],
            "url": site["url"],
            "snippet": site["description"],
            "description": site["description"],
            "display_url": site["url"],
            "domain": site["url"].split("//")[-1].split("/")[0],
            "favicon": f"https://icons.duckduckgo.com/ip3/{site['url'].split('//')[-1].split('/')[0]}.ico",
            "thumbnail": "",
            "pageid": 0,
            "provider": source if source else f"nsindex:{category}",
            "_nsindex_score": site.get("_score", 0),
            "official": site.get("official", False)
        }

    def fetch_phase1_nsindex(self, query: str, coral_timing: dict = None) -> dict:
        """Phase 1: Instant NSIndex-only results!
        Returns immediately, no provider calls!
        Now includes timing, confidence scoring, fast path, AND caching!
        """
        import time
        import uuid
        
        # Reset scoring pass count for new query
        self._scoring_pass_count = 0
        
        # Set new active query token! Invalidate all previous workers!
        self.runtime.set_active_query_token(str(uuid.uuid4()))
        
        normalized_query = query.strip().lower()
        
        # Check load cache first!
        if self.load_cache:
            load_start = time.time()
            cached_result = self.load_cache.get(normalized_query)
            if cached_result:
                load_cache_latency = (time.time() - load_start) * 1000
                if cached_result.get("trusted_ranked"):
                    _log("OPAL:SEARCH:LOADCACHE", f"TRUSTED HIT {query} | retrieved in {load_cache_latency:.1f}ms | SKIPPING FULL RANKING")
                    if coral_timing is not None:
                        coral_timing["retrieval"] = load_cache_latency / 1000
                    return cached_result
                else:
                    _log("OPAL:SEARCH:LOADCACHE", f"PARTIAL HIT {query} | retrieved in {load_cache_latency:.1f}ms | QUICKSCORE MODE")
                
        # Overall Phase1 timing start
        phase1_start = time.time()
        
        timing = dict()
        
        # Preprocessing: Direct domain guesser (omnibox intelligence)
        start = time.time()
        direct_domain_results = self._domain_guesser.search(query, limit=1)
        timing["direct_domain"] = (time.time() - start) * 1000
        
        results = {
            "phase": "phase1",
            "results": [],
            "intent": None,
            "interest_profile": None,
            "timing": timing,
            "confidence": 0.0,
            "skip_phase3": False,
            "fast_path": False,
            "trusted_ranked": False
        }
        
        results["results"].extend(direct_domain_results)
        
        if self.nsindex:
            try:
                start = time.time()
                nsindex_search = self.nsindex.search(query, include_adaptive=True, use_semantic_walls=True)
                timing["nsindex_search"] = (time.time() - start) * 1000
                if coral_timing is not None:
                    coral_timing["retrieval"] = timing["nsindex_search"] / 1000
                
                results["intent"] = nsindex_search.get("intent")
                results["interest_profile"] = nsindex_search.get("interest_profile")
                
                # Add pack results
                for category, sites in nsindex_search["pack_results"].items():
                    for site in sites:
                        results["results"].append(self._format_nsindex_result(site, category))
                
                # Add adaptive index results
                for site in nsindex_search["adaptive_results"]:
                    formatted = self._format_nsindex_result(site, "adaptive", "nsindex:adaptive")
                    results["results"].append(formatted)
                
                _log("PHASE1", f"Delivered {len(results['results'])} NSIndex results for query '{query}'")
            except Exception as e:
                _log("PHASE1_ERR", f"Error getting Phase1 results: {e}")
        
        # Score Phase1 results for initial display
        start = time.time()
        results["results"] = self._score_and_curate(results["results"], query, normalized_query, quickscore=False)
        timing["ranking"] = (time.time() - start) * 1000
        
        # Calculate confidence and decide whether to use fast path!
        confidence_info = self._calculate_phase1_confidence(query, results["results"])
        results["confidence"] = confidence_info["confidence"]
        results["skip_phase3"] = confidence_info["skip_phase3"]
        results["fast_path"] = confidence_info["fast_path"]
        results["trusted_ranked"] = True
        
        # Total Phase1 time!
        results["timing"]["total"] = (time.time() - phase1_start) * 1000
        
        # Log timing!
        _log("PHASE1_TIMING", f"Total Phase1: {results['timing']['total']:.1f}ms | Domain: {results['timing']['direct_domain']:.1f}ms | Search: {results['timing'].get('nsindex_search', 0):.1f}ms | Ranking: {results['timing']['ranking']:.1f}ms")
        _log("PHASE1_CONFIDENCE", f"Query: '{query}' | Confidence: {results['confidence']:.2%} | Skip Phase3: {results['skip_phase3']} | Fast Path: {results['fast_path']}")
        
        # Cache the result!
        if self.load_cache:
            self.load_cache.put(normalized_query, results)
            _log("OPAL:SEARCH:LOADCACHE", f"STORED {query} (TRUSTED_RANKED)")
            
        return results
        
    def _calculate_phase1_confidence(self, query: str, phase1_results: list) -> dict:
        """Calculate lightweight confidence score for Phase1 results.
        Also decides whether to skip Phase3!
        """
        q_lower = query.lower().strip()
        
        confidence = 0.0
        skip_phase3 = False
        fast_path = False
        
        if len(phase1_results) == 0:
            return {"confidence": 0.0, "skip_phase3": False, "fast_path": False}
            
        top_result = phase1_results[0]
        
        # Exact domain match?
        domain = top_result.get("domain", "").lower()
        if domain and q_lower.replace(" ", "") in domain.replace("www.", ""):
            confidence += 0.4
            skip_phase3 = True
            fast_path = True
            _log("CONFIDENCE", "Exact domain match!")
            
        # Exact title match?
        title_lower = top_result.get("title", "").lower()
        if q_lower in title_lower or title_lower.startswith(q_lower):
            confidence += 0.3
            
        # Official site?
        if top_result.get("official", False):
            confidence += 0.2
            skip_phase3 = True
            
        # High score?
        if top_result.get("_score", 0) > 250:
            confidence += 0.1
            
        # Strong NSIndex results count?
        if len(phase1_results) >= 5:
            confidence += 0.05
            
        # Sanity check confidence between 0 and 1
        confidence = min(confidence, 1.0)
        
        return {"confidence": confidence, "skip_phase3": skip_phase3, "fast_path": fast_path}

    def fetch_phase2_providers(self, query: str, callback=None, max_candidate_pool: int = 80, timeout_seconds: float = 2.0, coral_timing: dict = None):
        """Phase 2: Asynchronous provider enrichment in the background!
        Takes a callback to emit results as they are ready. Now with timing and query tokens!
        Also has hard timeout of 2.0 seconds!
        """
        current_token = self.runtime._active_query_token
        
        def _background_fetch():
            import time
            import concurrent.futures
            
            if current_token != self.runtime._active_query_token:
                return
            
            phase2_start = time.time()
            
            try:
                _log("PHASE2", f"Starting Phase2 provider fetch for '{query}' with {timeout_seconds}s timeout")
                timing = dict()
                
                # Get related links (often has the official website!) - no timeout for local thing
                start = time.time()
                related_links = self.fetch_related_links(query)
                timing["related_links"] = (time.time() - start)*1000
                
                official_results = []
                for rel in related_links:
                    official_results.append({
                        "title": rel.get("name", ""),
                        "url": rel.get("url", ""),
                        "snippet": rel.get("description", "Official site for " + query),
                        "domain": urlparse(rel.get("url", "")).netloc,
                        "favicon": rel.get("favicon", ""),
                        "provider": "related_links"
                    })
                
                # Get raw provider results with hard timeout!
                raw_results = []
                start = time.time()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self.engine.execute, query, limit=max_candidate_pool + 50)
                    try:
                        raw_results = future.result(timeout=timeout_seconds)
                        timing["providers"] = (time.time() - start)*1000
                        if coral_timing is not None:
                            coral_timing["candidate_gen"] = timing["providers"] / 1000
                        _log("PHASE2", "Provider fetch completed within timeout")
                    except concurrent.futures.TimeoutError:
                        _log("PHASE2_TIMEOUT", f"Provider fetch timed out after {timeout_seconds}s")
                        raw_results = []
                        timing["providers"] = (time.time() - start)*1000
                        if coral_timing is not None:
                            coral_timing["candidate_gen"] = timing["providers"] / 1000
                
                # Check token again
                if current_token != self.runtime._active_query_token:
                    return
                
                # If we have NO provider results, abandon pipeline! No scoring/dedupe!
                if not (official_results or raw_results):
                    if callback:
                        callback({
                            "phase": "phase2",
                            "results": [],
                            "query": query,
                            "timing": timing
                        })
                    return
                
                # Combine and curate only if we have results
                all_new_results = official_results + list(raw_results)
                start = time.time()
                curated_new_results = self._score_and_curate(all_new_results, query)
                timing["ranking"] = (time.time() - start)*1000
                
                timing["total"] = (time.time() - phase2_start)*1000
                
                _log("PHASE2_TIMING", f"Total Phase2: {timing['total']:.1f}ms | Links: {timing['related_links']:.1f}ms | Providers: {timing['providers']:.1f}ms | Ranking: {timing['ranking']:.1f}ms")
                _log("PHASE2", f"Phase2 complete with {len(curated_new_results)} provider results")
                
                if callback:
                    try:
                        callback({
                            "phase": "phase2",
                            "results": curated_new_results,
                            "query": query,
                            "timing": timing
                        })
                    except Exception as e:
                        _log("PHASE2_CALLBACK_ERR", f"Phase2 callback error: {e}")
            except Exception as e:
                _log("PHASE2_ERR", f"Phase2 failed: {e}")
        
        thread = threading.Thread(target=_background_fetch, daemon=True)
        thread.start()
        return thread

    def fetch_phase3_discovery(self, query: str, callback=None, skip_phase3: bool = False, coral_timing: dict = None):
        """Phase3: Semantic relationship/discovery expansion in background!
        Now with skip_phase3 gating and timing and query tokens!
        """
        if not self.nsindex:
            if coral_timing is not None:
                coral_timing["semantic_expansion"] = 0.0
            return None
            
        if skip_phase3:
            _log("PHASE3_SKIP", f"Skipping Phase3 for query '{query}' (high confidence)")
            if coral_timing is not None:
                coral_timing["semantic_expansion"] = "SKIPPED"
            return None
            
        current_token = self.runtime._active_query_token
        
        def _background_expand():
            import time
            if current_token != self.runtime._active_query_token:
                return
            
            phase3_start = time.time()
            
            try:
                _log("PHASE3", f"Starting Phase3 discovery expansion for '{query}'")
                timing = dict()
                
                start = time.time()
                nsindex_search = self.nsindex.search(query, expand_relationships=True, max_expanded=30)
                timing["search_expand"] = (time.time() - start)*1000
                if coral_timing is not None:
                    coral_timing["semantic_expansion"] = timing["search_expand"] / 1000
                
                # Check token again after potentially slow search
                if current_token != self.runtime._active_query_token:
                    return
                
                expanded_results = []
                for site in nsindex_search.get("expanded_results", []):
                    formatted = self._format_nsindex_result(site, "expanded", "nsindex:expanded")
                    expanded_results.append(formatted)
                
                if not expanded_results:
                    if callback:
                        callback({
                            "phase": "phase3",
                            "results": [],
                            "query": query,
                            "timing": timing
                        })
                    return
                
                start = time.time()
                expanded_results = self._score_and_curate(expanded_results, query)
                timing["ranking"] = (time.time() - start)*1000
                
                timing["total"] = (time.time() - phase3_start)*1000
                
                _log("PHASE3_TIMING", f"Total Phase3: {timing['total']:.1f}ms | Expand Search: {timing['search_expand']:.1f}ms | Ranking: {timing['ranking']:.1f}ms")
                _log("PHASE3", f"Phase3 complete with {len(expanded_results)} expanded results")
                
                if callback:
                    try:
                        callback({
                            "phase": "phase3",
                            "results": expanded_results,
                            "query": query,
                            "timing": timing
                        })
                    except Exception as e:
                        _log("PHASE3_CALLBACK_ERR", f"Phase3 callback error: {e}")
            except Exception as e:
                _log("PHASE3_ERR", f"Phase3 failed: {e}")
        
        thread = threading.Thread(target=_background_expand, daemon=True)
        thread.start()
        return thread

    def _score_and_curate(self, candidate_results: list, query: str, normalized_query: Optional[str] = None, quickscore: bool = False, exclude_domains: Optional[set] = None, exclude_urls: Optional[set] = None) -> list:
        """Helper: Score and curate a list of results (used by all phases)
        Now with pre-rank deduplication, ranking cache, and domain analysis cache!
        Also has QuickScore mode for fast, lightweight scoring!
        """
        import time
        
        _log("ENTER _score_and_curate", f"query: {query}, candidates: {len(candidate_results)}, quickscore: {quickscore}")
        
        # Increment scoring pass counter
        self._scoring_pass_count +=1
        pass_num = self._scoring_pass_count
        
        q_lower = query.lower()
        if not normalized_query:
            normalized_query = q_lower
            
        timing = {}
        start = time.time()
        
        initial_candidate_count = len(candidate_results)
        
        # --- Step 1: Pre-rank deduplication ---
        dedup_start = time.time()
        seen_urls = set(exclude_urls) if exclude_urls else set()
        excluded_domains = set(exclude_domains) if exclude_domains else set()
        # Also deduplicate by domain, keep highest priority source first!
        domain_to_best = {}
        for r in candidate_results:
            url = r.get("url", "").strip()
            url_norm = url.rstrip("/")
            if not r.get("title") or not url:
                continue
            if url_norm in seen_urls:
                continue
                
            domain = r.get("domain", "").lower()
            # Check if domain or any parent domain is excluded!
            is_domain_excluded = False
            domain_parts = domain.split('.')
            for i in range(len(domain_parts)):
                parent_domain = '.'.join(domain_parts[i:])
                if parent_domain in excluded_domains:
                    is_domain_excluded = True
                    break
            if is_domain_excluded:
                continue
            rep = _DOMAIN_REPUTATION.get(domain, "medium")
            if rep == "ignore":
                continue
                
            # Pre-rank source priority (NSIndex > direct domain > related links > others)
            source_priority = 0
            provider = r.get("provider", "")
            if provider.startswith("nsindex:"):
                source_priority = 4
            elif provider == "direct-domain":
                source_priority =3
            elif provider == "related_links":
                source_priority = 2
                
            # Keep the highest priority source per domain/url
            if url_norm in seen_urls:
                continue
            seen_urls.add(url_norm)
            if domain in domain_to_best:
                existing = domain_to_best[domain]
                existing_priority = 0
                ex_prov = existing.get("provider", "")
                if ex_prov.startswith("nsindex:"): existing_priority =4
                elif ex_prov == "direct-domain": existing_priority =3
                elif ex_prov == "related_links": existing_priority =2
                if source_priority > existing_priority:
                    domain_to_best[domain] = r
            else:
                domain_to_best[domain] = r
                
        clean_candidates = list(domain_to_best.values())
        timing["deduplication"] = (time.time() - dedup_start)*1000
        
        # --- Step 2: QuickScore OR Full Score ---
        score_start = time.time()
        scored_candidates = []
        cache_hits = 0
        
        if quickscore:
            _log("OPAL:SEARCH:QUICKSCORE", f"Activated for {len(clean_candidates)} candidates")
            # QuickScore mode: use cached scores, or basic heuristics!
            for r in clean_candidates:
                domain = r.get("domain", "").lower()
                ranking_key = f"{normalized_query}|{domain}"
                
                cached_score = None
                if self.ranking_cache:
                    cached_score = self.ranking_cache.get(ranking_key)
                    if cached_score:
                        cache_hits +=1
                        r["_score"] = cached_score
                        r["_confidence"] = min(max(cached_score / 50.0, 0.1), 0.99)
                        scored_candidates.append(r)
                        continue
                
                # QuickScore heuristics: basic keyword overlap, source priority
                title_lower = r.get("title", "").lower()
                provider = r.get("provider", "")
                
                quick_score = 50
                if provider.startswith("nsindex:"): quick_score +=100
                elif provider == "related_links": quick_score +=60
                elif provider == "direct-domain": quick_score +=40
                
                if q_lower in title_lower: quick_score +=25
                if title_lower.startswith(q_lower): quick_score +=15

                title_ratio = SequenceMatcher(None, q_lower, title_lower).ratio()
                if title_ratio > 0.6:
                    quick_score += int(title_ratio * 10)
                
                r["_score"] = quick_score
                r["_confidence"] = min(max(quick_score /50.0, 0.1),0.99)
                scored_candidates.append(r)
        else:
            # Full score mode!
            intent = self._detect_query_intent(query)
            query_type_info = detect_query_type(query)
            primary_category = query_type_info.get("type", "concept")
            
            for r in clean_candidates:
                domain = r.get("domain", "").lower()
                ranking_key = f"{normalized_query}|{domain}"
                
                cached_score = None
                if self.ranking_cache:
                    cached_score = self.ranking_cache.get(ranking_key)
                    if cached_score:
                        cache_hits +=1
                        _log("CACHE", f"HIT {ranking_key}")
                        r["_score"] = cached_score
                        r["_confidence"] = min(max(cached_score / 50.0, 0.1), 0.99)
                        r["_primary_category"] = primary_category
                        scored_candidates.append(r)
                        continue
                    else:
                        _log("CACHE", f"MISS {ranking_key}")
                        
                title_lower = r.get("title", "").lower()
                snippet_lower = r.get("snippet", "").lower()
                provider = r.get("provider", "")
                
                score = self._calculate_relevance_score(query, r, intent)
                
                if provider.startswith("nsindex:"):
                    score += 100.0
                elif provider == "related_links":
                    score += 60.0
                elif provider == "direct-domain":
                    score += 40.0
                    
                # Likely official boost
                is_likely_official = False
                clean_query_dom = re.sub(r'[^a-z0-9]', '', q_lower)
                clean_domain = re.sub(r'[^a-z0-9]', '', domain.split('.')[0])
                
                if self.domain_analysis_cache:
                    dom_cache_key = domain
                    dom_cached = self.domain_analysis_cache.get(dom_cache_key)
                    if dom_cached:
                        is_likely_official = dom_cached.get("is_likely_official", False)
                    
                if not is_likely_official:
                    if (q_lower in title_lower and ("official" in title_lower or "homepage" in title_lower or title_lower.startswith(q_lower)) or 
                        clean_query_dom == clean_domain or clean_query_dom in clean_domain or
                        not urlparse(r.get("url", "")).path.strip("/")):
                        is_likely_official = True
                        if self.domain_analysis_cache:
                            self.domain_analysis_cache.put(domain, {"is_likely_official": is_likely_official})
                    
                if is_likely_official:
                    score += 80.0
                    
                additional_boost = 0
                if q_lower in title_lower: additional_boost += 25
                if any(kw in domain for kw in ["official", "docs", "documentation", "edu", "gov", "github.com", "gitlab.com", "pypi.org", "npmjs.com"]):
                    additional_boost += 20
                if title_lower.startswith(q_lower): additional_boost += 15
                entity_occurrences = title_lower.count(q_lower) + snippet_lower.count(q_lower)
                if entity_occurrences >=3: additional_boost +=10
                elif entity_occurrences ==2: additional_boost +=5
                elif entity_occurrences ==1: additional_boost +=2
                if q_lower not in title_lower and q_lower not in snippet_lower: additional_boost -=10
                if any(kw in title_lower for kw in ["feastables", "team", "collaboration"]): additional_boost +=3
                if any(kw in title_lower for kw in ["category:", "list of", "people from"]): additional_boost -=15
                    
                final_score = score + additional_boost
                r["_score"] = final_score
                r["_confidence"] = min(max(final_score / 50.0, 0.1), 0.99)
                r["_primary_category"] = primary_category
                scored_candidates.append(r)
                
                if self.ranking_cache:
                    self.ranking_cache.put(ranking_key, final_score)
                
        timing["scoring"] = (time.time() - score_start)*1000
        
        # --- Step 3: Sort and final deduplication ---
        sort_start = time.time()
        scored_candidates.sort(key=lambda x: -x["_score"])
        seen_normalized_titles = set()
        unique_results = []
        domain_counts = {}
        curated_results = []
        
        # Helper: normalize title for fast deduplication
        def _normalize_title(title: str) -> str:
            # Lowercase, strip whitespace, collapse multiple spaces
            normalized = re.sub(r'\s+', ' ', title.lower().strip())
            # Split into words, sort them
            words = sorted(normalized.split())
            # Join back to a single string
            return ' '.join(words)
        
        for r in scored_candidates:
            # Fast pre-check with normalized title set
            normalized_title = _normalize_title(r["title"])
            if normalized_title in seen_normalized_titles:
                continue
            
            # Still do the is_similar check for edge cases
            is_dup = False
            for ur in unique_results:
                if self._is_similar(r["title"], ur["title"]):
                    is_dup = True
                    break
            if is_dup: continue
                
            domain = r.get("domain")
            domain_counts[domain] = domain_counts.get(domain, 0) +1
            if domain_counts[domain] >5: continue
                
            seen_normalized_titles.add(normalized_title)
            unique_results.append(r)
            curated_results.append(r)
        timing["sort_final"] = (time.time() - sort_start)*1000
        timing["total"] = (time.time() - start)*1000
        
        final_candidate_count = len(curated_results)
        
        # Log SCORING_PASS_X
        _log(f"SCORING_PASS_{pass_num}", f"candidates_in={initial_candidate_count}, candidates_out={final_candidate_count}, timing={timing['total']:.1f}ms, cache_hits={cache_hits}, quickscore={quickscore}")
        
        if quickscore:
            _log("OPAL:SEARCH:QUICKSCORE", f"Ranked {len(curated_results)} candidates in {timing['total']:.1f}ms")
        else:
            _log("RANKING_TIMING", f"Total: {timing['total']:.1f}ms | Dedupe: {timing['deduplication']:.1f}ms | Scoring: {timing['scoring']:.1f}ms | Sort: {timing['sort_final']:.1f}ms")
            # Log cache stats!
            if self.ranking_cache:
                _log("CACHE_STATS", f"Ranking: {self.ranking_cache.get_stats()}")
            
        return curated_results

    def fetch_opal_results(self, query: str, max_candidate_pool: int = 80, exclude_domains: Optional[set] = None, exclude_urls: Optional[set] = None) -> list[dict]:
        """Backwards-compatible blocking method for existing code.
        Now internally uses the new phase system!
        """
        import time
        
        _log("ENTER fetch_opal_results", f"query: {query}")
        
        # Initialize Coral timing dict
        coral_timing = {
            "query": query,
            "retrieval": 0.0,
            "semantic_expansion": 0.0,
            "candidate_gen": 0.0,
            "ranking": 0.0,
            "scoring": 0.0,
            "curation": 0.0,
            "ui_prep": 0.0
        }
        
        total_start = time.time()
        
        normalized_query = query.strip().lower()
        
        # Get Phase1 results instantly
        phase1 = self.fetch_phase1_nsindex(query, coral_timing)
        final_results = phase1["results"]
        
        # If we have exclusions, filter even trusted ranked results!
        if exclude_domains or exclude_urls:
            filtered_results = []
            exclude_urls_norm = {u.rstrip('/') for u in exclude_urls} if exclude_urls else set()
            exclude_domains_set = set(exclude_domains) if exclude_domains else set()
            for r in final_results:
                url = r.get('url', '').rstrip('/')
                domain = r.get('domain', '').lower()
                # Check if domain or any parent domain is excluded!
                domain_parts = domain.split('.')
                is_domain_excluded = False
                for i in range(len(domain_parts)):
                    parent_domain = '.'.join(domain_parts[i:])
                    if parent_domain in exclude_domains_set:
                        is_domain_excluded = True
                        break
                if url in exclude_urls_norm or is_domain_excluded:
                    continue
                filtered_results.append(r)
            final_results = filtered_results
            
            # If Phase1 was trusted ranked, return the filtered results!
            if phase1.get("trusted_ranked"):
                # Finalize timing and print
                coral_timing["total"] = (time.time() - total_start)
                self._print_coral_timing(coral_timing)
                return final_results
        
        # If Phase1 is trusted ranked and no exclusions: skip further scoring!
        if phase1.get("trusted_ranked"):
            # Finalize timing and print
            coral_timing["total"] = (time.time() - total_start)
            self._print_coral_timing(coral_timing)
            return final_results
        
        # Do Phase2 in blocking fashion for backwards compatibility
        # Wait a little for providers, but don't block forever
        phase2_collected = []
        lock = threading.Lock()
        
        def phase2_callback(data):
            nonlocal phase2_collected
            with lock:
                phase2_collected = data["results"]
                
        def phase3_callback(data):
            nonlocal final_results
            with lock:
                seen_urls = {r["url"] for r in final_results}
                for r in data["results"]:
                    if r["url"] not in seen_urls:
                        final_results.append(r)
        
        phase2_thread = self.fetch_phase2_providers(query, phase2_callback, max_candidate_pool, coral_timing=coral_timing)
        phase3_thread = self.fetch_phase3_discovery(query, phase3_callback, phase1["skip_phase3"], coral_timing=coral_timing)
        
        # Wait a few seconds for providers, but don't block UI indefinitely
        phase2_thread.join(timeout=3.0)
        
        # Merge phase2 results
        seen_urls = {r["url"] for r in final_results}
        for r in phase2_collected:
            if r["url"] not in seen_urls:
                final_results.append(r)
                
        # Re-score and deduplicate final results ONLY if NOT trusted_ranked!
        start_scoring = time.time()
        final_results = self._score_and_curate(final_results, query, normalized_query, exclude_domains=exclude_domains, exclude_urls=exclude_urls)
        coral_timing["ranking"] = (time.time() - start_scoring)
        coral_timing["scoring"] = coral_timing["ranking"] * 0.8
        coral_timing["curation"] = coral_timing["ranking"] * 0.2
        
        # Proxy thumbnails for the final merged list
        start_ui = time.time()
        with ThreadPoolExecutor(max_workers=5) as pool:
            def _proxy_thumb(r):
                if r.get("thumbnail"):
                    r["thumbnail"] = _fetch_data_uri(r["thumbnail"])
                return r
            final_results = list(pool.map(_proxy_thumb, final_results))
        coral_timing["ui_prep"] = (time.time() - start_ui)
        
        # Finalize total timing and print
        coral_timing["total"] = (time.time() - total_start)
        self._print_coral_timing(coral_timing)
            

        return final_results

    def _print_coral_timing(self, timing: dict):
        if not _DEBUG:
            return
        print(f"[CORAL] Query: {timing['query']}")
        if isinstance(timing['retrieval'], (int, float)):
            print(f"[CORAL] Retrieval: {timing['retrieval']:.3f}s")
        else:
            print(f"[CORAL] Retrieval: {timing['retrieval']}")
        
        if isinstance(timing['semantic_expansion'], (int, float)):
            print(f"[CORAL] Semantic Expansion: {timing['semantic_expansion']:.3f}s")
        else:
            print(f"[CORAL] Semantic Expansion: {timing['semantic_expansion']}")
        
        print(f"[CORAL] Candidate Generation: {timing['candidate_gen']:.3f}s")
        print(f"[CORAL] Ranking: {timing['ranking']:.3f}s")
        print(f"[CORAL] Scoring: {timing['scoring']:.3f}s")
        print(f"[CORAL] Curation: {timing['curation']:.3f}s")
        print(f"[CORAL] UI Preparation: {timing['ui_prep']:.3f}s")
        print(f"[CORAL] Total: {timing['total']:.3f}s")

    def _calculate_video_relevance_score(self, video: dict, query: str, query_type_info: dict) -> float:
        """Internal, separate video relevance scoring layer!
        Completely independent from web search ranking!
        
        Args:
            video: dict with title/url/img_src/author/etc.
            query: original user query
            query_type_info: from detect_query_type()
        
        Returns: float relevance score
        """
        score = 0.0
        q_lower = query.lower()
        title = video.get("title", "").lower()
        author = video.get("author", "").lower()
        channel = video.get("channel", "").lower()
        url = video.get("url", "").lower()
        primary_category = query_type_info.get("type", "concept")
        
        confidence_signals = 0
        
        # --- 1. Creator/Channel Confidence (EXTREMELY HIGH PRIORITY) ---
        creator_match = (q_lower in author) or (q_lower in channel)
        if creator_match:
            score += 80.0  # Absolute highest priority
            confidence_signals +=4
            
        # --- 2. URL contains entity ---
        if q_lower in url:
            score +=25
            confidence_signals +=2
            
        # --- 3. Title matching (EXTREMELY REDUCED WEIGHT) ---
        # Only give title points if we ALSO have AT LEAST 2 other signals
        title_match = q_lower in title
        title_starts = title.startswith(q_lower)
        if title_match and confidence_signals >=2:
            score += 12
            confidence_signals +=1
        elif title_starts and confidence_signals >=2:
            score += 8
        elif title_match:  # ONLY title match → NEGATIVE weight
            score -= 10
            
        # ---4. Query in video keywords ---
        video_keywords = ["video", "youtube", "trailer", "gameplay", "review", 
                        "interview", "music video", "showcase", "unboxing", 
                        "walkthrough", "demo", "guide", "how-to"]
        keyword_matches = sum(1 for kw in video_keywords if kw in title)
        if keyword_matches >=1 and confidence_signals >=2:
            score += 5 + (keyword_matches * 1)
            
        # ---5. Intent-aware boosts! ---
        intent_boosts = {
            "person": ["interview", "creator", "highlights", "q&a", "podcast"],
            "product": ["review", "unboxing", "showcase", "comparison", "specs"],
            "entertainment": ["trailer", "gameplay", "music video", "performance"],
            "tutorial": ["guide", "how to", "walkthrough", "tutorial", "lesson"]
        }
        
        if primary_category in intent_boosts:
            for kw in intent_boosts[primary_category]:
                if kw in title and confidence_signals >=2:
                    score +=10
                        
        # --- 6. Contextual Penalties ---
        bad_keywords = ["category:", "list of", "people from", "organizations", 
                       "history of", "politics of", "never gonna", "rick astley", 
                       "meme", "funny", "compilation", "music video",
                       "music", "song", "album"]
        
        # If it's a person/creator search, EXTREME penalty for music/meme without creator match!
        if primary_category in ["person", "entertainment"] and not creator_match:
            music_kw = ["music", "song", "track", "album", "never gonna", "rick astley"]
            meme_kw = ["meme", "funny", "compilation", "music video"]
            if any(m in title for m in music_kw):
                score -= 100
            if any(m in title for m in meme_kw):
                score -=80
                
        # General bad keywords penalty
        for kw in bad_keywords:
            if kw in title:
                score -= 50
                
        # If less than 2 confidence signals, VERY HEAVY penalty!
        if confidence_signals < 2:
            score -=80
            
        return score
        
    def fetch_opal_videos(self, query: str, limit: int = 12) -> list[dict]:
        """Fetch relevant videos (TEMPORARILY DISABLED)."""
        if not ENABLE_MEDIA_FETCH:
            _log("ENGINE", f"Media fetching disabled: skipping video search for {query!r}")
            return []
        
        """Fetch relevant videos: 
        Uses Yahoo and SearXNG as video candidates, then applies internal video-only ranking!
        No web search ranking reused!
        """
        _log("ENGINE", f"Fetching videos for {query!r}...")
        
        q_lower = query.lower()
        query_type_info = detect_query_type(query)
        
        raw_videos = []
        
        # Step1: Get candidate videos only from video-specific search endpoints!
        try:
            provider_videos1 = self.engine.execute_videos(query, limit=limit +30)
            raw_videos.extend(provider_videos1)
            _log("ENGINE", f"execute_videos found {len(provider_videos1)}")
        except Exception as e:
            _log("ENGINE_ERR", f"Primary video fetch failed: {e}")
            
        try:
            provider_videos2 = self.engine.execute_videos(f"{query} video", limit=limit +20)
            raw_videos.extend(provider_videos2)
        except Exception as e:
            _log("ENGINE_ERR", f"Video-enhanced query fetch failed: {e}")
            
        # Step 2: Extract videos from raw web search if needed
        try:
            raw_web = self.engine.execute(query, limit=40)
            for r in raw_web:
                domain = r.get("domain", "").lower()
                title = r.get("title", "").lower()
                if any(kw in domain or kw in title for kw in ["video", "youtube.com", "vimeo.com", "dailymotion.com", "youtu.be"]):
                    if r.get("thumbnail") or r.get("img_src"):
                        video_candidate = r.copy()
                        if "img_src" not in video_candidate and "thumbnail" in video_candidate:
                            video_candidate["img_src"] = video_candidate["thumbnail"]
                        raw_videos.append(video_candidate)
        except Exception as e:
            _log("ENGINE_ERR", f"Raw web fallback failed: {e}")
            
        _log("ENGINE", f"Found {len(raw_videos)} raw video candidates!")
        
        # Debug test videos
        _DEBUG = False
        if _DEBUG:
            _log("ENGINE", "Adding debug test videos!")
            raw_videos.extend([
                {"title": f"{query} - Official Video", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "img_src": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg", "source": "YouTube", "duration": "3:33"},
                {"title": f"{query} Highlights", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "img_src": "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg", "source": "YouTube", "duration": "2:15"}
            ])
            
        # Step3: Video-only ranking, completely separate from web!
        scored = []
        seen = set()
        
        for vid in raw_videos:
            url = vid.get("url", "").lower()
            if not url or url in seen:
                continue
            seen.add(url)
            
            score = self._calculate_video_relevance_score(vid, query, query_type_info)
            scored.append( ( -score, vid ) )  # sort ascending!
            
        scored.sort()
        
        curated = []
        for s, vid in scored:
            curated.append(vid)
            if len(curated) >= limit:
                break
                
        _log("ENGINE", f"Curated {len(curated)} video results!")
        return curated
        
    def fetch_opal_images(self, query: str, limit: int = 10) -> list[dict]:
        """Fetch relevant images (TEMPORARILY DISABLED)."""
        if not ENABLE_MEDIA_FETCH:
            _log("ENGINE", f"Media fetching disabled: skipping image search for {query!r}")
            return []
        
        """Fetch relevant images for the query."""
        _log("ENGINE", f"Fetching images for {query!r}...")
        
        intent = self._detect_query_intent(query)
        is_wallpaper = (intent == "wallpaper")
        
        # If wallpaper, increase limit to allow better filtering
        fetch_limit = limit * 3 if is_wallpaper else limit + 5
        results = self.engine.execute_images(query, limit=fetch_limit)
        
        # Fallback: If no images from SearXNG, try to get a main image from DDG
        if not results:
            _log("ENGINE", f"No images from engine for {query!r}, trying fallbacks...")
            # 1. Try DDG API for a primary image
            try:
                params = {"q": query, "format": "json", "no_html": "1"}
                resp = requests.get(_DDG_API, params=params, headers=_HEADERS, timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    img_url = data.get("Image")
                    if img_url:
                        _log("ENGINE", f"Found image from DDG API fallback: {img_url}")
                        if img_url.startswith("/"): img_url = "https://duckduckgo.com" + img_url
                        results.append({
                            "title": data.get("Heading", query),
                            "url": data.get("AbstractURL", "#"),
                            "img_src": img_url,
                            "source": "DuckDuckGo"
                        })
            except Exception as e:
                _log("ENGINE_ERR", f"DDG image fallback failed: {e}")
                pass
        
        # --- Image Relevance Filtering ---
        scored_images = []
        for r in results:
            score = 50.0 # baseline
            title = r.get("title", "").lower()
            url = r.get("img_src", "").lower()
            
            # Global Wikipedia Filter
            if "wikipedia.org" in url or "wikimedia.org" in url:
                continue
                
            # Penalize product photos/logos/screenshots/icons
            junk_keywords = ["product", "buy", "price", "amazon", "ebay", "logo", "icon", "screenshot", "ui", "button", "thumbnail", "vector", "illustration", "preview", "stock", "photo", "svg", "png"]
            if any(k in title for k in junk_keywords): score -= 35.0
            if any(k in url for k in junk_keywords): score -= 25.0
            
            # Wallpaper-specific filtering
            if is_wallpaper:
                # Prioritize Landscape / High Res hints
                landscape_boost = ["landscape", "wide", "panoramic", "scenery", "nature", "mountain", "forest", "beach", "ocean", "space", "nebula", "view", "cityscape"]
                res_boost = ["4k", "8k", "ultra hd", "uhd", "1920x1080", "2560x1440", "3840x2160", "wallpaper", "background", "desktop", "hd", "high res", "high resolution"]
                
                if any(k in title for k in landscape_boost): score += 25.0
                if any(k in url for k in landscape_boost): score += 15.0
                if any(k in title for k in res_boost): score += 30.0
                if any(k in url for k in res_boost): score += 20.0
                
                # Aspect ratio estimation from URL/Title
                if "wide" in title or "16x9" in title or "16-9" in title: score += 20.0
                if "1920x" in url or "2560x" in url or "3840x" in url: score += 15.0
                
                # Penalize Portrait / Mobile hints unless explicitly requested
                if "mobile" not in query.lower() and "phone" not in query.lower():
                    portrait_pen = ["portrait", "mobile", "phone", "iphone", "android", "vertical", "smartphone", "lockscreen"]
                    if any(k in title for k in portrait_pen): score -= 40.0
                    if any(k in url for k in portrait_pen): score -= 30.0
                
                # Aesthetic/Art boost
                aesthetic_boost = ["art", "digital art", "aesthetic", "minimal", "dark", "neon", "cyberpunk", "vaporwave", "abstract", "cinematic"]
                if any(k in title for k in aesthetic_boost): score += 20.0
                
                # Prefer known wallpaper sites
                wallpaper_sites = ["alphacoders.com", "wallhaven.cc", "unsplash.com", "pexels.com", "pixabay.com", "wallpapersden.com", "hdqwalls.com", "wallpapercave.com", "wallpapersafari.com", "wallpaperflare.com"]
                if any(site in url for site in wallpaper_sites): score += 60.0
            
            r["_score"] = score
            if score > 0:
                scored_images.append(r)
        
        scored_images.sort(key=lambda x: x["_score"], reverse=True)
        results = scored_images[:limit * 2] # Keep a buffer for data URI proxying
        
        _log("ENGINE", f"Total images found: {len(results)}")
        
        # Hardcoded test image fix: use a more reliable URL or handle failure
        if not results and _DEBUG:
            _log("ENGINE", "Adding hardcoded test image for debugging")
            results.append({
                "title": "NorthStar Test Image",
                "url": "https://github.com/PyQt/python-qtlogo",
                "img_src": "https://raw.githubusercontent.com/PyQt/python-qtlogo/master/logo.png",
                "source": "Debug"
            })

        if results:
            # Proxied load: convert top images to Data URIs to bypass hotlinking/CORS
            _log("ENGINE", f"Proxying {len(results[:limit])} images to Data URIs...")
            proxied_results = []
            
            # Use a slightly larger limit for proxying in case some fail
            to_proxy = results[:limit + 4]
            
            with ThreadPoolExecutor(max_workers=5) as pool:
                def _fetch_one(r):
                    data_uri = _fetch_data_uri(r["img_src"])
                    if data_uri and data_uri.startswith("data:"):
                        r["img_src"] = data_uri
                        return r
                    return None
                
                futures = [pool.submit(_fetch_one, r) for r in to_proxy]
                for f in as_completed(futures):
                    res = f.result()
                    if res:
                        proxied_results.append(res)
                        if len(proxied_results) >= limit:
                            break
            
            results = proxied_results
            
            for i, r in enumerate(results[:3]):
                src_preview = r.get('img_src', '')[:50] + "..." if r.get('img_src', '').startswith("data:") else r.get('img_src')
                _log("ENGINE_DATA", f"Sample {i}: {src_preview} ({r.get('title')})")
        
        return results[:limit]

    def _is_similar(self, s1: str, s2: str) -> bool:
        """Fuzzy similarity check using SequenceMatcher."""
        if not s1 or not s2:
            return False

        s1_lower = s1.lower().strip()
        s2_lower = s2.lower().strip()

        if s1_lower == s2_lower:
            return True

        ratio = SequenceMatcher(None, s1_lower, s2_lower).ratio()

        if ratio > 0.75:
            return True

        w1 = set(re.findall(r'\w+', s1_lower))
        w2 = set(re.findall(r'\w+', s2_lower))
        if not w1 or not w2:
            return False

        intersection = w1.intersection(w2)
        jaccard = len(intersection) / len(w1.union(w2))
        if jaccard > 0.6:
            return True

        return False

    def _calculate_relevance_score(self, query: str, result: dict, intent: str) -> float:
        """Calculate a relevance score for a search result (balanced for pagination)."""
        score = 0.0
        q = query.lower()
        title = result["title"].lower()
        snippet = result["snippet"].lower()
        domain = result["domain"].lower()
        url = result["url"].lower()
        provider = result.get("provider", "unknown")

        # 1. Exact phrase matches (HIGH PRIORITY)
        if q in title: 
            score += 30.0  # Heavily prioritize exact title matches
        if q in snippet: 
            score += 8.0

        # 1b. Fuzzy phrase matching (partial credit for near-misses)
        title_ratio = SequenceMatcher(None, q, title).ratio()
        if title_ratio > 0.6:
            score += title_ratio * 15.0
        snippet_ratio = SequenceMatcher(None, q, snippet).ratio()
        if snippet_ratio > 0.5:
            score += snippet_ratio * 5.0
        
        # 2. Exact word matches (higher weight for title)
        q_words = set(re.findall(r'\w+', q))
        title_words = set(re.findall(r'\w+', title))
        snippet_words = set(re.findall(r'\w+', snippet))
        common_title_words = q_words.intersection(title_words)
        common_snippet_words = q_words.intersection(snippet_words)
        total_keywords = len(q_words)
        
        score += len(common_title_words) * 5.0
        score += len(common_snippet_words) * 1.5

        # 2b. Fuzzy word matching (partial credit for similar words)
        fuzzy_title_bonus = 0.0
        for qw in q_words:
            best_ratio = 0.0
            for tw in title_words:
                ratio = SequenceMatcher(None, qw, tw).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
            if best_ratio > 0.7 and best_ratio < 1.0:
                fuzzy_title_bonus += best_ratio * 2.0
        score += fuzzy_title_bonus

        # 3. Domain Match (High priority for exact brand/entity matches)
        clean_q = re.sub(r'[^a-z0-9]', '', q)
        clean_dom = re.sub(r'[^a-z0-9]', '', domain.split('.')[0])
        if clean_q == clean_dom:
            score += 40.0
        elif clean_q in clean_dom:
            score += 15.0
        else:
            dom_ratio = SequenceMatcher(None, clean_q, clean_dom).ratio()
            if dom_ratio > 0.7:
                score += dom_ratio * 10.0

        # 4. Provider Weighting
        score += _PROVIDER_WEIGHTS.get(provider, 0.0)

        # 5. Domain Reputation Weighting
        rep = _DOMAIN_REPUTATION.get(domain, "medium")
        score += _REPUTATION_BOOST.get(rep, 0.0)

        # 6. Intent-based Boosting
        if intent == "tech":
            if any(d in domain for d in ["github.com", "stackoverflow.com", "docs.", "dev.to", "mozilla.org", "w3schools.com", "geeksforgeeks.org"]):
                score += 20.0
        
        elif intent == "news":
            if any(d in domain for d in ["bbc.com", "reuters.com", "apnews.com", "nytimes.com", "bloomberg.com", "wsj.com"]):
                score += 15.0
        
        # 7. Penalize loosely related matches (historical/political unless directly relevant)
        penalty_keywords = ["history", "historical", "politics", "political", "election", "government", "war", "battle", "president", "king", "queen", "empire"]
        query_has_penalty = any(k in q for k in penalty_keywords)
        if not query_has_penalty:
            if any(k in title for k in penalty_keywords):
                score -= 15.0
            if any(k in snippet for k in penalty_keywords):
                score -= 8.0

        # 8. Negative keywords (Targeting legal noise for brand searches)
        if len(q.split()) <= 2:
            legal_terms = ["v.", "vs.", "lawsuit", "dispute", "litigation", "court", "case", "legal", "sued", "suing"]
            if any(term in title for term in legal_terms):
                score -= 20.0
            if any(term in snippet for term in legal_terms):
                score -= 10.0

        # 9. URL Path Depth
        parsed_url = urlparse(result["url"])
        path = parsed_url.path.strip("/")
        if not path or path.lower() in ["index.html", "home", "index.php"]:
            score += 8.0
        elif path.count("/") > 3:
            score -= 3.0

        # 10. Secure site boost
        if result["url"].startswith("https://"):
            score += 2.0

        # 11. NSIndex score boost (BIG BOOST FOR LOCAL PACK RESULTS)
        nsindex_score = result.get("_nsindex_score", 0)
        if nsindex_score > 0:
            score += nsindex_score * 0.5  # Scale NSIndex score to fit

        # 12. Official site boost from NSIndex
        if result.get("official", False):
            score += 25.0

        _log("RANK", f"Score: {score:.1f} for {domain} (P:{provider}) - '{title[:30]}...'")
        return score

    # ── Related Links (DuckDuckGo Instant Answer) ─────────────────────────────

    def fetch_related_links(self, query: str) -> list[dict]:
        """Fetch official websites or related links for *query*.

        Uses canonical mappings first, then DuckDuckGo Instant Answer API + fallback to "official website" search.
        Returns a list of dicts: {name, url, description, favicon}
        """
        query = query.strip()
        if not query:
            return []

        links = []
        seen_urls = set()
        seen_domains = set()

        # First, check our canonical mappings for an exact match!
        q_lower = query.lower()
        if q_lower in _CANONICAL_MAPPINGS:
            canonical_url = _CANONICAL_MAPPINGS[q_lower]
            domain = urlparse(canonical_url).netloc
            links.append({
                "name": query.title(),
                "url": canonical_url,
                "description": "Official Website",
                "favicon": f"{_DDG_ICON_SRV}{domain}.ico"
            })
            seen_urls.add(canonical_url.rstrip("/"))
            seen_domains.add(domain.lower())

        try:
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1"
            }
            resp = _safe_request(_DDG_API, params=params, timeout=3)
            data = _safe_json_parse(resp)
            if not data:
                raise ValueError("No data from DDG API")

            official_url = data.get("OfficialWebsite")
            if official_url:
                url_norm = official_url.rstrip("/")
                domain = urlparse(official_url).netloc.lower()
                if url_norm not in seen_urls and domain not in seen_domains:
                    links.append({
                        "name": data.get("Heading") or domain,
                        "url": official_url,
                        "description": "Official Website",
                        "favicon": f"{_DDG_ICON_SRV}{domain}.ico"
                    })
                    seen_urls.add(url_norm)
                    seen_domains.add(domain)

            for r in data.get("Results", []):
                url = r.get("FirstURL")
                if not url: continue
                url_norm = url.rstrip("/")
                domain = urlparse(url).netloc.lower()
                if url_norm in seen_urls or domain in seen_domains: continue

                text = r.get("Text", "")
                name = text.split(" - ")[0] if " - " in text else text
                if not name or name == "Official site":
                    name = data.get("Heading") or urlparse(url).netloc

                desc = ""
                if " - " in text:
                    desc = text.split(" - ", 1)[1]

                links.append({
                    "name": name,
                    "url": url,
                    "description": desc or "Related Link",
                    "favicon": f"{_DDG_ICON_SRV}{domain}.ico"
                })
                seen_urls.add(url_norm)
                seen_domains.add(domain)

            abs_url = data.get("AbstractURL")
            if abs_url and "wikipedia.org" not in abs_url:
                url_norm = abs_url.rstrip("/")
                domain = urlparse(abs_url).netloc.lower()
                if url_norm not in seen_urls and domain not in seen_domains:
                    links.append({
                        "name": data.get("Heading") or domain,
                        "url": abs_url,
                        "description": "Related Link",
                        "favicon": f"{_DDG_ICON_SRV}{domain}.ico"
                    })
                    seen_urls.add(url_norm)
                    seen_domains.add(domain)
        except Exception as exc:
            _log("DDG_ERR", f"Primary DDG API call failed: {exc}")

        try:
            official_query = f"{query} official website"
            ddg_provider = DDGProvider()
            ddg_results = ddg_provider.search(official_query, limit=5)
            for r in ddg_results:
                url = r.get("url", "")
                url_norm = url.rstrip("/")
                domain = r.get("domain", "").lower()
                if url_norm in seen_urls or domain in seen_domains: continue
                
                title_lower = r.get("title", "").lower()
                snippet_lower = r.get("snippet", "").lower()
                
                if any(kw in title_lower for kw in ["official", "homepage", "site"]) or \
                   any(kw in snippet_lower for kw in ["official", "homepage", "site"]):
                    
                    links.append({
                        "name": r.get("title", query),
                        "url": url,
                        "description": r.get("snippet", "Official site for " + query),
                        "favicon": r.get("favicon", ""),
                        "domain": r.get("domain", "")
                    })
                    seen_urls.add(url_norm)
                    seen_domains.add(domain)
        except Exception as exc:
            _log("DDG_ERR", f"Fallback official search failed: {exc}")

        return links[:5]
