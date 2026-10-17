"""Join runtime-owned captures to the existing immutable workbench screens."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING

from textual.screen import Screen

from cadrumo.application.modelo.declaration_summary import DeclarationSummaryState
from cadrumo.application.modelo.declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
)
from cadrumo.application.modelo.declarations_workspace_contracts import (
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceProjectionV1,
)
from cadrumo.application.modelo.workbench_read import ModeloWorkbenchFormReadV1
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operator_actions.catalogue import lookup_action
from cadrumo.application.operator_actions.models import ActionReference
from cadrumo.application.search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from cadrumo.application.user_profile.view_operation import ProfileViewPageKind
from cadrumo.core.config import load_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError, AccountSessionUnavailableError
from cadrumo.entrypoints.tui.aeat_sync.routes import aeat_sync_screen_factory
from cadrumo.entrypoints.tui.app import RootBindingV1, RootPresentationV1
from cadrumo.entrypoints.tui.declarations.models import DeclarationsWorkspaceWiringV1
from cadrumo.entrypoints.tui.declarations.routes import declarations_screen_factory
from cadrumo.entrypoints.tui.google_saved_review import GoogleSavedReviewScreen
from cadrumo.entrypoints.tui.historical_export import HistoricalFilingExportScreen
from cadrumo.entrypoints.tui.home import HomeScreen
from cadrumo.entrypoints.tui.installation.destination import installation_screen_factory
from cadrumo.entrypoints.tui.ledger.routes import ledger_screen_factory
from cadrumo.entrypoints.tui.modelo.lifecycle import ModeloWorkspaceLifecycleDoor
from cadrumo.entrypoints.tui.modelo.workbench.factory import compose_installed_modelo_workbench_factory
from cadrumo.entrypoints.tui.navigation import TuiScreenContextV1, TuiScreenFactoryV1, build_destination_catalogue
from cadrumo.entrypoints.tui.operations.catalogue import OperationCatalogueSourceV1
from cadrumo.entrypoints.tui.operations.destination import OperationsDestinationV1
from cadrumo.entrypoints.tui.reconciliation_export import ReconciliationExportScreen
from cadrumo.entrypoints.tui.reference.destination import reference_screen_factory
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.workbench_generation import read_workbench_generation

from .aeat_sync.runtime_handoff import compose_runtime_aeat_sync_handoff
from .modelo.runtime_lifecycle import compose_runtime_modelo_lifecycle_door
from .modelo.runtime_work_create import compose_runtime_calendar_create_handoff, compose_runtime_work_create_handoff
from .modelo.runtime_workbench_reads import RuntimeModeloWorkbenchSource
from .profile.manager_client import ProfileManagerClientComposition
from .profile.overview_client import read_profile_overview
from .runtime_account import compose_runtime_account_factories
from .runtime_account_session import (
    read_runtime_account_session,
    runtime_account_activity_reporter,
    runtime_account_session_reader,
)
from .runtime_actividad_asset import compose_runtime_activity_asset_actions
from .runtime_evidence import RuntimeEvidenceTuiDoorV1
from .runtime_invoice_add import compose_runtime_invoice_add_door
from .runtime_ledger_import import compose_runtime_ledger_import_door
from .runtime_own_accounts import compose_runtime_own_account_door

if TYPE_CHECKING:
    from cadrumo.application.aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
    from cadrumo.application.operations.registry import OperationRegistry
    from cadrumo.application.user_profile.overview import ProfileOverview
    from cadrumo.application.workbench_generation_contracts import WorkbenchGenerationV1
    from cadrumo.entrypoints.tui.navigation import TuiDestinationCatalogueV1
    from cadrumo.entrypoints.tui.profile.overview import ProfileManagerScreen
    from cadrumo_client.transport.frontend_client import FrontendClient

    from .runtime_access_management import RecoveryClientOpener
    from .secret.automation_requester import HumanAutomationRequesterFactory


def _action(action_id: str) -> ActionReference:
    return ActionReference(action_id=lookup_action(action_id).action_id)


def _available(destination: str) -> WorkbenchDestinationAdmission:
    return WorkbenchDestinationAdmission(destination=destination, state=WorkbenchDestinationAdmissionState.AVAILABLE)


@dataclass(frozen=True, slots=True)
class _Capture:
    """Individually guarded reads; these do not claim a shared storage revision."""

    generation: WorkbenchGenerationV1
    profile: ProfileOverview
    language_epoch: int


class _DeclarationDestination:
    """Keep declaration and calendar factories on their latest capture."""

    def __init__(self, root: RuntimeWorkbenchRoot, generation: WorkbenchGenerationV1) -> None:
        self._root = root
        self._current = generation
        self._lock = Lock()

    def refresh(self) -> WorkbenchGenerationV1:
        captured = self._root._read().generation
        self._root._require_binding()
        with self._lock:
            self._current = captured
        return captured

    def latest(self) -> tuple[DeclarationsWorkspaceProjectionV1, DeclarationsCalendarProjectionV1 | None]:
        self._root._require_binding()
        with self._lock:
            captured = self._current
        declarations = captured.declarations.projection
        if (
            captured.declarations_admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE
            or declarations is None
        ):
            raise RefusalError(RefusalCode.UNAVAILABLE)
        return declarations, captured.declarations_calendar.projection

    def lifecycle_door(
        self,
        declaration: DeclarationsWorkspaceDeclarationRefV1,
        read: ModeloWorkbenchFormReadV1 | None,
    ) -> ModeloWorkspaceLifecycleDoor:
        return compose_runtime_modelo_lifecycle_door(
            self._root._client,
            declaration,
            calculation_revision_id=None if read is None else read.calculation_revision_id,
            verification_report_id=None if read is None else read.verification_report_id,
            asks_modelo_390=read is not None and read.asks_modelo_390,
            refresh_after_success=self.refresh,
        )

    def workspace_factory(self, declaration: DeclarationsWorkspaceDeclarationRefV1, /) -> Screen[None]:
        declarations, _ = self.latest()
        return compose_installed_modelo_workbench_factory(
            declarations=declarations.declarations,
            source=lambda selected: RuntimeModeloWorkbenchSource(self._root._client, selected),
            door=self.lifecycle_door,
            own_accounts=compose_runtime_own_account_door(client=self._root._client, profile_label=self._root._label),
            native_review=lambda revision_id: GoogleSavedReviewScreen(self._root._client, revision_id),
        )(declaration)

    def calendar_declaration(
        self, entry: DeclarationsCalendarEntryRefV1
    ) -> DeclarationsWorkspaceDeclarationRefV1 | None:
        declarations, _ = self.latest()
        matches = tuple(
            ref
            for ref in declarations.declarations
            if (str(ref.modelo), ref.filing_year, ref.period.registry_token) == entry.semantic_key()
            and (ref.summary is None or ref.summary.state is not DeclarationSummaryState.UNREADABLE)
        )
        return matches[0] if len(matches) == 1 else None

    def calendar_factory(self, entry: DeclarationsCalendarEntryRefV1, /) -> Screen[None] | None:
        declaration = self.calendar_declaration(entry)
        return None if declaration is None else self.workspace_factory(declaration)

    def factory(self, context: TuiScreenContextV1) -> Screen[None]:
        declarations, calendar = self.latest()
        create_work = compose_runtime_work_create_handoff(self._root._client, refresh_after_success=self.refresh)
        return declarations_screen_factory(
            declarations,
            DeclarationsWorkspaceWiringV1(
                work_action=_action("operator.modelo.work.list"),
                revisions_action=_action("operator.modelo.work.revisions"),
                filing_action=_action("operator.modelo.filing_record.list"),
                modelo_workspace_factory=self.workspace_factory,
                filing_export_factory=lambda filing: HistoricalFilingExportScreen(
                    self._root._client, filing.filing_record_id
                ),
                filing_google_review_factory=lambda filing: GoogleSavedReviewScreen(
                    self._root._client, filing.calculation_revision_id, filing_record_id=filing.filing_record_id
                ),
                reconciliation_export_factory=lambda filing: ReconciliationExportScreen(
                    self._root._client, filing.work_unit_id
                ),
                calendar_projection=calendar,
                calendar_entry_handoff=self.calendar_factory,
                calendar_entry_can_open=lambda entry: self.calendar_declaration(entry) is not None,
                calendar_recovery_handoff=compose_runtime_calendar_create_handoff(create_work),
                work_create_handoff=create_work,
                creation_targets=declarations.creation_targets,
                refresh_data=self.latest,
            ),
        )(context)


class RuntimeWorkbenchRoot:
    """Keep one exact client's capture and refresh doors without local custody.

    Construction and ``load`` run off the UI loop. Screen factories consume
    only captured values. Mutations are supplied individually by registered
    runtime operations; a missing mutation door stays unavailable.
    """

    def __init__(
        self,
        client: FrontendClient,
        *,
        profile_label: str,
        output_language: OutputLanguage,
        open_recovery_client: RecoveryClientOpener,
        operation_registry: Callable[[], OperationRegistry],
        requester_factory: HumanAutomationRequesterFactory | None = None,
    ) -> None:
        """Pin a TUI client and its explicit capture language without performing I/O.

        ``operation_registry`` is the installed session's, handed down so that
        this root composes nothing; it is called on first use and the session
        composes it once, however many generations this root captures.
        """
        if client.frontend is not OperationFrontendProjection.TUI:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._client = client
        self._operations = OperationsDestinationV1(client, OperationCatalogueSourceV1(operation_registry))
        self._profile_id, self._session_id = client.profile_id, client.session_id
        self._label, self._language = profile_label, output_language
        self._open_recovery_client = open_recovery_client
        self._requester_factory = requester_factory
        self._language_guard = Lock()
        self._language_epoch = 0
        self._latest_profile: ProfileOverview | None = None

    def set_output_language(self, language: OutputLanguage) -> None:
        """Update future requests and profile panes through one canonical read off-loop."""
        self._require_binding()
        with self._language_guard:
            self._language = language
            self._language_epoch += 1
            self._latest_profile = None
            epoch = self._language_epoch
        profile = read_profile_overview(self._client, profile_label=self._label, output_language=language)
        self._require_binding()
        self._adopt_language_profile(profile, epoch)

    def _adopt_language_profile(self, profile: ProfileOverview, epoch: int) -> None:
        """Fence the result and keep any newer same-epoch read cached during I/O."""
        with self._language_guard:
            if epoch != self._language_epoch or profile.profile_id != str(self._profile_id):
                raise RefusalError(RefusalCode.UNAVAILABLE)
            if self._latest_profile is None or profile.record_revision >= self._latest_profile.record_revision:
                self._latest_profile = profile

    def _require_binding(self) -> None:
        try:
            if (
                self._client.profile_id != self._profile_id
                or self._client.session_id != self._session_id
                or self._client.frontend is not OperationFrontendProjection.TUI
            ):
                raise AccountSessionExpiredError()
        except (FrontendRefusedError, RefusalError) as error:
            raise AccountSessionUnavailableError() from error

    def _read(self, initial_profile: ProfileOverview | None = None) -> _Capture:
        self._require_binding()
        with self._language_guard:
            language, epoch = self._language, self._language_epoch
        try:
            generation = read_workbench_generation(self._client, output_language=language)
            profile = initial_profile
            if profile is not None:
                # Routing already captured this overview. Revalidate its exact
                # provenance after generation before avoiding another full stream.
                current = self._client.read_profile_view((ProfileViewPageKind.STATUS,), output_language=language)
                if (
                    str(current.profile_id) != profile.profile_id
                    or current.record_revision != profile.record_revision
                    or current.content_digest != profile.content_digest
                    or current.setup_state is not profile.setup_state
                ):
                    profile = None
            if profile is None:
                profile = read_profile_overview(self._client, profile_label=self._label, output_language=language)
        except (FrontendRefusedError, RefusalError):
            # A permission/readiness refusal does not imply expiry. A fresh
            # status check distinguishes it from a lost originating session.
            read_runtime_account_session(
                self._client, profile_id=self._profile_id, session_id=self._session_id, profile_label=self._label
            )
            raise
        read_runtime_account_session(
            self._client, profile_id=self._profile_id, session_id=self._session_id, profile_label=self._label
        )
        if generation.home.projection is None or profile.profile_id != str(self._profile_id):
            raise RefusalError(RefusalCode.UNAVAILABLE)
        with self._language_guard:
            if epoch != self._language_epoch:
                raise RefusalError(RefusalCode.UNAVAILABLE)
            if self._latest_profile is None or profile.record_revision >= self._latest_profile.record_revision:
                self._latest_profile = profile
        return _Capture(generation, profile, epoch)

    def _destinations(
        self, generation: WorkbenchGenerationV1, profile_factory: TuiScreenFactoryV1
    ) -> TuiDestinationCatalogueV1:
        admissions: dict[str, WorkbenchDestinationAdmission] = {
            "workbench.home": _available("workbench.home"),
            "workbench.profile": _available("workbench.profile"),
            "workbench.operations": _available("workbench.operations"),
            "workbench.installation": _available("workbench.installation"),
            "workbench.reference": _available("workbench.reference"),
            "workbench.ledger": generation.ledger_admission,
            "workbench.declarations": generation.declarations_admission,
            "workbench.aeat_sync": generation.aeat_sync_admission,
            "workbench.withholding": WorkbenchDestinationAdmission(
                destination="workbench.withholding",
                state=WorkbenchDestinationAdmissionState.UNAVAILABLE,
                reason_code="workbench.withholding.runtime_unavailable",
            ),
        }

        factories = self._base_factories(generation, profile_factory)
        factories["workbench.operations"] = self._operations
        factories["workbench.installation"] = installation_screen_factory
        factories["workbench.reference"] = reference_screen_factory
        ledger = self._ledger_factory(generation)
        if ledger is not None:
            factories["workbench.ledger"] = ledger
        if generation.declarations_admission.state is WorkbenchDestinationAdmissionState.AVAILABLE:
            factories["workbench.declarations"] = _DeclarationDestination(self, generation).factory
        aeat_sync = self._aeat_sync_factory(generation)
        if aeat_sync is not None:
            factories["workbench.aeat_sync"] = aeat_sync
        return build_destination_catalogue(admissions=admissions, factories=factories)

    @staticmethod
    def _base_factories(
        generation: WorkbenchGenerationV1, profile_factory: TuiScreenFactoryV1
    ) -> dict[str, TuiScreenFactoryV1]:
        def home(context: TuiScreenContextV1) -> Screen[None]:
            if context.destination != "workbench.home" or generation.home.projection is None:
                raise RefusalError(RefusalCode.UNAVAILABLE)
            return HomeScreen(generation.home.projection)

        return {"workbench.home": home, "workbench.profile": profile_factory}

    def _ledger_factory(self, generation: WorkbenchGenerationV1) -> TuiScreenFactoryV1 | None:
        if generation.ledger_admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE:
            return None
        if generation.ledger.projection is None:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return ledger_screen_factory(
            generation.ledger.projection,
            review_action=_action("operator.ledger.review"),
            evidence_action=_action("operator.ledger.evidence.review.list"),
            activity_asset_actions=compose_runtime_activity_asset_actions(self._client, profile_label=self._label),
            invoice_add_door=compose_runtime_invoice_add_door(
                client=self._client,
                profile_label=self._label,
            ),
            evidence_door=RuntimeEvidenceTuiDoorV1(self._client, profile_label=self._label),
            own_account_door=compose_runtime_own_account_door(client=self._client, profile_label=self._label),
            import_door=compose_runtime_ledger_import_door(client=self._client, profile_label=self._label),
        )

    def _aeat_sync_factory(self, generation: WorkbenchGenerationV1) -> TuiScreenFactoryV1 | None:
        if generation.aeat_sync_admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE:
            return None
        if generation.aeat_sync.projection is None:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        operation_handoff, operation_contracts = compose_runtime_aeat_sync_handoff(
            self._client,
            output_root=load_settings().cadrumo_filed_declarations_dir,
        )

        def refresh_aeat_sync() -> AeatSyncWorkspaceProjectionV1:
            captured = self._read().generation
            self._require_binding()
            projection = captured.aeat_sync.projection
            if (
                captured.aeat_sync_admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE
                or projection is None
            ):
                raise RefusalError(RefusalCode.UNAVAILABLE)
            return projection

        return aeat_sync_screen_factory(
            generation.aeat_sync.projection,
            operation_handoff=operation_handoff,
            refresh_snapshot=refresh_aeat_sync,
            operation_contracts=operation_contracts,
            aeat_auth_setup=ProfileManagerClientComposition(
                self._client, profile_label=self._label, output_language=self._language
            ).auth_setup(),
        )

    def _presentation(self, capture: _Capture) -> RootPresentationV1:
        with self._language_guard:
            if capture.language_epoch != self._language_epoch:
                raise RefusalError(RefusalCode.UNAVAILABLE)
        generation = capture.generation
        home = generation.home.projection
        if home is None:
            raise RefusalError(RefusalCode.UNAVAILABLE)

        def profile(context: TuiScreenContextV1) -> ProfileManagerScreen:
            if context.destination != "workbench.profile":
                raise ValueError("profile factory requires its exact destination")
            self._require_binding()
            with self._language_guard:
                language, latest = self._language, self._latest_profile
            if latest is None:
                raise RefusalError(RefusalCode.UNAVAILABLE)
            return ProfileManagerClientComposition(
                self._client, profile_label=self._label, output_language=language
            ).compose_from_overview(latest)

        search = generation.search.projection
        presentation = RootPresentationV1(
            home=home,
            destination_catalogue=self._destinations(generation, profile),
            workbench_search_service=None if search is None else search.service(),
            account_factories=compose_runtime_account_factories(
                self._client,
                profile=profile,
                open_recovery_client=self._open_recovery_client,
                requester_factory=self._requester_factory,
                onboarding_pending=capture.profile.setup_state is ProfileSetupState.INCOMPLETE,
                on_language_changed=self.set_output_language,
            ),
        )
        with self._language_guard:
            if capture.language_epoch != self._language_epoch:
                raise RefusalError(RefusalCode.UNAVAILABLE)
        return presentation

    def load(self, *, initial_profile: ProfileOverview | None = None) -> RootBindingV1:
        """Read the first authorized generation, then join its existing screens."""
        first_capture = self._read(initial_profile)
        first = self._presentation(first_capture)
        pending = [first]
        pending_lock = Lock()

        def refresh_home() -> RootPresentationV1:
            self._require_binding()
            with pending_lock:
                if pending:
                    with self._language_guard:
                        current = self._language_epoch == first_capture.language_epoch
                    cached = pending.pop()
                    if current:
                        return cached
            # Nothing is published by the capturing thread. The root applies
            # Home, navigation, search and account factories together only
            # after checking that this session and navigation still own it.
            return self._presentation(self._read())

        return RootBindingV1(
            destination_catalogue=first.destination_catalogue,
            refresh_home=refresh_home,
            workbench_search_service=first.workbench_search_service,
            refresh_workbench_search=None,
            refresh_destination_catalogue=None,
            account_factories=first.account_factories,
            read_account_session=runtime_account_session_reader(
                self._client, profile_id=self._profile_id, profile_label=self._label
            ),
            note_activity=runtime_account_activity_reporter(self._client),
        )
