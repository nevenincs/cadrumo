"""Master-key rotation for ciphertext-at-rest envelopes.

The substrate's at-rest encryption derives a per-consumer key from the
project master key via HKDF-SHA256 over a stable, per-consumer
``hkdf_context``. Callers supply the old and new keys as
:class:`MasterKeyProvider` instances. Rotating the master key requires
walking every consumer's persisted ciphertext, decrypting under the old
key, and re-writing under the new key. This module is the single
sanctioned path for that operation.

Rotation operates at the bytes level - it never parses the inner
:class:`Envelope` payload. That keeps the rotation contract
content-preserving across every consumer's payload type without
requiring rotation code to know the typed payload schemas.

The rotation is **per-file atomic** - each cipher envelope is
re-written via tempfile + ``os.replace`` so a crash mid-rotation
leaves either the old or the new ciphertext on disk, never a torn
state. The whole rotation is **not** transactional across files:
both keys must remain available until rotation completes.

Detection of "already rotated" works by attempting to decrypt under
the new key first; on AEAD-tag verify success the file is skipped.
On failure, the helper falls back to the old key.
"""

from __future__ import annotations

import binascii
import hashlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError

from ....core import STRICT_FROZEN_CONFIG
from ....core.external_constants import UTF_8_ENCODING
from ....core.locks import exclusive_file_lock, fsync_parent_dir
from ....core.logging import get_logger
from ....core.time import now
from .blob_store._blob_store import EncryptedBlobStore
from .crypto._crypto import decrypt_record, encrypt_record
from .envelope._envelope import (
    CipherEnvelope,
    EncryptionMetadata,
    _build_aad,
    _derive_envelope_key,
)
from .errors import DecryptionError, EncryptionError
from .master_key._master_key import MasterKeyProvider

_log = get_logger(__name__)


def _path_log_marker(path: Path) -> str:
    """Return a stable diagnostic marker without exposing the filesystem path."""
    try:
        raw_path = path.resolve(strict=False).as_posix()
    except OSError:
        raw_path = path.as_posix()
    digest = hashlib.sha256(raw_path.encode(UTF_8_ENCODING)).hexdigest()[:16]
    return f"<path:{digest}>"


class _RotationPlanSettings(Protocol):
    """Minimal settings surface required by :func:`default_rotation_plan`."""

    aeat_financial_txs_dir: Path
    aeat_invoices_dir: Path
    aeat_attachments_dir: Path
    aeat_usage_ratios_path: Path
    aeat_drafts_dir: Path
    aeat_submissions_dir: Path
    aeat_justificantes_dir: Path
    aeat_filing_history_dir: Path
    aeat_workflow_runs_dir: Path


class _BlobStoreSettings(Protocol):
    """Minimal settings surface required by :func:`default_blob_store_roots`."""

    aeat_blob_store_dir: Path
    aeat_attachments_dir: Path


class RotationPlanEntry(BaseModel):
    """One consumer's directory + HKDF context that the rotation must visit.

    Attributes:
        store_dir: Directory that contains the consumer's
            ``*.envelope.json`` files (or, when ``target_filename`` is
            set, the directory containing that specific file).
        hkdf_context: The same ``hkdf_context`` the consumer's
            repository uses at save / load time.
        envelope_suffix: Filename suffix the consumer uses; defaults
            to ``.envelope.json`` (matches every repository).
            Ignored when ``target_filename`` is set.
        target_filename: Optional exact filename inside ``store_dir``.
            Use this for single-file consumers whose on-disk filename
            does not end in ``.envelope.json`` (e.g.
            ``usage-ratios.json`` written by the usage-ratios
            service). When set, the rotation
            visits exactly ``store_dir / target_filename`` and ignores
            every other file in the directory.
    """

    model_config = STRICT_FROZEN_CONFIG

    store_dir: Path
    hkdf_context: bytes
    envelope_suffix: str = ".envelope.json"
    target_filename: str | None = None

    def lock_path_for(self, envelope_path: Path) -> Path:
        """Return the writer-canonical lock target for ``envelope_path``.

        Aligns the rotation's ``exclusive_file_lock`` target with the
        sidecar lock the consumer's writer acquires at ``save()``
        time. Without this alignment, rotation and writer would
        contend on different ``.lock`` files and lose the OS-level
        serialisation the lock was meant to provide.

        - Multi-file envelopes (``envelope_suffix`` set, default
          ``.envelope.json``): the writer convention is
          ``<id>.lock`` ( ``lock_target_for`` helpers). Strip
          the configured ``envelope_suffix`` from the envelope name
          and append ``.lock``.
        - Single-file envelopes (``target_filename`` set, e.g.
          ``usage-ratios.json``): the writer convention is
          ``<base>.lock`` (``target.with_suffix('.lock')``). Use
          :meth:`Path.with_suffix` directly.

        The lock file ``exclusive_file_lock`` actually opens is the returned
        path with an additional ``.lock`` suffix appended; the rotation and
        writer therefore land on the same lock-byte target.
        """
        if self.target_filename is not None:
            return envelope_path.with_suffix(".lock")
        name = envelope_path.name
        stem = name[: -len(self.envelope_suffix)] if name.endswith(self.envelope_suffix) else envelope_path.stem
        return envelope_path.with_name(stem + ".lock")


class RotationSummary(BaseModel):
    """Frozen result of a :func:`rotate_master_key` call.

    Attributes:
        rotated: Count of envelope files re-encrypted under the new key.
        skipped: Count of envelope files already decryptable under the
            new key (resume idempotency).
        errors: Count of envelope files that could not be parsed,
            decrypted under either key, or re-encrypted.
    """

    model_config = STRICT_FROZEN_CONFIG

    rotated: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)


def _iter_envelope_files(
    plan: tuple[RotationPlanEntry, ...],
) -> Iterator[tuple[Path, RotationPlanEntry]]:
    """Yield every envelope file across every plan entry."""
    for entry in plan:
        if not entry.store_dir.exists():
            continue
        if entry.target_filename is not None:
            # Single-file mode: visit exactly this filename inside the
            # directory. Used by consumers whose on-disk filename does
            # not end in ``.envelope.json`` (usage_ratios).
            target = entry.store_dir / entry.target_filename
            if target.is_file():
                yield target, entry
            continue
        for path in sorted(entry.store_dir.iterdir()):
            if not path.is_file():
                continue
            if not path.name.endswith(entry.envelope_suffix):
                continue
            yield path, entry


def _try_decrypt_bytes(
    cipher_envelope: CipherEnvelope,
    *,
    master_key_provider: MasterKeyProvider,
    hkdf_context: bytes,
) -> bytes | None:
    """Attempt to recover the plaintext bytes of ``cipher_envelope``.

    Returns the decrypted plaintext on AEAD-tag success, ``None``
    on AAD mismatch / wrong key / any other crypto failure. The
    classification + HKDF-context AAD binding is enforced before the
    crypto attempt so a wrong-class file fails fast.
    """
    try:
        blob = cipher_envelope.encryption.to_blob()
        aad = _build_aad(cipher_envelope.classification, hkdf_context)
        if cipher_envelope.encryption.associated_data() != aad:
            return None
    except (ValueError, binascii.Error):
        # Malformed nonce/ciphertext base64 or invalid AAD encoding
        # surfaces as a probe miss rather than a hard error so the
        # rotation can continue past the corrupt file and report it
        # in the errors counter via the outer caller.
        _log.debug("rotation probe: AAD/blob parse failed; treating as miss", exc_info=True)
        return None
    derived_key = _derive_envelope_key(
        master_key=master_key_provider.get_master_key(),
        hkdf_context=hkdf_context,
    )
    try:
        return decrypt_record(blob, key=derived_key, associated_data=aad)
    except (DecryptionError, EncryptionError):
        _log.debug("rotation probe: decrypt failed; treating as miss", exc_info=True)
        return None


def _atomic_write(target: Path, *, payload: str) -> None:
    """Atomically replace ``target`` with ``payload`` via tempfile + os.replace."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=UTF_8_ENCODING,
            dir=target.parent,
            prefix=f"{target.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(payload)
        os.replace(tmp_path, target)
        fsync_parent_dir(target)
    except OSError as exc:
        _log.error(
            "rotation: atomic write failed path_marker=%s error_type=%s",
            _path_log_marker(target),
            type(exc).__name__,
        )
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def rotate_master_key(
    plan: tuple[RotationPlanEntry, ...],
    *,
    old_master_key_provider: MasterKeyProvider,
    new_master_key_provider: MasterKeyProvider,
) -> RotationSummary:
    """Re-encrypt every envelope listed in ``plan`` under the new master key.

    Rotation contract:

    - For each envelope file, first attempt decryption under the new
      master-key provider. On success the file is already rotated;
      bump ``skipped`` and continue. (Resume-idempotency contract: a
      half-complete rotation can be re-run safely.)
    - On failure, try the old master-key provider. On success,
      re-encrypt the recovered plaintext bytes under the new
      provider, build a fresh :class:`CipherEnvelope`, and replace
      the on-disk file atomically.
    - On failure under both providers, log the path and bump ``errors``.
      Rotation continues so partial-rotation ground state is visible
      in the summary.

    Args:
        plan: Tuple of :class:`RotationPlanEntry` records — one per
            consumer (transactions, drafts, submissions, etc.).
        old_master_key_provider: :class:`MasterKeyProvider` returning
            the master key currently in use.
        new_master_key_provider: :class:`MasterKeyProvider` returning
            the new master key. Rotating to an identical key is permitted
            (no-op rotation) but the caller is responsible for the
            different-keys discipline.

    Returns:
        A frozen :class:`RotationSummary`.
    """
    rotated = 0
    skipped = 0
    errors = 0
    for path, entry in _iter_envelope_files(plan):
        # Hold the per-file repository lock across the read + decrypt
        # + re-encrypt + atomic-rewrite sequence so a concurrent
        # repository writer cannot stomp the rotation (or vice versa).
        # The lock target is computed via ``RotationPlanEntry.lock_path_for``
        # so rotation and writer contend on the same OS-level lock-byte
        # target — see the helper's docstring for the / single-
        # file conventions.
        lock_target = entry.lock_path_for(path)
        with exclusive_file_lock(lock_target):
            try:
                cipher_envelope = CipherEnvelope.model_validate_json(
                    path.read_text(encoding=UTF_8_ENCODING),
                )
            except (OSError, ValueError, ValidationError) as exc:
                _log.warning(
                    "rotate_master_key: path_marker=%s is not a CipherEnvelope error_type=%s",
                    _path_log_marker(path),
                    type(exc).__name__,
                )
                errors += 1
                continue

            # Try the new key first — already-rotated files succeed here.
            already_rotated = _try_decrypt_bytes(
                cipher_envelope,
                master_key_provider=new_master_key_provider,
                hkdf_context=entry.hkdf_context,
            )
            if already_rotated is not None:
                _log.debug(
                    "rotate_master_key: path_marker=%s already rotated, skipping",
                    _path_log_marker(path),
                )
                skipped += 1
                continue

            # Fall back to the old key.
            plaintext = _try_decrypt_bytes(
                cipher_envelope,
                master_key_provider=old_master_key_provider,
                hkdf_context=entry.hkdf_context,
            )
            if plaintext is None:
                _log.warning(
                    "rotate_master_key: cannot decrypt path_marker=%s under either old or new key",
                    _path_log_marker(path),
                )
                errors += 1
                continue

            # Re-encrypt under the new key. Build the AAD freshly so the
            # outer cipher-envelope wrapper continues to bind the same
            # (classification, hkdf_context) pair.
            aad = _build_aad(cipher_envelope.classification, entry.hkdf_context)
            new_derived_key = _derive_envelope_key(
                master_key=new_master_key_provider.get_master_key(),
                hkdf_context=entry.hkdf_context,
            )
            try:
                new_blob = encrypt_record(plaintext, key=new_derived_key, associated_data=aad)
            except EncryptionError as exc:
                _log.warning(
                    "rotate_master_key: failed to encrypt path_marker=%s error_type=%s",
                    _path_log_marker(path),
                    type(exc).__name__,
                )
                errors += 1
                continue

            new_cipher_envelope = CipherEnvelope(
                cipher_schema_version=cipher_envelope.cipher_schema_version,
                written_at=now(),
                classification=cipher_envelope.classification,
                encryption=EncryptionMetadata.from_blob(new_blob, associated_data=aad),
            )
            try:
                _atomic_write(path, payload=new_cipher_envelope.model_dump_json())
            except OSError as exc:
                _log.warning(
                    "rotate_master_key: failed to atomic-write path_marker=%s error_type=%s",
                    _path_log_marker(path),
                    type(exc).__name__,
                )
                errors += 1
                continue
            rotated += 1
    _log.info(
        "rotate_master_key: rotated=%d skipped=%d errors=%d at %s",
        rotated,
        skipped,
        errors,
        now().isoformat(),
    )
    return RotationSummary(rotated=rotated, skipped=skipped, errors=errors)


def default_rotation_plan(settings: _RotationPlanSettings) -> tuple[RotationPlanEntry, ...]:
    """Return the canonical rotation plan as a tuple of :class:`RotationPlanEntry` records.

    Enumerates every master-key-encrypted file-envelope consumer's directory +
    HKDF context. Operators with custom directories / additional consumers pass
    an extended plan to :func:`rotate_master_key` directly.

    Scope boundary: this plan covers only the ``*.envelope.json`` file consumers
    whose ciphertext is derived directly from the project master key (via the
    per-consumer HKDF context above). The SQL ``secure_objects`` store is NOT in
    this plan and intentionally so: its payloads are encrypted under the
    per-bucket DEK (the column layer resolves the active :class:`BucketSession`
    DEK, not the master key). A master-key / passphrase custody change rewraps
    that DEK without changing its value, so the ``secure_objects`` ciphertext
    stays valid and never requires re-encryption on master-key rotation.
    """
    return (
        RotationPlanEntry(
            store_dir=Path(settings.aeat_financial_txs_dir),
            hkdf_context=b"aeat.domain.transactions.catalogue.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_invoices_dir),
            hkdf_context=b"aeat.domain.invoices.catalogue.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_attachments_dir) / "manifests",
            hkdf_context=b"aeat.domain.attachments.manifest.v1",
        ),
        RotationPlanEntry(
            # Single-file envelope: ``aeat_usage_ratios_path`` defaults
            # to ``var/financial/usage-ratios.json`` — the suffix is
            # ``.json`` not ``.envelope.json``, so target the exact
            # filename rather than relying on the directory walk's
            # default suffix match (which would miss this file).
            store_dir=Path(settings.aeat_usage_ratios_path).parent,
            hkdf_context=b"aeat.domain.usage_ratios.profile.v1",
            target_filename=Path(settings.aeat_usage_ratios_path).name,
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_drafts_dir),
            hkdf_context=b"aeat.application.filing.draft.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_submissions_dir),
            hkdf_context=b"aeat.adapters.outbound.aeat.export.filing.v1",
        ),
        # Amendments share one HKDF context across two store dirs.
        # ``ModeloAmendmentRepository`` is one consumer identity but it
        # binds to two sibling subdirectories under ``aeat_submissions_dir``
        # (``amendment-results/`` and ``amendments/``). Both directories
        # therefore appear here as separate plan entries with the same
        # HKDF context — DO NOT deduplicate. Removing either entry breaks
        # rotation for the corresponding directory's envelopes.
        RotationPlanEntry(
            store_dir=Path(settings.aeat_submissions_dir) / "amendment-results",
            hkdf_context=b"aeat.application.filing.amendment.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_submissions_dir) / "amendments",
            hkdf_context=b"aeat.application.filing.amendment.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_justificantes_dir),
            hkdf_context=b"aeat.domain.justificante.metadata.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_filing_history_dir),
            hkdf_context=b"aeat.application.filing.history.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_workflow_runs_dir),
            hkdf_context=b"aeat.application.workflow.run.v1",
        ),
    )


def rotate_blob_stores(
    blob_store_roots: tuple[Path, ...],
    *,
    old_master_key_provider: MasterKeyProvider,
    new_master_key_provider: MasterKeyProvider,
) -> RotationSummary:
    """Re-wrap every blob's per-record DEK across the given blob-store roots.

    The blob store wraps each blob's DEK directly under the master key;
    on master-key rotation, every wrapped DEK must be re-wrapped or the
    blob is unrecoverable. This helper composes the per-store
    :meth:`EncryptedBlobStore.rotate_master_key` results into a single
    summary.

    Args:
        blob_store_roots: Tuple of root directories (each containing
            a ``blobs/`` subtree) to walk.
        old_master_key_provider: :class:`MasterKeyProvider` returning
            the master key currently in use.
        new_master_key_provider: :class:`MasterKeyProvider` returning
            the new master key.

    Returns:
        A frozen :class:`RotationSummary` covering every visited blob.
    """
    rotated = 0
    skipped = 0
    errors = 0
    for root in blob_store_roots:
        if not root.exists():
            continue
        store = EncryptedBlobStore(
            root_dir=root,
            master_key_provider=old_master_key_provider,
        )
        store_rotated, store_skipped, store_errors = store.rotate_master_key(
            old_master_key_provider=old_master_key_provider,
            new_master_key_provider=new_master_key_provider,
        )
        rotated += store_rotated
        skipped += store_skipped
        errors += store_errors
    return RotationSummary(rotated=rotated, skipped=skipped, errors=errors)


def default_blob_store_roots(settings: _BlobStoreSettings) -> tuple[Path, ...]:
    """Return the canonical blob-store roots covered by master-key rotation.

    The substrate persists wrapped DEKs in:

    - The secret-store's blob store (``aeat_blob_store_dir``), wired up
      by :func:`get_secret_store` for opaque-bearer credentials, OAuth
      refresh tokens, and identity records.
    - The financial-attachments store (``aeat_attachments_dir``), wired
      up by :class:`aeat.domain.attachments.AttachmentStore` for
      receipts, invoices, and bank statements.

    Each root is a directory whose ``blobs/<hex[:2]>/<hex>.manifest.json``
    files carry the per-blob ``wrapped_dek`` field. Operators with
    custom blob stores extend this tuple before calling
    :func:`rotate_blob_stores`.

    Roots that resolve to the same absolute path (operator override /
    shared deployment) are deduplicated so the rotation does not
    walk the same blob twice.
    """
    seen: set[Path] = set()
    roots: list[Path] = []
    for setting_path in (
        Path(settings.aeat_blob_store_dir),
        Path(settings.aeat_attachments_dir),
    ):
        if not setting_path.exists():
            continue
        resolved = setting_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        roots.append(setting_path)
    return tuple(roots)


__all__ = [
    "RotationPlanEntry",
    "RotationSummary",
    "default_blob_store_roots",
    "default_rotation_plan",
    "rotate_blob_stores",
    "rotate_master_key",
]
