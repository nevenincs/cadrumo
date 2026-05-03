"""Session-scoped fixtures for the casilla-corpus tests.

The corpus contains ~200 JSON catalogues. The legacy layout had each
test re-walk the directory and re-parse every file, multiplying the
parse cost by the number of tests in a module (~13x for
``test_corpus_rule_alignment``). These fixtures load every catalogue
exactly once per session and hand the cached objects to every test
that needs them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...core.config import PROJECT_ROOT
from . import load_casillas
from .models import CasillaCatalogue

CORPUS_ROOT = PROJECT_ROOT / "corpus" / "casillas"


def _modelo_period_for(path: Path) -> tuple[str, str]:
    rel = path.relative_to(CORPUS_ROOT)
    modelo = f"MODELO_{rel.parts[0].removeprefix('modelo_')}"
    period = path.stem
    return modelo, period


@pytest.fixture(scope="session")
def corpus_files() -> tuple[Path, ...]:
    """Every committed casilla-catalogue JSON path, sorted."""
    return tuple(sorted(CORPUS_ROOT.rglob("*.json")))


@pytest.fixture(scope="session")
def corpus_catalogues(
    corpus_files: tuple[Path, ...],
) -> tuple[tuple[Path, str, str, CasillaCatalogue], ...]:
    """Pre-parsed (path, modelo, period, catalogue) for every corpus file."""
    rows: list[tuple[Path, str, str, CasillaCatalogue]] = []
    for path in corpus_files:
        modelo, period = _modelo_period_for(path)
        rows.append((path, modelo, period, load_casillas(modelo, period)))
    return tuple(rows)
