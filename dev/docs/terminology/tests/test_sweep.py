"""Real-behaviour conformance for the query-vocabulary RAG sweep runner.

The sweep is the build-time compilation oracle: it enumerates the closed query
vocabulary from the Handbook concepts, runs each term through the resident RAG
service, resolves and wrangles the hits, and emits a LAUNDERED term-to-target
relevance mapping (ids + targets + weights only -- no vectors, no SPLADE, no raw
score). These gates prove the enumeration is correct, the end-to-end
RAG->resolve->wrangle pipeline produces a meaningful mapping on REAL data, and
the laundering boundary holds.

No mocks. The deterministic end-to-end test replays a response CAPTURED FROM THE
REAL service (committed as a fixture) through the real resolver + wrangler, so
the resolution / wrangling / laundering is exercised against genuine hits
without depending on live-service latency. A separate ``integration`` test runs
at least one query against the LIVE service so the real retrieval path is
covered; if the service is unreachable, the integration test fails with the
service error rather than skipping.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.external_constants import OutputLanguage

from ...pagefind_inject import SearchRecordProjection, materialise_search_records
from .._query_aliases import (
    QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION,
    QueryAliasAuthority,
    QueryAliasEntry,
)
from .._resolution import (
    ChunkHit,
    GroundingSurface,
    ResolutionResult,
    TargetResolver,
    resolve_chunk_hits,
)
from .._sweep import (
    RagSearchClient,
    SweepQuery,
    SweepResult,
    TermRelevanceMapping,
    _mapping_from,
    _match_structured_casilla_query,
    enumerate_query_vocabulary,
    run_sweep,
)
from .._wrangle import wrangle
from ..search_record import SearchRecordKind
from ..unified_record import SearchRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def _authoritative_projection() -> SearchRecordProjection:
    """Use the bundled Pagefind/Rung-2 record projection as test authority."""
    projection = materialise_search_records()
    assert projection.concepts > 0
    assert projection.casillas > 0
    assert projection.legal_provisions > 0
    assert projection.cli_commands > 0
    assert projection.cli_options > 0
    assert projection.cli_skipped_reason is None
    assert len(projection.records) == (
        projection.concepts
        + projection.casillas
        + projection.legal_provisions
        + projection.cli_commands
        + projection.cli_options
    )
    cli_languages = {
        getattr(language, "value", language)
        for record in projection.records
        if record.kind is SearchRecordKind.CLI
        for language in record.descriptions
    }
    assert cli_languages == {language.value for language in OutputLanguage}
    return projection


@pytest.fixture(scope="module")
def _authoritative_search_records(
    _authoritative_projection: SearchRecordProjection,
) -> tuple[SearchRecord, ...]:
    return _authoritative_projection.records


@pytest.fixture(scope="module")
def _authoritative_target_resolver(
    _authoritative_projection: SearchRecordProjection,
) -> TargetResolver:
    return TargetResolver(search_record_projection=_authoritative_projection)


class _RecordedClient:
    """A retrieval client that replays a captured real RAG response per query.

    Implements the :class:`RagSearchClient` protocol by returning the chunk
    hits recorded from the live service (committed fixture) -- a deterministic
    replay of genuine hits, not a fabricated/mock response. An unseen query
    returns no hits (the honest empty result).
    """

    def __init__(self, by_query: dict[str, tuple[ChunkHit, ...]]) -> None:
        self._by_query = by_query

    def search(self, query: str, *, max_results: int) -> tuple[ChunkHit, ...]:
        return self._by_query.get(query, ())[:max_results]


def _load_recorded(name: str) -> tuple[str, tuple[ChunkHit, ...]]:
    data = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    hits = tuple(
        ChunkHit(
            path=row["path"],
            line_start=row["line_start"],
            line_end=row["line_end"],
            score=row["score"],
        )
        for row in data["hits"]
    )
    return data["query"], hits


# ---------------------------------------------------------------------------
# Vocabulary enumeration
# ---------------------------------------------------------------------------


def test_enumerate_vocabulary_covers_prorrata_terms_translations_and_hidden_forms() -> None:
    """The prorrata concept's terms, translations, and hidden forms become queries.

    The closed query set for one concept is every distinct term label across the
    four language sections plus every hidden search form, each tagged with the
    concept id and the language it came from.
    """
    queries = enumerate_query_vocabulary(concept_ids={"prorrata"})
    by_text = {q.query: q for q in queries}

    # Preferred + admitted terms across languages.
    assert "prorrata" in by_text  # es preferred
    assert "regla de prorrata" in by_text  # es admitted
    assert "prorrateo" in by_text  # es admitted
    assert "pro rata" in by_text  # en preferred
    assert "deductible proportion" in by_text  # en admitted
    assert "arányosítás" in by_text  # hu admitted; arány is ratio, arany is gold
    # The hidden search form is enumerated and flagged.
    assert "prorateo" in by_text
    assert by_text["prorateo"].is_hidden_form is True
    assert by_text["prorrata"].is_hidden_form is False
    # Every query keeps its concept association.
    assert all(q.concept_id == "prorrata" for q in queries)
    # Language tagging is correct.
    assert by_text["pro rata"].language is OutputLanguage.EN
    assert by_text["arányosítás"].language is OutputLanguage.HU


def test_enumerate_vocabulary_dedupes_identical_query_strings() -> None:
    """Identical query strings within a concept collapse (es/ca share 'prorrata')."""
    queries = enumerate_query_vocabulary(concept_ids={"prorrata"})
    texts = [q.query for q in queries]
    assert len(texts) == len(set(texts)), "duplicate query strings were not deduped"


def test_enumerate_vocabulary_uses_only_shipped_term_statuses() -> None:
    """Forbidden/deprecated term rows do not own shipped query metadata."""
    queries = enumerate_query_vocabulary(concept_ids={"casilla"})
    by_text = {q.query: q for q in queries}

    assert by_text["box"].language is OutputLanguage.EN
    assert by_text["box"].concept_id == "casilla"


def test_enumerate_full_vocabulary_is_a_bounded_closed_set() -> None:
    """The full 95-concept vocabulary is a finite, deduplicated closed set."""
    queries = enumerate_query_vocabulary()
    assert queries  # non-empty
    keys = [(q.concept_id, q.query.casefold()) for q in queries]
    assert len(keys) == len(set(keys)), "duplicate (concept, query) pairs"


def test_run_sweep_uses_explicit_alias_authority_for_the_same_pipeline(
    _authoritative_projection: SearchRecordProjection,
) -> None:
    """An explicit ratified alias is enumerated and laundered by the normal sweep.

    The client replays the committed real-service fixture boundary; the alias
    itself is unseen by that fixture and therefore exercises the honest empty
    retrieval path plus deterministic originating-concept seeding. The test
    proves the authority is threaded through enumeration rather than copied
    into a separate mapping path.
    """
    authority = QueryAliasAuthority(
        schema_version=QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION,
        authority_version=2,
        entries=(
            QueryAliasEntry(
                concept_id="prorrata",
                language=OutputLanguage.EN,
                query="pro-rata",
                canonical_query="pro rata",
                status="ratified",
                review_reason="Independent spelling form reviewed for the English prorrata query surface.",
                reviewed_at=date(2026, 8, 6),
            ),
        ),
    )
    queries = enumerate_query_vocabulary(
        concept_ids={"prorrata"},
        query_alias_authority=authority,
    )
    assert any(query.query == "pro-rata" and query.is_hidden_form for query in queries)

    result = run_sweep(
        client=_RecordedClient({}),
        concept_ids={"prorrata"},
        query_alias_authority=authority,
        search_record_projection=_authoritative_projection,
        reindex=False,
    )

    alias_mapping = next(mapping for mapping in result.mappings if mapping.query == "pro-rata")
    assert alias_mapping.concept_id == "prorrata"
    assert [target.record_id for target in alias_mapping.targets] == ["concept:prorrata"]


# ---------------------------------------------------------------------------
# End-to-end on real captured data (deterministic replay)
# ---------------------------------------------------------------------------


def test_real_sweep_maps_prorrata_to_its_grounding_targets(
    _authoritative_projection: SearchRecordProjection,
    _authoritative_target_resolver: TargetResolver,
) -> None:
    """End-to-end: a real 'regla de prorrata' response maps to its grounding targets.

    Replays a response CAPTURED FROM THE LIVE service through the real
    resolver + wrangler. The mapping's targets must deep-link to the prorrata
    grounding across surfaces -- the generated legal-reference destinations
    for the BOE art-102/art-104 provisions and/or the prorrata concept card --
    proving the precompiled-RAG pipeline works on genuine data.
    """
    query, hits = _load_recorded("sweep-regla-de-prorrata.json")
    client: RagSearchClient = _RecordedClient({query: hits})
    resolver = _authoritative_target_resolver

    result = run_sweep(
        client=client,
        concept_ids={"prorrata"},
        resolver=resolver,
        search_record_projection=_authoritative_projection,
        reindex=False,
        score_floor=0.5,
    )

    mapping = next(m for m in result.mappings if m.query == query)
    assert mapping.targets, "the real prorrata sweep produced no targets"
    targets = mapping.targets

    # A legal target deep-links to the exact generated prorrata destination.
    legal_targets = [t for t in targets if t.surface == GroundingSurface.LEGAL.value]
    expected_legal_targets = {
        "_generated/legal/boe-a-1992-28740.html#legal-ley-37-1992-art-102",
        "_generated/legal/boe-a-1992-28740.html#legal-ley-37-1992-art-104",
    }
    assert any(t.target in expected_legal_targets for t in legal_targets), "no generated legal grounding target"
    assert all(t.kind is SearchRecordKind.LEGAL for t in legal_targets)

    # Check BOE provenance independently on the real resolved records. The
    # laundered TermTargetRef intentionally carries no metadata beyond its
    # five shipped fields, while the resolver's SearchRecord does.
    resolved = resolve_chunk_hits(hits, resolver=resolver)
    legal_records = {
        target.record.id: target.record for target in resolved.resolved if target.surface is GroundingSurface.LEGAL
    }
    assert legal_records, "recorded prorrata hits did not resolve to a legal record"
    for target in legal_targets:
        record = legal_records.get(target.record_id)
        assert record is not None, f"no resolved legal record for {target.record_id}"
        assert record.kind is SearchRecordKind.LEGAL
        assert record.target == target.target
        assert record.metadata.legal_permalink is not None
        assert record.metadata.legal_permalink.startswith("https://www.boe.es/")

    # A concept card target deep-links to the glossary anchor.
    concept_targets = [t for t in targets if t.kind is SearchRecordKind.CONCEPT]
    assert any("_generated/glossary.html#term-prorrata" in t.target for t in concept_targets), (
        "no prorrata concept card target"
    )

    # Targets are ranked (descending weight).
    weights = [t.ranking_weight for t in targets]
    assert weights == sorted(weights, reverse=True)


def test_sweep_mapping_is_laundered_ids_targets_weights_only(
    _authoritative_projection: SearchRecordProjection,
) -> None:
    """Laundering: the shipped mapping carries NO vectors / scores / paths.

    The :class:`TermRelevanceMapping` and its targets serialise to a JSON
    document whose keys are exactly the laundered fields -- record id, target,
    kind, surface, ranking weight, plus audit COUNTS. No 'vector', 'embedding',
    'sparse', 'splade', 'score', or source 'path' field may appear.
    """
    query, hits = _load_recorded("sweep-regla-de-prorrata.json")
    client: RagSearchClient = _RecordedClient({query: hits})
    result = run_sweep(
        client=client,
        concept_ids={"prorrata"},
        search_record_projection=_authoritative_projection,
        reindex=False,
        score_floor=0.5,
    )

    payload = result.model_dump_json()
    lowered = payload.lower()
    for forbidden in ("vector", "embedding", "sparse", "splade", '"score"', '"path"', '"snippet"'):
        assert forbidden not in lowered, f"laundering leak: {forbidden!r} present in shipped mapping"

    # The target shape is exactly the laundered field set.
    mapping = next(m for m in result.mappings if m.targets)
    target = mapping.targets[0]
    dumped = target.model_dump()
    assert set(dumped) == {"record_id", "target", "kind", "surface", "ranking_weight"}


def test_sweep_result_is_json_serialisable_for_the_landing_step(
    _authoritative_projection: SearchRecordProjection,
) -> None:
    """The SweepResult serialises with one model_dump_json (the landing-step seam)."""
    query, hits = _load_recorded("sweep-regla-de-prorrata.json")
    client: RagSearchClient = _RecordedClient({query: hits})
    result = run_sweep(
        client=client,
        concept_ids={"prorrata"},
        search_record_projection=_authoritative_projection,
        reindex=False,
    )

    payload = result.model_dump_json(indent=2)
    restored = SweepResult.model_validate_json(payload)
    assert restored == result


def test_below_floor_query_yields_only_the_seeded_concept_card(
    _authoritative_projection: SearchRecordProjection,
) -> None:
    """A thin-signal query still surfaces its originating concept card, no more.

    With no RAG hits above the floor, the sweep fabricates no grounding target.
    But a swept term is, by construction, a declared label of its concept, so
    the concept card is seeded deterministically as the sole target (concepts
    are first-class palette results). The mapping is therefore never
    targetless -- it carries exactly the concept card -- yet carries no invented
    RAG grounding.
    """
    client: RagSearchClient = _RecordedClient({})  # no hits for any query
    result = run_sweep(
        client=client,
        concept_ids={"prorrata"},
        search_record_projection=_authoritative_projection,
        reindex=False,
    )
    assert result.query_count == len(enumerate_query_vocabulary(concept_ids={"prorrata"}))
    # Every mapping carries exactly its originating concept card, nothing more.
    for mapping in result.mappings:
        assert mapping.concept_id == "prorrata"
        assert [t.record_id for t in mapping.targets] == ["concept:prorrata"]
        assert mapping.targets[0].surface == "concept"
        assert mapping.targets[0].target == "_generated/glossary.html#term-prorrata"


def test_structured_casilla_matching_is_canonical_then_unique_display_metadata(
    _authoritative_search_records: tuple[SearchRecord, ...],
) -> None:
    """The production matcher accepts exact addresses and refuses ambiguity."""
    canonical = _match_structured_casilla_query(
        "form 00200 field dp200014:00562",
        _authoritative_search_records,
    )
    assert canonical is not None
    assert canonical.metadata.modelo == "200"
    assert canonical.metadata.casilla_id == "DP200014:00562"

    fallback = _match_structured_casilla_query(
        "model 036 box 0110",
        _authoritative_search_records,
    )
    assert fallback is not None
    assert fallback.metadata.modelo == "036"
    assert fallback.metadata.number == "110"
    assert fallback.metadata.segmento is None

    # Modelo 200 reuses this display number across segments, so a bare number
    # is not an address. A non-existent number is the zero-match refusal.
    assert _match_structured_casilla_query("modelo 200 box 00562", _authoritative_search_records) is None
    assert _match_structured_casilla_query("modelo 303 casilla does-not-exist", _authoritative_search_records) is None


def test_structured_casilla_target_is_added_once_at_mapping_boundary(
    _authoritative_search_records: tuple[SearchRecord, ...],
    _authoritative_target_resolver: TargetResolver,
) -> None:
    """An exact projection record augments the mapping while concept seeding stays intact."""
    resolver = _authoritative_target_resolver
    query = SweepQuery(
        query="FORM 00200 FIELD DP200014:00562",
        concept_id="casilla",
        language=OutputLanguage.EN,
    )
    mapping = _mapping_from(
        query,
        wrangle(ResolutionResult(resolved=())),
        resolver=resolver,
        search_records=_authoritative_search_records,
    )

    casilla_targets = [target for target in mapping.targets if target.kind is SearchRecordKind.CASILLA]
    assert len(casilla_targets) == 1
    assert mapping.targets[0].record_id == "concept:casilla"
    assert casilla_targets[0].target == "_generated/casillas/200.html#casilla-dp200014-00562"
    assert [target.record_id for target in mapping.targets].count(casilla_targets[0].record_id) == 1


def test_unmanifested_resolved_code_target_is_not_shipped(
    _authoritative_search_records: tuple[SearchRecord, ...],
    _authoritative_target_resolver: TargetResolver,
) -> None:
    """The projection gate drops resolver-only ``code:*`` PAGE records."""
    resolver = _authoritative_target_resolver
    resolution = resolve_chunk_hits(
        (ChunkHit(path="src/cadrumo/core/casilla_id.py", line_start=1, line_end=1, score=1.0),),
        resolver=resolver,
    )
    assert len(resolution.resolved) == 1
    code_record = resolution.resolved[0].record
    emitted_ids = {record.id for record in _authoritative_search_records}
    assert code_record.id.startswith("code:")
    assert code_record.id not in emitted_ids

    mapping = _mapping_from(
        SweepQuery(query="casilla", concept_id="casilla", language=OutputLanguage.ES),
        wrangle(resolution),
        resolver=resolver,
        search_records=_authoritative_search_records,
    )

    assert code_record.id not in {target.record_id for target in mapping.targets}
    assert [target.record_id for target in mapping.targets] == ["concept:casilla"]


def test_emitted_legal_and_concept_targets_survive_projection_gate(
    _authoritative_search_records: tuple[SearchRecord, ...],
    _authoritative_target_resolver: TargetResolver,
) -> None:
    """Manifest-emitted legal records and deterministic concept seeding remain shipped."""
    query, hits = _load_recorded("sweep-regla-de-prorrata.json")
    resolver = _authoritative_target_resolver
    resolution = resolve_chunk_hits(hits, resolver=resolver)
    legal_ids = {target.record.id for target in resolution.resolved if target.surface is GroundingSurface.LEGAL}
    emitted_ids = {record.id for record in _authoritative_search_records}
    assert legal_ids
    assert legal_ids <= emitted_ids
    assert "concept:prorrata" in emitted_ids

    mapping = _mapping_from(
        SweepQuery(query=query, concept_id="prorrata", language=OutputLanguage.ES),
        wrangle(resolution, score_floor=0.5),
        resolver=resolver,
        search_records=_authoritative_search_records,
    )
    shipped_ids = {target.record_id for target in mapping.targets}

    assert legal_ids & shipped_ids
    assert "concept:prorrata" in shipped_ids


# ---------------------------------------------------------------------------
# Live-service integration
# ---------------------------------------------------------------------------


def test_relevance_mapping_is_frozen() -> None:
    """The strict-frozen contract on the shipped mapping record."""
    from pydantic import ValidationError

    mapping = TermRelevanceMapping(query="x", concept_id="prorrata", language=OutputLanguage.ES)
    with pytest.raises(ValidationError):
        mapping.query = "mutated"  # type: ignore[misc]
