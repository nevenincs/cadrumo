"""Shared internal support for modelo-binding source resolvers."""

from __future__ import annotations

from ...adapters.persistence.storage import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    StorageValidationError,
)
from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.invoices.errors import InvoicePersistenceError
from ...domain.transactions.errors import TransactionPersistenceError
from ...domain.usage_ratios import UsageRatioPersistenceError
from ._source_mesh import CalculationSourceResolution

_STORAGE_DEGRADATION_ERRORS = (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    InvoicePersistenceError,
    StorageValidationError,
    TransactionPersistenceError,
    UsageRatioPersistenceError,
)


def _revision_has_binding_source(revision: ModeloRevision, source: str) -> bool:
    return any(binding.source == source for binding in revision.bindings)


def _empty_source_resolution(
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    return CalculationSourceResolution(resolver_id=resolver_id, owned_sources=owned_sources)
