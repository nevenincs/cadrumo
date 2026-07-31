"""Real-behavior tests for the build-time embedding precompute.

model2vec rides the capability-gated ``cadrumo[search]`` extra. These tests
branch on its real presence — never skip: when the extra is absent (the
shippable degraded default) they assert the typed refusal with the
install hint; when it is present they assert a real tiny embed. The
pure-numpy more-like-this primitive is exercised unconditionally.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from .._embed_build import (
    POTION_MODEL_ID,
    POTION_MODEL_REVISION,
    embed_corpus,
    load_embeddings,
    more_like_this,
)
from .._errors import CorpusSearchDependencyError, CorpusSearchInputError
from .._models import CorpusChunk
from .._query_embed import search_extra_available

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODEL2VEC_PRESENT = importlib.util.find_spec("model2vec") is not None


def _chunk(chunk_id: str, text: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        corpus_ref="corpus/normatives/html/x.html#a1",
        source_path="corpus/normatives/html/x.html",
        doc_title="X",
        ordinal=0,
        text=text,
    )


def test_pinned_model_constants_are_declared() -> None:
    assert POTION_MODEL_ID == "minishlab/potion-multilingual-128M"
    assert POTION_MODEL_REVISION


def test_embed_corpus_matches_environment_capability(tmp_path: Path) -> None:
    # No skip: the test always runs and asserts the correct real behavior for
    # the environment. Absent the search extra (the shippable degraded
    # default) embed_corpus refuses with the install hint and writes nothing.
    # Present, it must NOT hit this refusal path — but the actual embed is a
    # network-download path this unit gate does not drive (mirrors
    # test_query_embed.py::test_embed_query_matches_environment_capability);
    # the real build is proven in the opt-in
    # test_hybrid_real_model_recall_live.py instead.
    chunks = [_chunk("a:000:00", "recargo extemporáneo"), _chunk("b:000:00", "cuota íntegra")]
    matrix_path = tmp_path / "m.npy"
    chunk_ids_path = tmp_path / "ids.json"
    if not _MODEL2VEC_PRESENT:
        with pytest.raises(CorpusSearchDependencyError) as exc_info:
            embed_corpus(chunks, matrix_path=matrix_path, chunk_ids_path=chunk_ids_path)
        assert exc_info.value.suggestion == "pip install cadrumo[search]"
        assert not matrix_path.exists()
        return
    assert search_extra_available() is True


def test_more_like_this_ranks_by_cosine_and_excludes_self() -> None:
    matrix = np.array([[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
    ids = ["a", "b", "c", "d"]
    similar = more_like_this(matrix, ids, "a", top_k=2)
    assert [item.chunk_id for item in similar] == ["b", "c"]
    assert similar[0].similarity > similar[1].similarity
    assert [item.rank for item in similar] == [0, 1]


def test_more_like_this_load_roundtrip(tmp_path: Path) -> None:
    matrix = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]], dtype=np.float32)
    ids = ["a", "b", "c"]
    matrix_path = tmp_path / "m.npy"
    ids_path = tmp_path / "ids.json"
    np.save(matrix_path, matrix)
    ids_path.write_text(json.dumps(ids), encoding="utf-8")
    loaded_matrix, loaded_ids = load_embeddings(matrix_path, ids_path)
    assert loaded_ids == tuple(ids)
    similar = more_like_this(loaded_matrix, loaded_ids, "c", top_k=1)
    assert similar[0].chunk_id in {"a", "b"}


def test_more_like_this_unknown_id_is_refused() -> None:
    matrix = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    with pytest.raises(CorpusSearchInputError):
        more_like_this(matrix, ["a", "b"], "missing", top_k=1)


def test_more_like_this_length_mismatch_is_refused() -> None:
    matrix = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    with pytest.raises(CorpusSearchInputError):
        more_like_this(matrix, ["a"], "a", top_k=1)


def test_more_like_this_non_positive_top_k_is_refused() -> None:
    matrix = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    with pytest.raises(CorpusSearchInputError):
        more_like_this(matrix, ["a", "b"], "a", top_k=0)
