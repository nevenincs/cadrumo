"""Isolated continuation scratch ownership and pinned annual schema selection."""

from __future__ import annotations

from pathlib import Path

from .continuation_contracts import InstalledContinuationError


def _require_empty(path: Path, *, label: str) -> Path:
    if path.exists() and any(path.iterdir()):
        raise InstalledContinuationError(f"{label} must be fresh and empty")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _annual_schema(workspace_root: Path, year: int) -> Path:
    candidates = tuple(
        (workspace_root / "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files").glob(
            f"*-100-esquema-xsd-ejercicio-{year}-*.xsd"
        )
    )
    if len(candidates) != 1:
        raise InstalledContinuationError("selected Modelo 100 revision has no unambiguous official XSD")
    return candidates[0]
