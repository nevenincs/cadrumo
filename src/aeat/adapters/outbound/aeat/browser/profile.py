"""Profile defaults for Playwright browser sessions.

:class:`Profile` is the small browser-runtime record consumed by
:class:`aeat.adapters.outbound.aeat.browser.BrowserSession`,
:func:`aeat.adapters.outbound.aeat.browser.default_browser_session_factory`, and
Sede helpers that open Playwright pages. It carries the profile name, fallback
storage-state JSON path, optional user agent, and the locale/timezone values
forwarded into ``browser.new_context(...)``.

The locale and timezone defaults are resolved lazily from
:class:`aeat.core.config.Settings` when a ``Profile`` is instantiated. Importing
this module therefore does not construct settings or validate external
constants for commands that never touch the browser adapter.

See Also:
    :meth:`aeat.adapters.outbound.aeat.browser.BrowserSession.create_context`
        Consumes :class:`Profile` to build Playwright context kwargs.
    :func:`aeat.adapters.outbound.aeat.browser.opened_browser_page`
        Uses :class:`Profile` for short-lived Sede browser contexts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .....core.config import Settings as _Settings


def _browser_locale_default() -> str | None:
    """Resolve the default browser locale lazily.

    ``Settings()`` constructs the full pydantic-settings object,
    which validates the external-constants payload. Building it at
    module-import time meant a transient external-constants /
    model disagreement could crash an unrelated command — even
    ``--help`` of a verb that never touches the browser — with a raw
    ``ExternalConstants`` ``ValidationError``. Deferring the
    construction to first use (when a ``Profile`` is actually
    instantiated) confines any settings-data drift to the code path
    that genuinely needs the browser adapter.
    """
    return _Settings().aeat_browser_locale


def _browser_timezone_default() -> str | None:
    """Resolve the default browser timezone lazily (see :func:`_browser_locale_default`)."""
    return _Settings().aeat_browser_timezone


@dataclass
class Profile:
    """Browser profile values forwarded into a Playwright context.

    ``storage_state_path`` is a fallback path: auth providers and Sede readers
    may pass an explicit storage-state path or in-memory state to
    :meth:`aeat.adapters.outbound.aeat.browser.BrowserSession.create_context`,
    which takes precedence. ``locale`` and ``timezone_id`` default from
    :class:`aeat.core.config.Settings` at construction time unless supplied
    explicitly.

    Attributes:
        name: A unique identifier for this profile.
        storage_state_path: Path to the JSON file containing cookies and localStorage.
        user_agent: Optional custom User-Agent string.
        locale: Optional locale (e.g., 'es-ES'); defaults to ``Settings.aeat_browser_locale``.
        timezone_id: Optional timezone (e.g., 'Europe/Madrid'); defaults to
            ``Settings.aeat_browser_timezone``.
    """

    name: str
    storage_state_path: Path
    user_agent: str | None = None
    locale: str | None = field(default_factory=_browser_locale_default)
    timezone_id: str | None = field(default_factory=_browser_timezone_default)

    def ensure_storage_dir(self) -> None:
        """Create the parent directory for ``storage_state_path`` only.

        :meth:`BrowserSession.create_context <aeat.adapters.outbound.aeat.browser.BrowserSession.create_context>`
        calls this before deciding whether the fallback storage-state file
        exists. The method creates directories but never creates or mutates the
        storage-state JSON file itself.
        """
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
