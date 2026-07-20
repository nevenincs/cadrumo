"""Secret-store custody command registration.

Registers the ``config passphrase`` subgroup, the ``config recovery``
lifecycle subgroup (``status`` / ``create`` / ``rotate`` / ``verify``), and the
flat ``config recover`` execution verb. Secrets — passphrases and 24-word
recovery codes — reach these verbs only through the shared secure-input
channels in :mod:`._secure_input`: no-echo prompts on the controlling terminal
or one bounded strict-JSON ``--secrets-stdin`` object. No secret is ever an
``argv`` value, and no envelope or stdout line ever carries a mnemonic; the
candidate recovery words are written directly to the controlling terminal and
must be fully retyped (no echo) before the enrollment commits.
"""

from __future__ import annotations

import sys

import typer
from pydantic import BaseModel, ConfigDict, SecretStr

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._secure_input import prompt_secret_no_echo, read_secrets_stdin, write_to_controlling_terminal


class _PassphraseChangeSecrets(BaseModel):
    """Strict ``--secrets-stdin`` payload for ``config passphrase change``.

    Read from one bounded JSON object; the three passphrases arrive as
    :class:`~pydantic.SecretStr` so they never render in a repr, and
    ``extra="forbid"`` refuses an unexpected field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    current_passphrase: SecretStr
    new_passphrase: SecretStr
    new_passphrase_confirmation: SecretStr


def _resolve_passphrase_change_secrets(secrets_stdin: bool) -> tuple[str, str]:
    """Return the ``(current, new)`` passphrases from stdin JSON or no-echo prompts.

    Never reads a passphrase from ``argv``. With ``--secrets-stdin`` the three
    values arrive in one bounded strict-JSON object; otherwise each is prompted on
    the controlling terminal with echo suppressed. A new/confirmation mismatch
    refuses before any custody mutation.
    """
    if secrets_stdin:
        secrets = read_secrets_stdin(_PassphraseChangeSecrets)
        current = secrets.current_passphrase.get_secret_value()
        new = secrets.new_passphrase.get_secret_value()
        confirmation = secrets.new_passphrase_confirmation.get_secret_value()
    else:
        current = prompt_secret_no_echo(tr("cli.config.passphrase.current_passphrase_prompt"))
        new = prompt_secret_no_echo(tr("cli.config.passphrase.new_passphrase_prompt"))
        confirmation = prompt_secret_no_echo(tr("cli.config.passphrase.confirm_new_passphrase_prompt"))
    if new != confirmation:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.new_passphrase_mismatch",
        )
    return current, new


def _register_passphrase_commands(app: typer.Typer) -> None:
    """Register the ``config passphrase change`` transport command."""
    passphrase_app = typer.Typer(
        name="passphrase",
        help=tr("cli.config.passphrase.help"),
        no_args_is_help=True,
    )

    @passphrase_app.command("change", help=tr("cli.config.passphrase.change.help"))
    def passphrase_change(
        ctx: typer.Context,
        secrets_stdin: bool = typer.Option(
            False,
            "--secrets-stdin",
            help=tr("cli.config.custody.secrets_stdin_help"),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Rotate the file secret store's passphrase after verifying the current one."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....adapters.persistence.storage import (
            MasterKeyMaterialMissingError,
            MasterKeyPassphraseMismatchError,
            SecretStoreError,
        )
        from ....application.user_profile import change_passphrase
        from .._config_payloads import ConfigPassphraseChangeResult

        current, new = _resolve_passphrase_change_secrets(secrets_stdin)
        try:
            result = change_passphrase(current_passphrase=current, new_passphrase=new)
        except MasterKeyPassphraseMismatchError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.passphrase.errors.current_passphrase_incorrect",
            ) from exc
        except MasterKeyMaterialMissingError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.passphrase.errors.store_unprovisioned",
            ) from exc
        except SecretStoreError as exc:
            raise _CliRefusedBoundaryError(str(exc)) from exc

        payload = ConfigPassphraseChangeResult(
            secret_store_dir=str(result.secret_store_dir),
            changed=result.changed,
        )
        _emit_envelope(
            ctx,
            command="config.passphrase.change",
            result=payload,
            lines=(
                "changed\tyes",
                f"secret_store_dir\t{result.secret_store_dir}",
            ),
        )

    app.add_typer(passphrase_app)


class _RecoveryVerifySecrets(BaseModel):
    """Strict ``--secrets-stdin`` payload for ``config recovery verify``.

    One bounded JSON object carrying only the 24-word recovery code as a
    :class:`~pydantic.SecretStr`; ``extra="forbid"`` refuses an unexpected
    field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    recovery_code: SecretStr


class _RecoverSecrets(BaseModel):
    """Strict ``--secrets-stdin`` payload for the flat ``config recover`` verb.

    Carries the recovery code plus the new passphrase and its confirmation as
    :class:`~pydantic.SecretStr` fields so none of them render in a repr;
    ``extra="forbid"`` refuses an unexpected field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    recovery_code: SecretStr
    new_passphrase: SecretStr
    new_passphrase_confirmation: SecretStr


def _resolve_recovery_code(secrets_stdin: bool) -> str:
    """Return the recovery code from stdin JSON or a no-echo terminal prompt.

    Never reads the code from ``argv``; the 24 words must not land in the
    process table or shell history.
    """
    if secrets_stdin:
        return read_secrets_stdin(_RecoveryVerifySecrets).recovery_code.get_secret_value()
    return prompt_secret_no_echo(tr("cli.config.recovery.recovery_code_prompt"))


def _resolve_recover_secrets(secrets_stdin: bool) -> tuple[str, str]:
    """Return ``(recovery_code, new_passphrase)`` from stdin JSON or no-echo prompts.

    A new/confirmation passphrase mismatch refuses before any custody
    mutation; no value is ever read from ``argv``.
    """
    if secrets_stdin:
        secrets = read_secrets_stdin(_RecoverSecrets)
        code = secrets.recovery_code.get_secret_value()
        new = secrets.new_passphrase.get_secret_value()
        confirmation = secrets.new_passphrase_confirmation.get_secret_value()
    else:
        code = prompt_secret_no_echo(tr("cli.config.recovery.recovery_code_prompt"))
        new = prompt_secret_no_echo(tr("cli.config.passphrase.new_passphrase_prompt"))
        confirmation = prompt_secret_no_echo(tr("cli.config.passphrase.confirm_new_passphrase_prompt"))
    if new != confirmation:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.new_passphrase_mismatch",
        )
    return code, new


def _confirm_candidate_on_terminal(mnemonic: str) -> str:
    """Display the candidate recovery code on the controlling terminal and collect the retype.

    The words reach only the terminal device — never stdout, the JSON
    envelope, or a log — and the operator must retype all 24 words with echo
    suppressed before the enrollment is allowed to commit.
    """
    write_to_controlling_terminal(
        "\n".join(
            (
                tr("cli.config.recovery.candidate_intro"),
                "",
                mnemonic,
                "",
                tr("cli.config.custody.data_loss_warning"),
                "",
            ),
        ),
    )
    return prompt_secret_no_echo(tr("cli.config.recovery.retype_prompt"))


def _register_recover_command(app: typer.Typer) -> None:
    """Register the flat recovery-execution transport command."""

    @app.command("recover", help=tr("cli.config.recover.help"))
    def config_recover(
        ctx: typer.Context,
        secrets_stdin: bool = typer.Option(
            False,
            "--secrets-stdin",
            help=tr("cli.config.custody.secrets_stdin_help"),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Recover the configured file secret store from the persisted recovery wrapper."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....adapters.persistence.storage import RecoveryVerificationError, SecretStoreError
        from ....application.user_profile import recover_secret_store
        from .._config_payloads import ConfigRecoverResult

        code, new_passphrase = _resolve_recover_secrets(secrets_stdin)
        try:
            result = recover_secret_store(mnemonic=code, new_passphrase=new_passphrase)
        except RecoveryVerificationError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.recover.errors.recovery_code_rejected",
            ) from exc
        except SecretStoreError as exc:
            raise _CliRefusedBoundaryError(str(exc)) from exc
        payload = ConfigRecoverResult(
            recovery_path=str(result.recovery_path),
            secret_store_dir=str(result.secret_store_dir),
            recovered=result.recovered,
        )
        _emit_envelope(
            ctx,
            command="config.recover",
            result=payload,
            lines=(
                "recovered\tyes",
                f"recovery_path\t{result.recovery_path}",
                f"secret_store_dir\t{result.secret_store_dir}",
            ),
        )


def _register_recovery_commands(app: typer.Typer) -> None:
    """Register the ``config recovery`` lifecycle subgroup."""
    recovery_app = typer.Typer(
        name="recovery",
        help=tr("cli.config.recovery.help"),
        no_args_is_help=True,
    )

    @recovery_app.command("status", help=tr("cli.config.recovery.status.help"))
    def recovery_status(
        ctx: typer.Context,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Report recovery-wrapper enrollment without exposing any secret."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import inspect_recovery_status
        from .._config_payloads import ConfigRecoveryStatusResult

        status = inspect_recovery_status()
        payload = ConfigRecoveryStatusResult(
            recovery_path=str(status.recovery_path),
            recovery_enrolled=status.recovery_enrolled,
            recovery_fingerprint=status.recovery_fingerprint,
        )
        _emit_envelope(
            ctx,
            command="config.recovery.status",
            result=payload,
            lines=(
                f"recovery_enrolled\t{'yes' if status.recovery_enrolled else 'no'}",
                f"recovery_fingerprint\t{status.recovery_fingerprint or '<none>'}",
                f"recovery_path\t{status.recovery_path}",
            ),
        )

    @recovery_app.command("create", help=tr("cli.config.recovery.create.help"))
    def recovery_create(
        ctx: typer.Context,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Enroll a first recovery code after a full no-echo retype on the terminal."""
        _run_recovery_enrollment(ctx, output_language=output_language, rotate=False)

    @recovery_app.command("rotate", help=tr("cli.config.recovery.rotate.help"))
    def recovery_rotate(
        ctx: typer.Context,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Replace the enrolled recovery code after a full no-echo retype on the terminal."""
        _run_recovery_enrollment(ctx, output_language=output_language, rotate=True)

    @recovery_app.command("verify", help=tr("cli.config.recovery.verify.help"))
    def recovery_verify(
        ctx: typer.Context,
        secrets_stdin: bool = typer.Option(
            False,
            "--secrets-stdin",
            help=tr("cli.config.custody.secrets_stdin_help"),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Verify that a recovery code opens the persisted recovery wrapper."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....adapters.persistence.storage import SecretStoreError
        from ....application.user_profile import verify_recovery_code
        from .._config_payloads import ConfigRecoveryVerifyResult

        code = _resolve_recovery_code(secrets_stdin)
        try:
            result = verify_recovery_code(mnemonic=code)
        except SecretStoreError as exc:
            raise _CliRefusedBoundaryError(str(exc)) from exc
        payload = ConfigRecoveryVerifyResult(
            recovery_path=str(result.recovery_path),
            verified=result.verified,
            recovery_fingerprint=result.recovery_fingerprint,
        )
        _emit_envelope(
            ctx,
            command="config.recovery.verify",
            result=payload,
            lines=(
                f"verified\t{'yes' if result.verified else 'no'}",
                f"recovery_path\t{result.recovery_path}",
            ),
        )
        if not result.verified:
            raise typer.Exit(code=2)

    app.add_typer(recovery_app)


def _run_recovery_enrollment(
    ctx: typer.Context,
    *,
    output_language: OutputLanguage | None,
    rotate: bool,
) -> None:
    """Shared create/rotate enrollment body behind the two lifecycle verbs."""
    _activate_subcommand_output_language(ctx, output_language)
    # Enrollment is inherently interactive: the candidate words are shown once
    # on the controlling terminal and must be fully retyped with echo
    # suppressed before anything commits. Refuse cleanly before any custody
    # read when no terminal is attached.
    if not sys.stdin.isatty():
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.recovery.errors.interactive_terminal_required",
        )
    from ....adapters.persistence.storage import RecoveryVerificationError, SecretStoreError
    from ....application.user_profile import create_recovery_code, rotate_recovery_code
    from .._config_payloads import ConfigRecoveryCreateResult, ConfigRecoveryRotateResult

    enroll = rotate_recovery_code if rotate else create_recovery_code
    try:
        result = enroll(confirm=_confirm_candidate_on_terminal)
    except RecoveryVerificationError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.recovery.errors.retype_mismatch",
        ) from exc
    except SecretStoreError as exc:
        raise _CliRefusedBoundaryError(str(exc)) from exc

    lines = (
        "recovery_enrolled\tyes",
        f"rotated\t{'yes' if result.rotated else 'no'}",
        f"recovery_fingerprint\t{result.recovery_fingerprint}",
        f"recovery_path\t{result.recovery_path}",
    )
    if rotate:
        rotate_payload = ConfigRecoveryRotateResult(
            recovery_path=str(result.recovery_path),
            recovery_fingerprint=result.recovery_fingerprint,
            rotated=result.rotated,
        )
        _emit_envelope(ctx, command="config.recovery.rotate", result=rotate_payload, lines=lines)
        return
    create_payload = ConfigRecoveryCreateResult(
        recovery_path=str(result.recovery_path),
        recovery_fingerprint=result.recovery_fingerprint,
        rotated=result.rotated,
    )
    _emit_envelope(ctx, command="config.recovery.create", result=create_payload, lines=lines)


def register_secret_custody_commands(app: typer.Typer) -> None:
    """Register secret-store custody transport commands."""
    _register_passphrase_commands(app)
    _register_recover_command(app)
    _register_recovery_commands(app)


__all__ = ["register_secret_custody_commands"]
