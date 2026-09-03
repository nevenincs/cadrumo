"""Production composition proofs for one child-owned workbench generation."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from textual.screen import Screen

from ....application.aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from ....application.ledger.models import LedgerReviewQueryResult, LedgerStatusReport
from ....application.ledger.workspace import LedgerWorkspaceProjectionV1, project_ledger_workspace
from ....application.modelo.declarations_calendar import (
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceObservationV1,
    project_declarations_calendar,
)
from ....application.modelo.declarations_workspace import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
    project_declarations_workspace,
)
from ....application.modelo.workspace_models import ModeloWorkspaceProjectionV1
from ....application.operations.registry import OperationPublicContractSetV1
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_actions.models import ActionReference
from ....application.overview.calendar_models import OverviewCalendar, OverviewCalendarRange
from ....application.overview.evidence import CalendarEvidenceProjection
from ....application.overview.home import (
    HomeAccountSession,
    HomeAvailability,
    HomeProjectionInput,
    HomeSessionPosture,
    HomeZoneState,
)
from ....application.search.workbench import (
    WorkbenchDestinationAdmission,
    WorkbenchDestinationAdmissionState,
)
from ....application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION,
    build_censal_operation_registration,
)
from ....application.workbench_generation import (
    CallableWorkbenchGenerationReadDoorV1,
    InstalledWorkbenchGenerationProviderV1,
    WorkbenchGenerationInputsV1,
    WorkbenchGenerationSourceResultV1,
)
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.filing_record import ModeloRecordCatalogue
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ....domain.transactions.models import TransactionCatalogue
from ..account import AccountFactoriesV1
from ..declarations.calendar import DeclarationsCalendarScreen
from ..declarations.controller import DeclarationsWorkspaceScreen
from ..declarations.routes import resolve_declarations_screen
from ..launcher import (
    InstalledWorkbenchFactoryDependenciesV1,
    TuiOperationCompositionV1,
    compose_installed_workbench_generation_provider,
    compose_installed_workbench_root,
)
from ..navigation import TuiScreenContextV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET = "11111111-1111-4111-8111-111111111111"
_NOW = datetime(2026, 9, 3, 10, tzinfo=UTC)


def _zone(name: str) -> HomeZoneState:
    return HomeZoneState(availability=HomeAvailability.NEVER_CAPTURED, reason_code=f"source.{name}")


def _home(at: datetime) -> HomeProjectionInput:
    return HomeProjectionInput(
        generated_at=at,
        account=HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Synthetic profile"),
        actions_state=_zone("actions"),
        declarations_state=_zone("declarations"),
        ledger_state=_zone("ledger"),
        agenda_state=_zone("agenda"),
        agenda_evidence_state=_zone("agenda_evidence"),
        messages_state=_zone("messages"),
    )


def _ledger() -> LedgerWorkspaceProjectionV1:
    return project_ledger_workspace(
        summary=LedgerStatusReport(
            bucket_id=_BUCKET,
            total_count=0,
            active_count=0,
            archived_count=0,
            stashed_count=0,
            pending_review_count=0,
            reviewed_count=0,
            skipped_count=0,
        ),
        preflight=None,
        review=LedgerReviewQueryResult(bucket_id=_BUCKET, rows=()),
        transactions=TransactionCatalogue(),
        invoices=InvoiceCatalogue(),
        revisions={},
        work_units=WorkUnitCatalogue(),
    )


def _declarations(at: datetime) -> DeclarationsWorkspaceProjectionV1:
    observations = tuple(
        DeclarationsWorkspaceZoneObservationV1(
            zone=zone,
            availability=DeclarationsWorkspaceAvailability.AVAILABLE,
            observed_at=at,
        )
        for zone in DeclarationsWorkspaceZone
    )
    return project_declarations_workspace(
        bucket_id=_BUCKET,
        work_units=WorkUnitCatalogue(),
        calculation_revisions=CalculationRevisionCatalogue(),
        filing_records=ModeloRecordCatalogue(),
        lifecycle_facts=(),
        zone_observations=observations,
    )


def _calendar(at: datetime) -> DeclarationsCalendarProjectionV1:
    available = HomeZoneState(availability=HomeAvailability.AVAILABLE)
    return project_declarations_calendar(
        calendar=OverviewCalendar(
            range=OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
            entries=(),
            generated_at=at,
        ),
        evidence=CalendarEvidenceProjection(local_state=available, aeat_state=available),
        as_of=date(2026, 9, 3),
        schedule_observation=DeclarationsCalendarSourceObservationV1(
            source=DeclarationsCalendarSource.SCHEDULE,
            availability=HomeAvailability.AVAILABLE,
        ),
    )


def _admission(destination: str, state: WorkbenchDestinationAdmissionState) -> WorkbenchDestinationAdmission:
    return WorkbenchDestinationAdmission(
        destination=destination,
        state=state,
        reason_code=None if state is WorkbenchDestinationAdmissionState.AVAILABLE else f"{destination}.not_captured",
    )


def _inputs(at: datetime) -> WorkbenchGenerationInputsV1:
    return WorkbenchGenerationInputsV1(
        assembled_at=at,
        home=WorkbenchGenerationSourceResultV1.available(_home(at), observed_at=at),
        ledger=WorkbenchGenerationSourceResultV1.available(_ledger(), observed_at=at),
        declarations=WorkbenchGenerationSourceResultV1.available(_declarations(at), observed_at=at),
        declarations_calendar=WorkbenchGenerationSourceResultV1.available(_calendar(at), observed_at=at),
        aeat_sync=WorkbenchGenerationSourceResultV1[AeatSyncWorkspaceProjectionV1].never_captured(
            refusal="source.aeat_sync.not_captured"
        ),
        modelo=WorkbenchGenerationSourceResultV1[tuple[ModeloWorkspaceProjectionV1, ...]].never_captured(
            refusal="source.modelo.bulk_projection_unavailable"
        ),
        ledger_admission=_admission("workbench.ledger", WorkbenchDestinationAdmissionState.AVAILABLE),
        declarations_admission=_admission("workbench.declarations", WorkbenchDestinationAdmissionState.AVAILABLE),
        aeat_sync_admission=_admission("workbench.aeat_sync", WorkbenchDestinationAdmissionState.NEVER_CAPTURED),
    )


def _action(action_id: str) -> ActionReference:
    return ActionReference(action_id=lookup_action(action_id).action_id)


def _dependencies() -> InstalledWorkbenchFactoryDependenciesV1:
    def profile(_: TuiScreenContextV1) -> Screen[None]:
        return Screen()

    return InstalledWorkbenchFactoryDependenciesV1(
        account_factories=cast("AccountFactoriesV1", SimpleNamespace(profile=profile)),
        profile_admission=_admission("workbench.profile", WorkbenchDestinationAdmissionState.AVAILABLE),
        ledger_review_action=_action("operator.ledger.review"),
        declarations_work_action=_action("operator.modelo.work.list"),
        declarations_revisions_action=_action("operator.modelo.work.revisions"),
        declarations_filing_action=_action("operator.modelo.filing_record.list"),
    )


def _operation_runtime() -> TuiOperationCompositionV1:
    contracts = OperationPublicContractSetV1.build(
        (build_censal_operation_registration(CENSAL_OPERATION_DEFINITION).contract,)
    )
    services = cast("OperationComposedServices", SimpleNamespace(public_contracts=contracts))
    return TuiOperationCompositionV1(services=services, public_contracts=contracts)


def test_generation_provider_binds_real_declarations_factory_and_calendar_projection() -> None:
    """The installed Declarations route reaches the application-built calendar."""

    provider = InstalledWorkbenchGenerationProviderV1(CallableWorkbenchGenerationReadDoorV1(lambda: _inputs(_NOW)))
    root_inputs = compose_installed_workbench_generation_provider(provider, _dependencies())(_operation_runtime())
    root = compose_installed_workbench_root(root_inputs)

    route = root.destination_catalogue.resolve("workbench.declarations")
    assert route.factory is not None
    declarations = route.factory(TuiScreenContextV1(destination="workbench.declarations"))
    assert isinstance(declarations, DeclarationsWorkspaceScreen)
    assert declarations.controller.calendar_projection is not None
    target = declarations.controller.target("declarations.calendar")
    assert isinstance(resolve_declarations_screen(declarations.controller, target), DeclarationsCalendarScreen)


def test_available_declarations_admission_requires_calendar_projection() -> None:
    """The admitted Declarations route cannot silently omit its calendar child."""
    payload = _inputs(_NOW).model_dump()
    payload["declarations"]["value"]["bucket_id"] = _BUCKET
    payload["declarations_calendar"] = (
        WorkbenchGenerationSourceResultV1[DeclarationsCalendarProjectionV1]
        .unavailable(refusal="workbench.calendar.reader_unavailable")
        .model_dump()
    )

    with pytest.raises(ValueError, match="requires its calendar projection"):
        WorkbenchGenerationInputsV1.model_validate(payload)


def test_refresh_reuses_one_generation_for_search_then_home_and_keeps_missing_sources_explicit() -> None:
    """A child return captures once; unavailable sources never become empty fixtures."""
    captures = [_inputs(_NOW), _inputs(_NOW + timedelta(minutes=1))]
    calls = 0

    def read() -> WorkbenchGenerationInputsV1:
        nonlocal calls
        value = captures[calls]
        calls += 1
        return value

    provider = InstalledWorkbenchGenerationProviderV1(CallableWorkbenchGenerationReadDoorV1(read))
    root_inputs = compose_installed_workbench_generation_provider(provider, _dependencies())(_operation_runtime())

    assert calls == 1
    assert root_inputs.search_inputs is None
    assert root_inputs.admissions["workbench.aeat_sync"].state is WorkbenchDestinationAdmissionState.NEVER_CAPTURED
    assert root_inputs.aeat_sync_factory is None
    assert root_inputs.refresh_search_inputs() is None
    refreshed_home = root_inputs.refresh_home()
    assert calls == 2
    assert refreshed_home.generated_at == _NOW + timedelta(minutes=1)
