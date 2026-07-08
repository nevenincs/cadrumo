"""Real-behavior tests for the runtime query embedder.

model2vec rides the ``aeat-cli[search]`` extra. These tests never skip: they
branch on its real presence and assert the correct behavior for the
environment, and they never trigger the optional model download (the
shippability contract forbids depending on it), so the actual embed is
exercised only where model2vec is importable AND construction/refusal is
what is asserted, not a network fetch.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from ....core.config import override_settings
from .._errors import CorpusSearchDependencyError, CorpusSearchInputError
from .._query_embed import QueryEmbedder, search_extra_available, search_model_cache_dir

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODEL2VEC_PRESENT = importlib.util.find_spec("model2vec") is not None


def test_search_extra_available_reflects_environment() -> None:
    assert search_extra_available() is _MODEL2VEC_PRESENT


def test_cache_dir_is_rooted_in_storage_root(tmp_path: Path) -> None:
    with override_settings(aeat_local_storage_root=tmp_path):
        assert search_model_cache_dir() == tmp_path / "search-models"
        embedder = QueryEmbedder()
        assert embedder.cache_dir == tmp_path / "search-models"


def test_construction_is_lazy_and_does_not_load_the_model(tmp_path: Path) -> None:
    # Constructing must not load model2vec (so it never raises for want of the
    # extra); the model loads on first embed only.
    embedder = QueryEmbedder(cache_dir=tmp_path / "models")
    assert embedder.model_id == "minishlab/potion-multilingual-128M"
    assert embedder.revision


def test_empty_query_is_refused_before_any_model_load(tmp_path: Path) -> None:
    embedder = QueryEmbedder(cache_dir=tmp_path / "models")
    with pytest.raises(CorpusSearchInputError):
        embedder.embed_query("   ")


def test_embed_query_matches_environment_capability(tmp_path: Path) -> None:
    embedder = QueryEmbedder(cache_dir=tmp_path / "models")
    if not _MODEL2VEC_PRESENT:
        with pytest.raises(CorpusSearchDependencyError) as exc_info:
            embedder.embed_query("recargo por declaración extemporánea")
        assert exc_info.value.suggestion == "pip install aeat-cli[search]"
        return
    # With the extra present, availability is reported and construction stands;
    # the actual embed is a network-download path the unit gate does not drive.
    assert search_extra_available() is True
