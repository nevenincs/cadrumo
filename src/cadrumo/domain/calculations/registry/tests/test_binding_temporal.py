"""Focused contracts for the binding temporal, applicability, and authorship unions."""

import pytest
from pydantic import TypeAdapter, ValidationError

from ..binding_temporal import (
    AllRevisionContexts,
    AuthoredBinding,
    BindingApplicability,
    BindingAuthorship,
    BindingTemporalSelector,
    FiledCurrentPeriod,
    FilingYearOffset,
    GeneratedBinding,
    NonCalculation,
    PriorQuarterExpandingSpan,
    SameFilingYearPeriods,
    SameTargetContext,
    TargetPeriodOffset,
    TargetPeriods,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TEMPORAL = TypeAdapter(BindingTemporalSelector)
_APPLICABILITY = TypeAdapter(BindingApplicability)
_AUTHORSHIP = TypeAdapter(BindingAuthorship)


def test_temporal_members_construct_with_their_declared_axes() -> None:
    offset = FilingYearOffset(years=-1, source_periods=("0A",), max_years=4)

    assert offset.years == -1
    assert offset.source_periods == ("0A",)
    assert offset.max_years == 4
    assert SameFilingYearPeriods(source_periods=("1T", "2T")).source_periods == ("1T", "2T")
    assert TargetPeriodOffset(periods=-1).periods == -1
    assert FiledCurrentPeriod(source_period="4T").source_period == "4T"


@pytest.mark.parametrize(
    "member",
    [
        SameTargetContext(),
        SameFilingYearPeriods(source_periods=("0A",)),
        FilingYearOffset(years=-1, source_periods=("0A",)),
        TargetPeriodOffset(periods=-1),
        PriorQuarterExpandingSpan(),
        FiledCurrentPeriod(source_period="4T"),
    ],
)
def test_temporal_union_round_trips_every_member_through_its_discriminator(
    member: SameTargetContext
    | SameFilingYearPeriods
    | FilingYearOffset
    | TargetPeriodOffset
    | PriorQuarterExpandingSpan
    | FiledCurrentPeriod,
) -> None:
    serialized = _TEMPORAL.dump_python(member, mode="json")

    assert _TEMPORAL.validate_python(serialized) == member


def test_applicability_and_authorship_unions_round_trip_every_member() -> None:
    members: list[object] = [
        AllRevisionContexts(),
        TargetPeriods(periods=("0A",)),
        NonCalculation(
            reason="informational_total",
            box_retired_in="2023",
            consumed_by="modelo-390 annual informational handoff",
        ),
    ]
    for member in members:
        assert _APPLICABILITY.validate_python(_APPLICABILITY.dump_python(member, mode="json")) == member

    authorship: list[object] = [
        AuthoredBinding(),
        GeneratedBinding(generator_id="m303-binding-generator", run_digest="sha256:abc"),
    ]
    for member in authorship:
        assert _AUTHORSHIP.validate_python(_AUTHORSHIP.dump_python(member, mode="json")) == member


def test_temporal_union_refuses_an_unknown_discriminator() -> None:
    with pytest.raises(ValidationError, match=r"union_tag_invalid|does not match any"):
        _TEMPORAL.validate_python({"kind": "absolute_year", "year": 2025})


def test_filing_year_offset_refuses_a_zero_year_offset() -> None:
    with pytest.raises(ValidationError, match="years must be non-zero"):
        FilingYearOffset(years=0, source_periods=("0A",))


def test_filing_year_offset_refuses_a_negative_max_years() -> None:
    with pytest.raises(ValidationError, match="max_years must be non-negative"):
        FilingYearOffset(years=-1, source_periods=("0A",), max_years=-1)


def test_filing_year_offset_refuses_an_empty_period_set() -> None:
    with pytest.raises(ValidationError):
        FilingYearOffset(years=-1, source_periods=())


def test_period_bearing_members_refuse_duplicate_periods() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        SameFilingYearPeriods(source_periods=("1T", "1T"))
    with pytest.raises(ValidationError, match="must be unique"):
        TargetPeriods(periods=("1T", "1T"))


def test_target_period_offset_refuses_a_zero_offset() -> None:
    with pytest.raises(ValidationError, match="periods must be non-zero"):
        TargetPeriodOffset(periods=0)


def test_generated_binding_refuses_a_blank_run_digest() -> None:
    with pytest.raises(ValidationError, match="run_digest must be non-blank"):
        GeneratedBinding(generator_id="m303-binding-generator", run_digest="   ")
