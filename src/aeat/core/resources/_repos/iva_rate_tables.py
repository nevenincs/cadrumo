"""IvaRateTableRepository: singleton IVA rate table."""

from __future__ import annotations

from .._repository import ResourceCacheRepository


class IvaRateTableRepository(ResourceCacheRepository[object, None]):
    """Singleton-keyed repository for the bundled IVA rate table.

    Wraps :func:`aeat.domain.iva._rates.load_iva_rate_table`.
    """

    def _load(self, key: None) -> object:
        from ....domain.iva._rates import load_iva_rate_table

        return load_iva_rate_table()

    @property
    def singleton(self) -> object:
        return self.get(None)
