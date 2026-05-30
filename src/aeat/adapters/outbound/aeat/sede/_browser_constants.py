"""Playwright browser wait-state constants for the sede adapter.

Centralises the two Playwright ``wait_until`` / ``wait_for_load_state``
string literals used throughout the sede adapter so they are defined
once and verified by static analysis rather than spread as independent
string literals across every navigation call-site.
"""

from __future__ import annotations

from typing import Final

#: Playwright wait state that resolves as soon as the HTML document has
#: been parsed and the DOM is ready (no sub-resources awaited).
PLAYWRIGHT_WAIT_DOMCONTENTLOADED: Final[str] = "domcontentloaded"

#: Playwright wait state that resolves once all pending network requests
#: have completed or timed out (i.e., the network has gone idle).
PLAYWRIGHT_WAIT_NETWORKIDLE: Final[str] = "networkidle"
