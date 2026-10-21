"""Bounded delivery and possession proof for one-time profile recovery codes."""

from __future__ import annotations

import json
import os
from contextlib import suppress
from typing import TYPE_CHECKING

from pydantic import SecretStr

from cadrumo.core.descriptor_write import write_all
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.i18n.render import tr
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.secure_input import (
    MACHINE_SECRET_MAX_BYTES,
    MachineSecretPayload,
    prompt_secret_no_echo,
    terminal_can_prompt_for_secrets,
    validate_secrets_payload,
    write_to_controlling_terminal,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from cadrumo.application.user_profile.recovery_custody import ProfileRecoveryEnrollment

_RECOVERY_HANDOFF_MAX_BYTES = 8192


class ProfileRecoveryVerification(MachineSecretPayload):
    """Strict possession proof returned after the one-time handoff."""

    recovery_code: SecretStr


def _write_recovery_handoff(descriptor: int, code: str) -> None:
    """Write one bounded secret document and close its descriptor on every exit."""
    raw = bytearray(json.dumps({"recovery_code": code}, separators=(",", ":")).encode(UTF_8_ENCODING) + b"\n")
    try:
        if len(raw) > _RECOVERY_HANDOFF_MAX_BYTES:
            raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.handoff_too_large")
        write_all(descriptor, raw)
    except OSError as exc:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.handoff_unwritable") from exc
    finally:
        raw[:] = b"\x00" * len(raw)
        with suppress(OSError):
            os.close(descriptor)


def _read_recovery_verification(descriptor: int) -> ProfileRecoveryVerification:
    """Read one newline-framed strict object without depending on pipe EOF."""
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
    """Build one-time code delivery with console or descriptor possession proof."""
    from cadrumo.adapters.persistence.storage.errors import StorageValidationError
    from cadrumo.adapters.persistence.storage.recovery_key import canonical_recovery_code

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


__all__ = ["ProfileRecoveryVerification", "recovery_handover"]
