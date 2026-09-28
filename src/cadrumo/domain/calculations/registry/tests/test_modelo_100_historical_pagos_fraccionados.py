"""Every authored Modelo 100 edition folds the M130/M131 pagos-fraccionados relations into 0604.

Each edition carries the same legal grounding on 0604 and the same annual
settlement shape, so all of them must use one relation-prefill mechanism
rather than leaving the credit as a manual gap. The editions come from the
published registry, so a new edition is covered without editing this module.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from .....core.aggregation import BindingAggregationOp, BindingSourceKind
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..binding_aggregation import binding_aggregation_op
from ..binding_value_contract import BindingValueChannel
from ..errors import FilingYearOutsideSupportEnvelopeError
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..relations import (
    RegistryFoldRequirement,
    relation_prefill_bindings_for_period,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from ..schema import ModeloRevision, RegistrySnapshot
from ._cross_dependency_calculation_support import _observations_from_requirements
from .published_authority import published_authored_revision, published_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _authored_years() -> tuple[int, ...]:
    """The ejercicio of every Modelo 100 edition the published generation stores."""
    with bundled_indexed_authority().operation() as operation:
        return tuple(
            sorted(
                operation.revision("100", str(metadata.id)).valid_from.year
                for metadata in operation.modelo_directory("100").revisions
            )
        )


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


def _neutral_binding_inputs(
    revision: ModeloRevision,
) -> tuple[dict[str, Decimal], dict[str, bool], dict[str, date], dict[str, str]]:
    """Neutral values for every scalar binding the edition declares.

    Relations arrive through their own channel; an individual Madrid filer with
    no other income, family or carry-forward is the neutral profile.
    """
    decimals: dict[str, Decimal] = {}
    booleans: dict[str, bool] = {}
    dates: dict[str, date] = {}
    enums: dict[str, str] = {}
    for binding in revision.bindings:
        if binding.source is BindingSourceKind.RELATION_PREFILL:
            continue
        channel = binding.value.channel
        if channel in {BindingValueChannel.DECIMAL, BindingValueChannel.INTEGER}:
            decimals[binding.id] = Decimal("0")
        elif channel is BindingValueChannel.BOOLEAN:
            booleans[binding.id] = False
        elif channel is BindingValueChannel.DATE:
            dates[binding.id] = date(1975, 6, 15)
        elif channel is BindingValueChannel.ENUM:
            enums[binding.id] = "madrid"
    if any(binding.id == "renta-profile-declaration-type" for binding in revision.bindings):
        decimals["renta-profile-declaration-type"] = Decimal("1")
    return decimals, booleans, dates, enums


def _relation_observed_value(requirement: RegistryFoldRequirement, period_index: int) -> Decimal:
    relation_id = requirement.target_bindings[0]
    if relation_id == "renta-modelo-130-pagos-fraccionados":
        return _M130_QUARTERS[period_index]
    if relation_id == "renta-modelo-131-pagos-fraccionados":
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

    assert relation_values["renta-modelo-130-pagos-fraccionados"] == _EXPECTED_M130_TOTAL
    assert relation_values["renta-modelo-131-pagos-fraccionados"] == _EXPECTED_M131_TOTAL

    decimals, booleans, dates, enums = _neutral_binding_inputs(snapshot.revision)
    return calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(year, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values=relation_values,
        date_binding_values=dates,
        boolean_binding_values=booleans,
    )


@pytest.mark.parametrize("year", _authored_years())
def test_historical_pagos_fraccionados_relation_contract_and_fold(
    registry_authority: PinnedAuthorityOperation,
    year: int,
) -> None:
    """Each authored edition declares the M130/M131 relation contract and folds it into 0604.

    Years below the published filing floor keep their authored contract but
    refuse filing selection, so only in-envelope years run the fold.
    """
    supported_years = published_supported_filing_years()
    assert supported_years is not None
    if year < supported_years.floor:
        revision = published_authored_revision("100", year=year)
        _assert_relation_contract(revision, year=year)
        with pytest.raises(FilingYearOutsideSupportEnvelopeError):
            registry_authority.snapshot("100", filing_year=year, period="0A")
        return

    snapshot = registry_authority.snapshot("100", filing_year=year, period="0A")
    _assert_relation_contract(snapshot.revision, year=year)

    result = _calculate_historical_m100(snapshot, year=year)
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    pagos_entry = entries[_M100_PAGOS_CASILLA]

    assert result.values[_M100_PAGOS_CASILLA] == _EXPECTED_0604
    assert pagos_entry.operand_refs == (
        "renta-modelo-130-pagos-fraccionados",
        "renta-modelo-131-pagos-fraccionados",
    )
    assert pagos_entry.operand_values == (_EXPECTED_M130_TOTAL, _EXPECTED_M131_TOTAL)
    assert {"rd-439-2007:art-109", "rd-439-2007:art-110"} <= set(pagos_entry.legal_refs)
    assert "orden-eha-672-2007:art-3" in pagos_entry.legal_refs
    assert {f"aeat-renta-{year}-manual-parte1", f"boe-modelo-100-{year}-form"} <= set(pagos_entry.source_refs)
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == _EXPECTED_0604


def _assert_relation_contract(revision: ModeloRevision, *, year: int) -> None:
    casilla = next(c for c in revision.casillas if c.id == _M100_PAGOS_CASILLA)
    assert casilla.input_kind == "computed"
    assert casilla.formula == "renta-pagos-fraccionados-ingresados"

    relation_bindings = {
        binding.id: (binding, provider)
        for binding, provider in relation_prefill_bindings_for_period(revision, period="0A")
    }
    constructs = {construct.id: construct for construct in revision.constructs}
    dependencies = {dep.id: dep for dep in revision.dependency_classifications}

    binding_130, provider_130 = relation_bindings["renta-modelo-130-pagos-fraccionados"]
    binding_131, provider_131 = relation_bindings["renta-modelo-131-pagos-fraccionados"]
    assert provider_130.source_modelo == "130"
    assert provider_130.declared_source_casilla_ids == (_M130_SOURCE_CASILLA,)
    assert provider_131.source_modelo == "131"
    assert provider_131.declared_source_casilla_ids == (_M131_SOURCE_CASILLA,)
    assert provider_130.required_source_periods == ("1T", "2T", "3T", "4T")
    assert provider_131.required_source_periods == ("1T", "2T", "3T", "4T")
    assert binding_aggregation_op(binding_130) is BindingAggregationOp.SUM
    assert binding_aggregation_op(binding_131) is BindingAggregationOp.SUM

    assert any(
        "renta-pagos-fraccionados-ingresados" in construct.formulas
        and {binding_130.id, binding_131.id} <= set(construct.bindings)
        for construct in constructs.values()
    ), "no construct owns the pagos-fraccionados fold together with its relations"
    assert binding_130.id in dependencies["renta-dep-130"].binding_refs
    assert binding_131.id in dependencies["renta-dep-131"].binding_refs
