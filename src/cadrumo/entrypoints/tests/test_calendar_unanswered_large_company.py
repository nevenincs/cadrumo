"""A calendar whose large-company answer is missing loads, and names the question instead of a deadline.

The operator's profile (a general-regime autónomo with the four IVA answers
given and the large-company condition never asked) first showed Modelo 303 as
applicable with no deadline, because neither the monthly nor the quarterly
cadence matched. Holding those windows as undecided then handed a held-off row
a verdict with no served sentence, and the installed calendar read settled
FAILED on every refresh. Both were invisible below the row projection, so this
drives the registered overview read for every supported year with the answer
missing, stated "no" and stated "yes".

Every read and edit is a registered operation in a replayed persona world. No doubles.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ...adapters.persistence.storage.tests.profile_capsule_runtime import replace_test_profile_record
from ...application.overview.calendar_models import OverviewCalendar
from ...application.overview.coverage import CoverageAdviceReason
from ...application.overview.read_payload import OverviewCalendarRead
from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadKind, OverviewReadRequest
from ...application.overview.read_result import OverviewReadProjection
from ...application.overview.suppressed_verdict_words import SUPPRESSING_VERDICTS
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_PATCH_OPERATION_DEFINITION_ID,
    ProfilePatchOperationRequest,
    ProfilePatchValue,
)
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.user_profile.values import create_user_profile_record
from .persona_materialisation import materialised_persona
from .persona_operations import run_operation, settle_operation
from .persona_replay_requests import load_profile_record
from .persona_world import PersonaWorld, ReplayScope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PERSONA = "autonomo-fontanero"
_STORED_PATH = "censo.large_company"
_QUESTION_ID = "enrollment-large-company"
_WARNING_CODE = "enrollment.large_company"


def _years(world: PersonaWorld) -> tuple[int, ...]:
    envelope = world.operation.supported_filing_years()
    return tuple(range(envelope.floor, envelope.horizon + 1))


def _read(world: PersonaWorld, year: int) -> OverviewCalendarRead:
    request = OverviewReadRequest.model_validate(
        {
            "profile_id": world.profile_id,
            "kind": OverviewReadKind.CALENDAR,
            "output_language": OutputLanguage.ES,
            "from_date": date(year, 1, 1),
            "to_date": date(year + 1, 1, 31),
            "show_suppressed": True,
        },
    )
    projection = run_operation(
        world, OVERVIEW_READ_DEFINITION_IDS[OverviewReadKind.CALENDAR], request, OverviewReadProjection
    )
    payload = projection.payload
    assert isinstance(payload, OverviewCalendarRead)
    assert payload.calendar is not None, year
    # Every held-off row reached the operator with the worker's sentence for its verdict.
    assert all(row.verdict in SUPPRESSING_VERDICTS and row.verdict_words for row in payload.calendar.suppressed_entries)
    return payload


def _calendars(world: PersonaWorld) -> dict[int, OverviewCalendar]:
    calendars: dict[int, OverviewCalendar] = {}
    for year in _years(world):
        payload = _read(world, year)
        assert payload.calendar is not None
        calendars[year] = payload.calendar.to_calendar()
    return calendars


def _unanswer(world: PersonaWorld) -> None:
    """Store the profile as one saved before the large-company question was asked, as the operator's was."""
    record = load_profile_record(world)
    replace_test_profile_record(
        create_user_profile_record(
            setup_state=record.setup_state,
            profile_id=record.profile_id,
            facts=tuple(fact for fact in record.facts if fact.path != _STORED_PATH),
            created_at=record.created_at,
            updated_at=record.updated_at,
            context=world.operation.profile_create_context(),
        ),
        root=world.storage_root,
    )
    assert _STORED_PATH not in {fact.path for fact in load_profile_record(world).facts}


def _answer(world: PersonaWorld, value: str) -> None:
    record = load_profile_record(world)
    settle_operation(
        world,
        PROFILE_PATCH_OPERATION_DEFINITION_ID,
        ProfilePatchOperationRequest(
            profile_id=world.profile_id,
            expected_revision=record.record_revision,
            expected_content_digest=record.content_digest,
            values=(ProfilePatchValue(question_id=_QUESTION_ID, value=value),),
        ),
    )


def _window_missing(calendar: OverviewCalendar) -> set[str]:
    return {
        item.modelo
        for item in calendar.coverage.advised
        if item.reason is CoverageAdviceReason.APPLICABLE_WINDOW_MISSING
    }


def _periods(calendar: OverviewCalendar, modelo: str, year: int) -> set[str]:
    return {
        entry.period.registry_token
        for entry in calendar.entries
        if entry.modelo == modelo and entry.period.filing_year == year
    }


def test_the_calendar_loads_and_dates_303_by_the_large_company_answer(tmp_path: Path) -> None:
    with materialised_persona(_PERSONA, tmp_path, ReplayScope.PROFILE, reuse=True) as replayed:
        world = replayed.world
        periodic = str(form_for_role("iva.periodic", authority=world.operation))
        _unanswer(world)
        unanswered = _calendars(world)
        _answer(world, "false")
        small = _calendars(world)
        _answer(world, "true")
        large = _calendars(world)

    assert unanswered, "the supported-year envelope is empty"
    for year, calendar in unanswered.items():
        # No modelo is applicable without a deadline or a named question.
        assert _window_missing(calendar) == set(), year
        # A missing answer is never read as either cadence.
        assert not _periods(calendar, periodic, year), year
        held = [row for row in calendar.suppressed_entries if row.modelo == periodic]
        assert held, year
        assert all(row.verdict is ApplicabilityVerdict.INCOMPLETE and row.actions for row in held), year
        named = {warning.code: warning for warning in calendar.warnings}
        assert _WARNING_CODE in named, year
        assert periodic in named[_WARNING_CODE].affected_modelos, year
    for year, calendar in small.items():
        assert _window_missing(calendar) == set(), year
        assert _periods(calendar, periodic, year) == {"1T", "2T", "3T", "4T"}, year
        assert _WARNING_CODE not in {warning.code for warning in calendar.warnings}, year
    for year, calendar in large.items():
        assert _window_missing(calendar) == set(), year
        monthly = _periods(calendar, periodic, year)
        assert monthly, year
        assert all(token.isdigit() for token in monthly), (year, monthly)
