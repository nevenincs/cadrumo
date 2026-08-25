"""Persistent registry-validation verdict cache.

Not itself a validator: this module holds no checks, only the persisted
CERTIFICATION that a prior ``validate_registry`` run passed. Named without
the ``_validate`` prefix its predecessor carried (``_validate_verdict.py``),
which asserted a validation role this module never had -- it stamps and
reads verdicts a real validator already produced.

A green ``validate_registry`` run persists a verdict keyed by the registry
identity, source evidence, package version, canonical loader-code fingerprint,
and the outcome. On a later load a
match lets :class:`ValidatedRegistryAuthority` construct with validation marked
done and skip the multi-second re-validation of an immutable bundled registry
(build and continuous integration are the gate;
the runtime asserts fingerprint identity only).

Two homes back the verdict: a writable per-storage-root file (mutable trees)
and a read-only file the release build stamps beside the bundled tree. Both key
on the tree identity that :mod:`~domain.calculations.registry._identity` owns --
this module derives no identity of its own, so a verdict and the authority that
consults it can never disagree about which tree was certified. The shipped
verdict is honoured only for a STAMPED identity, because only a stamped tree has
an install-stable identity to certify. Every verdict is derived and rebuildable
per ``no-legacy-compatibility``: a key mismatch or a foreign record deletes the
writable verdict and re-validates in full -- no migration.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .... import __version__
from ....core import StorageCategory, storage_path
from ....core.atomic_write import atomic_write_best_effort_text
from ....core.external_constants import UTF_8_ENCODING
from ._compiled_cache import loader_code_fingerprint
from ._identity import RegistryIdentity
from ._loader_cache import is_bundled_registry_root

SourceEvidenceFingerprintTuples = tuple[tuple[str, int, int], ...]
"""``(path, size, mtime_ns)`` tuples for source-evidence files (no content digest)."""

VERDICT_OUTCOME_GREEN = "green"

_VERDICT_FILENAME_PREFIX = "cadrumo_validation_verdict_"
_BUNDLED_VERDICT_FILENAME = "aeat-validation-verdict.json"
_ROOT_HASH_LEN = 16

_LOGGER = logging.getLogger(__name__)


class RegistryValidationVerdict(BaseModel):
    """A persisted proof that a registry tree validated green.

    ``verdict_key`` folds the authority inputs and the canonical loader-code
    fingerprint into one hash; the runtime skips validation only when a stored
    green verdict's key equals the freshly recomputed key.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    verdict_key: str
    package_version: str
    outcome: str


def compute_verdict_key(
    *,
    identity_digest: str,
    source_evidence_fingerprints: SourceEvidenceFingerprintTuples,
    package_version: str = __version__,
    loader_code_fingerprint_override: str | None = None,
) -> str:
    """Bind tree, evidence, and current registry validation code into one key.

    ``identity_digest`` comes from
    :func:`~domain.calculations.registry._identity.resolve_registry_identity`
    and is the ONLY registry-tree input: this module never re-derives identity
    from fingerprint tuples, so a verdict cannot be keyed on a different view of
    the tree than the authority cached. A group label is mixed in so a value
    moving between groups cannot collide.

    Returns:
        The hex SHA-256 digest binding the identity and validation code to
        ``package_version``.
    """
    hasher = hashlib.sha256()
    hasher.update(package_version.encode("utf-8"))
    code_fingerprint = (
        loader_code_fingerprint() if loader_code_fingerprint_override is None else loader_code_fingerprint_override
    )
    hasher.update(b"registry-code")
    hasher.update(code_fingerprint.encode("utf-8"))
    hasher.update(b"identity")
    hasher.update(identity_digest.encode("utf-8"))
    hasher.update(b"source")
    for entry in source_evidence_fingerprints:
        for part in entry:
            hasher.update(str(part).encode("utf-8"))
    return hasher.hexdigest()


def compute_shipped_verdict_key(
    *,
    identity_digest: str,
    package_version: str = __version__,
    loader_code_fingerprint_override: str | None = None,
) -> str:
    """Compute the install-stable key for the release-stamped bundled verdict.

    Drops the source-evidence group that :func:`compute_verdict_key` folds:
    those tuples carry absolute paths and ``mtime_ns``, neither of which
    survives packaging. What remains is the release version, the canonical
    path-independent loader-code fingerprint, and the stamped install-stable
    tree identity, all byte-stable from build machine to install. Install byte
    integrity is owned by the package-manager digest chain; any change the stamp
    can see re-validates.

    Returns:
        The hex SHA-256 digest over the version and the stamped identity.
    """
    hasher = hashlib.sha256()
    hasher.update(b"shipped-registry-verdict")
    hasher.update(package_version.encode("utf-8"))
    code_fingerprint = (
        loader_code_fingerprint() if loader_code_fingerprint_override is None else loader_code_fingerprint_override
    )
    hasher.update(code_fingerprint.encode("utf-8"))
    hasher.update(identity_digest.encode("utf-8"))
    return hasher.hexdigest()


def stamp_bundled_verdict(
    *,
    identity_digest: str,
    output_path: Path,
    package_version: str = __version__,
) -> RegistryValidationVerdict:
    """Write the install-stable bundled-tree verdict at ``output_path``.

    Called by the release build against the tree it is packaging, immediately
    after that tree's identity stamp is written, so the first end-user touch of
    this release skips validation. The caller supplies the identity digest so
    this module adds no loader import edge and derives no identity of its own.

    Returns:
        The written :class:`RegistryValidationVerdict`.
    """
    key = compute_shipped_verdict_key(
        identity_digest=identity_digest,
        package_version=package_version,
    )
    verdict = RegistryValidationVerdict(
        verdict_key=key,
        package_version=package_version,
        outcome=VERDICT_OUTCOME_GREEN,
    )
    write_verdict(output_path, verdict)
    return verdict


def verdict_cache_path(root: Path) -> Path:
    """Return the writable per-storage-root verdict file for ``root``.

    Resolved through :func:`~core.storage_path` for
    ``StorageCategory.VALIDATION_VERDICT_CACHE``
    (``<storage-root>/cache/registry-verdict``), never a shared OS temp dir and
    never a direct read of ``cadrumo_validation_verdict_cache_dir`` here -- the
    accessor is what stays correct if the member's resolution ever gains a
    case. The filename embeds a hash of the resolved root path so distinct
    registry roots never share a file, while a fingerprint change on one root
    reuses the same filename so the mismatch branch deletes and rewrites in
    place.

    Returns:
        The verdict file location for ``root`` under the settings cache dir.
    """
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:_ROOT_HASH_LEN]
    return storage_path(StorageCategory.VALIDATION_VERDICT_CACHE) / f"{_VERDICT_FILENAME_PREFIX}{digest}.json"


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


def read_verdict(path: Path) -> RegistryValidationVerdict | None:
    """Read and strict-parse a verdict, or ``None`` if absent/unreadable/foreign.

    Returns:
        The parsed :class:`RegistryValidationVerdict`, or ``None`` on any read failure.
    """
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding=UTF_8_ENCODING))
        return RegistryValidationVerdict.model_validate(raw)
    except Exception:
        _LOGGER.debug("Ignoring unreadable or foreign validation verdict at %s; recomputing", path, exc_info=True)
        return None


def write_verdict(path: Path, verdict: RegistryValidationVerdict) -> None:
    """Persist ``verdict`` to ``path`` atomically via a sibling temp file."""
    try:
        atomic_write_best_effort_text(path, verdict.model_dump_json(), encoding=UTF_8_ENCODING)
    except Exception:
        _LOGGER.warning("Could not write validation verdict at %s", path, exc_info=True)


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
    identity: RegistryIdentity,
    package_version: str = __version__,
) -> bool:
    """Whether a persisted green verdict certifies this tree for ``root``.

    Checks the writable per-storage-root verdict first (matched on the full
    ``verdict_key``), deleting it on any mismatch; then, only when the tree's
    identity is STAMPED and a shipped verdict sits beside it, matches that
    verdict on :func:`compute_shipped_verdict_key`.

    The stamped-identity requirement is what makes the shipped branch sound: a
    shipped verdict certifies the tree the build packaged, and only a stamp
    establishes that this IS that tree. A walked identity -- any authoring or
    editable tree -- never reaches the shipped branch, so no amount of verdict
    material beside a mutable tree can certify it. Neither branch performs a
    filesystem walk. A hit skips ``validate_registry`` entirely.

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
    if not identity.is_stamped:
        return False
    shipped = bundled_verdict_path(root)
    if shipped is None:
        return False
    shipped_verdict = read_verdict(shipped)
    if shipped_verdict is None:
        return False
    shipped_key = compute_shipped_verdict_key(
        identity_digest=identity.digest,
        package_version=package_version,
    )
    return _verdict_matches(shipped_verdict, shipped_key)


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
        RegistryValidationVerdict(
            verdict_key=verdict_key,
            package_version=package_version,
            outcome=VERDICT_OUTCOME_GREEN,
        ),
    )
    return path


def _verdict_matches(verdict: RegistryValidationVerdict, verdict_key: str) -> bool:
    return verdict.outcome == VERDICT_OUTCOME_GREEN and verdict.verdict_key == verdict_key
