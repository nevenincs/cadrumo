"""The sweep runner against the LIVE RAG service.

Split out of ``test_sweep`` so each module carries one execution lane. Every
other gate there drives a recorded client over committed fixtures and is
``unit``; this one routes through the resident service on port 8766, so it is
``integration`` and belongs where a lane that needs a running daemon belongs.

It does not self-skip. An unreachable or busy service fails this test with the
service error, because a sweep gate that quietly passes when the oracle is
absent is worth nothing.
"""

from __future__ import annotations

import pytest

from dev.docs.terminology._sweep import ServiceRagSearchClient, SweepError, run_sweep

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]


def test_live_service_sweep_runs_at_least_one_term() -> None:
    """The real retrieval path runs against the LIVE service for one term.

    Routes through the resident service on port 8766 with an explicit timeout.
    If the service is unreachable or busy behind a peer index-rebuild, this
    integration test fails with the service error instead of self-skipping.
    """
    client = ServiceRagSearchClient(timeout_s=60.0)
    try:
        result = run_sweep(client=client, concept_ids={"prorrata"}, reindex=False, score_floor=0.5)
    except SweepError as exc:
        raise AssertionError(f"RAG service unreachable/busy: {exc}") from exc

    assert result.query_count > 0
    # At least one prorrata query should resolve to a target against the live
    # index (the prorrata grounding is well-indexed; the golden queries pass).
    assert any(mapping.targets for mapping in result.mappings), "no live target for any prorrata term"
