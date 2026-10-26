"""Euro valuation of Modelo 720 lots through the host-composed exchange-rate port.

The rate date and the refusals are domain policy
(:mod:`domain.foreign_assets.valuation`); this module only binds that policy to
the provider the process host composed, and asks for it only when a lot is held
in a currency other than the euro.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...core.external_constants import DEFAULT_CURRENCY
from ...domain.calculations.registry.detail_record_bindings import Modelo720RowObservation, Modelo720ValuedRow
from ...domain.currency.service import CurrencyNormalizationService, ExchangeRateProvider
from ...domain.foreign_assets.valuation import normalize_m720_valuation
from ..exchange_rate_provider import exchange_rate_provider


def value_modelo_720_rows(
    observations: Iterable[Modelo720RowObservation],
    *,
    filing_year: int,
    rate_provider: ExchangeRateProvider | None = None,
) -> tuple[Modelo720ValuedRow, ...]:
    """Return each lot with its euro valuation at the legal rate date, in input order.

    Args:
        observations: Native-currency lots of one declared year.
        filing_year: The declared ejercicio.
        rate_provider: The rate authority; the host-composed provider when omitted.

    Raises:
        ForeignAssetValuationRefusedError: A lot has no filing-grade euro value.
    """
    lots = tuple(observations)
    provider = rate_provider
    if provider is None and any(lot.currency_code != DEFAULT_CURRENCY for lot in lots):
        provider = exchange_rate_provider()
    service = CurrencyNormalizationService(rate_provider=provider)
    return tuple(
        Modelo720ValuedRow(
            observation=lot,
            valuation=normalize_m720_valuation(
                asset_ref=lot.asset_ref,
                asset_class=lot.asset_class_code,
                amount=lot.native_amount,
                event=lot.valuation_event,
                event_date=lot.valuation_event_date,
                filing_year=filing_year,
                service=service,
            ),
        )
        for lot in lots
    )


__all__ = ["value_modelo_720_rows"]
