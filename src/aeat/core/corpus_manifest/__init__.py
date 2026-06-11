"""Directory-level integrity manifest for CORPUS-class on-disk data.

The substrate's :class:`SensitivityClass.CORPUS` policy mandates
SHA-256 integrity tracking for plaintext-at-rest reference material.
This module is the canonical implementation: a single manifest model
covers every file under a corpus root with a per-file SHA-256 + size
record, plus a self-attesting ``manifest_sha256`` so a manifest-only
tamper is detectable.

Manifests are plaintext JSON on disk (corpus material is plaintext;
the manifest is the integrity gate, not the secrecy gate). Per-record
fields are validated against path-traversal at construction.

Operator workflow (via the ``aeat security verify-corpus`` CLI):

- ``aeat security verify-corpus --corpus manuals`` — re-walk the
  manuals root and exit non-zero with a per-file diff on drift.
- ``aeat security verify-corpus --corpus manuals --regenerate``
  — re-walk and rewrite the manifest in place after intentional
  corpus updates.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import TypedDict

from pydantic import BaseModel, Field, ValidationError, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..errors import CoreValidationError as _CoreValidationError
from ..logging import get_logger as _get_logger
from ..time._utc import validate_utc_aware
from ._errors import CorpusManifestDriftError, CorpusManifestError, CorpusManifestTamperError

_logger = _get_logger(__name__)

_MANIFEST_VERSION = 1
"""Wire-format version of the on-disk manifest schema."""

_MANIFEST_FILENAME = "corpus.manifest.json"
"""Canonical filename for the manifest sidecar inside each corpus root."""


# Sha-256 content-fingerprint shape shared by the per-entry file digest and
# the self-attesting manifest digest. Stays bare-str under ADR Rule 7
# (fingerprint, not identity); factored to a single module-local constraint
# kwargs mapping to remove the duplication of the shape literal.
class _Sha256FieldKwargs(TypedDict):
    min_length: int
    max_length: int
    pattern: str


_CORPUS_SHA256_KWARGS: _Sha256FieldKwargs = {
    "min_length": 64,
    "max_length": 64,
    "pattern": r"^[0-9a-f]{64}$",
}


class CorpusEntry(BaseModel):
    """One file's integrity record under a corpus root.

    Attributes:
        relative_path: POSIX-style path from the corpus root. Validated
            against path-traversal at construction.
        sha256: Lower-case hex SHA-256 of the file's bytes.
        content_length: Size of the file in bytes (>= 0; the empty file
            is permitted).
    """

    model_config = _STRICT_FROZEN

    relative_path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(**_CORPUS_SHA256_KWARGS)
    content_length: int = Field(ge=0)

    @field_validator("relative_path")
    @classmethod
    def _validate_relative_path(cls, value: str) -> str:
        if value in {".", "..", ""}:
            raise CorpusManifestError(f"relative_path must not be a dot token: {value!r}")
        # PurePosixPath ignores backslashes (treats them as part of a
        # single path token), so a Windows-style ``..\\escape`` would
        # slip past the dot-part walk below. Reject them explicitly.
        if "\\" in value:
            raise CorpusManifestError(
                f"relative_path must use POSIX-style separators only: {value!r}",
            )
        pure = PurePosixPath(value)
        if pure.is_absolute():
            raise CorpusManifestError(f"relative_path must not be absolute: {value!r}")
        for part in pure.parts:
            if part in {"..", "."}:
                raise CorpusManifestError(f"relative_path must not contain dot tokens: {value!r}")
        return value


class CorpusManifest(BaseModel):
    """Self-attesting manifest covering every file under a corpus root.

    The ``manifest_sha256`` field is a SHA-256 over the canonical JSON
    serialisation of ``(manifest_version, corpus_root_name,
    generated_at, entries)`` with sorted keys. On load, the same digest
    is re-derived and compared; a mismatch raises
    :class:`CorpusManifestTamperError`.

    Attributes:
        manifest_version: Wire-format version. Higher than the consumer
            supports raises :class:`CorpusManifestError` at load time.
        corpus_root_name: Stable identifier for the corpus
            (``"manuals"``, ``"legal"``, etc.).
        generated_at: UTC timestamp the manifest was built.
        entries: Frozen tuple of :class:`CorpusEntry` records, sorted by
            ``relative_path`` for deterministic ``manifest_sha256``.
        manifest_sha256: Self-attesting digest. Re-computed on load.
    """

    model_config = _STRICT_FROZEN

    manifest_version: int = Field(default=_MANIFEST_VERSION, ge=1)
    corpus_root_name: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    entries: tuple[CorpusEntry, ...]
    manifest_sha256: str = Field(**_CORPUS_SHA256_KWARGS)

    @field_validator("generated_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        try:
            return validate_utc_aware(value)
        except _CoreValidationError as exc:
            raise CorpusManifestError(str(exc)) from exc


class CorpusManifestDiff(BaseModel):
    """Result of comparing a manifest against the live corpus on disk.

    A manifest is in drift iff any of ``added`` / ``removed`` /
    ``changed`` is non-empty.
    """

    model_config = _STRICT_FROZEN

    corpus_root_name: str
    added: tuple[str, ...] = Field(default=())
    removed: tuple[str, ...] = Field(default=())
    changed: tuple[str, ...] = Field(default=())

    @property
    def is_clean(self) -> bool:
        """Return ``True`` iff every tracked file's hash matches the manifest."""
        return not (self.added or self.removed or self.changed)


def _hash_file(path: Path) -> tuple[str, int]:
    """Return ``(sha256_hex, content_length)`` for ``path``.

    Streams the file in 64 KiB chunks so manuals-sized PDFs do not
    inflate memory usage.
    """
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
            length += len(chunk)
    return digest.hexdigest(), length


def _iter_corpus_files(corpus_root: Path) -> Iterator[Path]:
    """Yield every regular file under ``corpus_root`` excluding the manifest.

    Hidden files / dirs (leading ``.``) are skipped — they are typically
    git internals or editor cruft that should not be tracked. The
    manifest sidecar at the root is excluded so the manifest does not
    cover itself recursively.

    Symlinks are skipped: a hostile actor with corpus-tree write access
    could plant a symlink pointing to a file outside the corpus and
    cause the manifest to attest to content the corpus does not own.
    The substrate's classification policy maps the corpus class to
    integrity-tracked-only, but the manifest must reflect the literal
    on-disk corpus contents — symlinks defeat that contract.
    """
    for path in sorted(corpus_root.rglob("*")):
        # ``is_symlink()`` is checked first because ``is_file()`` follows
        # the symlink target on most filesystems and would mask the link.
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(corpus_root).parts):
            continue
        if path.name == _MANIFEST_FILENAME and path.parent == corpus_root:
            continue
        yield path


def _canonical_manifest_body(
    *,
    manifest_version: int,
    corpus_root_name: str,
    generated_at: datetime,
    entries: tuple[CorpusEntry, ...],
) -> bytes:
    """Build the canonical bytes the ``manifest_sha256`` digests over.

    Stable across reads because ``json.dumps`` with ``sort_keys=True``
    + ``separators=(",", ":")`` + ISO timestamp formatting yields the
    same bytes for the same logical input.
    """
    payload = {
        "manifest_version": manifest_version,
        "corpus_root_name": corpus_root_name,
        "generated_at": generated_at.isoformat(),
        "entries": [
            {
                "relative_path": entry.relative_path,
                "sha256": entry.sha256,
                "content_length": entry.content_length,
            }
            for entry in entries
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_corpus_manifest(
    corpus_root: Path,
    *,
    corpus_root_name: str,
    generated_at: datetime | None = None,
) -> CorpusManifest:
    """Walk ``corpus_root`` and build a freshly self-signed manifest.

    Args:
        corpus_root: The corpus directory to walk.
        corpus_root_name: Stable identifier for this corpus (logged in
            the manifest body so an operator can grep for it).
        generated_at: Optional override for the timestamp. When ``None``
            the current UTC time is used. Tests pin this for
            determinism.

    Returns:
        A :class:`CorpusManifest` covering every regular file under
        ``corpus_root``.

    Raises:
        FileNotFoundError: If ``corpus_root`` does not exist.
        NotADirectoryError: If ``corpus_root`` is not a directory.
    """
    from datetime import UTC
    from datetime import datetime as _dt

    if not corpus_root.exists():
        raise FileNotFoundError(corpus_root)
    if not corpus_root.is_dir():
        raise NotADirectoryError(corpus_root)
    if generated_at is None:
        generated_at = _dt.now(UTC)
    raw_entries: list[CorpusEntry] = []
    for path in _iter_corpus_files(corpus_root):
        sha256_hex, length = _hash_file(path)
        relative = PurePosixPath(*path.relative_to(corpus_root).parts).as_posix()
        raw_entries.append(
            CorpusEntry(
                relative_path=relative,
                sha256=sha256_hex,
                content_length=length,
            ),
        )
    raw_entries.sort(key=lambda entry: entry.relative_path)
    entries = tuple(raw_entries)
    _logger.debug("build_corpus_manifest: hashed %d files under %s", len(entries), corpus_root)
    body = _canonical_manifest_body(
        manifest_version=_MANIFEST_VERSION,
        corpus_root_name=corpus_root_name,
        generated_at=generated_at,
        entries=entries,
    )
    manifest_sha256 = hashlib.sha256(body).hexdigest()
    _logger.debug(
        "build_corpus_manifest: built manifest for %r with %d entries (sha256=%s)",
        corpus_root_name,
        len(entries),
        manifest_sha256[:12],
    )
    return CorpusManifest(
        manifest_version=_MANIFEST_VERSION,
        corpus_root_name=corpus_root_name,
        generated_at=generated_at,
        entries=entries,
        manifest_sha256=manifest_sha256,
    )


def verify_corpus_manifest(
    corpus_root: Path,
    *,
    manifest: CorpusManifest,
) -> CorpusManifestDiff:
    """Compare ``manifest`` against the live state of ``corpus_root``.

    Returns a diff enumerating files added since the manifest was
    built, files removed, and files whose SHA-256 changed.
    Empty diff = clean.

    Args:
        corpus_root: The corpus directory to verify.
        manifest: The manifest to verify against.

    Returns:
        A :class:`CorpusManifestDiff` enumerating added, removed,
        and changed files. An empty diff means the corpus is clean.

    Raises:
        FileNotFoundError: If ``corpus_root`` does not exist.
    """
    if not corpus_root.exists():
        raise FileNotFoundError(corpus_root)
    expected: dict[str, CorpusEntry] = {entry.relative_path: entry for entry in manifest.entries}
    seen: set[str] = set()
    added: list[str] = []
    changed: list[str] = []
    for path in _iter_corpus_files(corpus_root):
        relative = PurePosixPath(*path.relative_to(corpus_root).parts).as_posix()
        seen.add(relative)
        actual_sha256, actual_length = _hash_file(path)
        if relative not in expected:
            added.append(relative)
            continue
        recorded = expected[relative]
        if recorded.sha256 != actual_sha256 or recorded.content_length != actual_length:
            changed.append(relative)
    removed = sorted(set(expected.keys()) - seen)
    return CorpusManifestDiff(
        corpus_root_name=manifest.corpus_root_name,
        added=tuple(sorted(added)),
        removed=tuple(removed),
        changed=tuple(sorted(changed)),
    )


def save_corpus_manifest(manifest: CorpusManifest, target: Path) -> None:
    """Atomically persist ``manifest`` as JSON to ``target``."""
    resolved = target.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.model_dump_json()
    # NamedTemporaryFile raising means no file was created; the outer
    # except re-raises cleanly.
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=resolved.parent,
            prefix=f"{resolved.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, resolved)
        from ..locks import fsync_parent_dir

        fsync_parent_dir(resolved)
        _logger.debug("save_corpus_manifest: wrote manifest to %s", resolved)
    except OSError:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        _logger.error("save_corpus_manifest: failed to write manifest to %s", resolved, exc_info=True)
        raise


def load_corpus_manifest(target: Path) -> CorpusManifest:
    """Load and verify a manifest's self-attesting digest.

    Args:
        target: Source file. Must exist.

    Returns:
        The validated :class:`CorpusManifest` loaded from ``target``.

    Raises:
        FileNotFoundError: If ``target`` does not exist.
        CorpusManifestError: If the on-disk version exceeds the
            consumer's supported version, or the JSON is structurally
            invalid.
        CorpusManifestTamperError: If the manifest's recorded
            ``manifest_sha256`` does not match the digest re-derived
            from the rest of its body.
    """
    if not target.exists():
        raise FileNotFoundError(target)
    raw = target.read_text(encoding="utf-8")
    try:
        manifest = CorpusManifest.model_validate_json(raw)
    except (OSError, ValueError, ValidationError) as exc:
        _logger.error("load_corpus_manifest: structurally invalid manifest at %s", target, exc_info=True)
        raise CorpusManifestError(f"manifest at {target} is structurally invalid: {exc}") from exc
    if manifest.manifest_version > _MANIFEST_VERSION:
        raise CorpusManifestError(
            f"manifest at {target} is at version {manifest.manifest_version}; "
            f"consumer supports up to {_MANIFEST_VERSION}",
        )
    body = _canonical_manifest_body(
        manifest_version=manifest.manifest_version,
        corpus_root_name=manifest.corpus_root_name,
        generated_at=manifest.generated_at,
        entries=manifest.entries,
    )
    expected_sha256 = hashlib.sha256(body).hexdigest()
    if manifest.manifest_sha256 != expected_sha256:
        _logger.error(
            "load_corpus_manifest: tamper detected in manifest at %s (recorded sha256 does not match body)",
            target,
        )
        raise CorpusManifestTamperError(
            f"manifest at {target}: recorded manifest_sha256 does not match the body digest "
            "(an attacker may have edited the manifest body without recomputing the digest).",
        )
    _logger.debug(
        "load_corpus_manifest: loaded %r with %d entries from %s",
        manifest.corpus_root_name,
        len(manifest.entries),
        target,
    )
    return manifest


def manifest_path_for(corpus_root: Path) -> Path:
    """Return the canonical manifest sidecar path inside ``corpus_root``."""
    return corpus_root / _MANIFEST_FILENAME


def assert_corpus_clean(corpus_root: Path) -> None:
    """Verify the on-disk manifest matches the corpus root.

    Loads the manifest sidecar, walks the corpus, and raises
    :class:`CorpusManifestDriftError` on any drift. This is the
    operator-facing assertion used by the CI gate.
    """
    manifest = load_corpus_manifest(manifest_path_for(corpus_root))
    diff = verify_corpus_manifest(corpus_root, manifest=manifest)
    if not diff.is_clean:
        _logger.warning(
            "assert_corpus_clean: drift detected in %r (added=%d removed=%d changed=%d)",
            manifest.corpus_root_name,
            len(diff.added),
            len(diff.removed),
            len(diff.changed),
        )
        raise CorpusManifestDriftError(
            f"corpus drift in {manifest.corpus_root_name!r}: "
            f"added={list(diff.added)} removed={list(diff.removed)} changed={list(diff.changed)}",
        )
    _logger.debug("assert_corpus_clean: corpus %r is clean", manifest.corpus_root_name)


__all__ = [
    "CorpusEntry",
    "CorpusManifest",
    "CorpusManifestDiff",
    "CorpusManifestDriftError",
    "CorpusManifestError",
    "CorpusManifestTamperError",
    "assert_corpus_clean",
    "build_corpus_manifest",
    "load_corpus_manifest",
    "manifest_path_for",
    "save_corpus_manifest",
    "verify_corpus_manifest",
]
