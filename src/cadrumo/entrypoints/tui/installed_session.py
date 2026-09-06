"""Production composition for one installed ``aeat --tui`` workbench session.

This is the seam the installed process actually starts through. It owns the
order of the session rather than any behaviour of its own: bind the adapter
inventory once, take one truthful profile-inventory observation, run the
existing credential journey that observation calls for, and only then bind
the authenticated generation provider the root shell consumes.

Three boundaries are deliberate.

The credential journeys are the EXISTING screens. Registration, login and
passphrase rotation are composed from their owning packages through their
published doors; nothing here re-implements a credential surface, retains a
passphrase, or holds recovery material.

Authentication happens OUTSIDE the root application. A credential screen is a
whole Textual session, so it cannot run inside the root's event loop; the
loop below therefore alternates bootstrap sessions and workbench sessions in
this synchronous frame, which is also what makes sign-out, handover, rotation
and expiry return to a genuinely fresh inventory read rather than reusing the
former profile-bound composition.

Availability stays truthful. A degraded or concurrently-changing profile
inventory is reported as such and refuses the session; it never renders as an
empty workbench, and an abandoned credential screen is an ordinary outcome
rather than an error.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...application.search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from ...application.user_profile.workbench_bootstrap import (
    WorkbenchBootstrapInventoryState,
    WorkbenchBootstrapSessionState,
    WorkbenchBootstrapV1,
    WorkbenchRegistrationRequiredV1,
)
from .bootstrap import run_workbench_bootstrap
from .launcher import (
    InstalledWorkbenchAccountInputsV1,
    InstalledWorkbenchFactoryDependenciesV1,
    InstalledWorkbenchRootInputsProviderV1,
    InstalledWorkbenchRootInputsV1,
    TuiOperationCompositionV1,
    compose_installed_workbench_generation_provider,
    compose_secure_profile_workbench_generation_provider,
    run_authenticated_workbench_sessions,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from textual.app import AutopilotCallbackType

    from ...application.user_profile.login_interaction import ProfileLoginChoice
    from ...application.user_profile.login_session import ProfileLoginOutcome
    from ...application.user_profile.overview import ProfileOverview
    from .secret.login import LoginScreen

SESSION_COMPLETED = 0
"""The session ran to a clean end, including an operator who declined it."""

SESSION_INVENTORY_UNAVAILABLE = 1
"""The profile inventory could not be read truthfully, so nothing was served."""

_LEDGER_REVIEW_ACTION = "operator.ledger.review"
_LEDGER_EVIDENCE_ACTION = "operator.ledger.evidence.review.list"
_LEDGER_CLASSIFY_ACTION = "operator.ledger.classify"
_LEDGER_LINK_ACTION = "operator.ledger.link"
_DECLARATIONS_WORK_ACTION = "operator.modelo.work.list"
_DECLARATIONS_REVISIONS_ACTION = "operator.modelo.work.revisions"
_DECLARATIONS_FILING_ACTION = "operator.modelo.filing_record.list"


@dataclass(frozen=True, slots=True)
class InstalledBootstrapObservationV1:
    """One bootstrap pass and whether it created a profile along the way.

    The created flag is what separates "the operator registered and can now
    sign in" from "the operator left the registration screen", which the
    bootstrap state alone cannot say: both end on an inventory read that was
    empty when it was taken.
    """

    state: WorkbenchBootstrapV1
    profile_registered: bool = False


def compose_authenticated_account_inputs(
    *,
    profile_id: str,
    profile_label: str,
    login_choices: Sequence[ProfileLoginChoice],
) -> InstalledWorkbenchAccountInputsV1:
    """Bind the account doors of one already-authenticated profile.

    Every door here is the canonical application or credential-screen owner.
    Composing them performs no write and acquires no credential: the profile
    record read below is the projection the Profile destination renders, and
    the remaining doors run only when the operator invokes them.
    """
    from ...application.user_profile.fact_write import apply_manager_profile_field_mutation
    from ...application.user_profile.login_interaction import attempt_profile_login
    from ...application.user_profile.overview import build_profile_overview
    from ...application.user_profile.profile_record_repository import ProfileRecordRepository
    from ...core.credentials import assess_profile_password
    from .secret.passphrase import build_profile_passphrase_change_door

    repository = ProfileRecordRepository.for_current_session(profile_id)

    def persist_profile_field(path: str, value: str) -> ProfileOverview:
        applied = apply_manager_profile_field_mutation(profile_id=profile_id, path=path, value=value)
        return build_profile_overview(applied, label=profile_label)

    return InstalledWorkbenchAccountInputsV1(
        profile_id=profile_id,
        profile_overview=build_profile_overview(repository.load(profile_id), label=profile_label),
        persist_profile_field=persist_profile_field,
        login_choices=tuple(login_choices),
        authenticate=attempt_profile_login,
        assess_password=assess_profile_password,
        rotate_password=build_profile_passphrase_change_door(profile_id),
    )


def compose_authenticated_root_inputs_provider(
    *,
    profile_id: str,
    profile_label: str,
    login_choices: Sequence[ProfileLoginChoice],
) -> InstalledWorkbenchRootInputsProviderV1:
    """Compose the installed root provider for one authenticated profile."""
    from ...application.operator_actions.catalogue import lookup_action
    from ...application.operator_actions.models import ActionReference

    def action(action_id: str) -> ActionReference:
        return ActionReference(action_id=lookup_action(action_id).action_id)

    dependencies = InstalledWorkbenchFactoryDependenciesV1(
        account=compose_authenticated_account_inputs(
            profile_id=profile_id,
            profile_label=profile_label,
            login_choices=login_choices,
        ),
        profile_admission=WorkbenchDestinationAdmission(
            destination="workbench.profile",
            state=WorkbenchDestinationAdmissionState.AVAILABLE,
        ),
        ledger_review_action=action(_LEDGER_REVIEW_ACTION),
        ledger_evidence_action=action(_LEDGER_EVIDENCE_ACTION),
        ledger_classify_action=action(_LEDGER_CLASSIFY_ACTION),
        ledger_link_action=action(_LEDGER_LINK_ACTION),
        declarations_work_action=action(_DECLARATIONS_WORK_ACTION),
        declarations_revisions_action=action(_DECLARATIONS_REVISIONS_ACTION),
        declarations_filing_action=action(_DECLARATIONS_FILING_ACTION),
    )

    def provide(operation_runtime: TuiOperationCompositionV1) -> InstalledWorkbenchRootInputsV1:
        """Bind the generation to the exact contracts this session composed.

        The AEAT Sync workspace offers only registered operations, so its
        projection cannot be built before the operation platform exists. The
        generation provider is therefore composed here, per session, rather
        than ahead of the runtime it has to agree with.
        """
        return compose_installed_workbench_generation_provider(
            compose_secure_profile_workbench_generation_provider(
                profile_id=profile_id,
                profile_label=profile_label,
                operation_contracts=operation_runtime.public_contracts,
            ),
            dependencies,
        )(operation_runtime)

    return provide


def observe_installed_bootstrap(*, allow_credential_screens: bool = True) -> InstalledBootstrapObservationV1:
    """Take one truthful inventory observation and run the journey it names.

    Registration and login are the existing full-screen owners, each run as
    its own session. ``allow_credential_screens`` is lowered for a headless
    run: nobody is there to type a passphrase, so opening either screen would
    block forever, and creating a profile would be a side effect of merely
    proving the artifact starts. A lowered run reports the inventory it
    observed and stops rather than pretending to authenticate.
    """
    from ...core.credentials import assess_profile_password
    from .secret.credentials import run_credential_screen
    from .secret.registration import RegistrationScreen, build_profile_registration_attempt

    registered: list[bool] = [False]

    def run_login(screen: LoginScreen, /) -> ProfileLoginOutcome | None:
        if not allow_credential_screens:
            return None
        return run_credential_screen(screen)

    def register(_requirement: WorkbenchRegistrationRequiredV1, /) -> None:
        if not allow_credential_screens:
            return
        outcome = run_credential_screen(
            RegistrationScreen(
                assess=assess_profile_password,
                register=build_profile_registration_attempt,
            )
        )
        registered[0] = outcome is not None

    def observed(_preparation: WorkbenchBootstrapV1, /) -> None:
        """Accept a closed state; the caller reads the returned observation."""

    state = run_workbench_bootstrap(
        run_login=run_login,
        registration_door=register,
        authenticated_door=observed,
        cancelled_door=observed,
        degraded_door=observed,
    )
    return InstalledBootstrapObservationV1(state=state, profile_registered=registered[0])


def run_installed_workbench_session(
    *,
    headless: bool = False,
    auto_pilot: AutopilotCallbackType | None = None,
) -> int:
    """Run installed workbench sessions until the operator ends the process.

    Each pass reads the profile inventory afresh. That is what makes sign-out,
    user handover, password rotation and session expiry return the operator to
    a real credential decision instead of a stale profile-bound composition.
    """
    from ..adapter_composition import profile_adapter_composition

    with profile_adapter_composition():
        while True:
            observation = observe_installed_bootstrap(allow_credential_screens=not headless)
            state = observation.state
            if state.inventory_state in {
                WorkbenchBootstrapInventoryState.CONCURRENT_CHANGE,
                WorkbenchBootstrapInventoryState.DEGRADED,
            }:
                sys.stderr.write(f"{state.reason_code}\n")
                return SESSION_INVENTORY_UNAVAILABLE
            if state.inventory_state is WorkbenchBootstrapInventoryState.EMPTY:
                if observation.profile_registered:
                    continue
                return SESSION_COMPLETED
            if state.session_state is WorkbenchBootstrapSessionState.CANCELLED:
                return SESSION_COMPLETED
            profile_id = state.selected_profile_id
            profile_label = state.selected_profile_label
            if profile_id is None or profile_label is None:
                return SESSION_COMPLETED
            recompose = asyncio.run(
                run_authenticated_workbench_sessions(
                    headless=headless,
                    auto_pilot=auto_pilot,
                    workbench_root_inputs_provider=compose_authenticated_root_inputs_provider(
                        profile_id=profile_id,
                        profile_label=profile_label,
                        login_choices=state.choices,
                    ),
                )
            )
            if recompose is None or headless:
                return SESSION_COMPLETED


__all__ = [
    "SESSION_COMPLETED",
    "SESSION_INVENTORY_UNAVAILABLE",
    "InstalledBootstrapObservationV1",
    "compose_authenticated_account_inputs",
    "compose_authenticated_root_inputs_provider",
    "observe_installed_bootstrap",
    "run_installed_workbench_session",
]
