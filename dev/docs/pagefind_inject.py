"""Inject the unified search records into the Pagefind index (ADR D4 + D5).

This is the custom-record injection that plugs into the post-build index
pass's seam: ``build_search_index(html_root, inject=build_record_injector())``
calls the returned async callback with the open ``PagefindIndex`` after the
HTML directory pass and before the index is written. Where the directory pass
indexes the built docs pages (full text, ADR-D5 tier three), this injection
adds the term cards (tier one) and the casilla / CLI navigation surfaces (tier
two) as first-class custom records, so the one Pagefind index serves all four
record kinds.

The records are materialised by the deterministic projections (concept cards
from the Handbook, casilla projections from the registry authority, CLI
surface records from the live command tree) and funnelled through the uniform
:class:`~dev.docs.terminology._unified_record.SearchRecord`. Each record is
injected once per language section it carries, with the per-language
description as the searchable content, so Pagefind's es/en/ca/hu index splits
each receive the record in their own language. Typed metadata (kind,
concept id/domain, modelo/casilla number, command path) rides on the record
for the palette term card, and ``kind``/``domain`` filters let the palette
narrow by surface.

Ranking: every record carries a base ranking weight from the unified
projection (ADR D5 tier ordering - concepts outrank navigation outranks full
text). If the committed relevance file
(``src/aeat/_data/terminology/relevance/relevance.json``) is present, its
term-to-target weights BOOST the matching records; if absent, the base weights
stand. Because the Pagefind index regenerates on every build and this module
re-reads the relevance file each run, the boost applies automatically once the
relevance file lands - no re-injection is needed.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from aeat.core.external_constants import OutputLanguage

from .terminology._unified_record import SearchRecord, to_search_record

if TYPE_CHECKING:
    from pagefind.index import PagefindIndex

logger = logging.getLogger(__name__)

InjectCallback = Callable[["PagefindIndex"], Awaitable[None]]

#: The committed relevance-weights file (the build-time RAG sweep's output).
#: Optional: present-boosts, absent-uses-base-weights. Re-read every build so
#: it auto-applies the moment the sweep lands the file.
_RELEVANCE_RELPATH = Path("src") / "aeat" / "_data" / "terminology" / "relevance" / "relevance.json"

#: Pagefind meta / filter / sort values are strings; the weight is rendered to
#: a fixed-width zero-padded integer string so Pagefind's lexical sort orders
#: records by descending relevance (higher weight -> larger sort key).
_SORT_SCALE = 1_000_000


@dataclass(frozen=True)
class InjectionStats:
    """Counts from a record-injection run, per kind and per language."""

    concepts: int = 0
    casillas: int = 0
    cli_commands: int = 0
    cli_options: int = 0
    custom_records_written: int = 0
    languages: tuple[str, ...] = ()
    cli_skipped_reason: str | None = None
    relevance_boosts_applied: int = 0


@dataclass
class _Materialised:
    """The unified records to inject, plus the projection stats."""

    records: list[SearchRecord] = field(default_factory=list)
    concepts: int = 0
    casillas: int = 0
    cli_commands: int = 0
    cli_options: int = 0
    cli_skipped_reason: str | None = None


def load_relevance_weights(repo_root: Path) -> dict[str, float]:
    """Load the committed term-to-weight relevance map, or an empty map.

    The file maps a record ``id`` (or a term/target identifier the sweep
    emitted) to a relevance weight in ``[0, 1]``. Absent or unparseable file
    yields an empty map - the injection then uses base weights only.

    Args:
        repo_root: Repository root holding the relevance file.

    Returns:
        A ``record-id -> weight`` mapping (possibly empty).
    """
    path = repo_root / _RELEVANCE_RELPATH
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("relevance file present but unreadable: %s", path)
        return {}
    weights: dict[str, float] = {}
    raw = data.get("weights", data) if isinstance(data, dict) else {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, (int, float)):
                weights[str(key)] = min(1.0, max(0.0, float(value)))
    return weights


def _materialise_records() -> _Materialised:
    """Project and funnel every record kind into unified search records.

    Concepts and casillas are the priority surfaces and always project. The CLI
    projection runs the live-command-tree subprocess walk; if it fails (a
    transiently broken CLI), it is skipped-and-reported rather than failing the
    whole injection - concepts + casillas still land.
    """
    from .terminology._casilla_projection import project_casilla_search_records
    from .terminology._concept_cards import project_concept_cards

    out = _Materialised()

    concept_cards, _ = project_concept_cards()
    out.concepts = len(concept_cards)
    out.records.extend(to_search_record(card) for card in concept_cards)

    casilla_records, _ = project_casilla_search_records()
    out.casillas = len(casilla_records)
    out.records.extend(to_search_record(rec) for rec in casilla_records)

    try:
        from .terminology._cli_projection import project_cli_search_records

        commands, options, _ = project_cli_search_records()
    except Exception as exc:  # the live CLI walk is fragile under peer churn
        out.cli_skipped_reason = f"{type(exc).__name__}: {exc}"
        logger.warning("CLI projection skipped: %s", out.cli_skipped_reason)
    else:
        out.cli_commands = len(commands)
        out.cli_options = len(options)
        out.records.extend(to_search_record(rec) for rec in commands)
        out.records.extend(to_search_record(rec) for rec in options)
    return out


def _effective_weight(record: SearchRecord, relevance: dict[str, float]) -> float:
    """Return the record's ranking weight, boosted by relevance when present.

    The relevance weight, when the file supplies one for this record id, is
    blended into the base weight (taking the stronger of the two, capped at 1)
    so a sweep-favoured record ranks at least as high as its base tier.
    """
    boost = relevance.get(record.id)
    if boost is None:
        return record.ranking_weight
    return min(1.0, max(record.ranking_weight, boost))


def _sort_key(weight: float) -> str:
    """Render a weight to a zero-padded integer string for Pagefind sort."""
    return f"{round(weight * _SORT_SCALE):08d}"


def _content_for(record: SearchRecord, language: OutputLanguage, description: str) -> str:
    """Build the searchable content for one language section of a record."""
    parts = [record.title, description]
    return "\n".join(part for part in parts if part)


def _meta_for(record: SearchRecord, weight: float) -> dict[str, str]:
    """Build the typed Pagefind meta map for the palette term card."""
    meta: dict[str, str] = {
        "kind": record.kind.value,
        "tier": record.tier.value,
        "title": record.title,
        "weight": f"{weight:.6f}",
    }
    md = record.metadata
    if md.concept_id:
        meta["concept_id"] = md.concept_id
    if md.domain:
        meta["domain"] = md.domain
    if md.modelo:
        meta["modelo"] = md.modelo
    if md.number:
        meta["number"] = md.number
    if md.command_path:
        meta["command_path"] = md.command_path
    return meta


def _filters_for(record: SearchRecord) -> dict[str, list[str]]:
    """Build the Pagefind filter map (kind + domain) for palette narrowing."""
    filters: dict[str, list[str]] = {"kind": [record.kind.value]}
    if record.metadata.domain:
        filters["domain"] = [record.metadata.domain]
    return filters


async def _inject_records(
    index: PagefindIndex,
    materialised: _Materialised,
    relevance: dict[str, float],
) -> InjectionStats:
    written = 0
    boosts = 0
    languages: set[str] = set()
    for record in materialised.records:
        weight = _effective_weight(record, relevance)
        if record.id in relevance:
            boosts += 1
        meta = _meta_for(record, weight)
        filters = _filters_for(record)
        sort = {"weight": _sort_key(weight)}
        for language, description in record.descriptions.items():
            if not description:
                continue
            await index.add_custom_record(
                url=record.target,
                content=_content_for(record, language, description),
                language=language.value,
                meta=meta,
                filters=filters,
                sort=sort,
            )
            written += 1
            languages.add(language.value)
    return InjectionStats(
        concepts=materialised.concepts,
        casillas=materialised.casillas,
        cli_commands=materialised.cli_commands,
        cli_options=materialised.cli_options,
        custom_records_written=written,
        languages=tuple(sorted(languages)),
        cli_skipped_reason=materialised.cli_skipped_reason,
        relevance_boosts_applied=boosts,
    )


def build_record_injector(
    repo_root: Path,
    *,
    on_complete: Callable[[InjectionStats], None] | None = None,
) -> InjectCallback:
    """Return the injection callback for the post-build index pass.

    The callback materialises every unified search record, applies the
    committed relevance boost when present, and injects one custom record per
    language section so each Pagefind language split receives the record.

    Args:
        repo_root: Repository root (for the relevance file).
        on_complete: Optional sink for the :class:`InjectionStats` (a caller
            that wants the counts, since the seam itself returns no value).

    Returns:
        An async callback suitable for ``build_search_index(..., inject=...)``.
    """
    relevance = load_relevance_weights(repo_root)

    async def _inject(index: PagefindIndex) -> None:
        materialised = _materialise_records()
        stats = await _inject_records(index, materialised, relevance)
        if on_complete is not None:
            on_complete(stats)

    return _inject
