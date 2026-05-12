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


@app.command("set", help=tr("cli.config.set.help"))
def config_set(
    ctx: typer.Context,
    key: str = typer.Argument(..., help=tr("cli.config.set.key_help")),
    value: str = typer.Argument(..., help=tr("cli.config.set.value_help")),
) -> None:
    """Write one profile key value through the shared application backend."""

    from ...application.profile._actions import set_profile_values
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


__all__ = ["app"]
