"""Governed-persistence repository for filing-history records.

Filing history contains submitted modelos, periods, timestamps, and AEAT
status evidence. Records are stored as encrypted byte objects in the
primary SQL backend at AUDIT sensitivity; no plaintext filing-history
JSON or envelope file lands on disk.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from ...adapters.persistence.storage import Envelope, SensitivityClass, safe_repository_id
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ._history_models import FilingHistory

_log = get_logger(__name__)

_HISTORY_ENVELOPE_VERSION = 1
_HISTORY_NAMESPACE = "aeat.application.filing.history"


class FilingHistoryRepository:
    """Repository over encrypted SQL-backed filing history records."""

    def __init__(self) -> None:
        self._objects = SecureObjectRepository()

    @property
    def store_dir(self) -> Path:
        """Return a logical backend marker for diagnostic messages."""

        return Path("db://secure_objects") / _HISTORY_NAMESPACE

    def envelope_path_for(self, modelo: str) -> Path:
        """Return a logical object marker for ``modelo``."""

        safe_repository_id(modelo, context="modelo")
        return self.store_dir / modelo

    def lock_target_for(self, modelo: str) -> Path:
        """Return a logical lock marker; SQL transactions govern writes."""

        safe_repository_id(modelo, context="modelo")
        return self.store_dir / f"{modelo}.lock"

    def load(self, modelo: str) -> FilingHistory | None:
        """Return the persisted filing history for ``modelo`` or ``None``."""

        safe_repository_id(modelo, context="modelo")
        record = self._objects.load(
            _HISTORY_NAMESPACE,
            modelo,
            expected_class=SensitivityClass.AUDIT,
            max_supported_version=_HISTORY_ENVELOPE_VERSION,
        )
        if record is None:
            return None
        envelope = Envelope[FilingHistory].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.AUDIT:
            raise ClassificationError(
                f"filing history {modelo} has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.AUDIT}",
            )
        if envelope.schema_version > _HISTORY_ENVELOPE_VERSION:
            raise EnvelopeVersionError(
                f"filing history {modelo} is at version {envelope.schema_version}; "
                f"consumer supports up to {_HISTORY_ENVELOPE_VERSION}",
            )
        return envelope.payload

    def save(self, modelo: str, history: FilingHistory) -> None:
        """Persist ``history`` for ``modelo`` in the encrypted database object store."""

        safe_repository_id(modelo, context="modelo")
        envelope = Envelope[FilingHistory](
            schema_version=_HISTORY_ENVELOPE_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.AUDIT,
            payload=history,
        )
        self._objects.save(
            namespace=_HISTORY_NAMESPACE,
            object_key=modelo,
            classification=SensitivityClass.AUDIT,
            schema_version=_HISTORY_ENVELOPE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _log.debug("saved filing history modelo=%s", modelo)

    def delete(self, modelo: str) -> bool:
        """Remove the filing-history object for ``modelo``."""

        safe_repository_id(modelo, context="modelo")
        deleted = self._objects.delete(_HISTORY_NAMESPACE, modelo)
        if deleted:
            _log.info("deleted filing history modelo=%s", modelo)
        return deleted

    def list_modelos(self) -> tuple[str, ...]:
        """Return every modelo persisted in this repository, sorted."""

        modelos: list[str] = []
        for record in self._objects.list_records(
            _HISTORY_NAMESPACE,
            expected_class=SensitivityClass.AUDIT,
            max_supported_version=_HISTORY_ENVELOPE_VERSION,
        ):
            envelope = Envelope[FilingHistory].model_validate_json(record.payload.decode("utf-8"))
            first_entry = envelope.payload.entries[0] if envelope.payload.entries else None
            modelos.append(str(first_entry.modelo) if first_entry is not None else record.object_key.hex())
        return tuple(sorted(modelos))

    def iter_histories(self) -> Iterator[tuple[str, FilingHistory]]:
        """Yield ``(modelo, history)`` tuples for every persisted modelo."""

        for modelo in self.list_modelos():
            payload = self.load(modelo)
            if payload is None:
                _log.debug("iter_histories: object for modelo=%s returned no payload; skipping", modelo)
                continue
            yield modelo, payload


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "FilingHistory",
    "FilingHistoryRepository",
]
