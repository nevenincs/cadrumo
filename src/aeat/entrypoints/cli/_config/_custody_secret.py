"""Secret-store custody command registration."""

from __future__ import annotations

import getpass

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError


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

    first = getpass.getpass(tr("cli.config.custody.new_passphrase_prompt"))
    second = confirmation
    if second is None:
        second = getpass.getpass(tr("cli.config.custody.confirm_new_passphrase_prompt"))
    if first != second:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.new_passphrase_mismatch",
        )
    return first


def _register_lock_command(app: typer.Typer) -> None:
    """Register the profile lock transport command."""

    @app.command("lock", help=tr("cli.config.lock.help"))
    def config_lock(
        ctx: typer.Context,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Lock the active profile by clearing the active-profile pointer."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import logout_active_profile
        from .._config_payloads import ConfigLockResult

        before = logout_active_profile()
        lock_result = ConfigLockResult(
            locked_profile=before or "",
            active_profile=None,
            session_warning=tr("cli.config.profile.logout_session_warning"),
        )
        _emit_envelope(
            ctx,
            command="config.lock",
            result=lock_result,
            lines=(
                f"locked_profile\t{before or '<none>'}",
                tr("cli.config.profile.logout_session_warning"),
            ),
        )


def _register_rekey_command(app: typer.Typer) -> None:
    """Register the profile rekey transport command."""

    @app.command("rekey", help=tr("cli.config.rekey.help"))
    def config_rekey(
        ctx: typer.Context,
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
        """Rewrap the configured file secret store under a fresh passphrase."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import rekey_secret_store
        from .._config_payloads import ConfigRekeyResult

        passphrase = _resolve_confirmed_new_passphrase(new_passphrase, confirm_new_passphrase)
        result = rekey_secret_store(new_passphrase=passphrase)
        payload = ConfigRekeyResult(secret_store_dir=str(result.secret_store_dir), rekeyed=result.rekeyed)
        _emit_envelope(
            ctx,
            command="config.rekey",
            result=payload,
            lines=(
                "rekeyed\tyes",
                f"secret_store_dir\t{result.secret_store_dir}",
            ),
        )


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
    _register_lock_command(app)
    _register_rekey_command(app)
    _register_recover_command(app)
    _register_show_recovery_command(app)
    _register_verify_recovery_command(app)


__all__ = ["register_secret_custody_commands"]
