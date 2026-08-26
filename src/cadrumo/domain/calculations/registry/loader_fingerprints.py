"""Orchestration for TTL-backed registry fingerprint cache keys."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .errors import RegistryFailureClassification, RegistryFailureCondition, RegistryLoadError
from .loader_cache import toml_file_fingerprint

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
    :func:`~domain.calculations.registry.loader_cache.is_bundled_registry_path`),
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


__all__ = [
    "bind_tree_fingerprint_collectors",
    "clear_fingerprint_cache",
    "collect_registry_tree_fingerprints_for_cache",
    "refresh_toml_fingerprint_after_load_error",
]
