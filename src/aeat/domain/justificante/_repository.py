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
from typing import ClassVar

from ...adapters.persistence.storage import SensitivityClass
from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ._schema import Justificante


class JustificanteRepository(SecureBoundRepository[Justificante]):
    """Repository over encrypted SQL-backed justificante metadata."""

    namespace: ClassVar[str] = "aeat.domain.justificante.metadata"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[Justificante]] = Justificante

    def extract_identifier(self, payload: Justificante) -> str:
        return payload.csv

    def list_csvs(self) -> tuple[str, ...]:
        """Return every justificante CSV persisted in this repository."""

        return tuple(self.iter_ids())

    def iter_justificantes(self) -> Iterator[Justificante]:
        """Yield every persisted justificante, in lexicographic CSV order."""

        yield from self.iter_records()


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "JustificanteRepository",
]
