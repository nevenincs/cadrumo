"""Orchestration for TTL-backed registry fingerprint cache keys."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from ._errors import RegistryLoadError
from ._loader_cache import toml_file_fingerprint

type RegistryPathFingerprint = tuple[str, int, int, str]
type RegistryPathFingerprints = tuple[RegistryPathFingerprint, ...]
type RegistryFingerprintCache = dict[
    Path,
    tuple[float, RegistryPathFingerprints, RegistryPathFingerprints],
]
type DirectoryFingerprintCollector = Callable[[Path], RegistryPathFingerprints]
type SourceFingerprintCollector = Callable[[Path], RegistryPathFingerprints]
type BundledRootPredicate = Callable[[Path], bool]
type LiveFingerprintLookup = Callable[
    [Path, float, float, RegistryPathFingerprints | None],
    RegistryPathFingerprints | None,
]
type FingerprintStore = Callable[..., None]

_registry_fingerprint_cache: RegistryFingerprintCache = {}


def clear_fingerprint_cache() -> None:
    """Clear the TTL-backed registry-tree fingerprint cache."""
    _registry_fingerprint_cache.clear()


def bind_tree_fingerprint_collectors(
    *,
    is_bundled_root: BundledRootPredicate,
    bundled_ttl: float,
    mutable_ttl: float,
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
            mutable_ttl=mutable_ttl,
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
            mutable_ttl=mutable_ttl,
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
            f"{path}: registry TOML changed during load; retry after concurrent registry writes settle. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
        ) from refresh_error


def collect_registry_tree_fingerprints_for_cache(
    resolved: Path,
    *,
    use_cache: bool,
    fingerprint_cache: RegistryFingerprintCache,
    is_bundled_root: BundledRootPredicate,
    bundled_ttl: float,
    mutable_ttl: float,
    live_cached: LiveFingerprintLookup,
    collect_directory: DirectoryFingerprintCollector,
    collect_sources: SourceFingerprintCollector,
    store: FingerprintStore,
) -> RegistryPathFingerprints:
    """Build a complete cache key while rejecting a concurrent directory edit."""
    started = time.time()
    bundled = use_cache and is_bundled_root(resolved)
    ttl = bundled_ttl if bundled else mutable_ttl

    if bundled:
        hit = live_cached(resolved, now=started, ttl=ttl, directory_fingerprints=None)
        if hit is not None:
            return hit

    directory_fingerprints = collect_directory(resolved)
    if use_cache:
        hit = live_cached(
            resolved,
            now=started,
            ttl=ttl,
            directory_fingerprints=directory_fingerprints,
        )
        if hit is not None:
            return hit

    fingerprints = (*directory_fingerprints, *collect_sources(resolved))
    refreshed_directory_fingerprints = collect_directory(resolved)
    if refreshed_directory_fingerprints != directory_fingerprints:
        fingerprint_cache.pop(resolved, None)
        raise RegistryLoadError(
            f"{resolved}: registry directory changed during cache fingerprinting; "
            "retry after concurrent registry writes settle",
        )
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
