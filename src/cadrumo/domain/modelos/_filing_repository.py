"""Domain-side filing-record catalogue port surface.

This module owns the pure filing-record catalogue vocabulary: the
:class:`ModeloRecordPersistenceError` raised at the storage boundary, the
:func:`upsert_filing_record` pure mutator, and the namespace / schema-version
constants that name the persisted envelope contract. The concrete encrypted
SQL repository lives in the persistence adapter
:class:`~cadrumo.adapters.persistence.profile.modelos_filing.ModeloRecordCatalogueRepository`,
behind the read-side
:class:`~cadrumo.domain.modelos.ModeloRecordCatalogueRepositoryProtocol`; the
domain package depends only on the structural port.
"""

from __future__ import annotations

from ...core.logging import get_logger
from .errors import ModeloError
from ._filing_record import ModeloRecord, ModeloRecordCatalogue

_LOGGER = get_logger(__name__)
_FILING_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_filing_record_persistence"


class ModeloRecordPersistenceError(ModeloError):
    """Raised when the filing-record catalogue cannot be persisted or loaded.

    This wraps storage-boundary failures from
    :class:`~cadrumo.adapters.persistence.profile.modelos_filing.ModeloRecordCatalogueRepository`
    while preserving translated recovery context for callers.
    """


def upsert_filing_record(catalogue: ModeloRecordCatalogue, record: ModeloRecord) -> ModeloRecordCatalogue:
    """Return a new :class:`ModeloRecordCatalogue` with ``record`` inserted or replaced.

    Args:
        catalogue: Source catalogue to update.
        record: The :class:`ModeloRecord` to insert or replace.
    """
    mapping = dict(catalogue.records)
    mapping[record.filing_record_id] = record
    return ModeloRecordCatalogue(records=mapping)


__all__ = [
    "ModeloRecordPersistenceError",
    "upsert_filing_record",
]
