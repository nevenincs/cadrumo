"""Profile management for Playwright browser sessions."""

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
    """A browser profile holding persistent state and fingerprint entropy.

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
        """Create the parent directory for the storage state if it doesn't exist."""
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
