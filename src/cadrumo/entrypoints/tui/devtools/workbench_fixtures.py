"""Deterministic, non-sensitive visual fixtures for the production workbench.

This module is deliberately a fixture boundary.  Every builder starts from
already-constructed application projections and hands a real production
screen to :class:`ScreenHostApp` (or to the real root application).  It does
not open a repository, contact AEAT, read a clock, or create a synthetic
screen subclass.  The central visual-surface registry can consume
``WORKBENCH_FIXTURES`` later without importing any fixture-private facts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Final, cast

from textual.app import App
from textual.screen import Screen

from ....application.aeat_sync.workspace import (
    AeatSyncAeatObservationState,
    AeatSyncCensusCategory,
    AeatSyncCensusStatus,
    AeatSyncDiscrepancyKind,
    AeatSyncDocumentCustodyState,
    AeatSyncJustificanteState,
    AeatSyncLocalFilingState,
    AeatSyncNotificationCategory,
    AeatSyncNotificationReadState,
    AeatSyncOverviewArea,
    AeatSyncReconciliationState,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceCensusRowV1,
    AeatSyncWorkspaceEvidenceComparisonRowV1,
    AeatSyncWorkspaceFactV1,
    AeatSyncWorkspaceFiledDeclarationRowV1,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceOverviewRowV1,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceReconciliationRowV1,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceSourceObservationV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneObservationV1,
    aeat_sync_workspace_sources,
    project_aeat_sync_workspace,
)
from ....application.modelo.declarations_calendar import (
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceObservationV1,
    project_declarations_calendar,
)
from ....application.modelo.declarations_workspace import (
    DeclarationsLifecycleKind,
    DeclarationsSanitizedLifecycleFactV1,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
    project_declarations_workspace,
)
from ....application.operations.composition import OperationComposedServices, OperationSubmission
from ....application.operations.frontend_contracts import (
    OperationNoPendingInteractionV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicProjectionV1,
    OperationReplayStatus,
    OperationSubmissionReceiptV1,
)
from ....application.operations.interactions import OperationActorReference
from ....application.operations.models import OperationId
from ....application.operations.registry import OperationPublicContractSetV1
from ....application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE, lookup_action
from ....application.operator_actions.models import ActionReference
from ....application.overview.calendar_models import (
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    OverviewPeriodState,
)
from ....application.overview.evidence import CalendarEvidenceProjection
from ....application.overview.home import HomeAvailability, HomeZoneState
from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ....application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION,
    build_censal_operation_registration,
)
from ....core.casilla_id import validated_casilla_id
from ....core.operations import OperationEffect, OperationLifecycle
from ....core.period import Period
from ....domain.deadlines.models import ObligationStatus
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import ModeloRecord, ModeloRecordCatalogue, derive_filing_record_id
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ..aeat_sync.controller import AeatSyncWorkspaceController
from ..aeat_sync.routes import resolve_aeat_sync_screen
from ..aeat_sync.screens import (
    AeatSyncCensusScreen,
    AeatSyncEvidenceComparisonScreen,
    AeatSyncFiledDeclarationsScreen,
    AeatSyncNotificationsScreen,
    AeatSyncOverviewScreen,
    AeatSyncReconciliationScreen,
)
from ..app import CadrumoTuiApp
from ..components.host import ScreenHostApp
from ..declarations.controller import DeclarationsWorkspaceController
from ..declarations.models import DeclarationsDestinationIdV1
from ..declarations.overview import DeclarationsModeloWorkspaceLauncherScreen
from ..declarations.routes import resolve_declarations_screen
from ..home import HomeScreen
from ..navigation import (
    TuiDestinationAdmissionV1,
    TuiScreenContextV1,
    build_destination_catalogue,
)
from ..operations.controller import OperationController
from ..operations.modal import OperationModal

_BUCKET: Final[str] = "00000000-0000-4000-8000-000000000001"
_AT: Final[datetime] = datetime(2026, 9, 3, 10, tzinfo=UTC)


class WorkbenchFixtureScenario(StrEnum):
    """Closed fixture states shared by the workbench candidates."""

    READY = "ready"
    EMPTY = "empty"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"
    REFUSAL = "refusal"
    FAILURE = "failure"


FixtureBuilder = Callable[[], App[Any]]


@dataclass(frozen=True, slots=True)
class WorkbenchFixtureSpec:
    """One production surface, state, interface list, and stable metadata."""

    surface_id: str
    scenario: WorkbenchFixtureScenario
    interfaces: tuple[str, ...]
    build: FixtureBuilder
    metadata: tuple[tuple[str, str], ...] = ()

    @property
    def fixture_id(self) -> str:
        """Return the deterministic identity consumed by the later registry."""
        return f"{self.surface_id}--{self.scenario.value}"


def _host(screen: Screen[Any]) -> App[Any]:
    """Wrap one real screen in the standard single-screen production host."""
    return ScreenHostApp(screen)


def _home(scenario: WorkbenchFixtureScenario) -> App[Any]:
    from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture

    mapping = {
        WorkbenchFixtureScenario.READY: HomeFixtureScenario.READY,
        WorkbenchFixtureScenario.EMPTY: HomeFixtureScenario.EMPTY,
        WorkbenchFixtureScenario.STALE: HomeFixtureScenario.STALE,
        WorkbenchFixtureScenario.UNAVAILABLE: HomeFixtureScenario.UNAVAILABLE,
        WorkbenchFixtureScenario.BLOCKED: HomeFixtureScenario.BLOCKED,
        WorkbenchFixtureScenario.REFUSAL: HomeFixtureScenario.UNAVAILABLE,
        WorkbenchFixtureScenario.FAILURE: HomeFixtureScenario.UNAVAILABLE,
    }
    return _host(HomeScreen(build_home_projection_fixture(mapping[scenario])))


def _source_availability(scenario: WorkbenchFixtureScenario) -> AeatSyncWorkspaceAvailability:
    if scenario is WorkbenchFixtureScenario.STALE:
        return AeatSyncWorkspaceAvailability.STALE
    if scenario is WorkbenchFixtureScenario.UNAVAILABLE:
        return AeatSyncWorkspaceAvailability.UNAVAILABLE
    return AeatSyncWorkspaceAvailability.AVAILABLE


def _aeat_source(
    source: AeatSyncWorkspaceSource,
    availability: AeatSyncWorkspaceAvailability,
    *,
    count: int,
) -> AeatSyncWorkspaceSourceObservationV1:
    observable = availability in {
        AeatSyncWorkspaceAvailability.AVAILABLE,
        AeatSyncWorkspaceAvailability.STALE,
    }
    return AeatSyncWorkspaceSourceObservationV1(
        source=source,
        availability=availability,
        observed_at=_AT if observable else None,
        refusal=None if availability is AeatSyncWorkspaceAvailability.AVAILABLE else "fixture.aeat_sync.refused",
        item_count=count if observable else None,
    )


def _operation_contracts() -> OperationPublicContractSetV1:
    """Build the canonical censo contract with its existing action join."""
    definition = CENSAL_OPERATION_DEFINITION.model_copy(
        update={"action_reference": ActionReference(action_id="operator.profile.edit")}
    )
    contract = build_censal_operation_registration(definition).contract
    return OperationPublicContractSetV1.build((contract,))


def _aeat_projection(scenario: WorkbenchFixtureScenario) -> AeatSyncWorkspaceProjectionV1:
    availability = _source_availability(scenario)
    populated = scenario not in {WorkbenchFixtureScenario.EMPTY, WorkbenchFixtureScenario.UNAVAILABLE}
    notification_read = scenario is not WorkbenchFixtureScenario.REFUSAL
    count = 1 if populated else 0
    observations = tuple(
        AeatSyncWorkspaceZoneObservationV1(
            zone=zone,
            sources=tuple(
                _aeat_source(source, availability, count=count) for source in aeat_sync_workspace_sources(zone)
            ),
        )
        for zone in AeatSyncWorkspaceZone
    )
    if not populated:
        return project_aeat_sync_workspace(
            bucket_id=_BUCKET,
            subject_key="fixture.subject",
            zone_observations=observations,
            action_catalogue=OPERATOR_ACTION_CATALOGUE,
            operation_contracts=_operation_contracts(),
        )

    period = Period.from_year_and_code(2026, "1T")
    action = ActionReference(action_id="operator.profile.edit")
    overview = AeatSyncWorkspaceOverviewRowV1(
        area=AeatSyncOverviewArea.CENSUS,
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.PRESENT,
        local_observed_at=_AT,
        aeat_observed_at=_AT,
        discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
        supported_actions=(action,),
        supported_operations=("user-profile.censo-review",),
    )
    census = AeatSyncWorkspaceCensusRowV1(
        path="Tax address",
        category=AeatSyncCensusCategory.ADDRESS,
        status=AeatSyncCensusStatus.CONFLICT,
    )
    filed = AeatSyncWorkspaceFiledDeclarationRowV1(
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        local_filing_state=AeatSyncLocalFilingState.FILED,
        local_filed_at=_AT,
        aeat_observation_state=AeatSyncAeatObservationState.ACCEPTED,
        aeat_observed_at=_AT,
        justificante_state=AeatSyncJustificanteState.VERIFIED,
        justificante_observed_at=_AT,
    )
    notification = AeatSyncWorkspaceNotificationRowV1(
        issued_on=date(2026, 9, 1),
        read_on=date(2026, 9, 2) if notification_read else None,
        read_state=AeatSyncNotificationReadState.READ if notification_read else AeatSyncNotificationReadState.UNREAD,
        category=AeatSyncNotificationCategory.FORMAL,
        document_custody_state=(
            AeatSyncDocumentCustodyState.HELD if notification_read else AeatSyncDocumentCustodyState.NOT_CAPTURED
        ),
        document_custody_observed_at=_AT if notification_read else None,
    )
    comparison = AeatSyncWorkspaceEvidenceComparisonRowV1(
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.ABSENT,
        local_observed_at=_AT,
        aeat_observed_at=_AT,
        discrepancy_kind=AeatSyncDiscrepancyKind.LOCAL_ONLY,
    )
    reconciliation = AeatSyncWorkspaceReconciliationRowV1(
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.ABSENT,
        local_observed_at=_AT,
        aeat_observed_at=_AT,
        discrepancy_kind=AeatSyncDiscrepancyKind.LOCAL_ONLY,
        reconciliation_state=AeatSyncReconciliationState.KEEP_LOCAL,
    )

    def fact(row: Any) -> AeatSyncWorkspaceFactV1[Any]:
        return AeatSyncWorkspaceFactV1(_BUCKET, "fixture.subject", row)

    return project_aeat_sync_workspace(
        bucket_id=_BUCKET,
        subject_key="fixture.subject",
        zone_observations=observations,
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=_operation_contracts(),
        overview=(fact(overview),),
        census=(fact(census),),
        filed_declarations=(fact(filed),),
        notifications=(
            AeatSyncWorkspaceFactV1(
                _BUCKET,
                "fixture.subject",
                notification,
                private_identity="fixture.notification",
            ),
        ),
        evidence_comparison=(fact(comparison),),
        reconciliation=(fact(reconciliation),),
    )


def _aeat_app(surface_id: str, scenario: WorkbenchFixtureScenario) -> App[Any]:
    projection = _aeat_projection(scenario)
    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        projection,
        operation_contracts=_operation_contracts(),
    )
    zone = next(route[2] for route in _AEAT_ROUTES if route[0] == surface_id)
    if scenario is WorkbenchFixtureScenario.UNAVAILABLE:
        screen_type = next(route[1] for route in _AEAT_ROUTES if route[0] == surface_id)
        return _host(screen_type(controller))
    return _host(resolve_aeat_sync_screen(controller, controller.target(zone)))


_AEAT_ROUTES: Final[
    tuple[tuple[str, Callable[[AeatSyncWorkspaceController], Screen[Any]], AeatSyncWorkspaceZone], ...]
] = (
    ("aeat-sync-overview", AeatSyncOverviewScreen, AeatSyncWorkspaceZone.OVERVIEW),
    ("aeat-sync-census", AeatSyncCensusScreen, AeatSyncWorkspaceZone.CENSUS),
    ("aeat-sync-filed-declarations", AeatSyncFiledDeclarationsScreen, AeatSyncWorkspaceZone.FILED_DECLARATIONS),
    ("aeat-sync-notifications", AeatSyncNotificationsScreen, AeatSyncWorkspaceZone.NOTIFICATIONS),
    ("aeat-sync-evidence-comparison", AeatSyncEvidenceComparisonScreen, AeatSyncWorkspaceZone.EVIDENCE_COMPARISON),
    ("aeat-sync-reconciliation", AeatSyncReconciliationScreen, AeatSyncWorkspaceZone.RECONCILIATION),
)


def _declaration_observations(
    scenario: WorkbenchFixtureScenario,
) -> tuple[DeclarationsWorkspaceZoneObservationV1, ...]:
    availability = (
        DeclarationsWorkspaceAvailability.STALE
        if scenario is WorkbenchFixtureScenario.STALE
        else DeclarationsWorkspaceAvailability.UNAVAILABLE
        if scenario is WorkbenchFixtureScenario.UNAVAILABLE
        else DeclarationsWorkspaceAvailability.AVAILABLE
    )
    return tuple(
        DeclarationsWorkspaceZoneObservationV1(
            zone=zone,
            availability=availability,
            observed_at=_AT
            if availability
            in {
                DeclarationsWorkspaceAvailability.AVAILABLE,
                DeclarationsWorkspaceAvailability.STALE,
            }
            else None,
            reason_code=(
                None if availability is DeclarationsWorkspaceAvailability.AVAILABLE else "fixture.declarations.refused"
            ),
        )
        for zone in DeclarationsWorkspaceZone
    )


def _declaration_catalogues(
    scenario: WorkbenchFixtureScenario,
) -> tuple[
    WorkUnitCatalogue,
    CalculationRevisionCatalogue,
    ModeloRecordCatalogue,
    tuple[DeclarationsSanitizedLifecycleFactV1, ...],
]:
    if scenario in {WorkbenchFixtureScenario.EMPTY, WorkbenchFixtureScenario.UNAVAILABLE}:
        return WorkUnitCatalogue(), CalculationRevisionCatalogue(), ModeloRecordCatalogue(), ()
    period = Period.from_year_and_code(2026, "1T")
    casilla = validated_casilla_id("01")
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        revision_id="2026",
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={casilla: "1.00"},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="fixture",
    )
    unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        revision_id="2026",
        name="Fixture declaration",
        created_at=_AT,
        updated_at=_AT,
        current_calculation_revision_id=revision_id,
        filed_calculation_revision_id=revision_id,
        current_filing_record_id=filing_id,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        input_values_by_casilla_id={casilla: "1.00"},
        casilla_values={},
        created_at=_AT,
        updated_at=_AT,
        verified_at=_AT,
        verified_by="fixture",
        filed_at=_AT,
        filed_by="fixture",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    filing = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_BUCKET,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        filed_at=_AT,
        filed_by="fixture",
    )
    lifecycle = DeclarationsSanitizedLifecycleFactV1(
        fact_id="fixture.filed",
        work_unit_id=work_unit_id,
        occurred_at=_AT,
        kind=DeclarationsLifecycleKind.FILED,
    )
    return (
        WorkUnitCatalogue.from_work_units((unit,)),
        CalculationRevisionCatalogue(revisions={revision_id: revision}),
        ModeloRecordCatalogue(records={filing_id: filing}),
        (lifecycle,),
    )


def _declarations_projection(scenario: WorkbenchFixtureScenario) -> DeclarationsWorkspaceProjectionV1:
    work, revisions, filings, lifecycle = _declaration_catalogues(scenario)
    return project_declarations_workspace(
        bucket_id=_BUCKET,
        work_units=work,
        calculation_revisions=revisions,
        filing_records=filings,
        lifecycle_facts=lifecycle,
        zone_observations=_declaration_observations(scenario),
    )


def _calendar_projection(scenario: WorkbenchFixtureScenario) -> DeclarationsCalendarProjectionV1:
    unavailable = scenario is WorkbenchFixtureScenario.UNAVAILABLE
    stale = scenario is WorkbenchFixtureScenario.STALE
    availability = (
        HomeAvailability.STALE if stale else HomeAvailability.UNAVAILABLE if unavailable else HomeAvailability.AVAILABLE
    )
    state = HomeZoneState(
        availability=availability,
        observed_at=_AT if availability in {HomeAvailability.AVAILABLE, HomeAvailability.STALE} else None,
        reason_code=None if availability is HomeAvailability.AVAILABLE else "fixture.calendar.refused",
    )
    period = Period.from_year_and_code(2026, "1T")
    entries: tuple[OverviewCalendarEntry, ...] = ()
    if scenario not in {WorkbenchFixtureScenario.EMPTY, WorkbenchFixtureScenario.UNAVAILABLE}:
        entries = (
            OverviewCalendarEntry(
                modelo="130",
                filing_year=2026,
                period=period,
                opens_on=date(2026, 1, 1),
                closes_on=date(2026, 4, 30),
                adjusted_closes_on=date(2026, 4, 30),
                shift_reason="fixture",
                status=ObligationStatus.UPCOMING,
                user_state=OverviewPeriodState.DUE,
                filing_evidence=OverviewCalendarFilingEvidence(modelo="130", filing_year=2026, period=period),
            ),
        )
    calendar = OverviewCalendar(
        range=OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        entries=entries,
        generated_at=_AT,
    )
    evidence = CalendarEvidenceProjection(local_state=state, aeat_state=state, evidence=())
    return project_declarations_calendar(
        calendar=calendar,
        evidence=evidence,
        as_of=date(2026, 2, 1),
        schedule_observation=DeclarationsCalendarSourceObservationV1(
            source=DeclarationsCalendarSource.SCHEDULE,
            availability=availability,
            observed_at=_AT if availability in {HomeAvailability.AVAILABLE, HomeAvailability.STALE} else None,
            reason_code=None if availability is HomeAvailability.AVAILABLE else "fixture.calendar.refused",
        ),
    )


def _declaration_controller(scenario: WorkbenchFixtureScenario) -> DeclarationsWorkspaceController:
    projection = _declarations_projection(scenario)

    def action(action_id: str) -> ActionReference:
        return ActionReference(action_id=lookup_action(action_id).action_id)

    return DeclarationsWorkspaceController(
        TuiScreenContextV1(destination="workbench.declarations"),
        projection,
        work_action=action("operator.modelo.work.list"),
        revisions_action=action("operator.modelo.work.revisions"),
        filing_action=action("operator.modelo.filing_record.list"),
        calendar_projection=_calendar_projection(scenario),
    )


def _declaration_app(surface_id: str, scenario: WorkbenchFixtureScenario) -> App[Any]:
    controller = _declaration_controller(scenario)
    if surface_id == "declarations-calendar":
        target = controller.target("declarations.calendar")
        return _host(resolve_declarations_screen(controller, target))
    if surface_id == "declarations-modelo-launcher":
        return _host(DeclarationsModeloWorkspaceLauncherScreen(controller))
    if surface_id == "declarations-unavailable":
        return _host(resolve_declarations_screen(controller, controller.target("declarations.revisions")))
    destination = cast(
        DeclarationsDestinationIdV1,
        {
            "declarations-overview": "declarations.overview",
            "declarations-revisions": "declarations.revisions",
            "declarations-filing-history": "declarations.filing_history",
        }[surface_id],
    )
    return _host(resolve_declarations_screen(controller, controller.target(destination)))


@dataclass(frozen=True, slots=True)
class _FixtureObservationService:
    """Preloaded observation service implementing the public operation door."""

    result: OperationObservationSuccessV1

    async def observe(self, _request: OperationObservationRequestV1) -> OperationObservationSuccessV1:
        return self.result


@dataclass(frozen=True, slots=True)
class _FixtureOperationServices:
    """Minimal injected service family used by the real OperationController."""

    observation: _FixtureObservationService


def _operation_modal_app() -> App[Any]:
    contracts = _operation_contracts()
    contract = contracts.definitions[0]
    operation_id = cast(OperationId, "a" * 64)
    projection = OperationPublicProjectionV1(
        operation_id=operation_id,
        definition_id=contract.definition_id,
        subject_ref="fixture.subject",
        revision=0,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=contracts.contract_set_digest,
        lifecycle=OperationLifecycle.RUNNING,
        terminal_condition=None,
        effect=OperationEffect.NONE,
        phase_code=None,
        started_at=_AT,
        updated_at=_AT,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None,
        refusal_ref=None,
        diagnostic_ref=None,
    )
    page = OperationPublicEventPageV1(
        operation_id=operation_id,
        anchor_cursor=0,
        requested_cursor=0,
        status=OperationReplayStatus.CAUGHT_UP,
        events=(),
        next_cursor=0,
        restart_cursor=None,
    )
    observation = OperationObservationSuccessV1(projection=projection, event_page=page)
    submission = OperationSubmission(
        receipt=OperationSubmissionReceiptV1(operation_id=operation_id, secret_requirement=None),
        response_capability=cast(Any, object()),
    )
    controller = OperationController(
        services=cast(OperationComposedServices, _FixtureOperationServices(_FixtureObservationService(observation))),
        submission=submission,
        actor_ref=cast(OperationActorReference, "fixture:operator"),
    )
    return _host(OperationModal(controller))


def _root_app(scenario: WorkbenchFixtureScenario) -> App[Any]:
    home_projection = _home_projection(scenario)

    def home_factory(_context: TuiScreenContextV1) -> Screen[None]:
        return HomeScreen(home_projection)

    admissions = {
        "workbench.home": TuiDestinationAdmissionV1(
            destination="workbench.home", state=WorkbenchDestinationAdmissionState.AVAILABLE
        ),
        "workbench.ledger": TuiDestinationAdmissionV1(
            destination="workbench.ledger",
            state=WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
            reason_code="fixture.root.unavailable",
        ),
        "workbench.declarations": TuiDestinationAdmissionV1(
            destination="workbench.declarations",
            state=WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
            reason_code="fixture.root.unavailable",
        ),
        "workbench.aeat_sync": TuiDestinationAdmissionV1(
            destination="workbench.aeat_sync",
            state=WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
            reason_code="fixture.root.unavailable",
        ),
        "workbench.profile": TuiDestinationAdmissionV1(
            destination="workbench.profile",
            state=WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
            reason_code="fixture.root.unavailable",
        ),
    }
    catalogue = build_destination_catalogue(admissions=admissions, factories={"workbench.home": home_factory})
    return CadrumoTuiApp(
        services=cast(OperationComposedServices, object()),
        destination_catalogue=catalogue,
        refresh_home=lambda: home_projection,
    )


def _home_projection(scenario: WorkbenchFixtureScenario) -> Any:
    from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture

    mapping = {
        WorkbenchFixtureScenario.READY: HomeFixtureScenario.READY,
        WorkbenchFixtureScenario.EMPTY: HomeFixtureScenario.EMPTY,
        WorkbenchFixtureScenario.STALE: HomeFixtureScenario.STALE,
        WorkbenchFixtureScenario.UNAVAILABLE: HomeFixtureScenario.UNAVAILABLE,
        WorkbenchFixtureScenario.BLOCKED: HomeFixtureScenario.BLOCKED,
        WorkbenchFixtureScenario.REFUSAL: HomeFixtureScenario.UNAVAILABLE,
        WorkbenchFixtureScenario.FAILURE: HomeFixtureScenario.UNAVAILABLE,
    }
    return build_home_projection_fixture(mapping[scenario])


def _spec(
    surface_id: str,
    scenario: WorkbenchFixtureScenario,
    interfaces: tuple[str, ...],
    build: FixtureBuilder,
) -> WorkbenchFixtureSpec:
    return WorkbenchFixtureSpec(
        surface_id=surface_id,
        scenario=scenario,
        interfaces=interfaces,
        build=build,
        metadata=(
            ("source", "application projection"),
            ("composition", "production screen"),
        ),
    )


_HOME_INTERFACE = ("cadrumo.entrypoints.tui.home.HomeScreen",)
_ROOT_INTERFACE = ("cadrumo.entrypoints.tui.app.CadrumoTuiApp",)
_DECLARATION_INTERFACES = {
    "declarations-overview": ("cadrumo.entrypoints.tui.declarations.overview.DeclarationsOverviewScreen",),
    "declarations-calendar": ("cadrumo.entrypoints.tui.declarations.calendar.DeclarationsCalendarScreen",),
    "declarations-revisions": ("cadrumo.entrypoints.tui.declarations.revisions.DeclarationsRevisionsScreen",),
    "declarations-filing-history": (
        "cadrumo.entrypoints.tui.declarations.filing_history.DeclarationsFilingHistoryScreen",
    ),
    "declarations-modelo-launcher": (
        "cadrumo.entrypoints.tui.declarations.overview.DeclarationsModeloWorkspaceLauncherScreen",
    ),
}
_AEAT_INTERFACE_BY_SURFACE = {
    surface: (screen.__module__ + "." + screen.__name__,) for surface, screen, _zone in _AEAT_ROUTES
}



_LEDGER_TX_A: Final[str] = "a" * 64
_LEDGER_TX_B: Final[str] = "b" * 64

_LEDGER_AREA_COUNTS: Final[dict[str, int]] = {
    "overview": 3,
    "entries": 2,
    "review": 2,
    "import": 0,
    "classification": 2,
    "evidence": 0,
    "reconciliation": 0,
}
"""Item counts per area for the populated reading, keyed by area value."""


def _ledger_area_state(
    area: object,
    scenario: WorkbenchFixtureScenario,
) -> object:
    """Describe one Ledger area under the shared scenario vocabulary."""
    from ....application.ledger.workspace import (
        LedgerWorkspaceAreaStateV1,
        LedgerWorkspaceAvailability,
        LedgerWorkspaceSource,
        LedgerWorkspaceStatus,
    )

    populated = scenario in {WorkbenchFixtureScenario.READY, WorkbenchFixtureScenario.STALE}
    availability = {
        WorkbenchFixtureScenario.READY: LedgerWorkspaceAvailability.AVAILABLE,
        WorkbenchFixtureScenario.EMPTY: LedgerWorkspaceAvailability.AVAILABLE,
        WorkbenchFixtureScenario.STALE: LedgerWorkspaceAvailability.STALE,
        WorkbenchFixtureScenario.UNAVAILABLE: LedgerWorkspaceAvailability.UNAVAILABLE,
    }[scenario]
    reason = {
        WorkbenchFixtureScenario.STALE: "ledger.snapshot_stale",
        WorkbenchFixtureScenario.UNAVAILABLE: "ledger.source_unavailable",
    }.get(scenario)
    deferred = area.value in {"import", "evidence", "reconciliation"}
    return LedgerWorkspaceAreaStateV1(
        area=area,
        sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
        availability=availability,
        reason_code=reason,
        status=(
            LedgerWorkspaceStatus.UNMEASURED
            if deferred or not populated
            else LedgerWorkspaceStatus.NEEDS_ATTENTION
        ),
        item_count=_LEDGER_AREA_COUNTS[area.value] if populated else 0,
    )


def _ledger_projection(scenario: WorkbenchFixtureScenario) -> object:
    """Build one immutable, non-sensitive Ledger workspace reading.

    The refs carry synthetic transaction identities and no monetary value,
    counterparty, or evidence payload: a review surface must be legible
    without ever holding a real operator's ledger.
    """
    from ....application.ledger.workspace import (
        LedgerWorkspaceArea,
        LedgerWorkspaceEntryRefV1,
        LedgerWorkspaceProjectionV1,
    )

    populated = scenario in {WorkbenchFixtureScenario.READY, WorkbenchFixtureScenario.STALE}
    entries = (
        (
            LedgerWorkspaceEntryRefV1(transaction_id=_LEDGER_TX_A, review_status="pending"),
            LedgerWorkspaceEntryRefV1(transaction_id=_LEDGER_TX_B, review_status="reviewed"),
        )
        if populated
        else ()
    )
    return LedgerWorkspaceProjectionV1(
        bucket_id=_BUCKET,
        areas=tuple(_ledger_area_state(area, scenario) for area in LedgerWorkspaceArea),
        entries=entries,
        review_transaction_ids=tuple(entry.transaction_id for entry in entries),
        invoice_reconciliations=(),
        link_inconsistencies=(),
        affected_declarations=(),
    )


def _ledger_controller(scenario: WorkbenchFixtureScenario) -> object:
    from ....application.operator_actions.catalogue import lookup_action
    from ....application.operator_actions.models import ActionReference
    from ..ledger.controller import LedgerWorkspaceController

    return LedgerWorkspaceController(
        TuiScreenContextV1(destination="workbench.ledger"),
        _ledger_projection(scenario),
        review_action=ActionReference(action_id=lookup_action("operator.ledger.review").action_id),
    )


def _ledger_app(surface_id: str, scenario: WorkbenchFixtureScenario) -> App[Any]:
    """Open one Ledger area the way its own route resolves it.

    An UNAVAILABLE area resolves to the refusal screen rather than the area
    body, which is the product's real behaviour; the area screens are still
    reachable in that state by constructing them directly, so a reviewer can
    see both what the refusal says and what the body would have shown.
    """
    from ..ledger.routes import resolve_ledger_screen

    controller = _ledger_controller(scenario)
    if surface_id == "ledger-unavailable":
        refused = _ledger_controller(WorkbenchFixtureScenario.UNAVAILABLE)
        area = _LEDGER_ROUTES[0][2]
        return _host(resolve_ledger_screen(refused, refused.route_target(area)))
    screen_type = next(route[1] for route in _LEDGER_ROUTES if route[0] == surface_id)
    if scenario is WorkbenchFixtureScenario.UNAVAILABLE:
        return _host(screen_type(controller))
    area = next(route[2] for route in _LEDGER_ROUTES if route[0] == surface_id)
    return _host(resolve_ledger_screen(controller, controller.route_target(area)))


def _ledger_routes() -> tuple[tuple[str, Any, Any], ...]:
    from ....application.ledger.workspace import LedgerWorkspaceArea
    from ..ledger.classification import LedgerClassificationScreen
    from ..ledger.entries import LedgerEntriesScreen
    from ..ledger.evidence import LedgerEvidenceScreen
    from ..ledger.import_flow import LedgerImportScreen
    from ..ledger.overview import LedgerOverviewScreen
    from ..ledger.reconciliation import LedgerReconciliationScreen
    from ..ledger.review import LedgerReviewScreen

    return (
        ("ledger-overview", LedgerOverviewScreen, LedgerWorkspaceArea.OVERVIEW),
        ("ledger-entries", LedgerEntriesScreen, LedgerWorkspaceArea.ENTRIES),
        ("ledger-review", LedgerReviewScreen, LedgerWorkspaceArea.REVIEW),
        ("ledger-import", LedgerImportScreen, LedgerWorkspaceArea.IMPORT),
        ("ledger-classification", LedgerClassificationScreen, LedgerWorkspaceArea.CLASSIFICATION),
        ("ledger-evidence", LedgerEvidenceScreen, LedgerWorkspaceArea.EVIDENCE),
        ("ledger-reconciliation", LedgerReconciliationScreen, LedgerWorkspaceArea.RECONCILIATION),
    )


_LEDGER_ROUTES: Final[tuple[tuple[str, Any, Any], ...]] = _ledger_routes()

_LEDGER_INTERFACE_BY_SURFACE: Final[dict[str, tuple[str, ...]]] = {
    "ledger-overview": ("cadrumo.entrypoints.tui.ledger.overview.LedgerOverviewScreen",),
    "ledger-entries": ("cadrumo.entrypoints.tui.ledger.entries.LedgerEntriesScreen",),
    "ledger-review": ("cadrumo.entrypoints.tui.ledger.review.LedgerReviewScreen",),
    "ledger-import": ("cadrumo.entrypoints.tui.ledger.import_flow.LedgerImportScreen",),
    "ledger-classification": ("cadrumo.entrypoints.tui.ledger.classification.LedgerClassificationScreen",),
    "ledger-evidence": ("cadrumo.entrypoints.tui.ledger.evidence.LedgerEvidenceScreen",),
    "ledger-reconciliation": ("cadrumo.entrypoints.tui.ledger.reconciliation.LedgerReconciliationScreen",),
    "ledger-unavailable": ("cadrumo.entrypoints.tui.ledger.routes.LedgerUnavailableScreen",),
}


def _build_specs() -> tuple[WorkbenchFixtureSpec, ...]:
    specs: list[WorkbenchFixtureSpec] = []
    for scenario in (
        WorkbenchFixtureScenario.READY,
        WorkbenchFixtureScenario.EMPTY,
        WorkbenchFixtureScenario.STALE,
        WorkbenchFixtureScenario.UNAVAILABLE,
        WorkbenchFixtureScenario.BLOCKED,
    ):
        specs.append(_spec("home", scenario, _HOME_INTERFACE, lambda scenario=scenario: _home(scenario)))
    specs.extend(
        _spec("workbench-root", scenario, _ROOT_INTERFACE, lambda scenario=scenario: _root_app(scenario))
        for scenario in (
            WorkbenchFixtureScenario.READY,
            WorkbenchFixtureScenario.EMPTY,
            WorkbenchFixtureScenario.UNAVAILABLE,
        )
    )
    for surface_id, interfaces in _DECLARATION_INTERFACES.items():
        scenarios = (
            (WorkbenchFixtureScenario.REFUSAL,)
            if surface_id == "declarations-modelo-launcher"
            else (
                WorkbenchFixtureScenario.READY,
                WorkbenchFixtureScenario.EMPTY,
                WorkbenchFixtureScenario.STALE,
                WorkbenchFixtureScenario.UNAVAILABLE,
            )
        )
        specs.extend(
            _spec(
                surface_id,
                scenario,
                interfaces,
                lambda surface_id=surface_id, scenario=scenario: _declaration_app(surface_id, scenario),
            )
            for scenario in scenarios
        )
    specs.append(
        _spec(
            "declarations-unavailable",
            WorkbenchFixtureScenario.UNAVAILABLE,
            ("cadrumo.entrypoints.tui.declarations.routes.DeclarationsUnavailableScreen",),
            lambda: _declaration_app("declarations-unavailable", WorkbenchFixtureScenario.UNAVAILABLE),
        )
    )
    for surface_id, interfaces in _AEAT_INTERFACE_BY_SURFACE.items():
        scenarios = (
            WorkbenchFixtureScenario.READY,
            WorkbenchFixtureScenario.EMPTY,
            WorkbenchFixtureScenario.STALE,
            WorkbenchFixtureScenario.UNAVAILABLE,
        )
        if surface_id == "aeat-sync-overview":
            scenarios += (WorkbenchFixtureScenario.BLOCKED, WorkbenchFixtureScenario.FAILURE)
        if surface_id == "aeat-sync-notifications":
            scenarios += (WorkbenchFixtureScenario.REFUSAL,)
        specs.extend(
            _spec(
                surface_id,
                scenario,
                interfaces,
                lambda surface_id=surface_id, scenario=scenario: _aeat_app(surface_id, scenario),
            )
            for scenario in scenarios
        )
    specs.append(
        _spec(
            "operation-modal",
            WorkbenchFixtureScenario.READY,
            ("cadrumo.entrypoints.tui.operations.modal.OperationModal",),
            _operation_modal_app,
        )
    )
    specs.extend(
        _spec(
            surface_id,
            scenario,
            _LEDGER_INTERFACE_BY_SURFACE[surface_id],
            lambda surface_id=surface_id, scenario=scenario: _ledger_app(surface_id, scenario),
        )
        for surface_id, _screen, _area in _LEDGER_ROUTES
        for scenario in (
            WorkbenchFixtureScenario.READY,
            WorkbenchFixtureScenario.EMPTY,
            WorkbenchFixtureScenario.STALE,
            WorkbenchFixtureScenario.UNAVAILABLE,
        )
    )
    specs.append(
        _spec(
            "ledger-unavailable",
            WorkbenchFixtureScenario.UNAVAILABLE,
            _LEDGER_INTERFACE_BY_SURFACE["ledger-unavailable"],
            lambda: _ledger_app("ledger-unavailable", WorkbenchFixtureScenario.UNAVAILABLE),
        )
    )
    return tuple(sorted(specs, key=lambda spec: spec.fixture_id))



WORKBENCH_FIXTURES: Final[tuple[WorkbenchFixtureSpec, ...]] = _build_specs()


def resolve_workbench_fixture(fixture_id: str) -> WorkbenchFixtureSpec:
    """Resolve one exact fixture identity or fail with the accepted set."""
    matches = tuple(spec for spec in WORKBENCH_FIXTURES if spec.fixture_id == fixture_id)
    if len(matches) != 1:
        accepted = ", ".join(spec.fixture_id for spec in WORKBENCH_FIXTURES)
        raise KeyError(f"unknown workbench fixture {fixture_id!r}; accepted: {accepted}")
    return matches[0]


__all__ = [
    "WORKBENCH_FIXTURES",
    "WorkbenchFixtureScenario",
    "WorkbenchFixtureSpec",
    "resolve_workbench_fixture",
]
