"""An unstated large-company condition yields no cadence, and the calendar says so.

LIVA art. 121 fixes the volumen de operaciones and RIVA art. 71 answers the
threshold with monthly IVA liquidation, which is the condition the filing
schedules of Modelos 111, 115, 123, 216 and 303 select their cadence from.
``censo.large_company`` defaulted to ``false``, so an unasked taxpayer was
given the quarterly cadence as though they had stated their turnover.

What an unanswered condition implies is neither cadence. A quarterly schedule
requires the condition to have been stated as a no and a monthly one as a yes,
so an unstated condition selects no schedule and the modelo gets no deadline
window for the period: the engine does not guess monthly and does not guess
quarterly. The operator is not left with silence, though, because the
condition is a gating key and the calendar emits its named unset warning
against exactly those modelos, which is the typed report of an unanswered
cadence.

Both levels are exercised through production code: the registry's own schedule
evaluator for every revision that reads the condition, and the production
calendar for the one modelo this record makes applicable, so what is asserted
is the behaviour an operator sees rather than a predicate in isolation.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schedules import applicable_filing_schedules
from ....domain.calculations.registry.temporal import RevisionSelectionMetadata
from ....domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ....domain.deadlines.models import TaxpayerProfile
from ...user_profile.projections import projection_for_taxpayer, record_to_path_values
from ...user_profile.tests.payer_fact_record_support import (
    LARGE_COMPANY_CADENCE_MODELOS,
    LARGE_COMPANY_PATH,
    large_company_record,
)
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendar, OverviewCalendarRange
from ..calendar_warnings import PROFILE_FIELD_WARNING_LOCALE_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HORIZON = PublishedGovernedFactSource().supported_filing_years().horizon
"""The registry's own last globally authored filing year; never a literal."""

_TODAY = date(_HORIZON, 10, 19)
_RANGE = OverviewCalendarRange(from_date=date(_HORIZON, 1, 1), to_date=date(_HORIZON + 1, 2, 1))

_WARNING_CODE = "enrollment.large_company"
"""The registry selector token the condition is named under, and so its warning code."""

_PERIODIC_IVA_MODELO = "303"
"""The one cadence modelo this record makes applicable, so its rows are observable.

The other four are withholding declarations whose own payer facts this record
leaves unanswered, so they are incomplete and the calendar gives them no row
at all. Their cadence is asserted through the schedule evaluator instead.
"""


def _profile(operation: PinnedAuthorityOperation, *, answer: bool | None) -> TaxpayerProfile:
    record = large_company_record(operation, answer=answer)
    return projection_for_taxpayer(record, schema=operation.profile_schema())


def _calendar(operation: PinnedAuthorityOperation, *, answer: bool | None) -> OverviewCalendar:
    record = large_company_record(operation, answer=answer)
    schema = operation.profile_schema()
    return build_overview_calendar(
        projection_for_taxpayer(record, schema=schema),
        _RANGE,
        operation=operation,
        today=_TODAY,
        raw_values=record_to_path_values(record),
    )


def _cadence_revisions(
    operation: PinnedAuthorityOperation,
) -> tuple[tuple[str, RevisionSelectionMetadata], ...]:
    """Return every revision whose filing schedules read the large-company condition."""
    found: list[tuple[str, RevisionSelectionMetadata]] = []
    for modelo in LARGE_COMPANY_CADENCE_MODELOS:
        for metadata in operation.modelo_directory(modelo).revisions:
            if _schedules_requiring(metadata, value=True) or _schedules_requiring(metadata, value=False):
                found.append((modelo, metadata))
    return tuple(found)


def _schedules_requiring(metadata: RevisionSelectionMetadata, *, value: bool) -> frozenset[str]:
    """Return the ids of the schedules this revision gives the condition's ``value``.

    Which value each schedule asks for comes from the registry, never from
    this test: a revision that declares no monthly schedule of its own must
    not be asserted to select one.
    """
    return frozenset(
        schedule.id
        for schedule in metadata.filing_schedules
        for condition in schedule.profile_conditions
        if condition.field == _WARNING_CODE and condition.value == value
    )


def test_the_condition_is_declared_three_state_on_the_projected_profile(
    operation: PinnedAuthorityOperation,
) -> None:
    record = large_company_record(operation, answer=None)

    assert not [fact for fact in record.facts if fact.path == LARGE_COMPANY_PATH]
    assert _profile(operation, answer=None).enrollment.large_company is None


def test_every_cadence_revision_reads_the_condition(authority_operation: PinnedAuthorityOperation) -> None:
    """The assertions below are empty unless the registry really declares these schedules."""
    named = {modelo for modelo, _metadata in _cadence_revisions(authority_operation)}

    assert named == set(LARGE_COMPANY_CADENCE_MODELOS)


def test_an_unstated_condition_selects_no_filing_schedule(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The defect this closes: a quarterly schedule used to match a condition nobody stated."""
    profile = _profile(authority_operation, answer=None)

    matched = {
        modelo: _selected_cadence_schedules(metadata, profile)
        for modelo, metadata in _cadence_revisions(authority_operation)
    }
    assert not [modelo for modelo, schedules in matched.items() if schedules], matched


@pytest.mark.parametrize("answer", [True, False])
def test_a_stated_condition_selects_the_schedules_declared_for_that_answer(
    answer: bool,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Each answer must select exactly the schedules the registry gives it.

    Compared against the declared set rather than against "at least one", so a
    revision that authors no schedule for one of the two answers is reported
    as declaring none instead of silently passing as a match.
    """
    profile = _profile(authority_operation, answer=answer)

    for modelo, metadata in _cadence_revisions(authority_operation):
        declared = _schedules_requiring(metadata, value=answer)
        assert _selected_cadence_schedules(metadata, profile) == declared, modelo


def test_both_answers_are_declared_somewhere_so_neither_assertion_is_empty(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A stated yes and a stated no must each select a real schedule for some modelo."""
    revisions = _cadence_revisions(authority_operation)

    for answer in (True, False):
        selecting = [
            modelo
            for modelo, metadata in revisions
            if _selected_cadence_schedules(metadata, _profile(authority_operation, answer=answer))
        ]
        assert selecting, answer


def test_an_unstated_condition_leaves_the_periodic_iva_calendar_empty(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unstated = _periods(_calendar(authority_operation, answer=None))
    quarterly = _periods(_calendar(authority_operation, answer=False))
    monthly = _periods(_calendar(authority_operation, answer=True))

    assert unstated == frozenset()
    assert quarterly
    assert monthly
    assert quarterly != monthly


def test_an_unstated_condition_warns_against_the_modelos_whose_cadence_it_decides(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A dropped cadence must reach the operator as a named gap, not as an empty calendar."""
    calendar = _calendar(authority_operation, answer=None)

    warnings = [warning for warning in calendar.warnings if warning.code == _WARNING_CODE]
    assert len(warnings) == 1
    assert warnings[0].message == PROFILE_FIELD_WARNING_LOCALE_KEYS[_WARNING_CODE]
    assert frozenset(LARGE_COMPANY_CADENCE_MODELOS) <= frozenset(warnings[0].affected_modelos)
    assert _WARNING_CODE in calendar.completeness.defaulted_keys


@pytest.mark.parametrize("answer", [True, False])
def test_a_stated_condition_raises_no_cadence_warning(
    answer: bool,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = _calendar(authority_operation, answer=answer)

    assert not [warning for warning in calendar.warnings if warning.code == _WARNING_CODE]
    assert _WARNING_CODE in calendar.completeness.explicitly_set_keys


def _selected_cadence_schedules(
    metadata: RevisionSelectionMetadata,
    profile: TaxpayerProfile,
) -> frozenset[str]:
    """Return the ids of the matched schedules that read the large-company condition."""
    return frozenset(
        schedule.id
        for schedule in applicable_filing_schedules(metadata, profile)
        if any(condition.field == _WARNING_CODE for condition in schedule.profile_conditions)
    )


def _periods(calendar: OverviewCalendar) -> frozenset[str]:
    return frozenset(entry.period.registry_token for entry in calendar.entries if entry.modelo == _PERIODIC_IVA_MODELO)
