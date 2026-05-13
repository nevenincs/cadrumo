"""Explicit read-only AEAT live observation CLI commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from ...application.live import capture_filed_data, capture_source_filed_data, list_filed_data
from ._common import _emit
from ._i18n import tr

app = typer.Typer(
    name="live",
    help=tr("cli.app.live.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
filed_app = typer.Typer(
    name="filed",
    help=tr("cli.app.live.filed_app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(filed_app, name="filed")


def _metric_line(key: str, value: object) -> str:
    return f"{key}={value}"


@filed_app.command("list", help=tr("cli.app.live.filed.list_help"))
def filed_list_cmd(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Option("--modelo", help=tr("cli.app.live.modelo_help"))],
    year_from: Annotated[int, typer.Option("--from-year", min=2000, max=2099, help=tr("cli.app.live.from_year_help"))],
    year_to: Annotated[int, typer.Option("--to-year", min=2000, max=2099, help=tr("cli.app.live.to_year_help"))],
) -> None:
    """List filed-declaration rows without downloading justificantes or submitted files."""

    report = asyncio.run(
        list_filed_data(
            modelo=modelo,
            year_from=year_from,
            year_to=year_to,
        )
    )
    lines = [_metric_line("row_count", report.row_count)]
    for row in report.rows:
        lines.append(
            _metric_line(
                "row",
                "\t".join(
                    (
                        row.modelo,
                        str(row.year),
                        row.period,
                        row.expediente_id,
                        row.status,
                        row.presented_at.isoformat(),
                        f"submitted_file={row.has_submitted_file}",
                        f"declaration_copy={row.has_declaration_copy}",
                        f"justificante={row.has_justificante}",
                    )
                ),
            )
        )
    _emit(ctx, report, lines)


@filed_app.command("capture", help=tr("cli.app.live.filed.capture_help"))
def filed_capture_cmd(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Option("--modelo", help=tr("cli.app.live.modelo_help"))],
    year: Annotated[int, typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help"))],
    output_root: Annotated[
        Path,
        typer.Option(
            "--output-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.app.live.output_root_help"),
        ),
    ] = Path("var/aeat/filed-declarations"),
    period: Annotated[str | None, typer.Option("--period", help=tr("cli.app.live.period_help"))] = None,
    expediente_id: Annotated[str | None, typer.Option("--expediente", help=tr("cli.app.live.expediente_help"))] = None,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help=tr("cli.app.live.limit_help"))] = None,
) -> None:
    """Capture filed-declaration data from the authenticated AEAT register."""

    report = asyncio.run(
        capture_filed_data(
            modelo=modelo,
            year=year,
            output_root=output_root,
            period=period,
            expediente_id=expediente_id,
            limit=limit,
        )
    )
    _emit(
        ctx,
        report,
        (
            _metric_line("captured_count", report.captured_count),
            _metric_line("casilla_count", report.casilla_count),
            _metric_line("observation_paths", ",".join(report.observation_paths)),
            _metric_line("artefact_refs", ",".join(report.artefact_refs)),
        ),
    )


@filed_app.command("capture-sources", help=tr("cli.app.live.filed.capture_sources_help"))
def filed_capture_sources_cmd(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Option("--modelo", help=tr("cli.app.live.modelo_help"))],
    year: Annotated[int, typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help"))],
    period: Annotated[str, typer.Option("--period", help=tr("cli.app.live.period_help"))],
    output_root: Annotated[
        Path,
        typer.Option(
            "--output-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.app.live.output_root_help"),
        ),
    ] = Path("var/aeat/filed-declarations"),
    registry_root: Annotated[
        Path,
        typer.Option(
            "--registry-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.app.live.registry_root_help"),
        ),
    ] = Path("registry/aeat"),
    source_root: Annotated[
        Path,
        typer.Option(
            "--source-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.app.live.source_root_help"),
        ),
    ] = Path("."),
) -> None:
    """Capture filed observations required by a target filing's dependencies."""

    report = asyncio.run(
        capture_source_filed_data(
            modelo=modelo,
            year=year,
            period=period,
            output_root=output_root,
            registry_root=registry_root,
            source_root=source_root,
        )
    )
    _emit(
        ctx,
        report,
        (
            _metric_line("captured_count", report.captured_count),
            _metric_line("casilla_count", report.casilla_count),
            _metric_line("observation_paths", ",".join(report.observation_paths)),
            _metric_line("artefact_refs", ",".join(report.artefact_refs)),
        ),
    )


__all__ = ["app", "filed_app", "filed_capture_cmd", "filed_capture_sources_cmd", "filed_list_cmd"]
