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

The credential channel is resolved in one declared order, and every step of
it is a channel the operator chose:

1. the hardened no-echo console prompt, when a real console is attached and
   the invocation is not already consuming a machine secret channel;
2. ``CADRUMO_SECRET_PASSPHRASE``, the sanctioned secrets environment surface
   that :func:`~cadrumo.application.user_profile.login_profile` already
   resolves the profile passphrase from, so creation and login read one
   variable with one meaning rather than growing a second;
3. otherwise an instructive refusal naming both, because silently creating a
   profile under a passphrase nobody chose is worse than refusing.

The passphrase is never accepted as an ``argv`` value, on this verb or any
other: a command line is visible in the process table and in shell history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import typer
from pydantic import BaseModel, ConfigDict, SecretStr

from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import _emit_envelope
from .._errors import CliRefusedBoundaryError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from typer._click.core import Context as _TyperClickContext

    from ....application.user_profile import ProfileRecoveryEnrollment


class _CreationSecrets(BaseModel):
    """Strict machine-channel payload for profile creation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    passphrase: SecretStr
    passphrase_confirmation: SecretStr


def resolve_creation_passphrase(*, secrets_stdin: bool = False) -> str:
    """Return the passphrase for a scripted registration, or refuse.

    Ordered console-first so an operator running the verb by hand on a
    headless host is asked rather than being told to export a variable. The
    environment value is a fallback for the genuinely unattended case, not
    the advertised interface.
    """
    from .. import _headless_secret_channel_active
    from ._secure_input import prompt_secret_no_echo, read_secrets_stdin, terminal_can_prompt_for_secrets

    if secrets_stdin:
        secrets = read_secrets_stdin(_CreationSecrets)
        first = secrets.passphrase.get_secret_value()
        if first != secrets.passphrase_confirmation.get_secret_value():
            raise CliRefusedBoundaryError(
                translated_message="cli.config.profile.create_passphrase_mismatch",
            )
        return first

    if not _headless_secret_channel_active() and terminal_can_prompt_for_secrets():
        first = prompt_secret_no_echo(tr("cli.config.profile.create_passphrase_prompt"))
        again = prompt_secret_no_echo(tr("cli.config.profile.create_confirm_passphrase_prompt"))
        if first != again:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.profile.create_passphrase_mismatch",
            )
        return first

    from ....core.config import load_settings

    configured = load_settings().cadrumo_secret_passphrase
    if configured is None:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.create_passphrase_channel_absent",
        )
    return configured.get_secret_value()


def _recovery_handover_or_none() -> Callable[[ProfileRecoveryEnrollment], None] | None:
    """Return the channel the 24 words reach the operator through, if one exists.

    Enrolment is only offered when there is somewhere safe to SHOW the result.
    A recovery wrapper whose mnemonic was never displayed is worse than no
    wrapper: the operator is told their profile is recoverable and holds
    nothing that can recover it. So on a host with no interactive terminal --
    a script, a CI job, a supervised child -- this returns ``None``, the
    registration door mints no wrapper at all, and the caller reports that
    through ``recovery_enrolled`` rather than leaving it to be assumed.

    Returning ``None`` rather than refusing the whole creation is deliberate:
    non-interactive profile creation is a supported operator path, and
    breaking it to enforce recovery would trade a real capability for one the
    operator can add no other way today.
    """
    from ._secure_input import terminal_can_prompt_for_secrets, write_to_controlling_terminal

    if not terminal_can_prompt_for_secrets():
        return None

    def handover(enrollment: ProfileRecoveryEnrollment) -> None:
        """Show the mnemonic on the terminal device, and nowhere else."""
        write_to_controlling_terminal(
            f"{tr('cli.config.custody.data_loss_warning')}\n\n{enrollment.recovery_key.mnemonic}",
        )

    return handover


def register_profile_from_scripted_invocation(
    ctx: _TyperClickContext,
    kwargs: Mapping[str, object],
) -> None:
    """Create a profile from a scripted ``config profile create`` invocation.

    The label is the verb's own positional subject. Facts supplied as field
    flags are applied after the record exists rather than as preconditions
    for it: a profile is born incomplete on purpose, so a rejected fact
    leaves a real profile the operator can correct instead of nothing.
    """
    from ....application.user_profile import register_profile_with_credentials
    from ....application.wizard import ConfigProfileCreateResult, ProfileWizardStatus, scripted_profile_facts
    from ....core.wizard_catalogue import get_setup_flow

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
    facts = scripted_profile_facts(get_setup_flow(), kwargs)
    passphrase = resolve_creation_passphrase(secrets_stdin=bool(kwargs.get("secrets_stdin")))
    try:
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=passphrase,
            facts=facts,
            recovery_handover=_recovery_handover_or_none(),
        )
    finally:
        del passphrase

    # A profile created without recovery is a supported outcome, not a silent
    # one: the operator must learn from the run itself that the one chance to
    # enrol has passed, because nothing can install a wrapper afterwards.
    notices = (
        ()
        if outcome.recovery_enrolled
        else (
            Notice(
                code="PROFILE_RECOVERY_NOT_ENROLLED",
                severity=NoticeSeverity.WARNING,
                message=tr("cli.config.profile.create_recovery_not_enrolled"),
            ),
        )
    )
    _emit_envelope(
        # CAST-RATIONALE-TYPER-CLICK-CONTEXT: ctx is the vendored
        # typer._click.core.Context this package accepts at its boundary;
        # _emit_envelope's signature names the public typer.Context alias
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
