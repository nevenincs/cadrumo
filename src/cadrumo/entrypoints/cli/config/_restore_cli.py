"""The ``config profile archive import`` verb: republish a capsule an operator holds.

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
from pydantic import SecretStr

from ....core.i18n import OutputLanguage, tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import emit_envelope
from .secure_input import MachineSecretPayload, MachineSecretSelection

if TYPE_CHECKING:
    from ....application.user_profile.capsule_restore import ProfileCapsuleSource, ProfileRestoreOutcome

_RECOVERY_LIMIT_NOTICE_CODE = "config.profile.archive.import.password_unchanged"


class RestorePassphraseSecrets(MachineSecretPayload):
    """Strict machine-channel payload for the passphrase door."""

    passphrase: SecretStr


class RestoreRecoverySecrets(MachineSecretPayload):
    """Strict machine-channel payload for the recovery-artifact door."""

    recovery_secret: SecretStr


def _collect_passphrase(*, selection: MachineSecretSelection | None) -> str:
    """Resolve the profile passphrase from one explicit channel or a verified prompt."""
    from .secure_input import prompt_secret_no_echo, read_machine_secret_payload

    if selection is not None:
        return read_machine_secret_payload(
            RestorePassphraseSecrets,
            selection=selection,
        ).passphrase.get_secret_value()
    return prompt_secret_no_echo(tr("cli.config.custody.current_passphrase_prompt"))


def _collect_recovery_secret(*, selection: MachineSecretSelection | None) -> str:
    """Resolve the 24-word recovery phrase from one explicit channel or a verified prompt."""
    from .secure_input import prompt_secret_no_echo, read_machine_secret_payload

    if selection is not None:
        return read_machine_secret_payload(
            RestoreRecoverySecrets,
            selection=selection,
        ).recovery_secret.get_secret_value()
    return prompt_secret_no_echo(tr("cli.config.profile.archive.import_recovery_secret_prompt"))


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
    from ....application.user_profile.capsule_archive import read_profile_capsule_archive
    from ....application.user_profile.capsule_restore import read_profile_capsule_source

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


def profile_archive_import(
    ctx: typer.Context,
    label: str,
    file: Path,
    artifact: Path | None = None,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Republish a capsule directory as a usable profile."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile.capsule_restore import (
        restore_profile_capsule_with_password,
        restore_profile_capsule_with_recovery_artifact,
    )
    from ..config_payloads import ConfigProfileArchiveImportResult
    from .secure_input import select_machine_secret_channel

    # Refuse an ambiguous source before reading the capsule, prompting, proving
    # custody, opening a publication transaction, or mutating storage.
    selection = select_machine_secret_channel(
        secrets_stdin=secrets_stdin,
        secrets_fd=secrets_fd,
    )

    # Read the public capsule before consuming or prompting for its credential:
    # a malformed source should not make an operator restage a secret.
    capsule = _read_capsule_source(file)

    notices: list[Notice] = []
    if artifact is None:
        outcome = restore_profile_capsule_with_password(
            label=label,
            capsule=capsule,
            password=_collect_passphrase(selection=selection),
        )
    else:
        outcome = restore_profile_capsule_with_recovery_artifact(
            label=label,
            capsule=capsule,
            artifact_source=artifact,
            recovery_secret=_collect_recovery_secret(selection=selection),
        )
        # The records are back; the credential is not. Saying so here is
        # the difference between an operator who knows to rotate and one
        # who finds out at the login prompt.
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=_RECOVERY_LIMIT_NOTICE_CODE,
                message=tr("cli.config.profile.archive.import_password_unchanged"),
            ),
        )

    emit_envelope(
        ctx,
        command="config.profile.archive.import",
        result=ConfigProfileArchiveImportResult(
            profile_id=outcome.profile_id,
            label=outcome.label,
            authority=outcome.authority,
            recovery_enrolled=outcome.recovery_enrolled,
            password_unchanged=artifact is not None,
        ),
        lines=list(_restore_lines(outcome)),
        notices=notices,
    )


__all__ = ["profile_archive_import"]
