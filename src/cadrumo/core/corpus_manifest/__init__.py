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

There is no human CLI for corpus verification. This module's API is the
whole surface: :func:`build_corpus_manifest`, :func:`verify_corpus_manifest`,
and :func:`save_corpus_manifest`, re-exported through
``cadrumo.adapters.persistence.storage`` and driven programmatically by its
consumers. The same API owns manifest regeneration after an intentional
corpus update.

This module also builds and verifies distributable corpus *bundles*: a
single ``.zip`` archive carrying every corpus file plus an embedded
:class:`CorpusManifest` (see :func:`build_corpus_bundle` and
:func:`verify_corpus_bundle`), for offline installation of the bundled
corpus checksummed against its own manifest. The SHA-256 manifest alone is
an integrity gate, not an authenticity gate; :mod:`._bundle_signing`
(re-exported here) adds the Ed25519 authenticity layer on top -- see
:func:`sign_corpus_bundle` and :func:`verify_corpus_bundle_signature`.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import ClassVar

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Hex64Str
from ...core.directory_scan import scan_directory
from ..errors.hierarchy import CoreValidationError as _CoreValidationError
from ..hashing import canonical_json_bytes as _canonical_json_bytes
from ..hashing import hash_file as _hash_file
from ..hashing import sha256_hex as _sha256_hex
from ..logging import get_logger as _get_logger
from ..time import now as _clock_now
from ..time import validate_utc_aware
from ._bundle_signing import (
    CorpusBundleSigningError,
    CorpusBundleSigningKeyNotFoundError,
    CorpusSigningKeypair,
    CorpusSigningPublicKey,
    SignedCorpusBundle,
    assert_corpus_bundle_signature_verifies,
    corpus_signing_public_key,
    generate_corpus_signing_keypair,
    load_corpus_signing_keypair,
    sign_corpus_bundle,
    verify_corpus_bundle_signature,
)
from .errors import (
    CorpusBundleError,
    CorpusBundleVerificationError,
    CorpusManifestDriftError,
    CorpusManifestError,
    CorpusManifestTamperError,
)

_logger = _get_logger(__name__)

_BUNDLE_MANIFEST_MEMBER = "corpus.manifest.json"
"""Canonical archive-member name for a bundle's embedded manifest."""

_MANIFEST_VERSION = 1
"""Wire-format version of the on-disk manifest schema."""

_MANIFEST_FILENAME = "corpus.manifest.json"
"""Canonical filename for the manifest sidecar inside each corpus root."""


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
    sha256: Hex64Str
    content_length: int = Field(ge=0)

    @field_validator("relative_path")
    @classmethod
    def _validate_relative_path(cls, value: str) -> str:
        if value in {".", "..", ""}:
            raise CorpusManifestError(
                translated_message="errors.integrity.integrity_storage_corpus_manifest",
                context={"relative_path": str(value), "dot_token": True},
            )
        # PurePosixPath ignores backslashes (treats them as part of a
        # single path token), so a Windows-style ``..\\escape`` would
        # slip past the dot-part walk below. Reject them explicitly.
        if "\\" in value:
            raise CorpusManifestError(
                translated_message="errors.integrity.integrity_storage_corpus_manifest",
                context={"relative_path": str(value), "posix_separators_only": False},
            )
        pure = PurePosixPath(value)
        if pure.is_absolute():
            raise CorpusManifestError(
                translated_message="errors.integrity.integrity_storage_corpus_manifest",
                context={"relative_path": str(value), "absolute": True},
            )
        for part in pure.parts:
            if part in {"..", "."}:
                raise CorpusManifestError(
                    translated_message="errors.integrity.integrity_storage_corpus_manifest",
                    context={"relative_path": str(value), "contains_dot_tokens": True},
                )
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
    manifest_sha256: Hex64Str

    @field_validator("generated_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        try:
            return validate_utc_aware(value)
        except _CoreValidationError as exc:
            raise CorpusManifestError(
                translated_message="errors.integrity.integrity_storage_corpus_manifest",
                context={
                    "field": "generated_at",
                    "utc_aware": False,
                    "validation_error_type": type(exc).__name__,
                },
            ) from exc


class _ManifestPayloadValidationError(ValueError):
    """Base error for an invalid raw manifest payload before I/O translation."""

    __bare_base_rationale__: ClassVar[str] = (
        "private manifest-payload validation carrier; raised only inside "
        "_validate_raw_manifest_payload so the file loader and the bundle loader apply identical "
        "schema/version/digest checks, and converted by every caller into the registry-bound "
        "CorpusManifestError / CorpusBundleError / CorpusManifestTamperError before leaving the "
        "module"
    )


class _MalformedManifestPayloadError(_ManifestPayloadValidationError):
    """Raw payload cannot be parsed into the manifest schema."""


class _UnsupportedManifestVersionError(_ManifestPayloadValidationError):
    """Raw payload declares a version this consumer cannot admit."""


class _TamperedManifestPayloadError(_ManifestPayloadValidationError):
    """Raw payload's recorded self-digest differs from its canonical body."""


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
        """Return ``True`` iff the corpus on disk matches the manifest exactly.

        Not merely a hash check over the tracked files: an untracked file
        appearing (``added``) and a tracked file vanishing (``removed``)
        each make the corpus dirty on their own, with every remaining
        hash still matching.
        """
        return not (self.added or self.removed or self.changed)


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
    for path in scan_directory(corpus_root, recursive=True):
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

    Serialised through :func:`~cadrumo.core.hashing.canonical_json_bytes`, the
    project's one canonical-JSON form, so the same logical input yields the same
    bytes on every read. This previously restated that serialisation inline and
    passed ``ensure_ascii=False``, which the shared helper does not — a
    non-ASCII corpus path therefore hashed differently here than under every
    other content-addressed digest in the tree.
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
    return _canonical_json_bytes(payload)


def _validate_raw_manifest_payload(raw: str | bytes) -> CorpusManifest:
    """Parse and verify the source-agnostic self-attesting manifest payload.

    Callers retain responsibility for reading their Path or ZIP member and for
    translating these private validation errors into their public boundary
    errors. Keeping the validation here ensures both sources apply identical
    schema, version, canonical-body, and self-digest checks.
    """
    try:
        manifest = CorpusManifest.model_validate_json(raw)
    except (ValueError, ValidationError) as exc:
        raise _MalformedManifestPayloadError(str(exc)) from exc
    if manifest.manifest_version > _MANIFEST_VERSION:
        raise _UnsupportedManifestVersionError(str(manifest.manifest_version))
    body = _canonical_manifest_body(
        manifest_version=manifest.manifest_version,
        corpus_root_name=manifest.corpus_root_name,
        generated_at=manifest.generated_at,
        entries=manifest.entries,
    )
    if manifest.manifest_sha256 != _sha256_hex(body):
        raise _TamperedManifestPayloadError()
    return manifest


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
            the canonical clock :func:`core.time.now` is consulted, so
            the deterministic-output seam (:func:`core.time.frozen_clock`)
            pins it under replay; an explicit value still overrides.

    Returns:
        A :class:`CorpusManifest` covering every regular file under
        ``corpus_root``.

    Raises:
        FileNotFoundError: If ``corpus_root`` does not exist.
        NotADirectoryError: If ``corpus_root`` is not a directory.
    """
    if not corpus_root.exists():
        raise FileNotFoundError(corpus_root)
    if not corpus_root.is_dir():
        raise NotADirectoryError(corpus_root)
    if generated_at is None:
        generated_at = _clock_now()
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
    manifest_sha256 = _sha256_hex(body)
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
    payload = manifest.model_dump_json()
    # Deferred import: mirrors the existing deferred-import discipline in
    # this module (see build_corpus_bundle) -- core.atomic_write
    # transitively imports core.locks, which imports core.config; kept
    # local to avoid widening this module's eager import surface.
    from ..atomic_write import atomic_write_text

    try:
        atomic_write_text(resolved, payload, encoding="utf-8")
        _logger.debug("save_corpus_manifest: wrote manifest to %s", resolved)
    except OSError:
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
        manifest = _validate_raw_manifest_payload(raw)
    except _MalformedManifestPayloadError as exc:
        _logger.error("load_corpus_manifest: structurally invalid manifest at %s", target, exc_info=True)
        raise CorpusManifestError(
            translated_message="errors.integrity.integrity_storage_corpus_manifest",
            context={
                "manifest_path": str(target),
                "structurally_valid": False,
                "validation_error_type": type(exc).__name__,
            },
        ) from exc
    except _UnsupportedManifestVersionError as exc:
        raise CorpusManifestError(
            translated_message="errors.integrity.integrity_storage_corpus_manifest",
            context={"manifest_path": str(target), "supported_version": str(_MANIFEST_VERSION)},
        ) from exc
    except _TamperedManifestPayloadError as exc:
        _logger.error(
            "load_corpus_manifest: tamper detected in manifest at %s (recorded sha256 does not match body)",
            target,
        )
        raise CorpusManifestTamperError(
            translated_message="errors.integrity.integrity_storage_corpus_manifest_tamper",
            context={
                "manifest_path": str(target),
                "manifest_sha256_matches_body": False,
                "digest_field": "manifest_sha256",
            },
        ) from exc
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
            translated_message="errors.integrity.integrity_storage_corpus_manifest_drift",
            context={
                "corpus_root_name": manifest.corpus_root_name,
                "added": diff.added,
                "removed": diff.removed,
                "changed": diff.changed,
            },
        )
    _logger.debug("assert_corpus_clean: corpus %r is clean", manifest.corpus_root_name)


class CorpusBundleVerification(BaseModel):
    """Result of verifying a bundle's archived files against its embedded manifest.

    An empty ``missing`` / ``unexpected`` / ``mismatched`` triple means
    the bundle is clean and safe to extract. ``missing`` is a file the
    manifest declares but the archive does not carry; ``unexpected`` is
    an archive member the manifest does not declare; ``mismatched`` is
    an archived file whose SHA-256 or byte length disagrees with its
    manifest record.
    """

    model_config = _STRICT_FROZEN

    manifest: CorpusManifest
    missing: tuple[str, ...] = Field(default=())
    unexpected: tuple[str, ...] = Field(default=())
    mismatched: tuple[str, ...] = Field(default=())

    @property
    def is_clean(self) -> bool:
        """Return ``True`` iff every archived file matches the embedded manifest."""
        return not (self.missing or self.unexpected or self.mismatched)


def build_corpus_bundle(
    corpus_root: Path,
    *,
    corpus_root_name: str,
    output_path: Path,
    generated_at: datetime | None = None,
) -> CorpusManifest:
    """Pack ``corpus_root`` into a checksummed zip bundle at ``output_path``.

    Walks ``corpus_root`` with the same file-selection rules as
    :func:`build_corpus_manifest` (hidden files and the manifest
    sidecar itself are excluded), builds the manifest, then writes a
    new zip archive containing the manifest under
    :data:`_BUNDLE_MANIFEST_MEMBER` plus every corpus file under its
    POSIX-relative path. The archive is assembled fully in memory, then
    persisted through :func:`~cadrumo.core.atomic_write.atomic_write_bytes`
    (standard tier: tempfile sibling, fsync, :func:`os.replace`,
    best-effort parent-directory fsync), so a failure mid-write never
    leaves a partial bundle at ``output_path``.

    Args:
        corpus_root: The corpus directory to bundle.
        corpus_root_name: Stable identifier recorded in the manifest
            (mirrors :func:`build_corpus_manifest`).
        output_path: Destination ``.zip`` path. Parent directories are
            created as needed; an existing file at this path is
            overwritten.
        generated_at: Optional override for the manifest timestamp;
            see :func:`build_corpus_manifest`.

    Returns:
        The :class:`CorpusManifest` embedded in the written bundle.

    Raises:
        FileNotFoundError: If ``corpus_root`` does not exist.
        NotADirectoryError: If ``corpus_root`` is not a directory.
    """
    manifest = build_corpus_manifest(
        corpus_root,
        corpus_root_name=corpus_root_name,
        generated_at=generated_at,
    )
    resolved_output = output_path.resolve()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(_BUNDLE_MANIFEST_MEMBER, manifest.model_dump_json())
        for entry in manifest.entries:
            archive.write(corpus_root / entry.relative_path, arcname=entry.relative_path)
    # Deferred import: core.atomic_write imports core.logging, whose runtime
    # configuration depends on settings. Keep it local to avoid widening this
    # module's eager import surface during settings bootstrap.
    from ..atomic_write import atomic_write_bytes

    atomic_write_bytes(resolved_output, buffer.getvalue())
    _logger.info(
        "build_corpus_bundle: wrote %r bundle with %d files to %s",
        corpus_root_name,
        len(manifest.entries),
        resolved_output,
    )
    return manifest


def verify_corpus_bundle(bundle_path: Path) -> CorpusBundleVerification:
    """Verify a zip bundle's archived files against its embedded manifest.

    Loads the manifest member (:data:`_BUNDLE_MANIFEST_MEMBER`),
    re-derives its self-attesting digest (a mismatch means the manifest
    member itself was tampered with, raising
    :class:`CorpusManifestTamperError`), then re-hashes every other
    archive member and compares against the manifest's per-file
    records.

    Args:
        bundle_path: Path to the ``.zip`` bundle to verify.

    Returns:
        A :class:`CorpusBundleVerification` enumerating any missing,
        unexpected, or hash-mismatched files. An empty result means the
        bundle is clean.

    Raises:
        FileNotFoundError: If ``bundle_path`` does not exist.
        CorpusBundleError: If ``bundle_path`` is not a valid zip
            archive, or the embedded manifest is absent, structurally
            invalid, or at an unsupported version.
        CorpusManifestTamperError: If the manifest member's recorded
            ``manifest_sha256`` does not match its own body.
    """
    if not bundle_path.exists():
        raise FileNotFoundError(bundle_path)
    try:
        with zipfile.ZipFile(bundle_path, mode="r") as archive:
            return _verify_open_corpus_bundle(archive)
    except zipfile.BadZipFile as exc:
        raise CorpusBundleError(
            translated_message="errors.integrity.integrity_storage_corpus_bundle",
            context={
                "bundle_path": str(bundle_path),
                "valid_zip_archive": False,
                "archive_error_type": type(exc).__name__,
            },
        ) from exc


def _verify_open_corpus_bundle(archive: zipfile.ZipFile) -> CorpusBundleVerification:
    names = frozenset(archive.namelist())
    if _BUNDLE_MANIFEST_MEMBER not in names:
        raise CorpusBundleError(
            translated_message="errors.integrity.integrity_storage_corpus_bundle",
            context={"manifest_member": str(_BUNDLE_MANIFEST_MEMBER), "manifest_member_present": False},
        )
    manifest = _load_bundle_manifest(archive)
    expected = {entry.relative_path: entry for entry in manifest.entries}
    archived_files = frozenset(name for name in names if name != _BUNDLE_MANIFEST_MEMBER and not name.endswith("/"))

    missing = tuple(sorted(set(expected) - archived_files))
    unexpected = tuple(sorted(archived_files - set(expected)))
    mismatched: list[str] = []
    for relative in sorted(archived_files & set(expected)):
        recorded = expected[relative]
        actual_bytes = archive.read(relative)
        actual_sha256 = _sha256_hex(actual_bytes)
        if actual_sha256 != recorded.sha256 or len(actual_bytes) != recorded.content_length:
            mismatched.append(relative)
    return CorpusBundleVerification(
        manifest=manifest,
        missing=missing,
        unexpected=unexpected,
        mismatched=tuple(mismatched),
    )


def _load_bundle_manifest(archive: zipfile.ZipFile) -> CorpusManifest:
    raw = archive.read(_BUNDLE_MANIFEST_MEMBER)
    try:
        return _validate_raw_manifest_payload(raw)
    except _MalformedManifestPayloadError as exc:
        raise CorpusBundleError(
            translated_message="errors.integrity.integrity_storage_corpus_bundle",
            context={"embedded_manifest_structurally_valid": False, "validation_error_type": type(exc).__name__},
        ) from exc
    except _UnsupportedManifestVersionError as exc:
        raise CorpusBundleError(
            translated_message="errors.integrity.integrity_storage_corpus_bundle",
            context={
                "embedded_manifest_version": str(exc),
                "supported_version": str(_MANIFEST_VERSION),
            },
        ) from exc
    except _TamperedManifestPayloadError as exc:
        raise CorpusManifestTamperError(
            translated_message="errors.integrity.integrity_storage_corpus_manifest_tamper",
            context={
                "manifest_member": str(_BUNDLE_MANIFEST_MEMBER),
                "manifest_sha256_matches_body": False,
                "digest_field": "manifest_sha256",
            },
        ) from exc


def assert_corpus_bundle_verifies(bundle_path: Path) -> CorpusManifest:
    """Verify ``bundle_path`` and raise on any drift; return the embedded manifest on success.

    The operator-facing assertion: call this before extracting or
    trusting a downloaded/copied bundle. Raises
    :class:`CorpusBundleVerificationError` naming every missing,
    unexpected, or mismatched file when the bundle does not verify
    clean.
    """
    result = verify_corpus_bundle(bundle_path)
    if not result.is_clean:
        _logger.warning(
            "assert_corpus_bundle_verifies: bundle %s failed verification (missing=%d unexpected=%d mismatched=%d)",
            bundle_path,
            len(result.missing),
            len(result.unexpected),
            len(result.mismatched),
        )
        raise CorpusBundleVerificationError(
            translated_message="errors.integrity.integrity_storage_corpus_bundle_verification",
            context={
                "bundle_path": str(bundle_path),
                "missing": result.missing,
                "unexpected": result.unexpected,
                "mismatched": result.mismatched,
            },
        )
    _logger.info(
        "assert_corpus_bundle_verifies: bundle %s verified clean (%d files)",
        bundle_path,
        len(result.manifest.entries),
    )
    return result.manifest


__all__ = [
    "CorpusBundleError",
    "CorpusBundleSigningError",
    "CorpusBundleSigningKeyNotFoundError",
    "CorpusBundleVerification",
    "CorpusBundleVerificationError",
    "CorpusEntry",
    "CorpusManifest",
    "CorpusManifestDiff",
    "CorpusManifestDriftError",
    "CorpusManifestError",
    "CorpusManifestTamperError",
    "CorpusSigningKeypair",
    "CorpusSigningPublicKey",
    "SignedCorpusBundle",
    "assert_corpus_bundle_signature_verifies",
    "assert_corpus_bundle_verifies",
    "assert_corpus_clean",
    "build_corpus_bundle",
    "build_corpus_manifest",
    "corpus_signing_public_key",
    "generate_corpus_signing_keypair",
    "load_corpus_manifest",
    "load_corpus_signing_keypair",
    "manifest_path_for",
    "save_corpus_manifest",
    "sign_corpus_bundle",
    "verify_corpus_bundle",
    "verify_corpus_bundle_signature",
    "verify_corpus_manifest",
]
