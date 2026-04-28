"""Master-key rotation for ciphertext-at-rest envelopes.

The substrate's at-rest encryption derives a per-consumer key from the
project master key via HKDF-SHA256 over a stable, per-consumer
``hkdf_context``. Rotating the master key therefore requires walking
every consumer's persisted ciphertext, decrypting under the old key,
and re-writing under the new key. This module is the single sanctioned
path for that operation.

Rotation operates at the bytes level — it never parses the inner
:class:`Envelope` payload. That keeps the rotation contract
content-preserving across every consumer's payload type without
requiring rotation code to know the typed payload schemas.

The rotation is **per-file atomic** — each cipher envelope is
re-written via tempfile + ``os.replace`` so a crash mid-rotation
leaves either the old or the new ciphertext on disk, never a torn
state. The whole rotation is **not** transactional across files:
both keys must remain available until rotation completes.

Detection of "already rotated" works by attempting to decrypt under
the new key first; on AEAD-tag verify success the file is skipped.
On failure, the helper falls back to the old key.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..logging import get_logger
from ._crypto import decrypt_record, encrypt_record
from ._envelope import (
    CipherEnvelope,
    EncryptionMetadata,
    _build_aad,  # type: ignore[attr-defined]
    _derive_envelope_key,  # type: ignore[attr-defined]
)
from ._master_key import MasterKeyProvider

_log = get_logger(__name__)


class RotationPlanEntry(BaseModel):
    """One consumer's directory + HKDF context that the rotation must visit.

    Attributes:
        store_dir: Directory that contains the consumer's
            ``*.envelope.json`` files.
        hkdf_context: The same ``hkdf_context`` the consumer's
            repository uses at save / load time.
        envelope_suffix: Filename suffix the consumer uses; defaults
            to ``.envelope.json`` (matches every wave-7 repository).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    store_dir: Path
    hkdf_context: bytes
    envelope_suffix: str = ".envelope.json"


class RotationSummary(BaseModel):
    """Frozen result of a :func:`rotate_master_key` call.

    Attributes:
        rotated: Count of envelope files re-encrypted under the new key.
        skipped: Count of envelope files already decryptable under the
            new key (resume idempotency).
        errors: Count of envelope files that could not be parsed,
            decrypted under either key, or re-encrypted.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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
    blob = cipher_envelope.encryption.to_blob()
    aad = _build_aad(cipher_envelope.classification, hkdf_context)
    if cipher_envelope.encryption.associated_data() != aad:
        return None
    derived_key = _derive_envelope_key(
        master_key=master_key_provider.get_master_key(),
        hkdf_context=hkdf_context,
    )
    try:
        return decrypt_record(blob, key=derived_key, associated_data=aad)
    except Exception:
        return None


def _atomic_write(target: Path, *, payload: str) -> None:
    """Atomically replace ``target`` with ``payload`` via tempfile + os.replace."""
    target.parent.mkdir(parents=True, exist_ok=True)
    # Capture tmp_path BEFORE the ``with`` so cleanup works when context
    # entry raises (rare but possible on some filesystems / antivirus
    # shims). NamedTemporaryFile raising means no file was created.
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - context-managed via `with handle:` below
        mode="w",
        encoding="utf-8",
        dir=target.parent,
        prefix=f"{target.stem}.",
        suffix=".tmp",
        delete=False,
    )
    tmp_path = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
        os.replace(tmp_path, target)
    except OSError:
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
        old_master_key_provider: Provider returning the master key
            currently in use.
        new_master_key_provider: Provider returning the new master
            key. Rotating to an identical key is permitted (no-op
            rotation) but the caller is responsible for the
            different-keys discipline.

    Returns:
        A frozen :class:`RotationSummary`.
    """
    rotated = 0
    skipped = 0
    errors = 0
    for path, entry in _iter_envelope_files(plan):
        try:
            cipher_envelope = CipherEnvelope.model_validate_json(
                path.read_text(encoding="utf-8"),
            )
        except Exception as exc:
            _log.warning("rotate_master_key: %s is not a CipherEnvelope: %s", path, exc)
            errors += 1
            continue

        # Try the new key first — already-rotated files succeed here.
        already_rotated = _try_decrypt_bytes(
            cipher_envelope,
            master_key_provider=new_master_key_provider,
            hkdf_context=entry.hkdf_context,
        )
        if already_rotated is not None:
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
                "rotate_master_key: cannot decrypt %s under either old or new key",
                path,
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
        except Exception as exc:
            _log.warning("rotate_master_key: failed to encrypt %s: %s", path, exc)
            errors += 1
            continue

        new_cipher_envelope = CipherEnvelope(
            cipher_schema_version=cipher_envelope.cipher_schema_version,
            written_at=datetime.now(UTC),
            classification=cipher_envelope.classification,
            encryption=EncryptionMetadata.from_blob(new_blob, associated_data=aad),
        )
        try:
            _atomic_write(path, payload=new_cipher_envelope.model_dump_json())
        except OSError as exc:
            _log.warning("rotate_master_key: failed to atomic-write %s: %s", path, exc)
            errors += 1
            continue
        rotated += 1
    _log.info(
        "rotate_master_key: rotated=%d skipped=%d errors=%d at %s",
        rotated,
        skipped,
        errors,
        datetime.now(UTC).isoformat(),
    )
    return RotationSummary(rotated=rotated, skipped=skipped, errors=errors)


def default_rotation_plan(settings: Any) -> tuple[RotationPlanEntry, ...]:
    """Return the canonical rotation plan against ``settings``.

    Enumerates every wave-7 governance repository's directory + HKDF
    context. Operators with custom directories / additional consumers
    pass an extended plan to :func:`rotate_master_key` directly.
    """
    return (
        RotationPlanEntry(
            store_dir=Path(settings.aeat_financial_txs_dir),
            hkdf_context=b"aeat.financial.transactions.catalogue.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_invoices_dir),
            hkdf_context=b"aeat.financial.invoices.catalogue.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_attachments_dir) / "manifests",
            hkdf_context=b"aeat.financial.attachments.manifest.v1",
        ),
        RotationPlanEntry(
            # Per-record envelope: every UsageRatioProfile write lands as
            # an ``*.envelope.json`` file in the parent directory of the
            # configured ``aeat_usage_ratios_path``.
            store_dir=Path(settings.aeat_usage_ratios_path).parent,
            hkdf_context=b"aeat.financial.usage_ratios.profile.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_drafts_dir),
            hkdf_context=b"aeat.filing.draft.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_submissions_dir),
            hkdf_context=b"aeat.submission.filing.v1",
        ),
        # Amendments share one HKDF context across two store dirs.
        # ``FilingAmendmentRepository`` is one consumer identity but it
        # binds to two sibling subdirectories under ``aeat_submissions_dir``
        # (``amendment-results/`` and ``amendments/``). Both directories
        # therefore appear here as separate plan entries with the same
        # HKDF context — DO NOT deduplicate. Removing either entry breaks
        # rotation for the corresponding directory's envelopes.
        RotationPlanEntry(
            store_dir=Path(settings.aeat_submissions_dir) / "amendment-results",
            hkdf_context=b"aeat.filing.amendment.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_submissions_dir) / "amendments",
            hkdf_context=b"aeat.filing.amendment.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_justificantes_dir),
            hkdf_context=b"aeat.justificante.metadata.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_filing_history_dir),
            hkdf_context=b"aeat.filing.history.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_workflow_runs_dir),
            hkdf_context=b"aeat.workflow.run.v1",
        ),
        RotationPlanEntry(
            store_dir=Path(settings.aeat_sync_divergence_file_dir),
            hkdf_context=b"aeat.sync.divergence.v1",
        ),
        RotationPlanEntry(
            # The setup wizard's ``AutonomoProfile`` is written as a
            # single-file envelope; rotation visits the parent directory
            # of the configured profile path. ``aeat_default_profile_path``
            # is optional in settings; rotation skips the entry when the
            # parent directory does not exist.
            store_dir=(
                Path(settings.aeat_default_profile_path).parent
                if settings.aeat_default_profile_path is not None
                else Path(settings.aeat_secret_store_dir) / "setup"
            ),
            hkdf_context=b"aeat.setup.profile.v1",
        ),
    )


__all__ = [
    "RotationPlanEntry",
    "RotationSummary",
    "default_rotation_plan",
    "rotate_master_key",
]
