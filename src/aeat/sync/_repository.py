"""Divergence record repository: Protocol + two implementations.

:class:`JsonFileDivergenceRepository` is the default sink until #10
(the storage subpackage) merges; it writes one JSON file per record
under ``AEAT_SYNC_DIVERGENCE_FILE_DIR``.

:class:`StorageDivergenceRepository` is a rebase-swap stub that refuses
to construct until #10 lands. Selecting ``AEAT_SYNC_DIVERGENCE_SINK=STORAGE``
before then will raise :class:`NotImplementedError`.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable

from .._paths import resolve_record_json_path
from ..logging import get_logger
from ._divergence import DivergenceRecord, ResolutionState
from ._errors import DivergenceRepositoryError

_LOGGER = get_logger(__name__)


@runtime_checkable
class DivergenceRecordRepository(Protocol):
    """Persistence contract for divergence records.

    The real storage-backed implementation will land with issue #10;
    until then :class:`JsonFileDivergenceRepository` is the default.
    """

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
    """JSON-file-backed divergence repository.

    One file per record at ``<root>/<record_id>.json`` written with
    UTF-8 pretty JSON and an atomic ``os.replace`` to avoid torn writes.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        """Return the backing directory."""
        return self._root

    def _path_for(self, record_id: str) -> Path:
        try:
            return resolve_record_json_path(self._root, record_id, context="divergence record id")
        except ValueError as exc:
            raise DivergenceRepositoryError(str(exc)) from exc

    def save(self, record: DivergenceRecord) -> None:
        target = self._path_for(record.record_id)
        payload = record.model_dump_json(indent=2)
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                delete=False,
                dir=self._root,
                suffix=".tmp",
            ) as fh:
                fh.write(payload)
                tmp_path = Path(fh.name)
            os.replace(tmp_path, target)
        except OSError as exc:
            raise DivergenceRepositoryError(f"Failed to persist divergence record {record.record_id}: {exc}") from exc
        _LOGGER.info("persisted divergence record %s -> %s", record.record_id, target)

    def load(self, record_id: str) -> DivergenceRecord:
        path = self._path_for(record_id)
        if not path.exists():
            raise DivergenceRepositoryError(f"divergence record {record_id} not found")
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise DivergenceRepositoryError(f"Failed to read divergence record {record_id}: {exc}") from exc
        return DivergenceRecord.model_validate_json(raw)

    def list(self) -> tuple[DivergenceRecord, ...]:
        records: list[DivergenceRecord] = []
        for path in sorted(self._root.glob("*.json")):
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError as exc:
                raise DivergenceRepositoryError(f"Failed to read divergence record at {path}: {exc}") from exc
            records.append(DivergenceRecord.model_validate_json(raw))
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


class StorageDivergenceRepository:
    """Rebase-swap stub for the #10 storage-backed repository.

    Selecting ``AEAT_SYNC_DIVERGENCE_SINK=STORAGE`` before #10 merges
    will raise :class:`NotImplementedError` on construction, which
    :class:`SyncError` wraps via :class:`DivergenceRepositoryError`.
    """

    def __init__(self) -> None:
        raise NotImplementedError("StorageDivergenceRepository is pending the aeat.storage subpackage from #10")

    def save(self, record: DivergenceRecord) -> None:  # pragma: no cover - unreachable
        raise NotImplementedError

    def load(self, record_id: str) -> DivergenceRecord:  # pragma: no cover - unreachable
        raise NotImplementedError

    def list(self) -> tuple[DivergenceRecord, ...]:  # pragma: no cover - unreachable
        raise NotImplementedError

    def update_resolution(  # pragma: no cover - unreachable
        self,
        record_id: str,
        *,
        resolution_state: ResolutionState,
        notes: str | None = None,
    ) -> DivergenceRecord:
        raise NotImplementedError
