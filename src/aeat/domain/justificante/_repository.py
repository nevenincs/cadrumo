"""Governed-persistence repository for parsed justificante metadata.

Justificante metadata captures AEAT verification identifiers, operator
identity, timestamps, and verification URLs. The structured metadata is
stored as encrypted byte objects in the primary SQL backend at
:class:`SensitivityClass` ``AUDIT`` sensitivity; no plaintext metadata
JSON or envelope file lands on disk.

Sensitivity rationale: justificantes are AEAT-issued verification receipts
whose sensitivity class is ``AUDIT`` for every modelo. The class is not
modelo-specific; it is determined by the nature of the artefact (an
AEAT-issued submission receipt carrying run-trace and NIF-bearing audit
fields), not by the modelo's ``output_sensitivity`` declaration. The
``ModeloDefinition.output_sensitivity`` field governs output artefacts
(calculation drafts, export payloads); justificante metadata is an
audit-sink artefact and is irreducibly AUDIT regardless of modelo.

See Also:
    :data:`aeat.adapters.persistence.storage.JUSTIFICANTE_METADATA_NAMESPACE`
        AUDIT namespace, schema-version, object-key, and custody contract for
        parsed AEAT receipt metadata.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar, override

from ...adapters.persistence.storage import SecureBoundRepository, SensitivityClass
from ._schema import Justificante

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    pass


class JustificanteRepository(SecureBoundRepository[Justificante]):
    """Encrypted AUDIT repository for :class:`Justificante` metadata.

    The :class:`SecureBoundRepository` base stores each :class:`Justificante`
    in a :class:`~aeat.adapters.persistence.storage.Envelope` row under
    :data:`aeat.adapters.persistence.storage.JUSTIFICANTE_METADATA_NAMESPACE`.
    The AEAT CSV is the natural key, so list and iteration APIs expose
    persisted receipt metadata without reading plaintext metadata from disk.

    Domain port previously at ``_protocols.py`` was removed on 2026-06-01 as
    zero-consumer; re-add via ADR amendment if a domain-layer caller needs
    typed substitutability.
    """

    namespace: ClassVar[str] = "aeat.domain.justificante.metadata"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1

    @override
    @classmethod
    def payload_model(cls) -> type[Justificante]:
        return Justificante

    @override
    def extract_identifier(self, payload: Justificante) -> str:
        return payload.csv

    def list_csvs(self) -> tuple[str, ...]:
        """Return every justificante CSV persisted in this repository, in lexicographic order."""
        return tuple(sorted(self.iter_ids()))

    def iter_justificantes(self) -> Iterator[Justificante]:
        """Yield every persisted justificante, in lexicographic CSV order.

        Returns:
            Iterator over :class:`Justificante` records.
        """
        yield from sorted(self.iter_records(), key=self.extract_identifier)


__all__ = [
    "JustificanteRepository",
]
