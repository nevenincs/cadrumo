"""Development-only orchestration for mutable registry fingerprint cache keys."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from cadrumo.core.directory_scan import scan_directory
from cadrumo.domain.calculations.registry.errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
    RegistryLoadError,
)

from .loader_cache import (
    BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS,
    is_bundled_registry_root,
    toml_file_fingerprint,
)

type RegistryPathFingerprint = tuple[str, int, int, str]
type RegistryPathFingerprints = tuple[RegistryPathFingerprint, ...]
type RegistryFingerprintCache = dict[
    Path,
    tuple[float, RegistryPathFingerprints, RegistryPathFingerprints],
]
type DirectoryFingerprintCollector = Callable[[Path], RegistryPathFingerprints]
type SourceFingerprintCollector = Callable[[Path], RegistryPathFingerprints]
type BundledRootPredicate = Callable[[Path], bool]
type FingerprintStore = Callable[..., None]


class LiveFingerprintLookup(Protocol):
    """Return the cached fingerprints for a root when its entry is still live.

    A protocol rather than a bare ``Callable`` alias because the lookup takes
    its window and comparison basis as keyword-only arguments, which a
    positional ``Callable[...]`` signature cannot express.
    """

    def __call__(
        self,
        resolved: Path,
        *,
        now: float,
        ttl: float,
        directory_fingerprints: RegistryPathFingerprints | None,
    ) -> RegistryPathFingerprints | None:
        """Return the live cached fingerprints, or ``None`` to recollect."""
        ...


_registry_fingerprint_cache: RegistryFingerprintCache = {}


def clear_fingerprint_cache() -> None:
    """Clear the TTL-backed registry-tree fingerprint cache."""
    _registry_fingerprint_cache.clear()


def bind_tree_fingerprint_collectors(
    *,
    is_bundled_root: BundledRootPredicate,
    bundled_ttl: float,
    live_cached: LiveFingerprintLookup,
    collect_directory: DirectoryFingerprintCollector,
    collect_sources: SourceFingerprintCollector,
    store: FingerprintStore,
) -> tuple[
    Callable[[Path], RegistryPathFingerprints],
    Callable[[Path], RegistryPathFingerprints],
]:
    """Bind the cache policy once for cached and uncached tree walks."""

    def collect_cached(resolved: Path) -> RegistryPathFingerprints:
        return collect_registry_tree_fingerprints_for_cache(
            resolved,
            use_cache=True,
            fingerprint_cache=_registry_fingerprint_cache,
            is_bundled_root=is_bundled_root,
            bundled_ttl=bundled_ttl,
            live_cached=live_cached,
            collect_directory=collect_directory,
            collect_sources=collect_sources,
            store=store,
        )

    def collect_uncached(resolved: Path) -> RegistryPathFingerprints:
        return collect_registry_tree_fingerprints_for_cache(
            resolved,
            use_cache=False,
            fingerprint_cache=_registry_fingerprint_cache,
            is_bundled_root=is_bundled_root,
            bundled_ttl=bundled_ttl,
            live_cached=live_cached,
            collect_directory=collect_directory,
            collect_sources=collect_sources,
            store=store,
        )

    return collect_cached, collect_uncached


def refresh_toml_fingerprint_after_load_error(
    path: Path,
    initial_error: RegistryLoadError,
) -> RegistryPathFingerprint:
    """Re-read a TOML fingerprint before classifying a concurrent-load error."""
    try:
        return toml_file_fingerprint(path)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{path}: registry TOML changed during load. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(path), "registry_tree_quiescent": False, "operation": "toml_load_refresh"},
            ),
        ) from refresh_error


def collect_registry_tree_fingerprints_for_cache(
    resolved: Path,
    *,
    use_cache: bool,
    fingerprint_cache: RegistryFingerprintCache,
    is_bundled_root: BundledRootPredicate,
    bundled_ttl: float,
    live_cached: LiveFingerprintLookup,
    collect_directory: DirectoryFingerprintCollector,
    collect_sources: SourceFingerprintCollector,
    store: FingerprintStore,
) -> RegistryPathFingerprints:
    """Build a complete cache key while rejecting a concurrent directory edit.

    A cached tuple may be served only where the freshness check that guards it
    covers everything the tuple asserts. The entry holds the COMPLETE tree
    fingerprint -- one ``(path, size, mtime_ns, content_digest)`` row per
    directory and per TOML file -- and it is that tuple which keys the compiled
    registry, the disk pickle and the validation verdict. The only cheap
    freshness signal available is the directory walk, and writing to an existing
    file moves no parent-directory stat on any mainstream filesystem, so a
    directory-only check cannot speak for the per-file rows.

    For the package-bundled tree the per-file rows carry an empty content digest
    by construction (read-only package data, see
    :func:`~dev.registry.compiler.loader_cache.is_bundled_registry_path`),
    and its window is a declared bound on how often the 17k-entry walk is
    redone rather than a claim about file content, so the directory-level check
    is the whole of what its entry asserts. A mutable authoring tree's rows DO
    carry content digests, and nothing short of re-reading the files can
    validate them -- which is the entire cost the cache would be skipping. Such
    a tree therefore recomputes its complete fingerprint on every call and is
    neither served from nor written to the cache; the compiled result is still
    reused through the fingerprint-keyed caches above.
    """
    started = time.time()
    bundled = use_cache and is_bundled_root(resolved)

    if bundled:
        hit = live_cached(resolved, now=started, ttl=bundled_ttl, directory_fingerprints=None)
        if hit is not None:
            return hit

    directory_fingerprints = collect_directory(resolved)
    if bundled:
        hit = live_cached(
            resolved,
            now=started,
            ttl=bundled_ttl,
            directory_fingerprints=directory_fingerprints,
        )
        if hit is not None:
            return hit

    fingerprints = (*directory_fingerprints, *collect_sources(resolved))
    refreshed_directory_fingerprints = collect_directory(resolved)
    if refreshed_directory_fingerprints != directory_fingerprints:
        fingerprint_cache.pop(resolved, None)
        raise RegistryLoadError(
            f"{resolved}: registry directory changed during cache fingerprinting",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={
                    "path": str(resolved),
                    "registry_tree_quiescent": False,
                    "operation": "cache_fingerprint",
                },
            ),
        )
    if bundled:
        store(
            resolved,
            directory_fingerprints=refreshed_directory_fingerprints,
            fingerprints=fingerprints,
            walk_started=started,
            bundled=bundled,
        )
    return fingerprints


def _live_cached_fingerprints(
    resolved: Path,
    *,
    now: float,
    ttl: float,
    directory_fingerprints: RegistryPathFingerprints | None,
) -> RegistryPathFingerprints | None:
    """Return the cached fingerprints when the entry is still live, else ``None``."""
    entry = _registry_fingerprint_cache.get(resolved)
    if entry is None:
        return None
    cached_time, cached_directories, cached_value = entry
    if now - cached_time >= ttl:
        return None
    if directory_fingerprints is None or cached_directories == directory_fingerprints:
        return cached_value
    _registry_fingerprint_cache.pop(resolved, None)
    return None


def _registry_source_fingerprints(resolved: Path) -> RegistryPathFingerprints:
    """Fingerprint every catalogue TOML the loader will subsequently re-open."""
    # Import here because fact providers use this module's fingerprint type.
    # Their registered inputs are nevertheless compiler inputs and must affect
    # the authority identity that publication records.
    from .fact_providers import collect_registered_fact_provider_fingerprints

    fingerprints: list[RegistryPathFingerprint] = []
    for path in scan_directory(resolved / "legal", pattern="*.toml"):
        fingerprints.append(toml_file_fingerprint(path))
    modelos_dir = resolved / "modelos"
    for path in scan_directory(modelos_dir, pattern="*.toml"):
        fingerprints.append(toml_file_fingerprint(path))
    for entry in scan_directory(modelos_dir):
        fingerprints.extend(_modelo_directory_fingerprints(entry))
    schema_path = resolved / "user_profile" / "schema.toml"
    if schema_path.is_file():
        fingerprints.append(toml_file_fingerprint(schema_path))
    return (*fingerprints, *collect_registered_fact_provider_fingerprints(resolved))


def _store_registry_fingerprints(
    resolved: Path,
    *,
    directory_fingerprints: RegistryPathFingerprints,
    fingerprints: RegistryPathFingerprints,
    walk_started: float,
    bundled: bool,
) -> None:
    """Record freshly walked fingerprints for the bundled-root TTL window."""
    stamped = time.time() if bundled else walk_started
    _registry_fingerprint_cache[resolved] = (stamped, directory_fingerprints, fingerprints)


def collect_registry_directory_fingerprints(resolved: Path) -> RegistryPathFingerprints:
    """Collect the directory-layout rows used to validate a registry walk."""
    if not resolved.is_dir():
        return ()

    def _raise_walk_error(exc: OSError) -> None:
        raise RegistryLoadError(
            f"{resolved}: registry directory could not be walked during cache fingerprinting; {exc}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(resolved), "registry_tree_quiescent": False, "operation": "directory_walk"},
            ),
        ) from exc

    fingerprints: list[RegistryPathFingerprint] = []
    for dirpath, dirnames, _filenames in os.walk(resolved, onerror=_raise_walk_error):
        dirnames.sort()
        fingerprints.append(_directory_fingerprint(Path(dirpath)))
    return tuple(fingerprints)


def collect_modelo_directory_fingerprints(resolved: Path) -> RegistryPathFingerprints:
    """Collect all directory-mode source rows for one modelo."""
    manifest_path = resolved / "manifest.toml"
    fingerprints: list[RegistryPathFingerprint] = list(collect_registry_directory_fingerprints(resolved))
    fingerprints.append(toml_file_fingerprint(manifest_path))
    for path in scan_directory(resolved / "locales", pattern="*.toml"):
        fingerprints.append(toml_file_fingerprint(path))
    for path in scan_directory(resolved / "revisions", pattern="*.toml", recursive=True):
        fingerprints.append(toml_file_fingerprint(path))
    return tuple(fingerprints)


def _modelo_directory_fingerprints(entry: Path) -> RegistryPathFingerprints:
    """Return fingerprints for one directory-mode modelo entry."""
    if not (entry.is_dir() and (entry / "manifest.toml").is_file()):
        return ()
    fingerprints: list[RegistryPathFingerprint] = [toml_file_fingerprint(entry / "manifest.toml")]
    for path in scan_directory(entry / "locales", pattern="*.toml", recursive=True):
        fingerprints.append(toml_file_fingerprint(path))
    for rev_path in scan_directory(entry / "revisions", pattern="*.toml", recursive=True):
        fingerprints.append(toml_file_fingerprint(rev_path))
    return tuple(fingerprints)


def _directory_fingerprint(path: Path) -> RegistryPathFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise RegistryLoadError(
            f"{path}: registry directory could not be fingerprinted; {exc}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(path), "registry_tree_quiescent": False, "operation": "directory_stat"},
            ),
        ) from exc
    return str(path), stat.st_size, stat.st_mtime_ns, ""


def _collect_registry_tree_fingerprints_uncached(resolved: Path) -> RegistryPathFingerprints:
    return collect_registry_tree_fingerprints_for_cache(
        resolved,
        use_cache=False,
        fingerprint_cache=_registry_fingerprint_cache,
        is_bundled_root=is_bundled_registry_root,
        bundled_ttl=BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS,
        live_cached=_live_cached_fingerprints,
        collect_directory=collect_registry_directory_fingerprints,
        collect_sources=_registry_source_fingerprints,
        store=_store_registry_fingerprints,
    )


def collect_registry_tree_fingerprints(resolved: Path) -> RegistryPathFingerprints:
    """Collect the complete canonical cache key for one registry tree."""
    return collect_registry_tree_fingerprints_for_cache(
        resolved,
        use_cache=True,
        fingerprint_cache=_registry_fingerprint_cache,
        is_bundled_root=is_bundled_registry_root,
        bundled_ttl=BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS,
        live_cached=_live_cached_fingerprints,
        collect_directory=collect_registry_directory_fingerprints,
        collect_sources=_registry_source_fingerprints,
        store=_store_registry_fingerprints,
    )


def _toml_fingerprint(path: Path) -> RegistryPathFingerprint:
    return toml_file_fingerprint(path)


__all__ = [
    "clear_fingerprint_cache",
    "collect_modelo_directory_fingerprints",
    "collect_registry_directory_fingerprints",
    "collect_registry_tree_fingerprints",
    "refresh_toml_fingerprint_after_load_error",
]
