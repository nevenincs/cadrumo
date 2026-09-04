"""Shared internal support for modelo-binding source resolvers."""

from __future__ import annotations

from typing import Final

from ...adapters.persistence.storage.errors import (
    STORAGE_DEGRADATION_ERRORS as _STORAGE_DEGRADATION_ERRORS,
)
from ...adapters.persistence.storage.errors import (
    StorageValidationError,
)
from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.invoices.errors import InvoicePersistenceError
from ...domain.transactions.errors import TransactionPersistenceError
from ...domain.usage_ratios.errors import UsageRatioPersistenceError
from ._source_mesh import CalculationSourceResolution

STORAGE_DEGRADATION_ERRORS: Final[tuple[type[Exception], ...]] = (
    *_STORAGE_DEGRADATION_ERRORS,
    InvoicePersistenceError,
    StorageValidationError,
    TransactionPersistenceError,
    UsageRatioPersistenceError,
)


def revision_has_binding_source(revision: ModeloRevision, source: str) -> bool:
    return any(binding.source == source for binding in revision.bindings)


def empty_source_resolution(
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    return CalculationSourceResolution(resolver_id=resolver_id, owned_sources=owned_sources)
