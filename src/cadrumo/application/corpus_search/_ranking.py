"""Import-safe vector and hybrid-ranking primitives for semantic search.

The corpus and command search surfaces use the same cosine preparation and
Reciprocal Rank Fusion contract. NumPy stays function-local so importing the
corpus-search facade remains safe in lexical-only installations.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import numpy as np


#: Canonical RRF damping constant. It keeps a strong hit on one ranker from
#: being drowned by the other ranker's long tail.
RRF_K: Final[int] = 60


def l2_normalise(matrix: np.ndarray) -> np.ndarray:
    """Return row-wise L2 unit vectors while preserving zero rows as zero."""
    import numpy as np

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


def reciprocal_rank_fusion(
    primary_rank_by_id: Mapping[str, int],
    secondary_rank_by_id: Mapping[str, int],
    *,
    rrf_k: int = RRF_K,
    candidate_ids: Collection[str] | None = None,
) -> list[tuple[str, float]]:
    """Fuse two zero-based rankings by RRF with stable primary-side ties.

    By default the result includes the union of both rank maps. A caller may
    supply ``candidate_ids`` to restrict that union, which keeps command search
    semantic re-ranking inside its lexical candidate set. Equal fused scores
    break by the primary ranking, then identifier, so callers retain
    deterministic lexical ordering when their semantic side cannot distinguish
    two results.
    """
    scores: dict[str, float] = {}
    for rank_by_id in (primary_rank_by_id, secondary_rank_by_id):
        for item_id, rank in rank_by_id.items():
            if candidate_ids is not None and item_id not in candidate_ids:
                continue
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (rrf_k + rank + 1)
    return sorted(
        scores.items(),
        key=lambda item: (-item[1], primary_rank_by_id.get(item[0], len(scores)), item[0]),
    )


__all__ = ["RRF_K", "l2_normalise", "reciprocal_rank_fusion"]
