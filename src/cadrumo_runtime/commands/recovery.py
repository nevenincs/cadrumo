"""The ``cadrumo-runtime config profile recovery`` verbs: enable, disable and inspect recovery.

Recovery is a second door onto a profile's records, opened by a minted code
instead of the passphrase, and it exists so a forgotten passphrase can be
replaced through ``cadrumo-runtime config passphrase reset`` rather than costing the records.
It is off by default and enrolled here, after the profile exists, by an
operator who proves the current passphrase.

The code is delivered exactly once and never through the ordinary render
path. At a terminal it is written to the controlling terminal device and the
operator must type it back before anything is installed. A headless caller
receives it as one bounded secret JSON object on an inherited writable
descriptor and returns the exact code on a second, readable descriptor. It
never enters a result envelope, standard output, an argument, an environment
variable, or a log.
"""

from __future__ import annotations

import os
from contextlib import suppress
from uuid import UUID

import typer
from pydantic import SecretStr

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.json_contract import Notice, NoticeSeverity
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.payloads import ConfigProfileRecoveryResult, ConfigProfileRecoveryStatusResult
from cadrumo_client.commands.recovery_handover import recovery_handover
from cadrumo_client.commands.secure_input import (
    MachineSecretPayload,
    prompt_secret_no_echo,
    read_machine_secret_payload,
    select_machine_secret_channel,
)

from .presentation import activate_subcommand_output_language as _activate_subcommand_output_language
from .presentation import emit_envelope
from .profile_admission import _profile_id


class RecoveryEnableSecrets(MachineSecretPayload):
    """Strict machine-channel payload for ``config profile recovery enable`` and ``disable``."""

    passphrase: SecretStr


def validated_recovery_descriptors(
    *,
    passphrase_fd: int | None,
    handoff_fd: int | None,
    verification_fd: int | None,
) -> tuple[int, int] | None:
    """Preflight the headless handoff pair before any descriptor is consumed."""
    if (handoff_fd is None) != (verification_fd is None):
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.descriptor_pair_required")
    if handoff_fd is None or verification_fd is None:
        return None
    descriptors = (handoff_fd, verification_fd)
    _require_recovery_descriptor_admission(descriptors, passphrase_fd)
    return descriptors


def close_recovery_descriptors(descriptors: tuple[int, int] | None) -> None:
    """Close both handoff descriptors after success or any refusal."""
    if descriptors is None:
        return
    for descriptor in descriptors:
        with suppress(OSError):
            os.close(descriptor)


def _collect_passphrase(*, secrets_stdin: bool, secrets_fd: int | None) -> str:
    """Resolve the current passphrase from one explicit channel or a verified prompt."""
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is not None:
        return read_machine_secret_payload(RecoveryEnableSecrets, selection=selection).passphrase.get_secret_value()
    return prompt_secret_no_echo(tr("cli.config.custody.current_passphrase_prompt"))


def _active_profile_id(ctx: typer.Context) -> UUID:
    """Resolve the exact root-selected or active profile for recovery operations."""
    profile_id, _label = _profile_id(ctx)
    return profile_id


def profile_recovery_enable(
    ctx: typer.Context,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    recovery_handoff_fd: int | None = None,
    recovery_verification_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Enrol a recovery code for the active profile after proving its passphrase."""
    _activate_subcommand_output_language(ctx, output_language)
    from cadrumo.application.user_profile.recovery_custody import enroll_profile_recovery

    profile_id = _active_profile_id(ctx)
    descriptors = validated_recovery_descriptors(
        passphrase_fd=secrets_fd,
        handoff_fd=recovery_handoff_fd,
        verification_fd=recovery_verification_fd,
    )
    try:
        handover = recovery_handover(descriptors=descriptors)
        passphrase = _collect_passphrase(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
        outcome = enroll_profile_recovery(
            profile_id=profile_id,
            current_passphrase=passphrase,
            recovery_handover=handover,
        )
    finally:
        close_recovery_descriptors(descriptors)
    notice = Notice(
        code="PROFILE_RECOVERY_ENABLED",
        severity=NoticeSeverity.INFO,
        message=tr("cli.config.profile.recovery.enabled_notice"),
    )
    emit_envelope(
        ctx,
        command="config.profile.recovery.enable",
        result=ConfigProfileRecoveryResult(
            profile_id=outcome.profile_id,
            enrolled=outcome.enrolled,
            changed=outcome.changed,
        ),
        lines=["enrolled\tyes", notice.message],
        notices=[notice],
    )


def profile_recovery_disable(
    ctx: typer.Context,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Remove the active profile's recovery code after proving its passphrase."""
    _activate_subcommand_output_language(ctx, output_language)
    from cadrumo.application.user_profile.recovery_custody import revoke_profile_recovery

    profile_id = _active_profile_id(ctx)
    outcome = revoke_profile_recovery(
        profile_id=profile_id,
        current_passphrase=_collect_passphrase(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd),
    )
    emit_envelope(
        ctx,
        command="config.profile.recovery.disable",
        result=ConfigProfileRecoveryResult(
            profile_id=outcome.profile_id,
            enrolled=outcome.enrolled,
            changed=outcome.changed,
        ),
        lines=["enrolled\tno", f"changed\t{'yes' if outcome.changed else 'no'}"],
    )


def profile_recovery_status(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Report whether the active profile has a recovery code enrolled."""
    _activate_subcommand_output_language(ctx, output_language)
    from .runtime_recovery_status import read_recovery_status

    status = read_recovery_status(ctx)
    emit_envelope(
        ctx,
        command="config.profile.recovery.status",
        result=ConfigProfileRecoveryStatusResult(profile_id=str(status.profile_id), enrolled=status.enrolled),
        lines=[f"enrolled\t{'yes' if status.enrolled else 'no'}"],
    )


__all__ = [
    "RecoveryEnableSecrets",
    "close_recovery_descriptors",
    "profile_recovery_disable",
    "profile_recovery_enable",
    "profile_recovery_status",
    "validated_recovery_descriptors",
]


def _require_recovery_descriptor_admission(descriptors: tuple[int, int], passphrase_fd: int | None) -> None:
    """Reject reserved or colliding handoff channels before consuming either descriptor."""
    if any(descriptor < 0 or descriptor in {0, 1, 2} for descriptor in descriptors):
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.descriptor_reserved")
    occupied = {descriptor for descriptor in (passphrase_fd,) if descriptor is not None}
    if descriptors[0] == descriptors[1] or any(descriptor in occupied for descriptor in descriptors):
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.descriptor_collision")
