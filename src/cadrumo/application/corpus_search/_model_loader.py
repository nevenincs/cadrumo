"""Shared model2vec loader for the semantic-search stack.

Both the build-time precompute
(:mod:`~application.corpus_search._embed_build`) and the runtime query embedder
(:mod:`~application.corpus_search._query_embed`) load the same
``potion-multilingual-128M`` static model behind the capability-gated
``cadrumo[search]`` extra. This module is the one place that lazily imports
``model2vec`` and refuses with an install hint when it is absent, so neither
consumer duplicates the gate and the degraded lexical-only mode never depends
on the semantic stack at import time.

The pinned model2vec range (``model2vec>=0.8,<1``) resolves ``from_pretrained``
signatures that accept neither a ``revision`` nor a ``cache_dir`` keyword, so
this loader never hands ``from_pretrained`` a bare model id and lets model2vec
resolve it. Instead it resolves the snapshot itself through
``huggingface_hub.snapshot_download`` (a direct import: model2vec's own
``tokenizers>=0.20`` dependency requires ``huggingface-hub`` unconditionally,
so it is always present alongside model2vec, not merely an incidental
transitive), pinning the revision and rooting the download under the
app-controlled cache directory there, then hands ``from_pretrained`` the
resolved LOCAL directory path. ``model2vec.persistence._resolve_folder``
returns an existing local directory unchanged before any network or
``force_download`` branch runs, so both guarantees hold regardless of which
keyword arguments the installed model2vec's own ``from_pretrained`` accepts.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Sequence
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

    Resolves the snapshot through ``huggingface_hub.snapshot_download`` first
    (offline-first: a complete snapshot already cached under ``cache_dir``, or
    under the default hub cache when ``cache_dir`` is ``None``, loads with no
    network access; only a cold or incomplete cache falls through to a live
    fetch), then hands ``model2vec.StaticModel.from_pretrained`` the resolved
    local directory path rather than the bare model id. Both ``revision`` and
    ``cache_dir`` are therefore load-bearing on every model2vec version,
    independent of whether the installed ``from_pretrained`` accepts either
    as a keyword.

    Args:
        model_id: The model2vec model to load.
        revision: The pinned model revision to resolve and load.
        cache_dir: Optional app-controlled cache directory for the download;
            ``None`` falls back to ``huggingface_hub``'s own default cache.

    Returns:
        The loaded model narrowed to the embedding protocol used here.

    Raises:
        CorpusSearchDependencyError: If ``model2vec`` or ``huggingface_hub``
            is not installed.
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
    try:
        # huggingface_hub is model2vec's own transitive dependency (via
        # tokenizers>=0.20, which requires huggingface-hub unconditionally),
        # imported directly here so the loader owns snapshot resolution
        # instead of depending on model2vec's own from_pretrained kwarg
        # surface, which accepts neither ``revision`` nor ``cache_dir`` on
        # the pinned model2vec range.
        huggingface_hub = importlib.import_module("huggingface_hub")
        hub_errors = importlib.import_module("huggingface_hub.errors")
    except ImportError as exc:
        raise CorpusSearchDependencyError(
            "the corpus-search semantic stack (huggingface_hub) is not installed",
            context={"model_id": model_id, "dependency": "huggingface_hub"},
            suggestion=SEARCH_EXTRA_HINT,
        ) from exc

    loaded = _resolve_and_load_snapshot(
        model_id,
        revision=revision,
        cache_dir=cache_dir,
        snapshot_download=huggingface_hub.snapshot_download,
        local_entry_not_found=hub_errors.LocalEntryNotFoundError,
        from_pretrained=model2vec.StaticModel.from_pretrained,
    )
    if not isinstance(loaded, StaticEmbeddingModel):
        raise CorpusSearchDependencyError(
            "the installed model2vec StaticModel lacks the required encode method",
            context={"model_id": model_id, "dependency": "model2vec"},
            suggestion=SEARCH_EXTRA_HINT,
        )
    return loaded


def _resolve_and_load_snapshot(
    model_id: str,
    *,
    revision: str,
    cache_dir: Path | None,
    snapshot_download: Callable[..., str],
    local_entry_not_found: type[Exception],
    from_pretrained: Callable[[str], object],
) -> object:
    """Resolve a pinned model snapshot to a local path, then load it from there.

    Extracted from :func:`load_static_model` so the pass-through of
    ``revision`` and ``cache_dir`` into the snapshot resolution call, and the
    hand-off of the resolved LOCAL path (never the bare ``model_id``) into
    ``from_pretrained``, is independently testable against plain callables at
    this exact boundary, without touching ``huggingface_hub`` or ``model2vec``
    themselves.

    Args:
        model_id: The model2vec model to resolve.
        revision: The pinned model revision to resolve and load.
        cache_dir: Optional app-controlled cache directory for the download;
            ``None`` lets ``snapshot_download`` fall back to its own default
            cache.
        snapshot_download: ``huggingface_hub.snapshot_download`` or an
            equivalent callable accepting ``repo_id``, ``repo_type``,
            ``revision``, ``local_files_only``, and (when ``cache_dir`` is not
            ``None``) ``cache_dir``, returning a local directory path.
        local_entry_not_found: The exception ``snapshot_download`` raises when
            ``local_files_only=True`` and no complete cached snapshot exists
            at ``revision``.
        from_pretrained: ``model2vec.StaticModel.from_pretrained`` or an
            equivalent callable accepting a single local directory path.

    Returns:
        Whatever ``from_pretrained`` returns for the resolved local path.
    """
    snapshot_kwargs: dict[str, object] = {"repo_id": model_id, "repo_type": "model", "revision": revision}
    if cache_dir is not None:
        snapshot_kwargs["cache_dir"] = str(cache_dir)
    try:
        # Offline-first: a complete cached snapshot loads with zero network
        # access; only a cold or incomplete cache falls through to a live fetch.
        local_path = snapshot_download(local_files_only=True, **snapshot_kwargs)
    except local_entry_not_found:
        local_path = snapshot_download(local_files_only=False, **snapshot_kwargs)
    return from_pretrained(local_path)


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
