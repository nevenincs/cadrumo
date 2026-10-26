"""The target-period-conditional filing-year offset and its scope-out.

Modelo 202's modalidad 40.2 bases each pago fraccionado on the last período
impositivo whose declaration deadline has elapsed (LIS art. 40.2). Because the
source modelo 200's deadline falls in July, that is two filing years back for
the April instalment and one year back for the October and December ones. No
uniform offset states both, which is what
:class:`FilingYearOffsetByTargetPeriod` exists for.

The expected anchors are enumerated by hand per target period -- an INDEPENDENT
enumeration, never derived from the member under test -- per
``aeat-quality-gates``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..binding_temporal import (
    BindingTemporalKind,
    FilingYearOffsetByTargetPeriod,
    temporal_max_year_delta,
    temporal_period_anchors,
)
from ..errors import RegistryValidationError
from ..relation_prefill_bindings import RelationPrefillProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The authored modelo 202 modalidad 40.2 shape, spelled out once.
_M202_OFFSETS = {"1P": -2, "2P": -1, "3P": -1}


def _member(**overrides: object) -> FilingYearOffsetByTargetPeriod:
    payload: dict[str, object] = {"offsets": dict(_M202_OFFSETS), "source_periods": ("0A",)}
    payload.update(overrides)
    return FilingYearOffsetByTargetPeriod.model_validate(payload)


def test_kind_discriminator_is_the_declared_token() -> None:
    assert _member().kind is BindingTemporalKind.FILING_YEAR_OFFSET_BY_TARGET_PERIOD


@pytest.mark.parametrize(
    ("target_period", "expected"),
    [
        ("1P", ((-2, "0A"),)),
        ("2P", ((-1, "0A"),)),
        ("3P", ((-1, "0A"),)),
    ],
)
def test_each_target_period_anchors_at_its_own_declared_year(
    target_period: str,
    expected: tuple[tuple[int, str], ...],
) -> None:
    assert temporal_period_anchors(_member(), target_period=target_period) == expected


def test_a_target_period_the_offsets_do_not_name_scopes_out() -> None:
    """An unnamed target period yields NO anchor, never a neighbouring year.

    This is the whole point of the member: substituting an adjacent year when
    the declared one is absent would read a filing whose deadline had not
    elapsed, which is precisely the condition the law keys on.
    """
    assert temporal_period_anchors(_member(), target_period="4T") == ()
    assert temporal_period_anchors(_member(), target_period="0A") == ()


def test_the_member_is_unbounded_so_neither_declared_distance_is_filtered() -> None:
    assert temporal_max_year_delta(_member()) is None


def test_several_source_periods_fan_against_the_target_period_offset() -> None:
    member = _member(offsets={"0A": -1}, source_periods=("1T", "2T"))
    assert temporal_period_anchors(member, target_period="0A") == ((-1, "1T"), (-1, "2T"))


def test_empty_offsets_are_refused() -> None:
    with pytest.raises((RegistryValidationError, ValidationError)) as excinfo:
        _member(offsets={})
    assert "at least one target-period offset" in str(excinfo.value)


def test_a_zero_offset_is_refused_in_favour_of_the_same_year_member() -> None:
    with pytest.raises((RegistryValidationError, ValidationError)) as excinfo:
        _member(offsets={"1P": -2, "2P": 0})
    assert "must be non-zero" in str(excinfo.value)


def test_duplicate_source_periods_are_refused() -> None:
    with pytest.raises((RegistryValidationError, ValidationError)) as excinfo:
        _member(source_periods=("0A", "0A"))
    assert "must be unique" in str(excinfo.value)


def test_a_relation_prefill_provider_carries_the_member_and_derives_its_anchors() -> None:
    provider = RelationPrefillProvider.model_validate(
        {
            "kind": "relation_prefill",
            "relation_kind": "cross_model_output",
            "dependency_role": "direct_calculation",
            "source_modelo": "200",
            "source_casilla_id": "DP200014B:00592",
            "temporal": {
                "kind": "filing_year_offset_by_target_period",
                "offsets": dict(_M202_OFFSETS),
                "source_periods": ["0A"],
            },
        },
    )
    assert provider.required_period_anchors_for_target("1P") == ((-2, "0A"),)
    assert provider.required_period_anchors_for_target("2P") == ((-1, "0A"),)
    assert provider.required_period_anchors_for_target("1T") == ()
    assert provider.required_source_periods == ("0A",)


def test_an_absolute_source_year_is_unspellable_in_a_provider_temporal() -> None:
    """No member of the closed union carries a year, so the row cannot validate.

    The refusal is structural rather than a validator: a declaration states
    timeless intent and the concrete coordinate is derived at resolve time, so
    an edition that inherits the row cannot carry a foreign year with it.
    """
    with pytest.raises((RegistryValidationError, ValidationError)):
        RelationPrefillProvider.model_validate(
            {
                "kind": "relation_prefill",
                "relation_kind": "cross_model_output",
                "dependency_role": "direct_calculation",
                "source_modelo": "200",
                "source_casilla_id": "DP200014B:00592",
                "temporal": {
                    "kind": "filing_year_offset_by_target_period",
                    "offsets": dict(_M202_OFFSETS),
                    "source_periods": ["0A"],
                    "year": 2024,
                },
            },
        )


@pytest.mark.parametrize(
    "temporal",
    [
        {"kind": "filing_year_offset", "years": -1, "source_periods": ["0A"], "year_from": 2019},
        {"kind": "same_filing_year_periods", "source_periods": ["0A"], "year": 2024},
    ],
)
def test_no_temporal_member_admits_an_absolute_year_field(temporal: dict[str, object]) -> None:
    with pytest.raises((RegistryValidationError, ValidationError)):
        RelationPrefillProvider.model_validate(
            {
                "kind": "relation_prefill",
                "relation_kind": "cross_model_output",
                "dependency_role": "direct_calculation",
                "source_modelo": "130",
                "source_casilla_id": "19",
                "temporal": temporal,
            },
        )


def test_an_annual_summary_fold_must_declare_the_role_that_names_it() -> None:
    with pytest.raises((RegistryValidationError, ValidationError)) as excinfo:
        RelationPrefillProvider.model_validate(
            {
                "kind": "relation_prefill",
                "relation_kind": "annual_summary",
                "dependency_role": "direct_calculation",
                "source_modelo": "303",
                "source_casilla_id": "iva.cuota-devengada-total",
                "temporal": {"kind": "same_filing_year_periods", "source_periods": ["1T"]},
            },
        )
    assert "periodic_to_annual_summary" in str(excinfo.value)
