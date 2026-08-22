"""The ``config profile archive`` group: back a profile up to a sealed file.

Two verbs, deliberately not three. ``export`` writes a published capsule to a
sealed, AEAD-encrypted archive an operator can copy to another machine, and
``inspect`` reports what that archive discloses without any key at all.

**There is no ``import`` verb, and its absence is the design.** An archive and
a capsule directory differ only in how their material is READ; both produce a
:class:`ProfileCapsuleSource`, and from there both reach one shared publication
authority. ``config profile restore`` therefore takes either shape and tells
them apart by asking the filesystem. A second import verb would be a second
door onto the same authority, and would leave an operator guessing which of two
commands restores their backup.

The archive carries the operator's records but NOT their label: the label lives
in plaintext beside the ciphertext inside a published capsule, so packing it
would leak the operator's chosen name to anyone holding the file. The label is
supplied by the operator at restore instead. That is also why ``inspect``
reports no label -- everything it prints is readable by anyone with a copy.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import typer

from ....core.i18n import OutputLanguage, tr
from .._command_policy import command_execution_policy
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from ._execution_policies import BOOTSTRAP_WRITE, PROFILE_READ, declare_metadata_group

if TYPE_CHECKING:
    from collections.abc import Callable

    from ....application.user_profile import (
        ProfileCapsuleArchiveInspection,
        ProfileCapsuleArchiveReceipt,
    )


def _export_lines(receipt: ProfileCapsuleArchiveReceipt) -> tuple[str, ...]:
    """Render the non-secret facts of one completed export.

    ``recovery_enrolled`` is reported here and is deliberately NOT discoverable
    from the archive itself: the recovery slot is constant-width whether the
    profile enrolled or not, so an operator can be told, while someone holding
    a copy of the file cannot infer it.
    """
    return (
        f"bucket_id\t{receipt.bucket_id}",
        f"target\t{receipt.target}",
        f"archive_schema_version\t{receipt.archive_schema_version}",
        f"recovery_enrolled\t{'yes' if receipt.recovery_enrolled else 'no'}",
    )


def _inspect_lines(inspection: ProfileCapsuleArchiveInspection) -> tuple[str, ...]:
    """Render the plaintext header, which is all an archive discloses unkeyed."""
    return (
        f"product\t{inspection.product}",
        f"bucket_id\t{inspection.bucket_id}",
        f"archive_schema_version\t{inspection.archive_schema_version}",
        f"created_at\t{inspection.created_at.isoformat()}",
        f"manifest_digest\t{inspection.manifest_digest}",
    )


def register_archive_commands(
    profile_app: typer.Typer,
    *,
    resolve_profile_by_label: Callable[[str], object],
) -> None:
    """Mount the ``config profile archive`` group on ``profile_app``.

    ``resolve_profile_by_label`` is injected rather than imported so this
    module does not grow its own opinion about how profiles are named; it is
    the same resolver the delete verb uses, so an ambiguous or unknown label
    refuses identically across the surface.
    """
    archive_app = typer.Typer(
        help=tr("cli.config.profile.archive.help"),
        no_args_is_help=True,
    )

    @archive_app.command("export", help=tr("cli.config.profile.archive.export_help"))
    @command_execution_policy(BOOTSTRAP_WRITE)
    def archive_export(
        ctx: typer.Context,
        name: str = typer.Argument(..., help=tr("cli.config.profile.archive.export_name_help")),
        output: Path = typer.Option(
            ...,
            "--output",
            help=tr("cli.config.profile.archive.export_out_help"),
            dir_okay=False,
            writable=True,
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Write a named profile's capsule to a sealed archive."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import export_profile_capsule_archive
        from .._config_payloads import ConfigProfileArchiveExportResult

        # The archive service takes a UUID and deliberately holds no opinion
        # about labels, so the label is resolved here through the one shared
        # resolver rather than inside the service.
        pointer = resolve_profile_by_label(name)
        receipt = export_profile_capsule_archive(
            profile_id=UUID(str(pointer.bucket_id)),  # type: ignore[attr-defined]  # reason: the injected resolver returns a ProfileBucketPointer; typing it here would import the workflow package into this module's import-time surface
            target=output,
        )

        _emit_envelope(
            ctx,
            command="config.profile.archive.export",
            result=ConfigProfileArchiveExportResult(
                bucket_id=receipt.bucket_id,
                target=receipt.target,
                archive_schema_version=receipt.archive_schema_version,
                recovery_enrolled=receipt.recovery_enrolled,
            ),
            lines=list(_export_lines(receipt)),
        )

    @archive_app.command("inspect", help=tr("cli.config.profile.archive.inspect_help"))
    @command_execution_policy(PROFILE_READ)
    def archive_inspect(
        ctx: typer.Context,
        file: Path = typer.Option(
            ...,
            "--file",
            help=tr("cli.config.profile.archive.inspect_path_help"),
            exists=True,
            dir_okay=False,
            readable=True,
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Report an archive's plaintext header without decrypting it."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import inspect_profile_capsule_archive
        from .._config_payloads import ConfigProfileArchiveInspectResult

        inspection = inspect_profile_capsule_archive(file)

        _emit_envelope(
            ctx,
            command="config.profile.archive.inspect",
            result=ConfigProfileArchiveInspectResult(
                product=inspection.product,
                bucket_id=inspection.bucket_id,
                archive_schema_version=inspection.archive_schema_version,
                created_at=inspection.created_at,
                manifest_digest=inspection.manifest_digest,
            ),
            lines=list(_inspect_lines(inspection)),
        )

    declare_metadata_group(archive_app)
    profile_app.add_typer(archive_app, name="archive")


__all__ = ["register_archive_commands"]
