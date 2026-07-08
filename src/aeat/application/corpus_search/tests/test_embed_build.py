"""Real-behavior tests for the build-time embedding precompute.

model2vec rides the capability-gated ``aeat-cli[search]`` extra. These tests
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
    # No skip: the test always runs and asserts the correct real behavior
    # for the environment. Absent the search extra (the shippable degraded
    # default) embed_corpus refuses with the install hint and writes
    # nothing; present, it writes a valid float32 matrix + chunk-id list.
    chunks = [_chunk("a:000:00", "recargo extemporáneo"), _chunk("b:000:00", "cuota íntegra")]
    matrix_path = tmp_path / "m.npy"
    chunk_ids_path = tmp_path / "ids.json"
    if not _MODEL2VEC_PRESENT:
        with pytest.raises(CorpusSearchDependencyError) as exc_info:
            embed_corpus(chunks, matrix_path=matrix_path, chunk_ids_path=chunk_ids_path)
        assert exc_info.value.suggestion == "pip install aeat-cli[search]"
        assert not matrix_path.exists()
        return
    result = embed_corpus(chunks, matrix_path=matrix_path, chunk_ids_path=chunk_ids_path)
    assert result.chunk_count == 2
    matrix = np.load(matrix_path)
    assert matrix.dtype == np.float32
    assert matrix.shape == (2, result.dimensions)
    assert json.loads(chunk_ids_path.read_text(encoding="utf-8")) == ["a:000:00", "b:000:00"]


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
