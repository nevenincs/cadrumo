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
from .work_unit import WorkUnit, WorkUnitCatalogue


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


__all__ = [
    "WorkUnitPersistenceError",
    "upsert_work_unit",
]
