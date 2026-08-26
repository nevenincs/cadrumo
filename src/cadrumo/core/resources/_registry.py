"""Central resource registry and process-wide factory.

The :class:`ResourceRegistry` aggregates every
:class:`ResourceRepository` the project exposes. The
:func:`resources` factory builds the registry once per process;
subsequent calls return the cached instance. Tests that override
:class:`cadrumo.core.config.Settings` to change the bundled-data
location must call ``resources.cache_clear()`` to force a rebuild
on the next access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache

from ._repos import (
    ApoderamientosRepository,
    CategoryProfileRepository,
    HolidayCalendarRepository,
    IvaCatalogueRepository,
    IvaRateTableRepository,
    ManualRepository,
    RecargoBandsRepository,
    TopicCatalogueRepository,
)
from ._repos.modelos import StaticModeloRepository


@dataclass(slots=True, frozen=True)
class ResourceRegistry:
    """Aggregate of every Repository the project exposes.

    Each field holds one :class:`ResourceRepository` instance
    owning its own Identity Map. The :meth:`clear` method empties
    every Repository's cache uniformly; tests that override
    Settings between cases call it via the module-level
    :func:`resources` factory's ``cache_clear``.
    """

    apoderamientos: ApoderamientosRepository = field(default_factory=ApoderamientosRepository)
    category_profiles: CategoryProfileRepository = field(default_factory=CategoryProfileRepository)
    holiday_calendars: HolidayCalendarRepository = field(default_factory=HolidayCalendarRepository)
    manuals: ManualRepository = field(default_factory=ManualRepository)
    modelos: StaticModeloRepository = field(default_factory=StaticModeloRepository)
    recargo_bands: RecargoBandsRepository = field(default_factory=RecargoBandsRepository)
    topics: TopicCatalogueRepository = field(default_factory=TopicCatalogueRepository)
    iva_catalogues: IvaCatalogueRepository = field(default_factory=IvaCatalogueRepository)
    iva_rate_tables: IvaRateTableRepository = field(default_factory=IvaRateTableRepository)

    def clear(self) -> None:
        """Clear every Repository's Identity Map."""
        from ._repository import ResourceRepository

        for attr in self.__dataclass_fields__:
            value = getattr(self, attr)
            if isinstance(value, ResourceRepository):
                value.clear_cache()


@cache
def resources() -> ResourceRegistry:
    """Return the process-wide resource registry.

    Cached at first call. The factory reads Settings once at
    construction and threads operator-supplied roots through to
    the Repositories that honour an env-override seam (manuals and
    iva catalogues). Tests that mutate Settings between cases call
    ``resources.cache_clear()`` to rebuild with the new values.

    Returns:
        The process-wide cached :class:`ResourceRegistry` instance.
    """
    from ..config import load_settings

    settings = load_settings()
    return ResourceRegistry(
        manuals=ManualRepository(root=settings.aeat_manuals_root),
        iva_catalogues=IvaCatalogueRepository(root=settings.cadrumo_iva_catalogue_root),
    )
