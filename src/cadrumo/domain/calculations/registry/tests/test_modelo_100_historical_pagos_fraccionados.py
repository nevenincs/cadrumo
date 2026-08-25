"""M100 2020-2023 0604 consumes M130/M131 pagos-fraccionados relations.

The current 2024/2025 revisions already compute casilla 0604 from the
cross-modelo M130/M131 pagos-fraccionados relations. The 2020-2023 revisions
carry the same legal grounding on 0604 and the same annual settlement shape, so
they must use the same current relation-prefill mechanism rather than leaving
the credit as a manual gap.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .. import (
    RegistryCalculationResult,
    RegistrySnapshot,
    calculate_registry_snapshot,
)
from ..authority import ValidatedRegistryAuthority
from ..binding_selector_utils import selector_as_dict
from ..relations import (
    RegistryFoldRequirement,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from ._cross_dependency_calculation_support import _observations_from_requirements

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEARS = (2020, 2021, 2022, 2023)
_M100_PAGOS_CASILLA: CasillaId = validated_casilla_id("0604", surface="_M100_PAGOS_CASILLA")
_M100_TOTAL_PAGOS_A_CUENTA_CASILLA: CasillaId = validated_casilla_id(
    "0609",
    surface="_M100_TOTAL_PAGOS_A_CUENTA_CASILLA",
)
_M130_SOURCE_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_SOURCE_CASILLA")
_M131_SOURCE_CASILLA: CasillaId = validated_casilla_id("15", surface="_M131_SOURCE_CASILLA")

_M130_QUARTERS = (Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"))
_M131_QUARTERS = (Decimal("25"), Decimal("30"), Decimal("35"), Decimal("40"))
_EXPECTED_M130_TOTAL = sum(_M130_QUARTERS, Decimal("0"))
_EXPECTED_M131_TOTAL = sum(_M131_QUARTERS, Decimal("0"))
_EXPECTED_0604 = _EXPECTED_M130_TOTAL + _EXPECTED_M131_TOTAL


def _historical_m100_binding_values(year: int) -> dict[str, Decimal]:
    return {
        f"renta-{year}-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        f"renta-{year}-modelo-111-retenciones-periodicas": Decimal("0"),
        f"renta-{year}-modelo-123-retenciones-periodicas": Decimal("0"),
        f"renta-{year}-profile-minimo-descendientes-estatal": Decimal("0"),
        f"renta-{year}-profile-minimo-descendientes-autonomico": Decimal("0"),
    }


def _relation_observed_value(requirement: RegistryFoldRequirement, period_index: int) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id.endswith("-rel-130-pagos-fraccionados"):
        return _M130_QUARTERS[period_index]
    if relation_id.endswith("-rel-131-pagos-fraccionados"):
        return _M131_QUARTERS[period_index]
    return Decimal("0")


def _calculate_historical_m100(snapshot: RegistrySnapshot, *, year: int) -> RegistryCalculationResult:
    requirements = relation_source_requirements(snapshot.revision, filing_year=year, period="0A")
    observations = _observations_from_requirements(requirements, _relation_observed_value)
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=year,
        period="0A",
    )

    assert relation_values[f"renta-{year}-rel-130-pagos-fraccionados"] == _EXPECTED_M130_TOTAL
    assert relation_values[f"renta-{year}-rel-131-pagos-fraccionados"] == _EXPECTED_M131_TOTAL

    return calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(year, 12, 31)},
        binding_values=_historical_m100_binding_values(year),
        enum_binding_values={f"renta-{year}-profile-tax-residence-ccaa": "madrid"},
        relation_values=relation_values,
    )


@pytest.mark.parametrize("year", _YEARS)
def test_historical_pagos_fraccionados_relation_contract_and_fold(
    registry_authority: ValidatedRegistryAuthority,
    year: int,
) -> None:
    """2020-2023 declare the current M130/M131 relation contract and fold it into 0604."""
    snapshot = registry_authority.snapshot("100", filing_year=year, period="0A")

    casilla = next(c for c in snapshot.revision.casillas if c.id == _M100_PAGOS_CASILLA)
    assert casilla.input_kind == "computed"
    assert casilla.formula == f"renta-{year}-pagos-fraccionados-ingresados"

    relations = {relation.id: relation for relation in snapshot.revision.relations}
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    constructs = {construct.id: construct for construct in snapshot.revision.constructs}
    dependencies = {dep.id: dep for dep in snapshot.revision.dependency_classifications}

    rel130 = relations[f"renta-{year}-rel-130-pagos-fraccionados"]
    rel131 = relations[f"renta-{year}-rel-131-pagos-fraccionados"]
    assert rel130.source_modelo == "130"
    assert rel130.source_casilla_id == _M130_SOURCE_CASILLA
    assert rel130.target_binding == f"renta-{year}-modelo-130-pagos-fraccionados"
    assert rel131.source_modelo == "131"
    assert rel131.source_casilla_id == _M131_SOURCE_CASILLA
    assert rel131.target_binding == f"renta-{year}-modelo-131-pagos-fraccionados"
    assert rel130.source_periods == ("1T", "2T", "3T", "4T")
    assert rel131.source_periods == ("1T", "2T", "3T", "4T")
    assert rel130.aggregation is not None and rel130.aggregation.op == "sum"
    assert rel131.aggregation is not None and rel131.aggregation.op == "sum"

    assert selector_as_dict(bindings[rel130.target_binding]) == {
        "source_modelo": "130",
        "source_casilla_id": _M130_SOURCE_CASILLA,
    }
    assert selector_as_dict(bindings[rel131.target_binding]) == {
        "source_modelo": "131",
        "source_casilla_id": _M131_SOURCE_CASILLA,
    }

    construct = constructs[f"renta-{year}-dependent-modelos"]
    assert f"renta-{year}-pagos-fraccionados-ingresados" in construct.formulas
    assert rel130.id in construct.relations
    assert rel131.id in construct.relations
    assert dependencies[f"renta-{year}-dep-130"].relation_refs == (rel130.id,)
    assert dependencies[f"renta-{year}-dep-131"].relation_refs == (rel131.id,)

    result = _calculate_historical_m100(snapshot, year=year)
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    pagos_entry = entries[_M100_PAGOS_CASILLA]

    assert result.values[_M100_PAGOS_CASILLA] == _EXPECTED_0604
    assert pagos_entry.operand_refs == (
        f"renta-{year}-rel-130-pagos-fraccionados",
        f"renta-{year}-rel-131-pagos-fraccionados",
    )
    assert pagos_entry.operand_values == (_EXPECTED_M130_TOTAL, _EXPECTED_M131_TOTAL)
    assert {"ley-35-2006:art-99", "rd-439-2007:art-109", "rd-439-2007:art-110"} <= set(pagos_entry.legal_refs)
    assert {"orden-eha-672-2007:art-1", "orden-eha-672-2007:art-3"} <= set(pagos_entry.legal_refs)
    assert {f"aeat-renta-{year}-manual-parte1", f"boe-modelo-100-{year}-form"} <= set(pagos_entry.source_refs)
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == _EXPECTED_0604
