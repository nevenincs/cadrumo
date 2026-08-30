"""A Schedule's label and its stamp must mean what they claim.

``generated_at`` was documented as a UTC timestamp and typed as a bare
``datetime``, so a naive or offset stamp could ride into persisted or replayed
filing evidence -- ambiguous about the day a filing window opened or closed.

This is a behaviour change: stamps that constructed successfully now refuse.
The assertions are on outcomes rather than identity, because reverting the
validator changes what the model accepts.

The companion class records a rule the audit got WRONG -- that a schedule's
year must equal its obligations' filing years -- measured against the real
engine rather than assumed.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from ....core.modelo import Modelo
from ....core.period import Period
from ..models import (
    CrossPeriodGroupMemberRoster,
    IVARegime,
    ModeloDeadline,
    ObligationStatus,
    Schedule,
    TaxpayerProfile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_UTC_STAMP = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL)


def _obligation(*, filing_year: int, code: str = "1T") -> ModeloDeadline:
    return ModeloDeadline(
        modelo="303",
        period=Period.from_year_and_code(filing_year, code),
        opens_on=date(filing_year, 4, 1),
        closes_on=date(filing_year, 4, 20),
        status=ObligationStatus.UPCOMING,
        applies_because="probe",
    )


def _schedule(**overrides: Any) -> Schedule:
    payload: dict[str, Any] = {
        "profile": _profile(),
        "year": 2026,
        "obligations": (_obligation(filing_year=2026),),
        "generated_at": _UTC_STAMP,
    }
    payload.update(overrides)
    return Schedule(**payload)  # type: ignore[arg-type]


class TestTargetYearIsNotBoundToObligationFilingYear:
    """A schedule's year deliberately does NOT equal its obligations' filing years.

    The audit prescribed an invariant requiring every
    ``obligation.period.filing_year`` to equal ``Schedule.year``. Implementing
    it refused 22 real engine schedules, because the two fields mean different
    things: ``Schedule.year`` is the calendar year whose filing WINDOWS the
    schedule covers, while a period's ``filing_year`` is the tax year being
    REPORTED. Every annual informativa separates them -- a Modelo 180 summary
    for tax year 2024 is filed in January 2025, so the real engine emits
    ``schedule year=2025`` carrying ``filing_year=2024`` obligations.

    This test pins the divergence as intended, so the invariant is not
    re-proposed and silently re-broken.
    """

    def test_a_schedule_may_carry_a_prior_tax_year_obligation(self) -> None:
        january_annual_summary = _obligation(filing_year=2025, code="0A")

        schedule = _schedule(year=2026, obligations=(january_annual_summary,))

        assert schedule.year == 2026
        assert schedule.obligations[0].period.filing_year == 2025

    def test_a_same_year_schedule_is_equally_valid(self) -> None:
        assert _schedule().obligations[0].period.filing_year == 2026

    def test_an_empty_schedule_remains_valid(self) -> None:
        assert _schedule(obligations=()).obligations == ()

    def test_the_schedule_survives_a_json_round_trip(self) -> None:
        restored = Schedule.model_validate_json(_schedule().model_dump_json())

        assert restored == _schedule()


class TestGeneratedAtIsUtc:
    def test_a_utc_stamp_is_accepted(self) -> None:
        assert _schedule().generated_at == _UTC_STAMP

    def test_a_naive_stamp_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _schedule(generated_at=datetime(2026, 1, 1, 12, 0))

    @pytest.mark.parametrize("offset_hours", [1, -5, 2])
    def test_a_non_utc_offset_is_refused(self, offset_hours: int) -> None:
        stamp = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=offset_hours)))

        with pytest.raises(ValidationError):
            _schedule(generated_at=stamp)

    def test_a_zero_offset_tzinfo_is_accepted(self) -> None:
        """UTC-equivalence is the contract, not the tzinfo object's identity."""
        stamp = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(0)))

        assert _schedule(generated_at=stamp).generated_at == _UTC_STAMP


class TestModeloIdentityIsClosed:
    """Deadline modelo identifiers resolve through the canonical closed set.

    ``ModeloDeadline.modelo`` and ``CrossPeriodGroupMemberRoster.source_modelo``
    were plain strings, so an unknown identifier or a whitespace-divergent
    spelling of a real one could enter persisted or imported schedules. Both
    then reach registry matching and downstream projections, which resolve
    them differently from every other surface that uses the canonical enum.

    These are behaviour changes: values that previously constructed now refuse.
    """

    @pytest.mark.parametrize("raw", ["BOGUS", "999", " 303 ", "303 ", "", "M303"])
    def test_an_unsupported_or_divergent_identifier_is_refused(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _obligation_with_modelo(raw)

    def test_a_canonical_token_resolves_to_the_enum_member(self) -> None:
        assert _obligation_with_modelo("303").modelo is Modelo.M303

    def test_an_enum_member_is_accepted_directly(self) -> None:
        assert _obligation_with_modelo(Modelo.M130).modelo is Modelo.M130

    def test_the_roster_shares_the_same_contract(self) -> None:
        assert _roster("322").source_modelo is Modelo.M322

    @pytest.mark.parametrize("raw", ["BOGUS", " 322 "])
    def test_the_roster_refuses_the_same_values(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _roster(raw)

    def test_a_schedule_json_round_trip_preserves_the_identity(self) -> None:
        restored = Schedule.model_validate_json(_schedule().model_dump_json())

        assert restored.obligations[0].modelo is Modelo.M303


def _obligation_with_modelo(raw: object) -> ModeloDeadline:
    return ModeloDeadline(
        modelo=raw,  # type: ignore[arg-type]
        period=Period.from_year_and_code(2026, "1T"),
        opens_on=date(2026, 4, 1),
        closes_on=date(2026, 4, 20),
        status=ObligationStatus.UPCOMING,
        applies_because="probe",
    )


def _roster(raw: object) -> CrossPeriodGroupMemberRoster:
    return CrossPeriodGroupMemberRoster(
        source_modelo=raw,  # type: ignore[arg-type]
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        member_nifs=("12345678Z",),
    )
