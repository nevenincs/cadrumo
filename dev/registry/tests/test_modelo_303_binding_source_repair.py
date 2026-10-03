"""The 2022/2023 three-rung recargo has one grounded source binding."""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_DIR = Path(__file__).resolve().parents[3] / "src/cadrumo/_data/registry/aeat/modelos/303"
_SUPER = "modelo-303-recargo-equivalencia-super-reducido-cuota"


@cache
def _modelo():
    return load_modelo_directory(_MODELO_DIR)


@pytest.mark.parametrize("revision_id", ("2022", "2023"))
def test_three_rung_recargo_cuota_uses_the_source_pinned_casilla_18(revision_id: str) -> None:
    """Both printed three-rung designs put the 0.5 % cuota in casilla 18."""
    revision = _modelo().revisions[revision_id]
    casilla = next(casilla for casilla in revision.casillas if casilla.number == "18")
    binding = next(binding for binding in revision.bindings if str(binding.id) == _SUPER)

    assert str(casilla.binding) == _SUPER
    assert binding.provider.fact == "recargo_amount_sum"
    assert binding.source_refs[0] == f"aeat-dr-303-{revision_id}"


def test_2023_construct_keeps_the_three_recargo_cuotas_without_retired_sources() -> None:
    """Inherited binding registration must not reintroduce retired 59/60 slots."""
    revision = _modelo().revisions["2023"]
    construct = next(item for item in revision.constructs if str(item.id) == "modelo-303-iva-autoliquidacion")
    members = tuple(str(binding_id) for binding_id in construct.bindings)

    assert members.count(_SUPER) == 1
    assert members.index("modelo-303-recargo-equivalencia-general-cuota") + 1 == members.index(
        "modelo-303-recargo-equivalencia-reducido-cuota"
    )
    assert members.index("modelo-303-recargo-equivalencia-reducido-cuota") + 1 == members.index(_SUPER)
    assert "modelo-303-iva-repercutido-general-base" in members
    assert "modelo-303-casilla-59-entregas-intracomunitarias-base" not in members
    assert "modelo-303-casilla-60-exportaciones-base" not in members
