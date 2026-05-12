"""User-facing configuration facade."""

from __future__ import annotations

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

app = typer.Typer(
    name="config",
    help=tr("cli.config.app_help"),
    no_args_is_help=True,
)
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
    """Move secure-object rows that fail tag verification into a quarantine table.

    The active ``secure_objects`` table retains only rows decryptable
    under the current master key after this operation. The quarantined
    rows are preserved (along with their original metadata) in
    ``secure_objects_quarantine`` so the operator can recover them
    manually if a missing master key is later restored.
    """

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


app.add_typer(doctor_app, name="doctor")


def _profile_state():
    from ...application.workflow._persistence import workflow_state_repository

    return workflow_state_repository()


@app.command("list", help=tr("cli.config.list.help"))
def config_list(ctx: typer.Context) -> None:
    """List every profile key with its current value (or ``<unset>``)."""

    from ...domain.profile import PROFILE_KEYS

    state = _profile_state().load()
    record = state.active_profile_record()
    values: dict[str, str] = dict(record.values) if record is not None else {}
    payload = {
        "active_profile": state.active_profile,
        "keys": [
            {
                "key": entry.key,
                "requirement": entry.requirement.value,
                "value": values.get(entry.key, ""),
            }
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


@app.command("get", help=tr("cli.config.get.help"))
def config_get(
    ctx: typer.Context,
    key: str = typer.Argument(..., help=tr("cli.config.get.key_help")),
) -> None:
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


@app.command("set", help=tr("cli.config.set.help"))
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

    question = _question_for_profile_key(registered.key)
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
    updated = repository.update(lambda current: set_profile_values(current, profile_name, {key: value}))
    record = updated.active_profile_record()
    stored_value = record.values.get(key, "") if record is not None else ""
    payload = {"key": key, "value": stored_value}
    if _format_of(ctx) == _FORMAT_JSON:
        import json as _json

        typer.echo(_json.dumps(payload, ensure_ascii=False))
        return
    typer.echo(f"{key}\t{stored_value}")


@app.command("unset", help=tr("cli.config.unset.help"))
def config_unset(
    ctx: typer.Context,
    key: str = typer.Argument(..., help=tr("cli.config.unset.key_help")),
) -> None:
    """Clear one profile key value through the shared application backend."""

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


@app.command("setup", help=tr("cli.config.setup.help"))
def config_setup(
    profile_name: str = typer.Option(
        "default",
        "--profile-name",
        help=tr("cli.config.setup.profile_name_help"),
    ),
    quiet: bool = typer.Option(False, "--quiet", help=tr("cli.config.setup.quiet_help")),
    accept_defaults: bool = typer.Option(
        False,
        "--accept-defaults",
        help=tr("cli.config.setup.accept_defaults_help"),
    ),
    tax_id: str | None = typer.Option(None, "--tax-id", help=tr("cli.config.setup.tax_id_help")),
    activity: str | None = typer.Option(None, "--activity", help=tr("cli.config.setup.activity_help")),
) -> None:
    """Run the schema-driven setup wizard interactively or via flag-driven quiet mode."""

    from ...application.wizard._catalogue import SETUP_FLOW
    from ...application.wizard._commands import build_wizard_command
    from ...application.wizard._errors import WizardMissingFlagError

    flag_values: dict[str, str] = {}
    if tax_id is not None:
        flag_values["tax-id"] = tax_id
    if activity is not None:
        flag_values["activity"] = activity

    command = build_wizard_command(SETUP_FLOW)
    try:
        command(
            profile_name=profile_name,
            quiet=quiet,
            accept_defaults=accept_defaults,
            flag_values=flag_values,
        )
    except WizardMissingFlagError as exc:
        translated = exc.translated_message or tr("cli.config.setup.errors.missing_required_flags")
        raise typer.BadParameter(translated) from exc


@app.command("status", help=tr("cli.config.status.help"))
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
    scope: str = typer.Option(
        "all",
        "--scope",
        help=tr("cli.config.reset.scope_help"),
    ),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.reset.yes_help")),
) -> None:
    """Reset operator-entered configuration scopes."""

    from ...application.setup_reset import SetupResetScope, reset_setup

    if not yes:
        raise typer.BadParameter(tr("cli.config.reset.requires_yes"))
    try:
        scope_enum = SetupResetScope(scope)
    except ValueError as exc:
        valid = ", ".join(member.value for member in SetupResetScope)
        raise typer.BadParameter(tr("cli.config.reset.invalid_scope", scope=scope, valid=valid)) from exc
    report = reset_setup(scope_enum, confirmed=True)
    typer.echo(f"scope\t{report.scope.value}")
    typer.echo(f"removed_profiles\t{len(report.removed_profile_names)}")
    typer.echo(f"removed_auth\t{report.removed_auth_session}")


@app.command("auth", help=tr("cli.config.auth.help"))
def config_auth(
    ctx: typer.Context,
    provider: str = typer.Option(
        ...,
        "--provider",
        help=tr("cli.config.auth.provider_help"),
    ),
    file: Path | None = typer.Option(None, "--file", help=tr("cli.config.auth.file_help")),
) -> None:
    """Configure the active authentication provider."""

    del ctx
    from ...application.auth._actions import update_auth
    from ...application.auth._catalogue import get_auth_provider
    from ...application.workflow._persistence import workflow_state_repository

    try:
        listing = get_auth_provider(provider)
    except KeyError as exc:
        raise typer.BadParameter(tr("cli.config.auth.unknown_provider", provider=provider)) from exc
    repository = workflow_state_repository()
    repository.update(
        lambda current: update_auth(
            current,
            provider=listing.id,
            certificate_path=str(file) if file is not None else None,
        )
    )
    typer.echo(f"provider\t{listing.id}")
    typer.echo(f"file\t{file or ''}")


__all__ = ["app"]
