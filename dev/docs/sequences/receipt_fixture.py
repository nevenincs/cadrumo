"""Ephemeral, process-shared keyring for the documented sign-out journeys.

Only synthetic sandbox receipts enter this explicit test backend. Production
credential resolution never imports it; the default docs fixture has no vault.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from pathlib import Path

import keyring
import keyring.core
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

from cadrumo.core.atomic_write import atomic_write_bytes

RECEIPT_FIXTURE_DIRECTORY = "docs-synthetic-receipt-store"
PERSISTENT_SIGN_IN_SEQUENCES = frozenset({"profile-setup-logout", "profile-setup-delete", "protect-data-access-logout"})


def requires_persistent_sign_in(sequence_ids: Iterable[str]) -> bool:
    """Select custody from enrolled executable scenarios, never a page label."""
    return any(sequence_id in PERSISTENT_SIGN_IN_SEQUENCES for sequence_id in sequence_ids)


class SequenceReceiptKeyring(KeyringBackend):
    """Share synthetic proof between the real worker and its CLI frontends."""

    priority = 1

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root.resolve(strict=True)

    def _path(self, service: str, account: str) -> Path:
        digest = hashlib.sha256(f"{len(service)}:{service}{account}".encode()).hexdigest()
        return self.root / digest

    def get_password(self, service: str, username: str) -> str | None:
        try:
            return self._path(service, username).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    def set_password(self, service: str, username: str, password: str) -> None:
        atomic_write_bytes(self._path(service, username), password.encode())

    def delete_password(self, service: str, username: str) -> None:
        try:
            self._path(service, username).unlink()
        except FileNotFoundError:
            raise PasswordDeleteError("no synthetic receipt entry") from None


@contextmanager
def sequence_receipt_store(storage_root: Path, *, enabled: bool) -> Generator[None]:
    """Install a fresh synthetic store only for explicitly enrolled journeys."""
    if not enabled:
        yield
        return
    root = storage_root / RECEIPT_FIXTURE_DIRECTORY
    root.mkdir()
    previous = keyring.core._keyring_backend
    keyring.set_keyring(SequenceReceiptKeyring(root))
    try:
        yield
    finally:
        keyring.core._keyring_backend = previous
        for entry in root.iterdir():
            entry.unlink()
        root.rmdir()
