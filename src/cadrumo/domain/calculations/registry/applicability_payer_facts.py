"""Payer-fact predicates for modelo applicability rules.

Each :class:`TaxpayerProfile` boolean answers one payer or trade fact used by
the modelo applicability rule table.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from types import MappingProxyType

from ...deadlines import TaxpayerProfile

__all__ = ["PayerFact", "payer_fact_holds"]


class PayerFact(StrEnum):
    """A withholding-payer / trade fact a modelo's applicability needs."""

    PAYS_WITHHELD_INCOME = "pays_withheld_income"
    PAYS_RENT_WITH_RETENCION = "pays_rent_with_retencion"
    TRADES_INTRACOMMUNITY = "trades_intracommunity"
    EXCEEDS_THIRD_PARTY_THRESHOLD = "exceeds_third_party_threshold"
    BIENES_EXTRANJERO_ABOVE_THRESHOLD = "bienes_extranjero_above_threshold"
    MONEDAS_VIRTUALES_EXTRANJERO_ABOVE_THRESHOLD = "monedas_virtuales_extranjero_above_threshold"
    PAYS_CAPITAL_INCOME_WITH_RETENCION = "pays_capital_income_with_retencion"
    IVA_GROUP_MEMBER = "iva_group_member"
    IVA_GROUP_DOMINANT_ENTITY = "iva_group_dominant_entity"
    OSS_ENROLLED = "oss_enrolled"


type _PayerFactEvaluator = Callable[[TaxpayerProfile], bool]


_PAYER_FACT_EVALUATORS: Mapping[PayerFact, _PayerFactEvaluator] = MappingProxyType(
    {
        PayerFact.PAYS_WITHHELD_INCOME: (
            lambda profile: profile.has_employees or profile.pays_professionals_with_retencion
        ),
        PayerFact.PAYS_RENT_WITH_RETENCION: lambda profile: profile.pays_rent_with_retencion,
        PayerFact.TRADES_INTRACOMMUNITY: lambda profile: profile.does_intracomunitario,
        PayerFact.EXCEEDS_THIRD_PARTY_THRESHOLD: (lambda profile: profile.third_party_transactions_above_347_threshold),
        PayerFact.BIENES_EXTRANJERO_ABOVE_THRESHOLD: lambda profile: profile.bienes_extranjero_above_threshold,
        PayerFact.MONEDAS_VIRTUALES_EXTRANJERO_ABOVE_THRESHOLD: (
            lambda profile: profile.monedas_virtuales_extranjero_above_threshold
        ),
        PayerFact.PAYS_CAPITAL_INCOME_WITH_RETENCION: (lambda profile: profile.pays_capital_income_with_retencion),
        PayerFact.IVA_GROUP_MEMBER: (lambda profile: profile.iva is not None and profile.iva.group_member_enrolled),
        PayerFact.IVA_GROUP_DOMINANT_ENTITY: (
            lambda profile: profile.iva is not None and profile.iva.group_dominant_entity_enrolled
        ),
        PayerFact.OSS_ENROLLED: lambda profile: profile.iva is not None and profile.iva.oss_enrolled,
    },
)


def payer_fact_holds(profile: TaxpayerProfile, fact: PayerFact) -> bool:
    """Return whether ``profile`` positively declares the payer ``fact``.

    The supplied :class:`TaxpayerProfile` provides the boolean field backing the
    requested :class:`PayerFact`.
    """
    return _PAYER_FACT_EVALUATORS[fact](profile)
