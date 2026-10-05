"""Fresh caller-owned storage preflight for installed ledger acceptance."""

from __future__ import annotations

from pathlib import Path

from .installed_tui_contracts import LedgerInstalledTuiError


def _require_empty_directory(path: Path, *, label: str) -> Path:
    """Create one caller-owned acceptance directory only when it is fresh."""
    if path.exists() and any(path.iterdir()):
        raise LedgerInstalledTuiError(f"{label} must be fresh and empty")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()
