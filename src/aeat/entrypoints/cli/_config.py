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

__all__ = ["app"]
