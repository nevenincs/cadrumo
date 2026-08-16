"""The ``config passphrase`` command group: rotate a profile's credential.

Rotation re-wraps the profile's existing data key under a new passphrase. It
is deliberately NOT a re-key: the data key itself is unchanged, so no record is
re-encrypted and any recovery artifact the operator already holds keeps
working. What changes is the wrapper the password opens, and the generation
counter that names it.

The three values ride one bounded machine channel or three no-echo prompts,
never ``argv``. A passphrase on a command line is visible in the process table,
in shell history, and in any supervisor's log of the invocation -- the whole
point of rotating a credential is defeated if the new one is published in the
act of setting it.

The confirmation is compared here AND again in the application authority. That
is not redundant: this surface is one caller among several, and a rotation
reached by any other route must not be able to skip the check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import typer
from pydantic import BaseModel, ConfigDict, SecretStr

from ....core import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.i18n import OutputLanguage, tr
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError

if TYPE_CHECKING:
    from ....application.user_profile import ProfilePassphraseRotationOutcome


class _PassphraseChangeSecrets(BaseModel):
    """Strict machine-channel payload for ``config passphrase change``.

    One bounded JSON object carrying exactly the three passphrases as
    :class:`~pydantic.SecretStr`; ``extra="forbid"`` refuses an unexpected
    field, and the secret type keeps the values out of any repr.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    current_passphrase: SecretStr
    new_passphrase: SecretStr
    new_passphrase_confirmation: SecretStr


def _collect_passphrases(*, secrets_stdin: bool, secrets_fd: int | None) -> _PassphraseChangeSecrets:
    """Resolve the three values from one channel, machine or interactive."""
    from ._secure_input import prompt_secret_no_echo, read_secrets_fd, read_secrets_stdin

    # Naming both machine channels is refused upstream, so at most one is read
    # here; the ordering expresses no precedence.
    if secrets_fd is not None:
        return read_secrets_fd(_PassphraseChangeSecrets, descriptor=secrets_fd)
    if secrets_stdin:
        return read_secrets_stdin(_PassphraseChangeSecrets)
    return _PassphraseChangeSecrets(
        current_passphrase=SecretStr(prompt_secret_no_echo(tr("cli.config.custody.current_passphrase_prompt"))),
        new_passphrase=SecretStr(prompt_secret_no_echo(tr("cli.config.profile.create_passphrase_prompt"))),
        new_passphrase_confirmation=SecretStr(
            prompt_secret_no_echo(tr("cli.config.profile.create_confirm_passphrase_prompt")),
        ),
    )


def _rotation_lines(outcome: ProfilePassphraseRotationOutcome) -> tuple[str, ...]:
    """Render the non-secret facts of a completed rotation.

    ``changed`` is stated as its own row rather than left implicit in a zero
    exit code, and the two retention facts are stated because "what did NOT
    change" is the operator's real question: whether their records still open
    and whether the recovery phrase they wrote down is still the right one.
    """
    return (
        "changed\tyes",
        f"password_generation\t{outcome.password_generation}",
        f"dek_epoch_preserved\t{'yes' if outcome.dek_epoch_preserved else 'no'}",
        f"recovery_enrollment_retained\t{'yes' if outcome.recovery_enrollment_retained else 'no'}",
    )


def register_passphrase_commands(app: typer.Typer) -> None:
    """Mount the ``config passphrase`` group on ``app``."""
    passphrase_app = typer.Typer(
        help=tr("cli.config.passphrase.help"),
        no_args_is_help=True,
    )

    @passphrase_app.command("change", help=tr("cli.config.passphrase.change_help"))
    def passphrase_change(
        ctx: typer.Context,
        secrets_stdin: bool = typer.Option(
            False,
            "--secrets-stdin",
            help=tr("cli.config.custody.secrets_stdin_help"),
        ),
        secrets_fd: int | None = typer.Option(
            None,
            "--secrets-fd",
            help=tr("cli.config.custody.secrets_fd_help"),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Rotate the active profile's passphrase, keeping its records readable."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import rotate_profile_passphrase
        from .._config_payloads import ConfigPassphraseChangeResult
        from ._secure_input import resolve_secrets_channel

        resolve_secrets_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
        secrets = _collect_passphrases(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)

        # A bucket identifier IS the profile UUID -- the capsule directory is
        # named for it and can exist for no other shape -- so the active
        # selector resolves the rotation subject without a second lookup.
        active = _resolve_active_bucket_id()
        if active is None:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.passphrase.no_active_profile",
            )

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

    app.add_typer(passphrase_app, name="passphrase")


__all__ = ["register_passphrase_commands"]
