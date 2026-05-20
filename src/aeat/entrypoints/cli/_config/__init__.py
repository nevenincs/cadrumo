"""User-facing configuration facade."""

from __future__ import annotations

import asyncio
import typing
from pathlib import Path

import click
import typer

from ....application.auth._catalogue import known_auth_provider_ids
from ....application.config_reset import CONFIG_RESET_SCOPE_CLI_VALUES, parse_config_reset_scope
from ....application.diagnostics import (
    build_config_repair_report,
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
from .._common import _emit
from .._errors import CliRefusedBoundaryError

_wizard_create_command = build_wizard_command(SETUP_FLOW, mode="create")
_wizard_edit_command = build_wizard_command(SETUP_FLOW, mode="edit")

app = typer.Typer(
    name="config",
    help=tr("cli.config.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
    add_help_option=False,
)
profile_app = typer.Typer(name="profile", help=tr("cli.config.profile.help"), no_args_is_help=True)
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
) -> None:
    """Move secure-object rows that fail tag verification into quarantine."""

    if not yes:
        raise CliRefusedBoundaryError(tr("cli.config.repair.quarantine_requires_yes"))
    report = quarantine_unreadable_secure_objects()
    _emit(
        ctx,
        report.model_dump(mode="json"),
        (
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
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.repair.yes_help")),
) -> None:
    """Inspect profile health or safely clear a degraded active-profile pointer."""

    from ....application.workflow._models import resolve_active_bucket_id
    from ....application.workflow._profile_health import repair_active_profile_pointer

    if profile is not None and not clear_active:
        _emit_profile_record_status(ctx, profile)
        return
    if profile is not None and profile != resolve_active_bucket_id():
        raise CliRefusedBoundaryError(tr("cli.config.repair.profile_clear_active_mismatch", profile=profile))
    if clear_active and not yes:
        raise CliRefusedBoundaryError(tr("cli.config.repair.profile_requires_yes"))
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


def _profile_record_missing_next_action(profile_id: str) -> str:
    if profile_id == resolve_active_bucket_id():
        return "aeat config repair profile --clear-active --yes"
    return f"aeat config repair profile --profile {profile_id}"


def _emit_profile_record_status(ctx: typer.Context, profile_id: str) -> None:
    """Emit a non-secret status report for one registered profile bucket."""

    from ....domain.user_profile import ProfileNotFoundError

    pointer = read_profile_bucket(profile_id)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=profile_id))
    try:
        record = _read_profile_record(profile_id=profile_id, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError:
        payload = {
            "profile_id": profile_id,
            "bucket_id": pointer.bucket_id,
            "registered_bucket": True,
            "profile_record_present": False,
            "status": "missing_profile_record",
            "next_action": _profile_record_missing_next_action(profile_id),
        }
        _emit(
            ctx,
            payload,
            (
                "readiness\tmissing_profile_record",
                f"profile_id\t{profile_id}",
                f"bucket_id\t{pointer.bucket_id}",
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
            "registered_bucket": True,
            "profile_record_present": False,
            "status": "profile_record_unreadable",
            "error": f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else type(exc).__name__}",
            "next_action": _profile_record_unreadable_next_action(profile_id),
        }
        _emit(
            ctx,
            payload,
            (
                "readiness\tprofile_record_unreadable",
                f"profile_id\t{profile_id}",
                f"bucket_id\t{pointer.bucket_id}",
                "registered_bucket\tpresent",
                "profile_record\tunreadable",
                f"next_action\t{payload['next_action']}",
            ),
        )
        raise typer.Exit(code=2) from exc
    payload = {
        "profile_id": record.profile_id,
        "bucket_id": pointer.bucket_id,
        "registered_bucket": True,
        "profile_record_present": True,
        "status": record.status.value,
        "next_action": f"aeat config profile switch {profile_id}",
    }
    _emit(
        ctx,
        payload,
        (
            "readiness\tready",
            f"profile_id\t{record.profile_id}",
            f"bucket_id\t{pointer.bucket_id}",
            "registered_bucket\tpresent",
            "profile_record\tpresent",
            f"status\t{record.status.value}",
            f"next_action\t{payload['next_action']}",
        ),
    )


@repair_app.command(
    "integrity",
    help=tr(
        "cli.config.repair.integrity_help",
        default="Probe AES-256-GCM tag verification across one namespace (or all).",
    ),
)
def repair_integrity(
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
    sorted_names = sorted(buckets)
    payload = {
        "active_profile": active,
        "profiles": [
            {"name": name, "bucket_id": buckets[name].bucket_id, "active": name == active}
            for name in sorted_names
        ],
    }
    if not sorted_names:
        lines = [f"active_profile\t{active or '<none>'}", "profiles\t<none>"]
    else:
        lines = [f"active_profile\t{active or '<none>'}"]
        for name in sorted_names:
            marker = "*" if name == active else " "
            lines.append(f"{marker}\t{name}")
    _emit(ctx, payload, lines)


@profile_app.command("switch", help=tr("cli.config.profile.switch_help"))
def config_profile_switch(
    ctx: typer.Context,
    name: str = typer.Argument(..., help=tr("cli.config.profile.switch_name_help")),
) -> None:
    """Select an existing profile as the active profile."""

    from ....application.user_profile._orchestration import select_profile
    from ....core.config import override_settings
    from ....domain.user_profile import ProfileNotFoundError

    pointer = read_profile_bucket(name)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name))
    _assert_profile_record_present(ctx, profile_id=name, bucket_id=pointer.bucket_id)
    try:
        with override_settings(aeat_active_profile=name):
            repository = _profile_state()
            repository.update(lambda current: select_profile(current, profile_id=name))
    except ProfileNotFoundError as exc:
        _emit_profile_record_missing(ctx, profile_id=name, bucket_id=pointer.bucket_id)
        raise typer.Exit(code=2) from exc
    active = resolve_active_bucket_id()
    _emit_profile_activated_event(profile_id=name, active_profile=active)
    _emit(
        ctx,
        {"active_profile": active},
        (f"active_profile\t{active or ''}",),
    )


def _assert_profile_record_present(ctx: typer.Context, *, profile_id: str, bucket_id: str) -> None:
    from ....domain.user_profile import ProfileNotFoundError

    try:
        _read_profile_record(profile_id=profile_id, bucket_id=bucket_id)
    except ProfileNotFoundError:
        _emit_profile_record_missing(ctx, profile_id=profile_id, bucket_id=bucket_id)
        raise typer.Exit(code=2) from None
    except Exception as exc:
        _emit_profile_record_unreadable(ctx, profile_id=profile_id, bucket_id=bucket_id, error=exc)
        raise typer.Exit(code=2) from exc


def _emit_profile_record_missing(ctx: typer.Context, *, profile_id: str, bucket_id: str) -> None:
    payload = {
        "profile_id": profile_id,
        "bucket_id": bucket_id,
        "registered_bucket": True,
        "profile_record_present": False,
        "configured": False,
        "next_action": _profile_record_missing_next_action(profile_id),
    }
    _emit(
        ctx,
        payload,
        (
            "readiness\tmissing_profile_record",
            f"profile_id\t{profile_id}",
            f"bucket_id\t{bucket_id}",
            "registered_bucket\tpresent",
            "profile_record\tmissing",
            f"next_action\t{payload['next_action']}",
        ),
    )


def _profile_record_unreadable_next_action(profile_id: str) -> str:
    if profile_id == resolve_active_bucket_id():
        return "aeat config repair profile --clear-active --yes"
    return f"aeat config repair profile --profile {profile_id}"


def _emit_profile_record_unreadable(
    ctx: typer.Context,
    *,
    profile_id: str,
    bucket_id: str,
    error: Exception,
) -> None:
    message = str(error).splitlines()[0] if str(error) else type(error).__name__
    payload = {
        "profile_id": profile_id,
        "bucket_id": bucket_id,
        "registered_bucket": True,
        "profile_record_present": False,
        "status": "profile_record_unreadable",
        "error": f"{type(error).__name__}: {message}",
        "next_action": _profile_record_unreadable_next_action(profile_id),
    }
    _emit(
        ctx,
        payload,
        (
            "readiness\tprofile_record_unreadable",
            f"profile_id\t{profile_id}",
            f"bucket_id\t{bucket_id}",
            "registered_bucket\tpresent",
            "profile_record\tunreadable",
            f"next_action\t{payload['next_action']}",
        ),
    )


def _read_profile_record(*, profile_id: str, bucket_id: str):
    """Read a profile record under a bucket session scoped to that profile."""

    from ....adapters.persistence.storage import (
        activate_master_key_provider,
        get_master_key_provider,
        has_active_bucket_session,
    )
    from ....application.user_profile._orchestration import build_lifecycle_service
    from ....application.workflow._models import resolve_active_bucket_id
    from ....core.config import override_settings

    if bucket_id == resolve_active_bucket_id() and has_active_bucket_session():
        return build_lifecycle_service(bucket_id=bucket_id).read(profile_id)
    with override_settings(aeat_active_profile=bucket_id):
        service = build_lifecycle_service(bucket_id=bucket_id)
        with activate_master_key_provider(get_master_key_provider(), fallback_bucket_id=bucket_id):
            return service.read(profile_id)


def _emit_profile_activated_event(*, profile_id: str, active_profile: str | None) -> None:
    """Append a PROFILE_ACTIVATED event to the bucket-event-history catalogue.

    Records the operator-visible profile-activation transition so
    downstream auditors can replay the activation timeline without
    re-deriving it from secure-object snapshots. Distinct from
    PROFILE_SELECTED (which records selection at workflow-state level)
    so the catalogue carries the explicit activation event.
    """

    from datetime import UTC, datetime

    from ....domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    if active_profile is None:
        return

    occurred_at = datetime.now(UTC)
    payload = {"profile_id": profile_id, "active_profile": active_profile}
    actor = "operator"
    bucket_id = active_profile
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=BucketEventType.PROFILE_ACTIVATED,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=profile_id,
        payload=payload,
    )
    repo = BucketEventHistoryRepository()
    repo.save(
        append_bucket_event(
            repo.load(),
            BucketEvent(
                event_id=event_id,
                bucket_id=bucket_id,
                event_type=BucketEventType.PROFILE_ACTIVATED,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PROFILE,
                object_id=profile_id,
                payload_version=1,
                payload=payload,
            ),
        )
    )


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

    from ....application.user_profile._orchestration import build_lifecycle_service
    from ....application.user_profile._projections import record_to_path_values
    from ....domain.user_profile import ProfileNotFoundError

    target = name or resolve_active_bucket_id()
    if target is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    pointer = read_profile_bucket(target)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=target))
    service = build_lifecycle_service(bucket_id=pointer.bucket_id)
    try:
        record = _read_profile_record(profile_id=target, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError as exc:
        _emit_profile_record_missing(ctx, profile_id=target, bucket_id=pointer.bucket_id)
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        _emit_profile_record_unreadable(ctx, profile_id=target, bucket_id=pointer.bucket_id, error=exc)
        raise typer.Exit(code=2) from exc
    report = service._validator.validate_record(record)
    blocking = [issue for issue in report.issues if issue.severity.value == "error"]
    values = record_to_path_values(record)
    payload = {
        "profile_id": record.profile_id,
        "display_name": record.display_name,
        "status": record.status.value,
        "valid": not blocking,
        "schema_version": report.schema_version,
        "issues": [issue.model_dump(mode="json") for issue in report.issues],
        "facts": [{"path": path, "value": value} for path, value in sorted(values.items())],
    }
    lines: list[str] = []
    if blocking:
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

    from ....application.user_profile import RemoveProfileCommand
    from ....application.user_profile._orchestration import (
        _clear_active_profile_pointer,
        build_lifecycle_service,
    )
    from ....domain.user_profile import ProfileNotFoundError

    if not confirmed:
        raise CliRefusedBoundaryError(tr("cli.config.profile.delete_requires_yes", name=name))
    repository = _profile_state()
    repository.load()
    pointer = read_profile_bucket(name)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name))
    service = build_lifecycle_service(bucket_id=pointer.bucket_id)
    try:
        result = service.remove(RemoveProfileCommand(profile_id=name))
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name)) from exc
    if resolve_active_bucket_id() == name:
        _clear_active_profile_pointer()
    _emit(
        ctx,
        {"profile_id": result.profile.profile_id, "status": result.profile.status.value},
        (f"profile_id\t{result.profile.profile_id}", f"status\t{result.profile.status.value}"),
    )


@profile_app.command("duplicate", help=tr("cli.config.profile.duplicate_help"))
def config_profile_duplicate(
    ctx: typer.Context,
    source: str = typer.Argument(..., help=tr("cli.config.profile.duplicate_source_help")),
    target: str = typer.Argument(..., help=tr("cli.config.profile.duplicate_target_help")),
    display_name: str | None = typer.Option(
        None, "--display-name", help=tr("cli.config.profile.duplicate_display_name_help")
    ),
) -> None:
    """Copy SOURCE into TARGET as a new active profile."""

    import shutil

    from ....adapters.persistence.storage.bucket._layout import bucket_paths
    from ....adapters.persistence.storage.bucket._manifest_io import read_manifest, write_manifest
    from ....adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
    from ....adapters.persistence.storage.sql.engine import dispose_engine
    from ....application.user_profile import UserProfileLifecycleRepository
    from ....application.workflow._utils import utc_now
    from ....core.config import Settings, load_settings
    from ....domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )
    from ....domain.user_profile import ProfileAlreadyExistsError, ProfileNotFoundError

    repository = _profile_state()
    repository.load()
    pointer = read_profile_bucket(source)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=source))
    if read_profile_bucket(target) is not None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target))

    settings = load_settings()
    source_paths = bucket_paths(settings.aeat_local_storage_root, source)
    target_paths = bucket_paths(settings.aeat_local_storage_root, target)

    try:
        shutil.copytree(source_paths.bucket_dir, target_paths.bucket_dir)
    except Exception as exc:
        raise CliRefusedBoundaryError(f"Failed to copy bucket directory: {exc}") from exc

    try:
        manifest = read_manifest(target_paths)
        manifest = manifest.model_copy(update={"bucket_id": target, "label": target})
        write_manifest(target_paths, manifest)
    except Exception as exc:
        raise CliRefusedBoundaryError(f"Failed to update target bucket manifest: {exc}") from exc

    dispose_engine()
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{(target_paths.db_dir / 'aeat.db').as_posix()}")
    )
    try:
        objects = SecureObjectRepository(engine=engine)
        copied_source = UserProfileLifecycleRepository(bucket_id=source, objects=objects)
        target_profiles = UserProfileLifecycleRepository(bucket_id=target, objects=objects)
        if target_profiles.exists(target):
            raise ProfileAlreadyExistsError(f"profile {target!r} already exists in bucket {target!r}")
        source_record = copied_source.load(source)
        now = utc_now()
        target_record = source_record.model_copy(
            update={
                "profile_id": target,
                "display_name": display_name or target,
                "created_at": now,
                "updated_at": now,
            }
        )
        target_profiles.save(target_record)
        copied_source.delete(source)
        events = BucketEventHistoryRepository(objects=objects)
        event = BucketEvent(
            event_id=derive_bucket_event_id(
                bucket_id=target,
                event_type=BucketEventType.PROFILE_DUPLICATED,
                occurred_at=now,
                actor="aeat.application.user_profile",
                object_type=BucketEventObjectType.PROFILE,
                object_id=target,
                payload={"source_profile_id": source},
            ),
            bucket_id=target,
            event_type=BucketEventType.PROFILE_DUPLICATED,
            occurred_at=now,
            actor="aeat.application.user_profile",
            object_type=BucketEventObjectType.PROFILE,
            object_id=target,
            payload_version=1,
            payload={"source_profile_id": source},
        )
        events.save(append_bucket_event(events.load(), event))
    except ProfileAlreadyExistsError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target)) from exc
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=source)) from exc
    finally:
        engine.dispose()

    # WorkflowState.profiles retired; the bucket manifest written by
    # the lifecycle service registration is what makes the new
    # profile appear in the manifest-scan computed mapping. Only the
    # updated_at stamp needs to advance on the encrypted record.
    repository.update(lambda current: current.model_copy(update={"updated_at": utc_now()}))
    _emit(
        ctx,
        {
            "source_profile_id": source,
            "target_profile_id": target_record.profile_id,
            "display_name": target_record.display_name,
        },
        (
            f"source_profile_id\t{source}",
            f"target_profile_id\t{target_record.profile_id}",
            f"display_name\t{target_record.display_name}",
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
        default="Rename a profile in place. The active-profile pointer follows automatically.",
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
    display_name: str | None = typer.Option(
        None,
        "--display-name",
        help=tr(
            "cli.config.profile.rename_display_name_help",
            default="Operator-visible label; defaults to the existing display name.",
        ),
    ),
) -> None:
    """Rename a profile by source NAME to target NEW NAME."""

    from ....application.user_profile import RenameProfileCommand
    from ....application.user_profile._orchestration import (
        _write_active_profile_pointer,
        build_lifecycle_service,
    )
    from ....application.workflow._utils import utc_now
    from ....domain.user_profile import ProfileAlreadyExistsError, ProfileNotFoundError

    repository = _profile_state()
    repository.load()
    pointer = read_profile_bucket(source)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=source))
    if target != source and read_profile_bucket(target) is not None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target))
    service = build_lifecycle_service(bucket_id=pointer.bucket_id)
    try:
        result = service.rename(
            RenameProfileCommand(
                source_profile_id=source,
                target_profile_id=target,
                target_display_name=display_name,
            )
        )
    except ProfileAlreadyExistsError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target)) from exc
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=source)) from exc

    was_active = resolve_active_bucket_id() == source

    import shutil

    from ....adapters.persistence.storage.bucket._layout import bucket_paths
    from ....adapters.persistence.storage.bucket._manifest_io import read_manifest, write_manifest
    from ....adapters.persistence.storage.sql.engine import dispose_engine
    from ....core.config import load_settings

    settings = load_settings()
    source_paths = bucket_paths(settings.aeat_local_storage_root, source)
    target_paths = bucket_paths(settings.aeat_local_storage_root, target)

    dispose_engine()
    try:
        shutil.move(source_paths.bucket_dir, target_paths.bucket_dir)
    except Exception as exc:
        raise CliRefusedBoundaryError(f"Failed to rename bucket directory: {exc}") from exc

    try:
        manifest = read_manifest(target_paths)
        manifest = manifest.model_copy(update={"bucket_id": target, "label": target})
        write_manifest(target_paths, manifest)
    except Exception as exc:
        raise CliRefusedBoundaryError(f"Failed to update bucket manifest: {exc}") from exc

    # WorkflowState.profiles retired; renaming the bucket directory on
    # disk is what removes ``source`` and registers ``target`` in the
    # manifest-scan view. Only the updated_at stamp needs to advance.
    repository.update(lambda current: current.model_copy(update={"updated_at": utc_now()}))
    if was_active:
        _write_active_profile_pointer(target)
    _emit(
        ctx,
        {
            "source_profile_id": source,
            "target_profile_id": result.profile.profile_id,
            "display_name": result.profile.display_name,
        },
        (
            f"source_profile_id\t{source}",
            f"target_profile_id\t{result.profile.profile_id}",
            f"display_name\t{result.profile.display_name}",
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
    """Serialize a profile bundle to a JSON file."""

    from ....application.user_profile._orchestration import build_lifecycle_service
    from ....domain.user_profile import ProfileNotFoundError

    _profile_state().load()
    target = name or resolve_active_bucket_id()
    if target is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    pointer = read_profile_bucket(target)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=target))
    service = build_lifecycle_service(bucket_id=pointer.bucket_id)
    try:
        bundle = service.export(target)
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=target)) from exc
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    _emit(
        ctx,
        {"profile_id": target, "out": str(out), "schema_version": bundle.bundle_schema_version},
        (
            f"profile_id\t{target}",
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
) -> None:
    """Read a portable profile bundle from a JSON file and register it."""

    from ....application.user_profile._orchestration import build_lifecycle_service
    from ....application.workflow._utils import utc_now
    from ....domain.user_profile import ProfileAlreadyExistsError, UserProfilePortableExport

    if not path.is_file():
        raise CliRefusedBoundaryError(
            tr(
                "cli.config.profile.import_missing_bundle",
                default=f"bundle path not found: {path}",
                path=str(path),
            )
        )
    bundle = UserProfilePortableExport.model_validate_json(path.read_text(encoding="utf-8"))
    target_id = bundle.profile.profile_id
    repository = _profile_state()
    repository.load()
    if read_profile_bucket(target_id) is not None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target_id))
    active_bucket = resolve_active_bucket_id()
    if active_bucket is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    bucket_pointer = read_profile_bucket(active_bucket)
    bucket_id = bucket_pointer.bucket_id if bucket_pointer is not None else active_bucket
    service = build_lifecycle_service(bucket_id=bucket_id)
    try:
        result = service.import_archive(bundle)
    except ProfileAlreadyExistsError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target_id)) from exc

    # WorkflowState.profiles retired; the imported bucket's manifest
    # is what registers the new profile in the manifest-scan view.
    # Only the updated_at stamp needs to advance.
    repository.update(lambda current: current.model_copy(update={"updated_at": utc_now()}))
    _emit(
        ctx,
        {
            "profile_id": result.profile.profile_id,
            "display_name": result.profile.display_name,
            "schema_version": bundle.bundle_schema_version,
        },
        (
            f"profile_id\t{result.profile.profile_id}",
            f"display_name\t{result.profile.display_name}",
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

    from ....application.user_profile._orchestration import _clear_active_profile_pointer

    before = resolve_active_bucket_id()
    _clear_active_profile_pointer()
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
    from ....application.workflow._profile_health import assess_active_profile_health

    profile_health = assess_active_profile_health()
    active_profile = profile_health.active_profile
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
            "active_profile": resolve_active_bucket_id(),
            "tax_id_present": bool(values.get("identity.tax_id")),
            "activity_present": bool(values.get("activities.description")),
            "configured": False,
        }
        _emit(ctx, payload, (tr("cli.config.status.empty_profile"),))
        return
    payload = {
        "active_profile": resolve_active_bucket_id(),
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
            f"profile\t{resolve_active_bucket_id() or ''}",
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
            f"removed_profiles\t{len(report.removed_profile_names)}",
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
        f"active_profile\t{result.active_profile}",
    ]
    if result.provider == "clave_movil":
        lines.extend(
            (
                f"profile_tax_id\t{'present' if result.profile_tax_id_present else 'missing'}",
                f"clave_identity\t{'present' if result.provider_identity_present else 'missing'}",
                f"identity_alignment\t{result.identity_alignment}",
            )
        )
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
        raise CliRefusedBoundaryError(f"auth diagnostic not found: {diagnostic_id}")
    reported_at = detail.phone_state_reported_at.isoformat() if detail.phone_state_reported_at is not None else ""
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
            f"phone_state\t{detail.phone_state}",
            f"phone_state_reported_at\t{reported_at}",
            f"html_captured\t{detail.html_captured}",
            f"screenshot_captured\t{detail.screenshot_captured}",
            f"html_excerpt\t{detail.html_excerpt or ''}",
        ),
    )


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

    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    pointer = read_profile_bucket(resolve_active_bucket_id() or "")
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
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    pointer = read_profile_bucket(resolve_active_bucket_id() or "")
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
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    pointer = read_profile_bucket(resolve_active_bucket_id() or "")
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

    workflow_state_repository().load()
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    pointer = read_profile_bucket(resolve_active_bucket_id() or "")
    svc = ApoderadoService()

    try:
        result = svc.check(bucket_id=pointer.bucket_id)
    except ApoderadoLiveCheckUnavailableError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

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
        raise typer.BadParameter("--since must be before or equal to --until")
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


def _parse_bucket_event_types(event_type: list[str] | None):  # type: ignore[no-untyped-def]
    """Parse the ``--event-type`` flag tuple, raising :class:`typer.BadParameter` on unknown values.

    Returns ``None`` when no filter was supplied so the catalogue
    walker reads the full event stream; otherwise returns a typed
    tuple of :class:`BucketEventType`.
    """
    if not event_type:
        return None
    from ....domain.buckets import BucketEventType

    try:
        return tuple(BucketEventType(value.strip()) for value in event_type)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _parse_bucket_history_instant(raw: str | None, *, flag: str):  # type: ignore[no-untyped-def]
    """Parse one ``--since`` / ``--until`` value into a :class:`datetime`, or ``None`` when absent."""
    if not raw:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise typer.BadParameter(
            f"{flag} must be an ISO-8601 timestamp (e.g. 2026-04-01T00:00:00+00:00); got {raw!r}",
        ) from exc


def _bucket_history_event_matches(
    event,
    *,
    since_dt,
    until_dt,
    object_id_token: str | None,
    actor_token: str | None,
) -> bool:  # type: ignore[no-untyped-def]
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


def _bucket_history_event_payload(event):  # type: ignore[no-untyped-def]
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
