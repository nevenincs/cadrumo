"""Master-key byte encoding, secure writes, and passphrase resolution."""

from __future__ import annotations

import base64
import getpass
import os
import secrets
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final

from .....core.locks import fsync_parent_dir
from .....core.logging import get_logger
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

_log = get_logger(__name__)

PASSPHRASE_ENV_VAR: Final[str] = "AEAT_SECRET_PASSPHRASE"  # noqa: S105 - env var name, not secret value
"""Environment variable consulted by the file backend before prompting."""

PassphraseCallback = Callable[[], str]
"""Pluggable hook for tests — callable returning the passphrase as a str."""


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def atomic_write_secure_bytes(target: Path, payload: bytes) -> None:
    """Atomically write ``payload`` to ``target`` with mode ``0o600``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f"{target.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    fd = os.open(tmp_path, flags, 0o600)
    try:
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_path, target)
        fsync_parent_dir(target)
    except BaseException:
        _log.error("master_key: atomic write failed target=%s", target, exc_info=True)
        try:
            os.unlink(tmp_path)
        except OSError as cleanup_exc:
            _log.debug(
                "master_key: atomic write tempfile cleanup failed error_type=%s",
                type(cleanup_exc).__name__,
            )
        raise


def _zeroise(buffer: bytearray | None) -> None:
    """Best-effort overwrite of a mutable buffer with zero bytes."""
    if buffer is None:
        return
    for i in range(len(buffer)):
        buffer[i] = 0


def _default_passphrase_callback(getpass_fn: Callable[[str], str] | None = None) -> str:
    """Resolve the operator's passphrase from env or stdin."""
    from .....core.config import load_settings

    configured = load_settings().aeat_secret_passphrase
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
            "run `aeat config unlock NAME` from an interactive terminal or "
            f"provide {PASSPHRASE_ENV_VAR} through the Settings environment.",
        )
    resolver = getpass_fn if getpass_fn is not None else getpass.getpass
    return resolver("AEAT secret-store passphrase: ")
