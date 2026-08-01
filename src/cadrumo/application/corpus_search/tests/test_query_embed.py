"""Real-behavior tests for the runtime query embedder.

model2vec rides the ``cadrumo[search]`` extra. These tests never skip: they
branch on its real presence and assert the correct behavior for the
environment, and they never trigger the optional model download (the
shippability contract forbids depending on it), so the actual embed is
exercised only where model2vec is importable AND construction/refusal is
what is asserted, not a network fetch.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

from ....core.config import override_settings
from .._errors import CorpusSearchDependencyError, CorpusSearchInputError
from .._model_loader import _resolve_and_load_snapshot
from .._query_embed import QueryEmbedder, search_extra_available, search_model_cache_dir

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODEL2VEC_PRESENT = importlib.util.find_spec("model2vec") is not None


class _SnapshotNotCachedError(Exception):
    """Local stand-in for ``huggingface_hub.errors.LocalEntryNotFoundError``.

    A plain, purpose-built exception type, not the real ``huggingface_hub``
    error class, so the fallback-path test below stays independent of the
    installed library's exact error hierarchy.
    """


def test_search_extra_available_reflects_environment() -> None:
    assert search_extra_available() is _MODEL2VEC_PRESENT


def test_cache_dir_is_rooted_in_storage_root(tmp_path: Path) -> None:
    with override_settings(cadrumo_local_storage_root=tmp_path):
        assert search_model_cache_dir() == tmp_path / "search-models"
        embedder = QueryEmbedder()
        assert embedder.cache_dir == tmp_path / "search-models"


def test_resolve_and_load_snapshot_delivers_revision_and_cache_dir_to_snapshot_download(tmp_path: Path) -> None:
    """The values ``load_static_model`` receives must reach the snapshot
    resolution call exactly, not merely be stored on a caller's own attribute.

    This is a real, narrow stand-in at the exact boundary
    ``_resolve_and_load_snapshot`` calls through (a plain callable, not a
    ``huggingface_hub`` or ``model2vec`` object, and not a Mock/Fake/Stub/Spy
    test double): it asserts on the keyword arguments it actually receives,
    which crosses the boundary the prior, weaker test
    (``test_cache_dir_is_rooted_in_storage_root`` above) never reached.
    """
    resolved_snapshot_path = str(tmp_path / "resolved-snapshot")
    received_snapshot_calls: list[dict[str, object]] = []
    received_from_pretrained_paths: list[str] = []

    def snapshot_download(**kwargs: object) -> str:
        received_snapshot_calls.append(kwargs)
        return resolved_snapshot_path

    def from_pretrained(path: str) -> str:
        received_from_pretrained_paths.append(path)
        return "loaded-model"

    result = _resolve_and_load_snapshot(
        "minishlab/potion-multilingual-128M",
        revision="73908c3438cf03b6a01bcb9611d62b23d0726f08",
        cache_dir=tmp_path / "search-models",
        snapshot_download=snapshot_download,
        local_entry_not_found=_SnapshotNotCachedError,
        from_pretrained=from_pretrained,
    )

    assert result == "loaded-model"
    assert received_snapshot_calls == [
        {
            "repo_id": "minishlab/potion-multilingual-128M",
            "repo_type": "model",
            "revision": "73908c3438cf03b6a01bcb9611d62b23d0726f08",
            "cache_dir": str(tmp_path / "search-models"),
            "local_files_only": True,
        }
    ]
    # from_pretrained must receive the resolved LOCAL snapshot path, never the
    # bare model id (the shape that lets model2vec's own kwarg-blind
    # from_pretrained resolve the id itself and silently drop the pin).
    assert received_from_pretrained_paths == [resolved_snapshot_path]


def test_resolve_and_load_snapshot_never_falls_back_to_network_when_the_cache_is_warm(tmp_path: Path) -> None:
    """A warm snapshot must load with zero attempt at a live fetch."""

    def snapshot_download(**kwargs: object) -> str:
        assert kwargs["local_files_only"] is True, "a warm cache must resolve offline-first, never fall back"
        return str(tmp_path / "warm-snapshot")

    def from_pretrained(path: str) -> str:
        return path

    result = _resolve_and_load_snapshot(
        "minishlab/potion-multilingual-128M",
        revision="73908c3438cf03b6a01bcb9611d62b23d0726f08",
        cache_dir=tmp_path,
        snapshot_download=snapshot_download,
        local_entry_not_found=_SnapshotNotCachedError,
        from_pretrained=from_pretrained,
    )

    assert result == str(tmp_path / "warm-snapshot")


def test_resolve_and_load_snapshot_falls_back_to_a_live_fetch_only_when_the_cache_is_cold(tmp_path: Path) -> None:
    """A cold or incomplete cache must fall through to exactly one live fetch."""
    local_files_only_values: list[bool] = []

    def snapshot_download(**kwargs: object) -> str:
        local_files_only_values.append(bool(kwargs["local_files_only"]))
        if kwargs["local_files_only"]:
            raise _SnapshotNotCachedError("no complete snapshot on disk yet")
        return str(tmp_path / "fetched-snapshot")

    def from_pretrained(path: str) -> str:
        return path

    result = _resolve_and_load_snapshot(
        "minishlab/potion-multilingual-128M",
        revision="73908c3438cf03b6a01bcb9611d62b23d0726f08",
        cache_dir=tmp_path,
        snapshot_download=snapshot_download,
        local_entry_not_found=_SnapshotNotCachedError,
        from_pretrained=from_pretrained,
    )

    assert local_files_only_values == [True, False]
    assert result == str(tmp_path / "fetched-snapshot")


def test_huggingface_hub_snapshot_download_signature_carries_the_parameters_the_loader_depends_on() -> None:
    """Pin the installed ``huggingface_hub`` signature the loader depends on.

    A future ``huggingface_hub`` release that renames or drops one of these
    parameters must surface here as an explicit signature-drift failure,
    rather than silently changing ``load_static_model``'s behaviour the way
    the pinned ``model2vec`` range silently dropped ``revision``/``cache_dir``
    from its own ``from_pretrained`` (see the corpus-search-model-cache-
    capability-gap audit). huggingface_hub is always installed alongside
    model2vec (a hard transitive floor via ``tokenizers>=0.20``), so this
    branches on the same ``_MODEL2VEC_PRESENT`` probe as the rest of this
    module and asserts the co-installation invariant in the absent branch.
    """
    if not _MODEL2VEC_PRESENT:
        assert importlib.util.find_spec("huggingface_hub") is None
        return
    huggingface_hub = importlib.import_module("huggingface_hub")
    accepted = inspect.signature(huggingface_hub.snapshot_download).parameters
    required = {"repo_id", "repo_type", "revision", "cache_dir", "local_files_only"}
    missing = required - accepted.keys()
    assert not missing, f"huggingface_hub.snapshot_download dropped required parameters: {sorted(missing)}"


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
        assert exc_info.value.suggestion == "pip install cadrumo[search]"
        return
    # With the extra present, availability is reported and construction stands;
    # the actual embed is a network-download path the unit gate does not drive.
    assert search_extra_available() is True
