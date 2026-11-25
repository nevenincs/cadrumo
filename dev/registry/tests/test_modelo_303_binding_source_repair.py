"""The fixed-tier recargo binding starts where the design pins its tier."""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_DIR = Path(__file__).resolve().parents[3] / "src/cadrumo/_data/registry/aeat/modelos/303"
_SUPER = "modelo-303-recargo-equivalencia-super-reducido-cuota"
# The support-floor design leaves the recargo tier a free field; the next one enumerates its tiers.
_FREE_RATE_REVISION, _FIXED_TIER_REVISION = authored_revisions("303")[:2]
_FREE_RATE_ID, _FIXED_TIER_ID = str(_FREE_RATE_REVISION.id), str(_FIXED_TIER_REVISION.id)


@cache
def _modelo():
    return load_modelo_directory(_MODELO_DIR)


def test_fixed_tier_recargo_binding_cites_its_2023_design() -> None:
    """The 2023 design supplies the fixed 0.5 percent rung's bound source."""
    revision = _modelo().revisions[_FIXED_TIER_ID]
    binding = next(binding for binding in revision.bindings if str(binding.id) == _SUPER)

    assert binding.provider.fact == "recargo_amount_sum"
    assert binding.source_refs[0] == f"aeat-dr-303-{_FIXED_TIER_REVISION.valid_from.year}"


def test_free_2022_rate_does_not_enroll_an_unused_fixed_tier_binding() -> None:
    """2022 binds the legal population's cuota without asserting the free wire rate."""
    revision = _modelo().revisions[_FREE_RATE_ID]
    binding = next(binding for binding in revision.bindings if str(binding.id) == _SUPER)
    assert binding.provider.categories == ("domestic_super_reduced",)
    assert not binding.provider.applied_rates
    assert binding.provider.fact == "recargo_amount_sum"
    assert "ley-37-1992:art-161" in binding.legal_refs
    construct = next(item for item in revision.constructs if str(item.id) == "modelo-303-iva-autoliquidacion")
    assert tuple(str(item) for item in construct.bindings).count(_SUPER) == 1


_TRANSITIONAL = "modelo-303-recargo-equivalencia-reducido-transitorio-cuota"
_SUPER_FIGURE = "recargo.super-reducido"
_TRANSITIONAL_FIGURE = "recargo.reducido.transitorio"
_AUTHORED = authored_revisions("303")
# Editions in authored order: the free-rate one, the one that pins [17]'s tiers and the edition that
# inherits it, the edition that moves the 4 % recargo to [170], and every later edition.
_PINNED_IDS = tuple(str(revision.id) for revision in _AUTHORED[1:3])
_RELOCATED_ID = str(_AUTHORED[3].id)
_LATER_IDS = tuple(str(revision.id) for revision in _AUTHORED[4:])


def _casilla(revision_id: str, number: str):
    revision = _modelo().revisions[revision_id]
    return revision, next(casilla for casilla in revision.casillas if casilla.number == number)


def _formula_leaves(revision_id: str, formula_id: str) -> tuple[str, ...]:
    """Return the casilla ids a formula reads, whatever its nesting."""
    revision = _modelo().revisions[revision_id]
    formula = next(item for item in revision.formulas if str(item.id) == formula_id)

    def leaves(node: object) -> tuple[str, ...]:
        if isinstance(node, dict):
            own = (str(node["casilla_id"]),) if node.get("casilla_id") else ()
            return own + tuple(leaf for child in node.get("args") or () for leaf in leaves(child))
        return ()

    return leaves(formula.expression.model_dump(mode="json"))


def _figure_binding(revision_id: str, figure_id: str) -> str:
    _, figure = _casilla(revision_id, figure_id)
    assert str(figure.input_kind) == "bound"
    return str(figure.binding)


def test_free_rate_edition_binds_casilla_18_to_the_super_reducido_cuota() -> None:
    """The 2022 design leaves Tipo % [17] a free field, so [18] reads the 4 % population directly."""
    _, casilla = _casilla(_FREE_RATE_ID, "18")

    assert str(casilla.binding) == _SUPER
    assert str(casilla.input_kind) == "bound"


@pytest.mark.parametrize("revision_id", _PINNED_IDS)
def test_pinned_tier_editions_project_casilla_18_from_both_recargo_figures(revision_id: str) -> None:
    """[18] sums the 4 % and the transitional reducido recargo and carries no binding itself."""
    _, casilla = _casilla(revision_id, "18")

    assert casilla.binding is None
    assert str(casilla.input_kind) == "computed"
    assert sorted(_formula_leaves(revision_id, str(casilla.formula))) == sorted((_SUPER_FIGURE, _TRANSITIONAL_FIGURE))
    assert _figure_binding(revision_id, _SUPER_FIGURE) == _SUPER
    assert _figure_binding(revision_id, _TRANSITIONAL_FIGURE) == _TRANSITIONAL


def test_relocated_edition_keeps_only_the_transitional_recargo_in_casilla_18() -> None:
    """The 4 % recargo moves to [170]; [18] projects the transitional figure alone."""
    revision, casilla = _casilla(_RELOCATED_ID, "18")
    _, relocated = _casilla(_RELOCATED_ID, "170")

    assert casilla.binding is None
    assert str(casilla.input_kind) == "computed"
    assert _formula_leaves(_RELOCATED_ID, str(casilla.formula)) == (_TRANSITIONAL_FIGURE,)
    assert _figure_binding(_RELOCATED_ID, _TRANSITIONAL_FIGURE) == _TRANSITIONAL
    assert str(relocated.binding) == _SUPER
    assert _SUPER_FIGURE not in {str(item.number) for item in revision.casillas}


@pytest.mark.parametrize("revision_id", _LATER_IDS)
def test_later_editions_leave_casilla_18_unbound_and_unfed(revision_id: str) -> None:
    """Where the design fixes [17] at zero, [18] has neither a binding nor a formula."""
    revision, casilla = _casilla(revision_id, "18")

    assert casilla.binding is None
    assert casilla.formula is None
    assert str(casilla.input_kind) != "bound"
    assert not any(str(binding.id) == _TRANSITIONAL for binding in revision.bindings)


def test_2023_construct_keeps_the_three_recargo_cuotas_without_retired_sources() -> None:
    """Inherited binding registration must not reintroduce retired 59/60 slots."""
    revision = _modelo().revisions[_FIXED_TIER_ID]
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
