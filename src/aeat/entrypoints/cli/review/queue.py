"""``aeat review queue`` command implementation.

Collects and renders the unified review queue across every kind of
pending pipeline decision (transactions, invoices, divergences, filing
findings, inbox), with optional filtering by kind, modelo, state and
classification confidence.

Delegates collection to :class:`aeat.application.review.ReviewQueue`
and only handles parameter parsing, filtering and rendering.
"""

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
from ....core.i18n import get_translation
from .._i18n import output_language, t, tr

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
        help=tr(
            t(
                "Filtra por uno o varios tipos de revisión (repetible). Valores: "
                "transaction, invoice, divergence, finding, inbox. Los tokens "
                "reservados 'classification' y 'approval-stale' son rechazados "
                "con un mensaje de bloqueo.",
                "Filter to one or more review kinds (repeatable). One of: "
                "transaction, invoice, divergence, finding, inbox. Reserved "
                "tokens 'classification' and 'approval-stale' are rejected "
                "with a blocking-issue message.",
                "Filtra per un o més tipus de revisió (repetible). Valors: "
                "transaction, invoice, divergence, finding, inbox. Els tokens "
                "reservats 'classification' i 'approval-stale' són rebutjats "
                "amb un missatge de bloqueig.",
                "Egy vagy tobb felulvizsgalat tipus szurese (ismetelheto). "
                "Ertekek: transaction, invoice, divergence, finding, inbox. "
                "A foglalt 'classification' es 'approval-stale' tokeneket "
                "blokkolo uzenet utasitja vissza.",
            )
        ),
    ),
    state: ReviewState = typer.Option(
        ReviewState.PENDING,
        "--state",
        case_sensitive=False,
        help=tr(
            t(
                "Filtra por estado de revisión (actualmente solo 'pending' lo emite alguna fuente).",
                "Filter by review state (currently only 'pending' is emitted by any source).",
                "Filtra per estat de revisió (actualment només 'pending' és emès per alguna font).",
                "Felulvizsgalat allapotara szures (jelenleg csak a 'pending' kerul kibocsatasra).",
            )
        ),
    ),
    modelo: str | None = typer.Option(
        None,
        "--modelo",
        help=tr(
            t(
                "Restringe a elementos vinculados a un único modelo (excluye los que no tienen modelo).",
                "Filter to items bound to one modelo (excludes items with no modelo concept).",
                "Restringeix a elements vinculats a un sol model (exclou els que no tenen cap model).",
                "Egy adott modeloz kotott elemekre szukit (kihagyja a modell nelkulieket).",
            )
        ),
    ),
    confidence_below: str | None = typer.Option(
        None,
        "--confidence-below",
        help=tr(
            t(
                "Solo muestra elementos de transacción cuya confianza de clasificación es "
                "estrictamente menor que este umbral (0..1). Otros tipos quedan excluidos "
                "cuando este filtro está activo.",
                "Show only transaction review items whose classification confidence is "
                "strictly below this threshold (0..1). Items of other kinds are excluded "
                "when this filter is active.",
                "Mostra només els elements de transacció amb una confiança de classificació "
                "estrictament inferior a aquest llindar (0..1). Els altres tipus s'exclouen "
                "quan aquest filtre està actiu.",
                "Csak azokat a tranzakcios elemeket mutatja, amelyek osztalyozasi bizonyossaga "
                "szigoruan kisebb ennel a kuszobnel (0..1). A tobbi tipus kizart, amig ez a szuro aktiv.",
            )
        ),
    ),
    fmt: ReviewFormat = typer.Option(
        ReviewFormat.TABLE,
        "--format",
        case_sensitive=False,
        help=tr(
            t(
                "Formato de salida: 'table' (por defecto) o 'json'.",
                "Output format: 'table' (default) or 'json'.",
                "Format de sortida: 'table' (per defecte) o 'json'.",
                "Kimeneti formatum: 'table' (alapertelmezett) vagy 'json'.",
            )
        ),
    ),
) -> None:
    """List every pending review item across the pipeline in one table.

    Args:
        kind: One or more :class:`ReviewItemKind` tokens; reserved
            tokens raise ``typer.BadParameter``.
        state: Filter by review state.
        modelo: Restrict to items bound to one modelo.
        confidence_below: When set, restrict to transaction items whose
            classification confidence is strictly below this threshold.
        fmt: Output format (table or JSON).
    """
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
        raise typer.BadParameter(
            tr(
                t(
                    f"--confidence-below {value!r} no es un Decimal válido",
                    f"--confidence-below {value!r} is not a valid Decimal",
                    f"--confidence-below {value!r} no és un Decimal vàlid",
                    f"--confidence-below {value!r} nem ervenyes Decimal",
                )
            )
        ) from exc
    if not _CONFIDENCE_MIN <= threshold <= _CONFIDENCE_MAX:
        raise typer.BadParameter(
            tr(
                t(
                    "--confidence-below debe estar dentro del rango inclusivo 0..1",
                    "--confidence-below must be within the inclusive 0..1 range",
                    "--confidence-below ha d'estar dins del rang inclusiu 0..1",
                    "--confidence-below a 0..1 zart intervallumon belul kell legyen",
                )
            )
        )
    return threshold


def _parse_kinds(tokens: list[str] | None) -> frozenset[ReviewItemKind] | None:
    """Parse repeated ``--kind`` tokens into a frozenset of enum values."""
    if tokens is None:
        return None
    parsed: set[ReviewItemKind] = set()
    for token in tokens:
        normalised = token.strip().lower()
        reservation = reserved_kind_reason(normalised)
        if reservation is not None:
            raise typer.BadParameter(
                tr(
                    t(
                        f"--kind {normalised!r} está reservado pero aún no se emite: {reservation}",
                        f"--kind {normalised!r} is reserved but not yet emitted: {reservation}",
                        f"--kind {normalised!r} és reservat però encara no s'emet: {reservation}",
                        f"--kind {normalised!r} foglalt, de meg nem kerul kibocsatasra: {reservation}",
                    )
                )
            ) from ReviewKindReservedError(normalised, reservation)
        try:
            parsed.add(ReviewItemKind(normalised))
        except ValueError as exc:
            valid = ", ".join(member.value for member in ReviewItemKind)
            raise typer.BadParameter(
                tr(
                    t(
                        f"--kind {normalised!r} no es reconocido; valores válidos: {valid}",
                        f"--kind {normalised!r} is not recognised; valid: {valid}",
                        f"--kind {normalised!r} no és reconegut; valors vàlids: {valid}",
                        f"--kind {normalised!r} nem ismert; ervenyes ertekek: {valid}",
                    )
                )
            ) from exc
    return frozenset(parsed)


def _emit_table(items: tuple[ReviewItem, ...]) -> None:
    """Render ``items`` as a Rich table on the shared console."""
    if not items:
        _CONSOLE.print(
            "[dim]"
            + tr(
                t(
                    "No hay elementos de revisión pendientes.",
                    "No pending review items.",
                    "No hi ha elements de revisió pendents.",
                    "Nincs fuggoben levo felulvizsgalat.",
                )
            )
            + "[/dim]"
        )
        return
    table = Table(
        title=tr(
            t(
                "cola de revisión",
                "review queue",
                "cua de revisió",
                "felulvizsgalati sor",
            )
        ),
        header_style="bold",
    )
    table.add_column(tr(t("tipo", "kind", "tipus", "tipus")), style="cyan")
    table.add_column(tr(t("id", "id", "id", "id")))
    table.add_column(tr(t("modelo", "modelo", "model", "modell")))
    table.add_column(tr(t("severidad", "severity", "severitat", "sulyossag")))
    table.add_column(tr(t("resumen", "summary", "resum", "osszegzes")), overflow="fold")
    table.add_column(tr(t("desde", "since", "des de", "ota")))
    table.add_column(tr(t("acceso →", "drill →", "accés →", "leasas →")), overflow="fold")

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
    summary_line = tr(
        t(
            f"[{len(items)} elemento{'' if len(items) == 1 else 's'} — "
            f"{kind_count} tipo{'' if kind_count == 1 else 's'}]",
            f"[{len(items)} item{'' if len(items) == 1 else 's'} — "
            f"{kind_count} kind{'' if kind_count == 1 else 's'}]",
            f"[{len(items)} element{'' if len(items) == 1 else 's'} — "
            f"{kind_count} tipus]",
            f"[{len(items)} elem — {kind_count} tipus]",
        )
    )
    _CONSOLE.print(f"[dim]{summary_line}[/dim]")


def _emit_json(items: tuple[ReviewItem, ...]) -> None:
    """Emit ``items`` as a JSON array via :func:`typer.echo`."""
    payload = [item.model_dump(mode="json") for item in items]
    typer.echo(json.dumps(payload, indent=2, default=str))


def _short_id(value: str) -> str:
    """Truncate long ids to ``_ID_DISPLAY_LEN`` for table display."""
    if len(value) <= _ID_DISPLAY_LEN:
        return value
    return value[:_ID_DISPLAY_LEN] + "…"


def _summary_text(item: ReviewItem) -> str:
    """Render the review item summary in the operator's CLI language.

    Routes through :func:`get_translation` so ``AEAT_OUTPUT_LANGUAGE``
    is honoured. The configured fallback chain handles partial
    summaries (records seeded before the quad-lingual contract may
    miss ``ca`` or ``hu``); empty summaries return an empty string
    rather than raising.
    """

    summary = item.summary
    if not summary:
        return ""
    return get_translation(summary, output_language())


def _relative_since(when: datetime, *, now: datetime) -> str:
    """Return a coarse human-readable age (``Nm/Nh/Nd ago`` or ISO date)."""
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
