"""User-facing configuration facade."""

from __future__ import annotations

import typing
from pathlib import Path

import click
import typer

from ....application.auth._catalogue import implemented_auth_provider_ids, known_auth_provider_ids
from ....application.config_reset import CONFIG_RESET_SCOPE_CLI_VALUES, parse_config_reset_scope
from ....application.diagnostics import (
    build_config_doctor_report,
    probe_browser_connectivity,
    quarantine_unreadable_secure_objects,
    render_browser_connectivity_text,
    render_config_doctor_text,
)
from ....application.operator_surface import build_help_document, render_help_text
from ....core.logging import default_log_file_path
from .._common import _emit
from .._errors import CliRefusedBoundaryError, write_stderr
from .._i18n import tr

app = typer.Typer(
    name="config",
    help=tr("cli.config.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
    add_help_option=False,
)
profile_app = typer.Typer(name="profile", help=tr("cli.config.profile.help"), no_args_is_help=True)
auth_app = typer.Typer(name="auth", help=tr("cli.config.auth.help"), no_args_is_help=True)
doctor_app = typer.Typer(
    name="doctor",
    help=tr("cli.config.doctor.help"),
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
    help_: bool = typer.Option(False, "--help", "-h", help="Show config workflow help.", is_eager=True),
) -> None:
    """Render config-level workflow help when requested."""

    if help_ or ctx.invoked_subcommand is None:
        document = build_help_document("config")
        _emit(ctx, document, render_help_text(document).splitlines())
        raise typer.Exit()


@doctor_app.callback()
def doctor(ctx: typer.Context) -> None:
    """Diagnose local configuration, registry, profile, auth, and log state."""

    if ctx.invoked_subcommand is not None:
        return
    report = build_config_doctor_report()
    _emit(ctx, report.model_dump(mode="json"), render_config_doctor_text(report).splitlines())


@doctor_app.command("logs", help=tr("cli.config.doctor.logs_help"))
def doctor_logs(
    ctx: typer.Context,
    lines: int = typer.Option(20, "--lines", min=0, help=tr("cli.config.doctor.logs_lines_help")),
) -> None:
    """Show the configured log file path and recent lines."""

    path = default_log_file_path()
    tail = _tail_lines(path, lines) if path.exists() and lines > 0 else ()
    _emit(
        ctx,
        {"path": str(path), "lines": tail},
        (f"path\t{path}", *tail),
    )


@doctor_app.command("quarantine", help=tr("cli.config.doctor.quarantine_help"))
def doctor_quarantine(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.doctor.quarantine_yes_help")),
) -> None:
    """Move secure-object rows that fail tag verification into quarantine."""

    if not yes:
        raise CliRefusedBoundaryError(tr("cli.config.doctor.quarantine_requires_yes"))
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


@doctor_app.command("connectivity", help=tr("cli.config.doctor.connectivity_help"))
def doctor_connectivity(
    ctx: typer.Context,
    target: typing.Annotated[
        str,
        typer.Option(
            "--target",
            click_type=click.Choice(("browser",)),
            help=tr("cli.config.doctor.connectivity_target_help"),
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


app.add_typer(doctor_app, name="doctor")


def _profile_state():
    from ....application.workflow._persistence import workflow_state_repository

    return workflow_state_repository()


@profile_app.command("list", help=tr("cli.config.list.help"))
def config_list(ctx: typer.Context) -> None:
    """List every profile key with its current value (or ``<unset>``)."""

    from ....domain.profile import PROFILE_KEYS

    state = _profile_state().load()
    record = state.active_profile_record()
    values: dict[str, str] = dict(record.values) if record is not None else {}
    payload = {
        "active_profile": state.active_profile,
        "keys": [
            {"key": entry.key, "requirement": entry.requirement.value, "value": values.get(entry.key, "")}
            for entry in PROFILE_KEYS
        ],
    }
    lines = [f"profile\t{state.active_profile or ''}"]
    for entry in PROFILE_KEYS:
        rendered_value = values.get(entry.key, "")
        lines.append(f"{entry.key}\t{entry.requirement.value}\t{rendered_value or '<unset>'}")
    _emit(ctx, payload, lines)


@profile_app.command("get", help=tr("cli.config.get.help"))
def config_get(ctx: typer.Context, key: str = typer.Argument(..., help=tr("cli.config.get.key_help"))) -> None:
    """Return one profile key's current value."""

    from ....domain.profile import get_profile_key

    try:
        get_profile_key(key)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.errors.unknown_key", name=key)) from exc
    state = _profile_state().load()
    record = state.active_profile_record()
    value = record.values.get(key, "") if record is not None else ""
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

    from ....application.profile._actions import set_profile_values
    from ....application.wizard._errors import WizardValidationError
    from ....application.wizard._widgets import validate_widget_answer
    from ....domain.profile import get_profile_key

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
    state = repository.load()
    profile_name = state.active_profile
    if profile_name is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    updated = repository.update(lambda current: set_profile_values(current, profile_name, {canonical_key: value}))
    record = updated.active_profile_record()
    stored_value = record.values.get(canonical_key, "") if record is not None else ""
    payload = {"key": canonical_key, "value": stored_value}
    _emit(ctx, payload, (f"{canonical_key}\t{stored_value}",))


@profile_app.command("unset", help=tr("cli.config.unset.help"))
def config_unset(ctx: typer.Context, key: str = typer.Argument(..., help=tr("cli.config.unset.key_help"))) -> None:
    """Clear one profile key value through the shared application backend."""

    from ....application.profile._actions import clear_profile_values
    from ....domain.profile import get_profile_key

    try:
        get_profile_key(key)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.errors.unknown_key", name=key)) from exc
    repository = _profile_state()
    state = repository.load()
    profile_name = state.active_profile
    if profile_name is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    repository.update(lambda current: clear_profile_values(current, profile_name, (key,)))
    _emit(ctx, {"key": key, "value": ""}, (f"{key}\t<unset>",))


def _register_wizard_commands(target: typer.Typer) -> None:
    """Register every wizard flow as a sub-command of ``target``."""

    from ....application.wizard._catalogue import WIZARD_FLOWS
    from ....application.wizard._commands import build_wizard_command
    from ....application.wizard._errors import WizardMissingFlagError
    from ....application.wizard._prompter import WizardUnsupportedConsoleError

    for flow in WIZARD_FLOWS:
        command_callable = build_wizard_command(flow)
        original = typing.cast(typing.Any, command_callable)

        def _wrapped(
            *args: object,
            _callable: typing.Callable[..., None] = command_callable,
            **kwargs: object,
        ) -> None:
            try:
                _callable(*args, **kwargs)
            except WizardMissingFlagError as exc:
                translated = exc.translated_message or tr("cli.config.setup.errors.missing_required_flags")
                raise CliRefusedBoundaryError(translated) from exc
            except WizardUnsupportedConsoleError as exc:
                write_stderr(f"{exc}\n")
                raise typer.Exit(2) from exc
            if kwargs.get("quiet"):
                profile_name = kwargs.get("profile_name", "default")
                typer.echo(tr("cli.config.setup.success.saved", profile_name=profile_name))
                typer.echo(tr("cli.config.setup.success.next_step"))

        wrapped = typing.cast(typing.Any, _wrapped)
        wrapped.__signature__ = original.__signature__
        wrapped.__annotations__ = original.__annotations__
        wrapped.__name__ = original.__name__
        wrapped.__doc__ = original.__doc__
        wrapped.__wizard_flow__ = getattr(original, "__wizard_flow__", None)
        command_name = "init" if flow.id == "setup" else flow.id
        target.command(name=command_name, help=tr(f"cli.config.{flow.id}.help"))(_wrapped)


_register_wizard_commands(app)


@profile_app.command("status", help=tr("cli.config.status.help"))
def config_status(ctx: typer.Context) -> None:
    """Show the readiness of the current configuration profile."""

    from pydantic import ValidationError

    from ....application.wizard._catalogue import SETUP_FLOW
    from ....application.wizard._persistence import project_answers
    from ....application.workflow._persistence import workflow_state_repository

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    values: dict[str, str] = dict(record.values) if record is not None else {}
    if not values.get("tax.id") or not values.get("activity"):
        payload = {
            "active_profile": state.active_profile,
            "tax_id_present": bool(values.get("tax.id")),
            "activity_present": bool(values.get("activity")),
            "configured": False,
        }
        _emit(ctx, payload, (tr("cli.config.status.empty_profile"),))
        return
    try:
        projection = project_answers(SETUP_FLOW, values)
    except ValidationError:
        payload = {
            "active_profile": state.active_profile,
            "tax_id_present": bool(values.get("tax.id")),
            "activity_present": bool(values.get("activity")),
            "configured": False,
        }
        _emit(ctx, payload, (tr("cli.config.status.empty_profile"),))
        return
    payload = {
        "active_profile": state.active_profile,
        "tax_id_present": bool(values.get("tax.id")),
        "activity_present": bool(values.get("activity")),
        "iva_regime": values.get("iva.regime", ""),
        "tax_residence_ccaa": values.get("tax.residence.ccaa", ""),
        "next_action": tr("cli.config.status.next_step"),
    }
    _emit(
        ctx,
        payload,
        (
            f"profile\t{state.active_profile or ''}",
            f"tax.id\t{values.get('tax.id', '<unset>')}",
            f"activity\t{values.get('activity', '<unset>')}",
            f"iva.regime\t{values.get('iva.regime', '<unset>')}",
            f"tax.residence.ccaa\t{values.get('tax.residence.ccaa', '<unset>')}",
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
        click_type=click.Choice(implemented_auth_provider_ids()),
        help=tr("cli.config.auth.provider_help"),
    ),
    file: Path | None = typer.Option(None, "--file", help=tr("cli.config.auth.file_help")),
) -> None:
    """Configure the active authentication provider."""

    from ....application.auth import AuthProviderReservedError, configure_operator_auth

    try:
        result = configure_operator_auth(provider, certificate_path=file)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.unknown_provider", provider=provider)) from exc
    except AuthProviderReservedError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.reserved_provider", provider=provider)) from exc
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
    provider: str | None = typer.Option(None, "--provider", click_type=click.Choice(implemented_auth_provider_ids())),
) -> None:
    """Render auth readiness through the application-owned auth state."""

    from ....application.auth import test_operator_auth

    try:
        result = test_operator_auth(provider)
    except KeyError as exc:
        raise CliRefusedBoundaryError(tr("cli.config.auth.unknown_provider", provider=provider or "")) from exc
    payload = result.model_dump(mode="json")
    _emit(ctx, payload, tuple(f"{key}\t{value}" for key, value in payload.items()))


@auth_app.command("clear", help=tr("cli.config.auth.clear_help"))
def auth_clear(
    ctx: typer.Context,
    provider: str | None = typer.Option(None, "--provider", click_type=click.Choice(implemented_auth_provider_ids())),
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
) -> None:
    """Browse the append-only bucket-event history."""

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

    events = catalogue.for_bucket(bucket_id, event_types=selected)
    payload = {
        "operation": "config.bucket.history",
        "bucket_id": bucket_id,
        "event_types": [t.value for t in selected] if selected else None,
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


app.add_typer(profile_app, name="profile")
app.add_typer(auth_app, name="auth")
app.add_typer(bucket_app, name="bucket")

__all__ = ["app"]
