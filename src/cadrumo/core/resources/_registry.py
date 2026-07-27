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

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cache

from ._repos import (
    ApoderamientosRepository,
    CategoryProfileRepository,
    HolidayCalendarRepository,
    IvaCatalogueRepository,
    IvaRateTableRepository,
    LegalParameterRepository,
    ManualRepository,
    RecargoBandsRepository,
    TopicCatalogueRepository,
    UserProfileSchemaRepository,
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
    legal_parameters: LegalParameterRepository = field(default_factory=LegalParameterRepository)
    manuals: ManualRepository = field(default_factory=ManualRepository)
    modelos: StaticModeloRepository = field(default_factory=StaticModeloRepository)
    recargo_bands: RecargoBandsRepository = field(default_factory=RecargoBandsRepository)
    topics: TopicCatalogueRepository = field(default_factory=TopicCatalogueRepository)
    user_profile_schema: UserProfileSchemaRepository = field(default_factory=UserProfileSchemaRepository)
    iva_catalogues: IvaCatalogueRepository = field(default_factory=IvaCatalogueRepository)
    iva_rate_tables: IvaRateTableRepository = field(default_factory=IvaRateTableRepository)

    def clear(self) -> None:
        """Clear every Repository's Identity Map."""
        from ._repository import ResourceRepository

        for attr in self.__dataclass_fields__:
            value = getattr(self, attr)
            if isinstance(value, ResourceRepository):
                value.clear_cache()


_resources_override: contextvars.ContextVar[ResourceRegistry | None] = contextvars.ContextVar(
    "cadrumo_resources_override",
    default=None,
)
"""In-process registry override, read by :func:`resources` ahead of the cache.

The resource analogue of :func:`cadrumo.core.config.override_settings`'s
channel. It exists because the process registry is otherwise unreachable: the
factory below is cached, :class:`ResourceRegistry` is frozen, and the ``modelos``
slot is built from a default factory rather than from Settings, so no Settings
override can re-point it. A consumer that needs the registry to name a different
tree therefore has no honest seam without this one.
"""


@cache
def _build_resources() -> ResourceRegistry:
    """Build the process-wide registry from Settings. Cached at first call.

    The factory reads Settings once at construction and threads
    operator-supplied roots through to the Repositories that honour an
    env-override seam (manuals and iva catalogues).
    """
    from ..config import load_settings

    settings = load_settings()
    return ResourceRegistry(
        manuals=ManualRepository(root=settings.aeat_manuals_root),
        iva_catalogues=IvaCatalogueRepository(root=settings.cadrumo_iva_catalogue_root),
    )


def resources() -> ResourceRegistry:
    """Return the active resource registry.

    Normally the process-wide cached instance built by :func:`_build_resources`;
    inside an :func:`override_resources` block, the registry that block supplies.
    Tests that mutate Settings between cases call ``resources.cache_clear()`` to
    rebuild with the new values, exactly as before -- the cache handle is
    re-exposed on this function so the call surface is unchanged.

    Returns:
        The active :class:`ResourceRegistry` instance.
    """
    override = _resources_override.get()
    return override if override is not None else _build_resources()


#: ``resources.cache_clear()`` is a documented part of this surface and is
#: re-exposed here rather than left on the now-private cached builder, so the
#: override seam is additive at the call site.
resources.cache_clear = _build_resources.cache_clear  # type: ignore[attr-defined]
resources.cache_info = _build_resources.cache_info  # type: ignore[attr-defined]


@contextmanager
def override_resources(registry: ResourceRegistry) -> Iterator[ResourceRegistry]:
    """Bind ``registry`` as the active registry for the with-block.

    The registry analogue of
    :func:`cadrumo.core.config.override_settings`, and it exists for the same
    reason: a consumer that needs a different registry must be able to say so
    through a scoped, restoring seam rather than by reaching into the cached
    factory or mutating a repository's private root. Reversion is guaranteed on
    exception as well as on ordinary exit, so an override cannot escape its
    block and leak into an unrelated caller.

    Production never enters this block, so the default path is unchanged: with
    no override set, :func:`resources` returns the same cached instance it
    always did.

    Args:
        registry: The registry to bind for the duration of the block. Build it
            with :func:`dataclasses.replace` over the current registry when only
            one slot should differ, so every other repository stays identical.

    Yields:
        The bound registry, for convenience.
    """
    token = _resources_override.set(registry)
    try:
        yield registry
    finally:
        _resources_override.reset(token)
