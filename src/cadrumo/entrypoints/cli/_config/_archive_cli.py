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

from ....core.i18n import OutputLanguage
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import emit_envelope

if TYPE_CHECKING:
    from ....application.user_profile.capsule_archive import ProfileCapsuleArchiveInspection, ProfileCapsuleArchiveReceipt


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


def archive_export(
    ctx: typer.Context,
    name: str,
    output: Path,
    output_language: OutputLanguage | None = None,
) -> None:
    from ._profile_support import resolve_profile_by_label

    """Write a named profile's capsule to a sealed archive."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile.capsule_archive import export_profile_capsule_archive
    from .._config_payloads import ConfigProfileArchiveExportResult

    # The archive service takes a UUID and deliberately holds no opinion
    # about labels, so the label is resolved here through the one shared
    # resolver rather than inside the service.
    pointer = resolve_profile_by_label(name)
    receipt = export_profile_capsule_archive(
        profile_id=UUID(str(pointer.bucket_id)),  # type: ignore[attr-defined]  # reason: the injected resolver returns a ProfileBucketPointer; typing it here would import the workflow package into this module's import-time surface
        target=output,
    )

    emit_envelope(
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


def archive_inspect(
    ctx: typer.Context,
    file: Path,
    output_language: OutputLanguage | None = None,
) -> None:
    """Report an archive's plaintext header without decrypting it."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile.capsule_archive import inspect_profile_capsule_archive
    from .._config_payloads import ConfigProfileArchiveInspectResult

    inspection = inspect_profile_capsule_archive(file)

    emit_envelope(
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


__all__ = ["archive_export", "archive_inspect"]
