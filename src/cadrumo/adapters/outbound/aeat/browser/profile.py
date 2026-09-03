"""Profile defaults for Playwright browser sessions.

:class:`Profile` is the small browser-runtime record consumed by
:class:`adapters.outbound.aeat.browser.BrowserSession`,
:func:`adapters.outbound.aeat.browser.default_browser_session_factory`, and
Sede helpers that open Playwright pages. It carries the profile name, optional
user agent, and the locale/timezone values
forwarded into ``browser.new_context(...)``.

The locale and timezone defaults are resolved lazily from
:class:`core.config.Settings` when a ``Profile`` is instantiated. Importing
this module therefore does not construct settings or validate external
constants for commands that never touch the browser adapter.

See Also:
    :meth:`adapters.outbound.aeat.browser.BrowserSession.create_context`
        Consumes :class:`Profile` to build Playwright context kwargs.
    :func:`adapters.outbound.aeat.browser.opened_browser_page`
        Uses :class:`Profile` for short-lived Sede browser contexts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .....core.config import Settings as _Settings


def _browser_locale_default() -> str | None:
    """Resolve the default browser locale lazily.

    ``Settings()`` constructs the full pydantic-settings object,
    which validates the external-constants payload. Building it at
    module-import time meant a transient external-constants /
    model disagreement could crash an unrelated command — even
    ``--help`` of a verb that never touches the browser — with a raw
    ``ExternalConstantRegistry`` ``ValidationError``. Deferring the
    construction to first use (when a ``Profile`` is actually
    instantiated) confines any settings-data drift to the code path
    that genuinely needs the browser adapter.
    """
    return _Settings().cadrumo_browser_locale


def _browser_timezone_default() -> str | None:
    """Resolve the default browser timezone lazily (see :func:`_browser_locale_default`)."""
    return _Settings().cadrumo_browser_timezone


@dataclass
class Profile:
    """Browser profile values forwarded into a Playwright context.

    Auth providers and Sede readers pass decrypted storage state explicitly as
    an in-memory mapping to
    :meth:`adapters.outbound.aeat.browser.BrowserSession.create_context`.
    ``locale`` and ``timezone_id`` default from
    :class:`core.config.Settings` at construction time unless supplied
    explicitly.

    Attributes:
        name: A unique identifier for this profile.
        user_agent: Optional custom User-Agent string.
        locale: Optional locale (e.g., 'es-ES'); defaults to ``Settings.cadrumo_browser_locale``.
        timezone_id: Optional timezone (e.g., 'Europe/Madrid'); defaults to
            ``Settings.cadrumo_browser_timezone``.
    """

    name: str
    user_agent: str | None = None
    locale: str | None = field(default_factory=_browser_locale_default)
    timezone_id: str | None = field(default_factory=_browser_timezone_default)
