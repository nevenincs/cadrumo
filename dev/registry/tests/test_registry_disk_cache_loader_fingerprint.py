"""Public contract coverage for the compiled-registry cache identity."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.core.config import override_settings
from cadrumo.core.resources.bundled_data import bundled_path

from ..compiler.compiled_cache import compiled_cache_path, loader_code_fingerprint
from ..compiler.loader import clear_registry_tree_cache, load_registry_tree
from ..compiler.loader_fingerprints import clear_fingerprint_cache, collect_registry_tree_fingerprints

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_compiled_cache_path_changes_when_the_tree_fingerprint_changes(tmp_path: Path) -> None:
    """Different source fingerprints cannot share a compiled-cache file."""
    root = tmp_path / "registry"
    first = ((str(root / "modelos" / "999.toml"), 10, 123, "digest-a"),)
    second = ((str(root / "modelos" / "999.toml"), 11, 123, "digest-b"),)

    with override_settings(cadrumo_registry_disk_cache_dir=tmp_path / "cache"):
        first_path = compiled_cache_path(root, first)
        second_path = compiled_cache_path(root, second)
        assert first_path != second_path
        assert first_path == compiled_cache_path(root, first)


def test_loader_code_fingerprint_is_a_stable_nonempty_sha256() -> None:
    """The public loader fingerprint is a real 64-hex SHA-256 digest."""
    fingerprint = loader_code_fingerprint()
    assert len(fingerprint) == 64
    assert all(character in "0123456789abcdef" for character in fingerprint)
    assert loader_code_fingerprint() == fingerprint


def test_loader_code_fingerprint_is_deferred_until_first_use() -> None:
    """Importing the public cache module does not hash source eagerly."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from dev.registry.compiler.compiled_cache import loader_code_fingerprint; "
                "print(loader_code_fingerprint.cache_info().currsize)"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "0"


def test_loader_reuses_the_publicly_addressable_compiled_cache(tmp_path: Path) -> None:
    """A warm public loader call reuses the cache for an unchanged bundled tree."""
    cache_dir = tmp_path / "registry-cache"
    root = bundled_path("registry", "aeat").resolve()
    with override_settings(cadrumo_registry_disk_cache_dir=cache_dir):
        clear_registry_tree_cache()
        clear_fingerprint_cache()
        fingerprints = collect_registry_tree_fingerprints(root)
        first = load_registry_tree(root)
        path = compiled_cache_path(root, fingerprints)
        assert path.is_file()

        clear_registry_tree_cache()
        second = load_registry_tree(root)
        assert second == first
