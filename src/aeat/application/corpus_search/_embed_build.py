"""Build-time corpus embedding precompute (the semantic half of R3).

The corpus is static and bundled, so its embeddings are precomputed ONCE
at build time with ``model2vec`` (``potion-multilingual-128M`` — MIT code
and MIT weights) and shipped as a plain float32 numpy matrix plus a
parallel chunk-id list. Model outputs are shippable per the licence-clean
rule; the query model is needed ONLY to embed a live query, so a build
that ships the corpus vectors carries a degraded, no-download semantic
mode: the "more-like-this-document" primitive here runs over the shipped
matrix with numpy alone and never touches the model.

``model2vec`` rides the capability-gated ``aeat-cli[search]`` extra. When it
is absent this module still imports (the degraded lexical-only mode stays
live) and :func:`embed_corpus` refuses with an install hint rather than
crashing, mirroring every other optional-integration boundary in the
tree. numpy is imported function-locally for the same reason, so the
lexical-only surface never depends on it at import time.

See Also:
    :func:`~application.corpus_search.ensure_corpus_embeddings`
        Runtime build-once cache that calls this precompute behind the
        ``aeat-cli[search]`` extra.
    :class:`~application.corpus_search.QueryEmbedder`
        Live-query half that embeds operator text into the same vector space.
    :func:`~application.corpus_search.hybrid_search`
        Retrieval fusion consumer of the precomputed matrix.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.external_constants import UTF_8_ENCODING
from ._model_loader import load_static_model, model_dimensions
from ._models import CorpusChunk, CorpusEmbeddingBuildResult, SimilarChunk

if TYPE_CHECKING:
    import numpy as np

# The distilled static embedding model. Licence: MIT code AND MIT weights,
# distilled from BGE-m3 (MIT) on the C4 (ODC-BY) corpus — the attribution
# line lands in THIRD_PARTY_NOTICES. The revision is pinned to a concrete
# commit SHA (not the moving ``main`` branch) so a first-use download is
# reproducible and cannot silently pull a re-published model; it rides through
# to the result record for provenance. Measured footprint at this revision:
# ~0.5 GB per weight file (safetensors), ~2.1 GB resident in the HF hub cache
# (onnx + safetensors + no-symlink blob duplication) — the first-use download
# cost of opting into the ``aeat-cli[search]`` extra.
POTION_MODEL_ID = "minishlab/potion-multilingual-128M"
POTION_MODEL_REVISION = "73908c3438cf03b6a01bcb9611d62b23d0726f08"


def embed_corpus(
    chunks: Iterable[CorpusChunk],
    *,
    matrix_path: Path,
    chunk_ids_path: Path,
    model_id: str = POTION_MODEL_ID,
    revision: str = POTION_MODEL_REVISION,
    cache_dir: Path | None = None,
) -> CorpusEmbeddingBuildResult:
    """Precompute and persist corpus embeddings for ``chunks``.

    Args:
        chunks: The chunk sequence to embed, typically
            ``iter_corpus_chunks()``. Order is preserved so the matrix
            stays row-aligned with the persisted chunk-id list.
        matrix_path: Destination ``.npy`` file for the float32 matrix.
        chunk_ids_path: Destination ``.json`` file for the parallel
            chunk-id list.
        model_id: The model2vec model to load.
        revision: The pinned model revision, recorded for provenance.
        cache_dir: Optional app-controlled model cache directory.

    Returns:
        A :class:`CorpusEmbeddingBuildResult` describing the written
        artifacts.

    Raises:
        CorpusSearchDependencyError: If the ``search`` extra (``model2vec``)
            is not installed.
    """
    import numpy as np

    model = load_static_model(model_id, revision=revision, cache_dir=cache_dir)
    chunk_list = list(chunks)
    chunk_ids = [chunk.chunk_id for chunk in chunk_list]
    texts = [chunk.text for chunk in chunk_list]
    raw = model.encode(texts) if texts else np.empty((0, model_dimensions(model)), dtype=np.float32)
    matrix = np.asarray(raw, dtype=np.float32)
    if matrix.ndim != 2:
        matrix = matrix.reshape(len(chunk_ids), -1)
    dimensions = int(matrix.shape[1]) if matrix.size else model_dimensions(model)

    matrix_path = Path(matrix_path)
    chunk_ids_path = Path(chunk_ids_path)
    np.save(matrix_path, matrix, allow_pickle=False)
    chunk_ids_path.write_text(json.dumps(chunk_ids, ensure_ascii=False, indent=0), encoding=UTF_8_ENCODING)

    return CorpusEmbeddingBuildResult(
        matrix_path=matrix_path.as_posix(),
        chunk_ids_path=chunk_ids_path.as_posix(),
        chunk_count=len(chunk_ids),
        dimensions=dimensions,
        embedding_model_id=model_id,
        embedding_model_revision=revision,
    )


def load_embeddings(matrix_path: Path, chunk_ids_path: Path) -> tuple[np.ndarray, tuple[str, ...]]:
    """Load a precomputed matrix and its parallel chunk-id list.

    Args:
        matrix_path: A ``.npy`` matrix written by :func:`embed_corpus`.
        chunk_ids_path: The parallel ``.json`` chunk-id list.

    Returns:
        The loaded matrix and the chunk-id tuple.
    """
    import numpy as np

    matrix = np.load(matrix_path, allow_pickle=False)
    chunk_ids = tuple(json.loads(Path(chunk_ids_path).read_text(encoding=UTF_8_ENCODING)))
    return matrix, chunk_ids


def more_like_this(
    matrix: np.ndarray,
    chunk_ids: Sequence[str],
    query_chunk_id: str,
    *,
    top_k: int = 5,
) -> tuple[SimilarChunk, ...]:
    """Return the cosine-nearest chunks to ``query_chunk_id``.

    Runs over the precomputed matrix with numpy alone — no model, so this
    is the degraded, no-download semantic primitive. The query chunk
    itself is excluded from its own results.

    Args:
        matrix: The precomputed embedding matrix, one row per chunk id.
        chunk_ids: The chunk ids aligned with ``matrix`` rows.
        query_chunk_id: The chunk to find neighbours for.
        top_k: Maximum number of neighbours to return.

    Returns:
        Up to ``top_k`` :class:`SimilarChunk` records, most similar first.

    Raises:
        CorpusSearchInputError: If ``query_chunk_id`` is not in
            ``chunk_ids``, ``top_k`` is not positive, or the matrix and id
            list disagree in length.
    """
    import numpy as np

    from ._errors import CorpusSearchInputError

    if top_k <= 0:
        raise CorpusSearchInputError("more-like-this top_k must be positive", context={"top_k": top_k})
    if matrix.shape[0] != len(chunk_ids):
        raise CorpusSearchInputError(
            "embedding matrix and chunk-id list length disagree",
            context={"matrix_rows": int(matrix.shape[0]), "chunk_ids": len(chunk_ids)},
        )
    try:
        query_index = list(chunk_ids).index(query_chunk_id)
    except ValueError as exc:
        raise CorpusSearchInputError(
            "unknown query chunk id",
            context={"query_chunk_id": query_chunk_id},
        ) from exc

    normalised = _l2_normalise(np.asarray(matrix, dtype=np.float32))
    similarities = normalised @ normalised[query_index]
    order = np.argsort(-similarities)
    results: list[SimilarChunk] = []
    for rank_index in order:
        index = int(rank_index)
        if index == query_index:
            continue
        results.append(
            SimilarChunk(
                chunk_id=chunk_ids[index],
                rank=len(results),
                similarity=float(similarities[index]),
            )
        )
        if len(results) >= top_k:
            break
    return tuple(results)


def _l2_normalise(matrix: np.ndarray) -> np.ndarray:
    import numpy as np

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


__all__ = [
    "POTION_MODEL_ID",
    "POTION_MODEL_REVISION",
    "embed_corpus",
    "load_embeddings",
    "more_like_this",
]
