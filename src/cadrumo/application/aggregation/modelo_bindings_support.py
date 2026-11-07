"""Shared internal support for modelo-binding source resolvers.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
"""

from __future__ import annotations

from typing import Final

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.invoices.errors import InvoicePersistenceError
from ...domain.transactions.errors import TransactionPersistenceError
from ...domain.usage_ratios.errors import UsageRatioPersistenceError
from ..persistence_errors import PersistenceDegradationError
from .source_mesh import CalculationSourceResolution

STORAGE_DEGRADATION_ERRORS: Final[tuple[type[Exception], ...]] = (
    PersistenceDegradationError,
    InvoicePersistenceError,
    TransactionPersistenceError,
    UsageRatioPersistenceError,
)


def revision_has_binding_source(revision: ModeloRevision, source: str) -> bool:
    """Report whether the revision declares a binding on the given source.

    ``revision`` is a :class:`ModeloRevision`.
    """
    return any(binding.source == source for binding in revision.bindings)


def empty_source_resolution(
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Return a source resolution that owns the given sources and carries no values."""
    return CalculationSourceResolution(resolver_id=resolver_id, owned_sources=owned_sources)
