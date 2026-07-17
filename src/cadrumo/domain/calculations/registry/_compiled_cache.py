"""Strict-validated, fingerprint-keyed compiled-registry cache (ADR mcp-call-latency D3).

Persists the compiled ``(modelos, catalogues)`` set so a warm process skips the
17,276-file TOML parse (measured cold compile 8.2 s versus a warm cache load of
~1.8 s on the bundled tree). The cache is a shortcut to the same compiled
:class:`ModeloDefinition` set the loader produces -- never a second authority:

* it is keyed by the complete registry-tree fingerprint tuples AND a content
  hash of the loader/compiler/schema source (:data:`_LOADER_CODE_FINGERPRINT`),
  so a tree edit or a compiler change that alters compiled semantics yields a
  new key and the pre-change cache is simply never read;
* on read the framed file is integrity-checked against an embedded SHA-256
  digest of the payload and the deserialised object is structurally type-checked
  to be exactly ``tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]``; any
  digest mismatch, schema-version mismatch, deserialisation failure, or foreign
  shape DELETES the file and returns ``None`` so the loader recompiles from TOML.

Serialisation is pickle, not pydantic JSON: the compiled models are strict and
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
the cache's threat model per the ADR (install byte integrity is owned by the
package-manager digest chain); the digest defends corruption, partial writes,
and stale/foreign files. Per ``no-legacy-compatibility`` the cache is derived
and rebuildable: on any mismatch, delete and recompute -- never migrated.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import logging
import os
import pickle
import sys
import tempfile
import time
from pathlib import Path

from ._loader_cache import registry_disk_cache_dir, registry_disk_cache_max_entries
from ._schema import ModeloDefinition, RegistryCatalogues

CompiledRegistryPayload = tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]
"""The compiled registry payload: every :class:`ModeloDefinition` plus the shared catalogues."""

FingerprintTuples = tuple[tuple[str, int, int], ...]
"""``(path, size, mtime_ns)`` tuples, exactly as the loader collects them for the cache key."""

_COMPILED_CACHE_SCHEMA_VERSION = b"compiled-registry-v1"
_CACHE_FILENAME_PREFIX = "cadrumo_registry_"
_CACHE_FILENAME_SUFFIX = ".pkl"
_FRAME_SEPARATOR = b"\n"
_READ_ATTEMPTS = 3
_READ_RETRY_BASE_DELAY_SECONDS = 0.01

_LOGGER = logging.getLogger(__name__)

_REGISTRY_TREE_CACHE_SCHEMA_VERSION = "legal-parameter-refs-v1"

_EMBEDDED_SCHEMA_CORE_MODULES = (
    # Cross-package core modules whose TYPES are EMBEDDED in the pickled compiled
    # (modelos, catalogues) objects. The registry-package hash below covers the
    # schema MODELS and the compiler/resolvers, but the compiled objects also
    # embed core primitives defined OUTSIDE the registry package -- a change to
    # one of these (a new BindingSourceKind member, a BindingAggregation field,
    # a SensitivityClass value, a Period/TaxDomain shape) alters the pickled
    # object semantics without touching any registry module, so it must be in
    # the key too. Extend this tuple when a new core type becomes embedded in
    # the compiled objects; `test_embedded_schema_core_modules_all_resolve`
    # guards it against drift to a non-existent module.
    "cadrumo.core.aggregation",  # BindingSourceKind / BindingAggregation / BindingTypedEnumKind
    "cadrumo.core.classification",  # SensitivityClass
    "cadrumo.core._period",  # Period
    "cadrumo.core._tax_domain",  # TaxDomain
)


def _compute_loader_code_fingerprint() -> str:
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

    * every registry-package module (excluding its tests) -- the schema models,
      the compiler, and the resolvers; and
    * the cross-package core modules whose types are embedded in the compiled
      objects (:data:`_EMBEDDED_SCHEMA_CORE_MODULES`).

    Any change to either surface yields a new key, so pre-change caches can never
    be served. Best-effort per surface: an unreadable registry tree (e.g. a
    zip-imported install) falls back to the interpreter version + bytecode cache
    tag; an unresolvable core module folds in a stable marker so the key stays
    deterministic and distinct rather than crashing.
    """
    hasher = hashlib.sha256()
    try:
        package_dir = Path(__file__).resolve().parent
        source_files = sorted(
            path for path in package_dir.rglob("*.py") if "tests" not in path.relative_to(package_dir).parts
        )
        for path in source_files:
            hasher.update(path.relative_to(package_dir).as_posix().encode("utf-8"))
            hasher.update(path.read_bytes())
    except OSError:
        hasher.update(sys.version.encode("utf-8"))
        hasher.update((sys.implementation.cache_tag or "").encode("utf-8"))

    for module_name in _EMBEDDED_SCHEMA_CORE_MODULES:
        try:
            module = importlib.import_module(module_name)
            module_file = getattr(module, "__file__", None)
            if module_file is None:
                hasher.update(f"unresolved:{module_name}".encode())
                continue
            hasher.update(module_name.encode("utf-8"))
            hasher.update(Path(module_file).read_bytes())
        except (OSError, ImportError):
            hasher.update(f"unresolved:{module_name}".encode())
    return hasher.hexdigest()


_LOADER_CODE_FINGERPRINT = _compute_loader_code_fingerprint()


def _registry_disk_cache_key(
    root: str,
    fingerprints: FingerprintTuples,
    *,
    loader_code_fingerprint: str = _LOADER_CODE_FINGERPRINT,
) -> str:
    """Compute the compiled-cache key.

    The key binds the compiled payload to (1) the schema-version marker, (2) a
    content hash of the loader/compiler/schema source (so a code change that
    alters compiled semantics invalidates the cache even without a manual version
    bump), (3) the registry root path, and (4) the per-TOML tree fingerprints
    (path, size, mtime_ns). ``loader_code_fingerprint`` is injected for test
    isolation; production always uses :data:`_LOADER_CODE_FINGERPRINT`.
    """
    hasher = hashlib.sha256()
    hasher.update(_REGISTRY_TREE_CACHE_SCHEMA_VERSION.encode("utf-8"))
    hasher.update(loader_code_fingerprint.encode("utf-8"))
    hasher.update(root.encode("utf-8"))
    for item in fingerprints:
        hasher.update(item[0].encode("utf-8"))
        hasher.update(str(item[1]).encode("utf-8"))
        hasher.update(str(item[2]).encode("utf-8"))
    return hasher.hexdigest()


def _evict_stale_registry_pickles(cache_dir: Path, *, logger: logging.Logger) -> None:
    """Keep only the newest ``registry_disk_cache_max_entries`` caches, prune the rest.

    One cache accumulates per registry-tree fingerprint, so a long-lived cache
    directory (an editable checkout re-compiling after successive registry edits)
    would otherwise grow without bound. Called after a successful write; entirely
    best-effort -- a prune failure (a permission error, a concurrent writer's
    unlink, a file that vanished mid-scan) is logged and swallowed. Eviction must
    never crash a registry load; the worst case is a few extra stale files.
    """
    keep = registry_disk_cache_max_entries()
    try:
        entries: list[tuple[int, Path]] = []
        for cache_path in cache_dir.glob(f"{_CACHE_FILENAME_PREFIX}*{_CACHE_FILENAME_SUFFIX}"):
            try:
                entries.append((cache_path.stat().st_mtime_ns, cache_path))
            except OSError:
                continue
    except OSError:
        logger.debug("Could not enumerate compiled registry caches in %s", cache_dir, exc_info=True)
        return
    entries.sort(reverse=True)
    for _mtime_ns, stale in entries[keep:]:
        try:
            stale.unlink()
        except OSError:
            logger.debug("Could not evict stale compiled registry cache %s", stale, exc_info=True)


def compiled_cache_path(root: Path, fingerprints: FingerprintTuples) -> Path:
    """Return the compiled-cache file for ``root`` at the current fingerprint key.

    The filename embeds the sha256 of the schema-version marker, the loader-code
    fingerprint, the root path, and the per-TOML tree fingerprints, so distinct
    trees and distinct compiler states never share a file while an identical tree
    reuses the same path across processes.

    Returns:
        The cache file path under the settings-derived registry cache directory.
    """
    key_hash = _registry_disk_cache_key(str(root), fingerprints)
    return registry_disk_cache_dir() / f"{_CACHE_FILENAME_PREFIX}{key_hash}{_CACHE_FILENAME_SUFFIX}"


def load_compiled_registry_cache(root: Path, fingerprints: FingerprintTuples) -> CompiledRegistryPayload | None:
    """Load the strict-validated compiled payload for ``root``, or ``None`` to recompile.

    Reads the framed cache file at the current fingerprint key, verifies the
    embedded integrity digest, deserialises the payload, and structurally
    type-checks it. Any failure -- an absent file, a transient read race that
    outlasts the retry, a schema-version or digest mismatch (the file was
    mutated on disk), an unpicklable payload, or a payload that is not exactly a
    ``(tuple[ModeloDefinition, ...], RegistryCatalogues)`` pair -- DELETES the
    file and returns ``None`` so the caller recompiles from TOML. The cache is
    therefore never a second authority: it can only ever serve a byte-integral
    payload of the exact expected shape.

    Returns:
        The compiled payload on a clean hit, else ``None``.
    """
    path = compiled_cache_path(root, fingerprints)
    if not path.is_file():
        return None
    raw = _read_cache_bytes(path)
    if raw is None:
        return None
    payload = _decode_and_validate(raw)
    if payload is None:
        _delete_cache_file(path)
        return None
    return payload


def store_compiled_registry_cache(
    root: Path,
    fingerprints: FingerprintTuples,
    payload: CompiledRegistryPayload,
) -> None:
    """Persist ``payload`` for ``root`` at the current fingerprint key.

    Writes the framed file (schema-version marker, integrity digest, pickled
    payload) atomically via a sibling temp file, then prunes stale sibling
    pickles beyond the retained-entry ceiling. Best-effort: a write failure is
    logged and swallowed so a cache-directory permission problem never crashes a
    registry load -- the worst case is a recompile on the next process.
    """
    path = compiled_cache_path(root, fingerprints)
    frame = _encode_frame(payload)
    temp_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as tf:
            tf.write(frame)
            temp_name = tf.name
        os.replace(temp_name, path)
        _evict_stale_registry_pickles(path.parent, logger=_LOGGER)
    except Exception:
        _LOGGER.debug("Could not write compiled registry cache at %s", path, exc_info=True)
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                _LOGGER.debug("Could not remove temporary compiled registry cache file %s", temp_name, exc_info=True)


def _encode_frame(payload: CompiledRegistryPayload) -> bytes:
    """Serialise ``payload`` into the newline-framed version, digest, and pickle bytes."""
    payload_bytes = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)  # nosemgrep
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
        # Same-user performance cache of first-party compiled registry data only.
        # The bytes are produced solely by _encode_frame above and are gated by the
        # integrity digest verified immediately before this load; a corrupt/foreign
        # payload is refused. See the module docstring for the threat model.
        payload = pickle.loads(payload_bytes)  # noqa: S301  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
    except Exception:
        _LOGGER.debug("Compiled registry cache payload could not be deserialised; recomputing", exc_info=True)
        return None
    if not _is_compiled_registry_payload(payload):
        return None
    return payload


def _payload_digest(payload_bytes: bytes) -> bytes:
    """Return the hex SHA-256 of the schema-version-bound payload, as ascii bytes."""
    return hashlib.sha256(_COMPILED_CACHE_SCHEMA_VERSION + payload_bytes).hexdigest().encode("ascii")


def _digests_equal(left: bytes, right: bytes) -> bool:
    return hmac.compare_digest(left, right)


def _is_compiled_registry_payload(payload: object) -> bool:
    """Whether ``payload`` is exactly ``(tuple[ModeloDefinition, ...], RegistryCatalogues)``.

    The structural gate that keeps a foreign or truncated-shape pickle -- even
    one that deserialises cleanly -- from being served as the compiled authority.
    """
    return (
        isinstance(payload, tuple)
        and len(payload) == 2
        and isinstance(payload[0], tuple)
        and all(isinstance(modelo, ModeloDefinition) for modelo in payload[0])
        and isinstance(payload[1], RegistryCatalogues)
    )


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


__all__ = [
    "CompiledRegistryPayload",
    "FingerprintTuples",
    "compiled_cache_path",
    "load_compiled_registry_cache",
    "store_compiled_registry_cache",
]
