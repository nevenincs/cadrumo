"""Inject the unified search records into the Pagefind index.

This is the custom-record injection that plugs into the post-build index
pass's seam: ``build_search_index(html_root, inject=build_record_injector())``
calls the returned async callback with the open ``PagefindIndex`` after the
HTML directory pass and before the index is written. Where the directory pass
indexes the built docs pages (full text, tier three), this injection
adds the term cards (tier one) and the casilla / CLI navigation surfaces (tier
two) as first-class custom records, so the one Pagefind index serves all five
record kinds.

The records are materialised by the deterministic projections (concept cards
from the Handbook, casilla projections from the registry authority, CLI
surface records from the live command tree, legal provisions from the
registry-backed legal-reference projection) and funnelled through the uniform
:class:`~dev.docs.terminology.unified_record.SearchRecord`. Each record is
injected ONCE, into the language of the root being built, with content
carrying every language's description (see :func:`_content_for`). It is not
injected once per language section: Pagefind's reader loads only the index
matching the page's own language, so a record duplicated into the other three
splits would be unreachable weight, while a record placed in a split the root
never loads would be invisible. Typed metadata (kind, concept id/domain,
modelo/casilla.id, command path, and legal catalogue/BOE grounding) rides on
the record for the palette term card, and ``kind``/``domain`` filters let the
palette narrow by surface.

Ranking: every record carries a base ranking weight from the unified
projection (tier ordering - concepts outrank navigation outranks full
text). If the committed relevance file
(``dev/docs/terminology/relevance/relevance.json``) is present, its
term-to-target weights BOOST the matching records; if absent, the base weights
stand. Because the Pagefind index regenerates on every build and this module
re-reads the relevance file each run, the boost applies automatically once the
relevance file lands - no re-injection is needed.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import ValidationError

from cadrumo.core.external_constants import OutputLanguage

from .._paths import REPO_ROOT, UTF_8
from .terminology._sweep import SweepResult
from .terminology.unified_record import SearchRecord, derive_display_class, to_search_record

if TYPE_CHECKING:
    from pagefind.index import PagefindIndex

logger = logging.getLogger(__name__)

_UTF_8: Final[str] = UTF_8

InjectCallback = Callable[["PagefindIndex"], Awaitable[None]]

#: The committed relevance-weights file (the build-time RAG sweep's output).
#: Optional: present-boosts, absent-uses-base-weights. Re-read every build so
#: it auto-applies the moment the sweep lands the file.
_RELEVANCE_RELPATH = Path("dev") / "docs" / "terminology" / "relevance" / "relevance.json"

#: Pagefind meta / filter / sort values are strings; the weight is rendered to
#: a fixed-width zero-padded integer string so Pagefind's lexical sort orders
#: records by descending relevance (higher weight -> larger sort key).
_SORT_SCALE = 1_000_000


class SearchInjectionError(RuntimeError):
    """Raised when committed search inputs cannot prove a full corpus."""


@dataclass(frozen=True)
class InjectionStats:
    """Counts from a record-injection run, per kind and per language."""

    concepts: int = 0
    casillas: int = 0
    legal_provisions: int = 0
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
    legal_provisions: int = 0
    cli_commands: int = 0
    cli_options: int = 0
    cli_skipped_reason: str | None = None


@dataclass(frozen=True)
class SearchRecordProjection:
    """The complete unified record projection consumed by Pagefind injection.

    Rung 2 uses this same record set for its manifest.  Exposing the projection
    as a read-only value object prevents a second build-time enumeration from
    inventing a different result identity or destination authority.
    """

    records: tuple[SearchRecord, ...]
    concepts: int
    casillas: int
    legal_provisions: int
    cli_commands: int
    cli_options: int
    cli_skipped_reason: str | None = None


def load_relevance_weights(repo_root: Path) -> dict[str, float]:
    """Load the committed sweep's per-record relevance boost map, or empty.

    The committed file is the build-time RAG sweep's :class:`SweepResult`
    (``mappings[].targets[]``, each carrying a ``record_id`` and a normalised
    ``ranking_weight``) -- the exact shape ``dev.docs.terminology.sweep``
    writes and ``test_relevance_data`` validates. A record id that several
    query terms resolved to keeps its STRONGEST weight (the best term that
    surfaced it). An absent file yields an empty map and the injection uses
    base weights only. A present but unparseable file raises
    :class:`SearchInjectionError`, so a build cannot silently publish an index
    with an unreviewed relevance input.

    Args:
        repo_root: Repository root holding the relevance file.

    Returns:
        A ``record-id -> weight`` mapping in ``[0, 1]`` (possibly empty).
    """
    path = repo_root / _RELEVANCE_RELPATH
    if not path.is_file():
        return {}
    try:
        result = SweepResult.model_validate_json(path.read_text(encoding=_UTF_8))
    except (OSError, UnicodeDecodeError, ValidationError) as exc:
        logger.error("relevance file present but not a valid sweep result: %s (%s)", path, exc)
        raise SearchInjectionError(f"committed relevance file is invalid: {path}") from exc
    weights: dict[str, float] = {}
    for mapping in result.mappings:
        for target in mapping.targets:
            clamped = min(1.0, max(0.0, target.ranking_weight))
            if clamped > weights.get(target.record_id, -1.0):
                weights[target.record_id] = clamped
    return weights


def _materialise_records(repo_root: Path | None = None) -> _Materialised:
    """Project and funnel every record kind into unified search records.

    Concepts and casillas are the priority surfaces and always project. The CLI
    projection runs the live-command-tree subprocess walk; if it fails (a
    transiently broken CLI), it is skipped-and-reported in this projection so
    diagnostic and manifest callers can see the omission. The authoritative
    Pagefind injector rejects that report before writing, rather than shipping
    concepts + casillas + legal provisions as a narrowed corpus. Legal records
    are loaded from the registry-backed generated legal-reference surface and
    fail closed when that authored catalogue cannot produce a safe destination.
    """
    from .terminology._concept_cards import project_concept_cards
    from .terminology._legal_projection import project_legal_search_records
    from .terminology.casilla_projection import project_casilla_search_records

    out = _Materialised()
    root = repo_root if repo_root is not None else REPO_ROOT

    # Inject APPROVED concept cards only. A draft concept is scaffold-empty
    # (placeholder short_description) and absent from the approved-only
    # generated glossary, so its ``#term-<id>`` deep link is dead --
    # surfacing it as a first-class palette result ships a placeholder card that
    # 404s. Drafts re-enter the corpus automatically once curated to approved.
    concept_cards, _ = project_concept_cards()
    approved_cards = [card for card in concept_cards if card.is_approved]
    out.concepts = len(approved_cards)
    out.records.extend(to_search_record(card) for card in approved_cards)

    casilla_records, _ = project_casilla_search_records()
    out.casillas = len(casilla_records)
    out.records.extend(to_search_record(rec) for rec in casilla_records)

    legal_records = project_legal_search_records(root)
    if not legal_records:
        raise SearchInjectionError("cannot inject the decided search corpus because the legal projection is empty")
    out.legal_provisions = len(legal_records)
    out.records.extend(to_search_record(rec) for rec in legal_records)

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


def materialise_search_records(repo_root: Path | None = None) -> SearchRecordProjection:
    """Return the exact unified records used by the Pagefind injector.

    This is a read-only build-time seam for artifact compilers.  It deliberately
    preserves the CLI projection outcome so a caller can refuse a partial
    manifest rather than silently compiling a bundle from a narrowed corpus.
    """
    materialised = _materialise_records(repo_root)
    return SearchRecordProjection(
        records=tuple(materialised.records),
        concepts=materialised.concepts,
        casillas=materialised.casillas,
        legal_provisions=materialised.legal_provisions,
        cli_commands=materialised.cli_commands,
        cli_options=materialised.cli_options,
        cli_skipped_reason=materialised.cli_skipped_reason,
    )


def _require_complete_projection(materialised: _Materialised) -> None:
    """Reject an incomplete authoritative projection before Pagefind writes."""
    if materialised.casillas == 0:
        raise SearchInjectionError("cannot inject an incomplete search corpus because the casilla projection is empty")
    if materialised.cli_skipped_reason is not None:
        raise SearchInjectionError(
            "cannot inject an incomplete search corpus because the CLI projection "
            f"was skipped: {materialised.cli_skipped_reason}"
        )


def _effective_weight(record: SearchRecord, relevance: dict[str, float]) -> float:
    """Return the record's ranking weight, boosted by relevance when present.

    The boost orders records WITHIN their display class and is contained in
    that class's band, so a record that topped one query can no longer outrank
    the classes above it for every query. A record the relevance file does not
    name keeps the weight the funnel gave it.
    """
    from .terminology.unified_record import contain_boost_in_band, derive_display_class

    boost = relevance.get(record.id)
    if boost is None:
        return record.ranking_weight
    return contain_boost_in_band(derive_display_class(record), boost)


def _sort_key(weight: float) -> str:
    """Render a weight to a zero-padded integer string for Pagefind sort."""
    return f"{round(weight * _SORT_SCALE):08d}"


#: The injection language when a caller names none: the English root's own
#: language. Every localized root passes its OWN build language instead (see
#: :func:`build_record_injector`), because Pagefind loads only the index
#: matching the reader's page language.
_DEFAULT_INJECTION_LANGUAGE = OutputLanguage.EN


def _content_for(record: SearchRecord) -> str:
    """Build the searchable content: title + aliases + every description.

    Combining the title, every declared term alias (the English "pro rata",
    the Catalan/Hungarian forms, unaccented variants), and all four language
    descriptions makes the record findable by any declared surface form from
    the single loaded index - the cross-lingual matching the four declared
    translations were meant to deliver.
    """
    parts = [record.title, *record.search_aliases, *record.descriptions.values()]
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.add(part)
            unique.append(part)
    return "\n".join(unique)


#: Cap for the clean one-line card summary. The palette shows this in place of
#: Pagefind's auto-excerpt, which for an injected record would otherwise be a
#: cross-lingual token blob (title + every alias + all four descriptions).
_SUMMARY_MAX_CHARS: Final[int] = 160


def _summary_for(record: SearchRecord, language: OutputLanguage = _DEFAULT_INJECTION_LANGUAGE) -> str:
    """A clean single-language one-line summary for the card display.

    Prefers the description in the ROOT's own language, so a reader on the
    Spanish root reads a Spanish card; falls back to English, then to the
    always-present Spanish text, when the record carries no section for the
    root language. Whitespace is collapsed and the result is truncated so the
    palette never renders the multilingual search blob.
    """
    text = record.descriptions.get(language) or record.descriptions.get(OutputLanguage.EN) or record.description_es
    collapsed = " ".join(text.split())
    if len(collapsed) > _SUMMARY_MAX_CHARS:
        collapsed = collapsed[: _SUMMARY_MAX_CHARS - 1].rstrip() + "…"
    return collapsed


def _meta_for(
    record: SearchRecord,
    weight: float,
    language: OutputLanguage = _DEFAULT_INJECTION_LANGUAGE,
) -> dict[str, str]:
    """Build the typed Pagefind meta map for the palette term card."""
    meta: dict[str, str] = {
        # An opaque record identity, kept explicit in Pagefind metadata so that
        # results deduplicate on the same identity whichever pass surfaced
        # them; neither the browser nor this seam derives a URL from it. A
        # semantic tier would hydrate the id from its own authoritative
        # manifest, but no such tier exists in this tree today.
        "record_id": record.id,
        "kind": record.kind.value,
        "tier": record.tier.value,
        # The closed display class the JS renderer reads verbatim for the
        # result icon and class-scoped style. Derived once here at the
        # injection seam -- the single derivation authority -- and shipped as a
        # display/crumb axis, never re-derived heuristically in the renderer.
        "display_class": derive_display_class(record).value,
        "title": record.title,
        "summary": _summary_for(record, language),
        "weight": f"{weight:.6f}",
    }
    md = record.metadata
    if md.concept_id:
        meta["concept_id"] = md.concept_id
    if md.domain:
        meta["domain"] = md.domain
    if md.modelo:
        meta["modelo"] = md.modelo
    if record.kind.value == "casilla" and md.casilla_id:
        meta["casilla_id"] = md.casilla_id
    if md.number:
        meta["number"] = md.number
    if md.segmento:
        # The casilla card crumb: a segmented modelo (M200 ``DP200014:00562``)
        # shows its segmento beside the modelo/number so the operator can tell
        # sibling casillas apart at a glance. Grounding (legal/source refs) stays
        # off the index meta and renders at the destination (D6).
        meta["segmento"] = md.segmento
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
    language: OutputLanguage = _DEFAULT_INJECTION_LANGUAGE,
) -> InjectionStats:
    written = 0
    boosts = 0
    languages: set[str] = set()
    for record in materialised.records:
        weight = _effective_weight(record, relevance)
        if record.id in relevance:
            boosts += 1
        meta = _meta_for(record, weight, language)
        filters = _filters_for(record)
        sort = {"weight": _sort_key(weight)}
        # Inject once, into the index this ROOT's pages are indexed under -- the
        # only index the reader's palette loads -- with content carrying every
        # language's description, so the record is reachable from this root's
        # pages and still matchable by the Spanish term and the other-language
        # forms.
        content = _content_for(record)
        if not content:
            continue
        await index.add_custom_record(
            url=record.target,
            content=content,
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
        legal_provisions=materialised.legal_provisions,
        cli_commands=materialised.cli_commands,
        cli_options=materialised.cli_options,
        custom_records_written=written,
        languages=tuple(sorted(languages)),
        cli_skipped_reason=materialised.cli_skipped_reason,
        relevance_boosts_applied=boosts,
    )


def _bounded_to_sample(materialised: _Materialised, sample_per_kind: int) -> _Materialised:
    """Return the materialised records capped at ``sample_per_kind`` per kind.

    The records kept are real projections — real targets, meta, filters, and
    weights — so a caller working over the bound still exercises the production
    record shape; only the row count shrinks. The per-kind counters are recut to
    what is actually carried, so the stats never over-report the injection.
    """
    kept: list[SearchRecord] = []
    seen: dict[str, int] = {}
    for record in materialised.records:
        kind = record.kind.value
        if seen.get(kind, 0) >= sample_per_kind:
            continue
        seen[kind] = seen.get(kind, 0) + 1
        kept.append(record)
    return _Materialised(
        records=kept,
        concepts=min(materialised.concepts, sample_per_kind),
        casillas=min(materialised.casillas, sample_per_kind),
        legal_provisions=min(materialised.legal_provisions, sample_per_kind),
        cli_commands=min(materialised.cli_commands, sample_per_kind),
        cli_options=min(materialised.cli_options, sample_per_kind),
        cli_skipped_reason=materialised.cli_skipped_reason,
    )


def build_record_injector(
    repo_root: Path,
    *,
    language: OutputLanguage = _DEFAULT_INJECTION_LANGUAGE,
    on_complete: Callable[[InjectionStats], None] | None = None,
    sample_per_kind: int | None = None,
) -> InjectCallback:
    """Return the injection callback for the post-build index pass.

    The callback materialises every unified search record, applies the
    committed relevance boost when present, and injects each record ONCE into
    the ``language`` index -- the one index this root's palette loads.

    Args:
        repo_root: Repository root (for the relevance file).
        language: The language of the root being built, which is the index the
            records are injected into. Pagefind's reader auto-loads only the
            index matching the page's own language, so a localized root whose
            records landed in another language's split would ship rendered
            prose alone: its palette would never fetch the record index at all.
            The caller resolves this from the build language rather than
            defaulting it, so English and localized roots carry the same
            record corpus in the index each one actually loads.
        on_complete: Optional sink for the :class:`InjectionStats` (a caller
            that wants the counts, since the seam itself returns no value).
        sample_per_kind: Optional cap on records injected per record kind.
            Production leaves this ``None`` and injects everything. The
            deployment-parity gate bounds it, because writing the full corpus
            costs about fifteen minutes while the property it checks — that
            every decided kind reaches the shipped index — is settled by a
            handful of real records per kind. The projections, the injection
            path, and the written artefact stay real; only the row count is
            bounded, and the row count is not what that gate asserts.

    Returns:
        An async callback suitable for ``build_search_index(..., inject=...)``.
    """

    async def _inject(index: PagefindIndex) -> None:
        materialised = _materialise_records(repo_root)
        _require_complete_projection(materialised)
        relevance = load_relevance_weights(repo_root)
        if sample_per_kind is not None:
            materialised = _bounded_to_sample(materialised, sample_per_kind)
        stats = await _inject_records(index, materialised, relevance, language)
        if on_complete is not None:
            on_complete(stats)

    return _inject
