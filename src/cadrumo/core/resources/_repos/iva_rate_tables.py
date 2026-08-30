"""Singleton IVA-rate-table repository.

:class:`IvaRateTableRepository` exposes the bundled IVA rate table through the
shared :class:`ResourceCacheRepository` cache used by :class:`ResourceRegistry`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from ....domain.iva.schema import EUMemberState, IvaRateRecord


class IvaRateTableRepository(ResourceCacheRepository[Mapping["EUMemberState", "tuple[IvaRateRecord, ...]"], None]):
    """Singleton-keyed repository for the bundled IVA rate table.

    Wraps :func:`cadrumo.domain.iva.load_iva_rate_table`
    and returns mappings from :class:`EUMemberState` to
    :class:`IvaRateRecord` tuples.
    """

    @override
    def _load(self, key: None) -> Mapping[EUMemberState, tuple[IvaRateRecord, ...]]:
        from ....domain.iva.rates import load_iva_rate_table

        return load_iva_rate_table()

    @property
    def singleton(self) -> Mapping[EUMemberState, tuple[IvaRateRecord, ...]]:
        return self.get(None)
