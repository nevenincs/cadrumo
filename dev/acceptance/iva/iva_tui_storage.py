"""Fresh isolated scratch and secure-store ownership for installed IVA acceptance."""

from __future__ import annotations

from pathlib import Path

from .iva_tui_contracts import IvaInstalledTuiError


def _require_empty_directory(path: Path, *, label: str) -> Path:
    """Use caller-owned temporary output only when it has no previous evidence."""
    if path.exists() and any(path.iterdir()):
        raise IvaInstalledTuiError(f"{label} must be empty before an installed acceptance run")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()
