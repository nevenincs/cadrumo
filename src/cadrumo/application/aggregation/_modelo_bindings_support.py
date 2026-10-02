"""Shared internal support for modelo-binding source resolvers.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
Caller leases are
:class:`~cadrumo.domain.calculations.registry.authority.PinnedAuthorityOperation`
capabilities on :class:`~cadrumo.application.aggregation.source_mesh.CalculationSourceContext`.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Final

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.invoices.errors import InvoicePersistenceError
from ...domain.transactions.errors import TransactionPersistenceError
from ...domain.usage_ratios.errors import UsageRatioPersistenceError
from ..persistence_errors import PersistenceDegradationError
from .source_mesh import CalculationSourceContext, CalculationSourceResolution


@contextmanager
def source_context_operation(context: CalculationSourceContext) -> Generator[PinnedAuthorityOperation]:
    """Reuse a caller's lease; admit one only for a standalone resolver boundary."""
    if context.operation is not None:
        with validating_governed_facts(context.operation):
            yield context.operation
        return
    with bundled_indexed_authority().operation() as operation:
        yield operation


STORAGE_DEGRADATION_ERRORS: Final[tuple[type[Exception], ...]] = (
    PersistenceDegradationError,
    InvoicePersistenceError,
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
