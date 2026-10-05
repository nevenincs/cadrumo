"""Caller-owned directory and immutable identity preflight for withholding acceptance."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .cli_contracts import RetencionesInstalledCliError


def _fresh_directory(path: Path, *, label: str) -> Path:
    """Claim one explicit empty caller-provided acceptance root."""
    if path.exists() and any(path.iterdir()):
        raise RetencionesInstalledCliError(stage="preflight", diagnostic_code=f"nonempty_{label.replace(' ', '_')}")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _require_nonempty_identity(value: str, *, label: str) -> None:
    """Reject a receipt coordinate that cannot identify its evaluated build."""
    if not value.strip():
        raise RetencionesInstalledCliError(stage="preflight", diagnostic_code=f"missing_{label}")


def _sha256_file(path: Path) -> str:
    """Return the identity digest of the executable actually invoked."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
