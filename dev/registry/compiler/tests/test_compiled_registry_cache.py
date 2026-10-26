"""Strict-validation contract for the compiled-registry cache.

The cache persists the compiled ``(modelos, catalogues)`` set so a warm process
skips the TOML parse, but it must never become a second authority: a hit may only
ever serve a byte-integral payload of exactly the compiled shape, and any mutated,
foreign, or corrupt file is refused and deleted so the loader recompiles from TOML.
These tests exercise the real module against the real bundled tree and a real
test-owned cache directory; only the cache directory is isolated.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from cadrumo.core.frozen_mapping import FrozenMapping
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.tests.env_scope import scoped_env_var

from .._compiled_cache import _COMPILED_CACHE_SCHEMA_VERSION, _FRAME_SEPARATOR, _payload_digest
from ..compiled_cache import (
    CompiledRegistryPayload,
    compiled_cache_path,
    load_compiled_registry_cache,
    store_compiled_registry_cache,
)
from ..loader import clear_registry_tree_cache, load_registry_tree
from ..loader_fingerprints import clear_fingerprint_cache, collect_registry_tree_fingerprints

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _bundled_payload() -> tuple[Path, tuple[tuple[str, int, int, str], ...], CompiledRegistryPayload]:
    """Compile the real bundled registry once and return its root, fingerprints, and payload."""
    clear_fingerprint_cache()
    root = bundled_path("registry", "aeat").resolve()
    fingerprints = collect_registry_tree_fingerprints(root)
    payload = load_registry_tree(root)
    assert payload[0], "sanity: the bundled tree must compile at least one modelo"
    return root, fingerprints, payload


def test_store_then_load_roundtrips_the_bundled_compiled_registry(tmp_path: Path) -> None:
    """A stored payload loads back strict-equal; an empty cache dir is a cold miss."""
    root, fingerprints, payload = _bundled_payload()
    cache_dir = tmp_path / "compiled-cache"
    cache_dir.mkdir()

    with scoped_env_var("CADRUMO_REGISTRY_DISK_CACHE_DIR", str(cache_dir)):
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

    with scoped_env_var("CADRUMO_REGISTRY_DISK_CACHE_DIR", str(cache_dir)):
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

    with scoped_env_var("CADRUMO_REGISTRY_DISK_CACHE_DIR", str(cache_dir)):
        path = compiled_cache_path(root, fingerprints)
        path.parent.mkdir(parents=True, exist_ok=True)
        # A frame with a valid schema version and a matching digest, but a foreign
        # payload object -- integrity passes, the structural type-check must not.
        foreign_bytes = pickle.dumps(("not", "a", "compiled", "registry"), protocol=pickle.HIGHEST_PROTOCOL)
        path.write_bytes(
            _FRAME_SEPARATOR.join(
                (_COMPILED_CACHE_SCHEMA_VERSION, _payload_digest(foreign_bytes), foreign_bytes),
            ),
        )

        assert load_compiled_registry_cache(root, fingerprints) is None
        assert not path.is_file()


def test_a_well_framed_pre_schema_pydantic_payload_is_deleted_not_hydrated(tmp_path: Path) -> None:
    """A stale pickle with today's class names cannot bypass current schema shape.

    Pickle does not run Pydantic validation when it restores an instance.  Plant
    the exact failure mode from adding ``supported_filing_years``: a digest-valid
    cache whose catalogue object predates that field.  The warm loader must delete
    it, never add the missing default in memory or serve an eventual AttributeError.
    """
    root, fingerprints, payload = _bundled_payload()
    cache_dir = tmp_path / "compiled-cache"
    cache_dir.mkdir()
    modelos, catalogues = payload
    stale_catalogues = catalogues.model_copy(deep=True)
    stale_catalogues.__dict__.pop("supported_filing_years")

    with scoped_env_var("CADRUMO_REGISTRY_DISK_CACHE_DIR", str(cache_dir)):
        path = compiled_cache_path(root, fingerprints)
        path.parent.mkdir(parents=True, exist_ok=True)
        store_compiled_registry_cache(root, fingerprints, (modelos, stale_catalogues))

        assert load_compiled_registry_cache(root, fingerprints) is None
        assert not path.exists(), "a stale Pydantic object must be deleted, not compatibility-hydrated"


def test_a_nested_pre_qualifier_deadline_window_is_deleted_not_served(tmp_path: Path) -> None:
    """The current-shape walk reaches deadline rows nested below revisions."""
    root, fingerprints, payload = _bundled_payload()
    cache_dir = tmp_path / "compiled-cache"
    cache_dir.mkdir()
    modelos = list(payload[0])
    modelo_index = next(
        index
        for index, modelo in enumerate(modelos)
        if any(revision.deadline_windows for revision in modelo.revisions.values())
    )
    live_modelo = modelos[modelo_index]
    revision_key = next(key for key, revision in live_modelo.revisions.items() if revision.deadline_windows)
    revision = live_modelo.revisions[revision_key]
    window = revision.deadline_windows[0]
    # A field the current shape REQUIRES, chosen from the live model rather than
    # named here: an optional field can be absent legitimately, so popping one
    # would plant no pre-qualifier object at all and the walk would rightly
    # serve the cache.
    missing = next(name for name, field in type(window).model_fields.items() if field.is_required())
    # Rebuilt member by member rather than mutated through a deep copy.
    # ``model_copy(deep=True)`` does NOT reach this window: ``revisions`` is a
    # ``FrozenMapping``, whose ``__deepcopy__`` returns itself on the premise
    # that its entries are immutable, so the "copy" shares every revision with
    # the live tree. Popping through ``__dict__`` then walks around the frozen
    # guard and strips the required field off the registry the in-process loader
    # memo is still serving, and every later test in the process pickles that
    # corrupted payload and is refused by the very gate under test here.
    stale_window = window.model_copy()
    stale_window.__dict__.pop(missing)
    stale_revision = revision.model_copy(update={"deadline_windows": (stale_window, *revision.deadline_windows[1:])})
    modelos[modelo_index] = live_modelo.model_copy(
        update={"revisions": FrozenMapping({**dict(live_modelo.revisions), revision_key: stale_revision})},
    )
    assert missing in live_modelo.revisions[revision_key].deadline_windows[0].__dict__, (
        "the planted defect must not reach the live registry the loader memo still serves"
    )

    with scoped_env_var("CADRUMO_REGISTRY_DISK_CACHE_DIR", str(cache_dir)):
        path = compiled_cache_path(root, fingerprints)
        path.parent.mkdir(parents=True, exist_ok=True)
        store_compiled_registry_cache(root, fingerprints, (tuple(modelos), payload[1]))

        assert load_compiled_registry_cache(root, fingerprints) is None
        assert not path.exists(), "a pre-qualifier deadline object must never reach validation"


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

    with scoped_env_var("CADRUMO_REGISTRY_DISK_CACHE_DIR", str(cache_dir)):
        clear_registry_tree_cache()
        clear_fingerprint_cache()
        root = bundled_path("registry", "aeat").resolve()
        fingerprints = collect_registry_tree_fingerprints(root)

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
        clear_registry_tree_cache()
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


def _with_bumped_mtimes(
    fingerprints: tuple[tuple[str, int, int, str], ...],
) -> tuple[tuple[str, int, int, str], ...]:
    """Restate every row with a later timestamp and identical path, size and digest.

    This is what a branch switch, a checkout or a rewrite of identical bytes
    leaves behind: the tree's CONTENT is untouched and only the stat timestamps
    moved.
    """
    return tuple((path, size, modified_ns + 1_000_000_000, digest) for path, size, modified_ns, digest in fingerprints)


def test_an_mtime_only_touch_reuses_the_compiled_payload(tmp_path: Path) -> None:
    """A tree whose bytes are unchanged must not pay a second compile.

    Keyed on mtime, the same declarations stored a SECOND 51 MB pickle under a
    new key and evicted a genuinely distinct entry out of the count-bound store,
    while every process that met the touched tree paid a full cold compile.
    """
    root, fingerprints, payload = _bundled_payload()
    touched = _with_bumped_mtimes(fingerprints)
    assert touched != fingerprints, "sanity: the perturbation must change the fingerprint rows"

    cache_dir = tmp_path / "compiled-cache"
    cache_dir.mkdir()
    with scoped_env_var("CADRUMO_REGISTRY_DISK_CACHE_DIR", str(cache_dir)):
        store_compiled_registry_cache(root, fingerprints, payload)

        # One file, one key: the touched tree addresses the payload already held.
        assert compiled_cache_path(root, touched) == compiled_cache_path(root, fingerprints)
        served = load_compiled_registry_cache(root, touched)
        assert served is not None
        assert served[0] == payload[0]
        assert served[1] == payload[1]
        assert len(list(cache_dir.glob("*.pkl"))) == 1, "an mtime touch must not store a second copy"


def test_a_content_change_under_an_unchanged_timestamp_is_still_a_miss(tmp_path: Path) -> None:
    """Detector teeth: dropping mtime must not blind the key to content.

    Both perturbations below leave every timestamp alone, so a key that leaned
    on mtime would serve the stale payload for either.
    """
    root, fingerprints, payload = _bundled_payload()
    first_path, first_size, first_modified_ns, first_digest = fingerprints[0]

    edited_bytes = ((first_path, first_size, first_modified_ns, f"{first_digest[:-1]}0"), *fingerprints[1:])
    edited_size = ((first_path, first_size + 1, first_modified_ns, first_digest), *fingerprints[1:])
    removed_row = fingerprints[1:]

    cache_dir = tmp_path / "compiled-cache"
    cache_dir.mkdir()
    with scoped_env_var("CADRUMO_REGISTRY_DISK_CACHE_DIR", str(cache_dir)):
        store_compiled_registry_cache(root, fingerprints, payload)
        for label, perturbed in (
            ("content digest", edited_bytes),
            ("byte size", edited_size),
            ("tree membership", removed_row),
        ):
            assert perturbed != fingerprints, f"sanity: the {label} perturbation must change the rows"
            assert compiled_cache_path(root, perturbed) != compiled_cache_path(root, fingerprints), (
                f"a changed {label} must key to a different cache entry"
            )
            assert load_compiled_registry_cache(root, perturbed) is None, (
                f"a changed {label} must be a cold miss, never the stale payload"
            )
