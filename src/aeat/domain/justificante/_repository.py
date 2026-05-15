"""Governed-persistence repository for parsed justificante metadata.

Justificante metadata captures AEAT verification identifiers, operator
identity, timestamps, and verification URLs. The structured metadata is
stored as encrypted byte objects in the primary SQL backend at AUDIT
sensitivity; no plaintext metadata JSON or envelope file lands on disk.

Sensitivity rationale: justificantes are AEAT-issued verification receipts
whose sensitivity class is ``AUDIT`` for every modelo. The class is not
modelo-specific — it is determined by the nature of the artefact (an
AEAT-issued submission receipt carrying run-trace and NIF-bearing audit
fields), not by the modelo's ``output_sensitivity`` declaration. The
``ModeloDefinition.output_sensitivity`` field governs *output* artefacts
(calculation drafts, export payloads); justificante metadata is an
*audit-sink* artefact and is irreducibly AUDIT regardless of modelo.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from ...adapters.persistence.storage import Envelope, SensitivityClass, safe_repository_id
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ._schema import Justificante

_log = get_logger(__name__)

_JUSTIFICANTE_ENVELOPE_VERSION = 1
_JUSTIFICANTE_NAMESPACE = "aeat.domain.justificante.metadata"


class JustificanteRepository:
    """Repository over encrypted SQL-backed justificante metadata."""

    def __init__(self) -> None:
        self._objects = SecureObjectRepository()

    @property
    def store_dir(self) -> Path:
        """Return a logical backend marker for diagnostic messages."""

        return Path("db://secure_objects") / _JUSTIFICANTE_NAMESPACE

    def envelope_path_for(self, csv: str) -> Path:
        """Return a logical object marker for a justificante CSV."""

        safe_repository_id(csv, context="csv")
        return self.store_dir / csv

    def lock_target_for(self, csv: str) -> Path:
        """Return a logical lock marker; SQL transactions govern writes."""

        safe_repository_id(csv, context="csv")
        return self.store_dir / f"{csv}.lock"

    def load(self, csv: str) -> Justificante | None:
        """Return the persisted justificante metadata or ``None`` if absent."""

        safe_repository_id(csv, context="csv")
        record = self._objects.load(
            _JUSTIFICANTE_NAMESPACE,
            csv,
            # rationale: justificante is an AEAT-issued audit-sink artefact; AUDIT
            # sensitivity is irreducible and modelo-independent (see module docstring).
            expected_class=SensitivityClass.AUDIT,
            max_supported_version=_JUSTIFICANTE_ENVELOPE_VERSION,
        )
        if record is None:
            return None
        envelope = Envelope[Justificante].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.AUDIT:
            raise ClassificationError(
                f"justificante {csv} has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.AUDIT}",
            )
        if envelope.schema_version > _JUSTIFICANTE_ENVELOPE_VERSION:
            raise EnvelopeVersionError(
                f"justificante {csv} is at version {envelope.schema_version}; "
                f"consumer supports up to {_JUSTIFICANTE_ENVELOPE_VERSION}",
            )
        return envelope.payload

    def save(self, justificante: Justificante) -> None:
        """Persist ``justificante`` in the encrypted database object store."""

        safe_repository_id(justificante.csv, context="csv")
        # rationale: justificante is an AEAT-issued audit-sink artefact; AUDIT
        # sensitivity is irreducible and modelo-independent (see module docstring).
        envelope = Envelope[Justificante](
            schema_version=_JUSTIFICANTE_ENVELOPE_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.AUDIT,
            payload=justificante,
        )
        self._objects.save(
            namespace=_JUSTIFICANTE_NAMESPACE,
            object_key=justificante.csv,
            classification=SensitivityClass.AUDIT,
            schema_version=_JUSTIFICANTE_ENVELOPE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _log.debug("saved justificante metadata for csv=%s", justificante.csv)

    def delete(self, csv: str) -> bool:
        """Remove the metadata object for ``csv``."""

        safe_repository_id(csv, context="csv")
        deleted = self._objects.delete(_JUSTIFICANTE_NAMESPACE, csv)
        if deleted:
            _log.debug("deleted justificante metadata for csv=%s", csv)
        return deleted

    def list_csvs(self) -> tuple[str, ...]:
        """Return every justificante CSV persisted in this repository."""

        csvs: list[str] = []
        for record in self._objects.list_records(
            _JUSTIFICANTE_NAMESPACE,
            # rationale: justificante is an AEAT-issued audit-sink artefact; AUDIT
            # sensitivity is irreducible and modelo-independent (see module docstring).
            expected_class=SensitivityClass.AUDIT,
            max_supported_version=_JUSTIFICANTE_ENVELOPE_VERSION,
        ):
            envelope = Envelope[Justificante].model_validate_json(record.payload.decode("utf-8"))
            csvs.append(envelope.payload.csv)
        return tuple(sorted(csvs))

    def iter_justificantes(self) -> Iterator[Justificante]:
        """Yield every persisted justificante, in lexicographic CSV order."""

        for csv in self.list_csvs():
            payload = self.load(csv)
            if payload is not None:
                yield payload


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "JustificanteRepository",
]
