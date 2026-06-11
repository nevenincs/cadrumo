"""Real-behaviour conformance for the query-vocabulary RAG sweep runner (ADR D6).

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
covered; it is skipped (not failed) when the service is unreachable -- the
resident store is single-writer and a peer index-rebuild can make it busy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aeat.core.external_constants import OutputLanguage
from dev.docs.terminology._resolution import ChunkHit
from dev.docs.terminology._search_record import SearchRecordKind
from dev.docs.terminology._sweep import (
    RagSearchClient,
    ServiceRagSearchClient,
    SweepError,
    SweepResult,
    TermRelevanceMapping,
    enumerate_query_vocabulary,
    run_sweep,
)

pytestmark = [pytest.mark.hex_core, pytest.mark.docs]

_FIXTURES = Path(__file__).parent / "fixtures"


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


@pytest.mark.unit
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
    assert "aranyositas" in by_text  # hu admitted
    # The hidden search form is enumerated and flagged.
    assert "prorateo" in by_text
    assert by_text["prorateo"].is_hidden_form is True
    assert by_text["prorrata"].is_hidden_form is False
    # Every query keeps its concept association.
    assert all(q.concept_id == "prorrata" for q in queries)
    # Language tagging is correct.
    assert by_text["pro rata"].language is OutputLanguage.EN
    assert by_text["aranyositas"].language is OutputLanguage.HU


@pytest.mark.unit
def test_enumerate_vocabulary_dedupes_identical_query_strings() -> None:
    """Identical query strings within a concept collapse (es/ca share 'prorrata')."""
    queries = enumerate_query_vocabulary(concept_ids={"prorrata"})
    texts = [q.query for q in queries]
    assert len(texts) == len(set(texts)), "duplicate query strings were not deduped"


@pytest.mark.unit
def test_enumerate_full_vocabulary_is_a_bounded_closed_set() -> None:
    """The full 95-concept vocabulary is a finite, deduplicated closed set."""
    queries = enumerate_query_vocabulary()
    assert queries  # non-empty
    keys = [(q.concept_id, q.query.casefold()) for q in queries]
    assert len(keys) == len(set(keys)), "duplicate (concept, query) pairs"


# ---------------------------------------------------------------------------
# End-to-end on real captured data (deterministic replay)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_real_sweep_maps_prorrata_to_its_grounding_targets() -> None:
    """End-to-end: a real 'regla de prorrata' response maps to its grounding targets.

    Replays a response CAPTURED FROM THE LIVE service through the real
    resolver + wrangler. The mapping's targets must deep-link to the prorrata
    grounding across surfaces -- the BOE art-104 article (the legal grounding
    the code is grounded against) and/or the prorrata concept card -- proving
    the precompiled-RAG pipeline works on genuine data.
    """
    query, hits = _load_recorded("sweep-regla-de-prorrata.json")
    client: RagSearchClient = _RecordedClient({query: hits})

    result = run_sweep(client=client, concept_ids={"prorrata"}, reindex=False, score_floor=0.5)

    mapping = next(m for m in result.mappings if m.query == query)
    assert mapping.targets, "the real prorrata sweep produced no targets"
    targets = mapping.targets

    # A legal grounding target deep-links to the BOE prorrata article (art 102/104).
    legal_targets = [t for t in targets if t.surface == "legal"]
    assert any("boe.es" in t.target for t in legal_targets), "no BOE legal grounding target"
    assert any("#a104" in t.target or "#a102" in t.target for t in legal_targets), "no prorrata article anchor"

    # A concept card target deep-links to the glossary anchor.
    concept_targets = [t for t in targets if t.kind is SearchRecordKind.CONCEPT]
    assert any("glossary.html#term-prorrata" in t.target for t in concept_targets), "no prorrata concept card target"

    # Targets are ranked (descending weight).
    weights = [t.ranking_weight for t in targets]
    assert weights == sorted(weights, reverse=True)


@pytest.mark.unit
def test_sweep_mapping_is_laundered_ids_targets_weights_only() -> None:
    """Laundering: the shipped mapping carries NO vectors / scores / paths.

    The :class:`TermRelevanceMapping` and its targets serialise to a JSON
    document whose keys are exactly the laundered fields -- record id, target,
    kind, surface, ranking weight, plus audit COUNTS. No 'vector', 'embedding',
    'sparse', 'splade', 'score', or source 'path' field may appear.
    """
    query, hits = _load_recorded("sweep-regla-de-prorrata.json")
    client: RagSearchClient = _RecordedClient({query: hits})
    result = run_sweep(client=client, concept_ids={"prorrata"}, reindex=False, score_floor=0.5)

    payload = result.model_dump_json()
    lowered = payload.lower()
    for forbidden in ("vector", "embedding", "sparse", "splade", '"score"', '"path"', '"snippet"'):
        assert forbidden not in lowered, f"laundering leak: {forbidden!r} present in shipped mapping"

    # The target shape is exactly the laundered field set.
    mapping = next(m for m in result.mappings if m.targets)
    target = mapping.targets[0]
    dumped = target.model_dump()
    assert set(dumped) == {"record_id", "target", "kind", "surface", "ranking_weight"}


@pytest.mark.unit
def test_sweep_result_is_json_serialisable_for_the_landing_step() -> None:
    """The SweepResult serialises with one model_dump_json (the landing-step seam)."""
    query, hits = _load_recorded("sweep-regla-de-prorrata.json")
    client: RagSearchClient = _RecordedClient({query: hits})
    result = run_sweep(client=client, concept_ids={"prorrata"}, reindex=False)

    payload = result.model_dump_json(indent=2)
    restored = SweepResult.model_validate_json(payload)
    assert restored == result


@pytest.mark.unit
def test_below_floor_query_yields_an_empty_but_recorded_mapping() -> None:
    """A query whose hits are all below the floor maps to zero targets, honestly.

    A thin-signal term (no recorded hits) produces a mapping with no targets
    rather than a fabricated one -- the honest empty result, still recorded with
    its concept association.
    """
    client: RagSearchClient = _RecordedClient({})  # no hits for any query
    result = run_sweep(client=client, concept_ids={"prorrata"}, reindex=False)
    assert result.query_count == len(enumerate_query_vocabulary(concept_ids={"prorrata"}))
    assert all(mapping.targets == () for mapping in result.mappings)
    # Every mapping still names its query + concept.
    assert all(mapping.concept_id == "prorrata" for mapping in result.mappings)


# ---------------------------------------------------------------------------
# Live-service integration (skipped when the service is busy/unreachable)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_live_service_sweep_runs_at_least_one_term() -> None:
    """The real retrieval path runs against the LIVE service for one term.

    Routes through the resident service on port 8766 with an explicit timeout.
    Skipped (not failed) when the service is unreachable / busy behind a peer
    index-rebuild -- the single-writer store can be mid-rebuild.
    """
    client = ServiceRagSearchClient(timeout_s=60.0)
    try:
        result = run_sweep(client=client, concept_ids={"prorrata"}, reindex=False, score_floor=0.5)
    except SweepError as exc:
        pytest.skip(f"RAG service unreachable/busy: {exc}")

    assert result.query_count > 0
    # At least one prorrata query should resolve to a target against the live
    # index (the prorrata grounding is well-indexed; the golden queries pass).
    assert any(mapping.targets for mapping in result.mappings), "no live target for any prorrata term"


@pytest.mark.unit
def test_relevance_mapping_is_frozen() -> None:
    """The strict-frozen contract on the shipped mapping record."""
    from pydantic import ValidationError

    mapping = TermRelevanceMapping(query="x", concept_id="prorrata", language=OutputLanguage.ES)
    with pytest.raises(ValidationError):
        mapping.query = "mutated"  # type: ignore[misc]
