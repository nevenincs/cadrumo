"""Query-vocabulary RAG sweep runner -- the build-time compilation oracle.

The load-bearing insight: a CLOSED query vocabulary makes runtime RAG
unnecessary. Every query a term card can answer is enumerable at build time --
each enrolled concept's preferred/admitted terms, its four-language
translations, and its hidden search forms -- so the expensive half of RAG
(embedding + hybrid retrieval) runs ONCE here, on the GPU dev box, and ships as
plain ranked data. This is what makes the offline palette "semantic" without
shipping a model.

The runner composes the pipeline already built:

  enumerate vocabulary (Handbook concepts)
    -> reindex-before-sweep (the mandated pre-sweep step)
    -> per query term: RAG retrieval -> resolve_chunk_hits -> wrangle
    -> a laundered term-to-target relevance mapping.

Laundering rule: the shipped mapping carries ONLY identifiers, targets, and
normalised ranking weights -- never stored vectors, never sparse / SPLADE
term-weight maps, never the raw retrieval score. The wrangled targets already
carry only ids, targets, and weights; this module projects them into the
laundered :class:`TermTargetRef` and never serialises the raw hit path or
score.

Scope: this module is the RUNNER plus the typed mapping plus the cadence verb.
Serialising the mapping to committed data files, and its drift / laundering /
licence gates, happen elsewhere; this module leaves a clean seam --
:class:`SweepResult` is strict, frozen, and JSON-serialisable, so that later
serialisation is one ``model_dump_json`` call.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.external_constants import OutputLanguage

from ..._paths import REPO_ROOT
from ..terminology_handbook.enums import TermStatus
from ..terminology_handbook.loader import TerminologyHandbook, load_terminology_handbook
from ._query_aliases import QueryAliasAuthority, load_query_alias_authority, validate_query_alias_authority
from ._resolution import ChunkHit, GroundingSurface, TargetResolver, resolve_chunk_hits
from ._wrangle import STRONG_SIGNAL_SCORE_FLOOR, WrangledResult, read_clusters, wrangle
from .search_record import SearchRecordKind
from .unified_record import SearchRecord

if TYPE_CHECKING:
    from ..pagefind_inject import SearchRecordProjection

# Dev tooling runs from a source checkout by definition, so it owns its own
# repo-root anchor. Production code has no repository concept and must never
# export one (see cadrumo.core.config_state_root for the runtime data root).
_REPO_ROOT = REPO_ROOT

__all__ = [
    "RagSearchClient",
    "ServiceRagSearchClient",
    "SweepError",
    "SweepQuery",
    "SweepResult",
    "TermRelevanceMapping",
    "TermTargetRef",
    "enumerate_query_vocabulary",
    "run_sweep",
]

_SHIPPED_TERM_STATUSES: frozenset[TermStatus] = frozenset({TermStatus.PREFERRED, TermStatus.ADMITTED})

#: Per-query result ceiling, raised to 20: the parallel es/en/ca/hu source
#: files return four near-identical hits per concept, so a low ceiling starves
#: the real targets; the wrangling layer collapses the quadruplets afterwards.
DEFAULT_MAX_RESULTS = 20

#: Default per-query RAG timeout (seconds). An explicit timeout is required on
#: every search to avoid the model-warmup/first-query abort; the resident
#: service can be busy behind a concurrent index rebuild, so the default is
#: generous.
DEFAULT_SEARCH_TIMEOUT_S = 60.0


class _StructuredCasillaQuery(NamedTuple):
    """The normalized parts of a structured Modelo/casilla query."""

    modelo: str
    casilla_id: str
    number: str
    segmento: str | None


_STRUCTURED_CASILLA_QUERY_RE = re.compile(
    r"^(?:modelo|model|form)\s+([0-9]+)\s+(?:casilla|casella|box|field)\s+"
    r"([a-z0-9][a-z0-9._:-]*)$",
    re.ASCII,
)


class SweepError(RuntimeError):
    """Raised when the sweep cannot run (e.g. the RAG service is unreachable)."""


class SweepQuery(BaseModel):
    """One enumerated query string and its concept association.

    ``query`` is the surface term swept through RAG; ``concept_id`` ties a hit
    back to the concept it came from; ``language`` and ``is_hidden_form`` record
    where the query string was authored (a translation, a synonym, an unaccented
    search form) so the mapping is auditable.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    query: str = Field(min_length=1, max_length=160)
    concept_id: str = Field(min_length=2, max_length=64)
    language: OutputLanguage
    is_hidden_form: bool = False


class TermTargetRef(BaseModel):
    """A laundered term-to-target reference (ids + target + weight ONLY).

    The shipped relevance unit: no vectors, no sparse / SPLADE term weights, no
    raw retrieval score, no source path. Just the resolved record's id, its deep
    link target, its kind, and the normalised ranking weight a consumer sorts
    on. This is the laundering boundary for what ships.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record_id: str = Field(min_length=1, max_length=320)
    target: str = Field(min_length=1, max_length=512)
    kind: SearchRecordKind
    surface: str = Field(min_length=1, max_length=32)
    ranking_weight: float = Field(ge=0.0, le=1.0)


class TermRelevanceMapping(BaseModel):
    """The ranked targets one query term resolved to, plus an audit summary.

    ``targets`` is the laundered ranked list (highest weight first). The audit
    is COUNTS only (``dropped`` / ``collapsed``) -- the per-hit drop/collapse
    detail stays in the build log, not the shipped mapping, so no path or score
    leaks. ``cluster_locator`` is the dominant directory cluster (a thin-signal
    tie-break hint), itself an identifier, not a vector.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    query: str = Field(min_length=1, max_length=160)
    concept_id: str = Field(min_length=2, max_length=64)
    language: OutputLanguage
    targets: tuple[TermTargetRef, ...] = Field(default=())
    dropped_count: int = Field(default=0, ge=0)
    collapsed_count: int = Field(default=0, ge=0)
    dominant_cluster: str | None = Field(default=None, min_length=1, max_length=272)


class SweepResult(BaseModel):
    """The full sweep output: one mapping per query term, plus run provenance.

    Strict, frozen, and JSON-serialisable so the sibling landing step
    serialises it to the committed relevance data file with one
    ``model_dump_json`` call -- the clean seam.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    mappings: tuple[TermRelevanceMapping, ...] = Field(default=())
    query_count: int = Field(ge=0)
    concept_count: int = Field(ge=0)
    #: How many queries failed retrieval (transient service errors) and were
    #: recorded as honest empty mappings. A non-zero count marks a degraded run.
    failed_query_count: int = Field(default=0, ge=0)
    #: The reindex-before-sweep outcome (the job-queued acknowledgement or a
    #: note that the index was used as-is because the service was busy).
    reindex_note: str = Field(min_length=1, max_length=1000)
    score_floor: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Vocabulary enumeration
# ---------------------------------------------------------------------------


def enumerate_query_vocabulary(
    handbook: TerminologyHandbook | None = None,
    *,
    concept_ids: Iterable[str] | None = None,
    query_alias_authority: QueryAliasAuthority | None = None,
) -> tuple[SweepQuery, ...]:
    """Enumerate the closed query vocabulary from the Handbook concepts.

    For every concept (or the ``concept_ids`` subset), emits one
    :class:`SweepQuery` per distinct term label across all four language
    sections (preferred + admitted) plus every hidden search form. Identical
    query strings within one concept collapse (the es/ca preferred label is
    often the same word); the concept association is kept on each query.

    That collapse keys on ``(concept_id, casefolded query)``, which is coarser
    than the ``(concept_id, language, query)`` row the alias authority is
    validated against: one surviving key stands for every language that
    authored the same string. The declared rows are therefore accumulated
    alongside the collapsed vocabulary and handed to that validation, so a
    canonical query is never invisible to it merely because a sibling language
    authored the same word first.

    Args:
        handbook: The compiled Handbook; defaults to the bundled load.
        concept_ids: Optional subset of concept ids to sweep (the test path
            sweeps a small subset; the full run sweeps all).

    Returns:
        The deduplicated query vocabulary, sorted by ``(concept_id, query)``.
    """
    resolved = handbook if handbook is not None else load_terminology_handbook()
    wanted = set(concept_ids) if concept_ids is not None else None

    queries: dict[tuple[str, str], SweepQuery] = {}
    declared: set[tuple[str, OutputLanguage, str]] = set()
    for concept in resolved.concepts:
        if wanted is not None and concept.concept_id not in wanted:
            continue
        # Only APPROVED concepts reach the shipped search surface (the glossary
        # and the Pagefind injection gate on approved), so only their terms are
        # the closed query vocabulary; a deprecated/draft concept's terms must
        # not be swept into the relevance mapping (they would target a card that
        # is never injected -- a dead entry).
        if concept.lifecycle is not ConceptLifecycle.APPROVED:
            continue
        for section in concept.languages:
            for term in section.terms:
                if term.term_status not in _SHIPPED_TERM_STATUSES:
                    continue
                row = _add_query(queries, concept.concept_id, term.label, section.language, is_hidden=False)
                if row is not None:
                    declared.add(row)
                for form in term.hidden_search_forms:
                    row = _add_query(queries, concept.concept_id, form, section.language, is_hidden=True)
                    if row is not None:
                        declared.add(row)

    authority = query_alias_authority if query_alias_authority is not None else load_query_alias_authority()
    authority_for_validation = authority
    if wanted is not None:
        # A concept-scoped sweep is a legitimate test/diagnostic boundary.  A
        # global authority entry must not be validated against the deliberately
        # smaller canonical-query set, otherwise an unrelated alias makes the
        # subset fail before its own entries are selected below.
        authority_for_validation = authority.model_copy(
            update={"entries": tuple(entry for entry in authority.entries if entry.concept_id in wanted)}
        )
    validate_query_alias_authority(
        authority_for_validation,
        handbook=resolved,
        canonical_queries=declared,
    )
    for entry in authority.entries:
        if wanted is not None and entry.concept_id not in wanted:
            continue
        _add_query(queries, entry.concept_id, entry.query, entry.language, is_hidden=True)
    return tuple(queries[key] for key in sorted(queries))


def _add_query(
    queries: dict[tuple[str, str], SweepQuery],
    concept_id: str,
    label: str,
    language: OutputLanguage,
    *,
    is_hidden: bool,
) -> tuple[str, OutputLanguage, str] | None:
    """Record one authored query row, collapsing repeats of the same string.

    Returns the ``(concept_id, language, query)`` row this label declares --
    whether or not it survived the collapse -- so a caller needing the declared
    rows never has to read them off the collapsed survivors, whose key does not
    carry the language. ``None`` means a blank label, which declares nothing.
    """
    normalised = label.strip()
    if not normalised:
        return None
    declared = (concept_id, language, normalised)
    key = (concept_id, normalised.casefold())
    if key in queries:
        return declared
    queries[key] = SweepQuery(
        query=normalised,
        concept_id=concept_id,
        language=language,
        is_hidden_form=is_hidden,
    )
    return declared


# ---------------------------------------------------------------------------
# RAG retrieval client
# ---------------------------------------------------------------------------


class RagSearchClient(Protocol):
    """The retrieval seam: maps a query string to raw chunk hits.

    A protocol so the sweep is testable with a recorded-fixture client and runs
    live against the resident service in production -- the END-TO-END path uses
    the real :class:`ServiceRagSearchClient`, the protocol only exists so a
    deterministic test can replay a captured response without a mock framework.
    """

    def search(self, query: str, *, max_results: int) -> tuple[ChunkHit, ...]:
        """Return the raw chunk hits for ``query`` (path + line range + score)."""
        ...


class ServiceRagSearchClient:
    """Routes every query through the resident vaultspec-rag service (port 8766).

    Routes through the running service, passes an explicit timeout on every
    search, and raises max-results for locale crowding. The single-writer
    Qdrant store means a competing in-process index would strand on the lock,
    so retrieval always delegates to the service.
    """

    def __init__(
        self,
        *,
        port: int = 8766,
        timeout_s: float = DEFAULT_SEARCH_TIMEOUT_S,
    ) -> None:
        self._port = port
        self._timeout_s = timeout_s

    def search(self, query: str, *, max_results: int) -> tuple[ChunkHit, ...]:
        """Run one code search through the service and parse the chunk hits.

        Raises:
            SweepError: The service search failed (unreachable / timed out).
        """
        import json
        import subprocess

        cmd = [
            "uv",
            "run",
            "--no-sync",
            "vaultspec-rag",
            "search",
            query,
            "--type",
            "code",
            "--port",
            str(self._port),
            "--max-results",
            str(max_results),
            "--timeout",
            str(int(self._timeout_s)),
            "--json",
        ]
        # Fixed literal argv (no shell); the variable parts are the query string
        # and integer flags. The query is operator vocabulary, not untrusted
        # input, and is passed as a single argv element (never interpolated into
        # a shell), hence the S603 suppression.
        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_s + 30.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SweepError(f"RAG search for {query!r} could not run: {exc}") from exc
        if result.returncode != 0:
            raise SweepError(f"RAG search for {query!r} failed (exit {result.returncode}): {result.stderr.strip()}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SweepError(f"RAG search for {query!r} returned non-JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise SweepError(f"RAG search for {query!r} returned a non-object JSON envelope")
        payload = cast(dict[str, object], payload)
        if not payload.get("ok"):
            raise SweepError(f"RAG search for {query!r} not ok: {payload.get('message', payload.get('error'))}")
        return _parse_hits(payload)


def _parse_hits(payload: object) -> tuple[ChunkHit, ...]:
    """Parse the service JSON envelope into typed chunk hits."""
    if not isinstance(payload, dict):
        return ()
    payload = cast(dict[str, object], payload)
    data = payload.get("data")
    if not isinstance(data, dict):
        return ()
    data = cast(dict[str, object], data)
    results = data.get("results")
    if not isinstance(results, list):
        return ()
    results = cast(list[object], results)
    hits: list[ChunkHit] = []
    for raw_row in results:
        if not isinstance(raw_row, dict):
            continue
        row = cast(dict[str, object], raw_row)
        path = row.get("path")
        if not isinstance(path, str) or not path:
            continue
        hits.append(
            ChunkHit(
                path=path,
                line_start=max(0, _as_int(row.get("line_start"))),
                line_end=max(0, _as_int(row.get("line_end"))),
                score=min(1.0, max(0.0, _as_float(row.get("score")))),
            ),
        )
    return tuple(hits)


def _as_int(value: object) -> int:
    """Coerce a JSON value to a non-negative int, defaulting to 0."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _as_float(value: object) -> float:
    """Coerce a JSON value to a float in the score range, defaulting to 0.0."""
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


# ---------------------------------------------------------------------------
# Reindex-before-sweep (robust to a busy service)
# ---------------------------------------------------------------------------


def _reindex_before_sweep(repo_root: Path, *, port: int) -> str:
    """Run the mandated pre-sweep reindex, tolerating a busy single-writer store.

    Calls the established ``run_incremental_reindex`` so the index reflects the
    committed sidecars. The resident store is single-writer: a long peer
    index-rebuild can hold the lock, so the reindex job QUEUES behind it. That
    is not a failure -- the already-indexed sidecars are queryable now -- so a
    reindex error is downgraded to a note and the sweep proceeds against the
    current index state rather than hanging on a queued rebuild.
    """
    import subprocess

    from ..preprocess._reindex import ReindexError, run_incremental_reindex

    try:
        stdout = run_incremental_reindex(repo_root, port=port, timeout_s=120.0)
    except ReindexError as exc:
        return f"reindex not confirmed (service busy / queued); swept against current index: {exc}"
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover - environment-dependent
        return f"reindex skipped (service unavailable); swept against current index: {exc}"
    return f"reindex queued/accepted: {stdout.strip()[:200]}"


# ---------------------------------------------------------------------------
# The sweep runner
# ---------------------------------------------------------------------------


def run_sweep(
    *,
    client: RagSearchClient,
    repo_root: Path | None = None,
    handbook: TerminologyHandbook | None = None,
    concept_ids: Iterable[str] | None = None,
    query_alias_authority: QueryAliasAuthority | None = None,
    resolver: TargetResolver | None = None,
    search_record_projection: SearchRecordProjection | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    score_floor: float = STRONG_SIGNAL_SCORE_FLOOR,
    port: int = 8766,
    reindex: bool = True,
) -> SweepResult:
    """Run the query-vocabulary sweep into a laundered relevance mapping.

    Enumerates the query vocabulary, runs the mandated reindex-before-sweep
    (tolerating a busy service), then for each query retrieves raw hits via
    ``client``, resolves them (``resolve_chunk_hits``), wrangles them
    (``wrangle``), and projects the wrangled targets into the laundered
    :class:`TermRelevanceMapping` (ids + targets + weights only).

    Args:
        client: The retrieval client (the live service in production; a
            recorded-fixture client in tests).
        repo_root: Repo root for the reindex step; defaults to the package's
            inferred project root.
        handbook: The Handbook to enumerate; defaults to the bundled load.
        concept_ids: Optional concept-id subset (the bounded test path).
        query_alias_authority: Optional explicit, validated authority for
            independently ratified aliases. When omitted, the enumerator loads
            the committed authority through its existing default boundary.
        resolver: A pre-built resolver (reused across queries to avoid
            re-projecting the casilla / concept indices per query).
        search_record_projection: The complete authoritative Pagefind/Rung-2
            record projection. When supplied, it is shared with a resolver so
            the expensive four-language CLI walk runs only once. When omitted,
            the projection is materialised once for this sweep.
        max_results: Per-query RAG result ceiling.
        score_floor: The wrangling strong-signal floor.
        port: Service port for the reindex step.
        reindex: When False, skip the reindex (the test path, which uses a
            recorded client and must not touch the live service).

    Returns:
        The :class:`SweepResult` -- one mapping per query, plus run provenance.
    """
    queries = enumerate_query_vocabulary(
        handbook,
        concept_ids=concept_ids,
        query_alias_authority=query_alias_authority,
    )
    root = repo_root if repo_root is not None else _default_repo_root()

    if reindex:
        reindex_note = _reindex_before_sweep(root, port=port)
    else:
        reindex_note = "reindex skipped (caller-supplied client; index used as-is)"

    # The resolver's CLI index and the sweep's manifest gate must consume the
    # exact same complete projection. Materialise it once and pass it through;
    # otherwise TargetResolver would independently repeat the four
    # language-pinned CLI subprocess walks before this function materialised
    # the same records for target filtering.
    from ..pagefind_inject import materialise_search_records

    projection = search_record_projection if search_record_projection is not None else materialise_search_records(root)
    target_resolver = resolver if resolver is not None else TargetResolver(search_record_projection=projection)

    # The mapping boundary may only ship ids emitted by the complete projection
    # consumed by Pagefind and Rung 2. This also rejects resolver-only synthetic
    # PAGE records (for example ``code:*``) without weakening resolution itself.
    search_records = projection.records

    mappings: list[TermRelevanceMapping] = []
    concepts_seen: set[str] = set()
    failed = 0
    for query in queries:
        concepts_seen.add(query.concept_id)
        try:
            hits = client.search(query.query, max_results=max_results)
        except SweepError:
            # A single query's retrieval failure (a transient service hiccup, a
            # query the backend rejects) must not abort the whole sweep: record
            # an honest empty mapping for it and continue. The failure count is
            # surfaced on the result so a degraded run is visible, never silent.
            failed += 1
            mappings.append(_empty_mapping(query))
            continue
        resolution = resolve_chunk_hits(hits, resolver=target_resolver)
        wrangled = wrangle(resolution, score_floor=score_floor)
        mappings.append(
            _mapping_from(
                query,
                wrangled,
                resolver=target_resolver,
                search_records=search_records,
            ),
        )

    return SweepResult(
        mappings=tuple(mappings),
        query_count=len(queries),
        concept_count=len(concepts_seen),
        failed_query_count=failed,
        reindex_note=reindex_note,
        score_floor=score_floor,
    )


def _empty_mapping(query: SweepQuery) -> TermRelevanceMapping:
    """Return an empty mapping for a query whose retrieval failed."""
    return TermRelevanceMapping(query=query.query, concept_id=query.concept_id, language=query.language)


def _mapping_from(
    query: SweepQuery,
    wrangled: WrangledResult,
    *,
    resolver: TargetResolver,
    search_records: tuple[SearchRecord, ...],
) -> TermRelevanceMapping:
    emitted_record_ids = frozenset(record.id for record in search_records)
    manifest_targets = tuple(target for target in wrangled.targets if target.record.id in emitted_record_ids)
    targets = tuple(_term_target_ref(target.record, target.surface.value) for target in manifest_targets)
    targets = _augment_structured_casilla_target(query, targets, search_records)
    targets = _seed_concept_card(query, targets, resolver, emitted_record_ids=emitted_record_ids)
    clusters = read_clusters(manifest_targets)
    dominant = clusters[0] if clusters else None
    locator = f"{dominant.surface}:{dominant.locator}" if dominant is not None else None
    return TermRelevanceMapping(
        query=query.query,
        concept_id=query.concept_id,
        language=query.language,
        targets=targets,
        dropped_count=len(wrangled.dropped),
        collapsed_count=len(wrangled.collapsed),
        dominant_cluster=locator,
    )


def _term_target_ref(record: SearchRecord, surface: str) -> TermTargetRef:
    """Launder one unified record into the shipped target shape."""
    return TermTargetRef(
        record_id=record.id,
        target=record.target,
        kind=record.kind,
        surface=surface,
        ranking_weight=record.ranking_weight,
    )


def _augment_structured_casilla_target(
    query: SweepQuery,
    targets: tuple[TermTargetRef, ...],
    search_records: tuple[SearchRecord, ...],
) -> tuple[TermTargetRef, ...]:
    """Add one exact structured casilla match at the laundering boundary.

    The match is deliberately outside RAG resolution and wrangling: the
    authoritative projection already owns the record id, target, metadata, and
    base weight. A zero or ambiguous match is refused, and an id already
    surfaced by RAG is retained exactly once.
    """
    record = _match_structured_casilla_query(query.query, search_records)
    if record is None or any(target.record_id == record.id for target in targets):
        return targets

    augmented = (*targets, _term_target_ref(record, GroundingSurface.CASILLA.value))
    return tuple(sorted(augmented, key=lambda target: (-target.ranking_weight, target.record_id)))


def _match_structured_casilla_query(
    query: str,
    records: Iterable[SearchRecord],
) -> SearchRecord | None:
    """Return the unique authoritative casilla record addressed by ``query``.

    The grammar and normalization mirror the docs search controller. Canonical
    ``(modelo, casilla_id)`` identity wins first; only when that yields no
    record is the reviewed ``(number, segmento)`` display metadata considered.
    Both paths fail closed for zero or multiple matches.
    """
    address = _parse_structured_casilla_query(query)
    if address is None:
        return None

    casillas = tuple(
        record
        for record in records
        if record.kind is SearchRecordKind.CASILLA
        and record.metadata.modelo is not None
        and _normalise_structured_value(str(record.metadata.modelo)) == address.modelo
    )
    canonical_matches = tuple(
        record
        for record in casillas
        if record.metadata.casilla_id is not None
        and _normalise_structured_text(str(record.metadata.casilla_id)) == address.casilla_id
    )
    if len(canonical_matches) == 1:
        return canonical_matches[0]
    if canonical_matches:
        return None

    display_matches = tuple(
        record
        for record in casillas
        if record.metadata.number is not None
        and _normalise_structured_value(record.metadata.number) == address.number
        and (
            address.segmento is None
            or (
                record.metadata.segmento is not None
                and _normalise_structured_value(record.metadata.segmento) == address.segmento
            )
        )
    )
    return display_matches[0] if len(display_matches) == 1 else None


def _parse_structured_casilla_query(query: str) -> _StructuredCasillaQuery | None:
    """Parse the exact structured Modelo/casilla vocabulary shared with docs JS."""
    text = _normalise_structured_text(query)
    text = re.sub(r"[^\w\s:.-]", " ", text, flags=re.ASCII)
    text = re.sub(r"\s+", " ", text).strip()
    match = _STRUCTURED_CASILLA_QUERY_RE.fullmatch(text)
    if match is None:
        return None

    casilla_id = match.group(2)
    separator = casilla_id.find(":")
    segmento = None
    number = casilla_id
    if separator >= 0:
        if separator == 0 or separator == len(casilla_id) - 1:
            return None
        segmento = _normalise_structured_value(casilla_id[:separator])
        number = casilla_id[separator + 1 :]
    return _StructuredCasillaQuery(
        modelo=_normalise_structured_value(match.group(1)),
        casilla_id=_normalise_structured_text(casilla_id),
        number=_normalise_structured_value(number),
        segmento=segmento,
    )


def _normalise_structured_text(value: str) -> str:
    """Apply the docs search controller's NFKD, accent, and case normalization."""
    decomposed = unicodedata.normalize("NFKD", value.strip())
    return "".join(character for character in decomposed if not unicodedata.combining(character)).lower()


def _normalise_structured_value(value: str) -> str:
    """Normalize a structured numeric value while preserving non-numeric ids."""
    text = _normalise_structured_text(value)
    if re.fullmatch(r"[0-9]+", text) is not None:
        return text.lstrip("0") or "0"
    return text


def _seed_concept_card(
    query: SweepQuery,
    targets: tuple[TermTargetRef, ...],
    resolver: TargetResolver,
    *,
    emitted_record_ids: frozenset[str],
) -> tuple[TermTargetRef, ...]:
    """Guarantee the query's originating concept card heads the target list.

    A swept query string is, by construction, a declared label of its concept,
    and concepts are first-class palette results. RAG retrieval over a
    generic or ambiguous surface form (the English "box", the bare "modelo
    303") may score the concept's own authoring fragment below the strong-
    signal floor or miss it entirely, but the concept card is still the
    canonical answer. Seeding it deterministically -- at the concept tier
    weight, ahead of the RAG-discovered grounding surfaces -- makes the
    compiled mapping complete without inventing a relevance signal: the card
    is enrolment fact, not a retrieval guess. A no-op when RAG already
    surfaced the card (deduped by record id) or when the concept has no
    enrolled card.
    """
    record = resolver.concept_record(query.concept_id)
    if record is None or record.id not in emitted_record_ids or any(ref.record_id == record.id for ref in targets):
        return targets
    seed = TermTargetRef(
        record_id=record.id,
        target=record.target,
        kind=record.kind,
        surface=GroundingSurface.CONCEPT.value,
        ranking_weight=record.ranking_weight,
    )
    return (seed, *targets)


def _default_repo_root() -> Path:
    return _REPO_ROOT
