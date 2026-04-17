"""Profile management for Playwright browser sessions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Profile:
    """A browser profile holding persistent state and fingerprint entropy.

    Attributes:
        name: A unique identifier for this profile.
        storage_state_path: Path to the JSON file containing cookies and localStorage.
        user_agent: Optional custom User-Agent string.
        locale: Optional locale (e.g., 'es-ES').
        timezone_id: Optional timezone (e.g., 'Europe/Madrid').
    """

    name: str
    storage_state_path: Path
    user_agent: str | None = None
    locale: str | None = "es-ES"
    timezone_id: str | None = "Europe/Madrid"

    def ensure_storage_dir(self) -> None:
        """Create the parent directory for the storage state if it doesn't exist."""
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
