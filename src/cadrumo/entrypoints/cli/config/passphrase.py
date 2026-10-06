"""CLI handler for active-profile passphrase rotation."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

import typer
from pydantic import SecretStr

from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....adapters.local_runtime.profile_password_rotation import run_profile_password_rotation
from ....application.operations.registry import OperationFrontendProjection
from ....core.bucket_pointer import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope, notice_lines
from ..errors import CliRefusedBoundaryError
from .secure_input import MachineSecretPayload

if TYPE_CHECKING:
    from ....application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
    from ....application.user_profile.recovery_custody import ProfilePassphraseResetOutcome


class PassphraseChangeSecrets(MachineSecretPayload):
    """Exact strict payload for ``config passphrase change``."""

    current_passphrase: SecretStr
    new_passphrase: SecretStr
    new_passphrase_confirmation: SecretStr


class PassphraseResetSecrets(MachineSecretPayload):
    """Exact strict payload for ``config passphrase reset``."""

    recovery_code: SecretStr
    new_passphrase: SecretStr
    new_passphrase_confirmation: SecretStr


def _collect_passphrases(*, secrets_stdin: bool, secrets_fd: int | None) -> PassphraseChangeSecrets:
    """Resolve all three rotation values through one explicit or interactive door."""
    from .secure_input import prompt_secret_no_echo, read_machine_secret_payload, select_machine_secret_channel

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


def _open_rotation_client(profile_id: UUID) -> RuntimeFrontendClient:
    """Open one exact CLI connection without local profile custody."""
    return asyncio.run(open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI))


def passphrase_change(
    ctx: typer.Context,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Rotate the active profile's passphrase without replacing its data key."""
    _activate_subcommand_output_language(ctx, output_language)
    from ..config_payloads import ConfigPassphraseChangeResult

    active = _resolve_active_bucket_id()
    if active is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.passphrase.no_active_profile")
    profile_id = UUID(active)

    # The selected profile is fixed before reading a leaf secret channel.
    current, replacement, confirmation = bytearray(), bytearray(), bytearray()
    try:
        secrets = _collect_passphrases(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
        try:
            current.extend(secrets.current_passphrase.get_secret_value().encode("utf-8"))
            replacement.extend(secrets.new_passphrase.get_secret_value().encode("utf-8"))
            confirmation.extend(secrets.new_passphrase_confirmation.get_secret_value().encode("utf-8"))
        finally:
            del secrets
        client = _open_rotation_client(profile_id)
        try:
            proof = bytearray(current)
            try:
                client.login_password(proof)
            except RuntimeFrontendRefusedError as error:
                raise CliRefusedBoundaryError(error.reason, context=error.context) from error
            finally:
                proof[:] = bytes(len(proof))
            completion = run_profile_password_rotation(
                client,
                current_passphrase=current,
                new_passphrase=replacement,
                new_passphrase_confirmation=confirmation,
                fresh_client=lambda: _open_rotation_client(profile_id),
            )
            outcome = completion.outcome
        except BaseException as primary:
            try:
                client.close()
            except Exception:
                primary.add_note("Runtime connection cleanup did not complete.")
            raise
        else:
            client.close()
    finally:
        current[:] = bytes(len(current))
        replacement[:] = bytes(len(replacement))
        confirmation[:] = bytes(len(confirmation))
    emit_envelope(
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


def _collect_reset_secrets(*, secrets_stdin: bool, secrets_fd: int | None) -> PassphraseResetSecrets:
    """Resolve the recovery code and the new passphrase pair through one door."""
    from .secure_input import prompt_secret_no_echo, read_machine_secret_payload, select_machine_secret_channel

    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is not None:
        return read_machine_secret_payload(PassphraseResetSecrets, selection=selection)
    return PassphraseResetSecrets(
        recovery_code=SecretStr(prompt_secret_no_echo(tr("cli.config.passphrase.reset_code_prompt"))),
        new_passphrase=SecretStr(prompt_secret_no_echo(tr("cli.config.profile.create_passphrase_prompt"))),
        new_passphrase_confirmation=SecretStr(
            prompt_secret_no_echo(tr("cli.config.profile.create_confirm_passphrase_prompt"))
        ),
    )


def _reset_lines(outcome: ProfilePassphraseResetOutcome) -> tuple[str, ...]:
    return (
        "changed\tyes",
        f"password_generation\t{outcome.password_generation}",
        f"dek_epoch_preserved\t{'yes' if outcome.dek_epoch_preserved else 'no'}",
        f"recovery_enrollment_retained\t{'yes' if outcome.recovery_enrollment_retained else 'no'}",
    )


def passphrase_reset(
    ctx: typer.Context,
    name: str,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Replace a forgotten passphrase by proving the profile's recovery code."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile.login_session import resolve_login_target
    from ..config_payloads import ConfigPassphraseResetResult

    # Resolve the exact target before consuming any secret source: an unknown
    # name refuses without a prompt and without reading a machine payload.
    profile_id = UUID(resolve_login_target(name).bucket_id)
    code, replacement, confirmation = bytearray(), bytearray(), bytearray()
    try:
        secrets = _collect_reset_secrets(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
        try:
            code.extend(secrets.recovery_code.get_secret_value().encode("utf-8"))
            replacement.extend(secrets.new_passphrase.get_secret_value().encode("utf-8"))
            confirmation.extend(secrets.new_passphrase_confirmation.get_secret_value().encode("utf-8"))
        finally:
            del secrets
        client = _open_rotation_client(profile_id)
        try:
            completion = client.reset_password(
                recovery_code=code,
                new_passphrase=replacement,
                new_passphrase_confirmation=confirmation,
            )
            outcome = completion.outcome
        except BaseException as primary:
            try:
                client.close()
            except Exception:
                primary.add_note("Runtime connection cleanup did not complete.")
            if isinstance(primary, RuntimeFrontendRefusedError):
                raise CliRefusedBoundaryError(primary.reason, context=primary.context) from primary
            raise
        else:
            client.close()
    finally:
        code[:] = bytes(len(code))
        replacement[:] = bytes(len(replacement))
        confirmation[:] = bytes(len(confirmation))
    # Reset fences saved human sign-in, but re-wraps the same data key.
    # Recovery codes and previously exported archives retain their own scope.
    notices = (
        Notice(
            code="config.passphrase.reset_scope",
            severity=NoticeSeverity.INFO,
            message=tr("cli.config.passphrase.reset_scope_notice"),
        ),
    )
    emit_envelope(
        ctx,
        command="config.passphrase.reset",
        result=ConfigPassphraseResetResult(
            profile_id=outcome.profile_id,
            changed=True,
            human_receipt_revoked=True,
            receipt_removed=completion.human_sign_in_revocation.receipt_removed,
            keychain_removed=completion.human_sign_in_revocation.keychain_removed,
            password_generation=outcome.password_generation,
            dek_epoch_preserved=outcome.dek_epoch_preserved,
            recovery_enrollment_retained=outcome.recovery_enrollment_retained,
        ),
        lines=[
            *notice_lines(notices),
            *_reset_lines(outcome),
            f"receipt_removed\t{str(completion.human_sign_in_revocation.receipt_removed).lower()}",
            f"keychain_removed\t{str(completion.human_sign_in_revocation.keychain_removed).lower()}",
        ],
        notices=notices,
    )


__all__ = ["PassphraseChangeSecrets", "PassphraseResetSecrets", "passphrase_change", "passphrase_reset"]
