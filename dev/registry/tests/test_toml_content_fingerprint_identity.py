"""Detector coverage for content-addressed fingerprints of bundled authoring TOML."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ..compiler import loader_cache

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_bundled_authoring_toml_fingerprint_tracks_same_stat_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bundled-path status must never exempt a developer TOML from hashing."""
    registry_root = tmp_path / "package-data" / "registry" / "aeat"
    manifest = registry_root / "modelos" / "111" / "manifest.toml"
    manifest.parent.mkdir(parents=True)
    original = '[modelo]\nid = "111"\n'
    replacement = '[modelo]\nid = "222"\n'
    assert len(replacement.encode()) == len(original.encode())
    manifest.write_text(original, encoding="utf-8", newline="\n")

    def redirected_bundled_path(*parts: str) -> Path:
        assert parts == ("registry", "aeat")
        return registry_root

    try:
        with monkeypatch.context() as patch:
            patch.setattr(loader_cache, "bundled_path", redirected_bundled_path)
            loader_cache._bundled_registry_root.cache_clear()
            assert loader_cache._bundled_registry_root() == registry_root.resolve()

            before = loader_cache.toml_file_fingerprint(manifest)
            assert loader_cache._read_modelo_id(manifest, description="test manifest") == "111"

            original_stat = manifest.stat()
            manifest.write_text(replacement, encoding="utf-8", newline="\n")
            os.utime(manifest, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

            after = loader_cache.toml_file_fingerprint(manifest)
            assert manifest.stat().st_size == original_stat.st_size
            assert manifest.stat().st_mtime_ns == original_stat.st_mtime_ns
            assert before[:3] == after[:3]
            assert before[3] != after[3]
            assert loader_cache._read_modelo_id(manifest, description="test manifest") == "222"
    finally:
        loader_cache._bundled_registry_root.cache_clear()
