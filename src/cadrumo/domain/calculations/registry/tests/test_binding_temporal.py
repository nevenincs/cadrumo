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
    temporal_selector_from_previous_modelo_fields,
)
from ..errors import RegistryValidationError

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


def test_legacy_defaults_map_to_the_same_target_context() -> None:
    assert temporal_selector_from_previous_modelo_fields() == SameTargetContext()


def test_legacy_singular_period_maps_to_same_filing_year_periods() -> None:
    assert temporal_selector_from_previous_modelo_fields(period="0A") == SameFilingYearPeriods(source_periods=("0A",))


def test_legacy_year_delta_maps_to_the_filing_year_offset() -> None:
    mapped = temporal_selector_from_previous_modelo_fields(
        filing_year_delta=-1,
        max_year_delta=4,
        source_periods=("0A",),
    )

    assert mapped == FilingYearOffset(years=-1, source_periods=("0A",), max_years=4)


def test_legacy_period_offset_maps_to_the_target_period_offset() -> None:
    assert temporal_selector_from_previous_modelo_fields(
        source_period_offset_from_target=-1,
    ) == TargetPeriodOffset(periods=-1)


def test_legacy_expanding_span_maps_to_its_own_member() -> None:
    assert (
        temporal_selector_from_previous_modelo_fields(
            prior_quarter_expanding_span=True,
        )
        == PriorQuarterExpandingSpan()
    )


def test_legacy_mapping_refuses_both_period_axes() -> None:
    with pytest.raises(RegistryValidationError, match="period or source_periods, not both"):
        temporal_selector_from_previous_modelo_fields(period="0A", source_periods=("1T",))


def test_legacy_mapping_refuses_an_expanding_span_beside_a_period_axis() -> None:
    with pytest.raises(RegistryValidationError, match="mutually exclusive"):
        temporal_selector_from_previous_modelo_fields(prior_quarter_expanding_span=True, source_periods=("1T",))


def test_legacy_mapping_refuses_an_expanding_span_carrying_a_year_offset() -> None:
    with pytest.raises(RegistryValidationError, match="cannot carry a filing-year offset"):
        temporal_selector_from_previous_modelo_fields(prior_quarter_expanding_span=True, filing_year_delta=-1)


def test_legacy_mapping_refuses_a_period_offset_beside_named_periods() -> None:
    with pytest.raises(RegistryValidationError, match="cannot declare period/source_periods together"):
        temporal_selector_from_previous_modelo_fields(source_period_offset_from_target=-1, source_periods=("1T",))


def test_legacy_mapping_refuses_a_period_offset_carrying_a_year_offset() -> None:
    with pytest.raises(RegistryValidationError, match="cannot carry a filing-year offset"):
        temporal_selector_from_previous_modelo_fields(source_period_offset_from_target=-1, filing_year_delta=-1)


def test_legacy_mapping_refuses_a_year_delta_without_a_period_axis() -> None:
    with pytest.raises(RegistryValidationError, match="requires period or source_periods"):
        temporal_selector_from_previous_modelo_fields(filing_year_delta=-1)


def test_legacy_mapping_refuses_a_max_year_delta_without_a_year_offset() -> None:
    with pytest.raises(RegistryValidationError, match="requires a non-zero filing_year_delta"):
        temporal_selector_from_previous_modelo_fields(max_year_delta=4, source_periods=("0A",))


def test_legacy_zero_period_offset_maps_to_the_same_target_context() -> None:
    """A zero offset names the target's own period, which is that member exactly.

    Modelo 353's per-grupo member fold authors it that way, so the mapping must
    keep the declaration rather than refusing an offset the union cannot spell.
    """
    assert temporal_selector_from_previous_modelo_fields(source_period_offset_from_target=0) == SameTargetContext()


def test_legacy_filing_year_bound_period_offset_stays_inside_the_filing_year() -> None:
    """Modelos 130 and 131 bound a one-period-back offset to the filing year.

    ``max_year_delta = 0`` is that bound. Dropping it would let a 1T target reach
    into the prior year and carry a foreign year's quota forward, so it is
    preserved as ``within_filing_year`` rather than discarded as a no-op.
    """
    member = temporal_selector_from_previous_modelo_fields(
        source_period_offset_from_target=-1,
        max_year_delta=0,
    )

    assert member == TargetPeriodOffset(periods=-1, within_filing_year=True)


def test_legacy_filing_year_bound_expanding_span_maps_to_the_plain_span() -> None:
    """The expanding span never crosses the year, so bounding it to the year filters nothing."""
    assert (
        temporal_selector_from_previous_modelo_fields(prior_quarter_expanding_span=True, max_year_delta=0)
        == PriorQuarterExpandingSpan()
    )


def test_legacy_mapping_still_refuses_a_positive_bound_on_an_offset_or_span() -> None:
    """A multi-year reach is unrepresentable for both relative-period members."""
    with pytest.raises(RegistryValidationError, match="cannot carry a filing-year offset"):
        temporal_selector_from_previous_modelo_fields(source_period_offset_from_target=-1, max_year_delta=1)
    with pytest.raises(RegistryValidationError, match="cannot carry a filing-year offset"):
        temporal_selector_from_previous_modelo_fields(prior_quarter_expanding_span=True, max_year_delta=2)
