"""Concrete runtime composition for installed and diagnostic TUI sessions."""

from __future__ import annotations

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
from ...core.errors.hierarchy import CadrumoError, InternalInvariantError
from .account import (
    AccountRecomposeRequiredV1,
    AccountSessionExpiredError,
    compose_account_factories,
    compose_profile_sign_out_factory,
)

if TYPE_CHECKING:
    from textual.app import AutopilotCallbackType
    from textual.screen import Screen

    from ...application.ledger.attachment_review import AttachmentReviewItem
    from ...application.ledger.models import ManualLedgerTransactionResult
    from ...application.ledger.workspace import LedgerWorkspaceProjectionV1
    from ...application.modelo.declarations_calendar import DeclarationsCalendarEntryRefV1
    from ...application.modelo.workspace_models import (
        ModeloWorkspaceProjectionV1,
        ModeloWorkspaceStaticInspectionResultV1,
    )
    from ...application.operations.composition import OperationComposedServices
    from ...application.operations.registry import OperationPublicContractSetV1
    from ...application.operator_actions.models import ActionReference, DeclaredNextAction
    from ...application.overview.home import HomeAccountSession, HomeProjectionV1
    from ...application.user_profile.login_interaction import ProfileLoginAttempt, ProfileLoginChoice
    from ...application.user_profile.overview import ProfileOverview
    from ...core.credentials import ProfilePasswordAssessment
    from ...core.external_constants import OutputLanguage
    from ...core.period import Period
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.work_unit import WorkUnit
    from .account import AccountFactoriesV1
    from .declarations.models import CalendarRecoveryHandoffV1
    from .ledger.models import (
        LedgerClassificationSubmissionV1,
        LedgerClassificationSubmitterV1,
        LedgerExclusionSubmissionV1,
        LedgerExclusionSubmitterV1,
        LedgerLinkResultV1,
        LedgerLinkSubmissionV1,
        LedgerLinkSubmitterV1,
    )
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
    authority_operation: PinnedAuthorityOperation
    event_loop: asyncio.AbstractEventLoop | None = None
    """The loop the session's screens read shared state on; captures publish to it."""

    def __post_init__(self) -> None:
        """Refuse a public inventory detached from the composed service graph."""
        if self.public_contracts is not self.services.public_contracts:
            raise ValueError("TUI operation contracts must be the exact composed service contracts")


def compose_secure_profile_workbench_generation_provider(
    *,
    profile_id: str,
    profile_label: str,
    operation: PinnedAuthorityOperation,
    operation_contracts: OperationPublicContractSetV1,
) -> InstalledWorkbenchGenerationProviderV1:
    """Bind the installed provider to the current secure profile session.

    Repository instances stay inside the application read door; neither the
    root nor any screen receives a repository/service locator. Calling the
    returned provider is the explicit local-I/O boundary for a fresh session
    generation and never initiates network work.
    """
    from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ...adapters.persistence.profile.modelos_verification_reports import (
        VerificationReportCatalogueRepository,
    )
    from ...application.user_profile.profile_record_repository import ProfileRecordRepository
    from ...application.workbench_generation import (
        InstalledWorkbenchGenerationProviderV1 as ApplicationGenerationProviderV1,
    )
    from ...application.workbench_generation import (
        SecureProfileWorkbenchGenerationReadDoorV1,
    )
    from ...core.time.clock import now
    from ..ledger_action_composition import compose_ledger_action_ports

    account_session = live_account_session_reader(profile_id=profile_id, profile_label=profile_label)
    account_session()

    def capture() -> WorkbenchGenerationV1:
        # The ledger ports are composed per capture, not once per session:
        # they carry the evidence records as read at composition, so a bundle
        # held across captures would keep reporting the evidence the session
        # started with after the operator had added more.
        return ApplicationGenerationProviderV1(read_door())()

    def read_door() -> SecureProfileWorkbenchGenerationReadDoorV1:
        ledger_action_ports = compose_ledger_action_ports(bucket_id=profile_id, operation=operation)
        return SecureProfileWorkbenchGenerationReadDoorV1(
            profile_id=profile_id,
            operation=operation,
            profile_repository=ProfileRecordRepository.for_current_session(
                profile_id,
                profile_decode_context=operation.profile_decode_context(),
            ),
            work_unit_repository=ledger_action_ports.work_unit_repository,
            calculation_repository=ledger_action_ports.calculation_repository,
            filing_repository=ModeloRecordCatalogueRepository(bucket_id=profile_id),
            clock=now,
            account_session_reader=account_session,
            transaction_repository=ledger_action_ports.transaction_repository,
            invoice_repository=ledger_action_ports.invoice_repository,
            bucket_event_repository=ledger_action_ports.bucket_event_repository,
            ledger_action_ports=ledger_action_ports,
            verification_repository=VerificationReportCatalogueRepository(bucket_id=profile_id),
            notification_custody_reader=_notification_custody_reader(profile_id),
            result_casilla_reader=_declaration_result_casilla_reader(operation),
            operation_contracts=operation_contracts,
            modelo_projection_reader=_modelo_projection_reader(operation),
        )

    return capture


def compose_local_reader_page(services: OperationComposedServices) -> Callable[[], Screen[None]]:
    """Bind the document reader page to this session's operation platform.

    Setup, install, start, pull, load, verify and remove are submitted into the
    same journal and leases the rest of the session uses, so an action running
    here is one ``config provision`` would see, not a second inventory's.
    """

    def open_page() -> Screen[None]:
        from .profile.local_reader import LocalReaderScreen, OperationLocalReaderDoor

        return LocalReaderScreen(OperationLocalReaderDoor(services))

    return open_page


def live_account_session_reader(*, profile_id: str, profile_label: str) -> Callable[[], HomeAccountSession]:
    """Bind a check of the live secure session that reads its deadlines and nothing else.

    It opens no secure object, so calling it never rolls the idle deadline
    forward: a timer may call it without keeping the session alive.
    """
    from ...application.overview.home import HomeAccountSession, HomeSessionPosture
    from ...application.user_profile.login_session_port import (
        profile_current_bucket_session,
        profile_session_serves_bucket,
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
            raise InternalInvariantError(
                "installed workbench requires the live secure session for its selected profile"
            )
        if current_session.is_expired(now()):
            raise AccountSessionExpiredError()
        return HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label=profile_label,
            expires_at=min(current_session.idle_deadline, current_session.absolute_deadline),
        )

    return account_session


def _ledger_classification_submitter(
    profile_id: str, operation: PinnedAuthorityOperation
) -> LedgerClassificationSubmitterV1:
    """Apply one reviewed classification patch to the operator's own ledger.

    The application writer owns every precondition — the row's lifecycle state,
    the no-op guard, evidence and usage-ratio references, the audit event — so
    this door adds no policy of its own, exactly as the link door does not.

    The catalogue-admitted action reference travels through as the source
    command, so the persisted event records which authority the operator acted
    under rather than an anonymous surface label. The transaction id is the
    workspace's current focus, already checked against the visible projection
    before the classification screen could be reached at all.
    """

    async def submit(submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult:
        return await asyncio.to_thread(write, submission)

    def write(submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult:
        from ...application.ledger.actions_manual import update_manual_transaction_fields
        from ..ledger_action_composition import compose_ledger_action_ports

        ports = compose_ledger_action_ports(bucket_id=profile_id, operation=operation)

        return update_manual_transaction_fields(
            bucket_id=profile_id,
            transaction_id=submission.transaction_id,
            patch=submission.patch,
            actor="operator",
            source_command=str(submission.action.action_id),
            ports=ports,
        )

    return submit


def _ledger_link_submitter(profile_id: str, operation: PinnedAuthorityOperation) -> LedgerLinkSubmitterV1:
    """Link one invoice to one transaction in the operator's own ledger.

    The application writer owns every precondition -- missing invoice,
    cross-bucket ownership, an existing link -- and co-commits both catalogues
    with its audit event, so this door adds no policy of its own. It carries
    the catalogue-admitted action reference through as the source command, so
    the persisted event records which authority the operator acted under rather
    than an anonymous surface label.
    """

    async def submit(submission: LedgerLinkSubmissionV1) -> LedgerLinkResultV1:
        return await asyncio.to_thread(write, submission)

    def write(submission: LedgerLinkSubmissionV1) -> LedgerLinkResultV1:
        from ...application.ledger.actions_manual import link_manual_transaction_invoice
        from ..ledger_action_composition import compose_ledger_action_ports
        from .ledger.models import LedgerLinkResultV1 as _LedgerLinkResultV1

        ports = compose_ledger_action_ports(bucket_id=profile_id, operation=operation)

        result = link_manual_transaction_invoice(
            bucket_id=profile_id,
            transaction_id=submission.transaction_id,
            invoice_id=submission.invoice_id,
            actor="operator",
            source_command=str(submission.action.action_id),
            ports=ports,
        )
        return _LedgerLinkResultV1(transaction_id=result.transaction_id, invoice_id=result.invoice_id)

    return submit


def _ledger_exclusion_submitter(profile_id: str, operation: PinnedAuthorityOperation) -> LedgerExclusionSubmitterV1:
    """Mark one entry reviewed and excluded in the operator's own ledger.

    The lifecycle writer owns the finalized-modelo guard and the audit event;
    this door passes the repositories that guard reads, and records the
    classify authority the operator acted under.
    """

    async def submit(submission: LedgerExclusionSubmissionV1) -> ManualLedgerTransactionResult:
        return await asyncio.to_thread(write, submission)

    def write(submission: LedgerExclusionSubmissionV1) -> ManualLedgerTransactionResult:
        from ...application.ledger.actions_lifecycle import mark_transaction_reviewed_excluded
        from ..ledger_action_composition import compose_ledger_action_ports

        ports = compose_ledger_action_ports(bucket_id=profile_id, operation=operation)
        return mark_transaction_reviewed_excluded(
            bucket_id=profile_id,
            transaction_id=submission.transaction_id,
            actor="operator",
            source_command=str(submission.action.action_id),
            transaction_repository=ports.transaction_repository,
            bucket_event_repository=ports.bucket_event_repository,
            work_unit_repository=ports.work_unit_repository,
            calculation_repository=ports.calculation_repository,
        )

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


def _declaration_result_casilla_reader(
    operation: PinnedAuthorityOperation,
) -> Callable[[str, int, Period], str | None]:
    """Name the casilla that settles one modelo revision, from the bundled registry.

    Resolution failures are answered with `None` rather than raised. A modelo
    or period the registry cannot select is a declaration whose result is
    UNKNOWN, which is exactly what the surface renders; letting it escape would
    take down a Home and Declarations read over a figure that is one column of
    one row.
    """

    def read(modelo: str, filing_year: int, period: Period) -> str | None:
        from ...application.modelo.settlement_casilla import declaration_result_casilla_id

        snapshot = operation.snapshot(str(modelo), filing_year=filing_year, period=period.registry_token)
        return declaration_result_casilla_id(snapshot.revision)

    return read


def _modelo_projection_reader(
    operation: PinnedAuthorityOperation,
) -> Callable[[WorkUnit], ModeloWorkspaceProjectionV1]:
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
            operation=operation,
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
    read_account_session: Callable[[], HomeAccountSession] | None = None
    """Check the live session without touching it, for the root's expiry watch."""


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
    read_account_session: Callable[[], HomeAccountSession] | None = None


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
    complete_setup: Callable[[], ProfileOverview] | None = None

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
            complete_setup=self.complete_setup,
            sign_out=compose_profile_sign_out_factory(services, profile_id=self.profile_id),
            open_document_reader=compose_local_reader_page(services),
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
    ledger_link_action: ActionReference
    declarations_work_action: ActionReference
    declarations_revisions_action: ActionReference
    declarations_filing_action: ActionReference
    attachment_review_queue: Callable[[], tuple[AttachmentReviewItem, ...]] | None = None
    """Lists the attachments awaiting review; absent, the evidence area is refused."""


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
        read_queue = dependencies.attachment_review_queue
        current = [generation_provider()]
        home_pending: list[WorkbenchGenerationV1 | None] = [current[0]]
        attachment_queue: list[tuple[AttachmentReviewItem, ...] | None] = [None if read_queue is None else read_queue()]
        loop = operation_runtime.event_loop

        def publish(apply: Callable[[], None]) -> None:
            """Swap shared state on the loop that reads it.

            Captures run on worker threads while factories and the catalogue
            read this state on the loop. The swap is queued before the
            capturing thread returns, so the awaiting caller resumes after it.
            """
            if loop is None or _on_loop_thread(loop):
                apply()
            else:
                loop.call_soon_threadsafe(apply)

        def capture(*, for_home: bool = False) -> WorkbenchGenerationV1:
            generation = generation_provider()
            attachments = None if read_queue is None else read_queue()

            def apply() -> None:
                current[0] = generation
                attachment_queue[0] = attachments
                if for_home:
                    home_pending[0] = generation

            publish(apply)
            return generation

        def refresh_home() -> HomeProjectionV1:
            generation = home_pending[0]
            if generation is None:
                generation = capture()

            def consume() -> None:
                home_pending[0] = None

            publish(consume)
            return _required_projection(generation.home, "Home")

        def refresh_search_inputs() -> InstalledWorkbenchSearchInputsV1 | None:
            return _search_inputs(capture(for_home=True))

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
            ledger_factory = _ledger_generation_factory(
                current,
                attachment_queue,
                dependencies,
                operation_runtime.authority_operation,
                lambda: _required_projection(capture().ledger, "Ledger"),
            )
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
            action_candidates=_workspace_action_candidates(dependencies),
            read_account_session=live_account_session_reader(
                profile_id=dependencies.account.profile_id,
                profile_label=dependencies.account.profile_overview.label,
            ),
        )

    return provide


def _workspace_action_candidates(
    dependencies: InstalledWorkbenchFactoryDependenciesV1,
) -> tuple[TuiActionCandidateV1, ...]:
    """Declare every action the root hands a workspace as that workspace's candidate.

    The root already decides which workspace performs which action when it
    injects the references below; declaring them here is what lets Home's
    suggested actions and the palette open the workspace that performs them.
    With none declared, a suggested action was selectable and led nowhere.
    """
    from .navigation import TuiActionCandidateV1

    owned = (
        (
            "workbench.ledger",
            (
                dependencies.ledger_review_action,
                dependencies.ledger_evidence_action,
                dependencies.ledger_classify_action,
                dependencies.ledger_link_action,
            ),
        ),
        (
            "workbench.declarations",
            (
                dependencies.declarations_work_action,
                dependencies.declarations_revisions_action,
                dependencies.declarations_filing_action,
            ),
        ),
    )
    candidates: dict[str, TuiActionCandidateV1] = {}
    for destination, actions in owned:
        for action in actions:
            action_id = str(action.action_id)
            candidates.setdefault(
                action_id,
                TuiActionCandidateV1(action_candidate_id=action_id, destination=destination),
            )
    return tuple(candidates.values())


def _admitted_candidates(
    candidates: Iterable[TuiActionCandidateV1],
    admissions: Mapping[str, WorkbenchDestinationAdmission],
) -> tuple[TuiActionCandidateV1, ...]:
    """Keep only candidates whose workspace is available in this capture.

    A workspace that is not available may not admit actions, and availability
    is re-read on every refresh, so the filter is applied at each build.
    """
    return tuple(
        candidate
        for candidate in candidates
        if candidate.destination in admissions
        and admissions[candidate.destination].state is WorkbenchDestinationAdmissionState.AVAILABLE
    )


def _available_admission(destination: str) -> WorkbenchDestinationAdmission:
    return WorkbenchDestinationAdmission(
        destination=destination,
        state=WorkbenchDestinationAdmissionState.AVAILABLE,
    )


def read_attachment_review_queue(profile_id: str) -> tuple[AttachmentReviewItem, ...]:
    """List the attachments awaiting review; it decrypts every manifest, so only captures call it."""
    from ...adapters.persistence.storage.attachment import AttachmentStore
    from ...application.ledger.attachment_review import list_attachment_review_queue

    return tuple(list_attachment_review_queue(AttachmentStore(bucket_id=profile_id)))


def _on_loop_thread(loop: asyncio.AbstractEventLoop) -> bool:
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


def _required_projection[ProjectionT](
    result: WorkbenchGenerationProjectionResultV1[ProjectionT],
    label: str,
) -> ProjectionT:
    projection = result.projection
    if projection is None:
        raise InternalInvariantError(f"{label} projection is unavailable in this workbench generation")
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
    attachment_queue: list[tuple[AttachmentReviewItem, ...] | None],
    dependencies: InstalledWorkbenchFactoryDependenciesV1,
    operation: PinnedAuthorityOperation,
    capture_ledger: Callable[[], LedgerWorkspaceProjectionV1],
) -> TuiScreenFactoryV1 | None:
    """Bind the Ledger workspace to the current generation and its write doors.

    ``capture_ledger`` takes a whole new generation, so a flow that wrote
    something re-reads through the same door Home and search refresh from
    rather than a Ledger-only reader that could disagree with them.
    """
    if current[0].ledger.projection is None:
        return None
    from .ledger.routes import ledger_screen_factory

    def create(context: TuiScreenContextV1) -> Screen[None]:
        from .ledger_doors import (
            LedgerEvidenceDoor,
            LedgerImportDoor,
            ledger_invoice_add_door,
            ledger_workspace_refresh,
        )

        profile_id = dependencies.account.profile_id
        return ledger_screen_factory(
            _required_projection(current[0].ledger, "Ledger"),
            review_action=dependencies.ledger_review_action,
            evidence_action=dependencies.ledger_evidence_action,
            # A TUPLE, including an empty one: the evidence area distinguishes
            # "read, nothing outstanding" from "never read", and only the
            # second is an absent door. Read with each capture, on the
            # capture's thread, because listing it decrypts every manifest.
            evidence_items=attachment_queue[0],
            # The link door is passed as a pair. The reconciliation body reads
            # without either, but its confirmation control stays hidden unless
            # BOTH the admitted action and a submitter are present, so passing
            # one alone would read as wired while still refusing.
            link_action=dependencies.ledger_link_action,
            link_submitter=_ledger_link_submitter(dependencies.account.profile_id, operation),
            # The classification door is a pair for the same reason the link
            # door is: the screen's control stays hidden unless BOTH the
            # admitted action and a submitter are present. The third thing it
            # needs — which entry to classify — is not the launcher's to give;
            # the operator supplies it by selecting a row, and it travels in
            # the workspace focus.
            classify_action=dependencies.ledger_classify_action,
            classification_submitter=_ledger_classification_submitter(dependencies.account.profile_id, operation),
            exclusion_submitter=_ledger_exclusion_submitter(profile_id, operation),
            # Import, invoice entry and evidence each carry the operator's own
            # input -- a path, a typed invoice, a document -- so the launcher
            # gives only the door and the operator supplies the rest.
            import_door=LedgerImportDoor(profile_id=profile_id, operation=operation),
            invoice_add_door=ledger_invoice_add_door(profile_id, operation),
            evidence_door=LedgerEvidenceDoor(profile_id=profile_id, operation=operation),
            refresh=ledger_workspace_refresh(profile_id, capture_ledger),
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
            calendar_recovery_handoff=_calendar_work_create_handoff(
                bucket_id=_required_projection(current[0].declarations, "Declarations").bucket_id,
                actor=dependencies.account.profile_overview.label,
            ),
        )(context)

    return create


def _calendar_work_create_handoff(*, bucket_id: str, actor: str) -> CalendarRecoveryHandoffV1:
    """Bind the calendar's "create this declaration" action to the door ``modelo work create`` uses.

    The calendar controller has already refused an action whose bound
    arguments contradict its row, so the row's own address is the address the
    action names. A refusal -- setup not complete, the modelo not applying to
    this profile -- is raised as the application's typed error, for the
    calendar to show as itself.
    """

    def create(action: DeclaredNextAction, entry: DeclarationsCalendarEntryRefV1, /) -> None:
        from ...application.modelo.profile_readiness_gate import load_modelo_work_profile
        from ...application.modelo.work_addressing import ensure_modelo_work_unit_for_active_target
        from ...application.modelo.work_create_policy import guard_active_profile_foral_ccaa
        from ...domain.calculations.registry.authority import bundled_indexed_authority
        from ..adapter_composition import build_work_lifecycle_ports

        if action.action.action_id != "operator.modelo.work.create":
            raise ValueError("the calendar handoff only creates declarations")
        with bundled_indexed_authority().operation() as operation:
            profile = load_modelo_work_profile(
                bucket_id=bucket_id,
                profile_decode_context=operation.profile_decode_context(),
            )
            guard_active_profile_foral_ccaa(profile.record if profile is not None else None)
            ports = build_work_lifecycle_ports(bucket_id=bucket_id)
            ensure_modelo_work_unit_for_active_target(
                bucket_id=bucket_id,
                modelo=str(entry.modelo),
                filing_year=entry.filing_year,
                period=entry.period,
                registry_revision_id=None,
                actor=actor,
                catalogue=ports.work_unit_repository.load(),
                ports=ports,
                profile=profile,
            )

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


def resolve_modelo_workspace_static_inspection(
    unit: WorkUnit, *, operation: PinnedAuthorityOperation, output_language: OutputLanguage
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

    return resolve_static_inspection_result(
        ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(
                work_unit_id=unit.work_unit_id,
                bucket_id=unit.bucket_id,
            )
        ),
        bucket_id=unit.bucket_id,
        catalogue_repository=WorkUnitCatalogueRepository(bucket_id=unit.bucket_id),
        authority=operation,
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
    from ...adapters.outbound.fx.ecb_provider import default_ecb_rate_provider
    from ...application.exchange_rate_provider import bind_exchange_rate_provider_factory
    from ...core.config import load_settings, override_settings
    from ...core.storage_taxonomy import StorageCategory
    from ...core.storage_taxonomy_locations import STORAGE_TAXONOMY, storage_location
    from ..adapter_composition import profile_adapter_composition

    storage_root = root / "cadrumo-storage"
    secret_field = STORAGE_TAXONOMY[StorageCategory.SECRETS].settings_field
    if secret_field is None:
        message = "the declared secret storage category has no settings field"
        raise InternalInvariantError(message)
    secret_path = root / storage_location(StorageCategory.SECRETS).relative_path()
    with ExitStack() as composition:
        composition.enter_context(
            override_settings(
                cadrumo_local_storage_root=storage_root,
                cadrumo_active_profile=None,
                cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
                cadrumo_profile_kdf_measure_calibration=False,
                **{secret_field: secret_path},
            )
        )
        composition.enter_context(bind_exchange_rate_provider_factory(default_ecb_rate_provider))
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
    from ...adapters.persistence.storage.operator_scope import build_operator_scope_ports
    from ...domain.calculations.registry.authority import bundled_indexed_authority
    from ..operation_composition import compose_operation_dependencies

    with bundled_indexed_authority().operation() as authority_operation:
        services = compose_operation_dependencies(
            authority_operation=authority_operation,
            operator_scope_ports=build_operator_scope_ports(),
        )
        try:
            yield TuiOperationCompositionV1(
                services=services,
                public_contracts=services.public_contracts,
                authority_operation=authority_operation,
                event_loop=asyncio.get_running_loop(),
            )
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
        if refresh_destinations is None:
            raise InternalInvariantError("destination refresh requested without a refresh provider")
        refreshed_admissions, refreshed_factories = refresh_destinations()
        admissions = {"workbench.home": _available_admission("workbench.home"), **refreshed_admissions}
        return build_destination_catalogue(
            admissions=admissions,
            factories={"workbench.home": home_factory, **refreshed_factories},
            action_candidates=_admitted_candidates(inputs.action_candidates, admissions),
        )

    return InstalledWorkbenchRootCompositionV1(
        destination_catalogue=build_destination_catalogue(
            admissions=inputs.admissions,
            factories=factories,
            action_candidates=_admitted_candidates(inputs.action_candidates, inputs.admissions),
        ),
        admissions=inputs.admissions,
        refresh_home=inputs.refresh_home,
        search_inputs=inputs.search_inputs,
        refresh_search_inputs=inputs.refresh_search_inputs,
        refresh_destination_catalogue=rebuild if refresh_destinations is not None else None,
        account_factories=inputs.account_factories,
        read_account_session=inputs.read_account_session,
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
    from .app import CadrumoTuiApp, RootBindingV1

    async with operation_services_scope() as operation_runtime:
        if workbench_root_inputs_provider is None:
            return await CadrumoTuiApp(services=operation_runtime.services).run_async(
                headless=headless,
                auto_pilot=auto_pilot,
            )
        provider = workbench_root_inputs_provider

        def load_root() -> RootBindingV1:
            """Build the root on a worker thread: the first capture is the slow part."""
            root = compose_installed_workbench_root(provider(operation_runtime))
            service = None if root.search_inputs is None else compose_installed_workbench_search(root.search_inputs)

            def refresh_search() -> WorkbenchSearchDoorV1:
                refreshed_inputs = root.refresh_search_inputs()
                if refreshed_inputs is None:
                    raise InternalInvariantError(
                        "installed workbench search is unavailable in the refreshed generation"
                    )
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

            return RootBindingV1(
                destination_catalogue=root.destination_catalogue,
                refresh_home=root.refresh_home,
                workbench_search_service=service,
                refresh_workbench_search=refresh_search,
                refresh_destination_catalogue=root.refresh_destination_catalogue,
                account_factories=root.account_factories,
                read_account_session=root.read_account_session,
            )

        return await CadrumoTuiApp(services=operation_runtime.services, load_root=load_root).run_async(
            headless=headless, auto_pilot=auto_pilot
        )


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


TUI_SELF_TEST_FLAG = "--self-test"
TUI_MODULE_ARGUMENT_ERROR_EXIT_CODE = 2


class TuiModuleArgumentError(CadrumoError):
    """Arguments outside the independent TUI root's closed invocation surface."""


def run_module(
    arguments: list[str],
    *,
    workbench_root_inputs_provider: InstalledWorkbenchRootInputsProviderV1 | None = None,
) -> int:
    """Start the root session from ``python -m``, retaining only the self-test flag.

    The argument surface and its refusal live here rather than in
    ``__main__.py``: a module executed as ``__main__`` carries that module
    name, so an error class defined there could never resolve the error code
    the registry declares for it.
    """
    if arguments not in ([], [TUI_SELF_TEST_FLAG]):
        raise TuiModuleArgumentError(f"unrecognised TUI module arguments: {arguments!r}")
    return main(
        headless=arguments == [TUI_SELF_TEST_FLAG],
        workbench_root_inputs_provider=workbench_root_inputs_provider,
    )


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
    from ...adapters.outbound.fx.ecb_provider import default_ecb_rate_provider
    from ...application.exchange_rate_provider import bind_exchange_rate_provider_factory
    from ...core.logging import configure_logging

    # Importing a module no longer configures logging, so the host does it
    # before anything records; earlier INFO records would otherwise be lost.
    configure_logging()
    if workbench_root_inputs_provider is None:
        from .installed_session import run_installed_workbench_session

        return run_installed_workbench_session(headless=headless, auto_pilot=auto_pilot)
    # Bound before the loop starts, because asyncio.run copies the current context.
    with bind_exchange_rate_provider_factory(default_ecb_rate_provider):
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
    "TUI_MODULE_ARGUMENT_ERROR_EXIT_CODE",
    "TUI_SELF_TEST_FLAG",
    "AuthenticatedSessionRecomposeDoorV1",
    "InstalledWorkbenchAccountInputsV1",
    "InstalledWorkbenchFactoryDependenciesV1",
    "InstalledWorkbenchGenerationProviderV1",
    "InstalledWorkbenchRootCompositionV1",
    "InstalledWorkbenchRootInputsProviderV1",
    "InstalledWorkbenchRootInputsV1",
    "InstalledWorkbenchSearchInputsProviderV1",
    "TuiModuleArgumentError",
    "TuiOperationCompositionV1",
    "compose_installed_workbench_generation_provider",
    "compose_installed_workbench_root",
    "compose_installed_workbench_search",
    "compose_local_reader_page",
    "compose_secure_profile_workbench_generation_provider",
    "live_account_session_reader",
    "main",
    "operation_services_scope",
    "profile_storage_scope",
    "resolve_modelo_workspace_static_inspection",
    "run_authenticated_workbench_sessions",
    "run_module",
]
