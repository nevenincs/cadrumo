"""Cross-reference casilla catalogue directories against the registry.

Enforces the direction called out in #108's acceptance brief: every
modelo the on-disk casilla catalogue knows about must resolve to a
:class:`aeat.models.ModeloMetadata` entry. The reverse direction
(every registry entry references only known casilla codes) lands in a
later iteration once :class:`ModeloMetadata` carries structured
casilla references.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ._registry import get_modelo

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CASILLAS_ROOT = _REPO_ROOT / "corpus" / "casillas"


def test_casillas_root_exists() -> None:
    """The on-disk casilla catalogue root is present."""
    assert _CASILLAS_ROOT.is_dir(), f"missing casilla corpus at {_CASILLAS_ROOT}"


def test_every_casilla_modelo_resolves_in_registry() -> None:
    """Every ``corpus/casillas/modelo_<code>/`` resolves via ``get_modelo``."""
    seen: list[str] = []
    for child in sorted(_CASILLAS_ROOT.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if not name.startswith("modelo_"):
            continue
        code = name.removeprefix("modelo_")
        seen.append(code)
        metadata = get_modelo(code)
        assert metadata.code.value == code
    assert seen, "expected at least one modelo_* directory under corpus/casillas"
