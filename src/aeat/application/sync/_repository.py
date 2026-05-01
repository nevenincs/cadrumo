"""Divergence record repository: Protocol + encrypted-envelope implementation.

:class:`JsonFileDivergenceRepository` writes one ciphertext envelope per
record under ``AEAT_SYNC_DIVERGENCE_FILE_DIR`` at AUDIT class via the
substrate's :func:`save_encrypted_envelope`. Future storage backends can
plug in by implementing :class:`DivergenceRecordRepository`; the runner
treats the repository contract as opaque.

Storage imports are deferred behind the methods that consult them so the
sync subpackage does not pull ``aeat.adapters.persistence.storage`` (with its Alembic plugin
discovery) into every CLI command's import chain.
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
    """Persistence contract for divergence records."""

    def save(self, record: DivergenceRecord) -> None:
        """Persist a single divergence record."""

    def load(self, record_id: str) -> DivergenceRecord:
        """Load a single divergence record by id."""

    def list(self) -> tuple[DivergenceRecord, ...]:
        """Return every persisted divergence record."""

    def update_resolution(
        self,
        record_id: str,
        *,
        resolution_state: ResolutionState,
        notes: str | None = None,
    ) -> DivergenceRecord:
        """Transition an existing record's resolution state."""


class JsonFileDivergenceRepository:
    """Encrypted-envelope-backed divergence repository.

    One ciphertext envelope per record at
    ``<root>/<record_id>.envelope.json`` written via the substrate's
    :func:`save_encrypted_envelope` at AUDIT class with HKDF context
    ``aeat.application.sync.divergence.v1``. The class name preserves wire-shape
    compatibility with the existing CLI surface; all on-disk records
    are now AES-256-GCM ciphertext.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        """Return the backing directory."""
        return self._root

    def _envelope_path_for(self, record_id: str) -> Path:
        # ``resolve_record_json_path`` validates the record_id shape and
        # rejects path-traversal attempts. We append the ``.envelope``
        # marker after that validation succeeds so the cipher-on-disk
        # filename remains unforgeable.
        try:
            json_path = resolve_record_json_path(self._root, record_id, context="divergence record id")
        except ValueError as exc:
            raise DivergenceRepositoryError(str(exc)) from exc
        return json_path.with_suffix(_ENVELOPE_SUFFIX)

    def _path_for(self, record_id: str) -> Path:
        """Public alias retained for callers that want the envelope path."""
        return self._envelope_path_for(record_id)

    def save(self, record: DivergenceRecord) -> None:
        from ...adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
            exclusive_file_lock,
            save_encrypted_envelope,
        )
        from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

        target = self._envelope_path_for(record.record_id)
        # Align with the / convention: strip the
        # full ``.envelope.json`` suffix and append ``.lock``. Using
        # ``Path.with_suffix(".lock")`` here would replace only the
        # last ``.json`` segment, producing ``<id>.envelope.lock`` —
        # which would NOT match what
        # ``RotationPlanEntry.lock_path_for`` resolves to and would
        # leave rotation and writer contending on different sidecar
        # files (defeating the fix).
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
        current = self.load(record_id)
        updated_fields: dict[str, object] = {"resolution_state": resolution_state}
        if notes is not None:
            updated_fields["notes"] = notes
        updated = current.model_copy(update=updated_fields)
        self.save(updated)
        return updated
