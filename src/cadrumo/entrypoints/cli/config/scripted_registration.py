"""Non-interactive profile creation for ``config profile create``.

``create`` serves two audiences through one verb. An operator at a capable
terminal is diverted to the registration screen; everything else — a script,
an agent, a CI job, any host without a full-screen console — arrives here.

That second arm had no creation path at all. It fell through to the setup
flow, whose ``create`` mode refuses outright because the flow is not a
creation authority: a profile is brought into existence by supplying a label
and a passphrase, and the flow collects neither. The refusal was correct
about the flow and wrong about the operator, who was told to "register with
credentials" by a surface that offered no way to do it.

The credential channel is resolved in one declared order, and every step is a
channel the operator chose:

1. one bounded strict-JSON ``--secrets-stdin`` or ``--secrets-fd`` payload for
   machine callers;
2. the hardened no-echo console prompt when a real console is attached;
3. otherwise an instructive refusal naming the supported channels, because silently creating a
   profile under a passphrase nobody chose is worse than refusing.

The passphrase is never accepted as an ``argv`` value, on this verb or any
other: a command line is visible in the process table and in shell history.

Recovery is optional and comes after the profile exists. At a console the
verb asks once whether to set up a recovery code, defaulting to no; a
machine caller is never asked and enrols later through
``config profile recovery enable``. Either way the profile is already created
by the time the question is put, so declining costs nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import typer
from pydantic import SecretStr

from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity
from ....core.logging import get_logger
from ..common import emit_envelope
from ..errors import CliRefusedBoundaryError
from .secure_input import MachineSecretPayload

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from typer._click.core import Context as _TyperClickContext

    from ....application.user_profile.registration import ProfileRegistrationOutcome
    from ....application.wizard.models import WizardFlow
    from ....domain.calculations.registry.authority import PinnedAuthorityOperation
    from ....domain.user_profile.values import UserProfileFact


def _runtime_object(value: object) -> object:
    """Capture a credential before applying the cleanup boundary check."""
    return value


class ProfileCreationSecrets(MachineSecretPayload):
    """Strict machine-channel payload for profile creation."""

    passphrase: SecretStr
    passphrase_confirmation: SecretStr


def resolve_creation_passphrase(*, secrets_stdin: bool = False, secrets_fd: int | None = None) -> str:
    """Return the passphrase for a scripted registration, or refuse.

    Exactly one explicit bounded machine payload wins. Without one, a real
    interactive terminal receives the no-echo prompt; a non-interactive caller
    must choose one of the explicit channels.
    """
    from .secure_input import (
        prompt_secret_no_echo,
        read_machine_secret_payload,
        select_machine_secret_channel,
        terminal_can_prompt_for_secrets,
    )

    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is not None:
        secrets = read_machine_secret_payload(ProfileCreationSecrets, selection=selection)
        first = secrets.passphrase.get_secret_value()
        if first != secrets.passphrase_confirmation.get_secret_value():
            raise CliRefusedBoundaryError(
                translated_message="cli.config.profile.create_passphrase_mismatch",
            )
        return first

    if terminal_can_prompt_for_secrets():
        first = prompt_secret_no_echo(tr("cli.config.profile.create_passphrase_prompt"))
        again = prompt_secret_no_echo(tr("cli.config.profile.create_confirm_passphrase_prompt"))
        if first != again:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.profile.create_passphrase_mismatch",
            )
        return first

    raise CliRefusedBoundaryError(
        translated_message="cli.config.profile.create_passphrase_channel_absent",
    )


def _offer_recovery_at_console(*, machine_channel: bool) -> bool:
    """Ask a console operator whether to enrol recovery now; never ask a machine caller."""
    from .secure_input import prompt_confirmation_on_controlling_terminal, terminal_can_prompt_for_secrets

    if machine_channel or not terminal_can_prompt_for_secrets():
        return False
    return prompt_confirmation_on_controlling_terminal(tr("cli.config.profile.create_recovery_offer_prompt"))


def _run_scripted_profile_creation(
    *,
    register_profile: Callable[..., ProfileRegistrationOutcome],
    label: str,
    facts: tuple[UserProfileFact, ...],
    secrets_stdin: bool,
    secrets_fd: int | None,
) -> tuple[ProfileRegistrationOutcome, bool]:
    """Register the profile, then offer recovery while the passphrase is still in this span.

    Returns the outcome and whether recovery was enrolled. The passphrase is
    held only for the duration of this span: it authorises the create and,
    when the operator opts in, the enrolment that immediately follows.
    """
    from uuid import UUID

    from ....application.user_profile.recovery_custody import enroll_profile_recovery
    from .recovery import recovery_handover

    passphrase = _runtime_object(None)
    try:
        resolved_passphrase = resolve_creation_passphrase(
            secrets_stdin=secrets_stdin,
            secrets_fd=secrets_fd,
        )
        passphrase = _runtime_object(resolved_passphrase)
        outcome = register_profile(
            label=label,
            passphrase=resolved_passphrase,
            facts=facts,
        )
        enrolled = False
        if _offer_recovery_at_console(machine_channel=secrets_stdin or secrets_fd is not None):
            enroll_profile_recovery(
                profile_id=UUID(outcome.profile_id),
                current_passphrase=resolved_passphrase,
                recovery_handover=recovery_handover(descriptors=None),
            )
            enrolled = True
        return outcome, enrolled
    finally:
        if passphrase is not None:
            del passphrase


def _creation_notices(*, recovery_enrolled: bool, label: str) -> tuple[Notice, ...]:
    """Render the post-create notices, degrading rather than failing the verb.

    This runs AFTER the custody transaction has committed, so the profile
    exists whatever happens here. A failure while rendering guidance must not
    surface as a refusal: that tells the operator their profile was not created
    and sends them to create it again under a name that is now taken. Report
    the creation, and report that the guidance could not be rendered.
    """
    try:
        return (
            Notice(
                code="PROFILE_RECOVERY_ENABLED" if recovery_enrolled else "PROFILE_RECOVERY_NOT_ENROLLED",
                severity=NoticeSeverity.INFO,
                message=tr(
                    "cli.config.profile.create_recovery_enrolled"
                    if recovery_enrolled
                    else "cli.config.profile.create_recovery_skipped"
                ),
            ),
            # Creation closes the record session it opened, and mints no
            # acceleration receipt, so the next process is logged out. Saying
            # so here is not optional: without it create reports success and
            # the very next command refuses with "you are not signed in",
            # which reads as a failure of that command rather than the state
            # creation left behind.
            Notice(
                code="PROFILE_LOGIN_REQUIRED",
                severity=NoticeSeverity.WARNING,
                message=tr("cli.config.profile.create_login_required", profile=label),
            ),
        )
    except Exception:
        get_logger(__name__).debug("post-create notice rendering failed; reporting degraded guidance", exc_info=True)
        return (
            Notice(
                code="PROFILE_CREATED_GUIDANCE_UNAVAILABLE",
                severity=NoticeSeverity.WARNING,
                message=tr("cli.config.profile.create_guidance_unavailable"),
            ),
        )


def register_profile_from_scripted_invocation(
    ctx: _TyperClickContext,
    kwargs: Mapping[str, object],
    *,
    flow: WizardFlow,
    operation: PinnedAuthorityOperation,
) -> None:
    """Create a profile from a scripted ``config profile create`` invocation.

    The label is the verb's own positional subject. Facts supplied as field
    flags are applied after the record exists rather than as preconditions
    for it: a profile is born incomplete on purpose, so a rejected fact
    leaves a real profile the operator can correct instead of nothing.
    """
    from ....application.user_profile.registration import register_profile_with_credentials
    from ....application.wizard.commands import scripted_profile_facts
    from ....application.wizard.results import ConfigProfileCreateResult, ProfileWizardStatus

    supplied = kwargs.get("profile_name")
    label = supplied.strip() if isinstance(supplied, str) else ""
    if not label:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.create_name_required",
        )

    # Projected BEFORE the passphrase is resolved so a refused flag -- a foral
    # CCAA token, an unparseable value -- costs the operator nothing: no
    # prompt, no profile, nothing to undo. The facts then ride INTO the create
    # transaction, which already holds the record session, rather than being
    # written through a second unlock once registration has closed it.
    facts = scripted_profile_facts(flow, kwargs, operation=operation)
    raw_secrets_fd = kwargs.get("secrets_fd")
    secrets_fd = raw_secrets_fd if isinstance(raw_secrets_fd, int) else None
    profile_create_context = operation.profile_create_context()
    profile_decode_context = operation.profile_decode_context()

    def register_profile_with_pinned_context(
        *,
        label: str,
        passphrase: str,
        facts: tuple[UserProfileFact, ...],
    ) -> ProfileRegistrationOutcome:
        return register_profile_with_credentials(
            label=label,
            passphrase=passphrase,
            facts=facts,
            profile_create_context=profile_create_context,
            profile_decode_context=profile_decode_context,
        )

    outcome, recovery_enrolled = _run_scripted_profile_creation(
        register_profile=register_profile_with_pinned_context,
        label=label,
        facts=facts,
        secrets_stdin=bool(kwargs.get("secrets_stdin")),
        secrets_fd=secrets_fd,
    )

    notices = _creation_notices(recovery_enrolled=recovery_enrolled, label=outcome.label)
    emit_envelope(
        # CAST-RATIONALE-TYPER-CLICK-CONTEXT: ctx is the vendored
        # typer._click.core.Context this package accepts at its boundary;
        # emit_envelope's signature names the public typer.Context alias
        # for the same runtime object.
        cast(typer.Context, ctx),
        command="config.profile.create",
        result=ConfigProfileCreateResult(
            profile_name=outcome.label,
            status=ProfileWizardStatus.CREATED,
            active_profile=outcome.label,
        ),
        lines=[
            tr("cli.config.profile.manager_closed_created", profile=outcome.label),
            *(notice.message for notice in notices),
        ],
        notices=notices,
    )


__all__ = ["register_profile_from_scripted_invocation", "resolve_creation_passphrase"]
