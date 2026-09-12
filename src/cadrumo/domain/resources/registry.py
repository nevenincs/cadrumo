"""Central resource registry and process-wide factory.

The :class:`ResourceRegistry` aggregates every
:class:`ResourceRepository` the project exposes. The
:func:`resources` factory builds the registry once per process;
subsequent calls return the cached instance. Regulated runtime repositories
delegate freshness to the published authority; only file-backed resources own
repository identity maps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache

from ._repos.apoderamientos import ApoderamientosRepository
from ._repos.category_profiles import CategoryProfileRepository
from ._repos.holiday_calendars import HolidayCalendarRepository
from ._repos.iva_catalogues import IvaCatalogueRepository
from ._repos.manuals import ManualRepository
from ._repos.recargo_bands import RecargoBandsRepository


@dataclass(slots=True, frozen=True)
class ResourceRegistry:
    """Aggregate of every Repository the project exposes.

    Each field holds one :class:`ResourceRepository` instance. The
    :meth:`clear` method invokes their uniform cache contract; authority-backed
    repositories implement that operation as a no-op because the authority owns
    freshness.
    """

    apoderamientos: ApoderamientosRepository = field(default_factory=ApoderamientosRepository)
    category_profiles: CategoryProfileRepository = field(default_factory=CategoryProfileRepository)
    holiday_calendars: HolidayCalendarRepository = field(default_factory=HolidayCalendarRepository)
    manuals: ManualRepository = field(default_factory=ManualRepository)
    recargo_bands: RecargoBandsRepository = field(default_factory=RecargoBandsRepository)
    iva_catalogues: IvaCatalogueRepository = field(default_factory=IvaCatalogueRepository)

    def clear(self) -> None:
        """Clear caches owned by repositories that maintain one."""
        from ...core.resources.repository import ResourceRepository

        for attr in self.__dataclass_fields__:
            value = getattr(self, attr)
            if isinstance(value, ResourceRepository):
                value.clear_cache()


@cache
def resources() -> ResourceRegistry:
    """Return the process-wide resource registry.

    Cached at first call. The factory reads Settings once at
    construction and threads operator-supplied roots only to resources that are
    not regulated runtime authority (currently manuals). Tests that mutate those
    settings call ``resources.cache_clear()`` to rebuild the registry.

    Returns:
        The process-wide cached :class:`ResourceRegistry` instance.
    """
    from ...core.config import load_settings

    settings = load_settings()
    return ResourceRegistry(
        manuals=ManualRepository(root=settings.aeat_manuals_root),
        iva_catalogues=IvaCatalogueRepository(),
    )
