"""Tests for shared binding selector projection helpers."""

from __future__ import annotations

from typing import Any, NamedTuple

import pytest
from pydantic import BaseModel

from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from ..binding_provider_registration import provider_model_for
from ..binding_selector_utils import BindingRowSetSelector, binding_row_set_selector, selector_as_dict
from ..binding_temporal import (
    FiledCurrentPeriod,
    FilingYearOffset,
    PriorQuarterExpandingSpan,
    SameFilingYearPeriods,
    SameTargetContext,
    TargetPeriodOffset,
)
from ..errors import RegistryValidationError
from ..schema import BindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _binding(
    provider_fields: dict[str, Any],
    *,
    source: BindingSourceKind = BindingSourceKind.WITHHOLDING,
    aggregation: BindingAggregation | None = None,
    value: dict[str, Any] | None = None,
) -> BindingDefinition:
    """Build one binding from its provider fields and an explicit value contract."""
    return BindingDefinition.model_validate(
        {
            "id": "binding-under-test",
            "provider": {"kind": source, **provider_fields},
            "value": value or {"data_type": "text", "channel": "row_set", "row_grouping": "withholding"},
            "aggregation": aggregation,
            "legal_refs": ("ley-37-1992:art-1",),
            "source_refs": ("aeat-dr-190",),
        },
    )


def test_binding_row_set_selector_returns_none_for_an_eligible_binding_with_no_claim() -> None:
    """A row-set-eligible binding that declares none of the row-set keys is ``None``, not refused."""
    binding = _binding(
        {"fact": "perceptor_count"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    assert binding_row_set_selector(binding) is None


def test_binding_row_set_selector_accepts_row_field_projection() -> None:
    binding = _binding(
        {
            "fact": "row_field",
            "row_field": "perceptor_tax_id",
            "grouping": "per_perceptor",
            "record": "perceptor",
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    selector = binding_row_set_selector(binding)

    assert isinstance(selector, BindingRowSetSelector)
    assert selector.fact == "row_field"
    assert selector.row_field == "perceptor_tax_id"
    assert selector.grouping == "per_perceptor"
    assert selector.record == "perceptor"


def test_binding_row_set_selector_rejects_a_non_row_set_eligible_binding() -> None:
    """A binding whose aggregation op is not ``rows`` is refused by name.

    This binding declares export-shaped keys (``field``/``offset``/``length``/
    ``data_type``), not a row-set claim -- exactly the shape that used to be
    silently accepted as "no row-set projection" before the precondition moved
    into the callee. It is now refused for the real reason (not row-set
    eligible) rather than answering a question it was never asked.
    """
    binding = _binding(
        {
            "record": "operador",
            "field": "base_imponible",
            "offset": 42,
            "length": 12,
            "data_type": "money",
        },
        source=BindingSourceKind.MANUAL_INPUT,
        value={"data_type": "money", "channel": "decimal"},
    )

    with pytest.raises(RegistryValidationError, match="is not row-set-eligible"):
        binding_row_set_selector(binding)


def test_binding_row_set_selector_rejects_row_fact_without_grouping() -> None:
    binding = _binding(
        {"fact": "row_field", "row_field": "perceptor_tax_id"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    with pytest.raises(RegistryValidationError, match="missing grouping"):
        binding_row_set_selector(binding)


def test_binding_row_set_selector_rejects_grouping_with_non_row_fact() -> None:
    binding = _binding(
        {"fact": "perceptor_count", "grouping": "per_perceptor", "row_field": "perceptor_tax_id"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    with pytest.raises(RegistryValidationError, match="non-row fact"):
        binding_row_set_selector(binding)


def test_binding_row_set_selector_rejects_non_row_fact_with_row_keys() -> None:
    binding = _binding(
        {"fact": "perceptor_count", "grouping": "per_perceptor"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    with pytest.raises(RegistryValidationError, match="non-row fact"):
        binding_row_set_selector(binding)


_SCALAR_VALUE: dict[str, Any] = {"data_type": "money", "channel": "decimal"}
_ROW_VALUE: dict[str, Any] = {"data_type": "money", "channel": "row_set"}


class _TemporalCase(NamedTuple):
    """One temporal union member on a provider whose own invariants admit it."""

    source: BindingSourceKind
    fields: dict[str, Any]
    temporal: BaseModel
    value: dict[str, Any]
    op: BindingAggregationOp


_PREVIOUS_FILING_FIELDS: dict[str, Any] = {"source_modelo": "303", "source_casilla_id": "110"}
_M303_FIELDS: dict[str, Any] = {
    "source_modelo": "303",
    "source_casilla_ids": ("51", "53", "52", "54", "55", "56", "57", "58"),
    "summary_casilla_id": "80",
}
_INVENTORY_FIELDS: dict[str, Any] = {
    "modelo": "100",
    "projection_grain": "taxpayer_year_activity",
    "fact": "row_field",
    "record": "inventory_activity",
    "grouping": "per_inventory_activity",
    "row_field": "closing_minus_opening_positive",
    "target_casilla_id": "0177",
}


def _temporal_cases() -> tuple[_TemporalCase, ...]:
    """Return every temporal union member on a provider whose invariants admit it.

    Each member is built with as few fields as its own model requires, so the
    two members that require none -- ``same_target_context`` and
    ``prior_quarter_expanding_span`` -- are exercised exactly as a fully
    defaulted nested union member, which is the case the projection used to
    lose.
    """

    def previous_filing(temporal: BaseModel) -> _TemporalCase:
        return _TemporalCase(
            BindingSourceKind.PREVIOUS_FILING,
            _PREVIOUS_FILING_FIELDS,
            temporal,
            _SCALAR_VALUE,
            BindingAggregationOp.COPY,
        )

    return (
        _TemporalCase(
            BindingSourceKind.INVENTORY,
            _INVENTORY_FIELDS,
            SameTargetContext(),
            _ROW_VALUE,
            BindingAggregationOp.ROWS,
        ),
        _TemporalCase(
            BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY,
            _M303_FIELDS,
            FiledCurrentPeriod(source_period="4T"),
            _SCALAR_VALUE,
            BindingAggregationOp.SUM,
        ),
        previous_filing(SameFilingYearPeriods(source_periods=("0A",))),
        previous_filing(FilingYearOffset(years=-1, source_periods=("0A",))),
        previous_filing(TargetPeriodOffset(periods=-1)),
        previous_filing(PriorQuarterExpandingSpan()),
    )


@pytest.mark.parametrize("case", _temporal_cases(), ids=lambda case: type(case.temporal).__name__)
def test_selector_projection_round_trips_every_temporal_member(case: _TemporalCase) -> None:
    """A nested temporal member survives the selector projection, including a fully defaulted one.

    A member built entirely from defaults sets no field, so an unset-excluding
    dump used to drop its discriminator too and the mapping no longer named
    which member it was. Re-validation then failed on the union tag rather than
    on anything authored.
    """
    binding = _binding(
        {**case.fields, "temporal": case.temporal},
        source=case.source,
        value=case.value,
        aggregation=BindingAggregation(op=case.op),
    )

    projected = selector_as_dict(binding)

    assert provider_model_for(case.source).model_validate(projected).temporal == case.temporal
