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
    modelo: Annotated[str | None, typer.Option("--modelo", help=tr("cli.app.live.modelo_help"))] = None,
    year_from: Annotated[
        int | None,
        typer.Option("--from-year", min=2000, max=2099, help=tr("cli.app.live.from_year_help")),
    ] = None,
    year_to: Annotated[
        int | None,
        typer.Option("--to-year", min=2000, max=2099, help=tr("cli.app.live.to_year_help")),
    ] = None,
) -> None:
    """List filed-declaration rows without downloading justificantes or submitted files.

    All filters are optional refinements. When ``--modelo`` is omitted the
    listing iterates every modelo configured in the registry. When
    ``--from-year`` / ``--to-year`` are omitted they default to the current
    calendar year.
    """

    from datetime import date as _date

    from ...core.config import PROJECT_ROOT
    from ...domain.calculations.registry import ValidatedRegistryAuthority

    resolved_from = year_from if year_from is not None else _date.today().year
    resolved_to = year_to if year_to is not None else _date.today().year
    if modelo is None:
        authority = ValidatedRegistryAuthority.load(
            PROJECT_ROOT / "registry" / "aeat", source_root=PROJECT_ROOT
        )
        modelos = tuple(str(m.id) for m in authority.modelos)
    else:
        modelos = (modelo,)
    all_rows: list[object] = []
    total_count = 0
    for code in modelos:
        report = asyncio.run(
            list_filed_data(
                modelo=code,
                year_from=resolved_from,
                year_to=resolved_to,
            )
        )
        total_count += report.row_count
        all_rows.extend(report.rows)
    lines = [_metric_line("row_count", total_count)]
    for row in all_rows:
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
    payload = {
        "modelo_filter": modelo,
        "year_from": resolved_from,
        "year_to": resolved_to,
        "row_count": total_count,
        "rows": [row.model_dump(mode="json") for row in all_rows],
    }
    _emit(ctx, payload, lines)


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


# ─────────────────────────────────────────────────────────────────────────
# Portals subgroup (W79 app-live-shape, apex §4.4 + R13)
# ─────────────────────────────────────────────────────────────────────────
# Portals list and show are local-only catalogue reads. They do NOT call
# AEAT and therefore do not invoke require_live_read; per apex §4.4 the
# subgroup lives under aeat app live for operator-discovery convenience.

portals_app = typer.Typer(
    name="portals",
    help=tr("cli.app.live.portals.app_help", default="Local AEAT portal registry catalogue (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(portals_app, name="portals")


def _portal_row(metadata) -> dict[str, object]:
    return {
        "portal": metadata.portal.value,
        "category": metadata.category.value,
        "subdomain": metadata.subdomain.value,
        "url": str(metadata.url),
        "auth_methods": ",".join(sorted(method.value for method in metadata.auth_methods)),
        "url_stability": metadata.url_stability.value,
        "label": str(metadata.label),
        "purpose": str(metadata.purpose),
        "active": metadata.active,
    }


@portals_app.command("list", help=tr("cli.app.live.portals.list_help", default="List portal-registry entries (optionally filtered)."))
def portals_list(
    ctx: typer.Context,
    category: Annotated[
        str | None,
        typer.Option("--category", help=tr("cli.app.live.portals.category_help", default="Filter to one PortalCategory value.")),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help=tr("cli.app.live.portals.modelo_help", default="Filter to portals bound to one modelo code (e.g. 303).")),
    ] = None,
) -> None:
    from ...domain.portals import PORTAL_REGISTRY, PortalCategory, portals_by_category, portals_for_modelo

    if category and modelo:
        raise typer.BadParameter("--category and --modelo are mutually exclusive")
    if category:
        try:
            cat = PortalCategory(category)
        except ValueError as exc:
            raise typer.BadParameter(f"Unknown portal category: {category!r}") from exc
        entries = portals_by_category(cat)
    elif modelo:
        entries = portals_for_modelo(modelo)
    else:
        entries = tuple(PORTAL_REGISTRY.values())

    rows = [_portal_row(m) for m in entries]
    payload = {"count": len(rows), "rows": rows}
    lines = [f"count\t{len(rows)}"]
    for row in rows:
        lines.append(f"{row['portal']}\t{row['category']}\t{row['url_stability']}\t{row['label']}")
    _emit(ctx, payload, lines)


@portals_app.command("show", help=tr("cli.app.live.portals.show_help", default="Show one portal-registry entry by Portal id."))
def portals_show(
    ctx: typer.Context,
    portal_id: Annotated[str, typer.Argument(help=tr("cli.app.live.portals.portal_id_help", default="Portal enum value."))],
) -> None:
    from ...domain.portals import get_portal

    try:
        metadata = get_portal(portal_id)
    except Exception as exc:  # PortalLookupError + similar typed registry errors
        raise typer.BadParameter(str(exc)) from exc
    payload = _portal_row(metadata)
    lines = [f"{key}\t{value}" for key, value in payload.items() if value != ""]
    _emit(ctx, payload, lines)


__all__ = [
    "app",
    "filed_app",
    "filed_capture_cmd",
    "filed_capture_sources_cmd",
    "filed_list_cmd",
    "portals_app",
    "portals_list",
    "portals_show",
]
