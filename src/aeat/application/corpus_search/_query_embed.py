"""Runtime query embedder (the live-query half of the R3 semantic stack).

The corpus vectors are precomputed at build time and ship as data
(:mod:`~application.corpus_search._embed_build`); the model is needed at
runtime ONLY to embed the operator's live query into the same vector space so a
cosine search can run.
This module owns that one live use of ``model2vec``, behind the capability-
gated ``aeat-cli[search]`` extra: absent the extra, :func:`search_extra_available`
reports ``False`` and the retrieval layer degrades to lexical-only, while
constructing/using a :class:`QueryEmbedder` refuses with the install hint.

The model download is app-controlled: the cache directory is rooted under the
Settings ``aeat_local_storage_root`` (``<root>/search-models``) rather than the
user's global Hugging Face cache, so a bundled Desktop Extension keeps its model
state inside the one app state root. The model is loaded lazily on first embed
and cached for the embedder's lifetime, so repeated queries pay the load once.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...core.config import Settings, load_settings
from ._embed_build import POTION_MODEL_ID, POTION_MODEL_REVISION
from ._errors import CorpusSearchInputError
from ._model_loader import load_static_model

if TYPE_CHECKING:
    import numpy as np

_SEARCH_MODEL_CACHE_SUBDIR = "search-models"


def search_extra_available() -> bool:
    """Return whether the semantic ``search`` extra (``model2vec``) is importable.

    The retrieval layer calls this to decide between hybrid and lexical-only
    degraded mode WITHOUT triggering a model load or download.
    """
    return importlib.util.find_spec("model2vec") is not None


def search_model_cache_dir(settings: Settings | None = None) -> Path:
    """Return the app-controlled model cache directory under the storage root."""
    resolved = settings or load_settings()
    return resolved.aeat_local_storage_root / _SEARCH_MODEL_CACHE_SUBDIR


class QueryEmbedder:
    """Embed live queries with the pinned potion static model.

    Construction records the model id, pinned revision, and app-controlled
    cache directory but does NOT load the model; the first :meth:`embed_query`
    loads it (refusing with the install hint when the extra is absent) and
    caches it for reuse.
    """

    def __init__(
        self,
        *,
        model_id: str = POTION_MODEL_ID,
        revision: str = POTION_MODEL_REVISION,
        cache_dir: Path | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._model_id = model_id
        self._revision = revision
        self._cache_dir = cache_dir if cache_dir is not None else search_model_cache_dir(settings)
        self._model: Any | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def revision(self) -> str:
        return self._revision

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    def _ensure_model(self) -> Any:
        if self._model is None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = load_static_model(self._model_id, revision=self._revision, cache_dir=self._cache_dir)
        return self._model

    def embed_query(self, text: str) -> np.ndarray:
        """Embed one query string into a 1-D float32 vector.

        Args:
            text: The free-text query.

        Returns:
            A 1-D float32 numpy vector in the corpus embedding space.

        Raises:
            CorpusSearchInputError: If ``text`` is blank.
            CorpusSearchDependencyError: If the ``search`` extra is absent.
        """
        import numpy as np

        cleaned = text.strip()
        if not cleaned:
            raise CorpusSearchInputError("query embedding requires non-empty text", context={"query": text})
        model = self._ensure_model()
        raw = model.encode([cleaned])
        vector = np.asarray(raw, dtype=np.float32).reshape(-1)
        return vector


__all__ = [
    "QueryEmbedder",
    "search_extra_available",
    "search_model_cache_dir",
]
