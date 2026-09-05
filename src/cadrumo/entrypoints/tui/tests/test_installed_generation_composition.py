"""Production composition proofs for one child-owned workbench generation."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest

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
from ....application.operations.composition import OperationComposedServices
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
from ....application.user_profile.login_interaction import ProfileLoginAttempt, ProfileLoginChoice
from ....application.user_profile.overview import ProfileOverview
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
from ..declarations.calendar import DeclarationsCalendarScreen
from ..declarations.controller import DeclarationsWorkspaceScreen
from ..declarations.routes import resolve_declarations_screen
from ..launcher import (
    InstalledWorkbenchAccountInputsV1,
    InstalledWorkbenchFactoryDependenciesV1,
    TuiOperationCompositionV1,
    compose_installed_workbench_generation_provider,
    compose_installed_workbench_root,
)
from ..navigation import TuiScreenContextV1
from ..profile.overview import ProfileManagerScreen
from ..secret.login import LoginScreen
from ..secret.passphrase import PassphraseScreen

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


def _aeat_sync_projection(at: datetime) -> AeatSyncWorkspaceProjectionV1:
    """A real pre-pull AEAT Sync reading, built by its own production reader."""
    from ....application.aeat_sync.workspace_reader import read_local_aeat_sync_workspace_projection

    return read_local_aeat_sync_workspace_projection(
        bucket_id=_BUCKET,
        subject_key="00000001R",
        observed_at=at,
        filings=(),
        operation_contracts=_operation_runtime().public_contracts,
    )


def _inputs(at: datetime, *, aeat_sync_available: bool = False) -> WorkbenchGenerationInputsV1:
    """One generation. ``aeat_sync_available`` models a declared NIF."""
    return WorkbenchGenerationInputsV1(
        assembled_at=at,
        home=WorkbenchGenerationSourceResultV1.available(_home(at), observed_at=at),
        ledger=WorkbenchGenerationSourceResultV1.available(_ledger(), observed_at=at),
        declarations=WorkbenchGenerationSourceResultV1.available(_declarations(at), observed_at=at),
        declarations_calendar=WorkbenchGenerationSourceResultV1.available(_calendar(at), observed_at=at),
        aeat_sync=(
            WorkbenchGenerationSourceResultV1[AeatSyncWorkspaceProjectionV1].available(
                _aeat_sync_projection(at), observed_at=at
            )
            if aeat_sync_available
            else WorkbenchGenerationSourceResultV1[AeatSyncWorkspaceProjectionV1].never_captured(
                refusal="source.aeat_sync.not_captured"
            )
        ),
        modelo=WorkbenchGenerationSourceResultV1[tuple[ModeloWorkspaceProjectionV1, ...]].never_captured(
            refusal="source.modelo.bulk_projection_unavailable"
        ),
        ledger_admission=_admission("workbench.ledger", WorkbenchDestinationAdmissionState.AVAILABLE),
        declarations_admission=_admission("workbench.declarations", WorkbenchDestinationAdmissionState.AVAILABLE),
        aeat_sync_admission=_admission(
            "workbench.aeat_sync",
            WorkbenchDestinationAdmissionState.AVAILABLE
            if aeat_sync_available
            else WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
        ),
    )


def _action(action_id: str) -> ActionReference:
    return ActionReference(action_id=lookup_action(action_id).action_id)


def _account_inputs(
    *,
    profile_id: str = _BUCKET,
    overview_profile_id: str = _BUCKET,
    label: str = "Synthetic profile",
    choice_label: str = "Synthetic profile",
) -> InstalledWorkbenchAccountInputsV1:
    def persist(_path: str, _value: str) -> ProfileOverview:
        raise AssertionError("profile persistence must not run while composing the workbench")

    def authenticate(_profile_id: str, _password: str) -> ProfileLoginAttempt:
        raise AssertionError("authentication must not run while composing the workbench")

    def assess(_password: str):
        raise AssertionError("password assessment must not run while composing the workbench")

    def rotate(_current: str, _replacement: str, _confirmation: str):
        raise AssertionError("password rotation must not run while composing the workbench")

    return InstalledWorkbenchAccountInputsV1(
        profile_id=profile_id,
        profile_overview=cast(
            "ProfileOverview",
            SimpleNamespace(profile_id=overview_profile_id, label=label),
        ),
        persist_profile_field=persist,
        login_choices=(ProfileLoginChoice(profile_id=profile_id, label=choice_label),),
        authenticate=authenticate,
        assess_password=assess,
        rotate_password=rotate,
    )


def _dependencies() -> InstalledWorkbenchFactoryDependenciesV1:
    return InstalledWorkbenchFactoryDependenciesV1(
        account=_account_inputs(),
        profile_admission=_admission("workbench.profile", WorkbenchDestinationAdmissionState.AVAILABLE),
        ledger_review_action=_action("operator.ledger.review"),
        ledger_evidence_action=_action("operator.ledger.evidence.review.list"),
        ledger_classify_action=_action("operator.ledger.classify"),
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


def test_generation_provider_keeps_modelo_navigation_unavailable_without_a_captured_workspace_projection() -> None:
    """The installed factory never creates a second read or treats no capture as empty work."""
    provider = InstalledWorkbenchGenerationProviderV1(CallableWorkbenchGenerationReadDoorV1(lambda: _inputs(_NOW)))
    root_inputs = compose_installed_workbench_generation_provider(provider, _dependencies())(_operation_runtime())
    root = compose_installed_workbench_root(root_inputs)
    route = root.destination_catalogue.resolve("workbench.declarations")
    assert route.factory is not None

    declarations = route.factory(TuiScreenContextV1(destination="workbench.declarations"))

    assert isinstance(declarations, DeclarationsWorkspaceScreen)
    assert declarations.controller.modelo_workspace_factory is None


def test_generation_provider_composes_the_real_account_screen_owners_without_effects() -> None:
    """The installed root receives real account doors, not a test-only placeholder."""
    provider = InstalledWorkbenchGenerationProviderV1(CallableWorkbenchGenerationReadDoorV1(lambda: _inputs(_NOW)))
    root_inputs = compose_installed_workbench_generation_provider(provider, _dependencies())(_operation_runtime())
    context = TuiScreenContextV1(destination="workbench.profile")

    assert isinstance(root_inputs.account_factories.profile(context), ProfileManagerScreen)
    assert isinstance(root_inputs.account_factories.change_user(), LoginScreen)
    assert isinstance(root_inputs.account_factories.password(), PassphraseScreen)


@pytest.mark.parametrize(
    ("overview_profile_id", "choice_label"),
    [
        ("22222222-2222-4222-8222-222222222222", "Synthetic profile"),
        (_BUCKET, "Different profile"),
    ],
)
def test_account_composition_refuses_stale_profile_identity_or_label(
    overview_profile_id: str,
    choice_label: str,
) -> None:
    """A root cannot render one account while an account door targets another."""
    with pytest.raises(ValueError, match="authenticated profile"):
        _account_inputs(overview_profile_id=overview_profile_id, choice_label=choice_label)


def test_generation_factory_receives_exact_session_operation_contract_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AEAT Sync authority comes from the active service graph, not dependencies."""
    captured: list[OperationPublicContractSetV1] = []

    def capture_contracts(
        _current: list[object],
        _dependencies: InstalledWorkbenchFactoryDependenciesV1,
        contracts: OperationPublicContractSetV1,
    ) -> None:
        captured.append(contracts)

    monkeypatch.setattr(
        "cadrumo.entrypoints.tui.launcher._aeat_sync_generation_factory",
        capture_contracts,
    )
    runtime = _operation_runtime()
    provider = InstalledWorkbenchGenerationProviderV1(CallableWorkbenchGenerationReadDoorV1(lambda: _inputs(_NOW)))

    compose_installed_workbench_generation_provider(provider, _dependencies())(runtime)

    assert captured == [runtime.public_contracts]
    assert captured[0] is runtime.services.public_contracts


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


def test_a_generation_that_gains_a_source_readmits_its_destination() -> None:
    """Availability belongs to the CURRENT capture, not to the session's first.

    An operator who declares their NIF part-way through a session makes AEAT
    Sync readable. Before this, admissions were frozen at composition while the
    factories resolved from the latest generation, so the refreshed capture and
    the catalogue disagreed: search was refused for the rest of the session and
    navigation kept advertising a reader-unavailable reason that had stopped
    being true.
    """
    generations = [_inputs(_NOW), _inputs(_NOW, aeat_sync_available=True)]

    def read() -> WorkbenchGenerationInputsV1:
        return generations.pop(0) if len(generations) > 1 else generations[0]

    provider = InstalledWorkbenchGenerationProviderV1(CallableWorkbenchGenerationReadDoorV1(read))
    root_inputs = compose_installed_workbench_generation_provider(provider, _dependencies())(_operation_runtime())
    root = compose_installed_workbench_root(root_inputs)

    assert root.destination_catalogue.resolve("workbench.aeat_sync").factory is None
    assert root.refresh_destination_catalogue is not None

    root.refresh_search_inputs()
    refreshed = root.refresh_destination_catalogue()

    route = refreshed.resolve("workbench.aeat_sync")
    assert route.admission.state is WorkbenchDestinationAdmissionState.AVAILABLE
    assert route.factory is not None


def test_a_generation_that_loses_a_source_stops_offering_its_destination() -> None:
    """The other direction, which used to crash rather than refuse.

    Clearing a declared NIF is a supported profile edit. The catalogue kept
    listing AEAT Sync with a live factory that then raised out of a Textual
    handler when the operator selected it from the palette.
    """
    generations = [_inputs(_NOW, aeat_sync_available=True), _inputs(_NOW)]

    def read() -> WorkbenchGenerationInputsV1:
        return generations.pop(0) if len(generations) > 1 else generations[0]

    provider = InstalledWorkbenchGenerationProviderV1(CallableWorkbenchGenerationReadDoorV1(read))
    root_inputs = compose_installed_workbench_generation_provider(provider, _dependencies())(_operation_runtime())
    root = compose_installed_workbench_root(root_inputs)

    assert root.destination_catalogue.resolve("workbench.aeat_sync").factory is not None
    assert root.refresh_destination_catalogue is not None

    root.refresh_search_inputs()
    refreshed = root.refresh_destination_catalogue()

    route = refreshed.resolve("workbench.aeat_sync")
    assert route.admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE
    assert route.factory is None
