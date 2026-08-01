"""Golden contracts shared by corpus and command semantic ranking."""

from __future__ import annotations

import numpy as np
import pytest

from .. import RRF_K, l2_normalise, reciprocal_rank_fusion

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_l2_normalise_preserves_cosine_geometry_and_zero_rows() -> None:
    vectors = np.array([[3.0, 4.0], [0.0, 0.0], [-5.0, 0.0]], dtype=np.float32)

    normalised = l2_normalise(vectors)

    np.testing.assert_allclose(
        normalised,
        np.array([[0.6, 0.8], [0.0, 0.0], [-1.0, 0.0]], dtype=np.float32),
    )


def test_rrf_golden_keeps_primary_tie_break_and_secondary_only_hits() -> None:
    fused = reciprocal_rank_fusion(
        {"lexical-first": 0, "both": 1},
        {"semantic-only": 0, "both": 1},
    )

    assert [item_id for item_id, _score in fused] == ["both", "lexical-first", "semantic-only"]
    assert fused[0][1] == pytest.approx(2.0 / (RRF_K + 2))
    assert fused[1][1] == pytest.approx(1.0 / (RRF_K + 1))
    assert fused[2][1] == pytest.approx(1.0 / (RRF_K + 1))


def test_rrf_candidate_filter_preserves_command_search_lexical_universe() -> None:
    lexical_candidates = {"lexical-first": 0, "lexical-second": 1}

    fused = reciprocal_rank_fusion(
        lexical_candidates,
        {"semantic-only": 0, "lexical-second": 0, "lexical-first": 100},
        candidate_ids=lexical_candidates,
    )

    assert [item_id for item_id, _score in fused] == ["lexical-second", "lexical-first"]
