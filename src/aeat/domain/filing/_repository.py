"""Governed-persistence repository for filing drafts.

Wraps the substrate's :class:`aeat.adapters.persistence.storage.Envelope`
contract behind a small typed surface that the filing CLI and any future
consumer can call. Each draft is persisted as its own envelope file
(``<draft_id>.envelope.json``) under
:attr:`aeat.core.config.AeatSettings.aeat_drafts_dir`, so per-draft locking
does not contend across the whole drafts directory.

The repository is the only sanctioned read/write path for filing drafts.
There is no plaintext fallback: every reader and writer routes through
this surface so the on-disk record is always the encrypted envelope.

**Sensitivity classification.** Drafts carry per-line casilla arithmetic
that drives the exact tax due. Per the policy table that is
:attr:`aeat.adapters.persistence.storage.SensitivityClass.FINANCIAL`; the
gate at
:func:`aeat.adapters.persistence.storage.load_encrypted_envelope` rejects
payloads whose recorded class drifted.
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
from ._schema import FilingDraft

_HKDF_CONTEXT_FILING_DRAFT = b"aeat.application.filing.draft.v1"

_log = get_logger(__name__)

_DRAFT_ENVELOPE_VERSION = 1
_DRAFT_ENVELOPE_SUFFIX = ".envelope.json"
_DRAFT_LOCK_SUFFIX = ".lock"


class FilingDraftRepository:
    """Repository over the per-draft, file-locked, envelope-backed store."""

    def __init__(self, *, store_dir: Path) -> None:
        """Bind the repository to a store directory.

        Args:
            store_dir: Directory where the per-draft envelope files
                and lock sidecars live. Created on first write.
        """
        self._store_dir = Path(store_dir)

    @property
    def store_dir(self) -> Path:
        """Return the bound store directory."""
        return self._store_dir

    def envelope_path_for(self, draft_id: str) -> Path:
        """Return the canonical envelope path for ``draft_id``.

        Args:
            draft_id: The draft id (content-addressed hash from
                :func:`aeat.application.filing.compute_draft_id`).

        Returns:
            ``<store_dir>/<draft_id>.envelope.json``.
        """
        safe_repository_id(draft_id, context="draft_id")
        return self._store_dir / f"{draft_id}{_DRAFT_ENVELOPE_SUFFIX}"

    def lock_target_for(self, draft_id: str) -> Path:
        """Return the canonical lock-sidecar path for ``draft_id``."""
        safe_repository_id(draft_id, context="draft_id")
        return self._store_dir / f"{draft_id}{_DRAFT_LOCK_SUFFIX}"

    def load(self, draft_id: str) -> FilingDraft | None:
        """Return the persisted draft or ``None`` if absent.

        Args:
            draft_id: Draft id to load.

        Returns:
            The :class:`FilingDraft` payload, or ``None`` if the
            envelope file does not exist.

        Raises:
            ClassificationError: If the on-disk envelope's class is
                not FINANCIAL.
            EnvelopeVersionError: If the envelope schema version is
                higher than the consumer supports.
        """
        target = self.envelope_path_for(draft_id)
        if not target.exists():
            return None
        envelope = load_encrypted_envelope(
            target,
            Envelope[FilingDraft],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_FILING_DRAFT,
            max_supported_version=_DRAFT_ENVELOPE_VERSION,
        )
        return envelope.payload

    def save(self, draft: FilingDraft) -> None:
        """Persist ``draft`` atomically under its per-draft file lock.

        The on-disk envelope is AES-256-GCM ciphertext at FINANCIAL
        class — no plaintext casilla value lands on disk.
        """
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target_for(draft.draft_id)):
            envelope = Envelope[FilingDraft](
                schema_version=_DRAFT_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=draft,
            )
            save_encrypted_envelope(
                envelope,
                self.envelope_path_for(draft.draft_id),
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_FILING_DRAFT,
            )
        _log.debug("saved filing draft modelo=%s period=%s", draft.modelo, draft.period)

    def delete(self, draft_id: str) -> bool:
        """Remove the envelope for ``draft_id``.

        Returns ``True`` when the envelope existed and was removed,
        ``False`` when nothing was on disk to begin with. The lock
        sidecar is left in place so concurrent ``save`` callers do
        not race against an unlink-then-recreate sequence.
        """
        target = self.envelope_path_for(draft_id)
        if not self._store_dir.exists():
            return False
        with exclusive_file_lock(self.lock_target_for(draft_id)):
            if not target.exists():
                return False
            target.unlink()
        _log.debug("deleted filing draft %s", draft_id)
        return True

    def list_draft_ids(self) -> tuple[str, ...]:
        """Return every draft id persisted in this repository.

        The result is sorted lexicographically; callers that need
        chronological order should compare ``written_at`` after
        loading each envelope.
        """
        if not self._store_dir.exists():
            return ()
        ids: list[str] = []
        for path in self._store_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if not name.endswith(_DRAFT_ENVELOPE_SUFFIX):
                continue
            draft_id = name[: -len(_DRAFT_ENVELOPE_SUFFIX)]
            if not draft_id:
                continue
            ids.append(draft_id)
        ids.sort()
        return tuple(ids)

    def iter_drafts(self) -> Iterator[FilingDraft]:
        """Yield every persisted draft, in lexicographic id order."""
        for draft_id in self.list_draft_ids():
            payload = self.load(draft_id)
            if payload is not None:
                yield payload


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "FilingDraftRepository",
]
