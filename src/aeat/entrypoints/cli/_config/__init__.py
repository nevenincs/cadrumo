"""User-facing configuration facade."""

from __future__ import annotations

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
from ....core.logging import default_log_file_path
from .._common import _emit
from .._errors import CliRefusedBoundaryError
from ....core.i18n import tr

_wizard_init_command = build_wizard_command(SETUP_FLOW)

app = typer.Typer(
    name="config",
    help=tr("cli.config.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
    add_help_option=False,
)
profile_app = typer.Typer(name="profile", help=tr("cli.config.profile.help"), no_args_is_help=True)
auth_app = typer.Typer(name="auth", help=tr("cli.config.auth.help"), no_args_is_help=True)
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
    """Return the last ``count`` lines from ``path`` without trailing newlines."""

    if count <= 0:
        return ()
    return tuple(path.read_text(encoding="utf-8", errors="replace").splitlines()[-count:])


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
    """List every profile key with its current value (or ``<unset>``)."""

    from ....application.user_profile._projections import record_to_path_values
    from ....domain.profile import PROFILE_KEYS

    state = _profile_state().load()
    record = state.active_profile_record()
    values = record_to_path_values(record)
    payload = {
        "active_profile": resolve_active_bucket_id(),
        "keys": [
            {"key": entry.key, "requirement": entry.requirement.value, "value": values.get(entry.key, "")}
            for entry in PROFILE_KEYS
        ],
    }
    lines = [f"profile\t{resolve_active_bucket_id() or ''}"]
    for entry in PROFILE_KEYS:
        rendered_value = values.get(entry.key, "")
        lines.append(f"{entry.key}\t{entry.requirement.value}\t{rendered_value or '<unset>'}")
    _emit(ctx, payload, lines)


@profile_app.command("switch", help=tr("cli.config.profile.switch_help"))
def config_profile_switch(
    ctx: typer.Context,
    name: str = typer.Argument(..., help=tr("cli.config.profile.switch_name_help")),
) -> None:
    """Select an existing profile as the active profile."""

    from ....application.user_profile._orchestration import select_profile
    from ....domain.user_profile import ProfileNotFoundError

    repository = _profile_state()
    try:
        updated = repository.update(lambda current: select_profile(current, profile_id=name))
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name)) from exc
    active = resolve_active_bucket_id()
    _emit_profile_activated_event(profile_id=name, active_profile=active)
    _emit(
        ctx,
        {"active_profile": active},
        (f"active_profile\t{active or ''}",),
    )


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

    state = _profile_state().load()
    target = name or resolve_active_bucket_id()
    if target is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    pointer = state.profiles.get(target)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=target))
    service = build_lifecycle_service(bucket_id=pointer.bucket_id)
    try:
        record = service.read(target)
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=target)) from exc
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
    state = repository.load()
    pointer = state.profiles.get(name)
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

    from ....application.user_profile import DuplicateProfileCommand
    from ....application.user_profile._orchestration import build_lifecycle_service
    from ....application.workflow._models import ProfileBucketPointer
    from ....application.workflow._utils import utc_now
    from ....domain.user_profile import ProfileAlreadyExistsError, ProfileNotFoundError

    repository = _profile_state()
    state = repository.load()
    pointer = state.profiles.get(source)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=source))
    if target in state.profiles:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target))
    service = build_lifecycle_service(bucket_id=pointer.bucket_id)
    try:
        result = service.duplicate(
            DuplicateProfileCommand(
                source_profile_id=source,
                target_profile_id=target,
                target_display_name=display_name or target,
            )
        )
    except ProfileAlreadyExistsError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target)) from exc
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=source)) from exc

    def _register_target(current):
        profiles = dict(current.profiles)
        profiles[target] = ProfileBucketPointer(bucket_id=pointer.bucket_id)
        return current.model_copy(update={"profiles": profiles, "updated_at": utc_now()})

    repository.update(_register_target)
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


_config_init_callback = app.command(
    "init",
    help=tr("cli.config.init.help", default="Initialize a new active profile and config bucket."),
)(_wizard_init_command)


# Re-runs the wizard against the same backend so an operator can update
# an existing profile interactively. The wizard's persist_answers path
# detects an existing pointer and calls `set_active_fields` rather than
# `register_active_profile`; the same closure powers both "create" and
# "edit" semantics with the chosen `--profile NAME` deciding which side
# of the branch runs.
_config_profile_edit_callback = profile_app.command(
    "edit",
    help=tr(
        "cli.config.profile.edit_help",
        default="Re-run the wizard against an existing profile; updates values in place.",
    ),
)(_wizard_init_command)


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
    from ....application.workflow._models import ProfileBucketPointer
    from ....application.workflow._utils import utc_now
    from ....domain.user_profile import ProfileAlreadyExistsError, ProfileNotFoundError

    repository = _profile_state()
    state = repository.load()
    pointer = state.profiles.get(source)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=source))
    if target != source and target in state.profiles:
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

    def _swap_pointer(current):
        profiles = dict(current.profiles)
        profiles.pop(source, None)
        profiles[target] = ProfileBucketPointer(bucket_id=pointer.bucket_id)
        return current.model_copy(update={"profiles": profiles, "updated_at": utc_now()})

    repository.update(_swap_pointer)
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

    state = _profile_state().load()
    target = name or resolve_active_bucket_id()
    if target is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    pointer = state.profiles.get(target)
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
    from ....application.workflow._models import ProfileBucketPointer
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
    state = repository.load()
    if target_id in state.profiles:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target_id))
    active_bucket = resolve_active_bucket_id()
    if active_bucket is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    bucket_pointer = state.profiles.get(active_bucket)
    bucket_id = bucket_pointer.bucket_id if bucket_pointer is not None else active_bucket
    service = build_lifecycle_service(bucket_id=bucket_id)
    try:
        result = service.import_archive(bundle)
    except ProfileAlreadyExistsError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.already_exists", name=target_id)) from exc

    def _register(current):
        profiles = dict(current.profiles)
        profiles[target_id] = ProfileBucketPointer(bucket_id=bucket_id)
        return current.model_copy(update={"profiles": profiles, "updated_at": utc_now()})

    repository.update(_register)
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

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    values = record_to_path_values(record)
    if not values.get("identity.tax_id") or not values.get("activities.description"):
        payload = {
            "active_profile": resolve_active_bucket_id(),
            "tax_id_present": bool(values.get("identity.tax_id")),
            "activity_present": bool(values.get("activities.description")),
            "configured": False,
        }
        _emit(ctx, payload, (tr("cli.config.status.empty_profile"),))
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
    from ....application.auth._operator import AuthConfigureNoActiveBucketError

    try:
        result = configure_operator_auth(provider, certificate_path=file)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.unknown_provider", provider=provider)) from exc
    except AuthProviderReservedError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.reserved_provider", provider=provider)) from exc
    except AuthConfigureNoActiveBucketError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.no_active_bucket")) from exc
    _emit(ctx, result.model_dump(mode="json"), (f"provider\t{result.provider}", f"file\t{result.file}"))


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
    from ....application.workflow._persistence import workflow_state_repository

    state = workflow_state_repository().load()
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    pointer = state.profiles[resolve_active_bucket_id() or ""]
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

    state = workflow_state_repository().load()
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    pointer = state.profiles[resolve_active_bucket_id() or ""]
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

    state = workflow_state_repository().load()
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    pointer = state.profiles[resolve_active_bucket_id() or ""]
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

    state = workflow_state_repository().load()
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.no_active_profile"))

    pointer = state.profiles[resolve_active_bucket_id() or ""]
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
app.add_typer(auth_app, name="auth")
app.add_typer(bucket_app, name="bucket")

from ._google import google_app

app.add_typer(google_app, name="google")

__all__ = ["app"]
