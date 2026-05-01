"""LIRPF art. 23.2 four-tier auto-resolver post Ley 12/2023 (#454).

Implements the BOE priority order (90 → 70 → 60 → 50, highest
applicable wins) per disposición final segunda apartado uno of
Ley 12/2023, de 24 de mayo (BOE-A-2023-12203). Trigger conditions
reproduced verbatim in
``.vault/research/2026-04-29-rental-income-hardening-research.md``
section §2.

Effective-date dispatch:

  - ``period_year < ejercicio_amendment_year`` (default 2024) →
    flat 60 % under the pre-amendment art. 23.2 wording, regardless
    of contract date.
  - ``period_year >= ejercicio_amendment_year`` AND
    ``contract_celebration_date < ley_12_2023_in_force_date``
    (2023-05-26) → flat 60 % under DT 38ª (LIRPF redacción vigente
    a 31/12/2021).
  - Otherwise → four-tier dispatch.

LAU art. 17.6 non-compliance forfeits the reducción entirely
(``FORFEIT_LAU_17_6``) — checked before any tier evaluation per
the closing paragraph of the rewritten apartado 2.

Tier 70-b-1 (joven inquilino) carries a per-co-tenant qualifying
share: BOE explicitly states "Cuando existan varios arrendatarios
de una misma vivienda, esta reducción se aplicará sobre la parte
del rendimiento neto que proporcionalmente corresponda a los
arrendatarios que cumplan los requisitos previstos en esta letra".
The resolver returns ``qualifying_share = qualifying_co_tenant_count
/ tenant_count`` for that tier; every other tier returns share=1.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ._enums import ReduccionTier
from ._errors import TierResolutionError
from ._models import RentalContract, RentalFinca

LEY_12_2023_IN_FORCE_DATE: date = date(2023, 5, 26)
"""Entry-into-force date of Ley 12/2023 (BOE-A-2023-12203). Contracts
celebrated on or after this date are subject to the new four-tier
framework once the IRPF amendment also takes legal effect."""

DEFAULT_EJERCICIO_AMENDMENT_YEAR: int = 2024
"""First ejercicio in which the new IRPF apartado 2 art. 23 wording
applies (Ley 12/2023 disposición final novena segundo párrafo)."""

REHAB_LOOKBACK_DAYS: int = 730
"""``2 años anteriores`` interpreted as 730 calendar days (2 * 365).
The BOE wording ("en los dos años anteriores a la fecha de la
celebración del contrato") permits exact-day arithmetic; the
project picks 730-day lookback as the deterministic boundary."""

PRIOR_RENT_REBAJA_THRESHOLD: Decimal = Decimal("0.05")
"""Tier 90-a threshold: ``más de un 5 por ciento``. Strict ``>``
comparison — exactly 5 % does not qualify (BOE wording is "en más
de un 5 por ciento", not "en al menos un 5 por ciento")."""

JOVEN_TENANT_AGE_MIN: int = 18
JOVEN_TENANT_AGE_MAX: int = 35
"""Tier 70-b-1 inclusive age range (BOE: "una edad comprendida entre
18 y 35 años")."""


class TierResolution(BaseModel):
    """Outcome of a single :func:`resolve_reduccion` invocation.

    Attributes:
        tier: Closed-enum tier identifier.
        reduccion_pct: Numeric reducción percentage as a Decimal in
            ``[0, 1]``. Multiplied by ``qualifying_share`` and the
            per-contract rendimiento neto positivo to compute the
            casilla 0078 contribution.
        qualifying_share: Fraction of rendimiento neto eligible for
            the tier reducción. Always ``1`` except for tier 70-b-1
            with mixed-qualification co-tenants.
        boe_citation_id: Stable identifier for the BOE provision
            grounding the resolution (e.g. ``"art_23_2_a"``,
            ``"art_23_2_b_1"``, ``"dt_38"``,
            ``"art_23_2_par_4_lau_17_6"``).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    tier: ReduccionTier
    reduccion_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    qualifying_share: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    boe_citation_id: str = Field(min_length=1)


_FORFEIT_LAU_17_6 = TierResolution(
    tier=ReduccionTier.FORFEIT_LAU_17_6,
    reduccion_pct=Decimal("0"),
    qualifying_share=Decimal("0"),
    boe_citation_id="art_23_2_par_4_lau_17_6",
)
_DT_38 = TierResolution(
    tier=ReduccionTier.TIER_60_GRANDFATHERED_DT38,
    reduccion_pct=Decimal("0.60"),
    qualifying_share=Decimal("1"),
    boe_citation_id="dt_38",
)
_PRE_AMENDMENT = TierResolution(
    tier=ReduccionTier.TIER_60_GRANDFATHERED_DT38,
    reduccion_pct=Decimal("0.60"),
    qualifying_share=Decimal("1"),
    boe_citation_id="pre_amendment",
)
_TIER_50 = TierResolution(
    tier=ReduccionTier.TIER_50,
    reduccion_pct=Decimal("0.50"),
    qualifying_share=Decimal("1"),
    boe_citation_id="art_23_2_d",
)
_TIER_60_REHAB = TierResolution(
    tier=ReduccionTier.TIER_60_REHAB,
    reduccion_pct=Decimal("0.60"),
    qualifying_share=Decimal("1"),
    boe_citation_id="art_23_2_c",
)
_TIER_70_PUBLIC_ADMIN = TierResolution(
    tier=ReduccionTier.TIER_70_PUBLIC_ADMIN,
    reduccion_pct=Decimal("0.70"),
    qualifying_share=Decimal("1"),
    boe_citation_id="art_23_2_b_2",
)
_TIER_90 = TierResolution(
    tier=ReduccionTier.TIER_90,
    reduccion_pct=Decimal("0.90"),
    qualifying_share=Decimal("1"),
    boe_citation_id="art_23_2_a",
)


def resolve_reduccion(
    contract: RentalContract,
    finca: RentalFinca,
    period_year: int,
    *,
    ejercicio_amendment_year: int = DEFAULT_EJERCICIO_AMENDMENT_YEAR,
) -> TierResolution:
    """Resolve the LIRPF art. 23.2 reducción tier for ``contract`` in ``period_year``.

    Args:
        contract: The per-contract metadata record.
        finca: The owning finca (provides ``is_stressed_area``).
        period_year: Ejercicio for which the reducción is being
            computed.
        ejercicio_amendment_year: First ejercicio on which the new
            apartado 2 wording applies (default 2024 per Ley 12/2023
            disposición final novena).

    Returns:
        :class:`TierResolution` carrying the tier, the numeric
        reducción percentage, the qualifying share, and the BOE
        citation identifier.

    Raises:
        TierResolutionError: When tier-90-a is the only candidate
            but the contract record lacks ``prior_contract_last_rent``
            (cannot evaluate the 5 % rebaja threshold without prior-
            contract data).
    """
    if period_year < ejercicio_amendment_year:
        return _PRE_AMENDMENT
    if contract.contract_celebration_date < LEY_12_2023_IN_FORCE_DATE:
        return _DT_38
    if not contract.lau_17_6_compliant:
        return _FORFEIT_LAU_17_6
    if _qualifies_for_tier_90(contract, finca):
        return _TIER_90
    tier_70 = _resolve_tier_70(contract, finca)
    if tier_70 is not None:
        return tier_70
    if _qualifies_for_tier_60_rehab(contract):
        return _TIER_60_REHAB
    return _TIER_50


def _qualifies_for_tier_90(contract: RentalContract, finca: RentalFinca) -> bool:
    """Tier a) — same landlord + new contract + zona tensionada +
    initial rent more than 5 % below the prior contract's indexed
    last rent.
    """
    if not finca.is_stressed_area:
        return False
    if contract.prior_contract_last_rent is None:
        return False
    if contract.prior_contract_last_rent <= Decimal("0"):
        return False
    if contract.initial_rent < Decimal("0"):
        raise TierResolutionError("initial_rent must be non-negative")
    rebaja_ratio = (contract.prior_contract_last_rent - contract.initial_rent) / contract.prior_contract_last_rent
    return rebaja_ratio > PRIOR_RENT_REBAJA_THRESHOLD


def _resolve_tier_70(
    contract: RentalContract,
    finca: RentalFinca,
) -> TierResolution | None:
    """Tier b) — split into two independent ordinals.

    Returns ``None`` when neither ordinal applies. Returns a
    :class:`TierResolution` with the appropriate qualifying share
    when ordinal 1.º (joven inquilino) applies; full-share otherwise.
    """
    public_admin_resolution = _resolve_tier_70_b_2(contract)
    if public_admin_resolution is not None:
        return public_admin_resolution
    return _resolve_tier_70_b_1(contract, finca)


def _resolve_tier_70_b_2(contract: RentalContract) -> TierResolution | None:
    """Ordinal 2.º — Public Admin tenant or Ley 49/2002 entity destining
    the dwelling to alquiler social, IMV beneficiary, or dwelling in a
    public housing program with a rent cap."""
    if (
        contract.tenant_is_public_admin
        or contract.tenant_is_ley_49_2002_entity_with_social_use
        or contract.tenant_is_imv_beneficiary
        or contract.dwelling_in_public_program
    ):
        return _TIER_70_PUBLIC_ADMIN
    return None


def _resolve_tier_70_b_1(
    contract: RentalContract,
    finca: RentalFinca,
) -> TierResolution | None:
    """Ordinal 1.º — first-time rental + zona tensionada + tenant aged 18-35.

    Multi-tenant case: the reducción applies proportionally to the
    qualifying-co-tenant share. The age bracket is enforced at the
    co-tenant level via ``qualifying_co_tenant_count``; the
    ``tenant_min_age`` / ``tenant_max_age`` fields on the contract
    are advisory metadata that surface a configuration mistake when
    inconsistent.
    """
    if not contract.is_first_rental:
        return None
    if not finca.is_stressed_area:
        return None
    if contract.qualifying_co_tenant_count == 0:
        return None
    if (
        contract.tenant_min_age is not None
        and contract.tenant_max_age is not None
        and (contract.tenant_min_age < JOVEN_TENANT_AGE_MIN or contract.tenant_max_age > JOVEN_TENANT_AGE_MAX)
        and contract.qualifying_co_tenant_count == contract.tenant_count
    ):
        raise TierResolutionError(
            "tenant age range falls outside 18-35 but qualifying_co_tenant_count claims every co-tenant qualifies",
        )
    qualifying_share = Decimal(contract.qualifying_co_tenant_count) / Decimal(contract.tenant_count)
    return TierResolution(
        tier=ReduccionTier.TIER_70_JOVEN,
        reduccion_pct=Decimal("0.70"),
        qualifying_share=qualifying_share,
        boe_citation_id="art_23_2_b_1",
    )


def _qualifies_for_tier_60_rehab(contract: RentalContract) -> bool:
    """Tier c) — actuación de rehabilitación finished within 730 days
    preceding the contract celebration date.
    """
    if contract.rehabilitation_finished_date is None:
        return False
    delta_days = (contract.contract_celebration_date - contract.rehabilitation_finished_date).days
    return 0 <= delta_days <= REHAB_LOOKBACK_DAYS


__all__ = [
    "DEFAULT_EJERCICIO_AMENDMENT_YEAR",
    "LEY_12_2023_IN_FORCE_DATE",
    "TierResolution",
    "resolve_reduccion",
]
