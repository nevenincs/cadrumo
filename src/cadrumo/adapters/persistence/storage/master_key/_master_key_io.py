"""Master-key byte encoding, secure writes, and passphrase resolution."""

from __future__ import annotations

import base64
import getpass
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final

from .....core.atomic_write import atomic_write_hardened_bytes
from ..errors import SecretStoreError

__all__ = [
    "PASSPHRASE_ENV_VAR",
    "PassphraseCallback",
    "_b64decode",
    "_b64encode",
    "_default_passphrase_callback",
    "_zeroise",
    "atomic_write_secure_bytes",
]

PASSPHRASE_ENV_VAR: Final[str] = "CADRUMO_SECRET_PASSPHRASE"  # noqa: S105 - env var name, not secret value
"""Environment variable consulted by the file backend before prompting."""

PassphraseCallback = Callable[[], str]
"""Pluggable hook for tests — callable returning the passphrase as a str."""


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def atomic_write_secure_bytes(target: Path, payload: bytes) -> None:
    """Atomically write ``payload`` to ``target`` with mode ``0o600``."""
    atomic_write_hardened_bytes(target, payload)


def _zeroise(buffer: bytearray | None) -> None:
    """Best-effort overwrite of a mutable buffer with zero bytes."""
    if buffer is None:
        return
    for i in range(len(buffer)):
        buffer[i] = 0


def _default_passphrase_callback(getpass_fn: Callable[[str], str] | None = None) -> str:
    """Resolve the operator's passphrase from env or stdin."""
    from .....core.config import load_settings

    configured = load_settings().cadrumo_secret_passphrase
    if configured is not None:
        normalized = configured.get_secret_value().rstrip("\r\n")
        if not normalized:
            raise SecretStoreError(
                f"{PASSPHRASE_ENV_VAR} is set to whitespace-only; supply a non-empty passphrase.",
            )
        return normalized
    if getpass_fn is None and (not sys.stdin.isatty() or not sys.stderr.isatty()):
        raise SecretStoreError(
            f"{PASSPHRASE_ENV_VAR} is not set and stdin is not interactive; "
            "re-run the command from an interactive terminal (the CLI prompts "
            f"for the passphrase) or provide {PASSPHRASE_ENV_VAR} through the "
            "Settings environment.",
        )
    resolver = getpass_fn if getpass_fn is not None else getpass.getpass
    return resolver("AEAT secret-store passphrase: ")
