"""The prior-value rules a carry declares, through the real binding schema and previous-filing resolver.

``before_activity_unresolved`` keeps an earlier period that ended before the
activity began unresolved instead of zero; ``zero_needs_attestation`` is checked
for its placement here and for its effect in the clean-state evaluation. Both are
refused on any binding that is not a decimal carry read from an earlier filing.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period
from ..binding_temporal import FilingYearOffset
from ..binding_value_contract import BindingDataType, BindingValueChannel, BindingValueContract
from ..bindings import CasillaObservation, RegistryModeloObservation
from ..bindings_previous_filing import PreviousFilingProvider, resolve_previous_filing_binding_values
from ..schema import BindingDefinition, ModeloRevision
from ..schema_references import PeriodSelector
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_YEARS = filing_year_envelope().years
_LEGAL_ID = "ley-27-2014:art-29"
_SOURCE_ID = "aeat-modelo-200-manual-2023"
_TURNOVER: CasillaId = validated_casilla_id("DP200007:00255", surface="_TURNOVER")
_BINDING_ID = "modelo-200-test-preceding-turnover"
_MONEY = BindingValueContract(data_type=BindingDataType.MONEY, channel=BindingValueChannel.DECIMAL)


def _carry(**rules: bool) -> BindingDefinition:
    return BindingDefinition.model_validate(
        {
            "id": _BINDING_ID,
            "provider": PreviousFilingProvider(
                source_modelo="200",
                source_casilla_ids=(_TURNOVER,),
                temporal=FilingYearOffset(years=-1, source_periods=("0A",)),
            ),
            "value": _MONEY,
            "aggregation": BindingAggregation(op=BindingAggregationOp.COPY),
            "legal_refs": (_LEGAL_ID,),
            "source_refs": (_SOURCE_ID,),
            **rules,
        }
    )


def _revision(year: int, binding: BindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="test-prior-value-rules-revision",
        localization_key="test.schema.revision.test-prior-value-rules.label",
        valid_from=date(year, 1, 1),
        period_selector=PeriodSelector(years=(year,), periods=("0A",)),
        legal_refs=(_LEGAL_ID,),
        source_refs=(_SOURCE_ID,),
        bindings=(binding,),
    )


def _filed(year: int, value: Decimal) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="200",
        filing_year=year,
        period="0A",
        observations=(
            CasillaObservation(casilla_id=_TURNOVER, value=value, legal_refs=(_LEGAL_ID,), source_refs=(_SOURCE_ID,)),
        ),
    )


def _after_prior_period(year: int) -> date:
    return Period.from_year_and_code(year - 1, "0A").end_date + timedelta(days=1)


def test_both_rules_are_admitted_on_a_decimal_carry_read_from_an_earlier_filing() -> None:
    binding = _carry(zero_needs_attestation=True, before_activity_unresolved=True)

    assert binding.zero_needs_attestation is True
    assert binding.before_activity_unresolved is True
    assert "zero_needs_attestation" in binding.model_dump()


def test_an_undeclared_rule_is_left_out_of_the_dump() -> None:
    dumped = _carry().model_dump()

    assert "zero_needs_attestation" not in dumped
    assert "before_activity_unresolved" not in dumped


@pytest.mark.parametrize("rule", ["zero_needs_attestation", "before_activity_unresolved"])
def test_a_rule_declared_false_is_refused(rule: str) -> None:
    with pytest.raises(ValidationError):
        _carry(**{rule: False})


@pytest.mark.parametrize("rule", ["zero_needs_attestation", "before_activity_unresolved"])
def test_a_rule_on_a_profile_binding_is_refused(rule: str) -> None:
    with pytest.raises(ValidationError, match="needs a decimal binding read from an earlier filing"):
        BindingDefinition.model_validate(
            {
                "id": _BINDING_ID,
                "provider": {"kind": "profile", "profile_model": "taxpayer", "field": "incn_prior_12_months"},
                "value": _MONEY,
                "aggregation": BindingAggregation(op=BindingAggregationOp.COPY),
                "legal_refs": (_LEGAL_ID,),
                "source_refs": (_SOURCE_ID,),
                rule: True,
            }
        )


def test_an_unknown_rule_is_refused() -> None:
    with pytest.raises(ValidationError):
        _carry(zero_needs_attestatio=True)


@pytest.mark.parametrize("year", _YEARS)
def test_the_held_preceding_return_supplies_the_carry(year: int) -> None:
    revision = _revision(year, _carry(zero_needs_attestation=True, before_activity_unresolved=True))

    resolved = resolve_previous_filing_binding_values(
        revision, (_filed(year - 1, Decimal("812345.67")),), filing_year=year, period="0A"
    )

    assert resolved == {_BINDING_ID: Decimal("812345.67")}


@pytest.mark.parametrize("year", _YEARS)
def test_a_return_held_at_another_coordinate_is_not_read(year: int) -> None:
    revision = _revision(year, _carry(zero_needs_attestation=True, before_activity_unresolved=True))

    resolved = resolve_previous_filing_binding_values(
        revision, (_filed(year - 2, Decimal("812345.67")), _filed(year, Decimal("1"))), filing_year=year, period="0A"
    )

    assert resolved == {}


@pytest.mark.parametrize("year", _YEARS)
def test_a_period_before_the_activity_leaves_the_declared_carry_unresolved(year: int) -> None:
    revision = _revision(year, _carry(before_activity_unresolved=True))

    resolved = resolve_previous_filing_binding_values(
        revision, (), filing_year=year, period="0A", activity_start_date=_after_prior_period(year)
    )

    assert resolved == {}


@pytest.mark.parametrize("year", _YEARS)
def test_a_period_before_the_activity_still_zeroes_an_undeclared_carry(year: int) -> None:
    revision = _revision(year, _carry())

    resolved = resolve_previous_filing_binding_values(
        revision, (), filing_year=year, period="0A", activity_start_date=_after_prior_period(year)
    )

    assert resolved == {_BINDING_ID: Decimal("0")}
