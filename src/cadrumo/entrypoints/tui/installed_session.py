"""Production composition for one installed ``aeat app tui`` workbench session.

This is the seam the installed process actually starts through. It owns the
order of the session rather than any behaviour of its own: bind the adapter
inventory once, read which profiles can be signed into, hand that target to
the shared admission door with this surface's credential screens as the
journey, and only then bind the authenticated generation provider the root
shell consumes.

Four boundaries are deliberate.

Admission is the APPLICATION's, not this module's. Whether a profile is
unlocked -- reused, resumed from its receipt, or freshly authenticated -- is
decided by :func:`~cadrumo.application.user_profile.session_admission.admit_profile_session`,
the same door the CLI calls. This surface once carried its own copy of that
sequence, which is how the two entry points came to disagree about what being
logged in means; the copy is gone and must not return.

The credential journeys are the EXISTING screens. Registration, login and
passphrase rotation are composed from their owning packages through their
published doors; nothing here re-implements a credential surface, retains a
passphrase, or holds recovery material.

Authentication happens OUTSIDE the root application. A credential screen is a
whole Textual session, so it cannot run inside the root's event loop; the
loop below therefore alternates credential sessions and workbench sessions in
this synchronous frame, which is also what makes sign-out, handover, rotation
and expiry return to a genuinely fresh inventory read rather than reusing the
former profile-bound composition. The session those screens establish is
published process-wide by the login services, so it survives the Textual
worker and event loop that produced it and is the same session a later CLI
invocation in the same process would see.

Availability stays truthful. A degraded or concurrently-changing profile
inventory is reported as such and refuses the session; it never renders as an
empty workbench, and an abandoned credential screen is an ordinary outcome
rather than an error.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from ...application.search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from ...application.user_profile.login_interaction import (
    ProfileLoginInventoryState,
    observe_profile_login_inventory,
)
from ...application.user_profile.session_admission import admit_profile_session
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
    from textual.app import AutopilotCallbackType

    from ...application.user_profile.login_interaction import ProfileLoginChoice, ProfileLoginInventoryV1
    from ...application.user_profile.login_session import ProfileLoginOutcome
    from ...application.user_profile.overview import ProfileOverview
    from ...application.user_profile.session_admission import (
        ProfileCredentialRequestV1,
        ProfileSessionAdmissionV1,
    )
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

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


def compose_authenticated_account_inputs(
    *,
    profile_id: str,
    profile_label: str,
    login_choices: Sequence[ProfileLoginChoice],
    operation: PinnedAuthorityOperation,
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

    profile_decode_context = operation.profile_decode_context()
    repository = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=profile_decode_context,
    )
    profile_schema = profile_decode_context.schema

    def persist_profile_field(path: str, value: str) -> ProfileOverview:
        applied = apply_manager_profile_field_mutation(
            profile_id=profile_id,
            path=path,
            value=value,
            profile_decode_context=profile_decode_context,
        )
        return build_profile_overview(applied, label=profile_label, schema=profile_schema)

    def complete_setup() -> ProfileOverview:
        """Promote setup to complete through the repository door ``complete-setup`` uses."""
        profiles = ProfileRecordRepository.for_current_session(
            profile_id,
            profile_decode_context=profile_decode_context,
        )
        current = profiles.load(profile_id)
        promoted = profiles.complete_setup(
            profile_id,
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
        )
        return build_profile_overview(promoted, label=profile_label, schema=profile_schema)

    def authenticate(candidate_profile_id: str, passphrase: str):
        """Authenticate through the same generation-pinned decode context."""
        return attempt_profile_login(
            candidate_profile_id,
            passphrase,
            profile_decode_context=profile_decode_context,
        )

    return InstalledWorkbenchAccountInputsV1(
        profile_id=profile_id,
        profile_overview=build_profile_overview(
            repository.load(profile_id),
            label=profile_label,
            schema=profile_schema,
        ),
        persist_profile_field=persist_profile_field,
        complete_setup=complete_setup,
        login_choices=tuple(login_choices),
        authenticate=authenticate,
        assess_password=assess_profile_password,
        rotate_password=build_profile_passphrase_change_door(
            profile_id,
            profile_decode_context=profile_decode_context,
        ),
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

    def provide(operation_runtime: TuiOperationCompositionV1) -> InstalledWorkbenchRootInputsV1:
        """Bind the generation to the exact contracts this session composed.

        The AEAT Sync workspace offers only registered operations, so its
        projection cannot be built before the operation platform exists. The
        generation provider is therefore composed here, per session, rather
        than ahead of the runtime it has to agree with.
        """
        operation = operation_runtime.authority_operation
        dependencies = InstalledWorkbenchFactoryDependenciesV1(
            account=compose_authenticated_account_inputs(
                profile_id=profile_id,
                profile_label=profile_label,
                login_choices=login_choices,
                operation=operation,
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
        return compose_installed_workbench_generation_provider(
            compose_secure_profile_workbench_generation_provider(
                profile_id=profile_id,
                profile_label=profile_label,
                operation=operation,
                operation_contracts=operation_runtime.public_contracts,
            ),
            dependencies,
        )(operation_runtime)

    return provide


def _login_credential_journey(
    *,
    choices: Sequence[ProfileLoginChoice],
    preselected_profile_id: str | None,
) -> Callable[[ProfileCredentialRequestV1], ProfileLoginOutcome | None]:
    """Offer the existing Login screen as the admission door's credential journey.

    The screen is the operator's, not the door's: it owns which profile is
    chosen from the offered set, how a refusal is shown, and when the operator
    gives up. What it must not own is the decision that the resulting session
    counts -- it authenticates through the canonical application door and
    returns only the non-secret outcome, and the admission door proves the
    binding afterwards.
    """
    from ...application.user_profile.login_interaction import attempt_profile_login
    from .secret.credentials import run_credential_screen
    from .secret.login import LoginScreen

    def journey(request: ProfileCredentialRequestV1) -> ProfileLoginOutcome | None:
        return run_credential_screen(
            LoginScreen(
                choices=tuple(choices),
                authenticate=lambda candidate_profile_id, passphrase: attempt_profile_login(
                    candidate_profile_id,
                    passphrase,
                    profile_decode_context=request.profile_decode_context,
                ),
                preselected=preselected_profile_id,
            )
        )

    return journey


def _run_registration_screen() -> bool:
    """Run the existing Registration screen and report whether a profile was created.

    Registration unlocks what it creates: the create span publishes the live
    session exactly as a login would, so a successful registration leaves the
    operator admitted and the next pass through the loop reuses that session
    rather than asking for the passphrase a second time.
    """
    from ...core.credentials import assess_profile_password
    from .secret.credentials import run_credential_screen
    from .secret.registration import (
        RegistrationScreen,
        build_profile_recovery_enrollment_attempt,
        build_profile_registration_attempt,
    )

    outcome = run_credential_screen(
        RegistrationScreen(
            assess=assess_profile_password,
            register=build_profile_registration_attempt,
            enroll_recovery=build_profile_recovery_enrollment_attempt,
        )
    )
    return outcome is not None


def _admit_installed_profile(
    inventory: ProfileLoginInventoryV1,
    *,
    operation: PinnedAuthorityOperation,
    allow_credential_screens: bool,
) -> ProfileSessionAdmissionV1:
    """Admit the recognized inventory's profile through the shared door.

    ``allow_credential_screens`` is lowered for a headless run: nobody is
    there to type a passphrase, so opening the Login screen would block
    forever. A lowered run therefore offers no journey at all and takes
    whatever the door can establish without one -- a reused or resumed
    session, otherwise a truthful refusal -- rather than pretending to
    authenticate.
    """
    return admit_profile_session(
        bucket_id=inventory.preselected_profile_id,
        profile_decode_context=operation.profile_decode_context(),
        credentials=None
        if not allow_credential_screens
        else _login_credential_journey(
            choices=inventory.choices,
            preselected_profile_id=inventory.preselected_profile_id,
        ),
    )


def _admitted_profile_label(
    admission: ProfileSessionAdmissionV1,
    inventory: ProfileLoginInventoryV1,
) -> str | None:
    """Return the recognized label of the admitted profile, or ``None``.

    The label comes from the inventory rather than from the login outcome so
    that what the workbench titles itself is what the operator was offered. A
    profile admitted but absent from the inventory read is a disagreement, not
    a naming problem, and is reported as no label so the caller declines the
    session instead of rendering an unrecognized one.
    """
    return next(
        (choice.label for choice in inventory.choices if choice.profile_id == admission.bucket_id),
        None,
    )


def run_installed_workbench_session(
    *,
    headless: bool = False,
    auto_pilot: AutopilotCallbackType | None = None,
) -> int:
    """Run installed workbench sessions until the operator ends the process.

    Each pass reads the profile inventory afresh and re-admits through the
    shared door. That is what makes sign-out, user handover, password rotation
    and session expiry return the operator to a real credential decision
    instead of a stale profile-bound composition -- and what makes a
    registration, which already unlocks what it created, continue straight
    into the workbench.
    """
    from ...domain.calculations.registry.authority import bundled_indexed_authority
    from ..adapter_composition import profile_adapter_composition

    with profile_adapter_composition():
        while True:
            inventory = observe_profile_login_inventory()
            if inventory.state in {
                ProfileLoginInventoryState.CONCURRENT_CHANGE,
                ProfileLoginInventoryState.DEGRADED,
            }:
                sys.stderr.write(f"{inventory.reason_code}\n")
                return SESSION_INVENTORY_UNAVAILABLE
            if inventory.state is ProfileLoginInventoryState.EMPTY:
                if headless or not _run_registration_screen():
                    return SESSION_COMPLETED
                continue

            with bundled_indexed_authority().operation() as operation:
                admission = _admit_installed_profile(
                    inventory,
                    operation=operation,
                    allow_credential_screens=not headless,
                )
            if not admission.admitted:
                return SESSION_COMPLETED
            profile_id = admission.bucket_id
            profile_label = _admitted_profile_label(admission, inventory)
            if profile_id is None or profile_label is None:
                return SESSION_COMPLETED

            recompose = asyncio.run(
                run_authenticated_workbench_sessions(
                    headless=headless,
                    auto_pilot=auto_pilot,
                    workbench_root_inputs_provider=compose_authenticated_root_inputs_provider(
                        profile_id=profile_id,
                        profile_label=profile_label,
                        login_choices=inventory.choices,
                    ),
                )
            )
            if recompose is None or headless:
                return SESSION_COMPLETED


__all__ = [
    "SESSION_COMPLETED",
    "SESSION_INVENTORY_UNAVAILABLE",
    "compose_authenticated_account_inputs",
    "compose_authenticated_root_inputs_provider",
    "run_installed_workbench_session",
]
