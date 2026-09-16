"""The ``config profile recovery`` verbs: enable, disable and inspect optional recovery.

Recovery is a second door onto a profile's records, opened by a minted code
instead of the passphrase, and it exists so a forgotten passphrase can be
replaced through ``config passphrase reset`` rather than costing the records.
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

import json
import os
from contextlib import suppress
from typing import TYPE_CHECKING
from uuid import UUID

import typer
from pydantic import SecretStr

from ....core.bucket_pointer import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.external_constants import UTF_8_ENCODING, OutputLanguage
from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope
from ..errors import CliRefusedBoundaryError
from .secure_input import MachineSecretPayload

if TYPE_CHECKING:
    from collections.abc import Callable

    from ....application.user_profile.recovery_custody import ProfileRecoveryEnrollment

_RECOVERY_HANDOFF_MAX_BYTES = 8192


class RecoveryEnableSecrets(MachineSecretPayload):
    """Strict machine-channel payload for ``config profile recovery enable`` and ``disable``."""

    passphrase: SecretStr


class ProfileRecoveryVerification(MachineSecretPayload):
    """Strict possession proof returned after the one-time handoff."""

    recovery_code: SecretStr


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
    if any(descriptor < 0 or descriptor in {0, 1, 2} for descriptor in descriptors):
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.descriptor_reserved")
    occupied = {descriptor for descriptor in (passphrase_fd,) if descriptor is not None}
    if descriptors[0] == descriptors[1] or any(descriptor in occupied for descriptor in descriptors):
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.descriptor_collision")
    return descriptors


def close_recovery_descriptors(descriptors: tuple[int, int] | None) -> None:
    """Close both handoff descriptors after success or any refusal."""
    if descriptors is None:
        return
    for descriptor in descriptors:
        with suppress(OSError):
            os.close(descriptor)


def _write_recovery_handoff(descriptor: int, code: str) -> None:
    """Write one bounded secret document and close its descriptor on every exit."""
    raw = bytearray(json.dumps({"recovery_code": code}, separators=(",", ":")).encode(UTF_8_ENCODING) + b"\n")
    try:
        if len(raw) > _RECOVERY_HANDOFF_MAX_BYTES:
            raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.handoff_too_large")
        view = memoryview(raw)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise OSError("recovery handoff descriptor accepted no bytes")
            written += count
    except OSError as exc:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.handoff_unwritable") from exc
    finally:
        raw[:] = b"\x00" * len(raw)
        with suppress(OSError):
            os.close(descriptor)


def _read_recovery_verification(descriptor: int) -> ProfileRecoveryVerification:
    """Read one newline-framed strict object without depending on pipe EOF."""
    from .secure_input import MACHINE_SECRET_MAX_BYTES, validate_secrets_payload

    raw = bytearray()
    try:
        while len(raw) <= MACHINE_SECRET_MAX_BYTES:
            chunk = os.read(descriptor, min(1024, MACHINE_SECRET_MAX_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
            newline = raw.find(b"\n")
            if newline >= 0:
                if newline != len(raw) - 1:
                    raise CliRefusedBoundaryError(
                        translated_message="cli.config.custody.errors.secrets_fd_invalid_json",
                        context={"expected_fields": "recovery_code"},
                    )
                del raw[newline:]
                break
        if len(raw) > MACHINE_SECRET_MAX_BYTES:
            raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.secrets_fd_too_large")
        return validate_secrets_payload(
            raw,
            ProfileRecoveryVerification,
            invalid_json_key="cli.config.custody.errors.secrets_fd_invalid_json",
            missing_fields_key="cli.config.custody.errors.secrets_fd_missing_fields",
        )
    except OSError as exc:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_fd_unreadable",
            context={"descriptor": str(descriptor)},
        ) from exc
    finally:
        raw[:] = b"\x00" * len(raw)
        with suppress(OSError):
            os.close(descriptor)


def recovery_handover(
    *,
    descriptors: tuple[int, int] | None,
) -> Callable[[ProfileRecoveryEnrollment], str]:
    """Build the one-time code delivery with possession proof.

    A terminal caller sees the code on the controlling terminal and must type
    it back; a headless caller receives it on one bounded descriptor and
    returns the exact code on another. Either proof completes before the
    wrapper is installed. Without a terminal and without descriptors there is
    nowhere safe to show the code, so the enrolment is refused up front.
    """
    from ....adapters.persistence.storage.errors import StorageValidationError
    from ....adapters.persistence.storage.recovery_key import canonical_recovery_code
    from .secure_input import prompt_secret_no_echo, terminal_can_prompt_for_secrets, write_to_controlling_terminal

    if descriptors is None and not terminal_can_prompt_for_secrets():
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.channel_absent")

    def handover(enrollment: ProfileRecoveryEnrollment) -> str:
        expected = enrollment.recovery_key.code
        if descriptors is None:
            write_to_controlling_terminal(
                f"{tr('cli.config.profile.recovery.code_heading')}\n\n    {expected}\n\n"
                f"{tr('cli.config.profile.recovery.code_warning')}",
            )
            supplied = prompt_secret_no_echo(tr("cli.config.profile.recovery.verification_prompt"))
        else:
            handoff_fd, verification_fd = descriptors
            _write_recovery_handoff(handoff_fd, expected)
            supplied = _read_recovery_verification(verification_fd).recovery_code.get_secret_value()
        try:
            try:
                normalised = canonical_recovery_code(supplied)
            except StorageValidationError as exc:
                raise CliRefusedBoundaryError(
                    translated_message="cli.config.profile.recovery.verification_mismatch",
                ) from exc
            if normalised != expected:
                raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.verification_mismatch")
            return normalised
        finally:
            del expected

    return handover


def _collect_passphrase(*, secrets_stdin: bool, secrets_fd: int | None) -> str:
    """Resolve the current passphrase from one explicit channel or a verified prompt."""
    from .secure_input import prompt_secret_no_echo, read_machine_secret_payload, select_machine_secret_channel

    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is not None:
        return read_machine_secret_payload(RecoveryEnableSecrets, selection=selection).passphrase.get_secret_value()
    return prompt_secret_no_echo(tr("cli.config.custody.current_passphrase_prompt"))


def _active_profile_id() -> UUID:
    active = _resolve_active_bucket_id()
    if active is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.no_active_profile")
    return UUID(active)


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
    from ....application.user_profile.recovery_custody import enroll_profile_recovery
    from ..config_payloads import ConfigProfileRecoveryResult

    profile_id = _active_profile_id()
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
    from ....application.user_profile.recovery_custody import revoke_profile_recovery
    from ..config_payloads import ConfigProfileRecoveryResult

    profile_id = _active_profile_id()
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
    from ....application.user_profile.recovery_custody import profile_recovery_status as _status
    from ..config_payloads import ConfigProfileRecoveryStatusResult

    status = _status(profile_id=_active_profile_id())
    emit_envelope(
        ctx,
        command="config.profile.recovery.status",
        result=ConfigProfileRecoveryStatusResult(profile_id=status.profile_id, enrolled=status.enrolled),
        lines=[f"enrolled\t{'yes' if status.enrolled else 'no'}"],
    )


__all__ = [
    "ProfileRecoveryVerification",
    "RecoveryEnableSecrets",
    "close_recovery_descriptors",
    "profile_recovery_disable",
    "profile_recovery_enable",
    "profile_recovery_status",
    "recovery_handover",
    "validated_recovery_descriptors",
]
