"""``aeat review queue`` — emit the unified review queue."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import typer
from rich.console import Console
from rich.table import Table

from ....application.review import (
    ReviewFormat,
    ReviewItem,
    ReviewItemKind,
    ReviewKindReservedError,
    ReviewQueue,
    ReviewSeverity,
    ReviewState,
    reserved_kind_reason,
)
from ....core.config import load_settings

_CONFIDENCE_MIN = Decimal("0")
_CONFIDENCE_MAX = Decimal("1")

_CONSOLE = Console()

_SEVERITY_STYLE: dict[ReviewSeverity, str] = {
    ReviewSeverity.CRITICAL: "bold red",
    ReviewSeverity.HIGH: "yellow",
    ReviewSeverity.NORMAL: "default",
    ReviewSeverity.INFO: "dim",
}

_ID_DISPLAY_LEN = 16


def queue_cmd(
    kind: list[str] | None = typer.Option(
        None,
        "--kind",
        help=(
            "Filter to one or more review kinds (repeatable). One of: "
            "transaction, invoice, divergence, finding, inbox. "
            "Reserved tokens 'classification' and 'approval-stale' are "
            "rejected with a blocking-issue message."
        ),
    ),
    state: ReviewState = typer.Option(
        ReviewState.PENDING,
        "--state",
        case_sensitive=False,
        help="Filter by review state (currently only 'pending' is emitted by any source).",
    ),
    modelo: str | None = typer.Option(
        None,
        "--modelo",
        help="Filter to items bound to one modelo (excludes items with no modelo concept).",
    ),
    confidence_below: str | None = typer.Option(
        None,
        "--confidence-below",
        help=(
            "Show only transaction review items whose classification confidence "
            "is strictly below this threshold (0..1). Items of other kinds are "
            "excluded when this filter is active."
        ),
    ),
    fmt: ReviewFormat = typer.Option(
        ReviewFormat.TABLE,
        "--format",
        case_sensitive=False,
        help="Output format: 'table' (default) or 'json'.",
    ),
) -> None:
    """List every pending review item across the pipeline in one table."""
    kinds = _parse_kinds(kind)
    threshold = _parse_confidence_threshold(confidence_below)
    settings = load_settings()
    items = ReviewQueue.collect(
        settings,
        kinds=kinds,
        modelo=modelo,
        state=state,
        confidence_below=threshold,
    )
    if fmt is ReviewFormat.JSON:
        _emit_json(items)
        return
    _emit_table(items)


def _parse_confidence_threshold(value: str | None) -> Decimal | None:
    """Parse and range-check the ``--confidence-below`` option value."""
    if value is None:
        return None
    try:
        threshold = Decimal(value)
    except InvalidOperation as exc:
        raise typer.BadParameter(f"--confidence-below {value!r} is not a valid Decimal") from exc
    if not _CONFIDENCE_MIN <= threshold <= _CONFIDENCE_MAX:
        raise typer.BadParameter("--confidence-below must be within the inclusive 0..1 range")
    return threshold


def _parse_kinds(tokens: list[str] | None) -> frozenset[ReviewItemKind] | None:
    if tokens is None:
        return None
    parsed: set[ReviewItemKind] = set()
    for token in tokens:
        normalised = token.strip().lower()
        reservation = reserved_kind_reason(normalised)
        if reservation is not None:
            raise typer.BadParameter(
                f"--kind {normalised!r} is reserved but not yet emitted: {reservation}"
            ) from ReviewKindReservedError(normalised, reservation)
        try:
            parsed.add(ReviewItemKind(normalised))
        except ValueError as exc:
            valid = ", ".join(member.value for member in ReviewItemKind)
            raise typer.BadParameter(f"--kind {normalised!r} is not recognised; valid: {valid}") from exc
    return frozenset(parsed)


def _emit_table(items: tuple[ReviewItem, ...]) -> None:
    if not items:
        _CONSOLE.print("[dim]No pending review items.[/dim]")
        return
    table = Table(title="review queue", header_style="bold")
    table.add_column("kind", style="cyan")
    table.add_column("id")
    table.add_column("modelo")
    table.add_column("severity")
    table.add_column("summary", overflow="fold")
    table.add_column("since")
    table.add_column("drill →", overflow="fold")

    now = datetime.now(tz=UTC)
    for item in items:
        severity_style = _SEVERITY_STYLE[item.severity]
        table.add_row(
            item.kind.value,
            _short_id(item.item_id),
            item.modelo or "-",
            f"[{severity_style}]{item.severity.value}[/{severity_style}]",
            _summary_text(item),
            _relative_since(item.since, now=now),
            item.drill_command,
        )
    _CONSOLE.print(table)
    kind_count = len({item.kind for item in items})
    plural_item = "" if len(items) == 1 else "s"
    plural_kind = "" if kind_count == 1 else "s"
    _CONSOLE.print(f"[dim][{len(items)} item{plural_item} — {kind_count} kind{plural_kind}][/dim]")


def _emit_json(items: tuple[ReviewItem, ...]) -> None:
    payload = [item.model_dump(mode="json") for item in items]
    typer.echo(json.dumps(payload, indent=2, default=str))


def _short_id(value: str) -> str:
    if len(value) <= _ID_DISPLAY_LEN:
        return value
    return value[:_ID_DISPLAY_LEN] + "…"


def _summary_text(item: ReviewItem) -> str:
    summary = item.summary
    return summary.get("en") or summary.get("es") or summary.get("hu") or ""


def _relative_since(when: datetime, *, now: datetime) -> str:
    delta = now - when
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return when.date().isoformat()
    if seconds < 3600:
        return f"{max(seconds // 60, 1)}m ago"
    if seconds < 86_400:
        return f"{seconds // 3600}h ago"
    days = seconds // 86_400
    if days < 30:
        return f"{days}d ago"
    return when.date().isoformat()
