"""Sealed bucket-archive command registration for ``aeat config profile archive``.

``config profile export``/``import`` (registered in :mod:`._profile_bundle`)
carry a structured-only cleartext bundle and are explicitly NOT a full backup
(see the not-a-full-backup :class:`~core.json_contract.Notice` it emits).
This module wires the sealed, AEAD-encrypted full-custody transport that
:class:`~application.bucket_maintenance.BucketMaintenanceService`
already implements as ``export``/``import_``/``inspect`` — it is the true
backup/restore surface: attachment evidence bytes, the audit trail, and the
cross-period calculation inputs all ride inside the sealed archive.

The verbs delegate every write to the existing service methods
(``composition-service-no-parallel-write-path``); this module owns only CLI
argument parsing, pointer resolution, and envelope emission.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import _emit_envelope, _no_active_profile_refusal
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

if TYPE_CHECKING:
    from ....application.workflow import ProfileBucketPointer


def register_bucket_archive_commands(
    profile_app: typer.Typer,
    *,
    resolve_profile_by_label: Callable[[str], ProfileBucketPointer],
    resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None],
) -> None:
    """Register the sealed archive ``export``/``import``/``inspect`` commands."""
    archive_app = typer.Typer(
        name="archive",
        help=tr(
            "cli.config.profile.archive.help",
            default=(
                "Back up and restore a profile as a sealed, AEAD-encrypted "
                "archive (the full-custody recovery transport)."
            ),
        ),
        no_args_is_help=True,
    )
    _register_archive_export_command(
        archive_app,
        resolve_profile_by_label=resolve_profile_by_label,
        resolve_active_profile_pointer=resolve_active_profile_pointer,
    )
    _register_archive_import_command(archive_app)
    _register_archive_inspect_command(archive_app)
    profile_app.add_typer(archive_app, name="archive")


def _resolve_target_pointer(
    name: str | None,
    *,
    resolve_profile_by_label: Callable[[str], ProfileBucketPointer],
    resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None],
) -> ProfileBucketPointer:
    if name is not None:
        return resolve_profile_by_label(name)
    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise _no_active_profile_refusal()
    return pointer


def _register_archive_export_command(
    archive_app: typer.Typer,
    *,
    resolve_profile_by_label: Callable[[str], ProfileBucketPointer],
    resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None],
) -> None:
    @archive_app.command(
        "export",
        help=tr(
            "cli.config.profile.archive.export_help",
            default=(
                "Write a sealed, AEAD-encrypted full-backup archive to PATH; add "
                "--recovery-wrap-passphrase before email or cross-host transfer."
            ),
        ),
    )
    def config_profile_archive_export(
        ctx: typer.Context,
        name: str | None = typer.Argument(
            None,
            help=tr(
                "cli.config.profile.archive.export_name_help",
                default="Profile to back up; defaults to active.",
            ),
        ),
        out: Path = typer.Option(
            ...,
            "--to",
            help=tr("cli.config.profile.archive.export_out_help", default="Destination path for the archive."),
        ),
        recovery_wrap_passphrase: str | None = typer.Option(
            None,
            "--recovery-wrap-passphrase",
            help=tr(
                "cli.config.profile.archive.export_recovery_wrap_help",
                default=(
                    "Optional passphrase to seal the archive under, instead of "
                    "the active bucket key; required if the archive will leave this host."
                ),
            ),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Write a sealed full-custody archive through BucketMaintenanceService.export."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import BucketMaintenanceService, ExportBucketCommand
        from ....domain.user_profile import ProfileNotFoundError
        from .._config_payloads import ConfigProfileArchiveExportResult

        pointer = _resolve_target_pointer(
            name,
            resolve_profile_by_label=resolve_profile_by_label,
            resolve_active_profile_pointer=resolve_active_profile_pointer,
        )
        try:
            outcome = BucketMaintenanceService().export(
                ExportBucketCommand(
                    bucket_id=pointer.bucket_id,
                    output_path=out,
                    recovery_wrap_passphrase=recovery_wrap_passphrase,
                ),
            )
        except ProfileNotFoundError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": pointer.label},
            ) from exc

        result = ConfigProfileArchiveExportResult(
            profile_id=outcome.bucket_id,
            display_name=pointer.label,
            out=str(outcome.output_path),
            manifest_digest=outcome.manifest_digest,
            recovery_wrap_present=outcome.recovery_wrap_present,
        )
        completeness_notice = _build_export_completeness_notice()
        _emit_envelope(
            ctx,
            command="config.profile.archive.export",
            result=result,
            lines=(
                f"profile_id\t{outcome.bucket_id}",
                f"display_name\t{pointer.label}",
                f"out\t{outcome.output_path}",
                f"manifest_digest\t{outcome.manifest_digest}",
                f"recovery_wrap_present\t{outcome.recovery_wrap_present}",
                f"INFO\t{completeness_notice.message}",
            ),
            notices=(completeness_notice,),
        )


def _build_export_completeness_notice() -> Notice:
    """Build the info notice confirming this archive is the full-backup transport.

    ``config profile export`` emits a WARNING that it is NOT a full backup;
    the sealed archive is the transport that IS. This info notice is the
    positive counterpart, so an operator comparing the two verbs in the
    same session sees the completeness claim stated explicitly on both
    sides rather than only as an absence on one.
    """
    return Notice(
        severity=NoticeSeverity.INFO,
        code="config.profile.archive.export.full_backup",
        message=tr(
            "cli.config.profile.archive.export_full_backup_info",
            default=(
                "This archive is a FULL backup: it is AEAD-encrypted at rest and "
                "carries attachment evidence bytes, the audit trail, and the "
                "cross-period calculation inputs, in addition to the profile, "
                "ledger, calculation, and filing history. When exported with "
                "--recovery-wrap-passphrase it is the encrypted cross-host transfer "
                "path for profile bundles. Store it somewhere safe; restore with "
                "'aeat config profile archive import'."
            ),
        ),
    )


def _register_archive_import_command(archive_app: typer.Typer) -> None:
    @archive_app.command(
        "import",
        help=tr(
            "cli.config.profile.archive.import_help",
            default="Restore a profile from a sealed, encrypted archive at PATH.",
        ),
    )
    def config_profile_archive_import(
        ctx: typer.Context,
        path: Path = typer.Argument(
            ...,
            help=tr("cli.config.profile.archive.import_path_help", default="Path to the sealed archive."),
        ),
        force: bool = typer.Option(
            False,
            "--force",
            help=tr(
                "cli.config.profile.archive.import_force_help",
                default="Overwrite an existing profile that shares the archive's bucket id.",
            ),
        ),
        recovery_wrap_passphrase: str | None = typer.Option(
            None,
            "--recovery-wrap-passphrase",
            help=tr(
                "cli.config.profile.archive.import_recovery_wrap_help",
                default="Passphrase to unseal the archive; required if it was exported with one.",
            ),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Restore a sealed full-custody archive through BucketMaintenanceService.import_."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import BucketMaintenanceService, ImportBucketCommand
        from .._config_payloads import ConfigProfileArchiveImportResult

        if not path.is_file():
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.import_missing_bundle",
                context={"path": str(path)},
            )
        outcome = BucketMaintenanceService().import_(
            ImportBucketCommand(
                source_path=path,
                force_replace=force,
                recovery_wrap_passphrase=recovery_wrap_passphrase,
            ),
        )

        result = ConfigProfileArchiveImportResult(
            profile_id=outcome.bucket_id,
            manifest_digest=outcome.manifest_digest,
            archive_schema_version=outcome.archive_schema_version,
        )
        from ....application.workflow import read_profile_bucket_by_id

        restored_pointer = read_profile_bucket_by_id(outcome.bucket_id)
        # ImportBucketResult carries no display label; the restored bucket's
        # own manifest (written by the import itself) is the source of truth
        # for it. A missing manifest read here would mean the import call
        # above already failed, so this is a defensive fallback, not the
        # expected path.
        label = restored_pointer.label if restored_pointer is not None else outcome.bucket_id
        switch_notice = _build_archive_import_active_switch_notice(label)
        _emit_envelope(
            ctx,
            command="config.profile.archive.import",
            result=result,
            lines=(
                f"profile_id\t{outcome.bucket_id}",
                f"manifest_digest\t{outcome.manifest_digest}",
                f"archive_schema_version\t{outcome.archive_schema_version}",
                f"INFO\t{switch_notice.message}",
            ),
            notices=(switch_notice,),
        )


def _build_archive_import_active_switch_notice(label: str) -> Notice:
    """Build the info notice naming the active-profile switch on archive import.

    Mirrors ``_build_import_active_switch_notice`` in :mod:`._profile_bundle`:
    the restored bucket is provisioned as the ACTIVE profile, so subsequent
    commands operate on it until the operator explicitly switches. ``label``
    is the restored profile's own operator-facing label (read back from its
    manifest, since :class:`~application.bucket_maintenance.ImportBucketResult`
    carries no label), so the message and suggestion are as complete and
    actionable as the sibling profile-bundle-import notice, never the raw
    bucket UUID or a literal unfilled placeholder.
    """
    return Notice(
        severity=NoticeSeverity.INFO,
        code="config.profile.archive.import.active_profile_switched",
        message=tr(
            "cli.config.profile.archive.import_active_switch_info",
            default=(
                "The restored profile {name} is now the ACTIVE profile; subsequent "
                "commands operate on it. Run 'aeat config login <name>' to change "
                "the active profile."
            ),
            name=label,
        ),
        suggestion=f"aeat config login {label}",
        context={"active_profile": label},
    )


def _register_archive_inspect_command(archive_app: typer.Typer) -> None:
    @archive_app.command(
        "inspect",
        help=tr(
            "cli.config.profile.archive.inspect_help",
            default="Show a sealed archive's header without decrypting or restoring it.",
        ),
    )
    def config_profile_archive_inspect(
        ctx: typer.Context,
        path: Path = typer.Argument(
            ...,
            help=tr("cli.config.profile.archive.inspect_path_help", default="Path to the sealed archive."),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Read a sealed archive's plaintext header through BucketMaintenanceService.inspect."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import BucketMaintenanceService, InspectBucketArchiveCommand
        from .._config_payloads import ConfigProfileArchiveInspectResult

        if not path.is_file():
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.import_missing_bundle",
                context={"path": str(path)},
            )
        outcome = BucketMaintenanceService().inspect(InspectBucketArchiveCommand(source_path=path))

        result = ConfigProfileArchiveInspectResult(
            profile_id=outcome.bucket_id,
            manifest_digest=outcome.manifest_digest,
            recovery_wrap_present=outcome.recovery_wrap_present,
            archive_schema_version=outcome.archive_schema_version,
            created_at=outcome.created_at,
            size_bytes=outcome.size_bytes,
        )
        _emit_envelope(
            ctx,
            command="config.profile.archive.inspect",
            result=result,
            lines=(
                f"profile_id\t{outcome.bucket_id}",
                f"manifest_digest\t{outcome.manifest_digest}",
                f"recovery_wrap_present\t{outcome.recovery_wrap_present}",
                f"archive_schema_version\t{outcome.archive_schema_version}",
                f"created_at\t{outcome.created_at.isoformat()}",
                f"size_bytes\t{outcome.size_bytes}",
            ),
        )


__all__ = ["register_bucket_archive_commands"]
