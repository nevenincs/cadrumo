"""IvaRateTableRepository: singleton IVA rate table."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from ....domain.iva import EUMemberState, IvaRateRecord


class IvaRateTableRepository(
    ResourceCacheRepository[
        Mapping["EUMemberState", "tuple[IvaRateRecord, ...]"], None
    ]
):
    """Singleton-keyed repository for the bundled IVA rate table.

    Wraps :func:`aeat.domain.iva._rates.load_iva_rate_table`.
    """

    def _load(self, key: None) -> Mapping[EUMemberState, tuple[IvaRateRecord, ...]]:
        from ....domain.iva._rates import load_iva_rate_table

        return load_iva_rate_table()

    @property
    def singleton(self) -> Mapping[EUMemberState, tuple[IvaRateRecord, ...]]:
        return self.get(None)
