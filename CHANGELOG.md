# Changelog

## [4.0.0] — 2026-07-30

### Added
- Sidebar AI assistant with Leo (local/remote LLM support)
- Opal search engine with query intent detection and semantic expansion
- NSIndex: modular search indexing pipeline with crawler, parser, ranker
- Visual new tab page with wallpaper backgrounds
- Password book with OS keyring integration
- Bookmark import from Chrome, Edge, Brave, Vivaldi, Opera, Firefox
- Toolbar bookmark bar with favicons (persisted across sessions)
- Right-click context menu on bookmark buttons (Open in New Tab, Remove Bookmark)
- Tab close button (top-right pill shape)
- Settings UI with toolbar mode, theme, and search provider configuration
- Enrichment pipeline for fetching page metadata/profiles
- Firecrawl content enrichment provider

### Fixed
- Newtab flicker on alt+tab: removed redundant `update()` calls in state change handlers
- `createWindow` returning `QWebEngineView` instead of `QWebEnginePage` (PyQt6 requirement)
- Last tab close causing black screen (index shift bug in `_close_tab`)
- Tab close button `border-radius` not matching tab card (applied inline stylesheet)
- Console noise from autofocus warnings and JS console forwarding (gated behind `NS_DEBUG`)
- Bookmark favicons blocking UI thread (moved to async background threads)
- Window icon not loading (renamed `favicon.ico` → `northstar.ico` to match code reference)

### Changed
- All debug prints gated behind `NS_DEBUG` environment variable
- Enrichment manager logging moved behind `_DEBUG` flag
- CORAL search timing prints gated behind `_DEBUG`
- Bookmark favicons cached to disk (base64 PNG in `northstar_favicons.json`)
- Cleaned up backup files and `__pycache__` directories

### Security
- Added `.gitignore` with `.env` ignore rule
- Created `.env.example` template (removes hardcoded API key exposure)
- Added MIT License
