"""Shared model2vec loader for the semantic-search stack.

Both the build-time precompute
(:mod:`~application.corpus_search._embed_build`) and the runtime query embedder
(:mod:`~application.corpus_search._query_embed`) load the same
``potion-multilingual-128M`` static model behind the capability-gated
``aeat-cli[search]`` extra. This module is the one place that lazily imports
``model2vec`` and refuses with an install hint when it is absent, so neither
consumer duplicates the gate and the degraded lexical-only mode never depends
on the semantic stack at import time.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from ._errors import CorpusSearchDependencyError

#: Install hint surfaced on every semantic-stack refusal.
SEARCH_EXTRA_HINT = "pip install aeat-cli[search]"

_DEFAULT_DIMENSIONS = 256


def load_static_model(model_id: str, *, revision: str, cache_dir: Path | None = None) -> Any:
    """Load a model2vec ``StaticModel``, refusing if the ``search`` extra is absent.

    Args:
        model_id: The model2vec model to load.
        revision: The pinned model revision, passed through when the installed
            ``from_pretrained`` accepts it.
        cache_dir: Optional app-controlled cache directory for the download.

    Returns:
        The loaded ``StaticModel`` (typed ``Any`` — model2vec ships no stubs).

    Raises:
        CorpusSearchDependencyError: If ``model2vec`` is not installed.
    """
    try:
        # IMPORT-RATIONALE-OPTIONAL-SEARCH-EXTRA: model2vec rides the optional
        # aeat-cli[search] extra; a bare-core install lacks it, so the import is
        # lazy and its typing is unresolved until the extra is present.
        from model2vec import (
            StaticModel,  # type: ignore[import-not-found, unused-ignore]  # TYPE-IGNORE-RATIONALE-optextra: model2vec is an optional extra without shipped type stubs
        )
    except ImportError as exc:
        raise CorpusSearchDependencyError(
            "the corpus-search semantic stack (model2vec) is not installed",
            context={"model_id": model_id, "dependency": "model2vec"},
            suggestion=SEARCH_EXTRA_HINT,
        ) from exc
    kwargs: dict[str, object] = {}
    accepted = inspect.signature(StaticModel.from_pretrained).parameters
    if "revision" in accepted:
        kwargs["revision"] = revision
    if cache_dir is not None and "cache_dir" in accepted:
        kwargs["cache_dir"] = str(cache_dir)
    return StaticModel.from_pretrained(model_id, **kwargs)


# KWARGS-ANY-RATIONALE-cli: model is an untyped model2vec StaticModel optional-extra object
def model_dimensions(
    model: Any,
) -> int:  # KWARGS-ANY-RATIONALE-optextra: model is an untyped model2vec StaticModel optional-extra object
    """Return the embedding dimensionality of a loaded ``StaticModel``."""
    dim = getattr(model, "dim", None)
    if isinstance(dim, int) and dim > 0:
        return dim
    embedding = getattr(model, "embedding", None)
    shape = getattr(embedding, "shape", None)
    if shape is not None and len(shape) == 2:
        return int(shape[1])
    return _DEFAULT_DIMENSIONS


__all__ = ["SEARCH_EXTRA_HINT", "load_static_model", "model_dimensions"]
