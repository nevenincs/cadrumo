"""Corpus source-text validation cache location and write behavior.

The corpus-text cache formerly lived at a fixed name in the shared OS temp
directory (``aeat_corpus_text_cache.json``), where two users or CI containers
on one host could clobber it. It now derives a per-user location under the
settings storage root (``<root>/cache/corpus-text/cadrumo_corpus_text_cache.json``).
These tests exercise the real files and the real read/merge/write path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....core.config import override_settings
from .._validate_evidence import (
    _CORPUS_TEXT_CACHE_FILENAME,
    _corpus_text_cache_path,
    _load_disk_cache,
    _write_disk_cache,
    reset_corpus_text_cache,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_cache_path_derives_under_cache_namespace(tmp_path: Path) -> None:
    with override_settings(cadrumo_local_storage_root=tmp_path / "state"):
        path = _corpus_text_cache_path()
    assert path == tmp_path / "state" / "cache" / "corpus-text" / "cadrumo_corpus_text_cache.json"
    assert _CORPUS_TEXT_CACHE_FILENAME == "cadrumo_corpus_text_cache.json"


def test_write_creates_the_derived_file_and_roundtrips(tmp_path: Path) -> None:
    cache_dir = tmp_path / "corpus-text"
    with override_settings(cadrumo_corpus_text_cache_dir=cache_dir):
        reset_corpus_text_cache()
        _write_disk_cache({"source:one": "normalised text one"})
        cache_file = cache_dir / "cadrumo_corpus_text_cache.json"
        assert cache_file.is_file(), "write must create the cache file under the derived directory"
        # No former OS-temp-named artifact is produced.
        assert not (cache_dir / "aeat_corpus_text_cache.json").exists()
        reset_corpus_text_cache()
        loaded = _load_disk_cache()
    assert loaded["source:one"] == "normalised text one"


def test_write_merges_concurrent_on_disk_entries(tmp_path: Path) -> None:
    """A write folds in entries a concurrent writer already committed to disk,
    so a parallel writer's key is not dropped by last-writer-wins."""
    cache_dir = tmp_path / "corpus-text"
    cache_dir.mkdir(parents=True)
    cache_file = cache_dir / "cadrumo_corpus_text_cache.json"
    # Simulate a sibling process that already committed its own key.
    cache_file.write_text(json.dumps({"sibling:key": "sibling value"}), encoding="utf-8")

    with override_settings(cadrumo_corpus_text_cache_dir=cache_dir):
        reset_corpus_text_cache()
        _write_disk_cache({"mine:key": "my value"})
        merged = json.loads(cache_file.read_text(encoding="utf-8"))

    assert merged == {"sibling:key": "sibling value", "mine:key": "my value"}
