"""A ledger renta binding may only target a box its own edition gives that binding family."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import (
    ledger_renta_gastos_estimacion_directa_target_failures,
    renta_first_slice_binding_target_casillas,
)
from cadrumo.domain.calculations.registry.ledger_renta_gastos_pago_fraccionado_bindings import (
    ledger_renta_gastos_pago_fraccionado_target_failures,
)
from cadrumo.domain.calculations.registry.ledger_renta_income_bindings import (
    LedgerRentaIncomeProvider,
    ledger_renta_income_target_failures,
    renta_income_target_casilla,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEARS = (2022, 2023, 2024, 2025, 2026)
_COORDINATES = tuple(("100", year, "0A") for year in _YEARS) + tuple(
    (modelo, year, "1T") for modelo in ("130", "131") for year in _YEARS
)
_RULES: tuple[Callable[[ModeloRevision], list[str]], ...] = (
    ledger_renta_income_target_failures,
    ledger_renta_gastos_estimacion_directa_target_failures,
    ledger_renta_gastos_pago_fraccionado_target_failures,
)


@cache
def _revision(modelo: str, year: int, period: str) -> ModeloRevision:
    with bundled_indexed_authority().operation() as operation:
        return operation.revision_for_context(modelo, filing_year=year, period=period)


def _retargeted(revision: ModeloRevision, binding_id: str, target: str) -> ModeloRevision:
    bindings = tuple(
        binding.model_copy(
            update={
                "provider": binding.provider.model_copy(
                    update={"target_casilla_id": validated_casilla_id(target, surface="test")}
                )
            }
        )
        if binding.id == binding_id
        else binding
        for binding in revision.bindings
    )
    return revision.model_copy(update={"bindings": bindings})


@pytest.mark.parametrize(("modelo", "year", "period"), _COORDINATES)
def test_every_published_edition_satisfies_the_rule(modelo: str, year: int, period: str) -> None:
    revision = _revision(modelo, year, period)
    assert [failure for rule in _RULES for failure in rule(revision)] == []


@pytest.mark.parametrize("year", _YEARS)
def test_the_published_targets_are_the_boxes_the_forms_print(year: int) -> None:
    """The box numbers the earlier fixed checks named, not read from the declaration."""
    modelo_100 = _revision("100", year, "0A")
    assert renta_income_target_casilla(modelo_100, modelo="100") == "0171"
    assert renta_income_target_casilla(_revision("130", year, "1T"), modelo="130") == "01"
    assert renta_income_target_casilla(_revision("131", year, "1T"), modelo="131") == "05"
    assert renta_first_slice_binding_target_casillas(modelo_100) >= {"0183", "0186", "0208", "0227"}


@pytest.mark.parametrize(
    "target",
    [
        pytest.param("0505", id="computed-box"),
        pytest.param("0172", id="manual-box"),
        pytest.param("0171", id="income-family-box"),
        pytest.param("0186", id="another-gastos-box"),
        pytest.param("9999", id="undeclared-box"),
    ],
)
def test_a_gastos_binding_aimed_at_a_box_not_bound_to_it_is_refused(target: str) -> None:
    revision = _retargeted(_revision("100", 2025, "0A"), "renta-ledger-expense-0183-deductible", target)
    assert any(target in failure for failure in ledger_renta_gastos_estimacion_directa_target_failures(revision))


def test_an_income_binding_aimed_at_a_modulos_computed_box_is_refused() -> None:
    revision = _revision("131", 2025, "1T")
    binding = next(item for item in revision.bindings if isinstance(item.provider, LedgerRentaIncomeProvider))
    defective = _retargeted(revision, binding.id, "01")
    assert any("'01'" in failure for failure in ledger_renta_income_target_failures(defective))


def test_the_modelo_130_retencion_binding_may_share_the_income_box() -> None:
    revision = _revision("130", 2025, "1T")
    shared = [
        binding.id
        for binding in revision.bindings
        if isinstance(binding.provider, LedgerRentaIncomeProvider) and binding.provider.target_casilla_id == "01"
    ]
    assert len(shared) == 2
    assert ledger_renta_income_target_failures(revision) == []
