"""Divergence-record repository protocol and encrypted-envelope implementation.

Defines the persistence contract for sync divergence records and the
default file-backed implementation, :class:`JsonFileDivergenceRepository`.
The default implementation writes one ciphertext envelope per record
under ``AEAT_SYNC_DIVERGENCE_FILE_DIR`` at the AUDIT sensitivity class
via :func:`aeat.adapters.persistence.storage.save_encrypted_envelope`. Alternative storage
backends plug in by implementing :class:`DivergenceRecordRepository`;
the runner treats the contract as opaque.

Storage imports are deferred inside methods so the sync subpackage does
not drag :mod:`aeat.adapters.persistence.storage` (and its Alembic plugin discovery) into
every CLI command's import chain.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from ...core.logging import get_logger
from ...core.paths import resolve_record_json_path
from ._divergence import DivergenceRecord, ResolutionState
from ._errors import DivergenceRepositoryError

_LOGGER = get_logger(__name__)
_HKDF_CONTEXT_DIVERGENCE = b"aeat.application.sync.divergence.v1"
_DIVERGENCE_ENVELOPE_VERSION = 1
_ENVELOPE_SUFFIX = ".envelope.json"


@runtime_checkable
class DivergenceRecordRepository(Protocol):
    """Persistence contract for :class:`DivergenceRecord` instances.

    Implementations may store records on the filesystem, in object
    storage, or in a database. The runner depends only on this Protocol.
    """

    def save(self, record: DivergenceRecord) -> None:
        """Persist a single divergence record.

        Args:
            record: The :class:`DivergenceRecord` to persist.
        """

    def load(self, record_id: str) -> DivergenceRecord:
        """Load a single divergence record by id.

        Args:
            record_id: The stable record identifier.

        Returns:
            The reconstructed :class:`DivergenceRecord`.
        """

    def list(self) -> tuple[DivergenceRecord, ...]:
        """Return every persisted divergence record."""

    def update_resolution(
        self,
        record_id: str,
        *,
        resolution_state: ResolutionState,
        notes: str | None = None,
    ) -> DivergenceRecord:
        """Transition an existing record's resolution state.

        Args:
            record_id: The record to mutate.
            resolution_state: The new :class:`ResolutionState`.
            notes: Optional human-readable annotation persisted alongside
                the new state.

        Returns:
            The freshly persisted :class:`DivergenceRecord`.
        """


class JsonFileDivergenceRepository:
    """Encrypted-envelope-backed :class:`DivergenceRecordRepository`.

    Stores one ciphertext envelope per record at
    ``<root>/<record_id>.envelope.json`` via
    :func:`aeat.adapters.persistence.storage.save_encrypted_envelope` at the AUDIT
    sensitivity class with HKDF context
    ``aeat.application.sync.divergence.v1``. The class name preserves
    wire-shape compatibility with the existing CLI surface; every
    on-disk record is AES-256-GCM ciphertext.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        """Return the backing directory."""
        return self._root

    def _envelope_path_for(self, record_id: str) -> Path:
        """Return the envelope path for ``record_id`` after safety validation.

        :func:`aeat.core.paths.resolve_record_json_path` validates the
        record id shape and rejects path-traversal attempts. The
        ``.envelope`` marker is appended only after validation succeeds
        so the cipher-on-disk filename remains unforgeable.
        """
        try:
            json_path = resolve_record_json_path(self._root, record_id, context="divergence record id")
        except ValueError as exc:
            raise DivergenceRepositoryError(str(exc)) from exc
        return json_path.with_suffix(_ENVELOPE_SUFFIX)

    def _path_for(self, record_id: str) -> Path:
        """Public alias retained for callers that want the envelope path."""
        return self._envelope_path_for(record_id)

    def save(self, record: DivergenceRecord) -> None:
        """Persist ``record`` as an encrypted envelope under :attr:`root`.

        Acquires the writer-canonical sidecar lock so concurrent
        master-key rotation and the writer contend on the same
        OS-level lock-byte target. Raises :exc:`DivergenceRepositoryError`
        on any I/O failure.
        """
        from ...adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
            exclusive_file_lock,
            save_encrypted_envelope,
        )
        from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

        target = self._envelope_path_for(record.record_id)
        # Strip the full ``.envelope.json`` suffix and append ``.lock``.
        # ``Path.with_suffix(".lock")`` would replace only the last
        # ``.json`` segment, producing ``<id>.envelope.lock`` — which
        # would NOT match what ``RotationPlanEntry.lock_path_for``
        # resolves to and would leave rotation and writer contending
        # on different sidecar files.
        lock_target = target.with_name(target.name[: -len(_ENVELOPE_SUFFIX)] + ".lock")
        try:
            with exclusive_file_lock(lock_target):
                envelope = Envelope[DivergenceRecord](
                    schema_version=_DIVERGENCE_ENVELOPE_VERSION,
                    written_at=datetime.now(UTC),
                    classification=SensitivityClass.AUDIT,
                    payload=record,
                )
                save_encrypted_envelope(
                    envelope,
                    target,
                    master_key_provider=_resolve_master_key_provider(),
                    hkdf_context=_HKDF_CONTEXT_DIVERGENCE,
                )
        except OSError as exc:
            raise DivergenceRepositoryError(f"Failed to persist divergence record {record.record_id}: {exc}") from exc
        _LOGGER.info("persisted divergence record %s -> %s", record.record_id, target)

    def load(self, record_id: str) -> DivergenceRecord:
        """Decrypt and return the persisted record matching ``record_id``.

        Raises:
            DivergenceRepositoryError: If the record is missing or its
                envelope cannot be decoded.
        """
        from ...adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
            load_encrypted_envelope,
        )
        from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

        path = self._envelope_path_for(record_id)
        if not path.exists():
            raise DivergenceRepositoryError(f"divergence record {record_id} not found")
        try:
            envelope = load_encrypted_envelope(
                path,
                Envelope[DivergenceRecord],
                expected_class=SensitivityClass.AUDIT,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_DIVERGENCE,
                max_supported_version=_DIVERGENCE_ENVELOPE_VERSION,
            )
        except (ValidationError, OSError) as exc:
            raise DivergenceRepositoryError(f"Failed to read divergence record {record_id}: {exc}") from exc
        return envelope.payload

    def list(self) -> tuple[DivergenceRecord, ...]:
        """Return every persisted record in deterministic filename order.

        Raises:
            DivergenceRepositoryError: If any envelope cannot be read
                or decrypted.
        """
        from ...adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
            load_encrypted_envelope,
        )
        from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

        records: list[DivergenceRecord] = []
        for path in sorted(self._root.glob(f"*{_ENVELOPE_SUFFIX}")):
            try:
                envelope = load_encrypted_envelope(
                    path,
                    Envelope[DivergenceRecord],
                    expected_class=SensitivityClass.AUDIT,
                    master_key_provider=_resolve_master_key_provider(),
                    hkdf_context=_HKDF_CONTEXT_DIVERGENCE,
                    max_supported_version=_DIVERGENCE_ENVELOPE_VERSION,
                )
            except (ValidationError, OSError) as exc:
                raise DivergenceRepositoryError(f"Failed to read divergence record at {path}: {exc}") from exc
            records.append(envelope.payload)
        return tuple(records)

    def update_resolution(
        self,
        record_id: str,
        *,
        resolution_state: ResolutionState,
        notes: str | None = None,
    ) -> DivergenceRecord:
        """Load, mutate, and re-save ``record_id`` with a new resolution.

        Args:
            record_id: The record to mutate.
            resolution_state: The new :class:`ResolutionState` to record.
            notes: Optional human-readable note appended alongside the
                state change.

        Returns:
            The persisted, updated :class:`DivergenceRecord`.
        """
        current = self.load(record_id)
        updated_fields: dict[str, object] = {"resolution_state": resolution_state}
        if notes is not None:
            updated_fields["notes"] = notes
        updated = current.model_copy(update=updated_fields)
        self.save(updated)
        return updated
