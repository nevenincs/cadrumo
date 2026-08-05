"""Regression gates for formula-to-casilla wiring across the registry."""

from __future__ import annotations

import pytest

from .. import RegistryValidationError
from .._schema_input_kind import InputKind
from ._modelo_100_registry_support import _loaded_registry, _registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_every_formula_target_is_declared_as_the_matching_computed_casilla() -> None:
    """Formula evaluation and casilla input classification share one contract."""
    modelos_by_id, _catalogues = _loaded_registry()

    _registry_validator().validate_registry(modelos_by_id.values())

    for modelo in modelos_by_id.values():
        for revision in modelo.revisions.values():
            casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
            for formula in revision.formulas:
                casilla = casillas_by_id[formula.target_casilla_id]
                assert casilla.input_kind is InputKind.COMPUTED, (
                    f"{modelo.id}/{revision.id}/{formula.id}: "
                    f"target {formula.target_casilla_id} is {casilla.input_kind.value}"
                )
                assert casilla.formula == formula.id, (
                    f"{modelo.id}/{revision.id}/{formula.id}: "
                    f"target {formula.target_casilla_id} declares {casilla.formula!r}"
                )


def test_registry_validator_rejects_a_manual_formula_target() -> None:
    """The load-boundary validator prevents the old M100 drift from returning."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    target = next(formula.target_casilla_id for formula in revision.formulas)
    broken_casillas = tuple(
        casilla.model_copy(update={"input_kind": InputKind.MANUAL}) if casilla.id == target else casilla
        for casilla in revision.casillas
    )
    broken_revision = revision.model_copy(update={"casillas": broken_casillas})
    broken_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: broken_revision}})

    with pytest.raises(RegistryValidationError, match=r"formula .*targets casilla"):
        _registry_validator().validate_modelo(broken_modelo)


def test_registry_validator_rejects_a_formula_target_without_back_reference() -> None:
    """The formula target must also name the same formula in its casilla row."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    target = next(formula.target_casilla_id for formula in revision.formulas)
    broken_casillas = tuple(
        casilla.model_copy(update={"formula": None}) if casilla.id == target else casilla
        for casilla in revision.casillas
    )
    broken_revision = revision.model_copy(update={"casillas": broken_casillas})
    broken_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: broken_revision}})

    with pytest.raises(RegistryValidationError, match=r"whose declared formula is None"):
        _registry_validator().validate_modelo(broken_modelo)
