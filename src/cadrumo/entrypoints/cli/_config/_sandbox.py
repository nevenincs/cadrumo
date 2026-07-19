"""Sandboxed experiment workspace commands for ``aeat config profile sandbox``.

An operator (or an LLM agent driving the CLI) needs to run experiments
(imports, classifications, calculations) without polluting the main profile's
records, and discard the experiment cleanly afterwards — or, when the
experiment is worth keeping around for later, move it into reversible
dormancy instead of erasing it outright. A sandbox is an ordinary profile
bucket labelled with the reserved
:data:`~application.bucket_maintenance.SANDBOX_LABEL_PREFIX`; every verb
here delegates to :mod:`~application.bucket_maintenance`
(``create_sandbox`` / ``discard_sandbox`` / ``archive_sandbox`` /
``restore_sandbox`` / ``BucketMaintenanceService``), which in turn delegates
to the same atomic profile-create span and destructive-erase / soft-tombstone
primitives ``config profile create`` / ``duplicate`` / ``delete`` already use
— this module owns only CLI argument parsing, pointer resolution, and
envelope emission (``composition-service-no-parallel-write-path``).

Isolation is not a new guarantee this module invents: it is the pre-existing
per-bucket encrypted-storage boundary every profile bucket already has (one
SQLite database + one secure-object namespace root per bucket id). A sandbox
is simply a bucket an operator can create, work in, and discard on a fast,
low-ceremony lifecycle without the "is this a real client?" hesitation a bare
``config profile create`` / ``delete`` pair carries.

See Also:
    :mod:`~application.bucket_maintenance`
        Application facade that owns the sandbox lifecycle command models and
        services.
    :func:`~application.bucket_maintenance.create_sandbox`
        Service entry point behind ``sandbox create``.
    :func:`~application.bucket_maintenance.preview_discard_sandbox`
        Read-only preview path used by destructive dry runs.
    :func:`~application.bucket_maintenance.discard_sandbox`
        Guarded destructive erase path used by ``sandbox discard`` and
        ``sandbox prune``.
    :func:`~application.bucket_maintenance.archive_sandbox`
        Reversible dormancy path used by ``sandbox archive``.
    :func:`~application.bucket_maintenance.restore_sandbox`
        Reversible dormancy inverse used by ``sandbox restore``.
    :class:`~application.bucket_maintenance.SandboxMergeScope`
        Closed set of sandbox merge scopes accepted by the merge command.
"""

from __future__ import annotations

import typer

from ....application.bucket_maintenance import SandboxMergeScope
from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

sandbox_app = typer.Typer(
    name="sandbox",
    help=tr(
        "cli.config.profile.sandbox.help",
        default=("Run experiments in an isolated, discardable bucket that never touches main profile state."),
    ),
    no_args_is_help=True,
)


def register_sandbox_commands(profile_app: typer.Typer) -> None:
    """Mount the ``sandbox`` sub-app on ``config profile``."""
    _register_sandbox_create_command(sandbox_app)
    _register_sandbox_list_command(sandbox_app)
    _register_sandbox_discard_command(sandbox_app)
    _register_sandbox_prune_command(sandbox_app)
    _register_sandbox_archive_command(sandbox_app)
    _register_sandbox_restore_command(sandbox_app)
    _register_sandbox_usage_command(sandbox_app)
    _register_sandbox_merge_command(sandbox_app)
    profile_app.add_typer(sandbox_app, name="sandbox")


def _register_sandbox_create_command(app: typer.Typer) -> None:
    @app.command(
        "create",
        help=tr(
            "cli.config.profile.sandbox.create_help",
            default="Fork a new isolated sandbox bucket and activate it.",
        ),
    )
    def config_profile_sandbox_create(
        ctx: typer.Context,
        name: str = typer.Argument(
            ...,
            help=tr("cli.config.profile.sandbox.create_name_help", default="Sandbox name."),
        ),
        from_profile: str | None = typer.Option(
            None,
            "--from-profile",
            help=tr(
                "cli.config.profile.sandbox.create_from_profile_help",
                default="Seed the sandbox with an existing profile's facts (read-only source).",
            ),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Create and activate a sandbox bucket through ``create_sandbox``."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import (
            CreateSandboxCommand,
            SandboxAlreadyExistsError,
            SandboxSourceNotFoundError,
            create_sandbox,
        )
        from .._config_sandbox_payloads import ConfigProfileSandboxCreateResult

        try:
            outcome = create_sandbox(CreateSandboxCommand(name=name, from_profile=from_profile))
        except SandboxAlreadyExistsError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.already_exists",
                context={"label": exc.label},
            ) from exc
        except SandboxSourceNotFoundError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.source_not_found",
                context={"name": exc.name},
            ) from exc

        result = ConfigProfileSandboxCreateResult(
            bucket_id=outcome.bucket_id,
            label=outcome.label,
            seeded_from=outcome.seeded_from,
        )
        activation_notice = Notice(
            severity=NoticeSeverity.INFO,
            code="config.profile.sandbox.create.active",
            message=tr(
                "cli.config.profile.sandbox.create_active_info",
                default=(
                    "The sandbox is now the ACTIVE profile; every command runs against "
                    "it until you switch away or discard it."
                ),
            ),
            suggestion="aeat config profile sandbox discard",
        )
        _emit_envelope(
            ctx,
            command="config.profile.sandbox.create",
            result=result,
            lines=(
                f"bucket_id\t{outcome.bucket_id}",
                f"label\t{outcome.label}",
                f"seeded_from\t{outcome.seeded_from or '<none>'}",
                f"INFO\t{activation_notice.message}",
            ),
            notices=(activation_notice,),
        )


def _register_sandbox_list_command(app: typer.Typer) -> None:
    @app.command(
        "list",
        help=tr(
            "cli.config.profile.sandbox.list_help",
            default="List every sandbox bucket.",
        ),
    )
    def config_profile_sandbox_list(
        ctx: typer.Context,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """List every profile bucket whose label carries the sandbox prefix."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import SANDBOX_LABEL_PREFIX
        from ....application.workflow import list_profile_buckets
        from ....core import resolve_active_bucket_id
        from .._config_payloads import ProfilePointerPayload
        from .._config_sandbox_payloads import ConfigProfileSandboxListResult

        active = resolve_active_bucket_id()
        buckets = list_profile_buckets()
        rows = sorted(
            (pointer for pointer in buckets.values() if pointer.label.startswith(SANDBOX_LABEL_PREFIX)),
            key=lambda pointer: pointer.label.casefold(),
        )
        active_label = next((p.label for p in rows if p.bucket_id == active), None)
        result = ConfigProfileSandboxListResult(
            active_profile=active_label,
            sandboxes=[
                ProfilePointerPayload(
                    name=pointer.label,
                    bucket_id=pointer.bucket_id,
                    active=pointer.bucket_id == active,
                )
                for pointer in rows
            ],
        )
        if not rows:
            lines = ["sandboxes\t<none>"]
        else:
            lines = []
            for pointer in rows:
                marker = "*" if pointer.bucket_id == active else " "
                lines.append(f"{marker}\t{pointer.label}")
        _emit_envelope(ctx, command="config.profile.sandbox.list", result=result, lines=lines)


def _register_sandbox_discard_command(app: typer.Typer) -> None:
    @app.command(
        "discard",
        help=tr(
            "cli.config.profile.sandbox.discard_help",
            default="Permanently erase a sandbox bucket.",
        ),
    )
    def config_profile_sandbox_discard(
        ctx: typer.Context,
        name: str = typer.Argument(
            ...,
            help=tr("cli.config.profile.sandbox.discard_name_help", default="Sandbox name (without the prefix)."),
        ),
        confirmed: bool = typer.Option(
            False,
            "--yes",
            help=tr("cli.config.profile.sandbox.discard_yes_help", default="Confirm the destructive erase."),
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run/--no-dry-run",
            help=tr(
                "cli.config.profile.sandbox.discard_dry_run_help",
                default="Preview what the discard would remove without removing anything.",
            ),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Discard a sandbox bucket through ``discard_sandbox``, or preview it with ``--dry-run``."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import (
            DiscardSandboxCommand,
            PreviewDiscardSandboxCommand,
            SandboxDiscardRefusedError,
            SandboxNotFoundError,
            discard_sandbox,
            preview_discard_sandbox,
            sandbox_label,
        )
        from ....application.workflow import read_profile_bucket
        from ....domain.buckets import BucketDeleteRefusedError
        from .._config_sandbox_payloads import ConfigProfileSandboxDiscardResult, SandboxNamespacePayload

        label = sandbox_label(name)
        pointer = read_profile_bucket(label)
        if pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            )

        if dry_run:
            try:
                preview = preview_discard_sandbox(
                    PreviewDiscardSandboxCommand(bucket_id=pointer.bucket_id),
                )
            except SandboxNotFoundError as exc:
                raise _CliRefusedBoundaryError(
                    translated_message="cli.config.profile.sandbox.unknown_sandbox",
                    context={"name": name},
                ) from exc
            except SandboxDiscardRefusedError as exc:
                raise _CliRefusedBoundaryError(
                    translated_message="cli.config.profile.sandbox.discard_not_a_sandbox",
                    context={"name": name},
                ) from exc

            result = ConfigProfileSandboxDiscardResult(
                dry_run=True,
                bucket_id=preview.bucket_id,
                namespaces=[
                    SandboxNamespacePayload(namespace=row.namespace, row_count=row.row_count)
                    for row in preview.namespaces
                ],
            )
            lines = [
                "dry_run\ttrue",
                f"bucket_id\t{preview.bucket_id}",
                f"label\t{preview.label}",
                f"would_discard_active\t{str(preview.is_active).lower()}",
                *(f"namespace:{row.namespace}\t{row.row_count}" for row in preview.namespaces),
            ]
            _emit_envelope(ctx, command="config.profile.sandbox.discard", result=result, lines=lines)
            return

        if not confirmed:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.discard_requires_yes",
                context={"name": name},
            )
        try:
            outcome = discard_sandbox(
                DiscardSandboxCommand(bucket_id=pointer.bucket_id, confirmed=confirmed),
            )
        except SandboxNotFoundError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            ) from exc
        except SandboxDiscardRefusedError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.discard_not_a_sandbox",
                context={"name": name},
            ) from exc
        except BucketDeleteRefusedError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.discard_active_profile",
                context={"name": name},
            ) from exc

        result = ConfigProfileSandboxDiscardResult(
            dry_run=False,
            bucket_id=outcome.bucket_id,
            previous_label=outcome.previous_label,
        )
        _emit_envelope(
            ctx,
            command="config.profile.sandbox.discard",
            result=result,
            lines=(
                "dry_run\tfalse",
                f"bucket_id\t{outcome.bucket_id}",
                f"previous_label\t{outcome.previous_label}",
            ),
        )


def _register_sandbox_prune_command(app: typer.Typer) -> None:
    @app.command(
        "prune",
        help=tr(
            "cli.config.profile.sandbox.prune_help",
            default="Discard every sandbox bucket at once.",
        ),
    )
    def config_profile_sandbox_prune(
        ctx: typer.Context,
        confirmed: bool = typer.Option(
            False,
            "--yes",
            help=tr("cli.config.profile.sandbox.prune_yes_help", default="Confirm discarding every sandbox."),
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run/--no-dry-run",
            help=tr(
                "cli.config.profile.sandbox.prune_dry_run_help",
                default="Preview which sandboxes would be discarded without discarding them.",
            ),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Discard every sandbox-labelled bucket, composing ``discard_sandbox`` per row.

        Never touches a non-sandbox profile: the enumeration source
        (``list_sandboxes``) only ever names sandbox-labelled buckets, and each
        row is still discarded through the same guarded ``discard_sandbox``
        primitive ``sandbox discard`` uses. The currently active sandbox (if
        any) is deliberately NOT auto-switched away from and forced-discarded;
        it is skipped with an advisory so the operator can switch away and
        re-run, mirroring ``discard``'s own active-bucket refusal rather than
        silently forcing a profile switch as a side effect of a bulk verb.
        """
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import (
            DiscardSandboxCommand,
            discard_sandbox,
            list_sandboxes,
        )
        from ....core import resolve_active_bucket_id
        from .._config_sandbox_payloads import ConfigProfileSandboxPruneResult

        sandboxes = list_sandboxes()
        active_bucket_id = resolve_active_bucket_id()

        if not confirmed and not dry_run:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.prune_requires_yes",
            )

        if dry_run:
            result = ConfigProfileSandboxPruneResult(
                dry_run=True,
                total=len(sandboxes),
                sandboxes=[label for _, label in sandboxes],
            )
            lines = [
                "dry_run\ttrue",
                f"total\t{len(sandboxes)}",
                *(f"would_discard\t{label}" for _, label in sandboxes),
            ]
            _emit_envelope(ctx, command="config.profile.sandbox.prune", result=result, lines=lines)
            return

        discarded: list[str] = []
        skipped_active: list[str] = []
        for bucket_id, label in sandboxes:
            if bucket_id == active_bucket_id:
                skipped_active.append(label)
                continue
            outcome = discard_sandbox(DiscardSandboxCommand(bucket_id=bucket_id, confirmed=True))
            discarded.append(outcome.previous_label)

        result = ConfigProfileSandboxPruneResult(
            dry_run=False,
            total=len(sandboxes),
            discarded=discarded,
        )
        lines = [
            "dry_run\tfalse",
            f"total\t{len(sandboxes)}",
            *(f"discarded\t{label}" for label in discarded),
        ]
        notices: tuple[Notice, ...] = ()
        if skipped_active:
            skipped_notice = Notice(
                severity=NoticeSeverity.WARNING,
                code="config.profile.sandbox.prune.skipped_active",
                message=tr(
                    "cli.config.profile.sandbox.prune_skipped_active_info",
                    default=(
                        "Skipped the active sandbox %{names}; switch to another profile and re-run "
                        "'aeat config profile sandbox prune --yes' to discard it."
                    ),
                    names=", ".join(skipped_active),
                ),
                suggestion="aeat config switch",
            )
            notices = (skipped_notice,)
            lines.append(f"INFO\t{skipped_notice.message}")
        _emit_envelope(ctx, command="config.profile.sandbox.prune", result=result, lines=lines, notices=notices)


def _register_sandbox_archive_command(app: typer.Typer) -> None:
    @app.command(
        "archive",
        help=tr(
            "cli.config.profile.sandbox.archive_help",
            default="Move a sandbox into reversible dormancy without erasing it.",
        ),
    )
    def config_profile_sandbox_archive(
        ctx: typer.Context,
        name: str = typer.Argument(
            ...,
            help=tr("cli.config.profile.sandbox.archive_name_help", default="Sandbox name (without the prefix)."),
        ),
        confirmed: bool = typer.Option(
            False,
            "--yes",
            help=tr("cli.config.profile.sandbox.archive_yes_help", default="Confirm the archive."),
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run/--no-dry-run",
            help=tr(
                "cli.config.profile.sandbox.archive_dry_run_help",
                default="Preview the archive without moving the sandbox out of the live surface.",
            ),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Archive a sandbox bucket through ``archive_sandbox``, or preview it with ``--dry-run``."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import (
            ArchiveSandboxCommand,
            SandboxDiscardRefusedError,
            SandboxNotFoundError,
            archive_sandbox,
            sandbox_label,
        )
        from ....application.workflow import read_profile_bucket
        from ....domain.buckets import BucketArchiveRefusedError
        from .._config_sandbox_payloads import ConfigProfileSandboxArchiveResult

        label = sandbox_label(name)
        pointer = read_profile_bucket(label)
        if pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            )

        if dry_run:
            lines = [
                "dry_run\ttrue",
                f"bucket_id\t{pointer.bucket_id}",
                f"label\t{pointer.label}",
            ]
            result = ConfigProfileSandboxArchiveResult(bucket_id=pointer.bucket_id, label=pointer.label)
            _emit_envelope(ctx, command="config.profile.sandbox.archive", result=result, lines=lines)
            return

        if not confirmed:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.archive_requires_yes",
                context={"name": name},
            )
        try:
            outcome = archive_sandbox(
                ArchiveSandboxCommand(bucket_id=pointer.bucket_id, confirmed=confirmed),
            )
        except SandboxNotFoundError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            ) from exc
        except SandboxDiscardRefusedError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.discard_not_a_sandbox",
                context={"name": name},
            ) from exc
        except BucketArchiveRefusedError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.archive_active_profile",
                context={"name": name},
            ) from exc

        result = ConfigProfileSandboxArchiveResult(bucket_id=outcome.bucket_id, label=outcome.label)
        restore_notice = Notice(
            severity=NoticeSeverity.INFO,
            code="config.profile.sandbox.archive.restorable",
            message=tr(
                "cli.config.profile.sandbox.archive_restorable_info",
                default=(
                    "The sandbox is now dormant; run 'aeat config profile sandbox restore %{name}' to bring it back."
                ),
                name=name,
            ),
            suggestion=f"aeat config profile sandbox restore {name}",
        )
        _emit_envelope(
            ctx,
            command="config.profile.sandbox.archive",
            result=result,
            lines=(
                "dry_run\tfalse",
                f"bucket_id\t{outcome.bucket_id}",
                f"label\t{outcome.label}",
                f"INFO\t{restore_notice.message}",
            ),
            notices=(restore_notice,),
        )


def _register_sandbox_restore_command(app: typer.Typer) -> None:
    @app.command(
        "restore",
        help=tr(
            "cli.config.profile.sandbox.restore_help",
            default="Bring an archived sandbox back to active status.",
        ),
    )
    def config_profile_sandbox_restore(
        ctx: typer.Context,
        name: str = typer.Argument(
            ...,
            help=tr("cli.config.profile.sandbox.restore_name_help", default="Sandbox name (without the prefix)."),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Restore an archived sandbox bucket through ``restore_sandbox``."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import (
            RestoreSandboxCommand,
            SandboxDiscardRefusedError,
            SandboxNotArchivedError,
            SandboxNotFoundError,
            restore_sandbox,
            sandbox_label,
        )
        from ....application.workflow import read_profile_bucket
        from .._config_sandbox_payloads import ConfigProfileSandboxRestoreResult

        label = sandbox_label(name)
        # The sandbox is dormant (tombstoned) after an archive, so the
        # live-surface resolver must include tombstoned candidates to find
        # it — the mirror of ``discard``'s lookup, which only ever targets
        # a live sandbox.
        pointer = read_profile_bucket(label, include_tombstoned=True)
        if pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            )

        try:
            outcome = restore_sandbox(RestoreSandboxCommand(bucket_id=pointer.bucket_id))
        except SandboxNotFoundError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            ) from exc
        except SandboxDiscardRefusedError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.discard_not_a_sandbox",
                context={"name": name},
            ) from exc
        except SandboxNotArchivedError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.restore_not_archived",
                context={"name": name},
            ) from exc

        result = ConfigProfileSandboxRestoreResult(bucket_id=outcome.bucket_id, label=outcome.label)
        _emit_envelope(
            ctx,
            command="config.profile.sandbox.restore",
            result=result,
            lines=(
                f"bucket_id\t{outcome.bucket_id}",
                f"label\t{outcome.label}",
            ),
        )


def _register_sandbox_usage_command(app: typer.Typer) -> None:
    @app.command(
        "usage",
        help=tr(
            "cli.config.profile.sandbox.usage_help",
            default="Report the on-disk footprint of one sandbox, or every sandbox at once.",
        ),
    )
    def config_profile_sandbox_usage(
        ctx: typer.Context,
        name: str | None = typer.Argument(
            None,
            help=tr(
                "cli.config.profile.sandbox.usage_name_help",
                default="Sandbox name (without the prefix); omit to report every sandbox.",
            ),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Report sandbox disk-envelope usage through ``BucketMaintenanceService.disk_usage``.

        Reads only filesystem metadata (``os.stat`` sizes) under each
        sandbox's bucket directory — never decrypted secure-object content —
        so a non-active, even archived, sandbox can be measured without
        switching into it first.
        """
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import (
            BucketMaintenanceService,
            DiskUsageBucketCommand,
            sandbox_label,
        )
        from ....application.workflow import read_profile_bucket
        from .._config_sandbox_payloads import (
            ConfigProfileSandboxUsageResult,
            SandboxDiskUsagePayload,
            SandboxDiskUsageSubdirPayload,
        )

        if name is not None:
            label = sandbox_label(name)
            pointer = read_profile_bucket(label, include_tombstoned=True)
            if pointer is None:
                raise _CliRefusedBoundaryError(
                    translated_message="cli.config.profile.sandbox.unknown_sandbox",
                    context={"name": name},
                )
            targets = ((pointer.bucket_id, pointer.label),)
        else:
            from ....application.bucket_maintenance import list_sandboxes

            targets = list_sandboxes()

        service = BucketMaintenanceService()
        rows: list[SandboxDiskUsagePayload] = []
        for bucket_id, label in targets:
            usage = service.disk_usage(DiskUsageBucketCommand(bucket_id=bucket_id))
            rows.append(
                SandboxDiskUsagePayload(
                    label=label,
                    bucket_id=bucket_id,
                    total_bytes=usage.total_bytes,
                    subdirs=[
                        SandboxDiskUsageSubdirPayload(
                            subdir=row.subdir,
                            total_bytes=row.total_bytes,
                            file_count=row.file_count,
                        )
                        for row in usage.subdirs
                    ],
                ),
            )

        total_bytes = sum(row.total_bytes for row in rows)
        result = ConfigProfileSandboxUsageResult(total_bytes=total_bytes, sandboxes=rows)
        if not rows:
            lines = ["total_bytes\t0", "sandboxes\t<none>"]
        else:
            lines = [f"total_bytes\t{total_bytes}"]
            for row in rows:
                lines.append(f"{row.label}\t{row.total_bytes}")
                for sub in row.subdirs:
                    lines.append(f"  {row.label}/{sub.subdir}\t{sub.total_bytes} bytes ({sub.file_count} files)")
        _emit_envelope(ctx, command="config.profile.sandbox.usage", result=result, lines=lines)


def _register_sandbox_merge_command(app: typer.Typer) -> None:
    @app.command(
        "merge",
        help=tr(
            "cli.config.profile.sandbox.merge_help",
            default="Promote a sandbox's ledger and/or modelo records into another profile.",
        ),
    )
    def config_profile_sandbox_merge(
        ctx: typer.Context,
        name: str = typer.Argument(
            ...,
            help=tr("cli.config.profile.sandbox.merge_name_help", default="Sandbox name (without the prefix)."),
        ),
        into: str = typer.Option(
            ...,
            "--into",
            help=tr(
                "cli.config.profile.sandbox.merge_into_help",
                default="Target profile name the sandbox's records are promoted into.",
            ),
        ),
        scope: SandboxMergeScope = typer.Option(
            SandboxMergeScope.LEDGER,
            "--scope",
            help=tr(
                "cli.config.profile.sandbox.merge_scope_help",
                default="Data category to promote: ledger, modelo, or all.",
            ),
        ),
        confirmed: bool = typer.Option(
            False,
            "--yes",
            help=tr("cli.config.profile.sandbox.merge_yes_help", default="Confirm promoting sandbox data."),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Promote ``scope`` from a sandbox into another live profile through ``merge_sandbox``.

        The sandbox (``name``) is the source; ``--into`` names the target
        profile the records are promoted into — ordinarily the operator's
        main profile. Neither bucket needs to be the currently active
        profile: both are resolved by label and the merge runs through
        scoped storage sessions per source/target.
        """
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import (
            MergeSandboxCommand,
            SandboxMergeRefusedError,
            SandboxNotFoundError,
            merge_sandbox,
            sandbox_label,
        )
        from ....application.workflow import ProfileLabelAmbiguousError, read_profile_bucket
        from .._config_sandbox_payloads import ConfigProfileSandboxMergeResult

        label = sandbox_label(name)
        source_pointer = read_profile_bucket(label)
        if source_pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            )
        try:
            target_pointer = read_profile_bucket(into)
        except ProfileLabelAmbiguousError as exc:
            raise _CliRefusedBoundaryError(
                message=f"profile name {into!r} is ambiguous; use its bucket id instead",
                context={"into": into},
            ) from exc
        if target_pointer is None:
            raise _CliRefusedBoundaryError(
                message=f"no live profile named {into!r} to merge into",
                context={"into": into},
            )
        if not confirmed:
            raise _CliRefusedBoundaryError(
                message=(
                    f"promoting sandbox {name!r} into {into!r} is a state-mutating operation. "
                    f"Re-run 'aeat config profile sandbox merge {name} --into {into} "
                    f"--scope {scope.value} --yes' to confirm."
                ),
                context={"name": name, "into": into, "scope": scope.value},
            )

        try:
            outcome = merge_sandbox(
                MergeSandboxCommand(
                    source_bucket_id=source_pointer.bucket_id,
                    target_bucket_id=target_pointer.bucket_id,
                    scope=scope,
                    confirmed=confirmed,
                ),
            )
        except SandboxNotFoundError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            ) from exc
        except SandboxMergeRefusedError as exc:
            raise _CliRefusedBoundaryError(message=str(exc), context={"name": name, "into": into}) from exc

        result = ConfigProfileSandboxMergeResult(
            scope=outcome.scope.value,
            source_label=source_pointer.label,
            target_label=target_pointer.label,
            merged_counts=outcome.merged_counts,
        )
        lines = [
            f"scope\t{outcome.scope.value}",
            f"source\t{source_pointer.label}",
            f"target\t{target_pointer.label}",
            *(f"merged:{category}\t{count}" for category, count in outcome.merged_counts.items()),
        ]
        merge_notice = Notice(
            severity=NoticeSeverity.INFO,
            code="config.profile.sandbox.merge.promoted",
            message=tr(
                "cli.config.profile.sandbox.merge_promoted_info",
                default="Promoted %{scope} from %{source} into %{target}.",
                scope=outcome.scope.value,
                source=source_pointer.label,
                target=target_pointer.label,
            ),
        )
        _emit_envelope(
            ctx,
            command="config.profile.sandbox.merge",
            result=result,
            lines=(*lines, f"INFO\t{merge_notice.message}"),
            notices=(merge_notice,),
        )


__all__ = ["register_sandbox_commands", "sandbox_app"]
