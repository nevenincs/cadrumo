"""Tests for the central legal calculation registry."""

from __future__ import annotations

import pytest

from ...core.errors import RulesetValidationError
from ..formulas import FiscalPeriod, Quarter
from ..formulas._rulesets.modelo_115_2025 import RULESET as MODELO_115_2025
from ..modelos import MODELO_REGISTRY, ModeloCode
from ._registry import CalculationRegistry, get_calculation_registry

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_default_registry_scopes_every_formula_id_to_owning_ruleset() -> None:
    registry = get_calculation_registry()

    for ruleset in registry.rulesets:
        prefix = f"{ruleset.ruleset_id}."
        assert all(formula.formula_id.startswith(prefix) for formula in ruleset.formulas)


def test_default_registry_requires_legal_basis_for_every_ruleset() -> None:
    registry = get_calculation_registry()

    assert registry.rulesets
    assert all(ruleset.legal_citations for ruleset in registry.rulesets)


def test_registry_rejects_shadow_formula_ids() -> None:
    bad_ruleset = MODELO_115_2025.model_copy(
        update={
            "ruleset_id": "modelo_115.2026",
            "formulas": tuple(
                f.model_copy(update={"formula_id": f.formula_id.replace(".2025.", ".2024.")})
                for f in MODELO_115_2025.formulas
            ),
        }
    )

    with pytest.raises(RulesetValidationError, match="outside owning ruleset scope"):
        CalculationRegistry(rulesets=(bad_ruleset,), modelos=MODELO_REGISTRY)


def test_registry_targets_follow_modelo_cadence() -> None:
    registry = get_calculation_registry()

    targets = registry.catalogue_targets(modelo=ModeloCode.MODELO_115, year=2026)

    assert [target.period for target in targets] == ["2026Q1", "2026Q2", "2026Q3", "2026Q4"]


def test_registry_resolves_ruleset_for_target_period() -> None:
    registry = get_calculation_registry()

    ruleset = registry.resolve_ruleset(
        modelo=ModeloCode.MODELO_123,
        period=FiscalPeriod(year=2024, quarter=Quarter.Q1),
    )

    assert ruleset.ruleset_id == "modelo_123.2024"
    assert all(formula.formula_id.startswith("modelo_123.2024.") for formula in ruleset.formulas)
