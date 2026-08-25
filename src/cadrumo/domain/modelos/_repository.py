"""Encrypted SQL repository for the modelo work-unit catalogue.

:class:`~adapters.persistence.profile.modelos_work_units.WorkUnitCatalogueRepository` persists
:class:`WorkUnit` records in a :class:`WorkUnitCatalogue` at
``FINANCIAL`` :class:`~cadrumo.adapters.persistence.storage.SensitivityClass`
through
:class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`. The
catalogue is serialised as a single
:class:`~cadrumo.adapters.persistence.storage.Envelope`-wrapped JSON payload keyed
by a stable namespace and object key; the underlying column is encrypted so no
plaintext work-unit metadata lands on disk.
The storage contract is declared by
:data:`cadrumo.adapters.persistence.storage.MODELO_WORK_UNIT_CATALOGUE_NAMESPACE`;
its default object key is the singleton ``catalogue`` row.
"""

from __future__ import annotations

from .errors import ModeloError
from ._work_unit import WorkUnit, WorkUnitCatalogue


class WorkUnitPersistenceError(ModeloError):
    """Raised when the work-unit catalogue cannot be loaded or saved.

    This wraps storage-boundary failures from
    :class:`~adapters.persistence.profile.modelos_work_units.WorkUnitCatalogueRepository` while preserving
    translated recovery context for callers.
    """


def upsert_work_unit(catalogue: WorkUnitCatalogue, unit: WorkUnit) -> WorkUnitCatalogue:
    """Return a new :class:`WorkUnitCatalogue` with ``unit`` inserted or replaced.

    The input catalogue is not mutated. The returned catalogue
    carries the same work units as the input plus ``unit`` at its
    deterministic ``work_unit_id``; any existing entry under that
    id is replaced.
    """
    mapping = dict(catalogue.work_units)
    mapping[unit.work_unit_id] = unit
    return WorkUnitCatalogue(work_units=mapping)


def remove_work_unit(catalogue: WorkUnitCatalogue, work_unit_id: str) -> WorkUnitCatalogue:
    """Return a new catalogue with ``work_unit_id`` removed.

    Removing an absent id is a no-op that returns a value-equal
    catalogue. The original is not mutated.

    Returns:
        A :class:`WorkUnitCatalogue` without the given work unit.
    """
    if work_unit_id not in catalogue.work_units:
        return catalogue
    mapping = dict(catalogue.work_units)
    del mapping[work_unit_id]
    return WorkUnitCatalogue(work_units=mapping)


__all__ = [
    "WorkUnitPersistenceError",
    "remove_work_unit",
    "upsert_work_unit",
]
