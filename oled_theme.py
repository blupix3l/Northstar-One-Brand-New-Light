"""
oled_theme.py — OLED Mode for NorthStar
=======================================
Centralized OLED colour/token system.

OLED Mode is layered onto NorthStar's existing theme architecture instead of
replacing it:

  * Qt chrome (toolbars, tabs, panels, menus, dialogs) is driven by the token
    dict returned by `oled_qss_tokens()`; NorthStar_v1's `_theme_qss()`
    emitter consumes it alongside the normal dark/light tokens so the selector
    block is written exactly once.
  * The embedded HTML pages (new tab, settings, notes, extensions, Opal)
    pull their OLED palette from `oled_web_tokens()` / `oled_css_vars()`
    so there is exactly one source of truth for OLED colours.

Flipping the Fernway `oled_mode` key on/off is fully reversible and leaves the
standard NorthStar theme untouched.

Palette — true-black OLED with refined gold accents:
  surfaces   #000000 / #0a0a0a / #121212
  accent     #d4af37 (restrained gold), hover #e8cd77, deep #b8932f
  text       #e8edf8, muted tinted white — gold is used for emphasis only.
"""

from fernway_manager import get_fernway

# ── Palette ───────────────────────────────────────────────────────────────────
ACCENT        = "#d4af37"
ACCENT_HOVER  = "#e8cd77"
ACCENT_DEEP   = "#b8932f"
BORDER        = "rgba(212,175,55,0.28)"     # faint dark-gold separators
BORDER_IMPORTANT = "rgba(212,175,55,0.55)"  # active/focus edges
GLOW          = "rgba(212,175,55,0.30)"     # soft inner glows, gradients

BG            = "#000000"
SURFACE       = "#0a0a0a"
SURFACE_2     = "#121212"
HOVER         = "rgba(24,20,8,0.92)"        # gold-tinted hover wash
ACTIVE        = "rgba(34,28,10,0.96)"       # active tab / selected

TEXT          = "#e8edf8"
TEXT_MUTED    = "rgba(200,210,240,0.55)"
INPUT_BG      = "rgba(0,0,0,0.80)"
SCROLLBAR     = "rgba(212,175,55,0.35)"

DL_DONE_BG    = "rgba(18,14,5,0.85)"
DL_DONE_BDR   = "rgba(232,205,119,0.40)"

# Wallpaper live-video sources (the OLED default mirrors the dark galaxy vibe).
WALLPAPER_VIDEO_DEFAULT = "https://moewalls.com/wp-content/uploads/preview/2026/orbital-dawn-preview.webm"
WALLPAPER_VIDEO_OLED   = WALLPAPER_VIDEO_DEFAULT


def oled_enabled() -> bool:
    """True when OLED Mode is active in Fernway."""
    try:
        return bool(get_fernway().get("oled_mode", False))
    except Exception:
        return False


def oled_wallpaper_video_src() -> str:
    """Live wallpaper video used in OLED Mode (else the stock one)."""
    return WALLPAPER_VIDEO_OLED if oled_enabled() else WALLPAPER_VIDEO_DEFAULT


# ── Qt chrome tokens (consumed by NorthStar_v1._theme_qss) ────────────────────
def oled_qss_tokens(fw) -> dict:
    """Full OLED token dict for the Qt chrome QSS emitter.

    Mirrors the key set produced by NorthStar_v1 for dark/light so the shared
    `_theme_qss(t)` selector template can render OLED with zero duplication.
    """
    opacity = float(fw.get("transparency_level", 0.88) or 0.88)
    tab_style = fw.get("tab_style", "default")
    sidebar_style = fw.get("sidebar_style", "default")
    leo_style = fw.get("leo_appearance", "glass")

    glass  = f"rgba(0,0,0,{opacity})"
    glass2 = f"rgba(10,10,10,{min(1.0, opacity + 0.08)})"

    logo_grad = (
        "qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        f"stop:0 {ACCENT},stop:0.5 {ACCENT_HOVER},stop:1 {ACCENT_DEEP})"
    )
    grad = (
        "qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        f"stop:0 {ACCENT},stop:1 {ACCENT_HOVER})"
    )

    toolbar_bg = "rgba(0,0,0,0.85)"
    sidebar_glass = "rgba(0,0,0,0.85)"

    tab_radius = (
        "10px" if tab_style == "default"
        else "4px" if tab_style == "compact"
        else "16px"
    )
    tab_border = (
        BORDER if tab_style not in ("glass", "floating")
        else "rgba(212,175,55,0.22)"
    )

    sidebar_bg = (
        sidebar_glass
        if sidebar_style in ("default", "floating")
        else "transparent"
        if sidebar_style == "minimal"
        else glass2
    )
    if sidebar_style == "floating":
        sidebar_qss = (
            f"background:{sidebar_glass};"
            f"border-right:1px solid {BORDER};"
            "border-top-right-radius:22px;border-bottom-right-radius:22px;margin:0;"
        )
    else:
        sidebar_qss = (
            f"background:{sidebar_bg};"
            f"border-right:1px solid {BORDER if sidebar_style != 'minimal' else 'none'};"
        )

    leo_bg = (
        glass if leo_style == "glass"
        else BG if leo_style == "solid"
        else "transparent"
    )
    leo_border = f"1px solid {BORDER}" if leo_style != "minimal" else "none"

    return {
        "bg_base": "000000",
        "glass": glass,
        "glass2": glass2,
        "hover": HOVER,
        "active": ACTIVE,
        "border": BORDER,
        "glow": BORDER_IMPORTANT,
        "accent": ACCENT,
        "accent2": ACCENT_HOVER,
        "accent3": ACCENT_DEEP,
        "text": TEXT,
        "text2": TEXT_MUTED,
        "input_bg": INPUT_BG,
        "scroll": SCROLLBAR,
        "dl_done_bg": DL_DONE_BG,
        "dl_done_bdr": DL_DONE_BDR,
        "logo_grad": logo_grad,
        "grad": grad,
        "toolbar_bg": toolbar_bg,
        "menu_bg": "rgba(10,10,10,0.80)",
        "bookmarks_bar_bg": "rgba(0,0,0,0.80)",
        "tab_radius": tab_radius,
        "tab_border": tab_border,
        "sidebar_qss": sidebar_qss,
        "leo_bg": leo_bg,
        "leo_border": leo_border,
    }


def oled_popup_qss() -> str:
    """OLED chrome for Qt surfaces the base QSS does not cover."""
    return f"""
QMenu {{ background-color: {SURFACE}; color: {TEXT};
        border: 1px solid {BORDER}; border-radius: 8px; padding: 5px; }}
QMenu::item {{ background: transparent; padding: 6px 22px 6px 10px; border-radius: 5px; }}
QMenu::item:selected {{ background: {HOVER}; color: {ACCENT_HOVER}; }}
QMenu::item:disabled {{ color: {TEXT_MUTED}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
QMenuBar {{ background-color: {BG}; color: {TEXT}; border-bottom: 1px solid {BORDER}; }}
QMenuBar::item {{ background: transparent; padding: 5px 10px; }}
QMenuBar::item:selected {{ background: {HOVER}; }}
QToolTip {{ background-color: {SURFACE_2}; color: {TEXT};
           border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 8px; }}
QDialog, QMessageBox, QInputDialog, QFileDialog
        {{ background-color: {BG}; color: {TEXT}; }}
QComboBox QAbstractItemView {{ background-color: {SURFACE}; color: {TEXT};
                              border: 1px solid {BORDER}; outline: 0;
                              selection-background-color: {HOVER};
                              selection-color: {ACCENT_HOVER}; }}
"""


def oled_toolbar_qss() -> str:
    """OLED toolbar override — pure black chrome, gold removed.

    The toolbar keeps its true-black glass, but every gold accent on it
    (bottom hairline, address-bar borders/focus, pressed/hover button
    colours, load-progress bar, text selection) is swapped for a neutral
    white/black tone.  Scoped to `#Toolbar` descendants so the sidebar,
    tabs, and panels keep the OLED gold identity.
    """
    _line   = "rgba(255,255,255,0.05)"
    _edge   = "rgba(255,255,255,0.10)"
    _edge_h = "rgba(255,255,255,0.22)"
    _edge_f = "rgba(255,255,255,0.35)"
    _sel_bg = "rgba(255,255,255,0.28)"
    return f"""
#Toolbar {{ border-bottom-color: {_line}; }}
#Toolbar #AddressBar {{ border: 1px solid {_edge};
    selection-background-color: {_sel_bg}; selection-color: {BG}; }}
#Toolbar #AddressBar:focus {{ border: 2px solid {_edge_f}; }}
#Toolbar #AddressBar:hover:!focus {{ border-color: {_edge_h}; }}
#Toolbar #NavBtn:pressed {{ color: {TEXT}; }}
#Toolbar #BmBtn:hover {{ color: {TEXT}; }}
#Toolbar #LoadProgress::chunk {{ background: {_edge_h}; }}
#BookmarksBar #NavBtn:pressed {{ color: {TEXT}; }}
"""


# ── Embedded web-page tokens ──────────────────────────────────────────────────
def oled_web_tokens(opacity: float = 0.85) -> dict:
    """Python-dict palette for `_build_*_html` pages."""
    bg = f"rgba(0,0,0,{min(1.0, max(0.5, opacity))})"
    return {
        "bg": BG,
        "page_bg": bg,
        "surface": "rgba(255,255,255,0.03)",
        "surface2": "rgba(255,255,255,0.055)",
        "card_bg": "rgba(6,6,6,0.92)",
        "card_bdr": BORDER,
        "input_bg": "rgba(0,0,0,0.78)",
        "text": TEXT,
        "muted": TEXT_MUTED,
        "accent": ACCENT,
        "accent2": ACCENT_HOVER,
        "border": BORDER,
        "glow": GLOW,
        "scrollbar": SCROLLBAR,
    }


def oled_css_vars(blur_str: int = 20) -> str:
    """Inline CSS custom-property block for JS-driven pages (Opal, loading…)."""
    return (
        f"--bg:{BG};--surface:rgba(255,255,255,0.028);"
        f"--surface2:rgba(255,255,255,0.055);--border:{BORDER};"
        f"--accent:{ACCENT};--accent2:{ACCENT_HOVER};--text:{TEXT};"
        f"--muted:{TEXT_MUTED};--glow:{GLOW};--hdr-bg:rgba(0,0,0,0.88);"
        f"--scrollbar:{SCROLLBAR};--link-accent:{ACCENT_HOVER};"
        f"--thumb-bg:rgba(255,255,255,0.03);--blur:{blur_str}px;"
    )