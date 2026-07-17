"""Shared model2vec loader for the semantic-search stack.

Both the build-time precompute
(:mod:`~application.corpus_search._embed_build`) and the runtime query embedder
(:mod:`~application.corpus_search._query_embed`) load the same
``potion-multilingual-128M`` static model behind the capability-gated
``cadrumo[search]`` extra. This module is the one place that lazily imports
``model2vec`` and refuses with an install hint when it is absent, so neither
consumer duplicates the gate and the degraded lexical-only mode never depends
on the semantic stack at import time.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from ._errors import CorpusSearchDependencyError

#: Install hint surfaced on every semantic-stack refusal.
SEARCH_EXTRA_HINT = "pip install cadrumo[search]"

_DEFAULT_DIMENSIONS = 256


@runtime_checkable
class StaticEmbeddingModel(Protocol):
    """Minimal model2vec surface consumed by corpus embedding services."""

    def encode(self, sentences: Sequence[str]) -> object:
        """Return an array-like embedding matrix for ``sentences``."""
        ...


def load_static_model(
    model_id: str,
    *,
    revision: str,
    cache_dir: Path | None = None,
) -> StaticEmbeddingModel:
    """Load a model2vec ``StaticModel``, refusing if the ``search`` extra is absent.

    Args:
        model_id: The model2vec model to load.
        revision: The pinned model revision, passed through when the installed
            ``from_pretrained`` accepts it.
        cache_dir: Optional app-controlled cache directory for the download.

    Returns:
        The loaded model narrowed to the embedding protocol used here.

    Raises:
        CorpusSearchDependencyError: If ``model2vec`` is not installed.
    """
    try:
        # IMPORT-RATIONALE-OPTIONAL-SEARCH-EXTRA: model2vec rides the optional
        # cadrumo[search] extra; importlib keeps the dependency lazy so a
        # bare-core install reaches the typed refusal below.
        model2vec = importlib.import_module("model2vec")
    except ImportError as exc:
        raise CorpusSearchDependencyError(
            "the corpus-search semantic stack (model2vec) is not installed",
            context={"model_id": model_id, "dependency": "model2vec"},
            suggestion=SEARCH_EXTRA_HINT,
        ) from exc
    kwargs: dict[str, object] = {}
    static_model = model2vec.StaticModel
    accepted = inspect.signature(static_model.from_pretrained).parameters
    if "revision" in accepted:
        kwargs["revision"] = revision
    if cache_dir is not None and "cache_dir" in accepted:
        kwargs["cache_dir"] = str(cache_dir)
    loaded = static_model.from_pretrained(model_id, **kwargs)
    if not isinstance(loaded, StaticEmbeddingModel):
        raise CorpusSearchDependencyError(
            "the installed model2vec StaticModel lacks the required encode method",
            context={"model_id": model_id, "dependency": "model2vec"},
            suggestion=SEARCH_EXTRA_HINT,
        )
    return loaded


def model_dimensions(
    model: StaticEmbeddingModel,
) -> int:
    """Return the embedding dimensionality of a loaded ``StaticModel``."""
    dim = getattr(model, "dim", None)
    if isinstance(dim, int) and dim > 0:
        return dim
    embedding = getattr(model, "embedding", None)
    shape = getattr(embedding, "shape", None)
    if isinstance(shape, Sequence) and len(shape) == 2:
        dimensions = shape[1]
        if isinstance(dimensions, int) and dimensions > 0:
            return dimensions
    return _DEFAULT_DIMENSIONS


__all__ = ["SEARCH_EXTRA_HINT", "StaticEmbeddingModel", "load_static_model", "model_dimensions"]
