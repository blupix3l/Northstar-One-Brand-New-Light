"""Legacy code kept for reference. Nothing in here is part of the browser.

`legacy/experimental_search/` holds the old Opal Discovery / NSIndex search
stack. It is unreachable from the browser UI (its only entry point,
`northstar://search?q=`, is only ever generated from inside the Opal page
itself) and is retained here for reference only.

The single piece of it that the browser still uses is the omnibox URL
heuristic in `legacy/experimental_search/northstar_search.py`
(`_is_url` / `format_url`).
"""
