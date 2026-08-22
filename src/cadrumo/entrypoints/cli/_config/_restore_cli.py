"""The ``config profile restore`` verb: republish a capsule an operator holds.

The restore door an operator reaches after a disk failure, after copying a
``buckets/<profile-id>/`` directory out of a backup, after restoring a sealed
archive written by ``config profile archive export``, or after a publication
was interrupted part-way. It takes the capsule and a credential that proves the
key, and publishes it back into the storage root as a usable profile.

**One verb takes both source shapes**, a capsule DIRECTORY or a sealed ARCHIVE
file, because the two differ only in how the material is READ. Both produce the
same :class:`ProfileCapsuleSource`, and from there both reach the one shared
publication authority. A separate ``archive import`` verb would be a second
door onto that authority differing only in its reader, which is the fork this
arrangement exists to prevent -- and it would leave an operator guessing which
of two verbs restores their backup. The shapes are told apart by asking the
filesystem, which is unambiguous, rather than by a flag the operator has to get
right.

Two credentials open it, and they are two ways of proving one key rather than
two restore paths: the profile's own password, or a portable recovery artifact
plus the 24-word phrase minted with it. Both converge on the same single
restore authority, which is why this is one verb selected by ``--artifact``
rather than a pair of sibling verbs that would each need their own argument
surface and could drift apart.

Recovering the DATA is not recovering the CREDENTIAL. The recovery door
republishes the capsule under its EXISTING password envelope, so an operator
who genuinely lost their password gets their records back and still cannot log
in with a password they do not know. That is stated to the operator through the
notices channel rather than left to be discovered at the next login prompt: a
verb that reports plain success here would be telling a half-truth at exactly
the moment the operator is deciding whether they are recovered.

The verb is bootstrap-exempt. Gating it behind an active session would be a
deadlock in the literal sense --- the profile the operator would log in to is
the one they are restoring --- and it grants nothing, because the caller must
already hold both the capsule bytes and a credential that opens them.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from pydantic import BaseModel, ConfigDict, SecretStr

from ....core.i18n import OutputLanguage, tr
from ....core.json_contract import Notice, NoticeSeverity
from .._command_policy import command_execution_policy
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from ._execution_policies import BOOTSTRAP_WRITE

if TYPE_CHECKING:
    from ....application.user_profile import ProfileCapsuleSource, ProfileRestoreOutcome

_RECOVERY_LIMIT_NOTICE_CODE = "config.profile.restore.password_unchanged"


class _RestorePasswordSecrets(BaseModel):
    """Strict machine-channel payload for the password door."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    password: SecretStr


class _RestoreRecoverySecrets(BaseModel):
    """Strict machine-channel payload for the recovery-artifact door."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recovery_secret: SecretStr


def _collect_password(*, secrets_stdin: bool, secrets_fd: int | None) -> str:
    """Resolve the profile password from one channel, machine or interactive."""
    from ._secure_input import prompt_secret_no_echo, read_secrets_fd, read_secrets_stdin

    if secrets_fd is not None:
        return read_secrets_fd(_RestorePasswordSecrets, descriptor=secrets_fd).password.get_secret_value()
    if secrets_stdin:
        return read_secrets_stdin(_RestorePasswordSecrets).password.get_secret_value()
    return prompt_secret_no_echo(tr("cli.config.custody.current_passphrase_prompt"))


def _collect_recovery_secret(*, secrets_stdin: bool, secrets_fd: int | None) -> str:
    """Resolve the 24-word recovery phrase from one channel."""
    from ._secure_input import prompt_secret_no_echo, read_secrets_fd, read_secrets_stdin

    if secrets_fd is not None:
        return read_secrets_fd(_RestoreRecoverySecrets, descriptor=secrets_fd).recovery_secret.get_secret_value()
    if secrets_stdin:
        return read_secrets_stdin(_RestoreRecoverySecrets).recovery_secret.get_secret_value()
    return prompt_secret_no_echo(tr("cli.config.profile.restore.recovery_secret_prompt"))


def _read_capsule_source(source: Path) -> ProfileCapsuleSource:
    """Read restorable capsule material from a directory or a sealed archive.

    The one place the two source shapes diverge. Everything downstream sees a
    :class:`ProfileCapsuleSource` and cannot tell which shape produced it,
    which is what keeps the publication authority single.

    Dispatch is on what the path IS, not on what the operator claims it is: an
    operator recovering from a failure should not have to tell the tool which
    kind of backup they are holding, and a flag they could set wrongly would
    turn a recoverable mistake into a confusing refusal.
    """
    from ....application.user_profile import read_profile_capsule_archive, read_profile_capsule_source

    if source.is_dir():
        return read_profile_capsule_source(source)
    return read_profile_capsule_archive(source)


def _restore_lines(outcome: ProfileRestoreOutcome) -> tuple[str, ...]:
    """Render the non-secret facts of one completed restore.

    ``recovery_enrolled`` is stated on every restore, not only when it is
    false. Recovery can be installed only at publication and a restore IS the
    publication, so this is the operator's last chance to learn that the
    profile they just recovered has no second door.
    """
    return (
        f"profile_id\t{outcome.profile_id}",
        f"label\t{outcome.label}",
        f"authority\t{outcome.authority}",
        f"recovery_enrolled\t{'yes' if outcome.recovery_enrolled else 'no'}",
    )


def register_restore_commands(profile_app: typer.Typer) -> None:
    """Mount ``config profile restore`` on ``profile_app``."""

    @profile_app.command("restore", help=tr("cli.config.profile.restore.help"))
    @command_execution_policy(BOOTSTRAP_WRITE)
    def profile_restore(
        ctx: typer.Context,
        label: str = typer.Argument(..., help=tr("cli.config.profile.restore.label_help")),
        file: Path = typer.Option(
            ...,
            "--file",
            help=tr("cli.config.profile.restore.file_help"),
            exists=True,
            file_okay=True,
            dir_okay=True,
            readable=True,
        ),
        artifact: Path | None = typer.Option(
            None,
            "--artifact",
            help=tr("cli.config.profile.restore.artifact_help"),
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
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
        """Republish a capsule directory as a usable profile."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import (
            restore_profile_capsule_with_password,
            restore_profile_capsule_with_recovery_artifact,
        )
        from .._config_payloads import ConfigProfileRestoreResult
        from ._secure_input import resolve_secrets_channel

        resolve_secrets_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)

        # Read before prompting: a source that will not parse should refuse
        # before the operator is asked for a secret they then have to retype.
        capsule = _read_capsule_source(file)

        notices: list[Notice] = []
        if artifact is None:
            outcome = restore_profile_capsule_with_password(
                label=label,
                capsule=capsule,
                password=_collect_password(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd),
            )
        else:
            outcome = restore_profile_capsule_with_recovery_artifact(
                label=label,
                capsule=capsule,
                artifact_source=artifact,
                recovery_secret=_collect_recovery_secret(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd),
            )
            # The records are back; the credential is not. Saying so here is
            # the difference between an operator who knows to rotate and one
            # who finds out at the login prompt.
            notices.append(
                Notice(
                    severity=NoticeSeverity.WARNING,
                    code=_RECOVERY_LIMIT_NOTICE_CODE,
                    message=tr("cli.config.profile.restore.password_unchanged"),
                ),
            )

        _emit_envelope(
            ctx,
            command="config.profile.restore",
            result=ConfigProfileRestoreResult(
                profile_id=outcome.profile_id,
                label=outcome.label,
                authority=outcome.authority,
                recovery_enrolled=outcome.recovery_enrolled,
                password_unchanged=artifact is not None,
            ),
            lines=list(_restore_lines(outcome)),
            notices=notices,
        )


__all__ = ["register_restore_commands"]
