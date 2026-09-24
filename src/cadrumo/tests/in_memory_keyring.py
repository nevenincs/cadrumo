"""A working keyring backend that starts empty in every process.

The keychain-less test backends refuse every call, so a process under them is
refused for want of a keychain before the question of a credential arises.
This one accepts writes and answers reads like a real credential store, but
holds nothing it was not given in the same process, so a fresh process that
selects it has a usable keychain with no session receipt in it: the only
thing it lacks is authentication. Selectable in a child process through
``PYTHON_KEYRING_BACKEND``.
"""

from __future__ import annotations

from typing import override

from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

IN_MEMORY_KEYRING = f"{__name__}.InMemoryKeyring"


class InMemoryKeyring(KeyringBackend):
    """A usable, process-local credential store that begins empty."""

    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self._entries: dict[tuple[str, str], str] = {}

    @override
    def get_password(self, service: str, username: str) -> str | None:
        return self._entries.get((service, username))

    @override
    def set_password(self, service: str, username: str, password: str) -> None:
        self._entries[(service, username)] = password

    @override
    def delete_password(self, service: str, username: str) -> None:
        if self._entries.pop((service, username), None) is None:
            raise PasswordDeleteError("no such entry")


__all__ = ["IN_MEMORY_KEYRING", "InMemoryKeyring"]
