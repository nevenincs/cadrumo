"""Domain-side calculation-revision catalogue port surface.

This module owns the pure calculation-revision catalogue vocabulary: the
:class:`CalculationRevisionPersistenceError` raised at the storage boundary, the
:func:`upsert_calculation_revision` pure mutator, and the namespace /
schema-version constants that name the persisted envelope contract. The concrete
encrypted SQL repository lives in the persistence adapter
:class:`~cadrumo.adapters.persistence.profile.modelos_calculation.CalculationRevisionCatalogueRepository`,
behind the read-side
:class:`~CalculationRevisionCatalogueRepositoryProtocol`; the
domain package depends only on the structural port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.logging import get_logger
from .calculation_revision import CalculationRevision, CalculationRevisionCatalogue
from .errors import ModeloError

if TYPE_CHECKING:
    from .calculation_revision_aggregate import CalculationRevisionAggregateContext

_LOGGER = get_logger(__name__)
_CALCULATION_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_calculation_revision_persistence"


class CalculationRevisionPersistenceError(ModeloError):
    """Raised when the calculation-revision catalogue cannot be persisted or loaded.

    This wraps storage-boundary failures from the persistence adapter's
    :class:`~cadrumo.adapters.persistence.profile.modelos_calculation.CalculationRevisionCatalogueRepository`
    while preserving translated recovery context for callers.
    """


def upsert_calculation_revision(
    catalogue: CalculationRevisionCatalogue,
    revision: CalculationRevision,
    *,
    aggregate_context: CalculationRevisionAggregateContext | None = None,
) -> CalculationRevisionCatalogue:
    """Return a new :class:`CalculationRevisionCatalogue` with ``revision`` inserted or replaced.

    Args:
        catalogue: Source catalogue to update.
        revision: The :class:`CalculationRevision` to insert or replace.
        aggregate_context: Joined authorities required when the catalogue contains
            a context-bound rectificativa revision.
    """
    mapping = dict(catalogue.revisions)
    mapping[revision.calculation_revision_id] = revision
    if aggregate_context is None:
        return CalculationRevisionCatalogue(revisions=mapping)
    from .calculation_revision_aggregate import CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY

    return CalculationRevisionCatalogue.model_validate(
        {"revisions": mapping},
        context={CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY: aggregate_context},
    )


__all__ = [
    "CalculationRevisionPersistenceError",
    "upsert_calculation_revision",
]
