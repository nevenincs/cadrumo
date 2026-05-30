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

#: Short Playwright timeout (ms) used for non-critical ``wait_for_load_state`` probes
#: inside retry loops where proceeding on timeout is the desired behaviour.
PLAYWRIGHT_TIMEOUT_SHORT_MS: Final[int] = 2_000

#: Character encoding used by the AEAT sede for legacy fixed-width response bodies
#: (e.g. Modelo 303 page-03 records).  ISO 8859-1 is the AEAT canonical encoding;
#: ``latin-1`` is Python's alias for the same codec.
SEDE_BODY_ENCODING: Final[str] = "latin-1"
