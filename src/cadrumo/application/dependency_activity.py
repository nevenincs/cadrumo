"""What a running setup is doing to each item, and how the last setup of an item ended.

State is derived, never stored, but derivation needs two facts no probe can
see: that a setup is changing an item right now, and that the last setup of an
item ended in a failure such as an interrupted download. Both are kept as
small non-secret files beside the receipts, and both are only ever evidence:

- An activity file counts only while the item's setup lock is held. A setup
  that died leaves its file behind, but its lock went with its process, so a
  stale file can never make an item look busy.
- A failure file shows only while the item's probe still finds it absent, and
  the next successful setup removes it.

A run marker names the setup operation that started changing items. When the
supervisor resumes that same operation after losing its owner, the marker
proves the downloads already began, and the setup ends as interrupted instead
of starting them again without the person.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ValidationError, model_validator

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.atomic_write import atomic_write_bytes
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.hashing import canonical_json_bytes
from ..core.locks import exclusive_file_lock
from ..core.locks_errors import LockAcquisitionError
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.utc import validate_utc_aware
from .dependency_contracts import DependencyActivity, DependencyItemId, DependencySetupStep, dependency_item_kind
from .operations.models import OperationId

__all__ = ["DependencyActivityStore", "DependencyFailureRecord", "DependencyStepRecord"]

_RUN_MARKER: Final = "setup-run.json"
_MAX_RECORD_BYTES: Final = 64 * 1024


class DependencyStepRecord(BaseModel):
    """The step one setup operation has reached for one item."""

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    operation_id: OperationId
    step: DependencySetupStep


class DependencyFailureRecord(BaseModel):
    """How the last setup of one item ended when it did not end ready."""

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    operation_id: OperationId
    category: DependencyFailureCategory
    recorded_at: datetime

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_time(self) -> DependencyFailureRecord:
        validate_utc_aware(self.recorded_at)
        return self


class _RunMarker(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    operation_id: OperationId


class DependencyActivityStore:
    """Activity, failure and run-marker files under one folder, with the per-item locks beside them."""

    def __init__(self, root: Path) -> None:
        """Bind the store to its folder, created on first write."""
        self._root = root

    @property
    def root(self) -> Path:
        """The folder holding the activity files and the item locks."""
        return self._root

    def _file(self, item_id: str, kind: str) -> Path:
        dependency_item_kind(item_id)
        return self._root / f"{item_id}.{kind}.json"

    def record_step(self, record: DependencyStepRecord) -> None:
        """Record the step a setup reached for an item; meaningful only while its lock is held."""
        atomic_write_bytes(self._file(record.item_id, "activity"), canonical_json_bytes(record.model_dump(mode="json")))

    def clear_step(self, item_id: str) -> None:
        """Remove an item's activity file once its setup is done with it."""
        self._file(item_id, "activity").unlink(missing_ok=True)

    def record_failure(self, record: DependencyFailureRecord) -> None:
        """Record how an item's setup failed, for status to show while the item is still absent."""
        atomic_write_bytes(self._file(record.item_id, "failure"), canonical_json_bytes(record.model_dump(mode="json")))

    def clear_failure(self, item_id: str) -> None:
        """Remove an item's failure record after a setup leaves it ready."""
        self._file(item_id, "failure").unlink(missing_ok=True)

    def activities(self, item_ids: tuple[str, ...]) -> tuple[DependencyActivity, ...]:
        """Return the step of every item a setup is changing right now, judged by its held lock."""
        found: list[DependencyActivity] = []
        for item_id in item_ids:
            record = _read(self._file(item_id, "activity"), DependencyStepRecord)
            if record is None or record.item_id != item_id or not self._lock_held(item_id):
                continue
            found.append(DependencyActivity(item_id=item_id, step=record.step))
        return tuple(found)

    def failures(self, item_ids: tuple[str, ...]) -> dict[str, DependencyFailureCategory]:
        """Return the recorded failure category of every listed item that has one."""
        found: dict[str, DependencyFailureCategory] = {}
        for item_id in item_ids:
            record = _read(self._file(item_id, "failure"), DependencyFailureRecord)
            if record is not None and record.item_id == item_id:
                found[item_id] = record.category
        return found

    def mark_run(self, operation_id: str) -> bool:
        """Mark ``operation_id`` as the setup changing items; ``False`` when it was already marked.

        ``False`` means the supervisor is running the same approved setup a
        second time after losing its owner, so its downloads already began.
        """
        marker = _read(self._root / _RUN_MARKER, _RunMarker)
        if marker is not None and marker.operation_id == operation_id:
            return False
        atomic_write_bytes(
            self._root / _RUN_MARKER,
            canonical_json_bytes(_RunMarker(operation_id=operation_id).model_dump(mode="json")),
        )
        return True

    def clear_run(self, operation_id: str) -> None:
        """Remove the run marker when ``operation_id`` finished with the items."""
        marker = _read(self._root / _RUN_MARKER, _RunMarker)
        if marker is not None and marker.operation_id == operation_id:
            (self._root / _RUN_MARKER).unlink(missing_ok=True)

    def _lock_held(self, item_id: str) -> bool:
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            with exclusive_file_lock(self._root / f"{item_id}.setup", timeout=0):
                return False
        except LockAcquisitionError:
            return True


def _read[RecordT: BaseModel](path: Path, model: type[RecordT]) -> RecordT | None:
    try:
        with path.open("rb") as handle:
            raw = handle.read(_MAX_RECORD_BYTES + 1)
    except OSError:
        return None
    if len(raw) > _MAX_RECORD_BYTES:
        return None
    try:
        return model.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError, UnicodeDecodeError):
        return None
