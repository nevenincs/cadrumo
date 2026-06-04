"""Application facade for Modelo IVA wallet seed operations."""

from __future__ import annotations

from decimal import Decimal

from ...domain.iva_compensation import IvaCompensationPeriodState
from ..calculations import seed_iva_compensation_period
from ._iva_wallet_gate import taxpayer_nif_for_bucket


class ModeloIvaWalletSeedError(Exception):
    """Base class for Modelo IVA wallet seed application errors."""

    translated_message: str
    context: dict[str, object]

    def __init__(self, *, translated_message: str, context: dict[str, object] | None = None) -> None:
        self.translated_message = translated_message
        self.context = context or {}
        super().__init__(translated_message)


class ModeloIvaWalletSeedNoTaxpayerError(ModeloIvaWalletSeedError):
    """Raised when the selected bucket cannot provide a taxpayer NIF."""


class ModeloIvaWalletSeedNegativeAmountError(ModeloIvaWalletSeedError):
    """Raised when a seed amount is negative."""


def seed_iva_compensation_period_for_bucket(
    *,
    bucket_id: str,
    filing_year: int,
    period: str,
    amount: Decimal,
) -> IvaCompensationPeriodState:
    """Seed IVA compensation history for the taxpayer attached to *bucket_id*."""
    if amount < Decimal("0"):
        raise ModeloIvaWalletSeedNegativeAmountError(
            translated_message="application.modelo.iva_wallet.seed_negative_amount",
            context={"amount": str(amount)},
        )
    taxpayer_nif = taxpayer_nif_for_bucket(bucket_id)
    if taxpayer_nif is None:
        raise ModeloIvaWalletSeedNoTaxpayerError(
            translated_message="application.modelo.iva_wallet.seed_no_nif",
            context={"bucket_id": bucket_id},
        )
    return seed_iva_compensation_period(
        taxpayer_nif=taxpayer_nif,
        filing_year=filing_year,
        period=period,
        amount=amount,
    )


__all__ = [
    "ModeloIvaWalletSeedError",
    "ModeloIvaWalletSeedNegativeAmountError",
    "ModeloIvaWalletSeedNoTaxpayerError",
    "seed_iva_compensation_period_for_bucket",
]
