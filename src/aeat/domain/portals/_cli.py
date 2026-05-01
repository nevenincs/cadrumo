"""Typer sub-app for the ``aeat portals`` CLI surface.

Exposes three commands backed by :data:`aeat.portals.PORTAL_REGISTRY`:

- ``aeat portals list`` — filter and list portal entries.
- ``aeat portals show`` — dump a single entry.
- ``aeat portals for-modelo`` — list filing portals for a modelo.

Every command emits deterministic JSON (sorted by :class:`Portal`
value) via :meth:`pydantic.BaseModel.model_dump` or a rich table
depending on ``--json``.
"""

from __future__ import annotations

import contextlib
import sys

import typer
from rich.console import Console
from rich.table import Table

from ...core.click_context import json_output_requested
from ...core.json_contract import OutputRootSchema, emit_json_success, register_schema
from ..modelos import UnknownModeloError
from ._categories import PortalCategory
from ._errors import UnknownPortalError
from ._metadata import PortalMetadata
from ._registry import (
    PORTAL_REGISTRY,
    get_portal,
    portals_for_modelo,
)

_CONSOLE = Console()


@register_schema("portals list")
class PortalListJson(OutputRootSchema[list[PortalMetadata]]):
    """Schema for ``aeat portals list --json``."""


@register_schema("portals show")
class PortalShowJson(OutputRootSchema[PortalMetadata]):
    """Schema for ``aeat portals show --json``."""


@register_schema("portals for-modelo")
class PortalForModeloJson(OutputRootSchema[list[PortalMetadata]]):
    """Schema for ``aeat portals for-modelo --json``."""


def _ensure_utf8_streams() -> None:
    """Reconfigure stdout/stderr to UTF-8 for the current process.

    The portal catalogue carries Spanish and Hungarian characters that
    Windows legacy code-page stdout (cp1252) cannot encode. Scoped to
    the Typer callback so the side effect only applies to
    ``aeat portals`` invocations.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(ValueError, OSError):
                reconfigure(encoding="utf-8", errors="replace")


app = typer.Typer(
    name="portals",
    help="AEAT portal inventory and cross-reference helpers.",
    no_args_is_help=True,
)


@app.callback()
def _main_callback() -> None:
    """Initialise the ``aeat portals`` sub-app for the current invocation."""
    _ensure_utf8_streams()


def _entries_sorted() -> tuple[PortalMetadata, ...]:
    return tuple(sorted(PORTAL_REGISTRY.values(), key=lambda m: m.portal.value))


def _emit_entries(entries: tuple[PortalMetadata, ...], json_out: bool, *, command: str) -> None:
    if json_out or json_output_requested():
        emit_json_success(command, [e.model_dump(mode="json") for e in entries], sort_keys=True)
        return
    table = Table(title="aeat portals", header_style="bold")
    table.add_column("portal", style="cyan")
    table.add_column("category")
    table.add_column("subdomain")
    table.add_column("active")
    table.add_column("modelo")
    for entry in entries:
        table.add_row(
            entry.portal.value,
            entry.category.value,
            entry.subdomain.value,
            "yes" if entry.active else "no",
            entry.related_modelo.value if entry.related_modelo else "-",
        )
    _CONSOLE.print(table)
    _CONSOLE.print(f"[dim]{len(entries)} entry(ies)[/dim]")


@app.command(name="list", help="List portal catalogue entries with optional filters.")
def list_command(
    category: PortalCategory | None = typer.Option(None, "--category", help="Filter by portal category."),
    modelo: str | None = typer.Option(
        None, "--modelo", help="Filter by related modelo code (FILING/CENSUS/BORRADOR only)."
    ),
    active_only: bool = typer.Option(False, "--active-only", help="Exclude retired portals."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """List catalogue entries, optionally filtered."""
    entries = _entries_sorted()
    if category is not None:
        entries = tuple(e for e in entries if e.category is category)
    if modelo is not None:
        try:
            matches = portals_for_modelo(modelo)
        except UnknownModeloError as exc:
            raise typer.BadParameter(str(exc)) from exc
        match_set = frozenset(m.portal for m in matches)
        entries = tuple(e for e in entries if e.portal in match_set)
    if active_only:
        entries = tuple(e for e in entries if e.active)
    _emit_entries(entries, json_out, command="portals list")


@app.command(name="show", help="Show a single portal catalogue entry.")
def show_command(
    portal: str = typer.Argument(..., help="Portal identifier, e.g. 'portal_m303_iva_autoliquidacion'."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """Resolve a single portal and print its metadata."""
    try:
        metadata = get_portal(portal)
    except UnknownPortalError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out or json_output_requested():
        emit_json_success("portals show", metadata.model_dump(mode="json"), sort_keys=True)
        return
    _emit_entries((metadata,), json_out=False, command="portals show")
    _CONSOLE.print(f"[dim]url:[/dim] {metadata.url}")
    _CONSOLE.print(f"[dim]purpose:[/dim] {metadata.purpose_es}")


@app.command(
    name="for-modelo",
    help="List every FILING / BORRADOR portal cross-referencing a modelo.",
)
def for_modelo_command(
    code: str = typer.Argument(..., help="Three-character modelo code, e.g. '303'."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """Return the FILING / BORRADOR portals bound to ``code``."""
    try:
        entries = portals_for_modelo(code)
    except UnknownModeloError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit_entries(entries, json_out, command="portals for-modelo")


__all__ = ("app",)
