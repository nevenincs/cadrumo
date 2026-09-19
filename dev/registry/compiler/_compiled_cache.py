"""Development-only, fingerprint-keyed mutable-registry compiler cache.

Persists the compiled ``(modelos, catalogues)`` set so a warm process skips the
17,276-file TOML parse (measured cold compile 8.2 s versus a warm cache load of
~1.8 s on the bundled tree). The cache is a shortcut to the same compiled
:class:`ModeloDefinition` set the loader produces -- never a second authority:

* it is keyed by the complete registry-tree fingerprint tuples AND a content
  hash of the loader/compiler/schema source (:func:`loader_code_fingerprint`),
  so a tree edit or a compiler change that alters compiled semantics yields a
  new key and the pre-change cache is simply never read;
* on read the framed file is integrity-checked against an embedded SHA-256
  digest of the payload and the deserialised object is structurally type-checked
  to be exactly ``tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]``; any
  digest mismatch, schema-version mismatch, deserialisation failure, or foreign
  shape DELETES the file and returns ``None`` so the loader recompiles from TOML.

Serialisation is a restricted pickle frame, not pydantic JSON: the compiled models are strict and
frozen (:class:`RegistryModel`) and the recursive ``FormulaExpression.args``
tuple combined with a ``mode="before"`` validator makes ``model_validate_json``
reject JSON arrays for the strict tuple, so a pydantic-JSON round-trip is not
available without weakening the strict contract or editing the schema (out of
scope for a derived cache). Pickle round-trips the exact frozen objects. The
arbitrary-pickle attack surface is bounded: the cache lives only in the
user-owned settings cache directory (never a shared OS temp dir in production),
the bytes are produced solely by this module's own compile, and the embedded
digest plus structural type-check refuse any corrupt or foreign file rather than
serving it. Deliberate local tampering that also rewrites the digest is out of
the cache's threat model (install byte integrity is owned by the
package-manager digest chain); the digest defends corruption, partial writes,
and stale/foreign files. Per ``no-legacy-compatibility`` the cache is derived
and rebuildable: on any mismatch, delete and recompute -- never migrated.
"""

from __future__ import annotations

import datetime
import decimal
import enum
import hashlib
import hmac
import inspect
import io
import logging
import pickle
import struct
import sys
import time
import typing
from collections.abc import Iterable, Iterator, Mapping
from functools import cache
from pathlib import Path
from typing import Final, NamedTuple, TypeGuard, override

from pydantic import BaseModel

import cadrumo
from cadrumo.core.directory_scan import iter_directory, scan_directory
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.paths import select_filesystem_retention_survivors
from cadrumo.domain.calculations.registry.governed_fact_scope import (
    CandidateFactAuthority,
    validating_governed_facts,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues

from .loader_cache import registry_disk_cache_max_entries

CompiledRegistryPayload = tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]
"""The compiled registry payload: every :class:`ModeloDefinition` plus the shared catalogues."""

FingerprintTuples = tuple[tuple[str, int, int, str], ...]
"""``(path, size, mtime_ns, content_digest)`` tuples, exactly as the loader collects them for the cache key.

EVERY TOML row carries a content hash, so a same-size, same-mtime rewrite still
re-keys the cache. That includes the package-bundled tree: an authoring tree
inside a checkout is mutable even when reached through ``bundled_path``, which
is why :func:`~.loader_cache.toml_file_fingerprint` digests unconditionally.
Measured against the bundled tree: 1,739 TOML rows, none without a digest.

The digest is empty only for directory entries, which exist to notice a change
in a directory's membership. Every TOML the compiler reads contributes its own
row, so membership of the compiler's actual inputs is carried by the row SET
independently of those entries.
"""

_COMPILED_CACHE_SCHEMA_VERSION = b"compiled-registry-v2"
_CACHE_FILENAME_PREFIX = "cadrumo_registry_"
_CACHE_FILENAME_SUFFIX = ".pkl"
_FRAME_SEPARATOR = b"\n"
_PAYLOAD_ENVELOPE_PREFIX = b"cadrumo-compiled-registry-envelope-v1\x00"
_READ_ATTEMPTS = 3
_READ_RETRY_BASE_DELAY_SECONDS = 0.01

_LOGGER = logging.getLogger(__name__)

_SAFE_PICKLE_BUILTINS: Final[frozenset[str]] = frozenset(
    {
        "bool",
        "bytes",
        "complex",
        "dict",
        "float",
        "frozenset",
        "int",
        "list",
        "object",
        "set",
        "str",
        "tuple",
    },
)
_SAFE_PICKLE_MODULES: Final[frozenset[str]] = frozenset({"datetime", "decimal"})
_SAFE_PICKLE_PREFIXES: Final[tuple[str, ...]] = ("cadrumo.", "dev.registry.")


class _CompiledCacheUnpickler(pickle.Unpickler):
    """Load only the first-party model graph and inert value types."""

    @override
    def find_class(self, module: str, name: str) -> object:
        if module == "builtins" and name in _SAFE_PICKLE_BUILTINS:
            return super().find_class(module, name)
        if module in _SAFE_PICKLE_MODULES or module.startswith(_SAFE_PICKLE_PREFIXES):
            resolved = super().find_class(module, name)
            if not hasattr(resolved, "from_registry"):
                return resolved
            registry_constructor = resolved.from_registry

            class _RegistryProjectedType(resolved):
                def __new__(cls, *args: object, **kwargs: object) -> object:
                    return registry_constructor(*args, **kwargs)

            return _RegistryProjectedType
        raise pickle.UnpicklingError(f"compiled cache references forbidden global {module}.{name}")


_REGISTRY_TREE_CACHE_SCHEMA_VERSION = "legal-parameter-refs-v1"

_CADRUMO_PACKAGE_DIR: Final[Path] = Path(cadrumo.__file__).resolve().parent
"""The ``cadrumo`` package root, resolved from the imported package itself.

Deliberately NOT derived from this file's own path: this module lives under
``dev/registry/compiler/``, outside ``src/cadrumo`` entirely, so a path
relative to ``__file__`` can never reach the ``cadrumo`` root. Resolving from
``cadrumo.__file__`` is stable across a package relocation on either side.
"""

_REGISTRY_PACKAGE_DIR: Final[Path] = _CADRUMO_PACKAGE_DIR / "domain" / "calculations" / "registry"
"""The compiled schema/model package -- the source surface hashed wholesale below.

The boundary that separates a FIRST-PARTY embedded type (hashed) from a stdlib
or third-party one (not ours to invalidate on). ``test_package_roots_are_the_real_directories``
pins this to the real directory so a package relocation reds loudly instead of
silently classifying every first-party type as foreign.
"""

_DEV_COMPILER_DIR: Final[Path] = Path(__file__).resolve().parent
"""The dev compiler package directory (``dev/registry/compiler``).

The compiled payload's shape is produced by this compiler as much as by the
schema package above: a compiler change can alter compiled semantics from
identical TOML just as a schema change can, so its source is hashed alongside
:data:`_REGISTRY_PACKAGE_DIR` in :func:`_compute_loader_code_fingerprint`. It
plays no role in the first-party/foreign-type boundary -- that boundary is
about types embedded in the compiled Pydantic models, and the compiler itself
defines none of those.
"""

_LOADER_CODE_SOURCE_ROOTS: Final[tuple[Path, ...]] = (_REGISTRY_PACKAGE_DIR, _DEV_COMPILER_DIR)
"""Every source directory whose bytes are hashed wholesale into the loader-code fingerprint."""

_UNDERIVABLE_EMBEDDED_TYPES_MARKER: Final[str] = "embedded-foreign-types-underivable"
"""Folded into the key when the derivation itself fails, keeping it deterministic."""


class _EmbeddedForeignType(NamedTuple):
    """One first-party type the compiled payload embeds from outside the registry package.

    ``marker`` is the stable ``module.qualname`` identity, ``relative_source`` the
    defining file's path under the ``cadrumo`` package root (machine-independent,
    so the fingerprint does not move with the checkout location), and
    ``source_path`` the absolute file whose bytes are hashed.
    """

    marker: str
    relative_source: str
    source_path: Path


def _compiled_payload_root_models() -> tuple[type[BaseModel], ...]:
    """Return every model an unpickled compiled payload can reconstruct objects from.

    The two schema roots are now sufficient. Every concrete binding provider
    model used to be listed separately because the former open ``selector``
    field hid them from an annotation walk, which is how ``Modelo``,
    ``IvaCategory`` and their siblings once sat unhashed. :attr:`BindingDefinition.provider`
    is a closed discriminated union, so the same walk reaches every provider
    member -- and every enum it embeds -- from :class:`ModeloDefinition` alone.
    """
    return (ModeloDefinition, RegistryCatalogues)


def _iter_annotation_types(annotation: object) -> Iterator[type[object]]:
    """Yield every concrete type a pydantic field annotation can hold at runtime.

    Unwraps type aliases, ``Annotated`` metadata, unions, and container
    parameters, and -- the case that hid the core ``Modelo`` enum -- yields the
    ENUM CLASS behind each member of a ``Literal[...]`` of enum members, because
    such a field pickles a real enum instance even though the annotation names
    only its values.
    """
    if isinstance(annotation, typing.TypeAliasType):
        yield from _iter_annotation_types(annotation.__value__)
        return
    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        for arg in typing.get_args(annotation):
            if isinstance(arg, enum.Enum):
                yield type(arg)
        return
    if origin is not None:
        for arg in typing.get_args(annotation):
            yield from _iter_annotation_types(arg)
        if isinstance(origin, type):
            yield origin
        return
    if isinstance(annotation, type):
        yield annotation


def _classify_foreign_type(candidate: object) -> _EmbeddedForeignType | None:
    """Return ``candidate`` as an embedded foreign type, or ``None`` if it is not one.

    ``None`` for anything without source on disk (a builtin, a C extension) and
    for anything defined inside the ``cadrumo`` registry package or outside the
    ``cadrumo`` package altogether: the former is already hashed wholesale, the
    latter is not ours to invalidate on.
    """
    if not isinstance(candidate, type):
        return None
    try:
        source_file = inspect.getsourcefile(candidate)
    except (TypeError, OSError):
        return None
    if source_file is None:
        return None
    path = Path(source_file).resolve()
    if not path.is_relative_to(_CADRUMO_PACKAGE_DIR) or path.is_relative_to(_REGISTRY_PACKAGE_DIR):
        return None
    return _EmbeddedForeignType(
        marker=f"{candidate.__module__}.{candidate.__qualname__}",
        relative_source=path.relative_to(_CADRUMO_PACKAGE_DIR).as_posix(),
        source_path=path,
    )


def _derive_embedded_foreign_types(
    roots: Iterable[type[BaseModel]] | None = None,
) -> tuple[_EmbeddedForeignType, ...]:
    """Derive every first-party non-registry type the compiled payload embeds.

    Walks ``roots`` (defaulting to :func:`_compiled_payload_root_models`)
    recursively over ``model_fields`` annotations, descending into every nested
    :class:`~pydantic.BaseModel` it meets, and collects the types defined inside
    ``cadrumo`` but outside the registry package. This replaces a remembered
    hand list: the cache key can no longer omit an embedded type because an
    author forgot to enrol it. ``roots`` is injectable so a test can prove the
    derivation DETECTS a newly embedded type rather than merely restating
    today's set.

    Returns:
        The derived types, ordered by marker so the fingerprint is deterministic.
    """
    pending: list[type[BaseModel]] = list(_compiled_payload_root_models() if roots is None else roots)
    visited_models: set[type[BaseModel]] = set()
    found: dict[str, _EmbeddedForeignType] = {}
    while pending:
        model = pending.pop()
        if model in visited_models:
            continue
        visited_models.add(model)
        for field in model.model_fields.values():
            for candidate in _iter_annotation_types(field.annotation):
                if issubclass(candidate, BaseModel):
                    pending.append(candidate)
                foreign = _classify_foreign_type(candidate)
                if foreign is not None:
                    found[foreign.marker] = foreign
    return tuple(found[marker] for marker in sorted(found))


def _compute_loader_code_fingerprint(roots: Iterable[type[BaseModel]] | None = None) -> str:
    """Return a content hash of the loader/compiler/schema source.

    The compiled-registry cache stores COMPILED ``(modelos, catalogues)``
    objects. The tree fingerprint keys only the TOML inputs, so a change to the
    compilation logic (or to a core type embedded in the compiled objects) that
    produces DIFFERENT compiled objects from IDENTICAL TOML is invisible to the
    tree key -- a stale cache from a prior session would be served for the
    current loader. The hand-maintained
    :data:`_REGISTRY_TREE_CACHE_SCHEMA_VERSION` only guards this when a developer
    remembers to bump it. Folding a content hash of the source into the cache key
    closes the gap automatically:

    * every module under the compiled schema/model package (excluding its
      tests) AND every module of the dev compiler that turns TOML into those
      models (excluding its tests) -- the schema models, the compiler, and the
      resolvers; and
    * every first-party type embedded in the compiled objects from OUTSIDE the
      registry package, DERIVED from the compiled models' own annotations by
      :func:`_derive_embedded_foreign_types` rather than remembered in a hand
      list. Each derived type contributes its ``module.qualname`` marker and the
      bytes of its TRUE defining file, so a change to the private module that
      defines it (``core/period.py``, ``domain/iva/schema.py``) invalidates the
      cache even though no registry module moved.

    Any change to either surface yields a new key, so pre-change caches can never
    be served. Best-effort per surface: an unreadable registry tree (e.g. a
    zip-imported install) falls back to the interpreter version + bytecode cache
    tag; a derivation or a source read that fails folds in a stable marker so the
    key stays deterministic and distinct rather than crashing.

    Args:
        roots: Models to derive the embedded foreign types from. Injected for
            test isolation; production derives them from the compiled payload's
            own roots.
    """
    hasher = hashlib.sha256()
    try:
        for source_root in _LOADER_CODE_SOURCE_ROOTS:
            source_files = scan_directory(
                source_root,
                pattern="*.py",
                recursive=True,
                prune_directories=("tests",),
            )
            hasher.update(source_root.name.encode("utf-8"))
            for path in source_files:
                hasher.update(path.relative_to(source_root).as_posix().encode("utf-8"))
                hasher.update(path.read_bytes())
    except OSError:
        hasher.update(sys.version.encode("utf-8"))
        hasher.update((sys.implementation.cache_tag or "").encode("utf-8"))

    try:
        embedded = _derive_embedded_foreign_types(roots)
    except Exception:  # pragma: no cover - derivation is pure introspection over imported models
        _LOGGER.debug("Could not derive the embedded foreign types for the cache key", exc_info=True)
        hasher.update(_UNDERIVABLE_EMBEDDED_TYPES_MARKER.encode("utf-8"))
        return hasher.hexdigest()

    read_sources: set[str] = set()
    for item in embedded:
        hasher.update(item.marker.encode("utf-8"))
        if item.relative_source in read_sources:
            continue
        read_sources.add(item.relative_source)
        hasher.update(item.relative_source.encode("utf-8"))
        try:
            hasher.update(item.source_path.read_bytes())
        except OSError:
            hasher.update(f"unreadable:{item.relative_source}".encode())
    return hasher.hexdigest()


@cache
def _loader_code_fingerprint() -> str:
    """Return the loader-source fingerprint, computed once on first use.

    Deriving it walks every registry source file, reads its bytes, and
    introspects the compiled models' annotations to read the defining file of
    each embedded foreign type -- about 160 ms and 150 filesystem calls. It was
    previously computed at IMPORT time, as the default argument of
    :func:`_registry_disk_cache_key`, so every process that so much as imported
    this module paid it: ``aeat app ledger --help`` hashed the whole registry
    source tree to print a list of command names, and never went near the disk
    cache it keys.

    The value cannot change within a process -- it hashes source files, and this
    interpreter has already imported them -- so memoising is not a staleness
    trade. A developer editing a registry module mid-run is running the OLD code
    for that module anyway; the fingerprint agrees with what is loaded, which is
    exactly what the cache key must describe.
    """
    return _compute_loader_code_fingerprint()


def _registry_disk_cache_key(
    root: str,
    fingerprints: FingerprintTuples,
    *,
    loader_code_fingerprint_override: str | None = None,
) -> str:
    """Compute the compiled-cache key.

    The key binds the compiled payload to (1) the schema-version marker, (2) a
    content hash of the loader/compiler/schema source (so a code change that
    alters compiled semantics invalidates the cache even without a manual version
    bump), (3) the registry root path, and (4) the per-TOML tree fingerprints
    reduced to ``(path, size, content_digest)``. ``loader_code_fingerprint_override``
    is injected for test isolation; production resolves
    :func:`loader_code_fingerprint`, which is why that resolution happens HERE
    rather than in the signature -- a default argument would be evaluated at
    import time and reinstate the cost this indirection removes.

    ``mtime_ns`` is DROPPED from every row, matching what the validation verdict
    already keys on: a compiled payload is a statement about CONTENT, and the
    same declarations compile the same way whenever they were last written. Kept
    in the key, an mtime-only touch -- a branch switch, a checkout, a rewrite of
    identical bytes -- was a full miss costing a ~30 s compile per process, and
    stored a second copy of a payload the directory already held. Observed
    directly: two of the eight retained pickles were byte-identical under
    different keys, so mtime churn was evicting genuinely distinct entries out
    of a ceiling-bound store.

    Dropping it is safe for the two things mtime was carrying here. A TOML whose
    bytes changed is caught by its content digest -- every TOML row has one,
    bundled tree included, as :data:`FingerprintTuples` records -- and that
    digest exists precisely because ``(size, mtime_ns)`` cannot separate two
    same-length writes inside the filesystem's mtime resolution. A TOML added or
    removed changes the SET of rows, and every registry TOML contributes one, so
    membership is keyed without consulting the digest-less directory rows'
    timestamps.

    What this does narrow, stated plainly: a directory row now contributes only
    its path and size, so a change to a directory's contents that adds or removes
    a NON-TOML file may no longer re-key. Such a file has no row of its own and
    was never content-checked either way, and the compiler's inputs are the TOML
    declarations plus the separately receipted source evidence, so nothing it
    reads loses coverage. A non-TOML file that ever does become a compiler input
    needs its own fingerprint row, not a parent directory's timestamp.

    The cheap directory-walk freshness check in the fingerprint cache is a
    separate mechanism and still reads directory mtimes.
    """
    override = loader_code_fingerprint_override
    resolved = _loader_code_fingerprint() if override is None else override
    hasher = hashlib.sha256()
    hasher.update(_REGISTRY_TREE_CACHE_SCHEMA_VERSION.encode("utf-8"))
    hasher.update(resolved.encode("utf-8"))
    hasher.update(root.encode("utf-8"))
    for path, size, _modified_ns, digest in fingerprints:
        # Delimited, unlike the undelimited concatenation this replaced: without
        # a separator, two different rows can serialise to the same bytes.
        hasher.update(f"{path}\0{size}\0{digest}\0".encode())
    return hasher.hexdigest()


def _evict_stale_registry_pickles(cache_dir: Path, *, logger: logging.Logger) -> None:
    """Keep only the newest ``registry_disk_cache_max_entries`` caches, prune the rest.

    One cache accumulates per registry-tree fingerprint, so a long-lived cache
    directory (an editable checkout re-compiling after successive registry edits)
    would otherwise grow without bound. Called after a successful write; entirely
    best-effort -- a prune failure (a permission error, a concurrent writer's
    unlink, a file that vanished mid-scan) is logged and swallowed. Eviction must
    never crash a registry load; the worst case is a few extra stale files. The
    survivor decision (a count bound alone) delegates to the shared
    :func:`~cadrumo.core.paths.select_filesystem_retention_survivors` selector.
    """
    keep = registry_disk_cache_max_entries()
    entries: list[tuple[Path, int]] = []
    try:
        for cache_path in iter_directory(
            cache_dir,
            pattern=f"{_CACHE_FILENAME_PREFIX}*{_CACHE_FILENAME_SUFFIX}",
            require_root=True,
        ):
            try:
                entries.append((cache_path, cache_path.stat().st_mtime_ns))
            except OSError:
                continue
    except OSError:
        logger.debug("Could not enumerate compiled registry caches in %s", cache_dir, exc_info=True)
        return
    # Pre-sort by path, descending: the selector's stable, timestamp-only sort
    # then preserves this order for any mtime_ns tie (real on some filesystems
    # whose mtime resolution is coarser than a nanosecond), reproducing the
    # prior ``(mtime_ns, Path)`` tuple sort's implicit path tie-break.
    entries.sort(key=lambda pair: pair[0], reverse=True)
    _keep, stale = select_filesystem_retention_survivors(
        entries,
        timestamp=lambda pair: pair[1],
        max_count=keep,
    )
    for cache_path, _mtime_ns in stale:
        try:
            cache_path.unlink()
        except OSError:
            logger.debug("Could not evict stale compiled registry cache %s", cache_path, exc_info=True)


def _encode_frame(payload: CompiledRegistryPayload) -> bytes:
    """Serialise ``payload`` into the newline-framed version, digest, and pickle bytes."""
    modelos, catalogues = payload
    catalogue_bytes = pickle.dumps(catalogues, protocol=pickle.HIGHEST_PROTOCOL)
    modelos_bytes = pickle.dumps(modelos, protocol=pickle.HIGHEST_PROTOCOL)
    payload_bytes = _PAYLOAD_ENVELOPE_PREFIX + struct.pack("!Q", len(catalogue_bytes))
    payload_bytes += catalogue_bytes + modelos_bytes
    digest = _payload_digest(payload_bytes)
    return _FRAME_SEPARATOR.join((_COMPILED_CACHE_SCHEMA_VERSION, digest, payload_bytes))


def _decode_and_validate(raw: bytes) -> CompiledRegistryPayload | None:
    """Verify the frame integrity and structural shape; ``None`` on any mismatch."""
    parts = raw.split(_FRAME_SEPARATOR, 2)
    if len(parts) != 3:
        return None
    version, digest, payload_bytes = parts
    if version != _COMPILED_CACHE_SCHEMA_VERSION:
        return None
    if not _digests_equal(digest, _payload_digest(payload_bytes)):
        return None
    try:
        payload = _decode_payload_bytes(payload_bytes)
    except Exception:
        _LOGGER.debug("Compiled registry cache payload could not be deserialised; recomputing", exc_info=True)
        return None
    if not _is_compiled_registry_payload(payload):
        return None
    return payload


def _decode_payload_bytes(payload_bytes: bytes) -> object:
    """Restore one cache payload, scoping opaque model tokens to its catalogue."""
    if not payload_bytes.startswith(_PAYLOAD_ENVELOPE_PREFIX):
        return _CompiledCacheUnpickler(io.BytesIO(payload_bytes)).load()
    offset = len(_PAYLOAD_ENVELOPE_PREFIX)
    if len(payload_bytes) < offset + 8:
        raise pickle.UnpicklingError("compiled cache envelope is truncated")
    (catalogue_length,) = struct.unpack("!Q", payload_bytes[offset : offset + 8])
    catalogue_start = offset + 8
    catalogue_end = catalogue_start + catalogue_length
    if catalogue_end > len(payload_bytes):
        raise pickle.UnpicklingError("compiled cache catalogue frame is truncated")
    catalogues = _CompiledCacheUnpickler(io.BytesIO(payload_bytes[catalogue_start:catalogue_end])).load()
    modelos_bytes = payload_bytes[catalogue_end:]
    if not isinstance(catalogues, RegistryCatalogues):
        raise pickle.UnpicklingError("compiled cache catalogue has a foreign shape")
    authority = CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    with validating_governed_facts(authority):
        modelos = _CompiledCacheUnpickler(io.BytesIO(modelos_bytes)).load()
    return modelos, catalogues


def _payload_digest(payload_bytes: bytes) -> bytes:
    """Return the hex SHA-256 of the schema-version-bound payload, as ascii bytes."""
    return sha256_hex(_COMPILED_CACHE_SCHEMA_VERSION + payload_bytes).encode("ascii")


def _digests_equal(left: bytes, right: bytes) -> bool:
    return hmac.compare_digest(left, right)


def _is_compiled_registry_payload(payload: object) -> TypeGuard[CompiledRegistryPayload]:
    """Whether ``payload`` is exactly ``(tuple[ModeloDefinition, ...], RegistryCatalogues)``.

    The structural gate that keeps a foreign or truncated-shape pickle -- even
    one that deserialises cleanly -- from being served as the compiled authority.
    """
    if not _is_two_object_tuple(payload):
        return False
    modelos_raw, catalogues_raw = payload
    if not _is_object_tuple(modelos_raw):
        return False
    if not all(isinstance(modelo, ModeloDefinition) for modelo in modelos_raw) or not isinstance(
        catalogues_raw, RegistryCatalogues
    ):
        return False
    return _has_current_pydantic_shape((*modelos_raw, catalogues_raw))


_INERT_LEAF_TYPES: Final[frozenset[type]] = frozenset(
    {
        bool,
        bytes,
        datetime.date,
        datetime.datetime,
        datetime.time,
        decimal.Decimal,
        float,
        int,
        str,
        type(None),
    },
)
"""Value types that hold no nested model, so the shape walk can retire them unopened.

Every member is a type the walk already descended into nothing, which is what
makes the exemption free of reach: none is a model, a mapping, or a
tuple/list/set/frozenset. Matched by exact type rather than ``isinstance``, so a
subclass -- which may well be a container -- keeps the walk's normal dispatch.
Both properties are pinned by ``test_compiled_payload_shape_walk``.
"""


@cache
def _current_field_names(model_type: type[BaseModel]) -> frozenset[str]:
    """Return one model class's current field names, derived once per class.

    ``model_fields`` is a mapping on the class, so the set it yields is the same
    for every instance; rebuilding it per instance was work proportional to the
    payload rather than to the schema.

    The key type is spelled out rather than taken from ``model_fields``
    directly, whose element type the type checker cannot see through Pydantic's
    class-level descriptor.
    """
    return frozenset(str(name) for name in model_type.model_fields)


def _has_current_pydantic_shape(values: Iterable[object]) -> bool:
    """Whether every nested Pydantic object carries every field in today's schema.

    Pickle restores an old Pydantic instance without running today's validators or
    materialising fields added since it was written.  ``isinstance`` alone therefore
    accepts a stale object whose class name still resolves, only to fail later with an
    ``AttributeError``.  Walk the already-decoded first-party graph and refuse any
    model whose stored state omits a current field.  Refusal deletes and recompiles
    the derived cache; it never hydrates or migrates the stale object.

    The walk only ENUMERATES the graph; it decides nothing from a container's own
    type. Containers are therefore iterated directly rather than passed through a
    ``TypeAdapter`` for ``dict[object, object]`` / ``list[object]``: those
    annotations accept every value, so the adapters validated nothing while
    copying each container and running a pydantic-core pass over it.

    Most of the graph is leaf scalars -- every mapping key, every field holding a
    string, number, date or decimal -- and each one was paying an ``id()``, a set
    insertion and three ``isinstance`` probes only to match none of them and be
    dropped. :data:`_INERT_LEAF_TYPES` retires exactly those, so the bail-out
    changes cost and not reach. Measured on the bundled payload, the walk costs
    roughly 1.6 s against roughly 2.3 s without it.
    """
    pending = list(values)
    seen: set[int] = set()
    while pending:
        value = pending.pop()
        if value.__class__ in _INERT_LEAF_TYPES:
            continue
        identity = id(value)
        if identity in seen:
            continue
        seen.add(identity)
        if isinstance(value, BaseModel):
            if not _current_field_names(type(value)).issubset(value.__dict__):
                return False
            pending.extend(value.__dict__.values())
        elif isinstance(value, Mapping):
            # Any mapping, not only ``dict``: a registry model holds its
            # revisions in an immutable mapping, and a walk that recognised
            # ``dict`` alone stopped there and never reached the rows nested
            # below it, which is exactly where a stale object hides.
            opaque_mapping = typing.cast("Mapping[object, object]", value)
            pending.extend(opaque_mapping.keys())
            pending.extend(opaque_mapping.values())
        elif isinstance(value, (tuple, list, set, frozenset)):
            pending.extend(typing.cast("Iterable[object]", value))
    return True


def _is_object_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
    """Narrow an untyped pickle tuple to an object-valued tuple."""
    return isinstance(value, tuple)


def _is_two_object_tuple(value: object) -> TypeGuard[tuple[object, object]]:
    """Narrow an untyped pickle tuple to the expected two-item envelope."""
    if not isinstance(value, tuple):
        return False
    # Narrowing an object to tuple yields no element type; the guard only asks how
    # many items the envelope carries, so the elements stay opaque by design.
    items: tuple[object, ...] = value  # pyright: ignore[reportUnknownVariableType]  # reason: narrowing an object to tuple yields no element type, and this guard only asks how many items the envelope carries
    return len(items) == 2


def _read_cache_bytes(path: Path) -> bytes | None:
    """Read the whole framed cache file, retrying past a transient replace race.

    ``os.replace`` is atomic but a reader can transiently observe a
    sharing-violation ``OSError`` on Windows while a concurrent writer's replace
    is in flight (an xdist worker racing a sibling on the shared bundled-root
    file). A short bounded retry outlasts the atomic replace; a genuinely
    unreadable file falls through to ``None`` and recompute.
    """
    for attempt in range(_READ_ATTEMPTS):
        try:
            return path.read_bytes()
        except OSError:
            final_attempt = attempt == _READ_ATTEMPTS - 1
            _LOGGER.debug(
                "Compiled registry cache read attempt %d/%d failed at %s%s",
                attempt + 1,
                _READ_ATTEMPTS,
                path,
                " -- giving up, will recompute" if final_attempt else " -- retrying",
                exc_info=True,
            )
            if not final_attempt:
                time.sleep(_READ_RETRY_BASE_DELAY_SECONDS * (2**attempt))
    return None


def _delete_cache_file(path: Path) -> None:
    """Best-effort delete of a mismatched or corrupt cache file (delete-not-migrate)."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        _LOGGER.debug("Could not delete stale compiled registry cache at %s", path, exc_info=True)


__all__ = []
