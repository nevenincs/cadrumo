"""Central browser automation surface for AEAT outbound adapters."""

from __future__ import annotations

from ._factory import (
    DefaultBrowserSession,
    create_browser_session,
    default_browser_session_factory,
    opened_browser_page,
    shared_playwright_runtime,
)
from ._site_health import (
    SiteHealthEvidence,
    SiteHealthState,
    SiteHealthStatus,
)
from ._site_health_parsers import (
    evaluate_response,
    parse_mantenimiento_banner,
    parse_rate_limit_response,
    parse_waf_challenge,
)
from .evasion import BrowserEvasionError, EvasionStrategy, PlaywrightStealthEvasion
from .health import run_health_check
from .profile import Profile
from .session import BrowserError, BrowserSession

__all__ = [
    "BrowserError",
    "BrowserEvasionError",
    "BrowserSession",
    "DefaultBrowserSession",
    "EvasionStrategy",
    "PlaywrightStealthEvasion",
    "Profile",
    "SiteHealthEvidence",
    "SiteHealthState",
    "SiteHealthStatus",
    "create_browser_session",
    "default_browser_session_factory",
    "evaluate_response",
    "opened_browser_page",
    "parse_mantenimiento_banner",
    "parse_rate_limit_response",
    "parse_waf_challenge",
    "run_health_check",
    "shared_playwright_runtime",
]
