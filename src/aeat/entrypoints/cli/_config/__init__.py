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
from .._i18n import tr
from ._payloads import ProfileFactSetResult, ProfileFactUnsetResult

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


@repair_app.command(
    "list",
    help=tr(
        "cli.config.repair.list_help",
        default="List secure-object keys stored under one namespace.",
    ),
)
def repair_list(
    ctx: typer.Context,
    namespace: str = typer.Argument(
        ..., help=tr("cli.config.repair.list_namespace_help", default="Namespace to inventory.")
    ),
    include_all: bool = typer.Option(
        False, "--all", help=tr("cli.config.repair.list_all_help", default="Return every key, including unreadable.")
    ),
    only_unreadable: bool = typer.Option(
        False,
        "--unreadable",
        help=tr("cli.config.repair.list_unreadable_help", default="Restrict to undecryptable rows."),
    ),
) -> None:
    """Wrap build_repair_list_report and render through _emit."""

    from ....application.repair_integrity import build_repair_list_report

    if include_all and only_unreadable:
        raise CliRefusedBoundaryError(
            tr(
                "cli.config.repair.list_conflicting_flags",
                default="--all and --unreadable cannot be combined; pass one or neither.",
            )
        )
    report = build_repair_list_report(
        namespace=namespace,
        include_all=include_all,
        only_unreadable=only_unreadable,
    )
    payload = report.model_dump(mode="json")
    lines = [f"namespace\t{namespace}", f"count\t{len(report.rows)}"]
    for row in report.rows:
        lines.append(f"{row.namespace}\t{row.object_key_digest}")
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


@profile_app.command("get", help=tr("cli.config.get.help"))
def config_get(ctx: typer.Context, key: str = typer.Argument(..., help=tr("cli.config.get.key_help"))) -> None:
    """Return one profile key's current value."""

    from ....application.user_profile._orchestration import fact_value
    from ....domain.profile import get_profile_key

    try:
        get_profile_key(key)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.errors.unknown_key", name=key)) from exc
    state = _profile_state().load()
    record = state.active_profile_record()
    value = fact_value(record, key) or ""
    payload = {"key": key, "value": value}
    _emit(ctx, payload, (f"{key}\t{value or '<unset>'}",))


def _question_for_profile_key(profile_key: str):
    """Return the descriptor's question for ``profile_key``, or ``None``."""

    from ....application.wizard._catalogue import WIZARD_FLOWS

    for flow in WIZARD_FLOWS:
        for section in flow.sections:
            for question in section.questions:
                if question.profile_key == profile_key:
                    return question
    return None


@profile_app.command("set", help=tr("cli.config.set.help"))
def config_set(
    ctx: typer.Context,
    key: str = typer.Argument(..., help=tr("cli.config.set.key_help")),
    value: str = typer.Argument(..., help=tr("cli.config.set.value_help")),
) -> None:
    """Write one profile key value, validated through the wizard descriptor."""

    from ....application.user_profile._orchestration import fact_value, set_active_field
    from ....application.wizard._errors import WizardValidationError
    from ....application.wizard._widgets import validate_widget_answer
    from ....domain.profile import get_profile_key
    from ....domain.user_profile import UserProfileFact

    try:
        registered = get_profile_key(key)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.errors.unknown_key", name=key)) from exc
    canonical_key = registered.key
    question = _question_for_profile_key(canonical_key)
    if question is not None:
        try:
            value = validate_widget_answer(question, value)
        except WizardValidationError as exc:
            choices = ", ".join(choice.value for choice in question.choices)
            translated = exc.translated_message or tr("cli.config.errors.invalid_value", name=key, value=value)
            message = f"{translated} ({choices})" if choices else translated
            raise CliRefusedBoundaryError(message) from exc

    repository = _profile_state()
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    fact = UserProfileFact(path=canonical_key, value=value)
    updated = repository.update(lambda current: set_active_field(current, fact))
    record = updated.active_profile_record()
    stored_value = fact_value(record, canonical_key) or ""
    payload = ProfileFactSetResult(key=canonical_key, value=stored_value)
    _emit(ctx, payload.model_dump(mode="json"), (f"{canonical_key}\t{stored_value}",))


@profile_app.command("unset", help=tr("cli.config.unset.help"))
def config_unset(ctx: typer.Context, key: str = typer.Argument(..., help=tr("cli.config.unset.key_help"))) -> None:
    """Clear one profile key value through the shared application backend."""

    from ....application.user_profile._orchestration import set_active_field
    from ....domain.profile import get_profile_key
    from ....domain.user_profile import UserProfileFact

    try:
        get_profile_key(key)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.errors.unknown_key", name=key)) from exc
    repository = _profile_state()
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    fact = UserProfileFact(path=key, value=None)
    repository.update(lambda current: set_active_field(current, fact))
    payload = ProfileFactUnsetResult(key=key)
    _emit(ctx, payload.model_dump(mode="json"), (f"{key}\t<unset>",))


@profile_app.command(
    "validate", help=tr("cli.config.profile.validate_help", default="Validate the active profile against the schema.")
)
def config_profile_validate(ctx: typer.Context) -> None:
    """Run the canonical ProfileValidationService over the active profile."""

    from ....application.user_profile._orchestration import build_lifecycle_service
    from ....domain.user_profile import ProfileNotFoundError

    state = _profile_state().load()
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    pointer = state.profiles.get(resolve_active_bucket_id() or "")
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    service = build_lifecycle_service(bucket_id=pointer.bucket_id)
    try:
        record = service.read(resolve_active_bucket_id() or "")
    except ProfileNotFoundError as exc:
        active = resolve_active_bucket_id() or ""
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=active)) from exc
    report = service._validator.validate_record(record)
    blocking = [issue for issue in report.issues if issue.severity.value == "error"]
    payload = report.model_dump(mode="json")
    payload["valid"] = not blocking
    lines = [
        f"profile_id\t{record.profile_id}",
        f"schema_version\t{report.schema_version}",
        f"valid\t{not blocking}",
        f"issues\t{len(report.issues)}",
    ]
    for issue in report.issues:
        lines.append(f"{issue.severity.value}\t{issue.code}\t{issue.path or '-'}\t{issue.message}")
    _emit(ctx, payload, lines)


@profile_app.command(
    "preflight",
    help=tr(
        "cli.config.profile.preflight_help",
        default="Report whether the active profile is ready for one modelo / year / period.",
    ),
)
def config_profile_preflight(
    ctx: typer.Context,
    modelo: str = typer.Option(
        ..., "--modelo", help=tr("cli.config.profile.preflight_modelo_help", default="Modelo code (e.g. 303).")
    ),
    revision_id: str = typer.Option(
        ..., "--revision-id", help=tr("cli.config.profile.preflight_revision_help", default="Registry revision id.")
    ),
    filing_year: int = typer.Option(
        ..., "--year", help=tr("cli.config.profile.preflight_year_help", default="Filing year.")
    ),
    period: str = typer.Option(
        ..., "--period", help=tr("cli.config.profile.preflight_period_help", default="Period token (e.g. Q1, annual).")
    ),
) -> None:
    """Wrap ProfilePreflightService over the active profile for one modelo target."""

    from ....application.user_profile._orchestration import _shared_schema, build_lifecycle_service
    from ....application.user_profile._preflight import ProfilePreflightService
    from ....domain.user_profile import ProfileNotFoundError

    state = _profile_state().load()
    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    pointer = state.profiles.get(resolve_active_bucket_id() or "")
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    service = build_lifecycle_service(bucket_id=pointer.bucket_id)
    try:
        record = service.read(resolve_active_bucket_id() or "")
    except ProfileNotFoundError as exc:
        active = resolve_active_bucket_id() or ""
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=active)) from exc
    preflight = ProfilePreflightService(schema=_shared_schema())
    report = preflight.report(
        record=record,
        modelo=modelo,
        revision_id=revision_id,
        filing_year=filing_year,
        period=period,
    )
    payload = report.model_dump(mode="json")
    lines = [
        f"profile_id\t{record.profile_id}",
        f"modelo\t{modelo}",
        f"revision_id\t{revision_id}",
        f"filing_year\t{filing_year}",
        f"period\t{period}",
        f"ready\t{report.ready}",
        f"missing\t{len(report.missing)}",
    ]
    for requirement in report.missing:
        lines.append(f"{requirement.section_key}.{requirement.field_key}\t{requirement.selector}")
    _emit(ctx, payload, lines)


@profile_app.command("use", help=tr("cli.config.profile.use_help"))
def config_profile_use(
    ctx: typer.Context,
    name: str = typer.Argument(..., help=tr("cli.config.profile.use_name_help")),
) -> None:
    """Select an existing profile as the active profile."""

    from ....application.user_profile._orchestration import select_profile
    from ....domain.user_profile import ProfileNotFoundError

    repository = _profile_state()
    try:
        updated = repository.update(lambda current: select_profile(current, profile_id=name))
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=name)) from exc
    _emit_profile_activated_event(profile_id=name, active_profile=updated.active_profile)
    _emit(
        ctx,
        {"active_profile": updated.active_profile},
        (f"active_profile\t{updated.active_profile or ''}",),
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


@profile_app.command("view", help=tr("cli.config.profile.view_help"))
def config_profile_show(
    ctx: typer.Context,
    name: str | None = typer.Argument(None, help=tr("cli.config.profile.show_name_help")),
) -> None:
    """View one profile's facts (defaults to the active profile)."""

    from ....application.user_profile._orchestration import build_lifecycle_service
    from ....application.user_profile._projections import record_to_path_values
    from ....domain.user_profile import ProfileNotFoundError

    state = _profile_state().load()
    target = name or state.active_profile
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
    values = record_to_path_values(record)
    payload = {
        "profile_id": record.profile_id,
        "display_name": record.display_name,
        "status": record.status.value,
        "facts": [{"path": path, "value": value} for path, value in sorted(values.items())],
    }
    lines = [
        f"profile_id\t{record.profile_id}",
        f"display_name\t{record.display_name}",
        f"status\t{record.status.value}",
    ]
    lines.extend(f"{path}\t{value}" for path, value in sorted(values.items()))
    _emit(ctx, payload, lines)


@profile_app.command("remove", help=tr("cli.config.profile.remove_help"))
def config_profile_remove(
    ctx: typer.Context,
    name: str = typer.Argument(..., help=tr("cli.config.profile.remove_name_help")),
    confirmed: bool = typer.Option(False, "--yes", help=tr("cli.config.profile.remove_yes_help")),
) -> None:
    """Tombstone a profile. Immutable filing snapshots are retained."""

    from ....application.user_profile import RemoveProfileCommand
    from ....application.user_profile._orchestration import build_lifecycle_service
    from ....domain.user_profile import ProfileNotFoundError

    if not confirmed:
        raise CliRefusedBoundaryError(tr("cli.config.profile.remove_requires_yes", name=name))
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
        from ....application.workflow._utils import utc_now

        repository.update(lambda current: current.model_copy(update={"active_profile": None, "updated_at": utc_now()}))
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

    from datetime import datetime as _datetime

    from ....domain.buckets import BucketEventHistoryRepository, BucketEventType

    repository = BucketEventHistoryRepository()
    catalogue = repository.load()
    selected: tuple[BucketEventType, ...] | None
    if event_type:
        try:
            selected = tuple(BucketEventType(value.strip()) for value in event_type)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        selected = None

    def _parse_filter_instant(raw: str, *, flag: str) -> _datetime:
        try:
            return _datetime.fromisoformat(raw.strip())
        except ValueError as exc:
            raise typer.BadParameter(
                f"{flag} must be an ISO-8601 timestamp (e.g. 2026-04-01T00:00:00+00:00); got {raw!r}",
            ) from exc

    since_dt = _parse_filter_instant(since, flag="--since") if since else None
    until_dt = _parse_filter_instant(until, flag="--until") if until else None
    if since_dt is not None and until_dt is not None and since_dt > until_dt:
        raise typer.BadParameter("--since must be before or equal to --until")

    object_id_token = object_id.strip() if object_id else None
    actor_token = actor.strip() if actor else None

    events = tuple(
        e
        for e in catalogue.for_bucket(bucket_id, event_types=selected)
        if (since_dt is None or e.occurred_at >= since_dt)
        and (until_dt is None or e.occurred_at <= until_dt)
        and (object_id_token is None or e.object_id == object_id_token)
        and (actor_token is None or e.actor == actor_token)
    )
    payload = {
        "operation": "config.bucket.history",
        "bucket_id": bucket_id,
        "event_types": [t.value for t in selected] if selected else None,
        "since": since_dt.isoformat() if since_dt else None,
        "until": until_dt.isoformat() if until_dt else None,
        "object_id": object_id_token,
        "actor": actor_token,
        "events": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type.value,
                "occurred_at": e.occurred_at.isoformat(),
                "actor": e.actor,
                "object_type": e.object_type.value,
                "object_id": e.object_id,
                "payload": dict(e.payload),
            }
            for e in events
        ],
    }
    lines = ["operation\tconfig.bucket.history", f"bucket_id\t{bucket_id}", f"event_count\t{len(events)}"] + [
        f"{e.occurred_at.isoformat()}\t{e.event_type.value}\t{e.object_type.value}\t{e.object_id}\t{e.actor}"
        for e in events
    ]
    _emit(ctx, payload, lines)


from ._profile_census import register as _register_profile_census

_register_profile_census(profile_app)

app.add_typer(profile_app, name="profile")
auth_app.add_typer(apoderado_app, name="apoderado")
app.add_typer(auth_app, name="auth")
app.add_typer(bucket_app, name="bucket")

from ._google import google_app

app.add_typer(google_app, name="google")

__all__ = ["app"]
