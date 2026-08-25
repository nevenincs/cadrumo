"""Golden-query retrieval verification: the sweep's trust-gate.

Runs the fixed golden-query set through the resident RAG service and asserts
each query lands on its pinned preprocessed surface above its declared score
floor. This is the gate the build-time sweep depends on: if a golden query
stops reaching its preprocessed source surface, the index is not trustworthy and the
sweep must not run.

It is ``integration``-marked (live service, real queries, no mocks). It is
NOT ``docs``-marked: it must not run in the docs build lane, where the
service may be busy or the index mid-reindex. The sweep entry point invokes
the reindex-before-sweep step first, then this verification, then proceeds
only on a green result.

A query that does not clear its floor is a REAL finding the sweep must know
about - the test reports the shortfall rather than hiding it.
"""

from __future__ import annotations

import pytest

from ...._paths import REPO_ROOT
from .._golden_queries import (
    GOLDEN_QUERIES,
    GoldenQuery,
    GoldenSurface,
    _classify,
    evaluate_query,
    extraction_sidecar_hits,
    run_query,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.resident_service]

# dev/docs/preprocess/tests/test_golden_queries.py -> parents[4] is repo root.
_REPO_ROOT = REPO_ROOT


def test_xlsm_record_design_is_a_corpus_and_diseno_source() -> None:
    path = "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/files/DR220e23.xlsm"
    assert _classify(path) == {GoldenSurface.ANY_CORPUS_SOURCE, GoldenSurface.DISENO_SOURCE}


@pytest.mark.parametrize(
    "golden",
    GOLDEN_QUERIES,
    ids=[g.surface.value + ":" + g.query[:24] for g in GOLDEN_QUERIES],
)
def test_golden_query_reaches_its_surface(golden: GoldenQuery) -> None:
    """Each golden query hits its pinned surface above its score floor.

    Runs the real query through the resident service and asserts a hit on the
    expected preprocessed surface clears the declared floor. A miss is a real
    retrieval-quality finding, reported with the top hits for triage.
    """
    hits = run_query(golden.query, repo_root=_REPO_ROOT)
    result = evaluate_query(golden, hits)
    top = [(round(h.score, 3), h.path[-60:]) for h in result.top_hits]
    assert result.passed, (
        f"query {golden.query!r} did not reach {golden.surface.value} above "
        f"floor {golden.floor} ({golden.note}); top hits: {top}"
    )


def test_extraction_sidecars_are_deduplicated_out_of_the_index() -> None:
    """A corpus query returns NO sidecar hits - only hook-fed source hits.

    Proves the post-cutover dedup: the
    ``*.extracted.*`` sidecars are ``.vaultragignore``-excluded because the
    preprocess-hook rules feed the same extraction truth under source paths.
    A sidecar hit means the exclusion did not take effect (the index was not
    rebuilt after the ``.vaultragignore`` change); an empty source-hit set
    means the hook rules over-excluded the corpus.
    """
    hits = run_query(
        "regla de prorrata operaciones deduccion",
        repo_root=_REPO_ROOT,
        max_results=15,
    )
    sidecars = extraction_sidecar_hits(hits)
    sources = [h for h in hits if "/corpus/normatives/html/" in h.path and h.path.endswith(".html")]
    sidecar_paths = [h.path[-55:] for h in sidecars]
    assert not sidecars, (
        f"{len(sidecars)} sidecar hits survived the dedup exclusion "
        f"(reindex after the .vaultragignore change): {sidecar_paths}"
    )
    # The hook-fed sources must still be present - the exclusion must not
    # have removed the preprocessed surface too.
    assert sources, "no normatives source hits - the dedup over-excluded"
