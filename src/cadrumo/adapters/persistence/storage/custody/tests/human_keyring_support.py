"""In-memory human keyring shared by the receipt suites."""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.storage.custody import acceleration_keychain


class KeyringError(Exception):
    """Controlled existing human keyring failure."""


class HumanKeyring:
    """Exact service/account in-memory keyring for the real receipt writer."""

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], str] = {}
        self.reads = 0

    def get_password(self, service_name: str, username: str) -> str | None:
        """Read one exact human account."""
        self.reads += 1
        return self.entries.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        """Store one exact human account."""
        self.entries[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        """Remove one exact human account."""
        self.entries.pop((service_name, username), None)


@pytest.fixture
def human_keyring(monkeypatch: pytest.MonkeyPatch) -> HumanKeyring:
    """Compose the real receipt crypto/filesystem with a controlled store."""
    keyring = HumanKeyring()
    monkeypatch.setattr(acceleration_keychain, "_keyring", lambda: (keyring, KeyringError, KeyringError))
    return keyring
