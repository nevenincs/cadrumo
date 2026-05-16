"""Repository implementations for every read-only bundled resource.

Each module under this package defines one Repository class
plus its typed key model. The :class:`ResourceRegistry`
aggregates them in :mod:`aeat.core.resources._registry`.
"""

from __future__ import annotations

from .apoderamientos import ApoderamientosRepository
from .legal_parameters import LegalParameterRepository
from .recargo_bands import RecargoBandsRepository
from .topics import TopicCatalogueRepository
from .user_profile import UserProfileSchemaRepository
from .vat_rate_tables import VatRateTableRepository

__all__ = [
    "ApoderamientosRepository",
    "LegalParameterRepository",
    "RecargoBandsRepository",
    "TopicCatalogueRepository",
    "UserProfileSchemaRepository",
    "VatRateTableRepository",
]
