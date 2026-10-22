# NorthStar Search Providers

NorthStar's `search` package uses a modular provider architecture. All
providers implement `SearchProvider` and return `SearchResult` objects,
which the `SearchManager` fans out concurrently, de-duplicates, caches,
and merges.

## Built-in providers (always available)

| Key         | Class                     | Source            | Notes                                  |
|-------------|---------------------------|-------------------|----------------------------------------|
| `nsindex`   | `NSIndexProvider`         | `nsindex`         | Local index, instant.                  |
| `duckduckgo`| `DuckDuckGoProvider`      | `duckduckgo`      | DDG instant-answer **HTML/API** fallback. |
| `brave`     | `BraveSearchProvider`     | `brave`           | Requires `BRAVE_SEARCH_API_KEY`.       |

## Optional providers (auto-detected)

These register **only if available**. If a tool/library is missing the
provider silently disables itself and returns `[]` — it never crashes the
pipeline.

| Key           | Class                     | Backend                | Detected via                  | Tag                    |
|---------------|---------------------------|------------------------|-------------------------------|------------------------|
| `ddglib`      | `DuckDuckGoLibProvider`   | `duckduckgo-search` lib| Python import                | `ddglib`                |
| `ddgr`        | `DDGRProvider`            | `ddgr` CLI             | `shutil.which("ddgr")`        | `ddgr`                  |
| `fd`          | `FdProvider`              | `fd` CLI               | `shutil.which("fd")`          | `Local File`           |
| `rg`          | `RipGrepProvider`         | `ripgrep` CLI          | `shutil.which("rg")`          | `Local Code` / `Local Content` |

### Installing optional backends

```bash
pip install duckduckgo-search   # enables ddglib
# ddgr, fd, rg are system CLIs: install via your package manager
```

### Local search configuration (env vars)

| Variable                | Default      | Purpose                              |
|-------------------------|--------------|--------------------------------------|
| `NS_LOCAL_SEARCH_ROOT`  | user home    | Root directory scoped for `fd`/`rg`. |
| `NS_LOCAL_SEARCH_MAX`   | `20`         | Max local results returned.          |

## Provider priority (fan-out order)

Defined by `_LIVE_ORDER` in `search/manager.py`:

```
nsindex → ddglib → ddgr → duckduckgo → brave → fd → rg
```

Local filesystem results (`fd`, `rg`) use `file://` URLs and are tagged
`"Local File"` / `"Local Code"` / `"Local Content"` so the UI can group
them under separate "Local Files" / "Local Code" headings rather than
mixing them with web results.

## Concurrency & timeouts

All providers run inside `SearchManager`'s `ThreadPoolExecutor`. Each has a
per-provider timeout in `_PROVIDER_TIMEOUT`; CLI providers additionally
apply an in-process `subprocess.run(timeout=...)`. A slow or failing
provider can never stall or abort the overall search.

## Benchmarking

Each provider logs its elapsed time on every call, e.g.:

```
[SEARCH] nsindex      7 ms  results=3
[SEARCH] ddglib     143 ms  results=8
[SEARCH] ddgr       182 ms  results=6
[SEARCH] Local File  11 ms  results=2
[SEARCH] Local Code  18 ms  results=4
```
