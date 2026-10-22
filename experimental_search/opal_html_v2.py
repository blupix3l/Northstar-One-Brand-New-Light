"""
opal_html_v2.py — Opal Discovery HTML Builder (Hybrid Web Edition)
==================================================================
Replaces the _build_opal_html() function in NorthStar_v0_3.py.
Also provides companion loading and error pages with broad web discovery themes.
"""

import html as _html_mod
import json
from urllib.parse import quote_plus


# ─────────────────────────────────────────────────────────────────────────────
#  LOADING PAGE  (unchanged aesthetically; updated flavour text)
# ─────────────────────────────────────────────────────────────────────────────

def _build_opal_loading_html(query: str, dark_mode: bool = True) -> str:
    q = _html_mod.escape(query)
    if dark_mode:
        bg, text, muted, accent, accent2 = "#080b14", "#dde4f0", "#6b7a99", "#4fc3f7", "#9c6ff7"
        overlay = "rgba(79,195,247,0.03)"
    else:
        bg, text, muted, accent, accent2 = "#f0f4ff", "#1e1b4b", "#6b7280", "#4f46e5", "#059669"
        overlay = "rgba(79,70,229,0.03)"
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{
  background:{bg};color:{text};font-family:'Segoe UI',system-ui,sans-serif;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;overflow:hidden;gap:4px;position:relative;
}}
body::before {{
  content:'';position:absolute;inset:0;
  background: radial-gradient(circle at center, {overlay} 0%, transparent 70%);
  animation: breathe 4s ease-in-out infinite;
}}
@keyframes breathe {{ 0%, 100% {{ opacity: 0.4; transform: scale(1); }} 50% {{ opacity: 1; transform: scale(1.1); }} }}

.loader-container {{
  position: relative; display: flex; flex-direction: column; align-items: center; z-index: 1;
}}
.gem-wrap {{
  position: relative; width: 64px; height: 64px; margin-bottom: 24px;
  display: flex; align-items: center; justify-content: center;
}}
.gem {{
  font-size: 36px; z-index: 2; color: {accent};
  text-shadow: 0 0 15px {accent};
  animation: float 3s ease-in-out infinite;
}}
.gem-ring {{
  position: absolute; inset: 0; border: 2px solid {accent}; border-radius: 50%;
  border-top-color: transparent; border-bottom-color: transparent;
  animation: spin 2s linear infinite; opacity: 0.3;
}}
.gem-ring-inner {{
  position: absolute; inset: 8px; border: 1px solid {accent2}; border-radius: 50%;
  border-left-color: transparent; border-right-color: transparent;
  animation: spin 1.5s linear infinite reverse; opacity: 0.2;
}}

@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
@keyframes float {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-6px); }} }}

.label {{
  font-size: 11px; font-weight: 700; letter-spacing: .2em; color: {muted};
  text-transform: uppercase; opacity: 0.8; margin-top: 8px;
}}
.query {{
  margin-top: 10px; font-size: 16px; color: {accent}; font-weight: 500;
  letter-spacing: 0.02em; animation: fadeIn 0.8s ease-out;
}}
.sub {{
  font-size: 12px; color: {muted}; margin-top: 6px; letter-spacing: .08em;
  display: flex; align-items: center; gap: 8px;
}}
.dot-flashing {{
  position: relative; width: 4px; height: 4px; border-radius: 5px;
  background-color: {muted}; color: {muted};
  animation: dot-flashing 1s infinite linear alternate; animation-delay: 0.5s;
}}
.dot-flashing::before, .dot-flashing::after {{
  content: ""; display: inline-block; position: absolute; top: 0;
  width: 4px; height: 4px; border-radius: 5px;
  background-color: {muted}; color: {muted};
  animation: dot-flashing 1s infinite linear alternate;
}}
.dot-flashing::before {{ left: -8px; animation-delay: 0s; }}
.dot-flashing::after {{ left: 8px; animation-delay: 1s; }}

@keyframes dot-flashing {{
  0% {{ background-color: {muted}; }}
  50%, 100% {{ background-color: rgba(107, 122, 153, 0.2); }}
}}
@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
</style></head><body>
<div class="loader-container">
  <div class="gem-wrap">
    <div class="gem-ring"></div>
    <div class="gem-ring-inner"></div>
    <div class="gem">◈</div>
  </div>
  <div class="label">Opal Discovery</div>
  <div class="query">"{q}"</div>
  <div class="sub">Exploring the web <div class="dot-flashing"></div></div>
</div>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  ERROR PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _build_opal_error_html(query: str, error: str = "") -> str:
    q     = _html_mod.escape(query)
    q_enc = quote_plus(query)
    err   = _html_mod.escape(error)
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#080b14;color:#dde4f0;font-family:'Segoe UI',system-ui,sans-serif;
     display:flex;flex-direction:column;align-items:center;justify-content:center;
     height:100vh;gap:12px}}
.icon{{font-size:36px;filter:drop-shadow(0 0 10px #f87171)}}
.title{{font-size:16px;font-weight:600;color:#f87171}}
.msg{{font-size:13px;color:#6b7a99;max-width:420px;text-align:center;line-height:1.6}}
.query{{color:#4fc3f7}}
.web-btn{{margin-top:8px;display:inline-block;color:#4fc3f7;font-size:13px;
       text-decoration:none;border:1px solid rgba(79,195,247,0.3);border-radius:8px;
       padding:6px 16px;transition:background .2s}}
.web-btn:hover{{background:rgba(79,195,247,0.12)}}
</style></head><body>
<div class="icon">◈</div>
<div class="title">Opal discovery offline</div>
<div class="msg">Something went wrong while exploring
  <span class="query">"{q}"</span>.
  {"<br><small style='color:#4b5563;margin-top:4px;display:block'>"+err+"</small>" if err else ""}
</div>
<a class="web-btn" href="https://google.com/search?q={q_enc}">
  Try Google instead →
</a>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN RESULTS PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _build_opal_html(
    query:       str,
    results:     list,
    model:       str  = None,
    dark_mode:   bool = True,
    leo_summary: str  = "",
    related_links: list = None,
    images:      list = None,
    videos:      list = None,
    load_time:   float = None,
) -> str:
    """Build the Opal Discovery results page."""
    if model is None:
        try:
            from ai_manager import AIManager
            ai_manager = AIManager()
            provider = ai_manager.get_current_provider()
            model = provider.config.get("model", "AI")
        except:
            model = "AI"
    q_esc  = _html_mod.escape(query)
    q_enc  = quote_plus(query)
    q_json = json.dumps(query)    # safe JS string literal
    results_json = json.dumps(results)  # for pagination

    # ── theme tokens ──────────────────────────────────────────────────────────
    if dark_mode:
        css_vars = (
            "--bg:#080b14;--surface:rgba(255,255,255,0.028);--surface2:rgba(255,255,255,0.055);"
            "--border:rgba(255,255,255,0.08);--accent:#4fc3f7;--accent2:#9c6ff7;"
            "--text:#dde4f0;--muted:#6b7a99;--glow:rgba(79,195,247,0.18);"
            "--hdr-bg:rgba(8,11,20,0.88);"
            "--scrollbar:rgba(255,255,255,0.1);--link-accent:#38bdf8;"
            "--thumb-bg:rgba(255,255,255,0.04);"
        )
    else:
        css_vars = (
            "--bg:#f0f4ff;--surface:rgba(0,0,0,0.03);--surface2:rgba(0,0,0,0.07);"
            "--border:rgba(0,0,0,0.09);--accent:#4f46e5;--accent2:#059669;"
            "--text:#1e1b4b;--muted:#6b7280;--glow:rgba(79,70,229,0.18);"
            "--hdr-bg:rgba(240,244,255,0.90);"
            "--scrollbar:rgba(0,0,0,0.15);--link-accent:#0284c7;"
            "--thumb-bg:rgba(0,0,0,0.06);"
        )

    # ── result cards ──────────────────────────────────────────────────────────
    # No need to pre-render all; JS will handle pagination
    # But we'll render the first page for initial display
    cards_html = _build_cards_for_page(results, 0, 8, q_enc)

    # ── related links ─────────────────────────────────────────────────────────
    rel_html = _build_related_links(related_links)

    # ── images ────────────────────────────────────────────────────────────────
    img_html = _build_images(images)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{q_esc} — Opal Discovery</title>
<style>
/* ── reset ─────────────────────────────────────── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{{css_vars}}}
html,body{{
  height:100%;background:var(--bg);color:var(--text);
  font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;
  line-height:1.6;overflow-x:hidden
}}
::-webkit-scrollbar{{width:5px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--scrollbar);border-radius:3px}}

/* ── header ────────────────────────────────────── */
.hdr{{
  position:sticky;top:0;z-index:100;
  background:var(--hdr-bg);backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border);
  padding:10px 28px;display:flex;align-items:center;gap:18px
}}
.brand{{display:flex;align-items:center;gap:7px;text-decoration:none;
        white-space:nowrap;cursor:pointer}}
.brand-gem{{font-size:20px;filter:drop-shadow(0 0 7px var(--accent))}}
.brand-name{{
  font-size:11px;font-weight:700;letter-spacing:.12em;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent
}}
.sbar{{
  flex:1;max-width:580px;display:flex;align-items:center;
  background:var(--surface2);border:1px solid var(--border);
  border-radius:10px;padding:0 12px;
  transition:border-color .2s,box-shadow .2s
}}
.sbar:focus-within{{border-color:var(--accent);box-shadow:0 0 0 3px var(--glow)}}
.sbar input{{
  flex:1;background:transparent;border:none;outline:none;
  color:var(--text);font-size:14px;padding:8px 0
}}
.sbar input::placeholder{{color:var(--muted)}}
.sbtn{{background:none;border:none;cursor:pointer;color:var(--muted);
       font-size:16px;padding:4px;transition:color .2s}}
.sbtn:hover{{color:var(--accent)}}

/* ── page layout ───────────────────────────────── */
.page{{max-width:740px;margin:0 auto;padding:22px 28px 70px}}

/* ── results header ────────────────────────────── */
.res-hdr{{
  font-size:11px;color:var(--muted);letter-spacing:.07em;text-transform:uppercase;
  margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:6px
}}
.web-badge{{
  font-size:10px;font-weight:700;letter-spacing:.06em;
  color:var(--accent);border:1px solid var(--accent);
  border-radius:4px;padding:1px 5px;text-transform:uppercase;opacity:.85
}}

/* ── result card ───────────────────────────────── */
.card{{
  background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:14px 18px;margin-bottom:10px;cursor:pointer;
  transition:all .2s cubic-bezier(0.4, 0, 0.2, 1);
  animation: slide-up 0.5s ease-out backwards;
}}
.card:nth-child(1) {{ animation-delay: 0.1s; }}
.card:nth-child(2) {{ animation-delay: 0.15s; }}
.card:nth-child(3) {{ animation-delay: 0.2s; }}
.card:nth-child(4) {{ animation-delay: 0.25s; }}
.card:nth-child(5) {{ animation-delay: 0.3s; }}
.card:nth-child(6) {{ animation-delay: 0.35s; }}
.card:nth-child(7) {{ animation-delay: 0.4s; }}
.card:nth-child(8) {{ animation-delay: 0.45s; }}

@keyframes slide-up {{
  from {{ opacity: 0; transform: translateY(15px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.card:hover{{
  background:var(--surface2);border-color:rgba(79,195,247,.35);
  box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(79,195,247,0.15);
  transform:translateY(-3px);
}}

/* card inner layout: text body left, thumbnail right */
.card-inner{{display:flex;align-items:flex-start;gap:14px}}
.card-body{{flex:1;min-width:0}}

/* thumbnail */
.card-thumb{{
  width:76px;height:76px;border-radius:8px;object-fit:cover;flex-shrink:0;
  background:var(--thumb-bg);opacity:.9;
  border:1px solid var(--border);
  transition:opacity .2s
}}
.card:hover .card-thumb{{opacity:1}}

.card-meta{{display:flex;align-items:center;gap:6px;margin-bottom:5px}}
.fav{{border-radius:2px;opacity:.8;flex-shrink:0;width:14px;height:14px}}
.dom{{font-size:12px;color:var(--accent);font-weight:500}}
.durl{{
  font-size:11px;color:var(--muted);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;max-width:340px
}}
.card-title{{
  display:block;font-size:15px;font-weight:500;color:var(--accent);
  text-decoration:none;line-height:1.4;margin-bottom:5px;transition:color .15s
}}
.card-title:hover{{color:#a5b4fc}}
.card-snip{{
  font-size:13px;color:#8892aa;line-height:1.65;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden
}}
.read-link{{
  display:inline-block;margin-top:7px;font-size:11px;color:var(--link-accent);
  text-decoration:none;opacity:.75;transition:opacity .15s
}}
.read-link:hover{{opacity:1;text-decoration:underline}}

/* no results */
.no-res{{text-align:center;padding:48px;color:var(--muted)}}
.web-link{{color:var(--accent);text-decoration:none}}
.web-link:hover{{text-decoration:underline}}

/* ── related links ────────────────────────────── */
.rel-box{{
  margin-bottom:26px;display:flex;flex-direction:column;gap:10px
}}
.rel-card{{
  background:var(--surface2);border:1px solid var(--border);border-radius:12px;
  padding:12px 16px;display:flex;align-items:center;gap:12px;
  text-decoration:none;transition:transform .15s, border-color .15s, box-shadow .15s
}}
.rel-card:hover{{
  transform:translateY(-1px);border-color:rgba(79,195,247,.3);
  box-shadow:0 4px 12px rgba(0,0,0,.2);
}}
.rel-fav{{width:18px;height:18px;border-radius:3px;flex-shrink:0}}
.rel-info{{flex:1;min-width:0}}
.rel-name{{
  display:block;font-size:14px;font-weight:600;color:var(--accent);
  margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}}
.rel-desc{{
  font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}}
.rel-arrow{{color:var(--muted);font-size:14px;margin-left:auto}}

/* ── image results ─────────────────────────────── */
.img-grid{{
  display:grid;grid-template-columns:repeat(auto-fill, minmax(140px, 1fr));
  gap:12px;margin-bottom:28px;
}}
.img-item{{
  position:relative;aspect-ratio:1/1;border-radius:12px;
  overflow:hidden;background:var(--surface2);border:1px solid var(--border);
  cursor:pointer;transition:transform .2s, box-shadow .2s;
}}
.img-item:hover{{
  transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.4);
  border-color:rgba(79,195,247,0.3);
}}
.img-item img{{
  width:100%;height:100%;object-fit:cover;transition:opacity .3s;
}}
.img-meta{{
  position:absolute;bottom:0;left:0;right:0;padding:8px;
  background:linear-gradient(transparent, rgba(0,0,0,0.85));
  color:#fff;font-size:10px;opacity:0;transition:opacity .2s;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  pointer-events:none;
}}
.img-item:hover .img-meta{{opacity:1}}

.view-all-btn{{
  color:var(--accent);text-decoration:none;font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:0.05em;opacity:0.8;
  transition:opacity 0.2s, transform 0.2s;
}}
.view-all-btn:hover{{opacity:1;transform:translateX(2px)}}
.show-all-wrap{{
  display:flex;justify-content:center;margin-top:-12px;margin-bottom:24px;
}}
.show-all-btn{{
  background:var(--surface2);border:1px solid var(--border);border-radius:8px;
  padding:8px 20px;font-size:12px;font-weight:600;color:var(--text);
  text-decoration:none;transition:background 0.2s, border-color 0.2s, transform 0.2s;
  display:flex;align-items:center;gap:8px;
}}
.show-all-btn:hover{{
  background:var(--surface);border-color:rgba(79,195,247,0.4);
  transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,0.2);
}}

/* ── discovery ─────────────────────────────────── */
.disc{{margin-top:32px;padding-top:22px;border-top:1px solid var(--border)}}
.disc-title{{
  font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin-bottom:13px;display:flex;align-items:center;gap:6px
}}
.chips{{display:flex;flex-wrap:wrap;gap:8px}}
.chip{{
  background:var(--surface);border:1px solid var(--border);border-radius:20px;
  padding:5px 13px;font-size:12px;color:var(--text);cursor:pointer;
  text-decoration:none;display:inline-block;
  transition:background .15s,border-color .15s,color .15s
}}
.chip:hover{{background:var(--surface2);border-color:rgba(79,195,247,.4);color:var(--accent)}}

/* ── pagination ─────────────────────────────────── */
.pagination{{
  display:flex;justify-content:center;align-items:center;gap:16px;margin-top:24px;
}}
.pagination-btn{{
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:8px 16px;font-size:12px;font-weight:600;color:var(--text);
  cursor:pointer;transition:background 0.2s,border-color 0.2s,color 0.2s;
}}
.pagination-btn:hover:not(:disabled){{
  background:var(--surface2);border-color:rgba(79,195,247,.4);color:var(--accent);
}}
.pagination-btn:disabled{{
  opacity:0.4;cursor:not-allowed;
}}
.pagination-info{{
  font-size:12px;color:var(--muted);
}}

/* ── load timer ─────────────────────────────────── */
.load-timer{{
  position:fixed;bottom:16px;left:16px;z-index:200;
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:6px 12px;font-size:11px;color:var(--muted);
  backdrop-filter:blur(12px);pointer-events:none;
}}
</style>
</head>
<body>

<header class="hdr">
  <div class="brand" onclick="history.back()">
    <span class="brand-gem">◈</span>
    <span class="brand-name">OPAL DISCOVERY</span>
  </div>
  <form class="sbar" onsubmit="doSearch(event)">
    <input id="q" type="text" value="{q_esc}" placeholder="Explore further…" autocomplete="off">
    <button class="sbtn" type="submit">⟶</button>
  </form>
</header>

<div class="page">

<div id="rel-container">{rel_html}</div>

<div id="img-container">{img_html}</div>

  <div class="res-hdr">
    Discovery Results
    <span class="web-badge">Web</span>
  </div>
  <div id="results">{cards_html}</div>

  <div id="pagination" class="pagination">
    <button class="pagination-btn" id="prev-btn" disabled>&lt; Previous</button>
    <span class="pagination-info" id="page-info">Page 1</span>
    <button class="pagination-btn" id="next-btn">Next &gt;</button>
  </div>

  <div class="disc">
    <div class="disc-title"><span>◈</span> Discover More</div>
    <div class="chips" id="chips"></div>
    </div>

</div>

{f'<div class="load-timer">Loaded in {load_time:.2f}s</div>' if load_time is not None else ''}

<script>
const QUERY = {q_json};
const OPAL  = "northstar://search?q=";
const ALL_RESULTS = {results_json};
const RESULTS_PER_PAGE = 8;
let currentPage = 0;

function doSearch(e) {{
  e.preventDefault();
  var q = document.getElementById('q').value.trim();
  if (q) window.location.href = OPAL + encodeURIComponent(q);
}}

function renderResults() {{
  const start = currentPage * RESULTS_PER_PAGE;
  const end = start + RESULTS_PER_PAGE;
  const resultsSlice = ALL_RESULTS.slice(start, end);
  const container = document.getElementById('results');
  
  if (!resultsSlice.length) {{
    container.innerHTML = '<div class="no-res">No results found — <a class="web-link" href="https://google.com/search?q={q_enc}">search Google directly →</a></div>';
  }} else {{
    container.innerHTML = buildCardsHTML(resultsSlice, '{q_enc}');
  }}
  
  updatePagination();
}}

function buildCardsHTML(results, qEnc) {{
  const h = (s) => s.replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[m]));
  return results.map(r => {{
    const title = h(r.title || '');
    const url = h(r.url || '#');
    const snippet = h(r.snippet || '');
    const domain = h(r.domain || '');
    const favicon = h(r.favicon || '');
    const displayUrl = h(r.display_url || '');
    const thumbnail = h(r.thumbnail || '');
    
    let thumbHtml = '';
    if (thumbnail) {{
      thumbHtml = `<img class="card-thumb" src="${{thumbnail}}" alt="" loading="lazy" onerror="this.style.display='none'">`;
    }}
    
    return `<div class="card" onclick="location.href='${{url}}'">
  <div class="card-inner">
    <div class="card-body">
      <div class="card-meta">
        <img class="fav" src="${{favicon}}" onerror="this.style.visibility='hidden'" width="14" height="14" alt="">
        <span class="dom">${{domain}}</span>
        <span class="durl">${{displayUrl}}</span>
      </div>
      <a class="card-title" href="${{url}}" onclick="event.stopPropagation()">${{title}}</a>
      <p class="card-snip">${{snippet}}</p>
      <a class="read-link" href="${{url}}" onclick="event.stopPropagation()">Visit site →</a>
    </div>
    ${{thumbHtml}}
  </div>
</div>`;
  }}).join('');
}}

function updatePagination() {{
  const totalPages = Math.ceil(ALL_RESULTS.length / RESULTS_PER_PAGE);
  const prevBtn = document.getElementById('prev-btn');
  const nextBtn = document.getElementById('next-btn');
  const pageInfo = document.getElementById('page-info');
  
  prevBtn.disabled = currentPage === 0;
  nextBtn.disabled = currentPage >= totalPages - 1;
  pageInfo.textContent = `Page ${{currentPage + 1}}`;
}}

document.getElementById('prev-btn').addEventListener('click', () => {{
  if (currentPage > 0) {{
    currentPage--;
    renderResults();
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
  }}
}});

document.getElementById('next-btn').addEventListener('click', () => {{
  const totalPages = Math.ceil(ALL_RESULTS.length / RESULTS_PER_PAGE);
  if (currentPage < totalPages - 1) {{
    currentPage++;
    renderResults();
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
  }}
}});

/* ── Image injection ── */
function injectImages(html) {{
  var container = document.getElementById('img-container');
  if (!container) return;
  container.innerHTML = html;
}}

/* ── Discovery chips ────────────────────────── */
(function() {{
  var topics = [
    QUERY + " guide",
    QUERY + " official",
    QUERY + " documentation",
    QUERY + " examples",
    QUERY + " applications",
    QUERY + " news",
    "how to " + QUERY,
  ].slice(0, 6);
  var chips = document.getElementById('chips');
  topics.forEach(function(t) {{
    var a = document.createElement('a');
    a.className   = 'chip';
    a.textContent = t;
    a.href        = OPAL + encodeURIComponent(t);
    chips.appendChild(a);
  }});
}})();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: build card HTML for a specific page (initial render)
# ─────────────────────────────────────────────────────────────────────────────

def _build_cards_for_page(results: list, page: int, per_page: int, q_enc: str) -> str:
    start = page * per_page
    end = start + per_page
    return _build_cards(results[start:end], q_enc)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: build card HTML
# ─────────────────────────────────────────────────────────────────────────────

def _build_cards(results: list, q_enc: str) -> str:
    """Render result cards.  Each card optionally shows a right-side thumbnail."""
    if not results:
        return (
            f'<div class="no-res">No results found — '
            f'<a class="web-link" '
            f'href="https://google.com/search?q={q_enc}">'
            f'search Google directly →</a></div>'
        )

    h   = _html_mod.escape   # shorthand
    out = []

    for r in results:
        title       = h(r.get("title",       ""))
        url         = h(r.get("url",         "#"))
        snippet     = h(r.get("snippet",     ""))
        domain      = h(r.get("domain",      ""))
        favicon     = h(r.get("favicon",     ""))
        display_url = h(r.get("display_url", ""))
        thumbnail   = h(r.get("thumbnail",   ""))

        thumb_html = ""
        if thumbnail:
            thumb_html = (
                f'<img class="card-thumb" src="{thumbnail}" '
                f'alt="" loading="lazy" '
                f'onerror="this.style.display=\'none\'">'
            )

        out.append(f"""
<div class="card" onclick="location.href='{url}'">
  <div class="card-inner">
    <div class="card-body">
      <div class="card-meta">
        <img class="fav" src="{favicon}"
             onerror="this.style.visibility='hidden'"
             width="14" height="14" alt="">
        <span class="dom">{domain}</span>
        <span class="durl">{display_url}</span>
      </div>
      <a class="card-title" href="{url}" onclick="event.stopPropagation()">{title}</a>
      <p class="card-snip">{snippet}</p>
      <a class="read-link" href="{url}" onclick="event.stopPropagation()">
        Visit site →
      </a>
    </div>
    {thumb_html}
  </div>
</div>""")

    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: build related links section
# ─────────────────────────────────────────────────────────────────────────────

def _build_related_links(links: list) -> str:
    """Render the 'Related Links' section if any links exist."""
    if not links:
        return ""

    h = _html_mod.escape
    out = []
    out.append('<div class="res-hdr">Related Links</div>')
    out.append('<div class="rel-box">')

    for l in links:
        name = h(l.get("name", ""))
        url  = h(l.get("url", "#"))
        desc = h(l.get("description", ""))
        fav  = h(l.get("favicon", ""))

        out.append(f"""
<a class="rel-card" href="{url}">
  <img class="rel-fav" src="{fav}" onerror="this.style.visibility='hidden'" alt="">
  <div class="rel-info">
    <span class="rel-name">{name}</span>
    {f'<span class="rel-desc">{desc}</span>' if desc else ''}
  </div>
  <span class="rel-arrow">⟶</span>
</a>""")

    out.append('</div>')
    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: build image results section
# ─────────────────────────────────────────────────────────────────────────────

def _build_images(images: list, query: str = "") -> str:
    """Render the 'Image Results' grid (4-thumbnail preview)."""
    if not images:
        return ""

    h = _html_mod.escape
    q_enc = quote_plus(query)
    out = []
    
    out.append('<div class="res-hdr" style="display:flex; justify-content:space-between; align-items:center;">')
    out.append('<span>Images</span>')
    if len(images) > 4:
        out.append(f'<a href="opal://discovery/images?q={q_enc}" class="view-all-btn">View All Images ⟶</a>')
    out.append('</div>')
    
    out.append('<div class="img-grid preview-grid">')

    # Show only the first 4 images in the main results page
    preview_images = images[:4]
    for img in preview_images:
        title   = h(img.get("title", ""))
        src     = h(img.get("img_src", ""))
        url     = h(img.get("url", "#"))
        source  = h(img.get("source", ""))
        
        if not src:
            continue

        out.append(f"""
<div class="img-item" onclick="window.open('{url}', '_blank')">
  <img src="{src}" alt="{title}" loading="lazy" referrerpolicy="no-referrer"
       onerror="console.error('Failed to load image:', '{src}'); this.style.display='none';">
  <div class="img-meta">{title or source}</div>
</div>""")

    out.append('</div>')
    
    if len(images) > 4:
        out.append(f"""
<div class="show-all-wrap">
  <a href="opal://discovery/images?q={q_enc}" class="show-all-btn">
    Show all image results
  </a>
</div>""")
    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: build related videos section
# ─────────────────────────────────────────────────────────────────────────────
def _build_videos(videos: list, query: str = "") -> str:
    """Render the 'Related Videos' section as a horizontal scroll strip."""
    if not videos or len(videos) == 0:
        return ""
        
    h = _html_mod.escape
    q_enc = quote_plus(query)
    out = []
    
    out.append('<div class="res-hdr" style="display:flex; justify-content:space-between; align-items:center;">')
    out.append('<span>Related Videos</span>')
    out.append('</div>')
    
    out.append('<div class="video-grid">')
    
    preview_videos = videos[:6]  # Show up to 6 videos
    for v in preview_videos:
        title       = h(v.get("title", ""))
        thumbnail   = h(v.get("img_src", "") or v.get("thumbnail", ""))
        url         = h(v.get("url", "#"))
        source      = h(v.get("source", ""))
        duration    = h(v.get("duration", ""))
        channel     = h(v.get("channel", ""))
        
        if not thumbnail:
            continue
            
        out.append(f"""
<div class="video-item" onclick="window.open('{url}', '_blank')">
  <div class="video-thumb-wrapper">
    <img class="video-thumb" src="{thumbnail}" alt="{title}" loading="lazy"
         onerror="console.error('Failed to load video thumb:', '{thumbnail}'); this.style.display='none';">
    {f'<div class="video-duration">{duration}</div>' if duration else ''}
  </div>
  <div class="video-info">
    <div class="video-title">{title}</div>
    <div class="video-meta">
      {f'<span class="video-channel">{channel}</span>' if channel else ''}
      {f'<span class="video-source">{source}</span>' if source else ''}
    </div>
  </div>
</div>""")
        
    out.append('</div>')
    return "".join(out)


def _build_image_results_page(query: str, images: list, dark_mode: bool = True) -> str:
    """Render a dedicated full-screen image results page."""
    q_esc = _html_mod.escape(query)
    q_enc = quote_plus(query)
    
    # Reuse theme logic
    from oled_theme import oled_enabled, oled_css_vars
    if oled_enabled():
        css_vars = oled_css_vars(20)
    elif dark_mode:
        css_vars = (
            "--bg:#080b14;--surface:rgba(255,255,255,0.028);--surface2:rgba(255,255,255,0.055);"
            "--border:rgba(255,255,255,0.08);--accent:#4fc3f7;--accent2:#9c6ff7;"
            "--text:#dde4f0;--muted:#6b7a99;--glow:rgba(79,195,247,0.18);"
            "--hdr-bg:rgba(8,11,20,0.88);--scrollbar:rgba(255,255,255,0.1);"
        )
    else:
        css_vars = (
            "--bg:#f0f4ff;--surface:rgba(0,0,0,0.03);--surface2:rgba(0,0,0,0.07);"
            "--border:rgba(0,0,0,0.09);--accent:#4f46e5;--accent2:#059669;"
            "--text:#1e1b4b;--muted:#6b7280;--glow:rgba(79,70,229,0.18);"
            "--hdr-bg:rgba(240,244,255,0.90);--scrollbar:rgba(0,0,0,0.15);"
        )

    h = _html_mod.escape
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Images: {q_esc} — Opal Discovery</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{{css_vars}}}
body{{
  background:var(--bg);color:var(--text);
  font-family:'Segoe UI',system-ui,sans-serif;
  overflow-x:hidden;
}}
::-webkit-scrollbar{{width:5px}}
::-webkit-scrollbar-thumb{{background:var(--scrollbar);border-radius:3px}}

.hdr{{
  position:sticky;top:0;z-index:100;
  background:var(--hdr-bg);backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border);
  padding:12px 28px;display:flex;align-items:center;gap:18px
}}
.brand{{display:flex;align-items:center;gap:7px;text-decoration:none;cursor:pointer}}
.brand-gem{{font-size:20px;filter:drop-shadow(0 0 7px var(--accent))}}
.brand-name{{
  font-size:11px;font-weight:700;letter-spacing:.12em;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent
}}
.title-area{{flex:1;font-size:14px;font-weight:500;color:var(--text);opacity:0.9}}

.page{{max-width:1200px;margin:0 auto;padding:30px 28px}}
.img-grid{{
  display:grid;grid-template-columns:repeat(auto-fill, minmax(240px, 1fr));
  gap:16px;
}}
.img-item{{
  position:relative;aspect-ratio:3/2;border-radius:12px;
  overflow:hidden;background:var(--surface2);border:1px solid var(--border);
  cursor:pointer;transition:transform .2s, box-shadow .2s;
  animation: fadeIn 0.4s ease forwards;
  animation-delay: calc(var(--i) * 0.05s);
  opacity: 0;
}}
.img-item:hover{{
  transform:translateY(-4px);box-shadow:0 12px 32px rgba(0,0,0,0.5);
  border-color:rgba(79,195,247,0.4);
}}
.img-item img{{width:100%;height:100%;object-fit:cover;transition:opacity 0.3s; opacity:0;}}
.img-item img.loaded{{opacity:1;}}
.img-meta{{
  position:absolute;bottom:0;left:0;right:0;padding:12px;
  background:linear-gradient(transparent, rgba(0,0,0,0.9));
  color:#fff;font-size:11px;opacity:0;transition:opacity .2s;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  pointer-events:none;
}}
.img-item:hover .img-meta{{opacity:1}}

@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
</style>
</head>
<body>
<header class="hdr">
  <div class="brand" onclick="history.back()" title="Go Back">
    <span class="brand-gem">◈</span>
    <span class="brand-name">OPAL DISCOVERY</span>
  </div>
  <div class="title-area">Images for "{q_esc}"</div>
</header>
<div class="page">
  <div class="img-grid">
    {_render_image_items(images, h)}
  </div>
</div>
<script>
document.querySelectorAll('.img-item img').forEach(img => {{
  if (img.complete) img.classList.add('loaded');
  else img.onload = () => img.classList.add('loaded');
  img.onerror = () => {{
    console.error('Failed to load image:', img.src);
    img.parentElement.style.display = 'none';
  }};
}});
</script>
</body>
</html>"""


def _render_image_items(images, h):
    items = []
    for i, img in enumerate(images):
        title   = h(img.get("title", ""))
        src     = h(img.get("img_src", ""))
        url     = h(img.get("url", "#"))
        source  = h(img.get("source", ""))
        if not src: continue
        items.append(f"""
<div class="img-item" style="--i:{i}" onclick="window.open('{url}', '_blank')">
  <img src="{src}" alt="{title}" loading="lazy">
  <div class="img-meta">{title or source}</div>
</div>""")
    return "".join(items)
