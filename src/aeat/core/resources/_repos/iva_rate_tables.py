"""VatRateTableRepository: singleton VAT rate table."""

from __future__ import annotations

from .._repository import Repository


class VatRateTableRepository(Repository[object, type(None)]):
    """Singleton-keyed repository for the bundled VAT rate table.

    Wraps :func:`aeat.domain.vat._rates.load_vat_rate_table`.
    """

    def _load(self, key: None) -> object:
        from ....domain.vat._rates import load_vat_rate_table

        return load_vat_rate_table()

    @property
    def singleton(self) -> object:
        return self.get(None)
