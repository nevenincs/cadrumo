"""The reducción por arrendamiento de vivienda tiers of LIRPF Art. 23.2.

Ley 35/2006 Art. 23.2, as rewritten by Ley 12/2023 for leases signed from
2024, replaced the single 60 % reducción on net positive rental income with
four closed tiers — 90, 70, 60 and 50 % — selected by the lease's own
circumstances (a zona de mercado residencial tensionado rent cut, a young
tenant in such a zone, a vivienda protegida or a recently rehabilitated
dwelling, and the residual case). The taxpayer declares which tier applies;
the rate behind it is registry data, not a member of this enum.

The tier is a closed-membership axis, so it lives as a substrate enum rather
than a free-form string: a registry binding that carries the taxpayer's answer
annotates itself with the class name through
:class:`~cadrumo.core.aggregation.BindingTypedEnumKind`, and the calculation
routes the value as an enum dispatch key. Following
:mod:`cadrumo.domain.contribuyente.ccaa`, the module carries no import-time
chain of its own.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["RentalReductionArt232Tier"]


class RentalReductionArt232Tier(StrEnum):
    """The declared reducción tier for rental income under LIRPF Art. 23.2.

    Attributes:
        TIER_90: 90 % — new lease in a zona de mercado residencial
            tensionado with the rent cut below the previous contract.
        TIER_70: 70 % — first lease to a tenant aged 18-35 in such a zone,
            or a lease to a public administration or qualifying entity.
        TIER_60: 60 % — dwelling rehabilitated within the two years before
            the lease.
        TIER_50: 50 % — the residual tier for every other qualifying lease.
    """

    TIER_50 = "tier-50"
    TIER_60 = "tier-60"
    TIER_70 = "tier-70"
    TIER_90 = "tier-90"
