"""Secret-store custody command registration."""

from __future__ import annotations

import getpass
import sys

import typer
from pydantic import BaseModel, ConfigDict, SecretStr

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._secure_input import prompt_secret_no_echo, read_secrets_stdin


def _resolve_confirmed_new_passphrase(value: str | None, confirmation: str | None) -> str:
    """Resolve a new passphrase from options or hidden interactive prompts."""
    if value is not None:
        if confirmation is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.custody.errors.missing_new_passphrase_confirmation",
            )
        if value != confirmation:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.custody.errors.new_passphrase_mismatch",
            )
        return value

    # No --new-passphrase supplied: the hidden prompts below require an
    # interactive terminal. Without a TTY, getpass raises a bare EOFError that
    # would escape to the generic INTERNAL boundary (exit 6, logged traceback).
    # Refuse cleanly instead (REFUSED, exit 2), naming the non-interactive path.
    if not sys.stdin.isatty():
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.non_interactive_passphrase_required",
        )
    try:
        first = getpass.getpass(tr("cli.config.custody.new_passphrase_prompt"))
        second = confirmation
        if second is None:
            second = getpass.getpass(tr("cli.config.custody.confirm_new_passphrase_prompt"))
    except EOFError as exc:
        # Defence in depth: a closed/redirected stdin that reports a TTY (rare)
        # still raises EOFError from getpass; refuse identically.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.non_interactive_passphrase_required",
        ) from exc
    if first != second:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.new_passphrase_mismatch",
        )
    return first


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


def _register_recover_command(app: typer.Typer) -> None:
    """Register the recovery transport command."""

    @app.command("recover", help=tr("cli.config.recover.help"))
    def config_recover(
        ctx: typer.Context,
        recovery_key: str = typer.Option(..., "--recovery-key", help=tr("cli.config.recover.recovery_key_help")),
        new_passphrase: str | None = typer.Option(
            None,
            "--new-passphrase",
            help=tr("cli.config.custody.new_passphrase_help"),
        ),
        confirm_new_passphrase: str | None = typer.Option(
            None,
            "--confirm-new-passphrase",
            help=tr("cli.config.custody.confirm_new_passphrase_help"),
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
        from ....application.user_profile import recover_secret_store
        from .._config_payloads import ConfigRecoverResult

        passphrase = _resolve_confirmed_new_passphrase(new_passphrase, confirm_new_passphrase)
        result = recover_secret_store(mnemonic=recovery_key, new_passphrase=passphrase)
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


def _register_show_recovery_command(app: typer.Typer) -> None:
    """Register the show-recovery transport command."""

    @app.command("show-recovery", help=tr("cli.config.show_recovery.help"))
    def config_show_recovery(
        ctx: typer.Context,
        rotate: bool = typer.Option(
            False,
            "--rotate",
            help=tr("cli.config.show_recovery.rotate_help"),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Show recovery-wrapper status or mint a one-time recovery mnemonic."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import inspect_recovery_status, mint_recovery_code
        from .._config_payloads import ConfigShowRecoveryResult

        status = inspect_recovery_status()
        if not status.recovery_enrolled or rotate:
            enrollment = mint_recovery_code()
            payload = ConfigShowRecoveryResult(
                recovery_path=str(enrollment.recovery_path),
                recovery_enrolled=True,
                rotated=enrollment.rotated,
                mnemonic=enrollment.mnemonic,
            )
            _emit_envelope(
                ctx,
                command="config.show_recovery",
                result=payload,
                lines=(
                    "recovery_enrolled\tyes",
                    f"rotated\t{'yes' if enrollment.rotated else 'no'}",
                    f"recovery_path\t{enrollment.recovery_path}",
                    f"recovery_key\t{enrollment.mnemonic}",
                    tr("cli.config.custody.data_loss_warning"),
                ),
            )
            return

        payload = ConfigShowRecoveryResult(
            recovery_path=str(status.recovery_path),
            recovery_enrolled=True,
        )
        _emit_envelope(
            ctx,
            command="config.show_recovery",
            result=payload,
            lines=(
                "recovery_enrolled\tyes",
                "rotated\tno",
                f"recovery_path\t{status.recovery_path}",
                tr("cli.config.show_recovery.existing_notice"),
            ),
        )


def _register_verify_recovery_command(app: typer.Typer) -> None:
    """Register the verify-recovery transport command."""

    @app.command("verify-recovery", help=tr("cli.config.verify_recovery.help"))
    def config_verify_recovery(
        ctx: typer.Context,
        recovery_key: str = typer.Option(..., "--recovery-key", help=tr("cli.config.recover.recovery_key_help")),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Verify that a recovery mnemonic opens the persisted recovery wrapper."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import verify_recovery_code
        from .._config_payloads import ConfigVerifyRecoveryResult

        result = verify_recovery_code(mnemonic=recovery_key)
        payload = ConfigVerifyRecoveryResult(recovery_path=str(result.recovery_path), verified=result.verified)
        _emit_envelope(
            ctx,
            command="config.verify_recovery",
            result=payload,
            lines=(
                f"verified\t{'yes' if result.verified else 'no'}",
                f"recovery_path\t{result.recovery_path}",
            ),
        )
        if not result.verified:
            raise typer.Exit(code=2)


def register_secret_custody_commands(app: typer.Typer) -> None:
    """Register secret-store custody transport commands."""
    _register_passphrase_commands(app)
    _register_recover_command(app)
    _register_show_recovery_command(app)
    _register_verify_recovery_command(app)


__all__ = ["register_secret_custody_commands"]
