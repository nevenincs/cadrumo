"""The palette finds a profile's declarations and works by the words the backend serves for them."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.external_constants import OutputLanguage
from ....core.operations import OperationFrontendProjection, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import ObligationStatus
from ....domain.modelos.work_unit import WorkUnitState
from ...modelo.declaration_summary import DeclarationSummary, DeclarationSummaryState
from ...modelo.declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceStateV1,
)
from ...modelo.declarations_list import DeclarationListInputs
from ...modelo.declarations_workspace_contracts import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceSource,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneStateV1,
)
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationRegistry
from ...overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntrySource,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ...overview.coverage import ObligationCoverageReport
from ...overview.home import HomeAvailability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..declarations_search_operation import (
    MODELO_DECLARATIONS_SEARCH_OPERATION_DEFINITION_ID,
    ModeloDeclarationsSearchHitKind,
    ModeloDeclarationsSearchRequest,
    ModeloDeclarationsSearchResultV1,
    build_modelo_declarations_search_definition,
    build_modelo_declarations_search_registration,
    project_declarations_search,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_AS_OF = date(2025, 10, 1)
_NOW = datetime(2025, 10, 1, 12, tzinfo=UTC)
_THIRD = Period.from_year_and_code(2025, "3T")
_FIRST = Period.from_year_and_code(2025, "1T")


def _work(modelo: str, period: Period, work: str) -> DeclarationsWorkspaceDeclarationRefV1:
    return DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=work * 64,
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        state=WorkUnitState.BORRADOR,
        has_current_calculation=False,
        has_current_filing=False,
        summary=DeclarationSummary(state=DeclarationSummaryState.DRAFT),
    )


def _workspace(*works: DeclarationsWorkspaceDeclarationRefV1) -> DeclarationsWorkspaceProjectionV1:
    return DeclarationsWorkspaceProjectionV1(
        bucket_id="13000000-0000-4000-8000-000000000450",
        zones=tuple(
            DeclarationsWorkspaceZoneStateV1(
                zone=zone,
                availability=DeclarationsWorkspaceAvailability.AVAILABLE,
                observed_at=_NOW,
                sources=tuple(DeclarationsWorkspaceSource),
                item_count=len(works) if zone is DeclarationsWorkspaceZone.DECLARATIONS else 0,
            )
            for zone in DeclarationsWorkspaceZone
        ),
        declarations=works,
        calculation_revisions=(),
        filings=(),
        lifecycle=(),
    )


def _due(modelo: str, period: Period) -> DeclarationsCalendarEntryRefV1:
    return DeclarationsCalendarEntryRefV1(
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        opens_on=date(2025, 10, 1),
        closes_on=date(2025, 10, 20),
        adjusted_closes_on=date(2025, 10, 20),
        shift_reason="unchanged",
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
        evaluated_on=_AS_OF,
        days_overdue=None,
        legal_status=ObligationStatus.UPCOMING,
        user_state=OverviewPeriodState.DUE,
        local_filing_state=OverviewLocalFilingState.NOT_READY_TO_FILE,
        aeat_submission_state=OverviewAeatSubmissionState.NOT_OBSERVED,
        justificante_verified=False,
        evidence_conflicted=False,
        aeat_submitted_at=None,
        source=OverviewCalendarEntrySource.REGISTRY_DEADLINE,
    )


def _calendar(*entries: DeclarationsCalendarEntryRefV1) -> DeclarationsCalendarProjectionV1:
    return DeclarationsCalendarProjectionV1(
        as_of=_AS_OF,
        generated_at=_NOW,
        query_range=OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 12, 31)),
        sources=tuple(
            DeclarationsCalendarSourceStateV1(
                source=source,
                availability=HomeAvailability.AVAILABLE,
                observed_at=_NOW,
                item_count=len(entries),
            )
            for source in DeclarationsCalendarSource
        ),
        entries=entries,
        coverage=ObligationCoverageReport(advised=()),
    )


def _search(
    query: str,
    *,
    language: OutputLanguage = OutputLanguage.ES,
    limit: int = 20,
    due: tuple[DeclarationsCalendarEntryRefV1, ...] = (),
) -> ModeloDeclarationsSearchResultV1:
    workspace = _workspace(_work("303", _THIRD, "a"), _work("303", _FIRST, "b"), _work("130", _THIRD, "c"))
    request = ModeloDeclarationsSearchRequest(profile_id=_PROFILE, output_language=language, query=query, limit=limit)
    return project_declarations_search(request, workspace, _calendar(*due))


def _addresses(result: ModeloDeclarationsSearchResultV1) -> list[tuple[str, str | None]]:
    return [(hit.modelo, hit.period_code) for hit in result.hits]


def test_the_modelo_number_finds_every_work_of_that_modelo() -> None:
    result = _search("303")

    assert sorted(_addresses(result)) == [("303", "1T"), ("303", "3T")]
    assert {hit.kind for hit in result.hits} == {ModeloDeclarationsSearchHitKind.WORK}
    assert all(hit.work_unit_id is not None and hit.title_words for hit in result.hits)
    assert result.total_matches == 2


def test_the_period_as_the_filer_reads_it_finds_the_work_of_that_period() -> None:
    result = _search("3.er trimestre")

    assert sorted(_addresses(result)) == [("130", "3T"), ("303", "3T")]


@pytest.mark.parametrize("query", ["3.ER TRIMESTRE", "  3 er  trimestre!", "TRIMéSTRE 3.er", "303 3.er trimestre"])
def test_case_accents_punctuation_and_order_do_not_change_a_match(query: str) -> None:
    result = _search(query)

    assert ("303", "3T") in _addresses(result)


def test_a_query_every_word_of_which_must_match_leaves_out_the_other_periods() -> None:
    result = _search("303 3.er trimestre")

    assert _addresses(result) == [("303", "3T")]


def test_the_words_are_said_in_the_language_asked_for() -> None:
    result = _search("3rd quarter", language=OutputLanguage.EN)

    assert sorted(_addresses(result)) == [("130", "3T"), ("303", "3T")]
    assert all(hit.period_words == "3rd quarter 2025" for hit in result.hits)
    assert _search("3rd quarter", language=OutputLanguage.ES).hits == ()


def test_a_work_ranks_before_a_declaration_that_is_only_due() -> None:
    result = _search("303 3.er trimestre", due=(_due("303", Period.from_year_and_code(2025, "3T")),))
    only_due = _search("303", due=(_due("303", Period.from_year_and_code(2025, "2T")),))

    assert [hit.kind for hit in result.hits] == [ModeloDeclarationsSearchHitKind.WORK]
    kinds = [hit.kind for hit in only_due.hits]
    assert kinds == [
        ModeloDeclarationsSearchHitKind.WORK,
        ModeloDeclarationsSearchHitKind.WORK,
        ModeloDeclarationsSearchHitKind.DECLARATION,
    ]
    assert only_due.hits[-1].work_unit_id is None
    assert [hit.rank for hit in only_due.hits] == [0, 1, 2]


def test_the_limit_caps_the_hits_but_not_the_count_of_matches() -> None:
    result = _search("trimestre", limit=1)

    assert len(result.hits) == 1 and result.total_matches == 3


def test_nothing_matching_is_an_empty_result_not_a_refusal() -> None:
    result = _search("zzzz")

    assert result.hits == () and result.total_matches == 0


@pytest.mark.parametrize("query", ["", "   ", "...", "\x00303"])
def test_a_query_without_words_is_refused_at_the_request(query: str) -> None:
    with pytest.raises(ValidationError):
        ModeloDeclarationsSearchRequest(profile_id=_PROFILE, output_language=OutputLanguage.ES, query=query)


def _unread(profile_id: str, operation: PinnedAuthorityOperation) -> Callable[[], DeclarationListInputs]:
    raise AssertionError("resolving access reads no declaration")


def _registration():
    definition = build_modelo_declarations_search_definition(_unread)
    registration = build_modelo_declarations_search_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(*, profile_id: UUID = _PROFILE, subject: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    request = OperationRequest[ModeloDeclarationsSearchRequest](
        definition_id=MODELO_DECLARATIONS_SEARCH_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject)),
        payload=ModeloDeclarationsSearchRequest(profile_id=profile_id, output_language=OutputLanguage.ES, query="303"),
    )
    return cast(OperationRequest[BaseModel], cast(object, request))


def _context(registration) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def test_the_search_needs_whole_profile_consent_and_holds_no_commit_door() -> None:
    registry, registration = _registration()

    resolved = resolve_operation_access(registry=registry, request=_request(), context=_context(registration))

    assert resolved.request.period_independent and not resolved.request.periods
    assert resolved.policy.allow_period_independent and resolved.policy.requires_all_periods
    assert AccessAction.COMMIT not in resolved.policy.actions


@pytest.mark.parametrize(("profile_id", "subject"), [(_OTHER, _OTHER), (_OTHER, _PROFILE), (_PROFILE, _OTHER)])
def test_a_search_for_another_profile_is_refused(profile_id: UUID, subject: UUID) -> None:
    registry, registration = _registration()

    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry, request=_request(profile_id=profile_id, subject=subject), context=_context(registration)
        )
