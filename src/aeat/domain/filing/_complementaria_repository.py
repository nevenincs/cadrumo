"""Governed-persistence repository for filing amendments.

Wraps the substrate's :class:`aeat.adapters.persistence.storage.Envelope`
contract behind a small typed surface that the complementaria flow can
call. Each amendment is persisted as its own envelope file
(``<amendment_id>.envelope.json``) under ``aeat_submissions_dir /
amendments/`` with a per-record
:func:`aeat.adapters.persistence.storage.exclusive_file_lock`.

**Sensitivity classification.** An amendment record captures the casilla
delta the operator is filing as a corrective. That carries
identity-bearing context plus arithmetic that drives the corrected tax due
— :attr:`aeat.adapters.persistence.storage.SensitivityClass.AUDIT` per the
default policy table (the amendment is the audit-grade evidence of *why*
the filing was changed).

Co-located with :mod:`aeat.domain.filing._repository` because the existing
complementaria flow consumes both submitted-filing records (to derive the
amendment's ``submission_id``) and amendment records (to persist the
result).
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
from ._amendment import FilingAmendment

_HKDF_CONTEXT_AMENDMENT = b"aeat.application.filing.amendment.v1"

_log = get_logger(__name__)

_AMENDMENT_ENVELOPE_VERSION = 1
_AMENDMENT_ENVELOPE_SUFFIX = ".envelope.json"
_AMENDMENT_LOCK_SUFFIX = ".lock"


class FilingAmendmentRepository:
    """Repository over the per-amendment, file-locked, envelope-backed store."""

    def __init__(self, *, store_dir: Path) -> None:
        """Bind the repository to a store directory.

        Args:
            store_dir: Directory where the per-amendment envelope
                files and lock sidecars live. Created on first write.
        """
        self._store_dir = Path(store_dir)

    @property
    def store_dir(self) -> Path:
        """Return the bound store directory."""
        return self._store_dir

    def envelope_path_for(self, amendment_id: str) -> Path:
        """Return the canonical envelope path for ``amendment_id``."""
        safe_repository_id(amendment_id, context="amendment_id")
        return self._store_dir / f"{amendment_id}{_AMENDMENT_ENVELOPE_SUFFIX}"

    def lock_target_for(self, amendment_id: str) -> Path:
        """Return the canonical lock-sidecar path for ``amendment_id``."""
        safe_repository_id(amendment_id, context="amendment_id")
        return self._store_dir / f"{amendment_id}{_AMENDMENT_LOCK_SUFFIX}"

    def load(self, amendment_id: str) -> FilingAmendment | None:
        """Return the persisted amendment or ``None`` if absent.

        Args:
            amendment_id: Repository-safe amendment identifier.

        Returns:
            The :class:`aeat.domain.filing._amendment.FilingAmendment`
            payload, or ``None`` when no envelope exists.

        Raises:
            :exc:`aeat.adapters.persistence.storage.errors.ClassificationError`:
                If the on-disk envelope's class is not AUDIT.
            :exc:`aeat.adapters.persistence.storage.errors.EnvelopeVersionError`:
                If the envelope schema version is higher than the consumer
                supports.
        """
        target = self.envelope_path_for(amendment_id)
        if not target.exists():
            return None
        envelope = load_encrypted_envelope(
            target,
            Envelope[FilingAmendment],
            expected_class=SensitivityClass.AUDIT,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_AMENDMENT,
            max_supported_version=_AMENDMENT_ENVELOPE_VERSION,
        )
        return envelope.payload

    def save(self, amendment: FilingAmendment) -> None:
        """Persist ``amendment`` atomically under its per-record file lock.

        The on-disk envelope is AES-256-GCM ciphertext at AUDIT class —
        no plaintext casilla delta or original-CSV reference lands on
        disk.

        Args:
            amendment: Amendment payload to persist; its
                ``amendment_id`` selects the envelope path.
        """
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target_for(amendment.amendment_id)):
            envelope = Envelope[FilingAmendment](
                schema_version=_AMENDMENT_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.AUDIT,
                payload=amendment,
            )
            save_encrypted_envelope(
                envelope,
                self.envelope_path_for(amendment.amendment_id),
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_AMENDMENT,
            )
        _log.debug("saved filing amendment %s kind=%s", amendment.amendment_id, amendment.amendment_kind.value)

    def delete(self, amendment_id: str) -> bool:
        """Remove the envelope for ``amendment_id``.

        Returns:
            ``True`` when an envelope existed and was removed,
            ``False`` when nothing was on disk.
        """
        target = self.envelope_path_for(amendment_id)
        if not self._store_dir.exists():
            return False
        with exclusive_file_lock(self.lock_target_for(amendment_id)):
            if not target.exists():
                return False
            target.unlink()
        _log.debug("deleted filing amendment %s", amendment_id)
        return True

    def list_amendment_ids(self) -> tuple[str, ...]:
        """Return every amendment id persisted in this repository."""
        if not self._store_dir.exists():
            return ()
        ids: list[str] = []
        for path in self._store_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if not name.endswith(_AMENDMENT_ENVELOPE_SUFFIX):
                continue
            amendment_id = name[: -len(_AMENDMENT_ENVELOPE_SUFFIX)]
            if not amendment_id:
                continue
            ids.append(amendment_id)
        ids.sort()
        return tuple(ids)

    def iter_amendments(self) -> Iterator[FilingAmendment]:
        """Yield every persisted amendment, in lexicographic id order."""
        for amendment_id in self.list_amendment_ids():
            payload = self.load(amendment_id)
            if payload is not None:
                yield payload


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "FilingAmendmentRepository",
]
