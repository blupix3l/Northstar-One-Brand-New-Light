# NorthStar Browser

A privacy-focused, feature-rich web browser built with PyQt6 and QWebEngine.

## Features

- **Tabbed browsing** with visual tab cards and keyboard shortcuts
- **DuckDuckGo-powered search** with optional Brave Search API
- **Bookmark manager** with import from Chrome, Edge, Firefox, Brave, Vivaldi, Opera
- **Visual new tab page** with wallpaper backgrounds and quick-dial bookmarks
- **Sidebar AI assistant** (Leo) with local (Ollama) and remote (OpenAI, Groq) LLM support
- **Password book** with OS keyring integration
- **Settings UI** for theme, toolbar mode, search provider, and API keys
- **Content enrichment** via Firecrawl for rich page previews
- **NSIndex** — built-in search indexing engine with crawling and ranking

Experimental search/discovery components are grouped in `experimental_search/`.
The browser continues to use these modules for its existing Opal search and
discovery views; the folder is for organization and does not disable them.

## Requirements

- Python 3.10+
- PyQt6 (tested with 6.8+)
- PyQt6-WebEngine
- requests
- keyring (optional, for password book)
- Firecrawl SDK (optional, for content enrichment)

## Quick Start

```bash
# Install dependencies
python dependency_manager.py

# Launch
python NorthStar_v1.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NS_DEBUG=1` | Enable debug logging |
| `NS_SEARCH_PROVIDER` | `duckduckgo` (default) or `brave` |
| `FIRECRAWL_API_KEY` | Firecrawl API key for content enrichment |
| `SERPAPI_API_KEY` | SerpAPI key (alternative search) |

Copy `.env.example` to `.env` to configure.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+T` | New tab |
| `Ctrl+W` | Close tab |
| `Ctrl+Tab` | Next tab |
| `Ctrl+Shift+Tab` | Previous tab |
| `Ctrl+L` / `Alt+D` | Focus address bar |
| `Ctrl+B` | Toggle bookmarks |

## License

MIT
