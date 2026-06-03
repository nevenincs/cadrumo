"""Playwright browser wait-state constants and settings accessors for the sede adapter.

Centralises the Playwright ``wait_until`` / ``wait_for_load_state`` string
literals and the settings-backed viewport / probe-timeout accessors used
throughout the sede adapter so they are defined once and verified by static
analysis rather than duplicated across every navigation module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

from .....core.config import load_settings
from .....core.external_constants import LATIN_1_ENCODING

if TYPE_CHECKING:
    from playwright.async_api import ViewportSize

#: Playwright wait state that resolves as soon as the HTML document has
#: been parsed and the DOM is ready (no sub-resources awaited).
PLAYWRIGHT_WAIT_DOMCONTENTLOADED: Final[Literal["domcontentloaded"]] = "domcontentloaded"

#: Playwright wait state that resolves once all pending network requests
#: have completed or timed out (i.e., the network has gone idle).
PLAYWRIGHT_WAIT_NETWORKIDLE: Final[Literal["networkidle"]] = "networkidle"

#: Short Playwright timeout (ms) used for non-critical ``wait_for_load_state`` probes
#: inside retry loops where proceeding on timeout is the desired behaviour.
PLAYWRIGHT_TIMEOUT_SHORT_MS: Final[int] = 2_000

#: Character encoding used by the AEAT sede for legacy fixed-width response bodies
#: (e.g. Modelo 303 page-03 records).  Alias of the canonical
#: :data:`~aeat.core.external_constants.LATIN_1_ENCODING` constant; kept under
#: this adapter-local name so existing callers do not need to reach into
#: ``external_constants`` directly.
SEDE_BODY_ENCODING: Final[str] = LATIN_1_ENCODING


def default_viewport() -> ViewportSize:
    """Return the configured browser viewport size from settings."""
    settings = load_settings()
    return {
        "width": settings.aeat_browser_viewport_width,
        "height": settings.aeat_browser_viewport_height,
    }


def selector_probe_timeout_ms() -> int:
    """Return the configured selector-probe timeout (ms) from settings."""
    return load_settings().aeat_browser_selector_probe_timeout_ms
