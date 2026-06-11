"""Golden-query retrieval verification: the sweep's trust-gate.

Runs the fixed golden-query set through the resident RAG service and asserts
each query lands on its pinned preprocessed surface above its declared score
floor. This is the gate the build-time sweep depends on: if a golden query
stops reaching its sidecar surface, the index is not trustworthy and the
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

from pathlib import Path

import pytest

from .._golden_queries import (
    GOLDEN_QUERIES,
    GoldenQuery,
    evaluate_query,
    raw_normatives_html_hits,
    run_query,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_golden_queries.py -> parents[4] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]


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


def test_raw_normatives_html_is_deduplicated() -> None:
    """A normatives query returns NO raw-HTML hits - only clean sidecars.

    Proves the dedup exclusion: the raw ``normatives/html/*.html`` files are
    excluded from the index via ``.vaultragignore``, so the duplicate-but-worse
    raw-markup hits are gone and only the clean ``*.extracted.md`` per-article
    sidecars survive. A non-empty raw-hit set means the exclusion did not take
    effect (the index was not rebuilt after the ``.vaultragignore`` change).
    """
    hits = run_query(
        "regla de prorrata operaciones deduccion",
        repo_root=_REPO_ROOT,
        max_results=15,
    )
    raw = raw_normatives_html_hits(hits)
    sidecar = [h for h in hits if "/corpus/normatives/" in h.path and ".extracted." in h.path]
    raw_paths = [h.path[-55:] for h in raw]
    assert not raw, (
        f"{len(raw)} raw normatives-HTML hits survived the dedup exclusion "
        f"(reindex after the .vaultragignore change): {raw_paths}"
    )
    # The clean sidecars must still be present - the exclusion must not have
    # removed the preprocessed surface too.
    assert sidecar, "no normatives sidecar hits - the dedup over-excluded"
