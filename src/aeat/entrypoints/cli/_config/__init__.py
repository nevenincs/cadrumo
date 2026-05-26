"""User-facing configuration facade."""

from __future__ import annotations

import asyncio
import typing
from datetime import datetime
from pathlib import Path

import click
import typer

from ....application.auth._catalogue import known_auth_provider_ids
from ....application.config_reset import CONFIG_RESET_SCOPE_CLI_VALUES, parse_config_reset_scope
from ....application.diagnostics import (
    build_config_repair_report,
    preview_quarantine_unreadable_secure_objects,
    probe_browser_connectivity,
    quarantine_unreadable_secure_objects,
    render_browser_connectivity_text,
    render_config_repair_text,
)
from ....application.operator_surface import build_help_document, render_help_text
from ....application.wizard._catalogue import SETUP_FLOW
from ....application.wizard._commands import build_wizard_command
from ....application.workflow._models import resolve_active_bucket_id
from ....application.workflow._profile_bucket_scan import read_profile_bucket
from ....core.i18n import tr
from ....core.logging import default_log_file_path
from .._command_suggestions import AeatTyperGroup
from .._common import _emit
from .._errors import CliRefusedBoundaryError

if typing.TYPE_CHECKING:
    from ....domain.buckets import BucketEvent, BucketEventType

_wizard_create_command = build_wizard_command(SETUP_FLOW, mode="create")
_wizard_edit_command = build_wizard_command(SETUP_FLOW, mode="edit")

app = typer.Typer(
    name="config",
    help=tr("cli.config.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
    add_help_option=False,
)
profile_app = typer.Typer(
    name="profile",
    help=tr("cli.config.profile.help"),
    no_args_is_help=True,
    cls=AeatTyperGroup,
)
auth_app = typer.Typer(name="auth", help=tr("cli.config.auth.help"), no_args_is_help=True)
auth_diagnostics_app = typer.Typer(
    name="diagnostics",
    help=tr("cli.config.auth.diagnostics.help", default="Inspect encrypted auth diagnostics."),
    no_args_is_help=True,
)
apoderado_app = typer.Typer(
    name="apoderado",
    help=tr("cli.config.auth.apoderado.help", default="Manage apoderado configuration"),
    no_args_is_help=True,
)
repair_app = typer.Typer(
    name="repair",
    help=tr("cli.config.repair.help"),
    no_args_is_help=False,
    invoke_without_command=True,
)
bucket_app = typer.Typer(
    name="bucket",
    help=tr("cli.config.bucket.help"),
    no_args_is_help=True,
)


@app.callback()
def config_root(
    ctx: typer.Context,
    help_: bool = typer.Option(False, "--help", "-h", help=tr("cli.config.workflow_help"), is_eager=True),
) -> None:
    """Render config-level workflow help when requested."""

    if help_ or ctx.invoked_subcommand is None:
        document = build_help_document("config")
        _emit(ctx, document, render_help_text(document).splitlines())
        raise typer.Exit()


@repair_app.callback()
def repair(ctx: typer.Context) -> None:
    """Diagnose and repair local configuration, registry, profile, auth, and log state."""

    if ctx.invoked_subcommand is not None:
        return
    report = build_config_repair_report()
    _emit(ctx, report.model_dump(mode="json"), render_config_repair_text(report).splitlines())


@repair_app.command("logs", help=tr("cli.config.repair.logs_help"))
def repair_logs(
    ctx: typer.Context,
    lines: int = typer.Option(20, "--lines", min=0, help=tr("cli.config.repair.logs_lines_help")),
) -> None:
    """Show the configured log file path and recent lines."""

    path = default_log_file_path()
    tail = _tail_lines(path, lines) if path.exists() and lines > 0 else ()
    _emit(
        ctx,
        {"path": str(path), "lines": tail},
        (f"path\t{path}", *tail),
    )


@repair_app.command("quarantine", help=tr("cli.config.repair.quarantine_help"))
def repair_quarantine(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.repair.quarantine_yes_help")),
    dry_run: bool = typer.Option(
        False,
        "--dry-run/--no-dry-run",
        help=tr("cli.config.repair.quarantine_dry_run_help"),
    ),
) -> None:
    """Move secure-object rows that fail tag verification into quarantine.

    ``--dry-run`` previews the rows that would be quarantined without
    moving anything, consistent with ``reset-state --dry-run``.
    """

    if not dry_run and not yes:
        raise CliRefusedBoundaryError(tr("cli.config.repair.quarantine_requires_yes"))
    # Cold-root guard: quarantine is bootstrap-exempt; on a root with no
    # active profile there is no per-bucket database to scan. Report
    # cleanly rather than crashing on the absent database URL
    # (disaster ADR Ruling 6).
    if resolve_active_bucket_id() is None:
        _emit(
            ctx,
            {"dry_run": dry_run, "quarantined": 0, "retained": 0, "reason": "no-active-profile"},
            (
                f"dry_run\t{str(dry_run).lower()}",
                "quarantined\t0",
                "retained\t0",
                "reason\tno active profile; nothing to quarantine",
            ),
        )
        return
    if dry_run:
        report = preview_quarantine_unreadable_secure_objects()
        payload = {"dry_run": True, **report.model_dump(mode="json")}
        _emit(
            ctx,
            payload,
            (
                "dry_run\ttrue",
                f"would_quarantine\t{report.unreadable_total}",
                f"would_retain\t{report.readable_total}",
                *tuple(
                    f"{item.namespace}\t{item.unreadable}"
                    for item in report.namespaces
                    if item.unreadable > 0
                ),
            ),
        )
        return
    report = quarantine_unreadable_secure_objects()
    _emit(
        ctx,
        {"dry_run": False, **report.model_dump(mode="json")},
        (
            "dry_run\tfalse",
            f"quarantined\t{report.unreadable_total}",
            f"retained\t{report.readable_total}",
            *tuple(f"{item.namespace}\t{item.unreadable}" for item in report.namespaces if item.unreadable > 0),
        ),
    )


def _tail_lines(path: Path, count: int) -> tuple[str, ...]:
    """Return the last ``count`` lines from ``path`` without trailing newlines.

    Reads the file from the end in bounded chunks (seek-from-end)
    rather than materialising the whole file in memory. The previous
    ``read_text().splitlines()`` implementation raised ``MemoryError``
    on a large log file (disaster ADR Ruling 6 / fumbler testimony
    F8). The chunked tail keeps memory proportional to the requested
    line count, not the file size.
    """

    if count <= 0:
        return ()
    chunk_size = 8192
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)  # SEEK_END
            file_size = handle.tell()
            blocks: list[bytes] = []
            newlines_seen = 0
            position = file_size
            # Read backwards until we have at least ``count`` newlines
            # or we have consumed the whole file.
            while position > 0 and newlines_seen <= count:
                read_size = min(chunk_size, position)
                position -= read_size
                handle.seek(position)
                block = handle.read(read_size)
                blocks.append(block)
                newlines_seen += block.count(b"\n")
            tail_bytes = b"".join(reversed(blocks))
    except OSError:
        return ()
    text = tail_bytes.decode("utf-8", errors="replace")
    return tuple(text.splitlines()[-count:])


@repair_app.command("reset-state", help=tr("cli.config.repair.reset_state_help"))
def repair_reset_state(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.repair.reset_state_yes_help")),
    dry_run: bool = typer.Option(
        False,
        "--dry-run/--no-dry-run",
        help=tr("cli.config.repair.reset_state_dry_run_help"),
    ),
) -> None:
    """Drop the unreadable workflow-state envelope and emit a reset event."""

    from ....application.workflow._persistence import fingerprint_workflow_state, reset_workflow_state

    if not dry_run and not yes:
        raise CliRefusedBoundaryError(tr("cli.config.repair.reset_state_requires_yes"))
    # Cold-root guard: reset-state is bootstrap-exempt; on a root with
    # no active profile there is no workflow-state envelope to reset.
    # Report cleanly rather than crashing on the absent per-bucket
    # database (disaster ADR Ruling 6).
    if resolve_active_bucket_id() is None:
        _emit(
            ctx,
            {"reset": False, "reason": "no-active-profile"},
            (
                "reset\tfalse",
                "reason\tno active profile; nothing to reset",
            ),
        )
        return
    if dry_run:
        fingerprint = fingerprint_workflow_state()
        payload = {"dry_run": True, "fingerprint": fingerprint.model_dump(mode="json")}
        lines = (
            "dry_run\ttrue",
            f"schema_version\t{fingerprint.schema_version if fingerprint.schema_version is not None else '<none>'}",
            f"written_at\t{fingerprint.written_at.isoformat() if fingerprint.written_at is not None else '<none>'}",
            f"byte_length\t{fingerprint.byte_length if fingerprint.byte_length is not None else '<none>'}",
            f"reason_class\t{fingerprint.reason_class}",
            f"recovered_bucket_id\t{fingerprint.recovered_bucket_id or '<none>'}",
        )
        _emit(ctx, payload, lines)
        return
    fingerprint = reset_workflow_state()
    payload = {"dry_run": False, "fingerprint": fingerprint.model_dump(mode="json")}
    lines = (
        "dry_run\tfalse",
        f"schema_version\t{fingerprint.schema_version if fingerprint.schema_version is not None else '<none>'}",
        f"written_at\t{fingerprint.written_at.isoformat() if fingerprint.written_at is not None else '<none>'}",
        f"byte_length\t{fingerprint.byte_length if fingerprint.byte_length is not None else '<none>'}",
        f"reason_class\t{fingerprint.reason_class}",
        f"recovered_bucket_id\t{fingerprint.recovered_bucket_id or '<none>'}",
    )
    _emit(ctx, payload, lines)


@repair_app.command(
    "profile",
    help=tr("cli.config.repair.profile_help"),
)
def repair_profile(
    ctx: typer.Context,
    profile: str | None = typer.Option(
        None,
        "--profile",
        help=tr("cli.config.repair.profile_name_help"),
    ),
    clear_active: bool = typer.Option(
        False,
        "--clear-active",
        help=tr("cli.config.repair.profile_clear_active_help"),
    ),
    repair_manifest_status: bool = typer.Option(
        False,
        "--repair-manifest-status",
        help=tr(
            "cli.config.repair.profile_repair_manifest_status_help",
            default="Backfill a legacy active bucket manifest status from the encrypted profile record.",
        ),
    ),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.repair.yes_help")),
) -> None:
    """Inspect profile health or safely repair a degraded active-profile pointer/manifest."""

    from ....application.workflow._models import resolve_active_bucket_id
    from ....application.workflow._profile_health import (
        repair_active_profile_manifest_status,
        repair_active_profile_pointer,
    )

    if clear_active and repair_manifest_status:
        raise CliRefusedBoundaryError(
            tr(
                "cli.config.repair.profile_one_action",
                default="Choose either --clear-active or --repair-manifest-status, not both.",
            )
        )
    if profile is not None and not clear_active and not repair_manifest_status:
        _emit_profile_record_status(ctx, profile)
        return
    if profile is not None:
        resolved = _resolve_profile_by_label(profile)
        if resolved.bucket_id != resolve_active_bucket_id():
            raise CliRefusedBoundaryError(tr("cli.config.repair.profile_clear_active_mismatch", profile=profile))
    if (clear_active or repair_manifest_status) and not yes:
        raise CliRefusedBoundaryError(tr("cli.config.repair.profile_requires_yes"))
    if repair_manifest_status:
        result = repair_active_profile_manifest_status(confirmed=yes)
        health = result.after or result.before
        lines = [
            f"dry_run\t{result.dry_run}",
            f"repaired\t{result.repaired}",
            f"active_profile\t{health.active_profile or ''}",
            f"status\t{health.status}",
            f"manifest_status\t{result.status or ''}",
            f"reason\t{result.reason}",
        ]
        if health.profile_record_error:
            lines.append(f"profile_record_error\t{health.profile_record_error}")
        if health.next_action:
            lines.append(f"next_action\t{health.next_action}")
        _emit(ctx, result.model_dump(mode="json"), lines)
        return
    result = repair_active_profile_pointer(clear_active=clear_active, confirmed=yes)
    health = result.after or result.before
    payload = result.model_dump(mode="json")
    lines = [
        f"dry_run\t{result.dry_run}",
        f"cleared_pointer\t{result.cleared_pointer}",
        f"active_profile\t{health.active_profile or ''}",
        f"source\t{health.source}",
        f"status\t{health.status}",
        f"registered_bucket\t{health.registered_bucket}",
        f"profile_record_present\t{health.profile_record_present}",
        f"repairable_by_clearing_pointer\t{health.repairable_by_clearing_pointer}",
    ]
    if health.profile_record_error:
        lines.append(f"profile_record_error\t{health.profile_record_error}")
    if health.next_action:
        lines.append(f"next_action\t{health.next_action}")
    _emit(ctx, payload, lines)


def _profile_record_missing_next_action(profile_id: str, *, label: str) -> str:
    if profile_id == resolve_active_bucket_id():
        return "aeat config repair profile --clear-active --yes"
    return f"aeat config repair profile --profile {label}"


def _emit_profile_record_status(ctx: typer.Context, label: str) -> None:
    """Emit a non-secret status report for one registered profile bucket.

    ``label`` is the operator-facing profile name; it resolves to the
    immutable bucket UUID via the manifest scan.
    """

    from ....domain.user_profile import ProfileNotFoundError

    pointer = _resolve_profile_by_label(label)
    profile_id = pointer.bucket_id
    try:
        record = _read_profile_record(profile_id=profile_id, bucket_id=profile_id)
    except ProfileNotFoundError:
        payload = {
            "profile_id": profile_id,
            "bucket_id": pointer.bucket_id,
            "display_name": pointer.label,
            "registered_bucket": True,
            "profile_record_present": False,
            "status": "missing_profile_record",
            "next_action": _profile_record_missing_next_action(profile_id, label=pointer.label),
        }
        _emit(
            ctx,
            payload,
            (
                "readiness\tmissing_profile_record",
                f"profile_id\t{profile_id}",
                f"bucket_id\t{pointer.bucket_id}",
                f"display_name\t{pointer.label}",
                "registered_bucket\tpresent",
                "profile_record\tmissing",
                f"next_action\t{payload['next_action']}",
            ),
        )
        raise typer.Exit(code=2) from None
    except Exception as exc:
        payload = {
            "profile_id": profile_id,
            "bucket_id": pointer.bucket_id,
            "display_name": pointer.label,
            "registered_bucket": True,
            "profile_record_present": False,
            "status": "profile_record_unreadable",
            "error": f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else type(exc).__name__}",
            "next_action": _profile_record_unreadable_next_action(profile_id, label=pointer.label),
        }
        _emit(
            ctx,
            payload,
            (
                "readiness\tprofile_record_unreadable",
                f"profile_id\t{profile_id}",
                f"bucket_id\t{pointer.bucket_id}",
                f"display_name\t{pointer.label}",
                "registered_bucket\tpresent",
                "profile_record\tunreadable",
                f"next_action\t{payload['next_action']}",
            ),
        )
        raise typer.Exit(code=2) from exc
    payload = {
        "profile_id": record.profile_id,
        "bucket_id": pointer.bucket_id,
        "display_name": record.display_name,
        "registered_bucket": True,
        "profile_record_present": True,
        "status": record.status.value,
        "next_action": f"aeat config profile switch {pointer.label}",
    }
    _emit(
        ctx,
        payload,
        (
            "readiness\tready",
            f"display_name\t{record.display_name}",
            f"profile_id\t{record.profile_id}",
            f"bucket_id\t{pointer.bucket_id}",
            "registered_bucket\tpresent",
            "profile_record\tpresent",
            f"status\t{record.status.value}",
            f"next_action\t{payload['next_action']}",
        ),
    )


integrity_app = typer.Typer(
    name="integrity",
    help=tr(
        "cli.config.repair.integrity_help",
        default="Probe secure-object and registry integrity.",
    ),
    no_args_is_help=True,
)


@integrity_app.command(
    "objects",
    help=tr(
        "cli.config.repair.integrity_objects_help",
        default="Probe AES-256-GCM tag verification across one namespace (or all).",
    ),
)
def repair_integrity_objects(
    ctx: typer.Context,
    namespace: str | None = typer.Option(
        None,
        "--namespace",
        help=tr(
            "cli.config.repair.integrity_namespace_help",
            default="Restrict the integrity probe to one namespace.",
        ),
    ),
) -> None:
    """Wrap build_repair_integrity_report and render through _emit."""

    from ....application.repair_integrity import build_repair_integrity_report

    # Cold-root guard: integrity is bootstrap-exempt; on a root with no
    # active profile there is no per-bucket database whose secure-object
    # rows could be probed. Report cleanly rather than crashing on the
    # absent database URL (disaster ADR Ruling 6).
    if resolve_active_bucket_id() is None:
        _emit(
            ctx,
            {"readable": 0, "unreadable": 0, "status": "ok", "reason": "no-active-profile"},
            (
                "readable\t0",
                "unreadable\t0",
                "status\tok",
                "reason\tno active profile; nothing to probe",
            ),
        )
        return
    report = build_repair_integrity_report(namespace=namespace)
    payload = report.model_dump(mode="json")
    lines = [
        f"readable\t{report.readable_total}",
        f"unreadable\t{report.unreadable_total}",
        f"status\t{report.check.status}",
        f"summary\t{report.check.summary}",
    ]
    for ns in report.namespaces:
        lines.append(f"{ns.namespace}\treadable={ns.readable}\tunreadable={ns.unreadable}")
    _emit(ctx, payload, lines)


@integrity_app.command(
    "registry",
    help=tr(
        "cli.config.repair.integrity_registry_help",
        default="Run full registry validation (the opt-in cross-domain integrity probe).",
    ),
)
def repair_integrity_registry(ctx: typer.Context) -> None:
    """Run full registry validation as an explicit, opt-in verb.

    Disaster ADR Ruling 4 moves the full registry TOML parse +
    cross-domain referential-integrity gate off the ``--version``
    and bare-invocation surfaces, where it caused a multi-minute
    cold-start hang. The validation is engineer-facing and runs only
    when the operator explicitly asks for it here.
    """

    from ....application.diagnostics import build_registry_integrity_report

    report = build_registry_integrity_report()
    payload = report.model_dump(mode="json")
    lines = [
        f"status\t{report.check.status}",
        f"summary\t{report.check.summary}",
    ]
    if report.check.detail:
        lines.append(f"detail\t{report.check.detail}")
    if report.check.next_action:
        lines.append(f"next_action\t{report.check.next_action}")
    _emit(ctx, payload, lines)


repair_app.add_typer(integrity_app, name="integrity")


@repair_app.command(
    "list",
    help=tr(
        "cli.config.repair.list_help",
        default="List secure-object keys in one namespace without mutating storage.",
    ),
)
def repair_list(
    ctx: typer.Context,
    namespace: str = typer.Argument(
        ...,
        help=tr("cli.config.repair.list_namespace_help", default="Namespace to inventory."),
    ),
    include_all: bool = typer.Option(
        False,
        "--all",
        help=tr("cli.config.repair.list_all_help", default="Return every key, including readable rows."),
    ),
    only_unreadable: bool = typer.Option(
        False,
        "--unreadable",
        help=tr("cli.config.repair.list_unreadable_help", default="Restrict output to undecryptable rows."),
    ),
) -> None:
    """Render a read-only secure-object key inventory for one namespace."""

    from ....application.repair_integrity import build_repair_list_report

    if include_all and only_unreadable:
        raise CliRefusedBoundaryError(
            tr(
                "cli.config.repair.list_conflicting_flags",
                default="--all and --unreadable cannot be combined; pass one or neither.",
            )
        )
    if resolve_active_bucket_id() is None:
        _emit(
            ctx,
            {"namespace": namespace, "rows_total": 0, "reason": "no-active-profile"},
            (
                f"namespace\t{namespace}",
                "rows_total\t0",
                "reason\tno active profile; nothing to inventory",
            ),
        )
        return
    report = build_repair_list_report(
        namespace=namespace,
        include_all=include_all,
        only_unreadable=only_unreadable,
    )
    lines = [
        f"namespace\t{report.namespace}",
        f"filter\t{report.filter_mode}",
        f"readable\t{report.integrity.readable}",
        f"unreadable\t{report.integrity.unreadable}",
        f"rows_total\t{report.rows_total}",
    ]
    for row in report.rows:
        parts = [
            f"key\t{row.object_key_digest}",
            f"readable\t{'' if row.readable is None else row.readable}",
        ]
        if row.row_id is not None:
            parts.append(f"row_id\t{row.row_id}")
        if row.classification:
            parts.append(f"class\t{row.classification}")
        if row.schema_version is not None:
            parts.append(f"schema\t{row.schema_version}")
        if row.written_at is not None:
            parts.append(f"written_at\t{row.written_at.isoformat()}")
        if row.reason:
            parts.append(f"reason\t{row.reason}")
        lines.append("\t".join(parts))
    _emit(ctx, report.model_dump(mode="json"), lines)


@repair_app.command("connectivity", help=tr("cli.config.repair.connectivity_help"))
def repair_connectivity(
    ctx: typer.Context,
    target: typing.Annotated[
        str,
        typer.Option(
            "--target",
            click_type=click.Choice(("browser",)),
            help=tr("cli.config.repair.connectivity_target_help"),
        ),
    ] = "browser",
) -> None:
    """Probe outbound browser connectivity through the diagnostics backend."""

    del target
    status = probe_browser_connectivity()
    _emit(
        ctx,
        {"target": "browser", "status": status.model_dump(mode="json")},
        render_browser_connectivity_text(status).splitlines(),
    )


app.add_typer(repair_app, name="repair")


def _profile_state():
    from ....application.workflow._persistence import workflow_state_repository

    return workflow_state_repository()


def _resolve_profile_by_label(name: str):
    """Resolve an operator-supplied profile label to its bucket pointer.

    Raises :class:`CliRefusedBoundaryError` when no live profile carries
    ``name`` or when the label is ambiguous. Returns a
    :class:`ProfileBucketPointer` carrying the immutable UUID
    ``bucket_id`` and the ``label``.
    """

    try:
        pointer = read_profile_bucket(name)
    except ValueError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name)) from exc
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name))
    return pointer


def _resolve_active_profile_pointer():
    """Resolve the active profile (by UUID) to its bucket pointer or ``None``."""

    from ....application.workflow._profile_bucket_scan import read_profile_bucket_by_id

    active = resolve_active_bucket_id()
    if active is None:
        return None
    return read_profile_bucket_by_id(active)


def _atomic_create_profile(*, display_name, facts) -> str:
    """Provision a new profile bucket through the canonical atomic-create.

    Both ``config profile import`` (recovery from a backup) and
    ``config profile duplicate`` route here so every create path lands
    on the single atomic provisioner ``register_active_profile``:
    bucket directory + manifest + encrypted record + active-profile
    pointer in one all-or-nothing unit of work owned by
    ``ProfileRepository.create``, with rollback on any failure.

    A fresh immutable UUID profile identity is minted here;
    ``display_name`` is the operator-chosen label. The minted UUID is
    returned so the caller can report it.

    Cold-start: the active-profile pointer must aim at the new UUID
    before ``workflow_state_repository().update`` opens its per-bucket
    engine, and a master-key session must be active before the
    encrypted record is written. The genuine prior pointer is captured
    and restored if the surrounding span fails, closing the window the
    repository's own rollback cannot see.
    """

    from ....application.user_profile._orchestration import (
        profile_create_storage_span,
        register_active_profile,
    )
    from ....domain.user_profile import new_profile_id

    profile_id = new_profile_id()
    with profile_create_storage_span(profile_id) as routing_profile_id:
        repository = _profile_state()
        repository.update(
            lambda current: register_active_profile(
                current,
                profile_id=profile_id,
                display_name=display_name,
                facts=facts,
                # `duplicate` and `import` legitimately reproduce an
                # existing profile's tax id; the duplicate-tax-id
                # refusal applies to a fresh `profile create` only.
                enforce_unique_tax_id=False,
                routing_profile_id=routing_profile_id,
            )
        )
    return profile_id


@profile_app.command("list", help=tr("cli.config.list.help"))
def config_list(ctx: typer.Context) -> None:
    """List every registered profile via the manifest-scan helper.

    Replaces the prior behaviour that enumerated only the active
    profile's key values (Axis B / Axis D / dual-persona pain). The
    canonical source of profile-existence truth is the per-bucket
    ``manifest.toml`` file written by every profile-creation path;
    :func:`list_profile_buckets` reads them and returns the full
    set without unlocking any bucket.
    """

    from ....application.workflow._profile_bucket_scan import list_profile_buckets

    active = resolve_active_bucket_id()
    buckets = list_profile_buckets()
    rows = sorted(buckets.values(), key=lambda pointer: pointer.label.casefold())
    active_label = next((p.label for p in rows if p.bucket_id == active), None)
    payload = {
        "active_profile": active_label,
        "profiles": [
            {
                "name": pointer.label,
                "bucket_id": pointer.bucket_id,
                "active": pointer.bucket_id == active,
            }
            for pointer in rows
        ],
    }
    if not rows:
        lines = [f"active_profile\t{active_label or '<none>'}", "profiles\t<none>"]
    else:
        lines = [f"active_profile\t{active_label or '<none>'}"]
        for pointer in rows:
            marker = "*" if pointer.bucket_id == active else " "
            lines.append(f"{marker}\t{pointer.label}")
    _emit(ctx, payload, lines)


@profile_app.command("switch", help=tr("cli.config.profile.switch_help"))
def config_profile_switch(
    ctx: typer.Context,
    name: str = typer.Argument(..., help=tr("cli.config.profile.switch_name_help")),
) -> None:
    """Select an existing profile as the active profile."""

    from ....application.user_profile._orchestration import select_profile_with_lifecycle_span
    from ....domain.user_profile import ProfileNotFoundError

    pointer = read_profile_bucket(name)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name))
    _assert_profile_record_present(
        ctx, profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id, label=pointer.label
    )
    try:
        select_profile_with_lifecycle_span(pointer.bucket_id)
    except ProfileNotFoundError as exc:
        _emit_profile_record_missing(
            ctx, profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id, label=pointer.label
        )
        raise typer.Exit(code=2) from exc
    _emit(
        ctx,
        {"active_profile": pointer.label},
        (f"active_profile\t{pointer.label}",),
    )


def _assert_profile_record_present(
    ctx: typer.Context, *, profile_id: str, bucket_id: str, label: str
) -> None:
    from ....domain.user_profile import ProfileNotFoundError

    try:
        _read_profile_record(profile_id=profile_id, bucket_id=bucket_id)
    except ProfileNotFoundError:
        _emit_profile_record_missing(ctx, profile_id=profile_id, bucket_id=bucket_id, label=label)
        raise typer.Exit(code=2) from None
    except Exception as exc:
        _emit_profile_record_unreadable(ctx, profile_id=profile_id, bucket_id=bucket_id, label=label, error=exc)
        raise typer.Exit(code=2) from exc


def _emit_profile_record_missing(ctx: typer.Context, *, profile_id: str, bucket_id: str, label: str) -> None:
    payload = {
        "profile_id": profile_id,
        "bucket_id": bucket_id,
        "display_name": label,
        "registered_bucket": True,
        "profile_record_present": False,
        "configured": False,
        "next_action": _profile_record_missing_next_action(profile_id, label=label),
    }
    _emit(
        ctx,
        payload,
        (
            "readiness\tmissing_profile_record",
            f"profile_id\t{profile_id}",
            f"bucket_id\t{bucket_id}",
            f"display_name\t{label}",
            "registered_bucket\tpresent",
            "profile_record\tmissing",
            f"next_action\t{payload['next_action']}",
        ),
    )


def _profile_record_unreadable_next_action(profile_id: str, *, label: str) -> str:
    if profile_id == resolve_active_bucket_id():
        return "aeat config repair profile --clear-active --yes"
    return f"aeat config repair profile --profile {label}"


def _emit_profile_record_unreadable(
    ctx: typer.Context,
    *,
    profile_id: str,
    bucket_id: str,
    label: str,
    error: Exception,
) -> None:
    message = str(error).splitlines()[0] if str(error) else type(error).__name__
    payload = {
        "profile_id": profile_id,
        "bucket_id": bucket_id,
        "display_name": label,
        "registered_bucket": True,
        "profile_record_present": False,
        "status": "profile_record_unreadable",
        "error": f"{type(error).__name__}: {message}",
        "next_action": _profile_record_unreadable_next_action(profile_id, label=label),
    }
    _emit(
        ctx,
        payload,
        (
            "readiness\tprofile_record_unreadable",
            f"profile_id\t{profile_id}",
            f"bucket_id\t{bucket_id}",
            f"display_name\t{label}",
            "registered_bucket\tpresent",
            "profile_record\tunreadable",
            f"next_action\t{payload['next_action']}",
        ),
    )


def _read_profile_record(*, profile_id: str, bucket_id: str):
    """Read a profile record under a bucket session scoped to that profile."""

    from ....adapters.persistence.storage import has_active_bucket_session
    from ....application.user_profile._orchestration import build_lifecycle_service, profile_storage_session
    from ....application.workflow._models import resolve_active_bucket_id

    if bucket_id == resolve_active_bucket_id() and has_active_bucket_session():
        return build_lifecycle_service(bucket_id=bucket_id).read(profile_id)
    with profile_storage_session(bucket_id):
        service = build_lifecycle_service(bucket_id=bucket_id)
        return service.read(profile_id)


@profile_app.command("show", help=tr("cli.config.profile.show_help"))
def config_profile_show(
    ctx: typer.Context,
    name: str | None = typer.Argument(None, help=tr("cli.config.profile.show_name_help")),
) -> None:
    """View one profile's facts (defaults to the active profile).

    Emits a readiness header line carrying the validation outcome of the
    canonical ProfileValidationService. When blocking issues exist, the
    command exits with code 2 after rendering the report so operators
    discover the failure on stdout and via the shell exit status.
    """

    from ....application.user_profile import ProfileValidationService
    from ....application.user_profile._projections import record_to_path_values
    from ....domain.user_profile import ProfileNotFoundError, load_user_profile_schema

    if name is not None:
        # ``show`` is the inspect surface: a tombstoned profile is still
        # resolvable by name so the operator can confirm a delete and
        # read the retained record. The verb renders the tombstoned
        # status; it never reports the profile as a live ``ready`` one.
        try:
            pointer = read_profile_bucket(name, include_tombstoned=True)
        except ValueError as exc:
            raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name)) from exc
        if pointer is None:
            raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name))
    else:
        pointer = _resolve_active_profile_pointer()
        if pointer is None:
            raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    try:
        record = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError as exc:
        _emit_profile_record_missing(
            ctx, profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id, label=pointer.label
        )
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        _emit_profile_record_unreadable(
            ctx, profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id, label=pointer.label, error=exc
        )
        raise typer.Exit(code=2) from exc
    from ....domain.user_profile import UserProfileStatus

    report = ProfileValidationService(schema=load_user_profile_schema()).validate_record(record)
    blocking = [issue for issue in report.issues if issue.severity.value == "error"]
    is_tombstoned = record.status is UserProfileStatus.TOMBSTONED
    values = record_to_path_values(record)
    payload = {
        "profile_id": record.profile_id,
        "display_name": record.display_name,
        "status": record.status.value,
        # A tombstoned profile is never "valid" as a live profile, no
        # matter what the schema validator says about its fields — the
        # readiness verdict must not contradict the status line.
        "valid": not blocking and not is_tombstoned,
        "schema_version": report.schema_version,
        "issues": [issue.model_dump(mode="json") for issue in report.issues],
        "facts": [{"path": path, "value": value} for path, value in sorted(values.items())],
    }
    lines: list[str] = []
    if is_tombstoned:
        lines.append("readiness\ttombstoned")
    elif blocking:
        lines.append(f"readiness\tblocked\tissues={len(blocking)}")
    else:
        lines.append(f"readiness\tready\tissues={len(report.issues)}")
    lines.append(f"profile_id\t{record.profile_id}")
    lines.append(f"display_name\t{record.display_name}")
    lines.append(f"status\t{record.status.value}")
    for issue in report.issues:
        lines.append(f"{issue.severity.value}\t{issue.code}\t{issue.path or '-'}\t{issue.message}")
    lines.extend(f"{path}\t{value}" for path, value in sorted(values.items()))
    _emit(ctx, payload, lines)
    if blocking:
        raise typer.Exit(code=2)


@profile_app.command("delete", help=tr("cli.config.profile.delete_help"))
def config_profile_delete(
    ctx: typer.Context,
    name: str = typer.Argument(..., help=tr("cli.config.profile.delete_name_help")),
    confirmed: bool = typer.Option(False, "--yes", help=tr("cli.config.profile.delete_yes_help")),
) -> None:
    """Tombstone a profile. Immutable filing snapshots are retained."""

    from ....application.user_profile._orchestration import delete_profile_with_lifecycle_span
    from ....domain.user_profile import ProfileNotFoundError

    if not confirmed:
        raise CliRefusedBoundaryError(tr("cli.config.profile.delete_requires_yes", name=name))
    # Resolve the operator-supplied label to a bucket pointer FIRST. This
    # is a plaintext manifest scan that needs no bucket session, so an
    # unknown name surfaces a clear "unknown profile" refusal distinct
    # from any session-state diagnostic — the operator can always tell
    # whether the name exists. ``delete`` does not require a pre-existing
    # session: like ``switch``, it opens its own scoped to the target.
    pointer = _resolve_profile_by_label(name)
    deleting_active_profile = pointer.bucket_id == resolve_active_bucket_id()
    try:
        record = delete_profile_with_lifecycle_span(pointer.bucket_id)
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name)) from exc
    payload = {
        "profile_id": record.profile_id,
        "display_name": record.display_name,
        "status": record.status.value,
        "active_profile_cleared": deleting_active_profile,
    }
    lines = [
        f"profile_id\t{record.profile_id}",
        f"display_name\t{record.display_name}",
        f"status\t{record.status.value}",
    ]
    if deleting_active_profile:
        # The deleted profile was the active one; ProfileRepository.delete
        # cleared the active-profile pointer as part of the tombstone.
        # Make that consequence explicit so the operator is not left in a
        # silent no-active-profile state.
        lines.append("active_profile\t<none>")
        lines.append(f"notice\t{tr('cli.config.profile.delete_active_cleared')}")
    _emit(ctx, payload, lines)


@profile_app.command("duplicate", help=tr("cli.config.profile.duplicate_help"))
def config_profile_duplicate(
    ctx: typer.Context,
    source: str = typer.Argument(..., help=tr("cli.config.profile.duplicate_source_help")),
    target: str = typer.Argument(..., help=tr("cli.config.profile.duplicate_target_help")),
    display_name: str | None = typer.Option(
        None, "--display-name", help=tr("cli.config.profile.duplicate_display_name_help")
    ),
) -> None:
    """Copy SOURCE into TARGET as a new active profile.

    The TARGET profile lands through the canonical atomic-create
    provisioner (``register_active_profile``): the source record's
    facts are read, then a fresh bucket directory + manifest +
    encrypted record + active pointer are written in one
    all-or-nothing sequence. The prior copytree-then-rewrite path
    bypassed the provisioner and could leave a half-copied bucket on
    a crash; the atomic provisioner rolls every write back instead.
    """

    from ....application.user_profile._orchestration import ProfileAlreadyRegisteredError
    from ....application.workflow._profile_bucket_scan import read_profile_bucket
    from ....domain.user_profile import ProfileNotFoundError

    source_pointer = _resolve_profile_by_label(source)
    if read_profile_bucket(target) is not None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target))

    try:
        source_record = _read_profile_record(
            profile_id=source_pointer.bucket_id,
            bucket_id=source_pointer.bucket_id,
        )
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=source)) from exc

    try:
        target_id = _atomic_create_profile(
            display_name=display_name or target,
            facts=source_record.facts,
        )
    except ProfileAlreadyRegisteredError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target)) from exc

    _emit(
        ctx,
        {
            "source_profile_id": source_pointer.bucket_id,
            "target_profile_id": target_id,
            "display_name": display_name or target,
        },
        (
            f"source_profile_id\t{source_pointer.bucket_id}",
            f"target_profile_id\t{target_id}",
            f"display_name\t{display_name or target}",
        ),
    )


# `create` and `edit` are two closures off the same wizard flow,
# each bound to its verb. The `create` closure refuses a name that
# already has a manifest; the `edit` closure refuses a name that has
# none. The verb — not a runtime-detected pointer — is the authority
# for the create-vs-edit branch.
_config_profile_create_callback = profile_app.command(
    "create",
    help=tr(
        "cli.config.profile.create_help",
        default="Initialize a new active profile and config bucket.",
    ),
)(_wizard_create_command)


_config_profile_edit_callback = profile_app.command(
    "edit",
    help=tr(
        "cli.config.profile.edit_help",
        default="Re-run the wizard against an existing profile; updates values in place.",
    ),
)(_wizard_edit_command)


@profile_app.command(
    "rename",
    help=tr(
        "cli.config.profile.rename_help",
        default="Rename a profile by updating its display label.",
    ),
)
def config_profile_rename(
    ctx: typer.Context,
    source: str = typer.Argument(
        ..., help=tr("cli.config.profile.rename_source_help", default="Existing profile name.")
    ),
    target: str = typer.Argument(
        ..., help=tr("cli.config.profile.rename_target_help", default="New profile name.")
    ),
) -> None:
    """Rename a profile by changing its operator-visible label.

    Profile identity is an immutable UUID, so a rename is a pure label
    edit: the encrypted record display name and the plaintext bucket
    manifest label are updated, and nothing else moves. The bucket
    directory, keystore directory, secure-object key, and active-profile
    pointer are untouched.
    """

    from ....application.user_profile._orchestration import (
        ProfileAlreadyRegisteredError,
        rename_profile,
    )
    from ....domain.user_profile import ProfileNotFoundError

    pointer = _resolve_profile_by_label(source)
    try:
        record = rename_profile(profile_id=pointer.bucket_id, new_label=target)
    except ProfileAlreadyRegisteredError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target)) from exc
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=source)) from exc

    _emit(
        ctx,
        {
            "profile_id": record.profile_id,
            "previous_display_name": source,
            "display_name": record.display_name,
        },
        (
            f"profile_id	{record.profile_id}",
            f"previous_display_name	{source}",
            f"display_name	{record.display_name}",
        ),
    )


@profile_app.command(
    "export",
    help=tr(
        "cli.config.profile.export_help",
        default="Write a portable profile bundle to PATH.",
    ),
)
def config_profile_export(
    ctx: typer.Context,
    name: str | None = typer.Argument(
        None,
        help=tr("cli.config.profile.export_name_help", default="Profile to export; defaults to active."),
    ),
    out: Path = typer.Option(
        ...,
        "--to",
        help=tr("cli.config.profile.export_out_help", default="Destination path for the JSON bundle."),
    ),
) -> None:
    """Serialize a profile bundle to a JSON file.

    The bundle wraps the live :class:`UserProfileRecord` read through
    the canonical lifecycle service. ``config profile import`` is the
    symmetric reader and re-provisions the record into a fresh bucket
    via the atomic-create provisioner.
    """

    from ....domain.user_profile import ProfileNotFoundError, UserProfilePortableExport

    _profile_state().load()
    if name is not None:
        pointer = _resolve_profile_by_label(name)
    else:
        pointer = _resolve_active_profile_pointer()
        if pointer is None:
            raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    try:
        record = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=pointer.label)) from exc
    bundle = UserProfilePortableExport(profile=record)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    _emit(
        ctx,
        {
            "profile_id": pointer.bucket_id,
            "display_name": pointer.label,
            "out": str(out),
            "schema_version": bundle.bundle_schema_version,
        },
        (
            f"profile_id\t{pointer.bucket_id}",
            f"display_name\t{pointer.label}",
            f"out\t{out}",
            f"schema_version\t{bundle.bundle_schema_version}",
        ),
    )


@profile_app.command(
    "import",
    help=tr(
        "cli.config.profile.import_help",
        default="Register a portable profile bundle from PATH into the active bucket.",
    ),
)
def config_profile_import(
    ctx: typer.Context,
    path: Path = typer.Argument(
        ..., help=tr("cli.config.profile.import_path_help", default="Path to the JSON bundle.")
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        help=tr("cli.config.profile.import_label_help"),
    ),
) -> None:
    """Read a portable profile bundle from a JSON file and register it.

    The imported profile lands in its **own** bucket through the
    canonical atomic-create provisioner (``register_active_profile``):
    bucket directory + manifest + encrypted record + active pointer
    in one all-or-nothing sequence. The imported bundle is recovery
    from a backup archive, so it becomes the new active profile. A
    crash mid-import rolls every write back, leaving no phantom bucket.

    ``--label`` overrides the operator-facing display name. Re-importing
    an exported profile into a storage root that already carries it
    would otherwise dead-end on a duplicate-label refusal; ``--label``
    lands the second copy under a fresh, non-colliding label while
    still minting its own immutable UUID identity.
    """

    from ....application.user_profile._orchestration import ProfileAlreadyRegisteredError
    from ....application.workflow._profile_bucket_scan import read_profile_bucket
    from ....domain.user_profile import UserProfilePortableExport

    if not path.is_file():
        raise CliRefusedBoundaryError(
            tr(
                "cli.config.profile.import_missing_bundle",
                default=f"bundle path not found: {path}",
                path=str(path),
            )
        )
    bundle = UserProfilePortableExport.model_validate_json(path.read_text(encoding="utf-8"))
    record = bundle.profile
    # An imported bundle becomes a fresh local profile with its own
    # minted UUID identity; the bundle's stored profile_id was the
    # identity on the originating machine and is not reused. The
    # operator-facing label must not collide with a live profile —
    # `--label` lets the operator land a second copy under a new name.
    target_label = label.strip() if label is not None and label.strip() else record.display_name
    if read_profile_bucket(target_label) is not None:
        raise CliRefusedBoundaryError(
            tr("cli.config.profile.import_label_taken", name=target_label)
        )
    try:
        target_id = _atomic_create_profile(display_name=target_label, facts=record.facts)
    except ProfileAlreadyRegisteredError as exc:
        raise CliRefusedBoundaryError(
            tr("cli.config.profile.already_exists", name=target_label)
        ) from exc
    _emit(
        ctx,
        {
            "profile_id": target_id,
            "display_name": target_label,
            "schema_version": bundle.bundle_schema_version,
        },
        (
            f"profile_id\t{target_id}",
            f"display_name\t{target_label}",
            f"schema_version\t{bundle.bundle_schema_version}",
        ),
    )


@profile_app.command(
    "logout",
    help=tr(
        "cli.config.profile.logout_help",
        default="Sign out of the active profile by clearing the pointer file.",
    ),
)
def config_profile_logout(ctx: typer.Context) -> None:
    """Clear the active-profile pointer so subsequent verbs refuse without an explicit switch."""

    from ....application.user_profile._orchestration import logout_active_profile

    before = logout_active_profile()
    _emit(
        ctx,
        {"logged_out_profile": before or "", "active_profile": None},
        (f"logged_out_profile\t{before or '<none>'}",),
    )


@profile_app.command("status", help=tr("cli.config.status.help"))
def config_status(ctx: typer.Context) -> None:
    """Show the readiness of the current configuration profile."""

    from pydantic import ValidationError

    from ....application.user_profile._projections import record_to_path_values
    from ....application.wizard._catalogue import SETUP_FLOW
    from ....application.wizard._persistence import project_answers
    from ....application.workflow._persistence import workflow_state_repository
    from ....application.workflow._profile_bucket_scan import read_profile_bucket_by_id
    from ....application.workflow._profile_health import assess_active_profile_health

    profile_health = assess_active_profile_health()
    # The health snapshot carries the profile UUID; operators address
    # profiles by their label, so resolve it for every display line.
    active_uuid = profile_health.active_profile
    _active_pointer = read_profile_bucket_by_id(active_uuid) if active_uuid else None
    active_profile = _active_pointer.label if _active_pointer is not None else active_uuid
    if profile_health.status == "none":
        payload = {
            "active_profile": None,
            "registered_profile": False,
            "configured": False,
        }
        _emit(
            ctx,
            payload,
            (
                tr("cli.config.status.empty_profile"),
                f"next_action\t{profile_health.next_action}",
            ),
        )
        return
    if profile_health.status == "dangling_pointer":
        payload = {
            "active_profile": active_profile,
            "registered_profile": False,
            "configured": False,
        }
        _emit(
            ctx,
            payload,
            (
                f"profile\t{active_profile}",
                "readiness\tdangling_pointer",
                "registered_profile\tmissing",
                f"next_action\t{profile_health.next_action}",
            ),
        )
        raise typer.Exit(code=2)
    if profile_health.status in {"missing_profile_record", "profile_record_unreadable"}:
        payload = {
            "active_profile": active_profile,
            "registered_profile": True,
            "profile_record_present": False,
            "configured": False,
            "profile_record_error": profile_health.profile_record_error,
        }
        lines = [
            f"profile\t{active_profile}",
            f"readiness\t{profile_health.status}",
            "registered_profile\tpresent",
            (
                "profile_record\tunreadable"
                if profile_health.status == "profile_record_unreadable"
                else "profile_record\tmissing"
            ),
        ]
        if profile_health.profile_record_error:
            lines.append(f"profile_record_error\t{profile_health.profile_record_error}")
        lines.append(f"next_action\t{profile_health.next_action}")
        _emit(ctx, payload, lines)
        raise typer.Exit(code=2)
    state = workflow_state_repository().load()
    record = state.active_profile_record()
    values = record_to_path_values(record)
    if not values.get("identity.tax_id") or not values.get("activities.description"):
        payload = {
            "active_profile": active_profile,
            "tax_id_present": bool(values.get("identity.tax_id")),
            "activity_present": bool(values.get("activities.description")),
            "configured": False,
        }
        if active_profile is None:
            lines = (tr("cli.config.status.empty_profile"),)
        else:
            lines = (
                f"profile\t{active_profile}",
                "readiness\tblocked",
                f"identity.tax_id\t{'present' if values.get('identity.tax_id') else 'missing'}",
                f"activities.description\t{'present' if values.get('activities.description') else 'missing'}",
                f"next_action\taeat config profile edit {active_profile}",
            )
        _emit(ctx, payload, lines)
        return
    try:
        projection = project_answers(SETUP_FLOW, values)
    except ValidationError:
        payload = {
            "active_profile": active_profile,
            "profile_id": active_uuid,
            "tax_id_present": bool(values.get("identity.tax_id")),
            "activity_present": bool(values.get("activities.description")),
            "configured": False,
        }
        _emit(ctx, payload, (tr("cli.config.status.empty_profile"),))
        return
    # Operators address a profile by its display name; the immutable
    # bucket UUID is carried as a secondary `profile_id` field so the
    # report stays unambiguous after the UUID-identity cutover.
    payload = {
        "active_profile": active_profile,
        "profile_id": active_uuid,
        "tax_id_present": bool(values.get("identity.tax_id")),
        "activity_present": bool(values.get("activities.description")),
        "iva_regime": values.get("iva.regime", ""),
        "tax_residence_ccaa": values.get("tax_residence.ccaa", ""),
        "next_action": "aeat app overview status",
    }
    _emit(
        ctx,
        payload,
        (
            f"profile\t{active_profile or ''}",
            f"profile_id\t{active_uuid or ''}",
            f"identity.tax_id\t{values.get('identity.tax_id', '<unset>')}",
            f"activities.description\t{values.get('activities.description', '<unset>')}",
            f"iva.regime\t{values.get('iva.regime', '<unset>')}",
            f"tax_residence.ccaa\t{values.get('tax_residence.ccaa', '<unset>')}",
            tr("cli.config.status.next_step"),
        ),
    )
    del projection


@app.command("reset", help=tr("cli.config.reset.help"))
def config_reset(
    ctx: typer.Context,
    scope: str = typer.Option(
        "all",
        "--scope",
        click_type=click.Choice(CONFIG_RESET_SCOPE_CLI_VALUES),
        help=tr("cli.config.reset.scope_help"),
    ),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.reset.yes_help")),
) -> None:
    """Reset operator-entered configuration scopes."""

    from ....application.config_reset import reset_config

    if not yes:
        raise CliRefusedBoundaryError(tr("cli.config.reset.requires_yes"))
    scope_enum = parse_config_reset_scope(scope)
    report = reset_config(scope_enum, confirmed=True)
    _emit(
        ctx,
        report.model_dump(mode="json"),
        (
            f"scope\t{report.scope.value}",
            f"removed_profiles\t{len(report.removed_profile_ids)}",
            f"removed_auth\t{report.removed_auth_session}",
        ),
    )


@auth_app.command("providers", help=tr("cli.config.auth.providers_help"))
def auth_providers(ctx: typer.Context) -> None:
    """List supported authentication providers from the backend catalogue."""

    from ....application.auth import list_operator_auth_providers

    report = list_operator_auth_providers()
    payload = report.model_dump(mode="json")
    _emit(
        ctx,
        payload,
        tuple(
            f"{provider.id}\t{'implemented' if provider.implemented else 'reserved'}\t{tr(str(provider.label))}"
            for provider in report.providers
        ),
    )


@auth_app.command("configure", help=tr("cli.config.auth.configure_help"))
def auth_configure(
    ctx: typer.Context,
    provider: str = typer.Option(
        ...,
        "--provider",
        click_type=click.Choice(known_auth_provider_ids()),
        help=tr("cli.config.auth.provider_help"),
    ),
    file: Path | None = typer.Option(None, "--file", help=tr("cli.config.auth.file_help")),
) -> None:
    """Configure the active authentication provider."""

    from ....application.auth import AuthProviderReservedError, configure_operator_auth
    from ....application.auth._operator import (
        AuthConfigureDanglingActiveProfileError,
        AuthConfigureNoActiveBucketError,
    )

    try:
        result = configure_operator_auth(provider, certificate_path=file)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.unknown_provider", provider=provider)) from exc
    except AuthProviderReservedError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.reserved_provider", provider=provider)) from exc
    except AuthConfigureNoActiveBucketError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.no_active_bucket")) from exc
    except AuthConfigureDanglingActiveProfileError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc
    lines = [
        f"provider\t{result.provider}",
        f"file\t{result.file}",
        f"status\t{'configured' if result.complete else 'incomplete'}",
        f"active_profile\t{result.active_profile}",
    ]
    if not result.complete:
        lines.append(f"incomplete_reason\t{result.incomplete_reason}")
    if result.provider == "clave_movil":
        lines.extend(
            (
                f"profile_tax_id\t{'present' if result.profile_tax_id_present else 'missing'}",
                f"clave_identity\t{'present' if result.provider_identity_present else 'missing'}",
                f"identity_alignment\t{result.identity_alignment}",
            )
        )
        if result.identity_alignment_detail:
            lines.append(f"identity_alignment_detail\t{result.identity_alignment_detail}")
    lines.append(f"next_action\t{result.next_action}")
    _emit(ctx, result.model_dump(mode="json"), lines)


@auth_app.command("status", help=tr("cli.config.auth.status_help"))
def auth_status(
    ctx: typer.Context,
    provider: str | None = typer.Option(None, "--provider", click_type=click.Choice(known_auth_provider_ids())),
) -> None:
    """Show the configured local authentication state."""

    from ....application.auth import inspect_operator_auth

    try:
        result = inspect_operator_auth(provider)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.unknown_provider", provider=provider or "")) from exc
    payload = result.model_dump(mode="json")
    _emit(ctx, payload, tuple(f"{key}\t{value}" for key, value in payload.items()))


@auth_app.command("test", help=tr("cli.config.auth.test_help"))
def auth_test(
    ctx: typer.Context,
    provider: str | None = typer.Option(None, "--provider", click_type=click.Choice(known_auth_provider_ids())),
) -> None:
    """Render auth readiness through the application-owned auth state."""

    from ....application.auth import AuthProviderReservedError, test_operator_auth

    try:
        result = test_operator_auth(provider)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.unknown_provider", provider=provider or "")) from exc
    except AuthProviderReservedError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.reserved_provider", provider=provider or "")) from exc
    payload = result.model_dump(mode="json")
    _emit(ctx, payload, tuple(f"{key}\t{value}" for key, value in payload.items()))


@auth_app.command("login", help=tr("cli.config.auth.login_help"))
def auth_login(
    ctx: typer.Context,
    provider: str | None = typer.Option(None, "--provider", click_type=click.Choice(known_auth_provider_ids())),
    fresh: bool = typer.Option(False, "--fresh", help=tr("cli.config.auth.login_fresh_help")),
    reset_lock: bool = typer.Option(False, "--reset-lock", help=tr("cli.config.auth.login_reset_lock_help")),
) -> None:
    """Acquire or verify a live AEAT session through the configured provider."""

    from ....application.auth import AuthProviderReservedError, login_operator_auth

    try:
        result = asyncio.run(login_operator_auth(provider, fresh=fresh, reset_lock=reset_lock))
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.unknown_provider", provider=provider or "")) from exc
    except AuthProviderReservedError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.reserved_provider", provider=provider or "")) from exc
    payload = result.model_dump(mode="json")
    _emit(ctx, payload, tuple(f"{key}\t{value}" for key, value in payload.items()))


@auth_app.command("clear", help=tr("cli.config.auth.clear_help"))
def auth_clear(
    ctx: typer.Context,
    provider: str | None = typer.Option(None, "--provider", click_type=click.Choice(known_auth_provider_ids())),
    all_providers: bool = typer.Option(False, "--all", help=tr("cli.config.auth.clear_all_help")),
    sessions: bool = typer.Option(False, "--sessions", help=tr("cli.config.auth.clear_sessions_help")),
    locks: bool = typer.Option(False, "--locks", help=tr("cli.config.auth.clear_locks_help")),
) -> None:
    """Clear local auth metadata, persisted sessions, and auth locks."""

    from ....application.auth import AuthProviderReservedError, clear_operator_auth

    try:
        result = clear_operator_auth(provider=provider, all_providers=all_providers, sessions=sessions, locks=locks)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.unknown_provider", provider=provider or "")) from exc
    except AuthProviderReservedError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.reserved_provider", provider=provider or "")) from exc
    _emit(
        ctx,
        result.model_dump(mode="json"),
        (
            f"removed_sessions\t{result.removed_sessions}",
            f"cleared_workflow_state\t{result.cleared_workflow_state}",
            f"cleared_locks\t{result.cleared_locks}",
        ),
    )


@auth_diagnostics_app.command(
    "list",
    help=tr("cli.config.auth.diagnostics.list_help", default="List encrypted Cl@ve auth diagnostics."),
)
def auth_diagnostics_list(ctx: typer.Context) -> None:
    """List encrypted auth diagnostics without revealing captured HTML/screenshots."""

    from ....application.auth import list_auth_diagnostics

    report = list_auth_diagnostics()
    lines = [f"row_count\t{report.row_count}"]
    for row in report.rows:
        lines.append(
            "\t".join(
                (
                    row.diagnostic_id or "-",
                    row.captured_at.isoformat(),
                    row.reason,
                    f"mode={row.auth_mode or '-'}",
                    f"identity_kind={row.identity_kind or '-'}",
                    f"profile={row.active_profile_label or row.active_profile_id or '-'}",
                    f"alignment={row.identity_alignment or '-'}",
                    f"headless={row.headless if row.headless is not None else '-'}",
                    f"phone_state={row.phone_state or '-'}",
                    f"html={row.html_captured}",
                    f"screenshot={row.screenshot_captured}",
                )
            )
        )
    _emit(ctx, report.model_dump(mode="json"), lines)


@auth_diagnostics_app.command(
    "show",
    help=tr("cli.config.auth.diagnostics.show_help", default="Show one redacted encrypted auth diagnostic."),
)
def auth_diagnostics_show(
    ctx: typer.Context,
    diagnostic_id: str = typer.Argument(..., help=tr("cli.config.auth.diagnostics.id_help", default="Diagnostic id")),
) -> None:
    """Show one encrypted auth diagnostic by id with sensitive bodies redacted."""

    from ....application.auth import load_auth_diagnostic

    detail = load_auth_diagnostic(diagnostic_id)
    if detail is None:
        raise CliRefusedBoundaryError(
            tr("cli.config.auth.diagnostics.not_found", diagnostic_id=diagnostic_id)
        )
    reported_at = detail.phone_state_reported_at.isoformat() if detail.phone_state_reported_at is not None else ""
    bool_value = _optional_bool_text
    _emit(
        ctx,
        detail.model_dump(mode="json"),
        (
            f"diagnostic_id\t{detail.diagnostic_id or diagnostic_id}",
            f"captured_at\t{detail.captured_at.isoformat()}",
            f"reason\t{detail.reason}",
            f"url\t{detail.url}",
            f"auth_mode\t{detail.auth_mode}",
            f"identity_kind\t{detail.identity_kind}",
            f"headless\t{detail.headless if detail.headless is not None else ''}",
            f"active_profile_id\t{detail.active_profile_id}",
            f"active_profile_label\t{detail.active_profile_label}",
            f"active_profile_registered\t{bool_value(detail.active_profile_registered)}",
            f"profile_record_present\t{bool_value(detail.profile_record_present)}",
            f"profile_tax_id_present\t{bool_value(detail.profile_tax_id_present)}",
            f"profile_tax_id_fingerprint\t{detail.profile_tax_id_fingerprint}",
            f"clave_identity_configured\t{bool_value(detail.clave_identity_configured)}",
            f"clave_identity_fingerprint\t{detail.clave_identity_fingerprint}",
            f"identity_alignment\t{detail.identity_alignment}",
            f"dni_fecha_configured\t{bool_value(detail.dni_fecha_configured)}",
            f"dni_fecha_fingerprint\t{detail.dni_fecha_fingerprint}",
            f"nie_soporte_configured\t{bool_value(detail.nie_soporte_configured)}",
            f"nie_soporte_fingerprint\t{detail.nie_soporte_fingerprint}",
            f"certificate_path_configured\t{bool_value(detail.certificate_path_configured)}",
            f"certificate_password_configured\t{bool_value(detail.certificate_password_configured)}",
            f"certificate_file_present\t{bool_value(detail.certificate_file_present)}",
            f"certificate_backend\t{detail.certificate_backend}",
            f"certificate_path_fingerprint\t{detail.certificate_path_fingerprint}",
            f"phone_state\t{detail.phone_state}",
            f"phone_state_reported_at\t{reported_at}",
            f"operator_report_commands\t{'; '.join(detail.operator_report_commands)}",
            f"html_captured\t{detail.html_captured}",
            f"screenshot_captured\t{detail.screenshot_captured}",
            f"html_excerpt\t{detail.html_excerpt or ''}",
        ),
    )


def _optional_bool_text(value: bool | None) -> str:
    return "" if value is None else str(value)


@auth_diagnostics_app.command(
    "report",
    help=tr(
        "cli.config.auth.diagnostics.report_help",
        default="Record the operator-observed Cl@ve app state for one auth diagnostic.",
    ),
)
def auth_diagnostics_report(
    ctx: typer.Context,
    diagnostic_id: str = typer.Argument(..., help=tr("cli.config.auth.diagnostics.id_help", default="Diagnostic id")),
    phone_state: str = typer.Option(
        ...,
        "--phone-state",
        help=tr(
            "cli.config.auth.diagnostics.phone_state_help",
            default=(
                "One of: app_prompted_and_accepted, app_prompted_not_accepted, "
                "app_did_not_prompt, operator_did_not_check."
            ),
        ),
    ),
) -> None:
    """Record the human-observed Cl@ve app state for a captured diagnostic."""

    from ....application.auth import AUTH_DIAGNOSTIC_PHONE_STATES, record_auth_diagnostic_phone_state

    try:
        result = record_auth_diagnostic_phone_state(diagnostic_id, phone_state)
    except ValueError as exc:
        raise CliRefusedBoundaryError(
            tr(
                "cli.config.auth.diagnostics.invalid_phone_state",
                phone_state=phone_state,
                choices=", ".join(AUTH_DIAGNOSTIC_PHONE_STATES),
            )
        ) from exc
    if result is None:
        raise CliRefusedBoundaryError(
            tr("cli.config.auth.diagnostics.not_found", diagnostic_id=diagnostic_id),
        )
    _emit(
        ctx,
        result.model_dump(mode="json"),
        (
            f"diagnostic_id\t{result.diagnostic_id}",
            f"phone_state\t{result.phone_state}",
            f"reported_at\t{result.reported_at.isoformat()}",
        ),
    )


scopes_app = typer.Typer(
    name="scopes",
    help=tr("cli.config.auth.apoderado.scopes.help", default="Manage apoderado scope vocabulary"),
    no_args_is_help=True,
)
apoderado_app.add_typer(scopes_app, name="scopes")


@scopes_app.command(
    "list", help=tr("cli.config.auth.apoderado.scopes.list_help", default="List accepted apoderado scopes")
)
def apoderado_scopes_list(ctx: typer.Context) -> None:
    """List all available representative scopes in the vocabulary."""
    from ....application.auth._apoderado import ApoderadoService

    svc = ApoderadoService()
    payload = svc.catalogue.model_dump(mode="json")
    lines = [f"{s.code}\t{tr(f'cli.config.auth.apoderado.scope.{s.code.lower()}')}" for s in svc.catalogue.scopes]
    _emit(ctx, payload, lines)


@apoderado_app.command(
    "status", help=tr("cli.config.auth.apoderado.status_help", default="Show active apoderado configuration")
)
def apoderado_status(ctx: typer.Context) -> None:
    from ....application.auth._apoderado import ApoderadoService

    pointer = _resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    svc = ApoderadoService()
    result = svc.status(bucket_id=pointer.bucket_id)

    payload = result.model_dump(mode="json")
    lines = [
        f"bucket_id\t{result.bucket_id}",
        f"configured\t{result.configured}",
    ]
    if result.configured:
        lines.append(f"represented_nif\t{result.represented_nif}")
        lines.append(f"granted_scopes\t{','.join(result.granted_scopes)}")

    _emit(ctx, payload, lines)


@apoderado_app.command(
    "configure", help=tr("cli.config.auth.apoderado.configure_help", default="Set active apoderado configuration")
)
def apoderado_configure(
    ctx: typer.Context,
    represented_nif: str = typer.Option(
        ...,
        "--represented-nif",
        help=tr("cli.config.auth.apoderado.configure.represented_nif_help", default="NIF of the represented party"),
    ),
    scope: list[str] = typer.Option(
        ...,
        "--scope",
        help=tr("cli.config.auth.apoderado.configure.scope_help", default="Scope tokens (can be repeated)"),
    ),
) -> None:
    from ....application.auth._apoderado import ApoderadoService
    from ....application.workflow._persistence import workflow_state_repository

    workflow_state_repository().load()
    pointer = _resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    svc = ApoderadoService()
    result = svc.configure(
        bucket_id=pointer.bucket_id,
        represented_nif=represented_nif,
        scope_tokens=tuple(scope),
    )

    payload = result.model_dump(mode="json")
    lines = [
        f"bucket_id\t{result.bucket_id}",
        f"represented_nif\t{result.represented_nif}",
        f"granted_scopes\t{','.join(result.granted_scopes)}",
    ]
    _emit(ctx, payload, lines)


@apoderado_app.command(
    "clear", help=tr("cli.config.auth.apoderado.clear_help", default="Retire the apoderado configuration")
)
def apoderado_clear(ctx: typer.Context) -> None:
    from ....application.auth._apoderado import ApoderadoService
    from ....application.workflow._persistence import workflow_state_repository

    workflow_state_repository().load()
    pointer = _resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    svc = ApoderadoService()
    cleared = svc.clear(bucket_id=pointer.bucket_id)

    payload = {"bucket_id": pointer.bucket_id, "cleared": cleared}
    lines = [
        f"bucket_id\t{pointer.bucket_id}",
        f"cleared\t{cleared}",
    ]
    _emit(ctx, payload, lines)


@apoderado_app.command("check", help=tr("cli.config.auth.apoderado.check_help", default="Read-only live verification"))
def apoderado_check(ctx: typer.Context) -> None:
    from ....application.auth._apoderado import ApoderadoLiveCheckUnavailableError, ApoderadoService
    from ....application.workflow._persistence import workflow_state_repository
    from ....core.errors import resolve_error_message

    workflow_state_repository().load()
    pointer = _resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    svc = ApoderadoService()

    try:
        result = svc.check(bucket_id=pointer.bucket_id)
    except ApoderadoLiveCheckUnavailableError as exc:
        # ApoderadoLiveCheckUnavailableError is a registered AeatError;
        # str(exc) is empty when it is raised message-key-based, so
        # render through resolve_error_message to keep the refusal text.
        raise CliRefusedBoundaryError(resolve_error_message(exc)) from exc

    payload = result.model_dump(mode="json")
    lines = [
        f"bucket_id\t{result.bucket_id}",
        f"configured\t{result.configured}",
    ]
    if result.configured:
        lines.append(f"represented_nif\t{result.represented_nif}")
        lines.append(f"granted_scopes\t{','.join(result.granted_scopes)}")

    _emit(ctx, payload, lines)


@bucket_app.command("history", help=tr("cli.config.bucket.history_help"))
def bucket_history(
    ctx: typer.Context,
    bucket_id: typing.Annotated[
        str,
        typer.Argument(help=tr("cli.config.bucket.bucket_id_help")),
    ],
    event_type: typing.Annotated[
        list[str] | None,
        typer.Option(
            "--event-type",
            help=tr("cli.config.bucket.event_type_help"),
        ),
    ] = None,
    since: typing.Annotated[
        str | None,
        typer.Option(
            "--since",
            help=tr("cli.config.bucket.since_help"),
        ),
    ] = None,
    until: typing.Annotated[
        str | None,
        typer.Option(
            "--until",
            help=tr("cli.config.bucket.until_help"),
        ),
    ] = None,
    object_id: typing.Annotated[
        str | None,
        typer.Option(
            "--object-id",
            help=tr("cli.config.bucket.object_id_help"),
        ),
    ] = None,
    actor: typing.Annotated[
        str | None,
        typer.Option(
            "--actor",
            help=tr("cli.config.bucket.actor_help"),
        ),
    ] = None,
) -> None:
    """Browse the append-only bucket-event history."""

    from ....domain.buckets import BucketEventHistoryRepository

    selected = _parse_bucket_event_types(event_type)
    since_dt = _parse_bucket_history_instant(since, flag="--since")
    until_dt = _parse_bucket_history_instant(until, flag="--until")
    if since_dt is not None and until_dt is not None and since_dt > until_dt:
        raise typer.BadParameter(tr("cli.config.bucket.history.since_after_until"))
    object_id_token = object_id.strip() if object_id else None
    actor_token = actor.strip() if actor else None

    catalogue = BucketEventHistoryRepository().load()
    events = tuple(
        event
        for event in catalogue.for_bucket(bucket_id, event_types=selected)
        if _bucket_history_event_matches(
            event,
            since_dt=since_dt,
            until_dt=until_dt,
            object_id_token=object_id_token,
            actor_token=actor_token,
        )
    )
    payload = {
        "operation": "config.bucket.history",
        "bucket_id": bucket_id,
        "event_types": [t.value for t in selected] if selected else None,
        "since": since_dt.isoformat() if since_dt else None,
        "until": until_dt.isoformat() if until_dt else None,
        "object_id": object_id_token,
        "actor": actor_token,
        "events": [_bucket_history_event_payload(event) for event in events],
    }
    lines = ["operation\tconfig.bucket.history", f"bucket_id\t{bucket_id}", f"event_count\t{len(events)}"] + [
        f"{e.occurred_at.isoformat()}\t{e.event_type.value}\t{e.object_type.value}\t{e.object_id}\t{e.actor}"
        for e in events
    ]
    _emit(ctx, payload, lines)


def _parse_bucket_event_types(event_type: list[str] | None) -> tuple[BucketEventType, ...] | None:
    """Parse the ``--event-type`` flag tuple, raising :class:`typer.BadParameter` on unknown values.

    Returns ``None`` when no filter was supplied so the catalogue
    walker reads the full event stream; otherwise returns a typed
    tuple of :class:`BucketEventType`.
    """
    if not event_type:
        return None
    from ....domain.buckets import BucketEventType

    parsed: list[BucketEventType] = []
    for value in event_type:
        token = value.strip()
        try:
            parsed.append(BucketEventType(token))
        except ValueError as exc:
            # str(exc) here is Python's raw "'x' is not a valid
            # BucketEventType" — untranslated and dev-flavoured. Surface a
            # localized refusal naming the bad token and the valid set.
            raise typer.BadParameter(
                tr(
                    "cli.config.bucket.history.invalid_event_type",
                    value=token,
                    valid=", ".join(member.value for member in BucketEventType),
                ),
            ) from exc
    return tuple(parsed)


def _parse_bucket_history_instant(raw: str | None, *, flag: str) -> datetime | None:
    """Parse one ``--since`` / ``--until`` value into a :class:`datetime`, or ``None`` when absent."""
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise typer.BadParameter(
            tr("cli.config.bucket.history.invalid_timestamp", flag=flag, raw=raw),
        ) from exc


def _bucket_history_event_matches(
    event: BucketEvent,
    *,
    since_dt: datetime | None,
    until_dt: datetime | None,
    object_id_token: str | None,
    actor_token: str | None,
) -> bool:
    """Return True when ``event`` passes every active history filter.

    Filters checked, in order: --since (lower bound), --until
    (upper bound), --object-id (exact match), --actor (exact match).
    ``None`` for any filter means the gate is open.
    """
    if since_dt is not None and event.occurred_at < since_dt:
        return False
    if until_dt is not None and event.occurred_at > until_dt:
        return False
    if object_id_token is not None and event.object_id != object_id_token:
        return False
    return not (actor_token is not None and event.actor != actor_token)


def _bucket_history_event_payload(event: BucketEvent) -> dict[str, object]:
    """Project one bucket event onto its JSON payload row."""
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "occurred_at": event.occurred_at.isoformat(),
        "actor": event.actor,
        "object_type": event.object_type.value,
        "object_id": event.object_id,
        "payload": dict(event.payload),
    }


from ._profile_census import register as _register_profile_census

_register_profile_census(profile_app)

app.add_typer(profile_app, name="profile")
auth_app.add_typer(apoderado_app, name="apoderado")
auth_app.add_typer(auth_diagnostics_app, name="diagnostics")
app.add_typer(auth_app, name="auth")
app.add_typer(bucket_app, name="bucket")

from ._google import google_app

app.add_typer(google_app, name="google")

__all__ = ["app"]
