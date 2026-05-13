"""User-facing configuration facade."""

from __future__ import annotations

import typing
from pathlib import Path

import typer

from ...application.diagnostics import (
    build_config_doctor_report,
    quarantine_unreadable_secure_objects,
    render_config_doctor_text,
)
from ...core.logging import default_log_file_path
from ._common import _FORMAT_JSON, _format_of
from ._i18n import tr

app = typer.Typer(name="config", help=tr("cli.config.app_help"), no_args_is_help=True)
profile_app = typer.Typer(name="profile", help=tr("cli.config.profile.help"), no_args_is_help=True)
auth_app = typer.Typer(name="auth", help=tr("cli.config.auth.help"), no_args_is_help=True)
doctor_app = typer.Typer(
    name="doctor",
    help=tr("cli.config.doctor.help"),
    no_args_is_help=False,
    invoke_without_command=True,
)


@doctor_app.callback()
def doctor(ctx: typer.Context) -> None:
    """Diagnose local configuration, registry, profile, auth, and log state."""

    if ctx.invoked_subcommand is not None:
        return
    report = build_config_doctor_report()
    if _format_of(ctx) == _FORMAT_JSON:
        typer.echo(report.model_dump_json())
        return
    typer.echo(render_config_doctor_text(report), nl=False)


@doctor_app.command("logs", help=tr("cli.config.doctor.logs_help"))
def doctor_logs(
    lines: int = typer.Option(20, "--lines", min=0, help=tr("cli.config.doctor.logs_lines_help")),
) -> None:
    """Show the configured log file path and recent lines."""

    path = default_log_file_path()
    typer.echo(f"path\t{path}")
    if not path.exists() or lines == 0:
        return
    for line in _tail_lines(path, lines):
        typer.echo(line)


@doctor_app.command("quarantine", help=tr("cli.config.doctor.quarantine_help"))
def doctor_quarantine(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.doctor.quarantine_yes_help")),
) -> None:
    """Move secure-object rows that fail tag verification into quarantine."""

    if not yes:
        typer.echo(tr("cli.config.doctor.quarantine_requires_yes"))
        raise typer.Exit(code=2)
    report = quarantine_unreadable_secure_objects()
    if _format_of(ctx) == _FORMAT_JSON:
        typer.echo(report.model_dump_json())
        return
    typer.echo(f"quarantined\t{report.unreadable_total}")
    typer.echo(f"retained\t{report.readable_total}")
    for item in report.namespaces:
        if item.unreadable > 0:
            typer.echo(f"{item.namespace}\t{item.unreadable}")


def _tail_lines(path: Path, count: int) -> tuple[str, ...]:
    """Return the last ``count`` lines from ``path`` without trailing newlines."""

    if count <= 0:
        return ()
    return tuple(path.read_text(encoding="utf-8", errors="replace").splitlines()[-count:])


def _register_doctor_connectivity(target: typer.Typer) -> None:
    """Mount the browser/site-health diagnostic under config doctor."""

    from .browser.health import health_cmd

    target.command("connectivity", help=tr("cli.config.doctor.connectivity_help"))(health_cmd)


_register_doctor_connectivity(doctor_app)
app.add_typer(doctor_app, name="doctor")


def _profile_state():
    from ...application.workflow._persistence import workflow_state_repository

    return workflow_state_repository()


@profile_app.command("list", help=tr("cli.config.list.help"))
def config_list(ctx: typer.Context) -> None:
    """List every profile key with its current value (or ``<unset>``)."""

    from ...domain.profile import PROFILE_KEYS

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
    if _format_of(ctx) == _FORMAT_JSON:
        import json as _json

        typer.echo(_json.dumps(payload, ensure_ascii=False))
        return
    for line in lines:
        typer.echo(line)


@profile_app.command("get", help=tr("cli.config.get.help"))
def config_get(ctx: typer.Context, key: str = typer.Argument(..., help=tr("cli.config.get.key_help"))) -> None:
    """Return one profile key's current value."""

    from ...domain.profile import get_profile_key

    try:
        get_profile_key(key)
    except KeyError as exc:
        raise typer.BadParameter(tr("cli.config.errors.unknown_key", name=key)) from exc
    state = _profile_state().load()
    record = state.active_profile_record()
    value = record.values.get(key, "") if record is not None else ""
    payload = {"key": key, "value": value}
    if _format_of(ctx) == _FORMAT_JSON:
        import json as _json

        typer.echo(_json.dumps(payload, ensure_ascii=False))
        return
    typer.echo(f"{key}\t{value or '<unset>'}")


def _question_for_profile_key(profile_key: str):
    """Return the descriptor's question for ``profile_key``, or ``None``."""

    from ...application.wizard._catalogue import WIZARD_FLOWS

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

    from ...application.profile._actions import set_profile_values
    from ...application.wizard._errors import WizardValidationError
    from ...application.wizard._widgets import validate_widget_answer
    from ...domain.profile import get_profile_key

    try:
        registered = get_profile_key(key)
    except KeyError as exc:
        raise typer.BadParameter(tr("cli.config.errors.unknown_key", name=key)) from exc
    canonical_key = registered.key
    question = _question_for_profile_key(canonical_key)
    if question is not None:
        try:
            value = validate_widget_answer(question, value)
        except WizardValidationError as exc:
            choices = ", ".join(choice.value for choice in question.choices)
            translated = exc.translated_message or tr("cli.config.errors.invalid_value", name=key, value=value)
            message = f"{translated} ({choices})" if choices else translated
            raise typer.BadParameter(message) from exc

    repository = _profile_state()
    state = repository.load()
    profile_name = state.active_profile
    if profile_name is None:
        raise typer.BadParameter(tr("cli.config.errors.no_active_profile"))
    updated = repository.update(lambda current: set_profile_values(current, profile_name, {canonical_key: value}))
    record = updated.active_profile_record()
    stored_value = record.values.get(canonical_key, "") if record is not None else ""
    payload = {"key": canonical_key, "value": stored_value}
    if _format_of(ctx) == _FORMAT_JSON:
        import json as _json

        typer.echo(_json.dumps(payload, ensure_ascii=False))
        return
    typer.echo(f"{canonical_key}\t{stored_value}")


@profile_app.command("unset", help=tr("cli.config.unset.help"))
def config_unset(ctx: typer.Context, key: str = typer.Argument(..., help=tr("cli.config.unset.key_help"))) -> None:
    """Clear one profile key value through the shared application backend."""

    del ctx
    from ...application.profile._actions import clear_profile_values
    from ...domain.profile import get_profile_key

    try:
        get_profile_key(key)
    except KeyError as exc:
        raise typer.BadParameter(tr("cli.config.errors.unknown_key", name=key)) from exc
    repository = _profile_state()
    state = repository.load()
    profile_name = state.active_profile
    if profile_name is None:
        raise typer.BadParameter(tr("cli.config.errors.no_active_profile"))
    repository.update(lambda current: clear_profile_values(current, profile_name, (key,)))
    typer.echo(f"{key}\t<unset>")


def _register_wizard_commands(target: typer.Typer) -> None:
    """Register every wizard flow as a sub-command of ``target``."""

    from ...application.wizard._catalogue import WIZARD_FLOWS
    from ...application.wizard._commands import build_wizard_command
    from ...application.wizard._errors import WizardMissingFlagError
    from ...application.wizard._prompter import WizardUnsupportedConsoleError

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
                raise typer.BadParameter(translated) from exc
            except WizardUnsupportedConsoleError as exc:
                translated = exc.translated_message or tr("wizard.errors.unsupported_console")
                typer.echo(translated, err=True)
                raise typer.Exit(code=78) from exc

        wrapped = typing.cast(typing.Any, _wrapped)
        wrapped.__signature__ = original.__signature__
        wrapped.__annotations__ = original.__annotations__
        wrapped.__name__ = original.__name__
        wrapped.__doc__ = original.__doc__
        command_name = "init" if flow.id == "setup" else flow.id
        target.command(name=command_name, help=tr(f"cli.config.{flow.id}.help"))(_wrapped)


_register_wizard_commands(app)


@profile_app.command("status", help=tr("cli.config.status.help"))
def config_status(ctx: typer.Context) -> None:
    """Show the readiness of the current configuration profile."""

    from ...application.wizard._catalogue import SETUP_FLOW
    from ...application.wizard._persistence import project_answers
    from ...application.workflow._persistence import workflow_state_repository

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    values: dict[str, str] = dict(record.values) if record is not None else {}
    projection = project_answers(SETUP_FLOW, values)
    payload = {
        "active_profile": state.active_profile,
        "tax_id_present": bool(values.get("tax.id")),
        "activity_present": bool(values.get("activity")),
        "iva_regime": values.get("iva.regime", ""),
        "tax_residence_ccaa": values.get("tax.residence.ccaa", ""),
    }
    if _format_of(ctx) == _FORMAT_JSON:
        import json as _json

        typer.echo(_json.dumps(payload, ensure_ascii=False))
        return
    typer.echo(f"profile\t{state.active_profile or ''}")
    typer.echo(f"tax.id\t{values.get('tax.id', '<unset>')}")
    typer.echo(f"activity\t{values.get('activity', '<unset>')}")
    typer.echo(f"iva.regime\t{values.get('iva.regime', '<unset>')}")
    typer.echo(f"tax.residence.ccaa\t{values.get('tax.residence.ccaa', '<unset>')}")
    del projection


@app.command("reset", help=tr("cli.config.reset.help"))
def config_reset(
    scope: str = typer.Option("all", "--scope", help=tr("cli.config.reset.scope_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.reset.yes_help")),
) -> None:
    """Reset operator-entered configuration scopes."""

    from ...application.config_reset import ConfigResetScope, reset_config

    if not yes:
        raise typer.BadParameter(tr("cli.config.reset.requires_yes"))
    try:
        scope_enum = ConfigResetScope(scope.strip().upper())
    except ValueError as exc:
        valid = ", ".join(member.value.lower() for member in ConfigResetScope)
        raise typer.BadParameter(tr("cli.config.reset.invalid_scope", scope=scope, valid=valid)) from exc
    report = reset_config(scope_enum, confirmed=True)
    typer.echo(f"scope\t{report.scope.value}")
    typer.echo(f"removed_profiles\t{len(report.removed_profile_names)}")
    typer.echo(f"removed_auth\t{report.removed_auth_session}")


@auth_app.command("providers", help=tr("cli.config.auth.providers_help"))
def auth_providers(ctx: typer.Context) -> None:
    """List supported authentication providers from the backend catalogue."""

    from ...application.auth import list_operator_auth_providers

    report = list_operator_auth_providers()
    payload = report.model_dump(mode="json")
    if _format_of(ctx) == _FORMAT_JSON:
        import json as _json

        typer.echo(_json.dumps(payload, ensure_ascii=False))
        return
    for provider in report.providers:
        status = "implemented" if provider.implemented else "reserved"
        typer.echo(f"{provider.id}\t{status}\t{tr(str(provider.label))}")


@auth_app.command("configure", help=tr("cli.config.auth.configure_help"))
def auth_configure(
    ctx: typer.Context,
    provider: str = typer.Option(..., "--provider", help=tr("cli.config.auth.provider_help")),
    file: Path | None = typer.Option(None, "--file", help=tr("cli.config.auth.file_help")),
) -> None:
    """Configure the active authentication provider."""

    del ctx
    from ...application.auth import AuthProviderReservedError, configure_operator_auth

    try:
        result = configure_operator_auth(provider, certificate_path=file)
    except KeyError as exc:
        raise typer.BadParameter(tr("cli.config.auth.unknown_provider", provider=provider)) from exc
    except AuthProviderReservedError as exc:
        raise typer.BadParameter(tr("cli.config.auth.reserved_provider", provider=provider)) from exc
    typer.echo(f"provider\t{result.provider}")
    typer.echo(f"file\t{result.file}")


@auth_app.command("status", help=tr("cli.config.auth.status_help"))
def auth_status(ctx: typer.Context, provider: str | None = typer.Option(None, "--provider")) -> None:
    """Show the configured local authentication state."""

    from ...application.auth import inspect_operator_auth

    try:
        result = inspect_operator_auth(provider)
    except KeyError as exc:
        raise typer.BadParameter(tr("cli.config.auth.unknown_provider", provider=provider or "")) from exc
    payload = result.model_dump(mode="json")
    if _format_of(ctx) == _FORMAT_JSON:
        import json as _json

        typer.echo(_json.dumps(payload, ensure_ascii=False))
        return
    for key, value in payload.items():
        typer.echo(f"{key}\t{value}")


@auth_app.command("test", help=tr("cli.config.auth.test_help"))
def auth_test(ctx: typer.Context, provider: str | None = typer.Option(None, "--provider")) -> None:
    """Render auth readiness through the application-owned auth state."""

    from ...application.auth import test_operator_auth

    try:
        result = test_operator_auth(provider)
    except KeyError as exc:
        raise typer.BadParameter(tr("cli.config.auth.unknown_provider", provider=provider or "")) from exc
    payload = result.model_dump(mode="json")
    if _format_of(ctx) == _FORMAT_JSON:
        import json as _json

        typer.echo(_json.dumps(payload, ensure_ascii=False))
        return
    for key, value in payload.items():
        typer.echo(f"{key}\t{value}")


@auth_app.command("clear", help=tr("cli.config.auth.clear_help"))
def auth_clear(
    provider: str | None = typer.Option(None, "--provider"),
    all_providers: bool = typer.Option(False, "--all", help=tr("cli.config.auth.clear_all_help")),
    sessions: bool = typer.Option(False, "--sessions", help=tr("cli.config.auth.clear_sessions_help")),
    locks: bool = typer.Option(False, "--locks", help=tr("cli.config.auth.clear_locks_help")),
) -> None:
    """Clear local auth metadata, persisted sessions, and auth locks."""

    from ...application.auth import AuthProviderReservedError, clear_operator_auth

    try:
        result = clear_operator_auth(provider=provider, all_providers=all_providers, sessions=sessions, locks=locks)
    except KeyError as exc:
        raise typer.BadParameter(tr("cli.config.auth.unknown_provider", provider=provider or "")) from exc
    except AuthProviderReservedError as exc:
        raise typer.BadParameter(tr("cli.config.auth.reserved_provider", provider=provider or "")) from exc
    typer.echo(f"removed_sessions\t{result.removed_sessions}")
    typer.echo(f"cleared_workflow_state\t{result.cleared_workflow_state}")
    typer.echo(f"cleared_locks\t{result.cleared_locks}")


app.add_typer(profile_app, name="profile")
app.add_typer(auth_app, name="auth")

__all__ = ["app"]
