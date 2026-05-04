"""Governed-persistence repository for submitted-filing audit records.

Wraps the substrate's :class:`Envelope[SubmittedFiling]` contract behind
a small typed surface that the submission engine and any future consumer
can call. Each submission is persisted as its own envelope file
(``<submission_id>.envelope.json``) under
:attr:`aeat.core.config.AeatSettings.aeat_submissions_dir` with a per-record
exclusive_file_lock so concurrent writers serialise per-record but never
across the whole directory.

Sensitivity classification: a submission record captures the exact bytes
the operator uploaded plus AEAT's response. That is auditable evidence
with identity-bearing context — :class:`SensitivityClass.AUDIT` per the
default policy table.

Layered-import note: this module is a domain-side persistence carve-out:
``aeat.domain.submission._repository`` imports
``aeat.adapters.persistence.storage.*`` because every domain-owned
governance repository wraps the same substrate.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from ...adapters.persistence.storage import (
    Envelope,
    SensitivityClass,
    exclusive_file_lock,
    load_encrypted_envelope,
    safe_repository_id,
    save_encrypted_envelope,
)
from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...core.logging import get_logger
from ._models import SubmittedFiling

# HKDF context bytes are a STABLE cryptographic identifier — they
# participate in key derivation for every persisted envelope. Changing
# this string would render previously-encrypted submission envelopes
# unreadable. The legacy ``aeat.adapters.outbound.aeat.export``
# qualifier is preserved verbatim for backwards compatibility.
_HKDF_CONTEXT_SUBMISSION = b"aeat.adapters.outbound.aeat.export.filing.v1"

_log = get_logger(__name__)

_SUBMISSION_ENVELOPE_VERSION = 1
_SUBMISSION_ENVELOPE_SUFFIX = ".envelope.json"
_SUBMISSION_LOCK_SUFFIX = ".lock"


class SubmissionRepository:
    """Repository over the per-submission, file-locked, envelope-backed store."""

    def __init__(self, *, store_dir: Path) -> None:
        """Bind the repository to a store directory.

        Args:
            store_dir: Directory where the per-submission envelope
                files and lock sidecars live. Created on first write.
        """
        self._store_dir = Path(store_dir)

    @property
    def store_dir(self) -> Path:
        """Return the bound store directory."""
        return self._store_dir

    def envelope_path_for(self, submission_id: str) -> Path:
        """Return the canonical envelope path for ``submission_id``.

        Args:
            submission_id: The submission identifier
                (:func:`aeat.domain.submission._models.make_submission_id`).

        Returns:
            ``<store_dir>/<submission_id>.envelope.json``.
        """
        safe_repository_id(submission_id, context="submission_id")
        return self._store_dir / f"{submission_id}{_SUBMISSION_ENVELOPE_SUFFIX}"

    def lock_target_for(self, submission_id: str) -> Path:
        """Return the canonical lock-sidecar path for ``submission_id``."""
        safe_repository_id(submission_id, context="submission_id")
        return self._store_dir / f"{submission_id}{_SUBMISSION_LOCK_SUFFIX}"

    def load(self, submission_id: str) -> SubmittedFiling | None:
        """Return the persisted submission or ``None`` if absent.

        Raises:
            ClassificationError: If the on-disk envelope's class is not
                AUDIT.
            EnvelopeVersionError: If the envelope schema version is
                higher than the consumer supports.
        """
        target = self.envelope_path_for(submission_id)
        if not target.exists():
            _log.debug("submission envelope not found for id %s", submission_id)
            return None
        envelope = load_encrypted_envelope(
            target,
            Envelope[SubmittedFiling],
            expected_class=SensitivityClass.AUDIT,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_SUBMISSION,
            max_supported_version=_SUBMISSION_ENVELOPE_VERSION,
        )
        return envelope.payload

    def save(self, filing: SubmittedFiling) -> None:
        """Persist ``filing`` atomically under its per-submission file lock.

        The on-disk envelope is AES-256-GCM ciphertext at AUDIT class —
        no plaintext NIF, justificante CSV, or attempt timestamp lands
        on disk.
        """
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target_for(filing.submission_id)):
            envelope = Envelope[SubmittedFiling](
                schema_version=_SUBMISSION_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.AUDIT,
                payload=filing,
            )
            save_encrypted_envelope(
                envelope,
                self.envelope_path_for(filing.submission_id),
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_SUBMISSION,
            )
        _log.info(
            "saved submission envelope for id %s modelo=%s status=%s",
            filing.submission_id,
            filing.modelo,
            filing.status,
        )

    def delete(self, submission_id: str) -> bool:
        """Remove the envelope for ``submission_id``.

        Returns ``True`` when the envelope existed and was removed,
        ``False`` when nothing was on disk to begin with.
        """
        target = self.envelope_path_for(submission_id)
        if not self._store_dir.exists():
            _log.debug("delete: store dir absent; nothing to delete for id %s", submission_id)
            return False
        with exclusive_file_lock(self.lock_target_for(submission_id)):
            if not target.exists():
                _log.debug("delete: envelope not found for id %s", submission_id)
                return False
            target.unlink()
        _log.info("deleted submission envelope for id %s", submission_id)
        return True

    def list_submission_ids(self) -> tuple[str, ...]:
        """Return every submission id persisted in this repository."""
        if not self._store_dir.exists():
            return ()
        ids: list[str] = []
        for path in self._store_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if not name.endswith(_SUBMISSION_ENVELOPE_SUFFIX):
                continue
            submission_id = name[: -len(_SUBMISSION_ENVELOPE_SUFFIX)]
            if not submission_id:
                continue
            ids.append(submission_id)
        ids.sort()
        return tuple(ids)

    def iter_submissions(self) -> Iterator[SubmittedFiling]:
        """Yield every persisted submission, in lexicographic id order."""
        for submission_id in self.list_submission_ids():
            try:
                payload = self.load(submission_id)
            except (ClassificationError, EnvelopeVersionError):
                _log.warning(
                    "iter_submissions: skipping submission id=%s due to envelope error",
                    submission_id,
                    exc_info=True,
                )
                continue
            if payload is not None:
                yield payload


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "SubmissionRepository",
]
