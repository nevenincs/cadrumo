"""CLI handler for active-profile passphrase rotation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import typer
from pydantic import SecretStr

from ....core import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.i18n import OutputLanguage, tr
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError
from ._secure_input import MachineSecretPayload

if TYPE_CHECKING:
    from ....application.user_profile import ProfilePassphraseRotationOutcome


class PassphraseChangeSecrets(MachineSecretPayload):
    """Exact strict payload for ``config passphrase change``."""

    current_passphrase: SecretStr
    new_passphrase: SecretStr
    new_passphrase_confirmation: SecretStr


def _collect_passphrases(*, secrets_stdin: bool, secrets_fd: int | None) -> PassphraseChangeSecrets:
    """Resolve all three rotation values through one explicit or interactive door."""
    from ._secure_input import prompt_secret_no_echo, read_machine_secret_payload, select_machine_secret_channel

    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is not None:
        return read_machine_secret_payload(PassphraseChangeSecrets, selection=selection)
    return PassphraseChangeSecrets(
        current_passphrase=SecretStr(prompt_secret_no_echo(tr("cli.config.custody.current_passphrase_prompt"))),
        new_passphrase=SecretStr(prompt_secret_no_echo(tr("cli.config.profile.create_passphrase_prompt"))),
        new_passphrase_confirmation=SecretStr(
            prompt_secret_no_echo(tr("cli.config.profile.create_confirm_passphrase_prompt"))
        ),
    )


def _rotation_lines(outcome: ProfilePassphraseRotationOutcome) -> tuple[str, ...]:
    return (
        "changed\tyes",
        f"password_generation\t{outcome.password_generation}",
        f"dek_epoch_preserved\t{'yes' if outcome.dek_epoch_preserved else 'no'}",
        f"recovery_enrollment_retained\t{'yes' if outcome.recovery_enrollment_retained else 'no'}",
    )


def passphrase_change(
    ctx: typer.Context,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Rotate the active profile's passphrase without replacing its data key."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import rotate_profile_passphrase
    from .._config_payloads import ConfigPassphraseChangeResult

    secrets = _collect_passphrases(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    active = _resolve_active_bucket_id()
    if active is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.passphrase.no_active_profile")

    outcome = rotate_profile_passphrase(
        profile_id=UUID(active),
        current_passphrase=secrets.current_passphrase.get_secret_value(),
        new_passphrase=secrets.new_passphrase.get_secret_value(),
        new_passphrase_confirmation=secrets.new_passphrase_confirmation.get_secret_value(),
    )
    _emit_envelope(
        ctx,
        command="config.passphrase.change",
        result=ConfigPassphraseChangeResult(
            profile_id=outcome.profile_id,
            changed=True,
            password_generation=outcome.password_generation,
            dek_epoch_preserved=outcome.dek_epoch_preserved,
            recovery_enrollment_retained=outcome.recovery_enrollment_retained,
        ),
        lines=list(_rotation_lines(outcome)),
    )


__all__ = ["PassphraseChangeSecrets", "passphrase_change"]
