"""Strict-validation contract for the compiled-registry cache.

The cache persists the compiled ``(modelos, catalogues)`` set so a warm process
skips the TOML parse, but it must never become a second authority: a hit may only
ever serve a byte-integral payload of exactly the compiled shape, and any mutated,
foreign, or corrupt file is refused and deleted so the loader recompiles from TOML.
These tests exercise the real module against the real bundled tree and a real
test-owned cache directory; only the cache directory is isolated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .....tests.env_scope import scoped_env_var
from .._compiled_cache import (
    _encode_frame,
    compiled_cache_path,
    load_compiled_registry_cache,
    store_compiled_registry_cache,
)
from .._loader import (
    _collect_registry_tree_fingerprints,
    _load_registry_tree_cached,
    clear_fingerprint_cache,
    load_registry_tree,
)
from .._loader_cache import REGISTRY_DISK_CACHE_DIR_ENV_VAR

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _bundled_payload() -> tuple[Path, tuple[tuple[str, int, int], ...], object]:
    """Compile the real bundled registry once and return its root, fingerprints, and payload."""
    clear_fingerprint_cache()
    root = bundled_path("registry", "aeat").resolve()
    fingerprints = _collect_registry_tree_fingerprints(root)
    payload = load_registry_tree(root)
    assert payload[0], "sanity: the bundled tree must compile at least one modelo"
    return root, fingerprints, payload


def test_store_then_load_roundtrips_the_bundled_compiled_registry(tmp_path: Path) -> None:
    """A stored payload loads back strict-equal; an empty cache dir is a cold miss."""
    root, fingerprints, payload = _bundled_payload()
    cache_dir = tmp_path / "compiled-cache"
    cache_dir.mkdir()

    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV_VAR, str(cache_dir)):
        assert load_compiled_registry_cache(root, fingerprints) is None

        store_compiled_registry_cache(root, fingerprints, payload)
        assert compiled_cache_path(root, fingerprints).is_file()

        loaded = load_compiled_registry_cache(root, fingerprints)
        assert loaded is not None
        modelos, catalogues = loaded
        # Strict pydantic equality across the pickle boundary, both members.
        assert modelos == payload[0]
        assert catalogues == payload[1]


def test_a_byte_mutation_is_refused_and_the_file_deleted(tmp_path: Path) -> None:
    """Flipping any payload byte breaks the integrity digest, so load refuses and deletes."""
    root, fingerprints, payload = _bundled_payload()
    cache_dir = tmp_path / "compiled-cache"
    cache_dir.mkdir()

    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV_VAR, str(cache_dir)):
        store_compiled_registry_cache(root, fingerprints, payload)
        path = compiled_cache_path(root, fingerprints)

        corrupted = bytearray(path.read_bytes())
        corrupted[-1] ^= 0xFF
        path.write_bytes(bytes(corrupted))

        assert load_compiled_registry_cache(root, fingerprints) is None
        assert not path.is_file(), "a mutated cache file must be deleted, never served"


def test_a_foreign_shaped_payload_is_refused_and_deleted(tmp_path: Path) -> None:
    """A well-framed, digest-valid file whose payload is not the compiled shape is refused.

    This proves the structural type gate: a file that deserialises cleanly but is
    not exactly ``(tuple[ModeloDefinition, ...], RegistryCatalogues)`` never
    reaches a caller as the compiled authority.
    """
    root, fingerprints, _payload = _bundled_payload()
    cache_dir = tmp_path / "compiled-cache"
    cache_dir.mkdir()

    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV_VAR, str(cache_dir)):
        path = compiled_cache_path(root, fingerprints)
        path.parent.mkdir(parents=True, exist_ok=True)
        # A frame with a valid schema version and a matching digest, but a foreign
        # payload object -- integrity passes, the structural type-check must not.
        path.write_bytes(_encode_frame(("not", "a", "compiled", "registry")))  # type: ignore[arg-type]

        assert load_compiled_registry_cache(root, fingerprints) is None
        assert not path.is_file()


def test_mutating_the_cache_through_the_loader_rebuilds_byte_equivalently_from_toml(tmp_path: Path) -> None:
    """Through the loader: a mutated on-disk cache is refused and TOML is recompiled.

    This is the never-a-second-authority proof. A cold
    ``load_registry_tree`` compiles from TOML and writes the cache; that result
    is the independent oracle. The on-disk cache is then mutated. A second load,
    with the in-process memo cleared so it must consult disk, must refuse the
    mutated cache (its integrity digest no longer matches), recompile from TOML,
    and return a payload byte-equivalent to the cold compile - the cache can
    never substitute a different authority for the one the TOML defines. A fresh
    valid cache replaces the poisoned one, so the mutation does not persist.
    """
    cache_dir = tmp_path / "compiled-cache"
    cache_dir.mkdir()

    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV_VAR, str(cache_dir)):
        _load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()
        root = bundled_path("registry", "aeat").resolve()
        fingerprints = _collect_registry_tree_fingerprints(root)

        # Cold compile from TOML into the empty cache dir; this is the oracle.
        reference_modelos, reference_catalogues = load_registry_tree(root)
        assert reference_modelos, "sanity: the bundled tree must compile at least one modelo"
        path = compiled_cache_path(root, fingerprints)
        assert path.is_file(), "the cold compile must have written the cache"

        # Mutate the on-disk cache so its embedded integrity digest no longer matches.
        corrupted = bytearray(path.read_bytes())
        corrupted[-1] ^= 0xFF
        path.write_bytes(bytes(corrupted))

        # Clear only the in-process memo so the next load must consult disk.
        _load_registry_tree_cached.cache_clear()
        rebuilt_modelos, rebuilt_catalogues = load_registry_tree(root)

        # The mutated cache was refused; the loader rebuilt from TOML byte-equivalently.
        assert rebuilt_modelos == reference_modelos
        assert rebuilt_catalogues == reference_catalogues

        # A fresh valid cache replaced the poisoned one, and it serves the real authority.
        assert path.is_file()
        reloaded = load_compiled_registry_cache(root, fingerprints)
        assert reloaded is not None
        assert reloaded[0] == reference_modelos
        assert reloaded[1] == reference_catalogues
