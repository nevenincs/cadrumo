"""Modelos 115 and 123 have both cadences, so a stated large company gets monthly windows.

RIRPF art. 108.1 gives every retención self-assessment two cadences. Paragraph
one puts the ordinary retenedor on the first twenty calendar days of April,
July, October and January; paragraph two moves the declaration to the first
twenty calendar days of each month, for the month immediately before, when the
retenedor is in the circumstances of RIVA art. 71.3 numbers 1 and 2 -- the
volumen de operaciones over 6.010.121,04 EUR that ``censo.large_company``
carries. AEAT's own Calendario del Contribuyente names Modelos 115 and 123 in
that monthly population every month.

Modelos 115 and 123 declared only the quarterly cadence. Once the condition
became three-state, a quarterly schedule needed a stated no, so a taxpayer who
stated that he is a large company selected no schedule at all and the two
modelos lost every deadline window: the filer with the stricter obligation was
shown none.

Each case below resolves through the real deadline engine over the pinned
authority, so a window counts only if the registry authors it and the schedule
gate admits it for the projected profile. The sibling
``test_large_company_cadence_declaration`` holds the condition's three-state
contract across every cadence modelo; this file holds that these two modelos
really declare both cadences, which that one deliberately does not assert.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ....domain.deadlines.engine import DeadlineEngine
from ....domain.deadlines.models import TaxpayerProfile
from ...user_profile.projections import projection_for_taxpayer
from ...user_profile.tests.payer_fact_record_support import LARGE_COMPANY_PATH, large_company_record
from ..calendar_warnings import PROFILE_FIELD_WARNING_LOCALE_KEYS, derive_gating_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELOS = ("115", "123")
"""The two retención modelos whose monthly cadence this file holds."""

_WARNING_CODE = "enrollment.large_company"
"""The registry selector token the condition is named under, and so its warning code."""

_QUARTERS = frozenset({"1T", "2T", "3T", "4T"})
_MONTHS = frozenset({"01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"})

_FILING_YEAR = PublishedGovernedFactSource().supported_filing_years().horizon
"""The registry's own last globally authored filing year; never a literal."""


def _profile(operation: PinnedAuthorityOperation, *, answer: bool | None) -> TaxpayerProfile:
    return projection_for_taxpayer(large_company_record(operation, answer=answer), schema=operation.profile_schema())


def _admitted_periods(operation: PinnedAuthorityOperation, *, modelo: str, answer: bool | None) -> frozenset[str]:
    """Return the period tokens whose window the engine's schedule gate admits for this filer."""
    profile = _profile(operation, answer=answer)
    engine = DeadlineEngine(authority=operation)
    return frozenset(
        window.period.registry_token
        for code, revision, window in engine.deadline_windows(_FILING_YEAR)
        if code == modelo and engine.schedule_applies(profile, revision, window)
    )


@pytest.mark.parametrize("modelo", _MODELOS)
def test_a_stated_large_company_is_given_the_monthly_windows(
    modelo: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The defect this closes: the stricter filer was given no window at all."""
    admitted = _admitted_periods(authority_operation, modelo=modelo, answer=True)

    assert admitted == _MONTHS


@pytest.mark.parametrize("modelo", _MODELOS)
def test_a_stated_ordinary_retenedor_is_given_the_quarterly_windows(
    modelo: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    admitted = _admitted_periods(authority_operation, modelo=modelo, answer=False)

    assert admitted == _QUARTERS


@pytest.mark.parametrize("modelo", _MODELOS)
def test_an_unanswered_condition_is_given_neither_cadence(
    modelo: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Neither cadence may be guessed: adding the monthly schedule must not revive a default."""
    record = large_company_record(authority_operation, answer=None)
    assert not [fact for fact in record.facts if fact.path == LARGE_COMPANY_PATH]

    assert _admitted_periods(authority_operation, modelo=modelo, answer=None) == frozenset()


@pytest.mark.parametrize("modelo", _MODELOS)
def test_the_unanswered_condition_reaches_the_operator_as_this_modelo_named_gap(
    modelo: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A withdrawn cadence is reported, not silent: the gating derivation names the modelo."""
    derived = derive_gating_fields(operation=authority_operation)

    modelos, message_key, _action = derived[_WARNING_CODE]
    assert modelo in modelos
    assert message_key == PROFILE_FIELD_WARNING_LOCALE_KEYS[_WARNING_CODE]


@pytest.mark.parametrize("modelo", _MODELOS)
def test_both_cadences_cover_the_whole_year_without_overlapping(
    modelo: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A filer is on one cadence or the other, never on a mixture of the two."""
    monthly = _admitted_periods(authority_operation, modelo=modelo, answer=True)
    quarterly = _admitted_periods(authority_operation, modelo=modelo, answer=False)

    assert not monthly & quarterly
    assert len(monthly) == 12
    assert len(quarterly) == 4


@pytest.mark.parametrize("modelo", _MODELOS)
def test_the_monthly_window_closes_the_month_after_its_period(
    modelo: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The authored closes are the published ones, so each opens after its own period ends."""
    profile = _profile(authority_operation, answer=True)
    engine = DeadlineEngine(authority=authority_operation)

    seen = 0
    for code, revision, window in engine.deadline_windows(_FILING_YEAR):
        if code != modelo or not engine.schedule_applies(profile, revision, window):
            continue
        seen += 1
        period_end = window.period.end_date
        deadline_month = (period_end.year + 1, 1) if period_end.month == 12 else (period_end.year, period_end.month + 1)
        assert window.opens_on > period_end
        assert window.closes_on >= window.opens_on
        assert (window.closes_on.year, window.closes_on.month) == deadline_month
    assert seen == 12
