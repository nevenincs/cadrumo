"""Persistent registry-validation verdict cache.

A green ``validate_registry`` run persists a verdict keyed by the registry
fingerprint tuples, the package version, and the outcome. On a later load a
match lets :class:`ValidatedRegistryAuthority` construct with validation marked
done and skip the multi-second re-validation of an immutable bundled registry
(ADR ``mcp-call-latency`` D1: build and continuous integration are the gate;
the runtime asserts fingerprint identity only).

Two homes back the verdict: a writable per-storage-root file (mutable trees,
keyed on the full ``(path, size, mtime)`` tuples) and a read-only file the
release build stamps beside the bundled tree (keyed on the install-stable
``(relative-path, size)`` plus version, since mtime does not survive
packaging). Every verdict is derived and rebuildable per
``no-legacy-compatibility``: a key mismatch or a foreign record deletes the
writable verdict and re-validates in full -- no migration.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .... import __version__
from ....core.config import load_settings
from ....core.external_constants import UTF_8_ENCODING
from ._loader_cache import is_bundled_registry_root

FingerprintTuples = tuple[tuple[str, int, int], ...]
"""``(path, size, mtime_ns)`` fingerprint tuples, as the loader collects them."""

VERDICT_OUTCOME_GREEN = "green"

_VERDICT_FILENAME_PREFIX = "cadrumo_validation_verdict_"
_BUNDLED_VERDICT_FILENAME = "aeat-validation-verdict.json"
_ROOT_HASH_LEN = 16

_LOGGER = logging.getLogger(__name__)


class ValidationVerdict(BaseModel):
    """A persisted proof that a registry tree validated green.

    ``verdict_key`` folds the fingerprint tuples and the package version into
    one hash; the runtime skips validation only when a stored green verdict's
    key equals the freshly recomputed key.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict_key: str
    package_version: str
    outcome: str


def compute_verdict_key(
    *,
    registry_fingerprints: FingerprintTuples,
    source_evidence_fingerprints: FingerprintTuples,
    package_version: str = __version__,
) -> str:
    """Hash the complete fingerprint tuples plus the package version into one key.

    The two groups are the exact tuples the authority passes as its
    ``lru_cache`` key, so correctness reduces to fingerprint identity per the
    registry authority-flow rule. A group label is mixed in so a tuple moving
    between groups cannot collide.

    Returns:
        The hex SHA-256 digest binding the fingerprints to ``package_version``.
    """
    hasher = hashlib.sha256()
    hasher.update(package_version.encode("utf-8"))
    for label, group in (("registry", registry_fingerprints), ("source", source_evidence_fingerprints)):
        hasher.update(label.encode("utf-8"))
        for path, size, mtime_ns in group:
            hasher.update(path.encode("utf-8"))
            hasher.update(str(size).encode("utf-8"))
            hasher.update(str(mtime_ns).encode("utf-8"))
    return hasher.hexdigest()


def compute_bundled_verdict_key(
    *,
    registry_fingerprints: FingerprintTuples,
    registry_root: Path,
    package_version: str = __version__,
) -> str:
    """Compute the install-stable key for the release-stamped bundled verdict.

    The per-storage-root key (:func:`compute_verdict_key`) folds absolute paths
    and ``mtime_ns``, which do NOT survive packaging: the cohort builds the
    wheel from a ``git archive`` extraction and installation rewrites mtimes and
    directory sizes. This key drops the mtime component and the directory
    entries (both packaging-unstable) and keys on the release version plus the
    sorted ``(relative-path, size)`` of every registry FILE -- stable from the
    build machine to every install because the bundled tree is byte-identical
    per release. Per the ADR, install byte integrity is owned by the
    package-manager digest chain; any file-set or size change re-validates.

    Returns:
        The hex SHA-256 digest over the version, relative paths, and sizes.
    """
    resolved_root = registry_root.resolve()
    entries: list[tuple[str, int]] = []
    for path, size, _mtime_ns in registry_fingerprints:
        candidate = Path(path)
        if not candidate.is_file():
            continue
        try:
            relative = candidate.resolve().relative_to(resolved_root).as_posix()
        except ValueError:
            relative = candidate.name
        entries.append((relative, size))
    hasher = hashlib.sha256()
    hasher.update(b"bundled-registry")
    hasher.update(package_version.encode("utf-8"))
    for relative, size in sorted(entries):
        hasher.update(relative.encode("utf-8"))
        hasher.update(str(size).encode("utf-8"))
    return hasher.hexdigest()


def stamp_bundled_verdict(
    *,
    registry_fingerprints: FingerprintTuples,
    registry_root: Path,
    output_path: Path,
    package_version: str = __version__,
) -> ValidationVerdict:
    """Write the install-stable bundled-tree verdict at ``output_path``.

    Called by the release build against the tree it is packaging so the first
    end-user touch of this release skips validation. The caller supplies the
    fingerprints so this module adds no loader import edge.

    Returns:
        The written :class:`ValidationVerdict`.
    """
    key = compute_bundled_verdict_key(
        registry_fingerprints=registry_fingerprints,
        registry_root=registry_root,
        package_version=package_version,
    )
    verdict = ValidationVerdict(verdict_key=key, package_version=package_version, outcome=VERDICT_OUTCOME_GREEN)
    write_verdict(output_path, verdict)
    return verdict


def verdict_cache_path(root: Path) -> Path:
    """Return the writable per-storage-root verdict file for ``root``.

    Derived from :attr:`~core.config.Settings.cadrumo_validation_verdict_cache_dir`
    (``<storage-root>/cache/registry-verdict``), never a shared OS temp dir. The
    filename embeds a hash of the resolved root path so distinct registry roots
    never share a file, while a fingerprint change on one root reuses the same
    filename so the mismatch branch deletes and rewrites in place.

    Returns:
        The verdict file location for ``root`` under the settings cache dir.
    """
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:_ROOT_HASH_LEN]
    return load_settings().cadrumo_validation_verdict_cache_dir / f"{_VERDICT_FILENAME_PREFIX}{digest}.json"


def shipped_verdict_location(registry_root: Path) -> Path:
    """Return the shipped-verdict file location for ``registry_root``.

    A sibling of the registry root, never inside it, so its own presence is not
    walked by the fingerprint it certifies. Shared by the release build (which
    stamps here) and the runtime read, so the two never disagree.

    Returns:
        The ``aeat-validation-verdict.json`` path beside ``registry_root``.
    """
    return registry_root.parent / _BUNDLED_VERDICT_FILENAME


def bundled_verdict_path(root: Path) -> Path | None:
    """Return the read-only shipped verdict location for the bundled tree.

    Returns ``None`` for any mutable authoring tree, which relies on the
    per-storage-root verdict instead.

    Returns:
        The shipped verdict path when ``root`` is the bundled tree, else ``None``.
    """
    if not is_bundled_registry_root(root):
        return None
    return shipped_verdict_location(root)


def read_verdict(path: Path) -> ValidationVerdict | None:
    """Read and strict-parse a verdict, or ``None`` if absent/unreadable/foreign.

    Returns:
        The parsed :class:`ValidationVerdict`, or ``None`` on any read failure.
    """
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding=UTF_8_ENCODING))
        return ValidationVerdict.model_validate(raw)
    except Exception:
        _LOGGER.debug("Ignoring unreadable or foreign validation verdict at %s; recomputing", path, exc_info=True)
        return None


def write_verdict(path: Path, verdict: ValidationVerdict) -> None:
    """Persist ``verdict`` to ``path`` atomically via a sibling temp file."""
    temp_name = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding=UTF_8_ENCODING) as tf:
            tf.write(verdict.model_dump_json())
            temp_name = tf.name
        os.replace(temp_name, path)
    except Exception:
        _LOGGER.warning("Could not write validation verdict at %s", path, exc_info=True)
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except Exception:
                _LOGGER.debug("Could not remove temporary validation verdict file %s", temp_name, exc_info=True)


def delete_verdict(path: Path) -> None:
    """Best-effort delete of a stale or mismatched verdict file."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        _LOGGER.debug("Could not delete validation verdict at %s", path, exc_info=True)


def registry_validation_is_certified(
    root: Path,
    *,
    verdict_key: str,
    registry_fingerprints: FingerprintTuples,
    package_version: str = __version__,
) -> bool:
    """Whether a persisted green verdict certifies this tree for ``root``.

    Checks the writable per-storage-root verdict first (matched on the full
    ``verdict_key``), deleting it on any mismatch; then, only when a shipped
    bundled verdict is present, matches it on the install-stable
    :func:`compute_bundled_verdict_key`. That key is computed lazily -- only on
    the first-touch path where a shipped verdict exists and the writable verdict
    has not hit -- so its file-stat pass never runs on a warm load or a dev tree
    with no shipped verdict. A hit skips ``validate_registry`` entirely.

    Returns:
        ``True`` when a stored green verdict certifies the current tree.
    """
    writable = verdict_cache_path(root)
    verdict = read_verdict(writable)
    if verdict is not None:
        if _verdict_matches(verdict, verdict_key):
            return True
        # Mismatch: delete-not-migrate, forcing a full re-validation next.
        delete_verdict(writable)
    shipped = bundled_verdict_path(root)
    if shipped is not None:
        shipped_verdict = read_verdict(shipped)
        if shipped_verdict is not None:
            bundled_key = compute_bundled_verdict_key(
                registry_fingerprints=registry_fingerprints,
                registry_root=root,
                package_version=package_version,
            )
            if _verdict_matches(shipped_verdict, bundled_key):
                return True
    return False


def certify_registry_validation(
    root: Path,
    *,
    verdict_key: str,
    package_version: str = __version__,
) -> Path:
    """Persist a fresh green verdict for ``root``, returning the path written."""
    path = verdict_cache_path(root)
    write_verdict(
        path,
        ValidationVerdict(verdict_key=verdict_key, package_version=package_version, outcome=VERDICT_OUTCOME_GREEN),
    )
    return path


def _verdict_matches(verdict: ValidationVerdict, verdict_key: str) -> bool:
    return verdict.outcome == VERDICT_OUTCOME_GREEN and verdict.verdict_key == verdict_key
