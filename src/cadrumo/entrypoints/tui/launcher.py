"""Concrete runtime composition for installed and diagnostic TUI sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...application.ledger.models import (
        LedgerSourceImportCommand,
        LedgerSourceImportResult,
        ManualLedgerTransactionResult,
    )
    from ...core.period import Period
    from .ledger.models import (
        LedgerClassificationSubmissionV1,
        LedgerClassificationSubmitterV1,
        LedgerImportSubmitterV1,
    )

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator, Iterable, Mapping, Sequence
from contextlib import ExitStack, asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ...application.search.installed_workbench import InstalledWorkbenchSearchInputsV1
from ...application.search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from ...application.workbench_generation import (
    WorkbenchGenerationAvailability,
    WorkbenchGenerationProjectionResultV1,
    WorkbenchGenerationV1,
)
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.work_unit import WorkUnitCatalogue
from .account import (
    AccountRecomposeRequiredV1,
    AccountSessionExpiredError,
    compose_account_factories,
    compose_profile_sign_out_factory,
)

if TYPE_CHECKING:
    from textual.app import AutopilotCallbackType
    from textual.screen import Screen

    from ...application.modelo.work_review import ModeloWorkReview
    from ...application.modelo.workspace_models import (
        ModeloWorkspaceProjectionV1,
        ModeloWorkspaceStaticInspectionResultV1,
    )
    from ...application.operations.composition import OperationComposedServices
    from ...application.operations.registry import OperationPublicContractSetV1
    from ...application.operator_actions.models import ActionReference
    from ...application.overview.home import HomeProjectionV1
    from ...application.user_profile.login_interaction import ProfileLoginAttempt, ProfileLoginChoice
    from ...application.user_profile.overview import ProfileOverview
    from ...core.credentials import ProfilePasswordAssessment
    from ...core.external_constants import OutputLanguage
    from ...domain.modelos.work_unit import WorkUnit
    from .account import AccountFactoriesV1
    from .navigation import (
        TuiActionCandidateV1,
        TuiDestinationCatalogueV1,
        TuiScreenContextV1,
        TuiScreenFactoryV1,
    )
    from .search import WorkbenchSearchDoorV1
    from .secret.passphrase import PassphraseChangeAttempt


type InstalledWorkbenchSearchInputsProviderV1 = Callable[[], InstalledWorkbenchSearchInputsV1 | None]
type InstalledWorkbenchDestinationsV1 = tuple[
    Mapping[str, WorkbenchDestinationAdmission], Mapping[str, TuiScreenFactoryV1]
]
type InstalledWorkbenchDestinationsProviderV1 = Callable[[], InstalledWorkbenchDestinationsV1]
type InstalledWorkbenchGenerationProviderV1 = Callable[[], WorkbenchGenerationV1]


@dataclass(frozen=True, slots=True)
class TuiOperationCompositionV1:
    """One operation service graph and its same-registry public contracts."""

    services: OperationComposedServices
    public_contracts: OperationPublicContractSetV1

    def __post_init__(self) -> None:
        """Refuse a public inventory detached from the composed service graph."""
        if self.public_contracts is not self.services.public_contracts:
            raise ValueError("TUI operation contracts must be the exact composed service contracts")


def compose_secure_profile_workbench_generation_provider(
    *,
    profile_id: str,
    profile_label: str,
    operation_contracts: OperationPublicContractSetV1 | None = None,
) -> InstalledWorkbenchGenerationProviderV1:
    """Bind the installed provider to the current secure profile session.

    Repository instances stay inside the application read door; neither the
    root nor any screen receives a repository/service locator. Calling the
    returned provider is the explicit local-I/O boundary for a fresh session
    generation and never initiates network work.
    """
    from ...adapters.persistence.profile.buckets import build_bucket_event_history_repository
    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ...adapters.persistence.profile.modelos_verification_reports import (
        VerificationReportCatalogueRepository,
    )
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ...application.overview.home import HomeAccountSession, HomeSessionPosture
    from ...application.user_profile.login_session_port import (
        profile_current_bucket_session,
        profile_session_serves_bucket,
    )
    from ...application.user_profile.profile_record_repository import ProfileRecordRepository
    from ...application.workbench_generation import (
        InstalledWorkbenchGenerationProviderV1 as ApplicationGenerationProviderV1,
    )
    from ...application.workbench_generation import (
        SecureProfileWorkbenchGenerationReadDoorV1,
    )
    from ...core.time.clock import now

    def account_session() -> HomeAccountSession:
        """Recheck custody and return the current non-secret account facts."""
        current_session = profile_current_bucket_session()
        if (
            current_session is None
            or current_session.sealed
            or not profile_session_serves_bucket(current_session, profile_id)
        ):
            raise RuntimeError("installed workbench requires the live secure session for its selected profile")
        if current_session.is_expired(now()):
            raise AccountSessionExpiredError()
        return HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label=profile_label,
            expires_at=min(current_session.idle_deadline, current_session.absolute_deadline),
        )

    account_session()
    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=profile_id,
        profile_repository=ProfileRecordRepository.for_current_session(profile_id),
        work_unit_repository=WorkUnitCatalogueRepository(bucket_id=profile_id),
        calculation_repository=CalculationRevisionCatalogueRepository(bucket_id=profile_id),
        filing_repository=ModeloRecordCatalogueRepository(bucket_id=profile_id),
        clock=now,
        account_session_reader=account_session,
        transaction_repository=TransactionCatalogueRepository(bucket_id=profile_id),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=profile_id),
        bucket_event_repository=build_bucket_event_history_repository(bucket_id=profile_id),
        verification_repository=VerificationReportCatalogueRepository(bucket_id=profile_id),
        notification_custody_reader=_notification_custody_reader(profile_id),
        result_casilla_reader=_declaration_result_casilla_reader(),
        operation_contracts=operation_contracts,
        modelo_projection_reader=_modelo_projection_reader(),
    )
    return ApplicationGenerationProviderV1(door)


def _ledger_classification_submitter(profile_id: str) -> LedgerClassificationSubmitterV1:
    """Apply one authorised classification patch to the operator's own ledger.

    The submission carries the action reference the catalogue admitted, so the
    door records WHICH authority the operator acted under rather than a bare
    "tui" label -- an amended classification that cannot say who authorised it
    is an audit gap in a filing-bound record.
    """

    async def submit(submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult:
        from ...application.ledger.actions_manual import update_manual_transaction_fields

        return update_manual_transaction_fields(
            bucket_id=profile_id,
            transaction_id=submission.transaction_id,
            patch=submission.patch,
            actor="operator",
            source_command=str(submission.action.action_id),
        )

    return submit


def _ledger_import_submitter() -> LedgerImportSubmitterV1:
    """Run one already-resolved import command through the application service.

    The command arrives sealed from the prepared import, so this door never
    sees a path the presentation layer chose -- it forwards what the operator
    prepared and the application validated.
    """

    async def submit(command: LedgerSourceImportCommand) -> LedgerSourceImportResult:
        from ...application.ledger.actions_import import import_ledger_source

        return import_ledger_source(command)

    return submit


def _notification_custody_reader(profile_id: str) -> Callable[[], int]:
    """Count the notification documents this profile already holds locally.

    The repository is the CLI's own -- one canonical factory, so a TUI read and
    a CLI write cannot disagree about where custody lives. Only the count is
    taken: AEAT Sync needs to know whether anything is there, not what it says,
    and reading document bytes to answer that would decrypt payloads for a
    number.
    """

    def read() -> int:
        from ...adapters.persistence.profile.notification_documents import (
            notification_document_repository,
        )
        from ...core.config import load_settings

        return len(notification_document_repository(profile_id, load_settings()).list_snapshots())

    return read


def _declaration_result_casilla_reader() -> Callable[[str, int, Period], str | None]:
    """Name the casilla that settles one modelo revision, from the bundled registry.

    Resolution failures are answered with `None` rather than raised. A modelo
    or period the registry cannot select is a declaration whose result is
    UNKNOWN, which is exactly what the surface renders; letting it escape would
    take down a Home and Declarations read over a figure that is one column of
    one row.
    """

    def read(modelo: str, filing_year: int, period: Period) -> str | None:
        from ...application.modelo.settlement_casilla import declaration_result_casilla_id
        from ...domain.calculations.registry.authority import bundled_authority

        try:
            snapshot = bundled_authority().snapshot(
                str(modelo), filing_year=filing_year, period=period.registry_token
            )
        except Exception:
            return None
        return declaration_result_casilla_id(snapshot.revision)

    return read


def _modelo_projection_reader() -> Callable[[WorkUnit], ModeloWorkspaceProjectionV1]:
    """Read one work unit's canonical workspace projection for search.

    The read is the same static inspection the Modelo workspace itself is
    admitted through, so a searchable declaration and an opened one cannot
    describe different registry state. The output language is resolved per
    read rather than closed over: a profile language change clears the
    resolver cache, and a projection captured under the previous language
    would leave the workbench half-translated until sign-out.
    """
    from ...core.external_constants import OutputLanguage as _OutputLanguage
    from ...core.i18n.render import output_language as resolve_output_language

    def project(unit: WorkUnit) -> ModeloWorkspaceProjectionV1:
        return resolve_modelo_workspace_static_inspection(
            unit,
            output_language=_OutputLanguage(resolve_output_language()),
        ).projection

    return project


@dataclass(frozen=True, slots=True)
class InstalledWorkbenchRootInputsV1:
    """Explicit safe inputs needed to compose one installed workbench root.

    Projection sourcing is deliberately outside this value object: its caller
    has already loaded the current authoritative generation and supplied the
    existing area factories.  The launcher may join those facts, but it never
    reads a repository, opens a notification, acquires credentials, or starts
    an operation merely to make a screen available.
    """

    home_projection: HomeProjectionV1
    refresh_home: Callable[[], HomeProjectionV1]
    admissions: Mapping[str, WorkbenchDestinationAdmission]
    account_factories: AccountFactoriesV1
    ledger_factory: TuiScreenFactoryV1 | None
    declarations_factory: TuiScreenFactoryV1 | None
    aeat_sync_factory: TuiScreenFactoryV1 | None
    search_inputs: InstalledWorkbenchSearchInputsV1 | None
    refresh_search_inputs: InstalledWorkbenchSearchInputsProviderV1
    refresh_destinations: InstalledWorkbenchDestinationsProviderV1 | None = None
    """Re-derive admissions and factories from the CURRENT generation.

    Without this the root would hold admissions from the first generation
    while every factory resolved its projection from the latest one, so a
    refresh that legitimately changed availability would leave the two
    disagreeing -- offering a destination whose projection is gone, or
    refusing one that has since become readable.
    """
    action_candidates: Iterable[TuiActionCandidateV1] = ()


@dataclass(frozen=True, slots=True)
class InstalledWorkbenchRootCompositionV1:
    """One closed root catalogue and explicit refresh doors for a session."""

    destination_catalogue: TuiDestinationCatalogueV1
    admissions: Mapping[str, WorkbenchDestinationAdmission]
    refresh_home: Callable[[], HomeProjectionV1]
    search_inputs: InstalledWorkbenchSearchInputsV1 | None
    refresh_search_inputs: InstalledWorkbenchSearchInputsProviderV1
    refresh_destination_catalogue: Callable[[], TuiDestinationCatalogueV1] | None
    account_factories: AccountFactoriesV1


type InstalledWorkbenchRootInputsProviderV1 = Callable[[TuiOperationCompositionV1], InstalledWorkbenchRootInputsV1]
type AuthenticatedSessionRecomposeDoorV1 = Callable[
    [AccountRecomposeRequiredV1], InstalledWorkbenchRootInputsProviderV1 | None
]


@dataclass(frozen=True, slots=True)
class InstalledWorkbenchAccountInputsV1:
    """Non-secret account doors the launcher binds to the current session."""

    profile_id: str
    profile_overview: ProfileOverview
    persist_profile_field: Callable[[str, str], ProfileOverview]
    login_choices: Sequence[ProfileLoginChoice]
    authenticate: Callable[[str, str], ProfileLoginAttempt]
    assess_password: Callable[[str], ProfilePasswordAssessment]
    rotate_password: Callable[[str, str, str], PassphraseChangeAttempt]

    def __post_init__(self) -> None:
        """Bind every account door to one exact authenticated profile identity."""
        if self.profile_overview.profile_id != self.profile_id:
            raise ValueError("account overview must name the authenticated profile")
        matching_choices = tuple(choice for choice in self.login_choices if choice.profile_id == self.profile_id)
        if len(matching_choices) != 1 or matching_choices[0].label != self.profile_overview.label:
            raise ValueError("account login choices must contain the authenticated profile and label exactly once")

    def factories(self, services: OperationComposedServices) -> AccountFactoriesV1:
        """Compose existing account owners without reading or retaining secrets."""
        return compose_account_factories(
            profile_overview=self.profile_overview,
            persist_profile_field=self.persist_profile_field,
            login_choices=self.login_choices,
            authenticate=self.authenticate,
            assess_password=self.assess_password,
            rotate_password=self.rotate_password,
            sign_out=compose_profile_sign_out_factory(services, profile_id=self.profile_id),
        )


@dataclass(frozen=True, slots=True)
class InstalledWorkbenchFactoryDependenciesV1:
    """TUI-owned factories and public action contracts for one session.

    No repository or service locator crosses this value.  The generation
    provider has already reduced secure source reads to safe application
    projections; these values only bind those projections to their existing
    screen owners.
    """

    account: InstalledWorkbenchAccountInputsV1
    profile_admission: WorkbenchDestinationAdmission
    ledger_review_action: ActionReference
    ledger_evidence_action: ActionReference
    ledger_classify_action: ActionReference
    declarations_work_action: ActionReference
    declarations_revisions_action: ActionReference
    declarations_filing_action: ActionReference


def compose_installed_workbench_generation_provider(
    generation_provider: InstalledWorkbenchGenerationProviderV1,
    dependencies: InstalledWorkbenchFactoryDependenciesV1,
) -> InstalledWorkbenchRootInputsProviderV1:
    """Adapt child-owned generations to the installed root input contract.

    The provider is invoked only at an explicit session refresh boundary.
    Search refresh captures the next whole generation and Home consumes that
    exact capture on the immediately following child return.  Destination
    wrappers resolve their projection from the same current generation.
    """

    def provide(operation_runtime: TuiOperationCompositionV1) -> InstalledWorkbenchRootInputsV1:
        account_factories = dependencies.account.factories(operation_runtime.services)
        current = [generation_provider()]
        home_pending: list[WorkbenchGenerationV1 | None] = [current[0]]

        def capture() -> WorkbenchGenerationV1:
            generation = generation_provider()
            current[0] = generation
            return generation

        def refresh_home() -> HomeProjectionV1:
            generation = home_pending[0]
            if generation is None:
                generation = capture()
            home_pending[0] = None
            return _required_projection(generation.home, "Home")

        def refresh_search_inputs() -> InstalledWorkbenchSearchInputsV1 | None:
            generation = capture()
            home_pending[0] = generation
            return _search_inputs(generation)

        def destinations() -> InstalledWorkbenchDestinationsV1:
            """Read admissions and factories from the generation in hand.

            Both halves come from the same capture, so a destination is
            offered exactly when its projection exists. Deriving them at
            different instants is what let the catalogue advertise a route
            whose factory would raise, and refuse one that had become
            readable.
            """
            generation = current[0]
            _require_generation_admission(generation.ledger, generation.ledger_admission, "Ledger")
            _require_generation_admission(
                generation.declarations,
                generation.declarations_admission,
                "Declarations",
            )
            _require_generation_admission(generation.aeat_sync, generation.aeat_sync_admission, "AEAT Sync")
            admissions: dict[str, WorkbenchDestinationAdmission] = {
                "workbench.home": _available_admission("workbench.home"),
                "workbench.ledger": generation.ledger_admission,
                "workbench.declarations": generation.declarations_admission,
                "workbench.aeat_sync": generation.aeat_sync_admission,
                "workbench.profile": dependencies.profile_admission,
            }
            factories: dict[str, TuiScreenFactoryV1] = {}
            ledger_factory = _ledger_generation_factory(current, dependencies)
            if ledger_factory is not None:
                factories["workbench.ledger"] = ledger_factory
            declarations_factory = _declarations_generation_factory(current, dependencies)
            if declarations_factory is not None:
                factories["workbench.declarations"] = declarations_factory
            aeat_sync_factory = _aeat_sync_generation_factory(
                current,
                dependencies,
                operation_runtime.public_contracts,
            )
            if aeat_sync_factory is not None:
                factories["workbench.aeat_sync"] = aeat_sync_factory
            factories["workbench.profile"] = account_factories.profile
            return admissions, factories

        admissions, factories = destinations()
        generation = current[0]

        return InstalledWorkbenchRootInputsV1(
            home_projection=_required_projection(generation.home, "Home"),
            refresh_home=refresh_home,
            admissions=admissions,
            account_factories=account_factories,
            ledger_factory=factories.get("workbench.ledger"),
            declarations_factory=factories.get("workbench.declarations"),
            aeat_sync_factory=factories.get("workbench.aeat_sync"),
            search_inputs=_search_inputs(generation),
            refresh_search_inputs=refresh_search_inputs,
            refresh_destinations=destinations,
        )

    return provide


def _available_admission(destination: str) -> WorkbenchDestinationAdmission:
    return WorkbenchDestinationAdmission(
        destination=destination,
        state=WorkbenchDestinationAdmissionState.AVAILABLE,
    )


def _required_projection[ProjectionT](
    result: WorkbenchGenerationProjectionResultV1[ProjectionT],
    label: str,
) -> ProjectionT:
    projection = result.projection
    if projection is None:
        raise RuntimeError(f"{label} projection is unavailable in this workbench generation")
    return projection


def _require_generation_admission[ProjectionT](
    result: WorkbenchGenerationProjectionResultV1[ProjectionT],
    admission: WorkbenchDestinationAdmission,
    label: str,
) -> None:
    available = admission.state is WorkbenchDestinationAdmissionState.AVAILABLE
    if available != (result.projection is not None):
        raise ValueError(f"{label} admission and generation projection availability disagree")


def _search_inputs(generation: WorkbenchGenerationV1) -> InstalledWorkbenchSearchInputsV1 | None:
    if generation.search.projection is None:
        return None
    return InstalledWorkbenchSearchInputsV1(
        ledger=_required_projection(generation.ledger, "Ledger"),
        declarations=_required_projection(generation.declarations, "Declarations"),
        aeat_sync=_required_projection(generation.aeat_sync, "AEAT Sync"),
        modelo=_required_projection(generation.modelo, "Modelo"),
        ledger_admission=generation.ledger_admission,
        declarations_admission=generation.declarations_admission,
        aeat_sync_admission=generation.aeat_sync_admission,
    )


def _ledger_generation_factory(
    current: list[WorkbenchGenerationV1],
    dependencies: InstalledWorkbenchFactoryDependenciesV1,
) -> TuiScreenFactoryV1 | None:
    if current[0].ledger.projection is None:
        return None
    from .ledger.routes import ledger_screen_factory

    def create(context: TuiScreenContextV1) -> Screen[None]:
        from ...adapters.persistence.storage.attachment import AttachmentStore
        from ...application.ledger.attachment_review import list_attachment_review_queue

        return ledger_screen_factory(
            _required_projection(current[0].ledger, "Ledger"),
            review_action=dependencies.ledger_review_action,
            evidence_action=dependencies.ledger_evidence_action,
            # A TUPLE, including an empty one: the evidence area distinguishes
            # "read, nothing outstanding" from "never read", and only the
            # second is an absent door. Read here rather than in the
            # generation because the queue is per-visit state an operator acts
            # on, not part of the immutable session snapshot.
            evidence_items=list_attachment_review_queue(AttachmentStore(bucket_id=dependencies.account.profile_id)),
            classify_action=dependencies.ledger_classify_action,
            classification_submitter=_ledger_classification_submitter(dependencies.account.profile_id),
            import_submitter=_ledger_import_submitter(),
        )(context)

    return create


def _declarations_generation_factory(
    current: list[WorkbenchGenerationV1],
    dependencies: InstalledWorkbenchFactoryDependenciesV1,
) -> TuiScreenFactoryV1 | None:
    if current[0].declarations.projection is None:
        return None
    from .declarations.routes import declarations_screen_factory

    def create(context: TuiScreenContextV1) -> Screen[None]:
        from .modelo.installed_workspace import compose_installed_modelo_workspace_factory

        modelo = current[0].modelo
        modelo_workspace_factory = (
            compose_installed_modelo_workspace_factory(
                bucket_id=_required_projection(current[0].declarations, "Declarations").bucket_id,
                declarations=_required_projection(current[0].declarations, "Declarations").declarations,
                projections=_required_projection(modelo, "Modelo"),
            )
            if modelo.availability is WorkbenchGenerationAvailability.AVAILABLE and modelo.projection is not None
            else None
        )
        calendar = current[0].declarations_calendar.projection
        return declarations_screen_factory(
            _required_projection(current[0].declarations, "Declarations"),
            work_action=dependencies.declarations_work_action,
            revisions_action=dependencies.declarations_revisions_action,
            filing_action=dependencies.declarations_filing_action,
            modelo_workspace_factory=modelo_workspace_factory,
            calendar_projection=calendar,
        )(context)

    return create


def _aeat_sync_generation_factory(
    current: list[WorkbenchGenerationV1],
    dependencies: InstalledWorkbenchFactoryDependenciesV1,
    operation_contracts: OperationPublicContractSetV1,
) -> TuiScreenFactoryV1 | None:
    if current[0].aeat_sync.projection is None:
        return None
    from .aeat_sync.routes import aeat_sync_screen_factory

    def create(context: TuiScreenContextV1) -> Screen[None]:
        return aeat_sync_screen_factory(
            _required_projection(current[0].aeat_sync, "AEAT Sync"),
            operation_contracts=operation_contracts,
        )(context)

    return create


def load_modelo_work_unit_catalogue(bucket_id: str) -> WorkUnitCatalogue:
    """Load one profile's work-unit catalogue at the TUI composition boundary."""
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository

    return WorkUnitCatalogueRepository(bucket_id=bucket_id).load()


def _require_active_bucket_id(bucket_id: str | None) -> str:
    """Resolve the bucket a session reads, refusing a cold start outright.

    A session that reached a work destination without a profile has nothing to
    render, and the honest report is a refusal rather than an empty surface
    that looks like a profile holding no work.
    """
    from ...core.bucket_pointer import resolve_active_bucket_id

    resolved = bucket_id or resolve_active_bucket_id()
    if resolved is None:
        raise ModeloError("no active profile: a work destination needs one profile's bucket to read")
    return resolved


def resolve_modelo_work_unit(*, work_unit_id: str, bucket_id: str | None) -> WorkUnit:
    """Resolve one work unit by exact id at the TUI composition boundary.

    The identifier is all that crosses into this process, so the record it
    names is read here rather than received. That is what makes the surface a
    read of current persistence instead of a projection of whatever a sibling
    entrypoint held when it asked for the destination.
    """
    from ...application.modelo.work_addressing import resolve_modelo_work_unit_for_operator_target

    resolved_bucket_id = _require_active_bucket_id(bucket_id)
    return resolve_modelo_work_unit_for_operator_target(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        catalogue=load_modelo_work_unit_catalogue(resolved_bucket_id),
        resolved_bucket_id=resolved_bucket_id,
    )


def load_modelo_work_units(*, bucket_id: str | None, include_discarded: bool) -> tuple[WorkUnit, ...]:
    """Read the work units a picker offers at the TUI composition boundary."""
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...application.modelo.work_lifecycle import list_work_units

    resolved_bucket_id = _require_active_bucket_id(bucket_id)
    return list_work_units(
        bucket_id=bucket_id,
        include_discarded=include_discarded,
        repository=WorkUnitCatalogueRepository(bucket_id=resolved_bucket_id),
    )


def build_modelo_work_review_for_unit(unit: WorkUnit) -> ModeloWorkReview:
    """Build the canonical review record for one resolved unit."""
    from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...application.modelo.work_review import build_modelo_work_review

    return build_modelo_work_review(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        verification_repository=VerificationReportCatalogueRepository(),
    )


def resolve_modelo_workspace_static_inspection(
    unit: WorkUnit, *, output_language: OutputLanguage
) -> ModeloWorkspaceStaticInspectionResultV1:
    """Assemble the workspace read result for one already-resolved unit.

    The unit is addressed by its exact identity rather than by its visible
    modelo/year/period coordinates. A profile that discarded a declaration and
    created a new one at the same address holds two units there, and a
    coordinate request is ambiguous across them — which would refuse a read
    the caller had already resolved. The catalogue is opened on the unit's own
    bucket rather than the active-profile pointer, so the read cannot drift to
    another profile.
    """
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...application.modelo.work_addressing import ModeloExactWorkUnitTarget
    from ...application.modelo.workspace import resolve_static_inspection_result
    from ...application.modelo.workspace_models import ModeloWorkspaceExactWorkUnitTargetV1
    from ...domain.calculations.registry.authority import bundled_authority

    return resolve_static_inspection_result(
        ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(
                work_unit_id=unit.work_unit_id,
                bucket_id=unit.bucket_id,
            )
        ),
        bucket_id=unit.bucket_id,
        catalogue_repository=WorkUnitCatalogueRepository(bucket_id=unit.bucket_id),
        authority=bundled_authority(),
        output_language=output_language,
    )


@contextmanager
def profile_storage_scope(root: Path) -> Generator[Path]:
    """Bind persistent profile infrastructure rooted at ``root`` for one TUI run.

    This is the sole TUI composition seam permitted to construct persistence
    adapters. Screens and devtools receive application contracts after this
    scope has bound them; neither needs to know which concrete adapter serves
    the session.
    """
    from ...core.config import SecretStoreBackend, load_settings, override_settings
    from ...core.storage_taxonomy import StorageCategory
    from ...core.storage_taxonomy_locations import STORAGE_TAXONOMY, storage_location
    from ..adapter_composition import profile_adapter_composition

    storage_root = root / "cadrumo-storage"
    secret_field = STORAGE_TAXONOMY[StorageCategory.SECRETS].settings_field
    if secret_field is None:
        message = "the declared secret storage category has no settings field"
        raise RuntimeError(message)
    secret_path = root / storage_location(StorageCategory.SECRETS).relative_path()
    with ExitStack() as composition:
        composition.enter_context(
            override_settings(
                cadrumo_local_storage_root=storage_root,
                cadrumo_active_profile=None,
                cadrumo_secret_store_backend=SecretStoreBackend.AUTO,
                cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
                cadrumo_profile_kdf_measure_calibration=False,
                **{secret_field: secret_path},
            )
        )
        composition.enter_context(profile_adapter_composition())
        yield storage_root


@asynccontextmanager
async def operation_services_scope() -> AsyncGenerator[TuiOperationCompositionV1]:
    """Compose the operation platform for one TUI run and settle it after.

    This is the sole TUI composition seam permitted to build the operation
    registry, journal, leases and supervisor. Screens and controllers receive
    the composed services; none of them constructs the graph, so a TUI session
    has exactly one place where that inventory comes into being.

    The factory itself lives one level up, shared with the CLI. Moving it into
    this package would oblige every other frontend to import the TUI to reach
    it, which is the dependency the TUI boundary exists to forbid.
    """
    from ..operation_composition import compose_operation_dependencies

    services = compose_operation_dependencies()
    composition = TuiOperationCompositionV1(
        services=services,
        public_contracts=services.public_contracts,
    )
    try:
        yield composition
    finally:
        await services.shutdown()


def compose_installed_workbench_search(
    inputs: InstalledWorkbenchSearchInputsV1,
) -> WorkbenchSearchDoorV1:
    """Assemble preloaded public projections through the application boundary.

    The input bundle is injected by the installed-session composition. This
    function performs no reads: the application-owned provider derives the
    immutable redacted snapshot from that one already-authoritative generation.
    """
    return inputs.snapshot().service()


def compose_installed_workbench_root(
    inputs: InstalledWorkbenchRootInputsV1,
) -> InstalledWorkbenchRootCompositionV1:
    """Join one already-authoritative session generation into the root shell.

    The inputs deliberately carry the application-owned projections, action
    admissions, and existing area factories.  This boundary only checks that
    the search and navigation views name the same authoritative admissions,
    then builds the closed TUI catalogue.  It neither creates a second screen
    implementation nor performs storage or network I/O.
    """
    from .home import HomeScreen
    from .navigation import build_destination_catalogue

    def home_factory(context: TuiScreenContextV1) -> HomeScreen:
        if context.destination != "workbench.home":
            raise ValueError("the Home factory accepts only the Home destination")
        return HomeScreen(inputs.home_projection)

    if inputs.search_inputs is not None:
        _require_search_admission_parity(inputs.search_inputs, inputs.admissions)

    factories = {
        destination: factory
        for destination, factory in {
            "workbench.home": home_factory,
            "workbench.ledger": inputs.ledger_factory,
            "workbench.declarations": inputs.declarations_factory,
            "workbench.aeat_sync": inputs.aeat_sync_factory,
            "workbench.profile": inputs.account_factories.profile,
        }.items()
        if factory is not None
    }

    refresh_destinations = inputs.refresh_destinations

    def rebuild() -> TuiDestinationCatalogueV1:
        """Rebuild the catalogue from the generation the factories now read.

        Called on the same authoritative child return that refreshes search,
        so navigation, search and the mounted projections all describe one
        capture rather than three instants.
        """
        assert refresh_destinations is not None  # noqa: S101 - guarded by the door below
        refreshed_admissions, refreshed_factories = refresh_destinations()
        return build_destination_catalogue(
            admissions={"workbench.home": _available_admission("workbench.home"), **refreshed_admissions},
            factories={"workbench.home": home_factory, **refreshed_factories},
            action_candidates=inputs.action_candidates,
        )

    return InstalledWorkbenchRootCompositionV1(
        destination_catalogue=build_destination_catalogue(
            admissions=inputs.admissions,
            factories=factories,
            action_candidates=inputs.action_candidates,
        ),
        admissions=inputs.admissions,
        refresh_home=inputs.refresh_home,
        search_inputs=inputs.search_inputs,
        refresh_search_inputs=inputs.refresh_search_inputs,
        refresh_destination_catalogue=rebuild if refresh_destinations is not None else None,
        account_factories=inputs.account_factories,
    )


def _require_search_admission_parity(
    search_inputs: InstalledWorkbenchSearchInputsV1,
    admissions: Mapping[str, WorkbenchDestinationAdmission],
) -> None:
    """Refuse a palette generation that disagrees with the mounted catalogue."""
    expected_search_admissions = {
        "workbench.ledger": search_inputs.ledger_admission,
        "workbench.declarations": search_inputs.declarations_admission,
        "workbench.aeat_sync": search_inputs.aeat_sync_admission,
    }
    for destination, admission in expected_search_admissions.items():
        if admissions.get(destination) != admission:
            raise ValueError("installed search and root navigation admissions must agree")


async def _run_root_session(
    *,
    headless: bool,
    auto_pilot: AutopilotCallbackType | None,
    workbench_root_inputs_provider: InstalledWorkbenchRootInputsProviderV1 | None = None,
) -> AccountRecomposeRequiredV1 | None:
    """Compose one session's services, run the root application, settle them.

    The services are composed OUTSIDE the application and handed to it, so
    the root never constructs its own graph and the scope still settles if
    the application raises on the way up or down.
    """
    from .app import CadrumoTuiApp

    async with operation_services_scope() as operation_runtime:
        root = (
            compose_installed_workbench_root(workbench_root_inputs_provider(operation_runtime))
            if workbench_root_inputs_provider is not None
            else None
        )
        if root is None:
            return await CadrumoTuiApp(services=operation_runtime.services).run_async(
                headless=headless,
                auto_pilot=auto_pilot,
            )
        service = None if root.search_inputs is None else compose_installed_workbench_search(root.search_inputs)

        def refresh_search() -> WorkbenchSearchDoorV1:
            refreshed_inputs = root.refresh_search_inputs()
            if refreshed_inputs is None:
                raise RuntimeError("installed workbench search is unavailable in the refreshed generation")
            # Parity is checked against the admissions of the SAME capture the
            # inputs came from, not against the session's first ones: a refresh
            # that legitimately changes availability is coherent, and comparing
            # it to a stale snapshot is what made a supported profile edit kill
            # search for the rest of the session.
            _require_search_admission_parity(
                refreshed_inputs,
                {
                    "workbench.ledger": refreshed_inputs.ledger_admission,
                    "workbench.declarations": refreshed_inputs.declarations_admission,
                    "workbench.aeat_sync": refreshed_inputs.aeat_sync_admission,
                },
            )
            return compose_installed_workbench_search(refreshed_inputs)

        return await CadrumoTuiApp(
            services=operation_runtime.services,
            destination_catalogue=root.destination_catalogue,
            refresh_home=root.refresh_home,
            workbench_search_service=service,
            refresh_workbench_search=refresh_search,
            refresh_destination_catalogue=root.refresh_destination_catalogue,
            account_factories=root.account_factories,
        ).run_async(headless=headless, auto_pilot=auto_pilot)


async def run_authenticated_workbench_sessions(
    *,
    headless: bool,
    auto_pilot: AutopilotCallbackType | None,
    workbench_root_inputs_provider: InstalledWorkbenchRootInputsProviderV1,
    recompose_authenticated_session: AuthenticatedSessionRecomposeDoorV1 | None = None,
) -> AccountRecomposeRequiredV1 | None:
    """Run fresh roots until the outer authenticated-session owner declines one.

    Each root has its own operation-service scope. A handover, password
    rotation, sign-out, or expiry first settles and discards that scope, then
    gives only its non-secret recompose result to the injected outer owner.
    The owner must select a new bootstrap/session generation and return a new
    provider; returning ``None`` fails closed rather than reusing the former
    profile-bound root.
    """
    provider = workbench_root_inputs_provider
    while True:
        outcome = await _run_root_session(
            headless=headless,
            auto_pilot=auto_pilot,
            workbench_root_inputs_provider=provider,
        )
        if outcome is None or recompose_authenticated_session is None:
            return outcome
        next_provider = recompose_authenticated_session(outcome)
        if next_provider is None:
            return outcome
        provider = next_provider


def main(
    *,
    headless: bool = False,
    auto_pilot: AutopilotCallbackType | None = None,
    workbench_root_inputs_provider: InstalledWorkbenchRootInputsProviderV1 | None = None,
    recompose_authenticated_session: AuthenticatedSessionRecomposeDoorV1 | None = None,
) -> int:
    """Start one dedicated TUI session and report its process exit status.

    This is the sole entry point for module execution and for the installed
    console script; neither reaches past it into the composition seams, and
    neither imports the CLI. ``headless`` and ``auto_pilot`` are Textual's
    own run parameters, carried so a caller can drive a real session to
    completion without a terminal rather than assert against an import.

    Without an injected provider this composes the production installed
    session: adapters, one truthful profile-inventory observation, whichever
    existing credential journey that observation names, and the authenticated
    generation the root shell consumes. A caller that injects a provider has
    already made those choices, so its session is run exactly as given.
    """
    if workbench_root_inputs_provider is None:
        from .installed_session import run_installed_workbench_session

        return run_installed_workbench_session(headless=headless, auto_pilot=auto_pilot)
    asyncio.run(
        run_authenticated_workbench_sessions(
            headless=headless,
            auto_pilot=auto_pilot,
            workbench_root_inputs_provider=workbench_root_inputs_provider,
            recompose_authenticated_session=recompose_authenticated_session,
        )
    )
    return 0


__all__ = [
    "AuthenticatedSessionRecomposeDoorV1",
    "InstalledWorkbenchAccountInputsV1",
    "InstalledWorkbenchFactoryDependenciesV1",
    "InstalledWorkbenchGenerationProviderV1",
    "InstalledWorkbenchRootCompositionV1",
    "InstalledWorkbenchRootInputsProviderV1",
    "InstalledWorkbenchRootInputsV1",
    "InstalledWorkbenchSearchInputsProviderV1",
    "TuiOperationCompositionV1",
    "build_modelo_work_review_for_unit",
    "compose_installed_workbench_generation_provider",
    "compose_installed_workbench_root",
    "compose_installed_workbench_search",
    "compose_secure_profile_workbench_generation_provider",
    "load_modelo_work_unit_catalogue",
    "load_modelo_work_units",
    "main",
    "operation_services_scope",
    "profile_storage_scope",
    "resolve_modelo_work_unit",
    "resolve_modelo_workspace_static_inspection",
    "run_authenticated_workbench_sessions",
]
