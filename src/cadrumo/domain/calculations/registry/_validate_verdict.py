"""Persistent registry-validation verdict cache.

A green :meth:`RegistryValidator.validate_registry` run persists a small
verdict record keyed by the complete registry fingerprint tuples the loader
already computes (registry tree plus convenio, and the source-evidence set),
the package version, and the outcome. On a later load a fingerprint match lets
:class:`ValidatedRegistryAuthority` construct with validation marked done and
skip the multi-second re-validation of an immutable bundled registry. This is
the ADR ``mcp-call-latency`` D1 inversion: the build and continuous integration
are the validation gate; the runtime asserts fingerprint identity only.

Two verdict homes back the same key:

- a writable per-storage-root file under the settings-derived cache directory,
  covering mutable development trees; and
- a read-only file the release build stamps beside the bundled registry tree,
  so the very first touch on an end-user machine skips runtime validation.

Every verdict is derived and rebuildable per ``no-legacy-compatibility``: a key
mismatch, or an unreadable/foreign record, deletes the writable verdict and
forces a full re-validation. No migration, no version bridge, no read-tolerance
of an old shape.
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
from ._loader_cache import is_bundled_registry_root

FingerprintTuples = tuple[tuple[str, int, int], ...]
"""``(path, size, mtime_ns)`` fingerprint tuples, as the loader collects them."""

VERDICT_OUTCOME_GREEN = "green"
"""The only persisted outcome: a failed validation raises and stores nothing."""

_VERDICT_FILENAME_PREFIX = "cadrumo_validation_verdict_"
_BUNDLED_VERDICT_FILENAME = "aeat-validation-verdict.json"
_ROOT_HASH_LEN = 16

_LOGGER = logging.getLogger(__name__)


class ValidationVerdict(BaseModel):
    """A persisted proof that a registry tree validated green.

    ``verdict_key`` folds the complete fingerprint tuples and the package
    version into one hash (see :func:`compute_verdict_key`); the runtime skips
    validation only when a stored green verdict's key equals the freshly
    recomputed key.
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

    The two fingerprint groups are the exact tuples the authority already
    passes as its :func:`functools.lru_cache` key, so correctness reduces to
    fingerprint identity per the registry authority-flow rule. A group label is
    mixed in so a tuple moving between the registry and source-evidence groups
    cannot collide.

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


def verdict_cache_path(root: Path) -> Path:
    """Return the writable per-storage-root verdict file for ``root``.

    Derived from :attr:`~core.config.Settings.cadrumo_validation_verdict_cache_dir`
    (``<storage-root>/cache/registry-verdict`` by default), never a shared OS
    temp directory that two host users could collide in. The filename embeds a
    hash of the resolved root path so distinct registry roots (the bundled tree
    and a development authoring tree) never share one file; a fingerprint change
    on a given root reuses the same filename, so the mismatch branch deletes and
    rewrites in place.

    Returns:
        The verdict file location for ``root`` under the settings cache dir.
    """
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:_ROOT_HASH_LEN]
    return load_settings().cadrumo_validation_verdict_cache_dir / f"{_VERDICT_FILENAME_PREFIX}{digest}.json"


def bundled_verdict_path(root: Path) -> Path | None:
    """Return the read-only shipped verdict location for the bundled tree.

    The release build stamps the bundled-tree verdict here so the first
    end-user touch skips runtime validation; returns ``None`` for any mutable
    authoring tree, which relies on the per-storage-root verdict instead. The
    file is a sibling of the registry root, never inside it, so its own presence
    is not walked by the registry-tree fingerprint it certifies.

    Returns:
        The shipped verdict path when ``root`` is the bundled tree, else ``None``.
    """
    if not is_bundled_registry_root(root):
        return None
    return root.parent / _BUNDLED_VERDICT_FILENAME


def read_verdict(path: Path) -> ValidationVerdict | None:
    """Read and strict-parse a verdict, or ``None`` if absent/unreadable/foreign.

    Returns:
        The parsed :class:`ValidationVerdict`, or ``None`` on any read or
        validation failure (the caller then recomputes deterministically).
    """
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ValidationVerdict.model_validate(raw)
    except Exception:
        _LOGGER.debug("Ignoring unreadable or foreign validation verdict at %s; recomputing", path, exc_info=True)
        return None


def write_verdict(path: Path, verdict: ValidationVerdict) -> None:
    """Persist ``verdict`` to ``path`` atomically via a sibling temp file."""
    temp_name = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tf:
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


def registry_validation_is_certified(root: Path, *, verdict_key: str) -> bool:
    """Whether a persisted green verdict certifies ``verdict_key`` for ``root``.

    Checks the writable per-storage-root verdict first, deleting it on any
    mismatch so the next load recomputes; then the read-only shipped bundled
    verdict. A hit lets the authority construct with validation marked done and
    skip ``validate_registry`` entirely, including on ``modelo list``.

    Returns:
        ``True`` when a stored green verdict's key equals ``verdict_key``.
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
        if shipped_verdict is not None and _verdict_matches(shipped_verdict, verdict_key):
            return True
    return False


def certify_registry_validation(
    root: Path,
    *,
    verdict_key: str,
    package_version: str = __version__,
) -> Path:
    """Persist a fresh green verdict for ``root`` after a green validation.

    Returns:
        The writable verdict path the fresh record was written to.
    """
    path = verdict_cache_path(root)
    write_verdict(
        path,
        ValidationVerdict(verdict_key=verdict_key, package_version=package_version, outcome=VERDICT_OUTCOME_GREEN),
    )
    return path


def _verdict_matches(verdict: ValidationVerdict, verdict_key: str) -> bool:
    return verdict.outcome == VERDICT_OUTCOME_GREEN and verdict.verdict_key == verdict_key
