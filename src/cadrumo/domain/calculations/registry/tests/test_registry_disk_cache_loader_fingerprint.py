"""The registry disk-cache key binds a fingerprint of the loader/compiler source.

The disk cache stores COMPILED ``(modelos, catalogues)`` objects, but the tree
fingerprint keys only the TOML inputs. A loader/compiler/schema code change that
produces different compiled objects from IDENTICAL TOML would otherwise serve a
stale pickle from a prior session -- the shared OS temp dir persists across
sessions and code changes, so a pre-change pickle keyed by an unchanged tree
fingerprint (and a hand-maintained schema-version string a developer forgot to
bump) is served for the current loader. These tests pin the fix: the cache key
folds in a content hash of the registry package source, so a pickle written under
a different loader-code state can never be served.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .....tests.env_scope import scoped_env_var
from .._loader import (
    _LOADER_CODE_FINGERPRINT,
    _collect_registry_tree_fingerprints,
    _load_registry_tree_cached,
    _registry_disk_cache_key,
    clear_fingerprint_cache,
    load_registry_tree,
)
from .._loader_cache import REGISTRY_DISK_CACHE_DIR_ENV_VAR

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_cache_key_differs_when_loader_code_fingerprint_differs() -> None:
    """Two loader-code states yield different keys for identical tree inputs.

    This is the invariant that closes the stale-pickle gap: because the loader
    source hash is part of the key, a change to the compilation logic yields a
    new key and the pre-change pickle is simply never looked up.
    """
    root = "/registry/root"
    fingerprints = (("a/b.toml", 10, 123), ("c/d.toml", 20, 456))

    key_a = _registry_disk_cache_key(root, fingerprints, loader_code_fingerprint="loader-vA")
    key_b = _registry_disk_cache_key(root, fingerprints, loader_code_fingerprint="loader-vB")
    assert key_a != key_b

    # Deterministic for a fixed loader fingerprint and fixed tree inputs.
    assert key_a == _registry_disk_cache_key(root, fingerprints, loader_code_fingerprint="loader-vA")

    # The production key uses the real module-level source fingerprint.
    assert _registry_disk_cache_key(root, fingerprints) == _registry_disk_cache_key(
        root,
        fingerprints,
        loader_code_fingerprint=_LOADER_CODE_FINGERPRINT,
    )


def test_loader_code_fingerprint_is_a_stable_nonempty_sha256() -> None:
    """The module-level loader fingerprint is a real 64-hex sha256 digest."""
    assert isinstance(_LOADER_CODE_FINGERPRINT, str)
    assert len(_LOADER_CODE_FINGERPRINT) == 64
    assert all(character in "0123456789abcdef" for character in _LOADER_CODE_FINGERPRINT)


def test_stale_loader_pickle_is_not_served_while_current_key_pickle_is(tmp_path: Path) -> None:
    """End-to-end: a different-loader-state pickle is ignored; the current one is honoured.

    The CONTROL half proves the disk cache is genuinely live (a poison pickle at
    the CURRENT key is served, so a matching key IS read). The REGRESSION half
    proves the fix: the same poison, keyed instead to a DIFFERENT loader-code
    fingerprint, is NOT served -- the loader recompiles the real content. Real
    filesystem, real pickle read/write, real load path; only the poison payload
    and the cache directory are test-owned.
    """
    isolated_cache_dir = tmp_path / "registry-disk-cache"
    isolated_cache_dir.mkdir()

    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV_VAR, str(isolated_cache_dir)):
        _load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()

        resolved = bundled_path("registry", "aeat").resolve()
        root_str = str(resolved)

        # A real compile obtains real catalogues for a structurally-valid poison
        # and writes the current-key pickle.
        modelos, catalogues = load_registry_tree(resolved)
        assert modelos, "sanity: the bundled tree must compile at least one modelo"

        fingerprints = _collect_registry_tree_fingerprints(resolved)
        current_key = _registry_disk_cache_key(root_str, fingerprints)
        current_path = isolated_cache_dir / f"cadrumo_registry_{current_key}.pkl"
        assert current_path.is_file(), "the real compile must have written the current-key pickle"

        # CONTROL: poison the CURRENT-key pickle. A matching-key pickle IS read,
        # so the empty-modelos poison is served -- proving the cache is live and
        # the regression assertion below is meaningful.
        current_path.write_bytes(pickle.dumps(((), catalogues)))
        _load_registry_tree_cached.cache_clear()
        served_modelos, _served_catalogues = load_registry_tree(resolved)
        assert served_modelos == (), "control: a current-key poison pickle must be served (the disk cache is live)"

        # REGRESSION: move the poison to a key computed with a DIFFERENT loader
        # fingerprint (a pre-change loader state). The current load must ignore it
        # and recompile the real content.
        current_path.unlink()
        stale_key = _registry_disk_cache_key(
            root_str,
            fingerprints,
            loader_code_fingerprint="pre-change-loader-state",
        )
        assert stale_key != current_key
        stale_path = isolated_cache_dir / f"cadrumo_registry_{stale_key}.pkl"
        stale_path.write_bytes(pickle.dumps(((), catalogues)))

        _load_registry_tree_cached.cache_clear()
        real_modelos, _real_catalogues = load_registry_tree(resolved)
        assert real_modelos, (
            "a pickle keyed to a different loader-code state must not be served; "
            "the loader must recompile the real content instead of serving the stale pickle"
        )
