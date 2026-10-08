"""The fixed-tier recargo binding starts where the design pins its tier."""

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


def test_fixed_tier_recargo_binding_cites_its_2023_design() -> None:
    """The 2023 design supplies the fixed 0.5 percent rung's bound source."""
    revision = _modelo().revisions["2023"]
    binding = next(binding for binding in revision.bindings if str(binding.id) == _SUPER)

    assert binding.provider.fact == "recargo_amount_sum"
    assert binding.source_refs[0] == "aeat-dr-303-2023"


def test_free_2022_rate_does_not_enroll_an_unused_fixed_tier_binding() -> None:
    """2022 binds the legal population's cuota without asserting the free wire rate."""
    revision = _modelo().revisions["2022"]
    binding = next(binding for binding in revision.bindings if str(binding.id) == _SUPER)
    assert binding.provider.categories == ("domestic_super_reduced",)
    assert not binding.provider.applied_rates
    assert binding.provider.fact == "recargo_amount_sum"
    assert "ley-37-1992:art-161" in binding.legal_refs
    construct = next(item for item in revision.constructs if str(item.id) == "modelo-303-iva-autoliquidacion")
    assert tuple(str(item) for item in construct.bindings).count(_SUPER) == 1


@pytest.mark.parametrize(("revision_id", "bound"), (("2022", True), ("2023", True)))
def test_casilla_18_carries_the_binding_only_where_its_design_pins_the_tier(revision_id: str, bound: bool) -> None:
    """The 2022 design leaves Tipo % [17] a free field; 2023 enumerates its tiers."""
    revision = _modelo().revisions[revision_id]
    casilla = next(casilla for casilla in revision.casillas if casilla.number == "18")

    assert (str(casilla.binding) == _SUPER) is bound
    assert (str(casilla.input_kind) == "bound") is bound


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
