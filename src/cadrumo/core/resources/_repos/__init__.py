"""Repository implementations for every read-only bundled resource.

Each module under this package defines one
:class:`ResourceCacheRepository` subclass plus its typed key model
where needed. The :class:`ResourceRegistry` aggregates them in
:mod:`core.resources._registry`.
"""

from __future__ import annotations

from .apoderamientos import ApoderamientosRepository
from .category_profiles import CategoryProfileRepository
from .holiday_calendars import HolidayCalendarRepository
from .iva_catalogues import IvaCatalogueRepository
from .iva_rate_tables import IvaRateTableRepository
from .legal_parameters import LegalParameterRepository
from .manuals import ManualKey, ManualRepository
from .modelos import StaticModeloRepository
from .recargo_bands import RecargoBandsRepository
from .topics import TopicCatalogueRepository

__all__ = [
    "ApoderamientosRepository",
    "CategoryProfileRepository",
    "HolidayCalendarRepository",
    "IvaCatalogueRepository",
    "IvaRateTableRepository",
    "LegalParameterRepository",
    "ManualKey",
    "ManualRepository",
    "RecargoBandsRepository",
    "StaticModeloRepository",
    "TopicCatalogueRepository",
]
