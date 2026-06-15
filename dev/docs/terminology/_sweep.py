"""Query-vocabulary RAG sweep runner -- the build-time compilation oracle (ADR D6).

ADR D6's load-bearing insight: a CLOSED query vocabulary makes runtime RAG
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

Laundering rule (ADR D6 / the shipped-search licence-clean discipline): the
shipped mapping carries ONLY identifiers, targets, and normalised ranking
weights -- never stored vectors, never sparse / SPLADE term-weight maps, never
the raw retrieval score. The wrangled targets already carry only ids, targets,
and weights; this module projects them into the laundered
:class:`TermTargetRef` and never serialises the raw hit path or score.

Scope: this module is the RUNNER plus the typed mapping plus the cadence verb.
Serialising the mapping to committed data files and its drift / laundering /
licence gates is the sibling landing step; this module leaves a clean seam --
:class:`SweepResult` is strict, frozen, and JSON-serialisable, so the sibling
step serialises it with one ``model_dump_json`` call.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from aeat.core.external_constants import OutputLanguage

from ..terminology_handbook import TerminologyHandbook, load_terminology_handbook
from ..terminology_handbook._enums import TermStatus
from ._resolution import ChunkHit, GroundingSurface, TargetResolver, resolve_chunk_hits
from ._search_record import SearchRecordKind
from ._wrangle import STRONG_SIGNAL_SCORE_FLOOR, WrangledResult, wrangle

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

#: Per-query result ceiling. Raised to 20 per the locale-crowding guidance: the
#: parallel es/en/ca/hu source files return four near-identical hits per
#: concept, so a low ceiling starves the real targets; the wrangling layer
#: collapses the quadruplets afterwards.
DEFAULT_MAX_RESULTS = 20

#: Default per-query RAG timeout (seconds). The RAG-discipline mandate requires
#: an explicit timeout on every search to avoid the model-warmup/first-query
#: abort; the resident service can be busy behind a peer index-rebuild, so the
#: default is generous.
DEFAULT_SEARCH_TIMEOUT_S = 60.0


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
    on. This is the laundering boundary the licence-clean shipping rule mandates.
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
) -> tuple[SweepQuery, ...]:
    """Enumerate the closed query vocabulary from the Handbook concepts.

    For every concept (or the ``concept_ids`` subset), emits one
    :class:`SweepQuery` per distinct term label across all four language
    sections (preferred + admitted) plus every hidden search form. Identical
    query strings within one concept collapse (the es/ca preferred label is
    often the same word); the concept association is kept on each query.

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
    for concept in resolved.concepts:
        if wanted is not None and concept.concept_id not in wanted:
            continue
        for section in concept.languages:
            for term in section.terms:
                if term.term_status not in _SHIPPED_TERM_STATUSES:
                    continue
                _add_query(queries, concept.concept_id, term.label, section.language, is_hidden=False)
                for form in term.hidden_search_forms:
                    _add_query(queries, concept.concept_id, form, section.language, is_hidden=True)
    return tuple(queries[key] for key in sorted(queries))


def _add_query(
    queries: dict[tuple[str, str], SweepQuery],
    concept_id: str,
    label: str,
    language: OutputLanguage,
    *,
    is_hidden: bool,
) -> None:
    normalised = label.strip()
    if not normalised:
        return
    key = (concept_id, normalised.casefold())
    if key in queries:
        return
    queries[key] = SweepQuery(
        query=normalised,
        concept_id=concept_id,
        language=language,
        is_hidden_form=is_hidden,
    )


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

    Per the RAG-discovery mandate: route through the running service, pass an
    explicit timeout on every search, raise max-results for locale crowding. The
    single-writer Qdrant store means a competing in-process index would strand
    on the lock, so retrieval always delegates to the service.
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
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=self._timeout_s + 30.0,
            check=False,
        )
        if result.returncode != 0:
            raise SweepError(f"RAG search for {query!r} failed (exit {result.returncode}): {result.stderr.strip()}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SweepError(f"RAG search for {query!r} returned non-JSON: {exc}") from exc
        if not payload.get("ok"):
            raise SweepError(f"RAG search for {query!r} not ok: {payload.get('message', payload.get('error'))}")
        return _parse_hits(payload)


def _parse_hits(payload: object) -> tuple[ChunkHit, ...]:
    """Parse the service JSON envelope into typed chunk hits."""
    if not isinstance(payload, dict):
        return ()
    data = payload.get("data")
    if not isinstance(data, dict):
        return ()
    results = data.get("results")
    if not isinstance(results, list):
        return ()
    hits: list[ChunkHit] = []
    for row in results:
        if not isinstance(row, dict):
            continue
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

    from dev.docs.preprocess._reindex import ReindexError, run_incremental_reindex

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
    resolver: TargetResolver | None = None,
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
        resolver: A pre-built resolver (reused across queries to avoid
            re-projecting the casilla / concept indices per query).
        max_results: Per-query RAG result ceiling.
        score_floor: The wrangling strong-signal floor.
        port: Service port for the reindex step.
        reindex: When False, skip the reindex (the test path, which uses a
            recorded client and must not touch the live service).

    Returns:
        The :class:`SweepResult` -- one mapping per query, plus run provenance.
    """
    queries = enumerate_query_vocabulary(handbook, concept_ids=concept_ids)
    target_resolver = resolver if resolver is not None else TargetResolver()

    if reindex:
        root = repo_root if repo_root is not None else _default_repo_root()
        reindex_note = _reindex_before_sweep(root, port=port)
    else:
        reindex_note = "reindex skipped (caller-supplied client; index used as-is)"

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
        mappings.append(_mapping_from(query, wrangled, resolver=target_resolver))

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
) -> TermRelevanceMapping:
    targets = tuple(
        TermTargetRef(
            record_id=target.record.id,
            target=target.record.target,
            kind=target.record.kind,
            surface=target.surface.value,
            ranking_weight=target.record.ranking_weight,
        )
        for target in wrangled.targets
    )
    targets = _seed_concept_card(query, targets, resolver)
    dominant = wrangled.clusters[0] if wrangled.clusters else None
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


def _seed_concept_card(
    query: SweepQuery,
    targets: tuple[TermTargetRef, ...],
    resolver: TargetResolver,
) -> tuple[TermTargetRef, ...]:
    """Guarantee the query's originating concept card heads the target list.

    A swept query string is, by construction, a declared label of its concept
    (ADR D4: concepts are first-class palette results). RAG retrieval over a
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
    if record is None or any(ref.record_id == record.id for ref in targets):
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
    from aeat.core.config import PROJECT_ROOT

    return PROJECT_ROOT
