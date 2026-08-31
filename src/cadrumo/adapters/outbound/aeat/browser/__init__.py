"""Central browser-automation surface for AEAT outbound adapters.

Owns the Playwright-backed browser sessions every outbound AEAT adapter
shares, plus the site-health probing that classifies whether the Sede is
reachable, rate-limiting, under maintenance, or serving a WAF challenge.
The optional browser runtime is materialised only by the session factories;
importing this facade exposes types and factories without opening a browser.
Non-OK site-health classifications are carried through
:class:`core.errors.SiteHealthError` so diagnostics and live-read
application code can inspect one status envelope instead of re-parsing pages.

Major declarations:

* :class:`BrowserSession` and :class:`DefaultBrowserSession`, with
  :func:`create_browser_session` and :func:`default_browser_session_factory`
  — the session abstraction and its factories.
* :func:`run_health_check` with :class:`SiteHealthStatus` and
  :class:`core.errors.SiteHealthState` — the reachability probe and its verdict.
* :class:`EvasionStrategy` and :class:`PlaywrightStealthEvasion` — the
  bot-detection evasion seam.
* :class:`BrowserError`, :class:`BrowserValidationError`, and
  :class:`BrowserFailureMode` — the failure taxonomy.

See Also:
    :class:`adapters.outbound.aeat.auth.BrowserContextProvisioner`
        Auth-provider hook consumed by :meth:`BrowserSession.create_context`.
    :class:`adapters.outbound.aeat.auth.CertificateContextProvisioner`
        Certificate-auth provisioner that adds Playwright client-certificate
        kwargs at browser-context construction time.
    :mod:`adapters.outbound.aeat.sede`
        Read-only Sede readers that consume these browser sessions.
"""

from __future__ import annotations

from ._site_health_parsers import (
    evaluate_response,
    parse_mantenimiento_banner,
    parse_rate_limit_response,
    parse_waf_challenge,
)
from .errors import BrowserError, BrowserFailureMode, BrowserValidationError
from .evasion import BrowserEvasionError, EvasionStrategy, PlaywrightStealthEvasion
from .factory import (
    DefaultBrowserSession,
    create_browser_session,
    default_browser_session_factory,
    opened_browser_page,
    shared_playwright_runtime,
)
from .health import run_health_check
from .profile import Profile
from .session import BrowserSession
from .site_health_records import (
    SiteHealthEvidence,
    SiteHealthStatus,
)

__all__ = [
    "BrowserError",
    "BrowserEvasionError",
    "BrowserFailureMode",
    "BrowserSession",
    "BrowserValidationError",
    "DefaultBrowserSession",
    "EvasionStrategy",
    "PlaywrightStealthEvasion",
    "Profile",
    "SiteHealthEvidence",
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
