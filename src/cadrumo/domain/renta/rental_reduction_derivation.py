"""Derive whether the art. 23.2 LIRPF reduction reaches a lease, and at which rate.

The rate is never stored: it follows from the facts the lease records at signing
(:class:`~cadrumo.domain.contribuyente.arrendamiento_record.ArrendamientoRecord`)
and from dated registry data, the regime dates and the two thresholds the tiers
read. The order follows the law:

* a lease not for a dwelling has no reduction (art. 23.2, first paragraph);
* a devengo before the regime start, or a contract concluded before the cut-off,
  takes the legacy reduction (DT 38 LIRPF, applying the wording in force on
  31 December 2021);
* any other contract takes the tiers, in the law's order: 90 per cent for a
  tensioned-zone lease whose initial rent is more than the threshold below the
  last rent of the previous contract; 70 per cent for a first letting in a
  tensioned zone to tenants aged 18 to 35, or for a qualifying public or
  non-profit tenant; 60 per cent for a rehabilitation finished in the look-back
  before the contract; 50 per cent otherwise;
* a tiered-regime contract that breaches art. 17.6 LAU has no reduction. That
  bar is part of the wording Ley 12/2023 introduced, so it does not reach a
  contract the legacy wording governs.

A fact the tier regime needs to decide anything (dwelling use, the tensioned
zone, and the art. 17.6 LAU fact in a tensioned zone) refuses when unstated. A
fact that could only raise the tier and is unstated is not claimed, so the
residual tier applies: an absent benefit can never lower the tax. A lease where
only some natural-person tenants meet the age condition is refused, because the
law then reduces only the part of the income that proportionally corresponds to
them and no stored fact gives that proportion.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final

from ...core.calendar_shift import shift_by_calendar_years
from ..contribuyente.arrendamiento_record import (
    ArrendamientoRecord,
    ArrendatarioEntidadFinalidad,
    InquilinoEdad,
)
from .rental_reduction import RentalReductionArt232Tier

__all__ = [
    "TIER_50",
    "TIER_60",
    "TIER_70",
    "TIER_90",
    "RentalReductionArt232Rules",
    "RentalReductionDerivation",
    "RentalReductionRefusal",
    "derive_rental_reduction",
    "leases_active_in",
]

TIER_90: Final = RentalReductionArt232Tier("tier-90")
TIER_70: Final = RentalReductionArt232Tier("tier-70")
TIER_60: Final = RentalReductionArt232Tier("tier-60")
TIER_50: Final = RentalReductionArt232Tier("tier-50")


class RentalReductionRefusal(StrEnum):
    """Why the reduction of a profile's rental income cannot be derived."""

    NO_LEASE = "no_lease"
    SEVERAL_LEASES = "several_leases"
    LEASE_UNREADABLE = "lease_unreadable"
    USO_VIVIENDA_UNSTATED = "uso_vivienda_unstated"
    ZONA_TENSIONADA_UNSTATED = "zona_tensionada_unstated"
    LAU_17_6_UNSTATED = "lau_17_6_unstated"
    MIXED_TENANT_AGES = "mixed_tenant_ages"


@dataclass(frozen=True, slots=True)
class RentalReductionArt232Rules:
    """The dated registry data the derivation reads, resolved for one devengo.

    ``legacy_tier`` is the token of the legacy rate; ``rebaja_threshold`` is the
    share by which the initial rent must fall below the previous contract's last
    rent for the 90 per cent tier; ``rehabilitation_lookback_years`` is the
    number of calendar years before the contract in which a rehabilitation must
    have finished for the 60 per cent tier.
    """

    regime_start: date
    contract_cut_off: date
    legacy_tier: RentalReductionArt232Tier
    rebaja_threshold: Decimal
    rehabilitation_lookback_years: int


@dataclass(frozen=True, slots=True)
class RentalReductionDerivation:
    """The outcome for one ejercicio: a tier, no reduction, or a refusal.

    ``aplicable`` is ``True`` with a ``tier`` when the reduction reaches the
    lease, ``False`` with no tier when it does not, and ``None`` with a
    ``refusal`` when it cannot be decided. ``lease`` names the lease row the
    outcome concerns, when there is one.
    """

    aplicable: bool | None
    tier: RentalReductionArt232Tier | None = None
    refusal: RentalReductionRefusal | None = None
    lease: int | None = None


def leases_active_in(leases: Iterable[ArrendamientoRecord], *, year: int) -> tuple[ArrendamientoRecord, ...]:
    """Return the leases whose period overlaps the calendar year ``year``."""
    first, last = date(year, 1, 1), date(year, 12, 31)
    return tuple(
        lease
        for lease in leases
        if lease.fecha_inicio <= last and (lease.fecha_fin is None or lease.fecha_fin >= first)
    )


def derive_rental_reduction(
    leases: tuple[ArrendamientoRecord, ...],
    *,
    devengo: date,
    rules: RentalReductionArt232Rules,
) -> RentalReductionDerivation:
    """Derive the reduction for the leases active in the ejercicio whose devengo is ``devengo``.

    One lease is supported: the reduction applies per contract, and until the
    return carries a row per property the single scalar box can hold only one.
    """
    if not leases:
        return RentalReductionDerivation(aplicable=None, refusal=RentalReductionRefusal.NO_LEASE)
    if len(leases) > 1:
        return RentalReductionDerivation(aplicable=None, refusal=RentalReductionRefusal.SEVERAL_LEASES)
    lease = leases[0]
    if lease.uso_vivienda is None:
        return _refused(lease, RentalReductionRefusal.USO_VIVIENDA_UNSTATED)
    if not lease.uso_vivienda:
        return RentalReductionDerivation(aplicable=False, lease=lease.clave)
    if devengo < rules.regime_start or lease.fecha_contrato < rules.contract_cut_off:
        return RentalReductionDerivation(aplicable=True, tier=rules.legacy_tier, lease=lease.clave)
    return _tiered(lease, rules)


def _refused(lease: ArrendamientoRecord, refusal: RentalReductionRefusal) -> RentalReductionDerivation:
    return RentalReductionDerivation(aplicable=None, refusal=refusal, lease=lease.clave)


def _tiered(lease: ArrendamientoRecord, rules: RentalReductionArt232Rules) -> RentalReductionDerivation:
    if lease.zona_tensionada is None:
        return _refused(lease, RentalReductionRefusal.ZONA_TENSIONADA_UNSTATED)
    if lease.zona_tensionada:
        if lease.incumple_lau_17_6 is None:
            return _refused(lease, RentalReductionRefusal.LAU_17_6_UNSTATED)
        if lease.incumple_lau_17_6:
            return RentalReductionDerivation(aplicable=False, lease=lease.clave)
        if _rent_cut_beyond_threshold(lease, rules.rebaja_threshold):
            return RentalReductionDerivation(aplicable=True, tier=TIER_90, lease=lease.clave)
    young_tenants = _young_tenant_letting(lease)
    if young_tenants is None:
        return _refused(lease, RentalReductionRefusal.MIXED_TENANT_AGES)
    if young_tenants or _qualifying_entity_tenant(lease):
        return RentalReductionDerivation(aplicable=True, tier=TIER_70, lease=lease.clave)
    if _rehabilitated_within_lookback(lease, rules.rehabilitation_lookback_years):
        return RentalReductionDerivation(aplicable=True, tier=TIER_60, lease=lease.clave)
    return RentalReductionDerivation(aplicable=True, tier=TIER_50, lease=lease.clave)


def _rent_cut_beyond_threshold(lease: ArrendamientoRecord, threshold: Decimal) -> bool:
    """Art. 23.2.a: the initial rent is more than ``threshold`` below the previous contract's last rent."""
    if lease.renta_inicial is None or lease.renta_ultima_contrato_anterior is None:
        return False
    return lease.renta_inicial < lease.renta_ultima_contrato_anterior * (Decimal(1) - threshold)


def _young_tenant_letting(lease: ArrendamientoRecord) -> bool | None:
    """Art. 23.2.b.1: a first letting in a tensioned zone to tenants aged 18 to 35.

    Returns ``None`` when the letting otherwise qualifies but only some of its
    natural-person tenants are in the age band.
    """
    if not (lease.zona_tensionada and lease.primer_arrendamiento_vivienda):
        return False
    bands = [tenant.franja_edad for tenant in lease.inquilinos if tenant.franja_edad is not InquilinoEdad.NO_APLICA]
    if not bands:
        return False
    in_band = sum(band is InquilinoEdad.DE_18_A_35 for band in bands)
    if in_band == len(bands):
        return True
    if in_band == 0:
        return False
    return None


def _qualifying_entity_tenant(lease: ArrendamientoRecord) -> bool:
    """Art. 23.2.b.2: a public administration or non-profit tenant letting for social or affordable housing."""
    return (
        lease.arrendatario_entidad_tipo is not None
        and lease.arrendatario_entidad_finalidad is ArrendatarioEntidadFinalidad.VIVIENDA_ASEQUIBLE_O_SOCIAL
    )


def _rehabilitated_within_lookback(lease: ArrendamientoRecord, lookback_years: int) -> bool:
    """Art. 23.2.c: a rehabilitation finished in the calendar years before the contract, counted de fecha a fecha."""
    finished = lease.rehabilitacion_fecha
    if finished is None:
        return False
    return shift_by_calendar_years(lease.fecha_contrato, -lookback_years) <= finished <= lease.fecha_contrato
