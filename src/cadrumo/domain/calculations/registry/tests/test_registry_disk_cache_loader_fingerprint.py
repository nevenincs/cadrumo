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

The compiled objects also embed first-party types defined OUTSIDE the registry
package, whose source the package hash does not cover. That set is DERIVED from
the compiled models' own annotations rather than remembered, so these tests hold
the derivation from both ends: injected roots prove it DETECTS a newly embedded
type (and that the detection moves the key), and an independent walk of the real
compiled payload's object graph proves nothing the tree actually embeds escapes
it. The object walk is the ground truth the annotation walk is measured against;
a hand list could only ever be measured against its author's memory.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel

from .....core.auth_provider import AuthProviderKind
from .....core.config import override_settings
from .....core.directory_scan import scan_directory
from .....core.modelo import Modelo
from .....core.resources._boundary import bundled_path
from .._compiled_cache import (
    _CADRUMO_PACKAGE_DIR,
    _REGISTRY_PACKAGE_DIR,
    _classify_foreign_type,
    _compiled_payload_root_models,
    _compute_loader_code_fingerprint,
    _derive_embedded_foreign_types,
    _encode_frame,
    _registry_disk_cache_key,
    loader_code_fingerprint,
)
from .._loader_internals import _collect_registry_tree_fingerprints
from ..loader import _load_registry_tree_cached, load_registry_tree
from ..loader_fingerprints import clear_fingerprint_cache
from ..schema import ModeloDefinition, RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A first-party enum from a package the compiled payload does NOT embed today,
#: and whose defining module no already-derived type shares. Injecting it must
#: therefore add both a new marker and a new hashed source file.
_UNEMBEDDED_FOREIGN_ENUM = AuthProviderKind


def _derived_markers(roots: tuple[type[BaseModel], ...] | None = None) -> frozenset[str]:
    """Marker identities of every foreign type derived from ``roots``."""
    return frozenset(item.marker for item in _derive_embedded_foreign_types(roots))


def _marker_of(candidate: type) -> str:
    """The ``module.qualname`` identity the derivation records for ``candidate``."""
    return f"{candidate.__module__}.{candidate.__qualname__}"


def _foreign_types_in_object_graph(payload: object) -> frozenset[str]:
    """Walk ``payload``'s real object graph and return every foreign type it contains.

    The independent oracle for the annotation-driven derivation: it asks the
    COMPILED OBJECTS what types they are actually built from, which is what the
    pickle stream reconstructs and therefore what the cache key must cover. It
    shares only the in/out boundary predicate with production, never the walk.
    """
    found: set[str] = set()
    seen: set[int] = set()
    pending: list[object] = [payload]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        classified = _classify_foreign_type(type(item))
        if classified is not None:
            found.add(classified.marker)
        if isinstance(item, BaseModel):
            pending.extend(getattr(item, name, None) for name in type(item).model_fields)
        elif isinstance(item, str | bytes | int | float | bool | None.__class__):
            continue
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list | tuple | set | frozenset):
            pending.extend(item)
    return frozenset(found)


def test_cache_key_differs_when_loader_code_fingerprint_differs() -> None:
    """Two loader-code states yield different keys for identical tree inputs.

    This is the invariant that closes the stale-pickle gap: because the loader
    source hash is part of the key, a change to the compilation logic yields a
    new key and the pre-change pickle is simply never looked up.
    """
    root = "/registry/root"
    fingerprints = (("a/b.toml", 10, 123, "digest-a"), ("c/d.toml", 20, 456, "digest-b"))

    key_a = _registry_disk_cache_key(root, fingerprints, loader_code_fingerprint_override="loader-vA")
    key_b = _registry_disk_cache_key(root, fingerprints, loader_code_fingerprint_override="loader-vB")
    assert key_a != key_b

    # Deterministic for a fixed loader fingerprint and fixed tree inputs.
    assert key_a == _registry_disk_cache_key(root, fingerprints, loader_code_fingerprint_override="loader-vA")

    # The production key resolves the real source fingerprint lazily.
    assert _registry_disk_cache_key(root, fingerprints) == _registry_disk_cache_key(
        root,
        fingerprints,
        loader_code_fingerprint_override=loader_code_fingerprint(),
    )


def test_loader_code_fingerprint_is_a_stable_nonempty_sha256() -> None:
    """The loader fingerprint is a real 64-hex sha256 digest."""
    assert isinstance(loader_code_fingerprint(), str)
    assert len(loader_code_fingerprint()) == 64
    assert all(character in "0123456789abcdef" for character in loader_code_fingerprint())


def test_package_roots_are_the_real_directories() -> None:
    """The in/out boundary points at the real ``cadrumo`` and registry package dirs.

    The classification predicate walks ``parents[2]`` from the registry package
    to reach the ``cadrumo`` root. A package relocation that changed that depth
    would silently classify every first-party type as foreign (or none of them),
    so the depth is pinned rather than assumed.
    """
    assert _REGISTRY_PACKAGE_DIR.name == "registry"
    assert (_REGISTRY_PACKAGE_DIR / "_compiled_cache.py").is_file()
    assert _CADRUMO_PACKAGE_DIR.name == "cadrumo"
    assert (_CADRUMO_PACKAGE_DIR / "core").is_dir()
    assert _REGISTRY_PACKAGE_DIR.is_relative_to(_CADRUMO_PACKAGE_DIR)


def test_derived_embedded_types_all_resolve_to_first_party_sources_outside_the_registry() -> None:
    """Every derived type carries a real, readable, first-party, non-registry source file.

    A derived entry that no longer resolved would fold an ``unreadable:`` marker
    into the fingerprint instead of the definition's bytes, defeating the
    invalidation the derivation exists to provide. Also pins the in/out
    boundary: a registry-package type would be double-hashed, and a third-party
    one is not ours to invalidate on.
    """
    derived = _derive_embedded_foreign_types()
    assert derived, "the compiled payload embeds first-party types; deriving none means the walk is broken"
    for item in derived:
        assert item.source_path.is_file(), item.marker
        assert item.source_path.is_relative_to(_CADRUMO_PACKAGE_DIR), item.marker
        assert not item.source_path.is_relative_to(_REGISTRY_PACKAGE_DIR), item.marker
        assert item.relative_source == item.source_path.relative_to(_CADRUMO_PACKAGE_DIR).as_posix()


def test_derived_types_hash_their_private_defining_files_not_a_facade_init() -> None:
    """Period and TaxDomain hash their private DEFINING files, not a package ``__init__``.

    Anti-regression proof carried over from the facade-target fix: collapsing a
    re-exported type onto ``core/__init__.py`` would silently defeat
    invalidation when ``_period.py`` / ``_tax_domain.py`` change. Deriving from
    the type object rather than from an import path keeps that structural, but
    the assertion stays because the failure it guards is invisible otherwise.
    """
    resolved = {item.marker: item for item in _derive_embedded_foreign_types()}
    period = resolved["cadrumo.core.period.Period"]
    tax_domain = resolved["cadrumo.core.tax_domain.TaxDomain"]
    assert period.source_path.name == "period.py", period.source_path
    assert tax_domain.source_path.name == "_tax_domain.py", tax_domain.source_path


def test_loader_fingerprint_incorporates_embedded_foreign_module_source() -> None:
    """The fingerprint hashes the embedded foreign modules' bytes, not just the registry package.

    Recompute the fingerprint's registry-only half and confirm it differs from
    the full fingerprint, proving the foreign-module bytes genuinely contribute
    (so a change to ``core/aggregation.py``, ``domain/iva/_schema.py`` or any
    other derived definition invalidates the disk cache).
    """
    import hashlib

    registry_only = hashlib.sha256()
    package_dir = Path(__file__).resolve().parents[1]  # the registry package dir
    for path in scan_directory(package_dir, pattern="*.py", recursive=True, prune_directories=("tests",)):
        registry_only.update(path.relative_to(package_dir).as_posix().encode("utf-8"))
        registry_only.update(path.read_bytes())

    assert registry_only.hexdigest() != loader_code_fingerprint(), (
        "the loader fingerprint must fold in the embedded foreign-module source, not the registry package alone"
    )


def test_a_newly_embedded_foreign_type_is_derived_and_moves_the_fingerprint() -> None:
    """Injecting a root that embeds an unenrolled foreign type is DETECTED and re-keys the cache.

    The decisive anti-tautology proof. The old hand list could not fail this
    way: a type nobody remembered to enrol simply never entered the key, and no
    assertion anywhere flipped. Here the derivation is handed a root carrying a
    first-party type it does not already know, and both the derived set and the
    fingerprint must move.
    """
    assert _marker_of(_UNEMBEDDED_FOREIGN_ENUM) not in _derived_markers(), (
        "precondition: the injected enum must not already be embedded, or this proves nothing"
    )

    class _NewlyEmbeddingRoot(BaseModel):
        provider: _UNEMBEDDED_FOREIGN_ENUM  # type: ignore[valid-type]

    roots = (*_compiled_payload_root_models(), _NewlyEmbeddingRoot)
    assert _marker_of(_UNEMBEDDED_FOREIGN_ENUM) in _derived_markers(roots)
    assert _compute_loader_code_fingerprint(roots) != _compute_loader_code_fingerprint()


def test_a_root_embedding_nothing_foreign_leaves_the_fingerprint_unchanged() -> None:
    """The control: adding a root is not what moves the key -- the foreign type is.

    Without this, the proof above would also pass for a derivation that hashed
    the root COUNT, or anything else that happens to change when a root is
    appended.
    """

    class _StdlibOnlyRoot(BaseModel):
        label: str
        count: int

    roots = (*_compiled_payload_root_models(), _StdlibOnlyRoot)
    assert _derived_markers(roots) == _derived_markers()
    assert _compute_loader_code_fingerprint(roots) == _compute_loader_code_fingerprint()


def test_an_enum_reached_only_through_a_literal_is_derived() -> None:
    """A ``Literal`` of enum MEMBERS embeds the enum CLASS, and the derivation sees it.

    This is the exact hole that hid the core ``Modelo`` enum: the ledger
    selectors type their ``modelo`` field as ``Literal[Modelo.M100]``, so the
    annotation names only values while the compiled object pickles a real
    ``Modelo`` member. A walk that skipped ``Literal`` reported the type as
    absent.
    """

    class _LiteralOnlyRoot(BaseModel):
        provider: Literal[_UNEMBEDDED_FOREIGN_ENUM.CERTIFICATE]

    derived = _derived_markers((_LiteralOnlyRoot,))
    assert derived == frozenset({_marker_of(_UNEMBEDDED_FOREIGN_ENUM)})


def test_selector_models_contribute_types_the_schema_annotations_cannot_see() -> None:
    """The polymorphic ``selector`` field is an annotation hole the roots must close.

    ``DataBindingDefinition.selector`` is typed as an open ``BaseModel``, so a
    walk from the two schema roots alone cannot reach the concrete selector
    families or the IVA / modelo enums they embed. Enumerating the selector
    table through its own accessor is what closes it; dropping that would make
    this assertion flip.
    """
    schema_only = _derived_markers((ModeloDefinition, RegistryCatalogues))
    full = _derived_markers()

    # The claim is that the table CONTRIBUTES types the annotations cannot see,
    # so assert that contribution rather than pinning which types it is. This
    # named `Modelo`, and a peer adding `SourceReference.period_selector` made it
    # reachable from `RegistryCatalogues` by annotation alone -- a hole CLOSING,
    # which is the good direction, yet it reddened a test whose subject was
    # unaffected. A type migrating into annotation reach must not look like the
    # table having stopped contributing.
    table_only = full - schema_only
    assert schema_only < full, "the selector table contributed nothing the annotations miss"
    assert table_only, "the table-only contribution is empty; the polymorphic hole is unclosed or unreachable"
    # IvaCategory is the named specimen because the selector families embed it
    # and no schema annotation reaches it; it is asserted on both sides so a
    # derivation that simply returned everything would not satisfy this.
    assert "cadrumo.domain.iva.schema.IvaCategory" in table_only
    assert _marker_of(Modelo) in full


def test_every_foreign_type_in_the_compiled_payload_is_covered_by_the_derivation() -> None:
    """Ground truth: nothing the real compiled tree embeds escapes the cache key.

    The annotation walk is a MODEL of what the payload contains; this walks the
    payload itself and asserts the model covers it. A type present in the object
    graph but absent from the derived set is precisely the stale-cache hazard --
    its defining file could change while the key stood still.
    """
    payload = load_registry_tree(bundled_path("registry", "aeat").resolve())
    observed = _foreign_types_in_object_graph(payload)

    assert len(observed) > 10, "anti-vacuity: the compiled tree embeds many foreign types"
    assert _marker_of(Modelo) in observed, "anti-vacuity: the ledger selectors embed real Modelo members"
    assert "cadrumo.domain.iva.schema.IvaCategory" in observed, "anti-vacuity: the IVA selectors embed categories"

    missing = observed - _derived_markers()
    assert not missing, f"embedded in the compiled payload but absent from the cache key: {sorted(missing)}"


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

    # ``CADRUMO_REGISTRY_DISK_CACHE_DIR`` backs the Settings field
    # ``cadrumo_registry_disk_cache_dir``; ``load_settings()`` caches the
    # constructed ``Settings`` per active-profile pointer, so a plain
    # ``os.environ`` mutation is invisible to the in-process resolver once an
    # earlier call already built and cached a ``Settings`` instance.
    # ``override_settings`` is the mechanism that actually takes effect here.
    with override_settings(cadrumo_registry_disk_cache_dir=isolated_cache_dir):
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

        # CONTROL: poison the CURRENT-key cache with a well-framed, digest-valid
        # empty-modelos payload. A matching-key cache IS read, so the poison is
        # served -- proving the cache is live and the regression below meaningful.
        current_path.write_bytes(_encode_frame(((), catalogues)))
        _load_registry_tree_cached.cache_clear()
        served_modelos, _served_catalogues = load_registry_tree(resolved)
        assert served_modelos == (), "control: a current-key poison cache must be served (the disk cache is live)"

        # REGRESSION: move the poison to a key computed with a DIFFERENT loader
        # fingerprint (a pre-change loader state). The current load must ignore it
        # and recompile the real content.
        current_path.unlink()
        stale_key = _registry_disk_cache_key(
            root_str,
            fingerprints,
            loader_code_fingerprint_override="pre-change-loader-state",
        )
        assert stale_key != current_key
        stale_path = isolated_cache_dir / f"cadrumo_registry_{stale_key}.pkl"
        stale_path.write_bytes(_encode_frame(((), catalogues)))

        _load_registry_tree_cached.cache_clear()
        real_modelos, _real_catalogues = load_registry_tree(resolved)
        assert real_modelos, (
            "a pickle keyed to a different loader-code state must not be served; "
            "the loader must recompile the real content instead of serving the stale pickle"
        )


def test_the_fingerprint_is_not_computed_at_import_time() -> None:
    """Importing the module must not hash the registry source tree.

    Deriving the fingerprint walks every registry source file, reads its
    bytes, and introspects the compiled models' annotations to read each
    embedded foreign type's defining file -- around 150 filesystem calls. It
    used to run at import, as the default argument of
    ``_registry_disk_cache_key``, so every process that imported this module
    paid it whether or not it ever touched the disk cache: ``aeat app ledger
    --help`` hashed the whole registry source tree to print command names.

    Checked in a subprocess because the assertion is about a FRESH import;
    by the time this module's other tests have run, the memo is warm and an
    in-process check could not tell eager from already-used. The counter
    comes from the real memo rather than a copy of its logic, so a default
    argument reinstating the eager call fails here.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import cadrumo.domain.calculations.registry._compiled_cache as c;"
            "print(c.loader_code_fingerprint.cache_info().currsize)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "0", (
        "importing the compiled-cache module computed the loader fingerprint eagerly; it must be deferred to first use"
    )


def test_the_fingerprint_is_computed_once_and_reused() -> None:
    """Control: deferring must not turn one hash into one hash per caller.

    Without this, moving the work out of import could simply relocate it to
    every cache-key derivation -- strictly worse than the eager version it
    replaced.
    """
    loader_code_fingerprint.cache_clear()
    try:
        assert loader_code_fingerprint.cache_info().currsize == 0
        first = loader_code_fingerprint()
        assert loader_code_fingerprint.cache_info().misses == 1

        for _ in range(5):
            assert loader_code_fingerprint() == first
        assert loader_code_fingerprint.cache_info().misses == 1, (
            "the fingerprint must be derived once per process, not once per caller"
        )
    finally:
        loader_code_fingerprint.cache_clear()
