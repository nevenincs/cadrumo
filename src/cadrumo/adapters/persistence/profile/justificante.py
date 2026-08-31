"""Governed-persistence repository for parsed justificante metadata.

Justificante metadata captures AEAT verification identifiers, operator
identity, timestamps, and verification URLs. The structured metadata is
stored as encrypted byte objects in the primary SQL backend at
:class:`~adapters.persistence.storage.SensitivityClass` ``AUDIT``
sensitivity; no plaintext metadata JSON or envelope file lands on disk.

This concrete repository is the persistence adapter for the
:class:`~domain.justificante.Justificante` audit-sink record. It lives in
the persistence adapter (not in :mod:`~domain.justificante`) because its
base :class:`~adapters.persistence.storage.SecureBoundRepository` is
SQL/crypto-coupled; the domain package owns the pure record and the
:class:`~domain.justificante.JustificanteRepositoryProtocol` port.

See Also:
    :class:`~domain.justificante.Justificante`
        Payload model encrypted by this repository.
    :class:`~adapters.persistence.storage.SecureObjectRepository`
        SQL object store underlying the bound repository.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar, override

from ....core.classification.policies import SensitivityClass
from ....domain.justificante import Justificante
from ..storage.envelope._secure_repository import SecureBoundRepository
from ..storage.secure_object_namespaces import JUSTIFICANTE_METADATA_NAMESPACE


class JustificanteRepository(SecureBoundRepository[Justificante]):
    """Encrypted AUDIT repository for :class:`Justificante` metadata.

    The :class:`~adapters.persistence.storage.SecureBoundRepository` base
    stores each :class:`Justificante` in a
    :class:`~adapters.persistence.storage.Envelope` row under the AUDIT
    justificante-metadata namespace. The AEAT CSV is the natural key, so list
    and iteration APIs expose persisted receipt metadata without reading
    plaintext metadata from disk.
    """

    namespace: ClassVar[str] = JUSTIFICANTE_METADATA_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = JUSTIFICANTE_METADATA_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = JUSTIFICANTE_METADATA_NAMESPACE.schema_version

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
