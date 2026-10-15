"""Open incomplete profile setup before capturing the operational workbench."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import TYPE_CHECKING

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from cadrumo.core.logging import get_logger
from cadrumo.core.startup_phase_log import startup_phase
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError, AccountSessionUnavailableError
from cadrumo.entrypoints.tui.app import RootBindingV1, RootPresentationV1
from cadrumo.entrypoints.tui.navigation import (
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
    build_destination_catalogue,
    declared_destination_ids,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .profile.overview_client import read_profile_overview
from .runtime_account_session import (
    read_runtime_account_session,
    runtime_account_activity_reporter,
    runtime_account_session_reader,
)

if TYPE_CHECKING:
    from cadrumo.application.operations.registry import OperationRegistry
    from cadrumo.application.overview.home import HomeAccountSession
    from cadrumo.application.user_profile.overview import ProfileOverview
    from cadrumo.core.external_constants import OutputLanguage
    from cadrumo.entrypoints.tui.profile.overview import ProfileManagerScreen
    from cadrumo_client.transport.frontend_client import FrontendClient

    from .runtime_access_management import RecoveryClientOpener
    from .runtime_workbench import RuntimeWorkbenchRoot
    from .secret.automation_requester import HumanAutomationRequesterFactory

_LOGGER = get_logger(__name__)


class RuntimeInitialRoot:
    """Retain one admitted client while deferring all generation reads until Home."""

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
        """Pin the admitted client and defer operational composition."""
        if client.frontend is not OperationFrontendProjection.TUI:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._client = client
        self._profile_id, self._session_id = client.profile_id, client.session_id
        self._label, self._language = profile_label, output_language
        self._open_recovery_client = open_recovery_client
        self._operation_registry = operation_registry
        self._requester_factory = requester_factory
        self._workbench_binding: RootBindingV1 | None = None
        self._workbench_root: RuntimeWorkbenchRoot | None = None
        self._language_guard = Lock()
        self._language_epoch = 0
        self._latest_profile: ProfileOverview | None = None

    def _set_output_language(self, language: OutputLanguage) -> None:
        """Refresh future captures off the UI loop without replacing mounted screens."""
        self._session()
        with self._language_guard:
            self._language = language
            self._language_epoch += 1
            self._latest_profile = None
            epoch = self._language_epoch
            workbench = self._workbench_root
        if workbench is not None:
            workbench.set_output_language(language)
        profile = read_profile_overview(self._client, profile_label=self._label, output_language=language)
        self._session()
        self._adopt_language_profile(profile, epoch)

    def _adopt_language_profile(self, profile: ProfileOverview, epoch: int) -> None:
        """Fence the result and keep any newer same-epoch read cached during I/O."""
        with self._language_guard:
            if epoch != self._language_epoch or profile.profile_id != str(self._profile_id):
                raise RefusalError(RefusalCode.UNAVAILABLE)
            if self._latest_profile is None or profile.record_revision >= self._latest_profile.record_revision:
                self._latest_profile = profile

    def _session(self) -> HomeAccountSession:
        return read_runtime_account_session(
            self._client, profile_id=self._profile_id, session_id=self._session_id, profile_label=self._label
        )

    def _workbench(self, initial_profile: ProfileOverview | None = None) -> RootBindingV1:
        self._session()
        if self._workbench_binding is not None:
            return self._workbench_binding
        with startup_phase(_LOGGER, "tui_workbench_load"):
            from .runtime_workbench import RuntimeWorkbenchRoot

            with self._language_guard:
                language = self._language
            workbench = RuntimeWorkbenchRoot(
                self._client,
                profile_label=self._label,
                output_language=language,
                open_recovery_client=self._open_recovery_client,
                operation_registry=self._operation_registry,
                requester_factory=self._requester_factory,
            )
            with self._language_guard:
                self._workbench_root = workbench
                current_language = self._language
            if current_language != language:
                workbench.set_output_language(current_language)
                initial_profile = None
            self._workbench_binding = workbench.load(initial_profile=initial_profile)
            return self._workbench_binding

    def load(self) -> RootBindingV1:
        """Select the initial destination from an authenticated profile view."""
        with startup_phase(_LOGGER, "tui_initial_profile"):
            with self._language_guard:
                language, epoch = self._language, self._language_epoch
            try:
                overview = read_profile_overview(self._client, profile_label=self._label, output_language=language)
            except (FrontendRefusedError, RefusalError):
                self._session()
                raise
            session = self._session()
            if overview.profile_id != str(self._profile_id):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            with self._language_guard:
                if epoch != self._language_epoch:
                    raise RefusalError(RefusalCode.UNAVAILABLE)
                self._latest_profile = overview
        if overview.setup_state is not ProfileSetupState.INCOMPLETE:
            return self._workbench(initial_profile=overview)

        from .profile.manager_client import ProfileManagerClientComposition
        from .runtime_account import compose_runtime_account_factories

        def profile(context: TuiScreenContextV1) -> ProfileManagerScreen:
            if context.destination != "workbench.profile":
                raise ValueError("profile factory requires its exact destination")
            try:
                if self._client.profile_id != self._profile_id or self._client.session_id != self._session_id:
                    raise AccountSessionExpiredError()
            except (FrontendRefusedError, RefusalError):
                raise AccountSessionUnavailableError() from None
            with self._language_guard:
                language, latest = self._language, self._latest_profile
            if latest is None:
                raise RefusalError(RefusalCode.UNAVAILABLE)
            return ProfileManagerClientComposition(
                self._client, profile_label=self._label, output_language=language
            ).compose_from_overview(latest)

        def refresh_home() -> RootPresentationV1:
            binding = self._workbench()
            presentation = binding.refresh_home()
            if not isinstance(presentation, RootPresentationV1):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            return presentation

        admissions = {
            destination: WorkbenchDestinationAdmission(
                destination=destination,
                state=(
                    WorkbenchDestinationAdmissionState.AVAILABLE
                    if destination == "workbench.profile"
                    else WorkbenchDestinationAdmissionState.NEVER_CAPTURED
                ),
                reason_code=None if destination == "workbench.profile" else "workbench.startup.pending",
            )
            for destination in declared_destination_ids()
        }
        return RootBindingV1(
            destination_catalogue=build_destination_catalogue(
                admissions=admissions, factories={"workbench.profile": profile}
            ),
            refresh_home=refresh_home,
            workbench_search_service=None,
            refresh_workbench_search=None,
            refresh_destination_catalogue=None,
            account_factories=compose_runtime_account_factories(
                self._client,
                profile=profile,
                open_recovery_client=self._open_recovery_client,
                requester_factory=self._requester_factory,
                on_language_changed=self._set_output_language,
            ),
            read_account_session=runtime_account_session_reader(
                self._client, profile_id=self._profile_id, profile_label=self._label
            ),
            initial_account_session=session,
            note_activity=runtime_account_activity_reporter(self._client),
            initial_destination=TuiNavigationTargetV1(
                destination="workbench.profile",
                focus=TuiFocusIdentityV1(destination="workbench.profile", semantic_key="profile.overview"),
            ),
        )


__all__ = ["RuntimeInitialRoot"]
