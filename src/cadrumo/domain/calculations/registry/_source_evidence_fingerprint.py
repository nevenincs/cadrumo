"""Filesystem fingerprints for registry source-evidence cache keys.

The fingerprint is intentionally limited to source evidence that is explicitly
provided by a caller. The installed product does not infer checkout-only test
fixtures from package paths; registry validation may still receive an explicit
specimen root in authoring and test contexts.

Collecting the fingerprint means stat-ing every file under the evidence roots,
and the authority collects it on every load, so it is bounded exactly as the
registry tree fingerprint is: an evidence root that lies inside the read-only
package data observes a bounded window, and any other root -- an explicit
specimen tree a caller can rewrite mid-run -- is walked afresh on every call.

See Also:
    :func:`~domain.calculations.registry._loader_cache.is_bundled_registry_root`
        The sibling predicate that admits the registry tree to its own window.
"""

from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

from ....core.directory_scan import DirectoryEntryKind, scan_directory
from ._loader_cache import BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS

SourceEvidenceFingerprint = tuple[tuple[str, int, int], ...]

__all__ = (
    "SourceEvidenceFingerprint",
    "clear_source_evidence_fingerprint_cache",
    "collect_source_evidence_fingerprints",
)

_evidence_fingerprint_cache: dict[tuple[Path, ...], tuple[float, SourceEvidenceFingerprint]] = {}


def clear_source_evidence_fingerprint_cache() -> None:
    """Clear the window-bounded source-evidence fingerprint cache."""
    _evidence_fingerprint_cache.clear()


def collect_source_evidence_fingerprints(
    source_root: Path | None,
    *,
    justificante_corpus_root: Path | None = None,
) -> SourceEvidenceFingerprint:
    """Return ``(path, size, mtime_ns)`` fingerprints for source evidence files.

    Served from the cache only for roots inside the package-bundled data tree,
    which is read-only package data on the same premise the bundled registry
    window rests on, and only within
    :data:`~domain.calculations.registry._loader_cache.BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS`
    -- one number for one premise rather than two that can drift apart. Any
    root outside that tree is a caller-supplied specimen tree that the run
    itself can rewrite, so it is never cached and never served.

    Returns:
        One fingerprint per evidence file, ordered by root and then by path.
    """
    roots = _source_evidence_roots(
        source_root,
        justificante_corpus_root=justificante_corpus_root,
    )
    if not roots:
        return ()
    if not all(_is_bundled_evidence_root(root) for root in roots):
        return _walk_source_evidence(roots)

    started = time.time()
    entry = _evidence_fingerprint_cache.get(roots)
    if entry is not None and started - entry[0] < BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS:
        return entry[1]

    fingerprints = _walk_source_evidence(roots)
    # Stamped at walk COMPLETION, so the walk's own multi-hundred-millisecond
    # cost is not charged against the window it opens; a start stamp on a loaded
    # host can consume the window outright and defeat the cache exactly when it
    # is worth most.
    _evidence_fingerprint_cache[roots] = (time.time(), fingerprints)
    return fingerprints


def _walk_source_evidence(roots: tuple[Path, ...]) -> SourceEvidenceFingerprint:
    fingerprints: list[tuple[str, int, int]] = []
    for root in roots:
        for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES):
            stat = path.stat()
            fingerprints.append((str(path), stat.st_size, stat.st_mtime_ns))
    return tuple(fingerprints)


@lru_cache(maxsize=1)
def _bundled_data_root() -> Path:
    """Return the resolved package-bundled data root, computed once per process."""
    from ....core.resources import bundled_path

    return bundled_path().resolve()


def _is_bundled_evidence_root(root: Path) -> bool:
    """Whether ``root`` lies inside the package-bundled data tree.

    Fails closed to ``False`` -- always walk -- on any resources boundary
    failure, so an unusual install can never be mistaken for the immutable tree.
    """
    try:
        return root.is_relative_to(_bundled_data_root())
    except (ImportError, OSError, ValueError):
        return False


def _source_evidence_roots(
    source_root: Path | None,
    *,
    justificante_corpus_root: Path | None,
) -> tuple[Path, ...]:
    candidates: list[Path] = []
    if source_root is not None:
        resolved = source_root.expanduser().resolve()
        candidates.extend((resolved / "corpus", resolved / "src" / "cadrumo" / "_data" / "corpus"))
    if justificante_corpus_root is not None:
        candidates.append(justificante_corpus_root.expanduser().resolve())

    seen: set[Path] = set()
    roots: list[Path] = []
    for candidate in candidates:
        resolved_candidate = candidate.resolve()
        if resolved_candidate in seen or not resolved_candidate.is_dir():
            continue
        seen.add(resolved_candidate)
        roots.append(resolved_candidate)
    return tuple(roots)
