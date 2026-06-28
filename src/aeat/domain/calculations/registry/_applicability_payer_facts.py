"""Payer-fact predicates for modelo applicability rules.

Each :class:`TaxpayerProfile` boolean answers one payer or trade fact used by
the modelo applicability rule table.
"""

from __future__ import annotations

from enum import StrEnum

from ...deadlines.taxpayer_model import TaxpayerProfile

__all__ = ["PayerFact", "payer_fact_holds"]


class PayerFact(StrEnum):
    """A withholding-payer / trade fact a modelo's applicability needs."""

    PAYS_WITHHELD_INCOME = "pays_withheld_income"
    PAYS_RENT_WITH_RETENCION = "pays_rent_with_retencion"
    TRADES_INTRACOMMUNITY = "trades_intracommunity"
    EXCEEDS_THIRD_PARTY_THRESHOLD = "exceeds_third_party_threshold"
    BIENES_EXTRANJERO_ABOVE_THRESHOLD = "bienes_extranjero_above_threshold"


def payer_fact_holds(profile: TaxpayerProfile, fact: PayerFact) -> bool:
    """Return whether ``profile`` positively declares the payer ``fact``.

    The supplied :class:`TaxpayerProfile` provides the boolean field backing the
    requested :class:`PayerFact`.
    """
    match fact:
        case PayerFact.PAYS_WITHHELD_INCOME:
            return profile.has_employees or profile.pays_professionals_with_retencion
        case PayerFact.PAYS_RENT_WITH_RETENCION:
            return profile.pays_rent_with_retencion
        case PayerFact.TRADES_INTRACOMMUNITY:
            return profile.does_intracomunitario
        case PayerFact.EXCEEDS_THIRD_PARTY_THRESHOLD:
            return profile.third_party_transactions_above_347_threshold
        case PayerFact.BIENES_EXTRANJERO_ABOVE_THRESHOLD:
            return profile.bienes_extranjero_above_threshold
