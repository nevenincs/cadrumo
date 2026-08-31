"""LIRPF art. 23.2 four-tier auto-resolver post Ley 12/2023.

Implements the BOE priority order (90 → 70 → 60 → 50, highest
applicable wins) per disposición final segunda apartado uno of
Ley 12/2023, de 24 de mayo (BOE-A-2023-12203).

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
(:attr:`domain.fincas.ReduccionTier.FORFEIT_LAU_17_6`) — checked
before any tier evaluation per the closing paragraph of the rewritten
apartado 2.

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

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG, Modelo
from ...core.calendar_shift import shift_by_calendar_years
from ...core.logging import get_logger
from ..calculations.registry.ids import LegalRefId
from ._enums import ReduccionTier, UseType
from ._models import Arrendamiento, Finca
from .errors import TierResolutionError

_logger = get_logger(__name__)

LEY_12_2023_IN_FORCE_DATE: date = date(2023, 5, 26)
"""Entry-into-force date of Ley 12/2023 (BOE-A-2023-12203). Contracts
celebrated on or after this date are subject to the new four-tier
framework once the IRPF amendment also takes legal effect."""

DEFAULT_EJERCICIO_AMENDMENT_YEAR: int = 2024
"""First ejercicio in which the new IRPF apartado 2 art. 23 wording
applies (Ley 12/2023 disposición final novena segundo párrafo)."""

REHAB_LOOKBACK_YEARS: int = 2
"""``los dos años anteriores`` counted as whole CALENDAR years.

The BOE wording is "que hubiera finalizado en los dos años anteriores a la
fecha de la celebración del contrato de arrendamiento", which counts *de
fecha a fecha* and not in days. This shipped as a 730-day approximation,
which is one day short whenever the two-year span contains a 29 February:
a rehabilitation finished exactly two calendar years before a contract
celebrated on 2024-03-01 is 731 days away and was denied tier c), dropping
the reducción from 60 per cent to 50. Every figure in the rule was right;
the unit was not.

Counted through :func:`~core.calendar_shift.shift_by_calendar_years`, so the
leap-day clamp is decided once for every legal period rather than here."""

PRIOR_RENT_REBAJA_THRESHOLD: Decimal = Decimal("0.05")
"""Tier 90-a threshold: ``más de un 5 por ciento``. Strict ``>``
comparison — exactly 5 % does not qualify (BOE wording is "en más
de un 5 por ciento", not "en al menos un 5 por ciento")."""

JOVEN_TENANT_AGE_MIN: int = 18
JOVEN_TENANT_AGE_MAX: int = 35
"""Tier 70-b-1 inclusive age range (``BOE``: "una edad comprendida entre
18 y 35 años")."""

_LIRPF_ART_23_CURRENT_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-35-2006:art-23",)
_LIRPF_ART_23_2021_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-35-2006:art-23-2021",)
_LIRPF_DT_38_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-35-2006:dt-38",
    "ley-35-2006:art-23-2021",
)


class TierResolution(BaseModel):
    """Outcome of a single :func:`resolve_reduccion` invocation.

    Attributes:
        tier: Closed-enum tier identifier.
        reduccion_pct: Numeric reducción percentage as a Decimal in
            ``[0, 1]``. Multiplied by ``qualifying_share`` and the
            per-contract rendimiento neto positivo to compute the
            rental reduction amount.
        qualifying_share: Fraction of rendimiento neto eligible for
            the tier reducción. Always ``1`` except for tier 70-b-1
            with mixed-qualification co-tenants.
        legal_refs: Registry legal-reference ids grounding the
            resolution in the bundled legal catalogue and corpus.
    """

    model_config = STRICT_FROZEN_CONFIG

    tier: ReduccionTier
    reduccion_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    qualifying_share: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)


_FORFEIT_LAU_17_6 = TierResolution(
    tier=ReduccionTier.FORFEIT_LAU_17_6,
    reduccion_pct=Decimal("0"),
    qualifying_share=Decimal("0"),
    legal_refs=_LIRPF_ART_23_CURRENT_LEGAL_REFS,
)
_DT_38 = TierResolution(
    tier=ReduccionTier.TIER_60_GRANDFATHERED_DT38,
    reduccion_pct=Decimal("0.60"),
    qualifying_share=Decimal("1"),
    legal_refs=_LIRPF_DT_38_LEGAL_REFS,
)
_PRE_AMENDMENT = TierResolution(
    tier=ReduccionTier.TIER_60_GRANDFATHERED_DT38,
    reduccion_pct=Decimal("0.60"),
    qualifying_share=Decimal("1"),
    legal_refs=_LIRPF_ART_23_2021_LEGAL_REFS,
)
_TIER_50 = TierResolution(
    tier=ReduccionTier.TIER_50,
    reduccion_pct=Decimal("0.50"),
    qualifying_share=Decimal("1"),
    legal_refs=_LIRPF_ART_23_CURRENT_LEGAL_REFS,
)
_TIER_60_REHAB = TierResolution(
    tier=ReduccionTier.TIER_60_REHAB,
    reduccion_pct=Decimal("0.60"),
    qualifying_share=Decimal("1"),
    legal_refs=_LIRPF_ART_23_CURRENT_LEGAL_REFS,
)
_TIER_70_PUBLIC_ADMIN = TierResolution(
    tier=ReduccionTier.TIER_70_PUBLIC_ADMIN,
    reduccion_pct=Decimal("0.70"),
    qualifying_share=Decimal("1"),
    legal_refs=_LIRPF_ART_23_CURRENT_LEGAL_REFS,
)
_TIER_90 = TierResolution(
    tier=ReduccionTier.TIER_90,
    reduccion_pct=Decimal("0.90"),
    qualifying_share=Decimal("1"),
    legal_refs=_LIRPF_ART_23_CURRENT_LEGAL_REFS,
)


def _with_registry_rate(template: TierResolution, period_year: int, tier_id: str) -> TierResolution:
    """Return ``template`` with its reducción rate sourced from the registry.

    Wires a four-tier dispatch result to the law-determined
    ``renta-<period_year>-rental-reduccion-rate-<tier_id>`` Modelo-100 parameter
    so the registry is the causal authority for the numeric rate. When the
    registry rate equals the template's documented rate — every supported year
    currently matches — the frozen singleton is returned unchanged, preserving
    identity and behaviour.
    Only the genuine four-tier results route through here; the grandfathering
    (pre-amendment / DT-38) and forfeit resolutions are distinct provisions and
    keep their documented constant.
    """
    rate = _resolve_tier_reduccion_rate(period_year, tier_id)
    if rate == template.reduccion_pct:
        return template
    return template.model_copy(update={"reduccion_pct": rate})


def resolve_reduccion(
    contract: Arrendamiento,
    finca: Finca,
    period_year: int,
    *,
    ejercicio_amendment_year: int | None = None,
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
        reducción percentage, the qualifying share, and the registry
        legal-reference ids.

    Raises:
        TierResolutionError: If ``finca.use_type`` is not eligible
            for the LIRPF Art. 23.2 reducción — the article applies
            only to ``arrendamientos de bienes inmuebles destinados a
            vivienda``, which the second paragraph excludes for
            touristic / temporary rentals and which the use-type
            mapping further excludes for commercial premises and
            non-rented use types.
    """
    if finca.use_type is not UseType.VIVIENDA_ARRENDADA:
        raise TierResolutionError(
            f"reducción art. 23.2 LIRPF refused: finca {finca.id} use_type "
            f"{finca.use_type.value!r} is not VIVIENDA_ARRENDADA. The reducción "
            f"applies only to arrendamientos destinados a vivienda permanente; "
            f"the second paragraph of art. 23.2 excludes touristic / temporary "
            f"rentals (VIVIENDA_TURISTICA), and the article scope excludes "
            f"commercial premises (LOCAL_COMERCIAL) and non-rented use types.",
        )
    resolved_amendment_year = (
        ejercicio_amendment_year
        if ejercicio_amendment_year is not None
        else _resolve_ejercicio_amendment_year(period_year)
    )
    if period_year < resolved_amendment_year:
        _logger.debug(
            "reduccion tier: pre-amendment flat 60%% for contract_id=%s period=%d",
            contract.id,
            period_year,
        )
        return _PRE_AMENDMENT
    if contract.contract_celebration_date < LEY_12_2023_IN_FORCE_DATE:
        _logger.debug(
            "reduccion tier: DT-38 grandfathered 60%% for contract_id=%s (celebration %s)",
            contract.id,
            contract.contract_celebration_date.isoformat(),
        )
        return _DT_38
    if not contract.lau_17_6_compliant:
        _logger.debug("reduccion tier: FORFEIT (LAU 17.6 non-compliant) for contract_id=%s", contract.id)
        return _FORFEIT_LAU_17_6
    rebaja_threshold = _resolve_prior_rent_rebaja_threshold(period_year)
    if _qualifies_for_tier_90(contract, finca, prior_rent_rebaja_threshold=rebaja_threshold):
        _logger.debug("reduccion tier: TIER_90 for contract_id=%s finca_id=%s", contract.id, finca.id)
        return _with_registry_rate(_TIER_90, period_year, "tier-90")
    age_min, age_max = _resolve_joven_tenant_age_range(period_year)
    tier_70 = _resolve_tier_70(contract, finca, joven_age_min=age_min, joven_age_max=age_max)
    if tier_70 is not None:
        _logger.debug(
            "reduccion tier: %s for contract_id=%s finca_id=%s",
            tier_70.tier.value,
            contract.id,
            finca.id,
        )
        return _with_registry_rate(tier_70, period_year, "tier-70")
    rehab_lookback_years = _resolve_rehab_lookback_years(period_year)
    if _qualifies_for_tier_60_rehab(contract, rehab_lookback_years=rehab_lookback_years):
        _logger.debug("reduccion tier: TIER_60_REHAB for contract_id=%s", contract.id)
        return _with_registry_rate(_TIER_60_REHAB, period_year, "tier-60")
    _logger.debug("reduccion tier: TIER_50 (fallback) for contract_id=%s", contract.id)
    return _with_registry_rate(_TIER_50, period_year, "tier-50")


def _qualifies_for_tier_90(
    contract: Arrendamiento,
    finca: Finca,
    *,
    prior_rent_rebaja_threshold: Decimal,
) -> bool:
    """Return True if the contract qualifies for tier a) reduccion.

    Tier a) applies when the property is in a stressed area, there is a prior
    contract, and the initial rent is more than ``prior_rent_rebaja_threshold``
    below the prior contract's indexed last rent.
    """
    if not finca.is_stressed_area:
        return False
    if contract.prior_contract_last_rent is None:
        return False
    if contract.prior_contract_last_rent <= Decimal("0"):
        return False
    if contract.initial_rent < Decimal("0"):
        _logger.warning("tier resolver: negative initial_rent for contract_id=%s", contract.id)
        raise TierResolutionError("initial_rent must be non-negative")
    rebaja_ratio = (contract.prior_contract_last_rent - contract.initial_rent) / contract.prior_contract_last_rent
    return rebaja_ratio > prior_rent_rebaja_threshold


def _resolve_prior_rent_rebaja_threshold(period_year: int) -> Decimal:
    """Read the LIRPF art. 23.2 a) rebaja threshold from the registry parameter.

    Reads ``renta-<period_year>-rental-prior-rent-rebaja-threshold`` from
    Modelo 100. A missing registry revision or parameter is a grounding defect
    and raises :class:`RegistryValidationError`.
    """
    from ..calculations.registry.formula_runtime_ops import read_parameter

    return read_parameter(
        Modelo.M100.value,
        str(period_year),
        f"renta-{period_year}-rental-prior-rent-rebaja-threshold",
        date_context={"filing_period": date(period_year, 12, 31)},
    )


def _resolve_ejercicio_amendment_year(period_year: int) -> int:
    """Read the Ley 12/2023 amendment year from the registry parameter.

    Reads ``renta-<period_year>-rental-ejercicio-amendment-year`` from
    Modelo 100. A missing registry revision or parameter is a grounding defect
    and raises :class:`RegistryValidationError`.
    """
    from ..calculations.registry.formula_runtime_ops import read_parameter

    value = read_parameter(
        Modelo.M100.value,
        str(period_year),
        f"renta-{period_year}-rental-ejercicio-amendment-year",
        date_context={"filing_period": date(period_year, 12, 31)},
    )
    return int(value)


def _resolve_tier_70(
    contract: Arrendamiento,
    finca: Finca,
    *,
    joven_age_min: int,
    joven_age_max: int,
) -> TierResolution | None:
    """Tier b) — split into two independent ordinals.

    Returns ``None`` when neither ordinal applies. Returns a
    :class:`TierResolution` with the appropriate qualifying share
    when ordinal 1.º (joven inquilino) applies; full-share otherwise.
    """
    public_admin_resolution = _resolve_tier_70_b_2(contract)
    if public_admin_resolution is not None:
        return public_admin_resolution
    return _resolve_tier_70_b_1(contract, finca, joven_age_min=joven_age_min, joven_age_max=joven_age_max)


def _resolve_tier_70_b_2(contract: Arrendamiento) -> TierResolution | None:
    """Return the tier 70 resolution for ordinal 2.º qualifying contracts, or None.

    Qualifies when the tenant is a Public Admin entity, a Ley 49/2002 entity
    destining the dwelling to alquiler social, an IMV beneficiary, or when the
    dwelling is in a public housing program with a rent cap.
    """
    if (
        contract.tenant_is_public_admin
        or contract.tenant_is_ley_49_2002_entity_with_social_use
        or contract.tenant_is_imv_beneficiary
        or contract.dwelling_in_public_program
    ):
        return _TIER_70_PUBLIC_ADMIN
    return None


def _resolve_tier_70_b_1(
    contract: Arrendamiento,
    finca: Finca,
    *,
    joven_age_min: int,
    joven_age_max: int,
) -> TierResolution | None:
    """Ordinal 1.º — first-time rental + zona tensionada + tenant aged ``joven_age_min``-``joven_age_max``.

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
        and (contract.tenant_min_age < joven_age_min or contract.tenant_max_age > joven_age_max)
        and contract.qualifying_co_tenant_count == contract.tenant_count
    ):
        raise TierResolutionError(
            f"tenant age range falls outside {joven_age_min}-{joven_age_max}"
            " but qualifying_co_tenant_count claims every co-tenant qualifies",
        )
    qualifying_share = Decimal(contract.qualifying_co_tenant_count) / Decimal(contract.tenant_count)
    return TierResolution(
        tier=ReduccionTier.TIER_70_JOVEN,
        reduccion_pct=Decimal("0.70"),
        qualifying_share=qualifying_share,
        legal_refs=_LIRPF_ART_23_CURRENT_LEGAL_REFS,
    )


def _qualifies_for_tier_60_rehab(
    contract: Arrendamiento,
    *,
    rehab_lookback_years: int,
) -> bool:
    """Return True if the contract qualifies for tier c) reduccion.

    Tier c) applies when the actuación de rehabilitación finished within the
    ``rehab_lookback_years`` CALENDAR years preceding the contract celebration
    date. The window opens with the earlier boundary and closes on the contract
    date itself; a rehabilitation finished after the contract was celebrated is
    outside it in the other direction.
    """
    if contract.rehabilitation_finished_date is None:
        return False
    finished = contract.rehabilitation_finished_date
    celebrated = contract.contract_celebration_date
    earliest = shift_by_calendar_years(celebrated, -rehab_lookback_years)
    return earliest <= finished <= celebrated


def _resolve_tier_reduccion_rate(period_year: int, tier_id: str) -> Decimal:
    """Read a LIRPF art. 23.2 tier reducción rate from the registry parameter.

    ``tier_id`` is one of ``"tier-50"``, ``"tier-60"``, ``"tier-70"``,
    ``"tier-90"``. A missing registry revision or parameter is a grounding
    defect and raises :class:`RegistryValidationError`.
    """
    from ..calculations.registry.formula_runtime_ops import read_parameter

    return read_parameter(
        Modelo.M100.value,
        str(period_year),
        f"renta-{period_year}-rental-reduccion-rate-{tier_id}",
        date_context={"filing_period": date(period_year, 12, 31)},
    )


def _resolve_joven_tenant_age_range(period_year: int) -> tuple[int, int]:
    """Read the joven-tenant age range (min, max) from registry parameters.

    Reads ``renta-<period_year>-rental-joven-tenant-age-min`` and
    ``-max``. A missing registry revision or parameter is a grounding defect
    and raises :class:`RegistryValidationError`.
    """
    from ..calculations.registry.formula_runtime_ops import read_parameter

    ctx = {"filing_period": date(period_year, 12, 31)}
    age_min = int(
        read_parameter(
            Modelo.M100.value,
            str(period_year),
            f"renta-{period_year}-rental-joven-tenant-age-min",
            date_context=ctx,
        ),
    )
    age_max = int(
        read_parameter(
            Modelo.M100.value,
            str(period_year),
            f"renta-{period_year}-rental-joven-tenant-age-max",
            date_context=ctx,
        ),
    )
    return age_min, age_max


def _resolve_rehab_lookback_years(period_year: int) -> int:
    """Read the rehab-lookback window from the registry parameter.

    Reads ``renta-<period_year>-rental-rehab-lookback-years`` from
    Modelo 100. A missing registry revision or parameter is a grounding defect
    and raises :class:`RegistryValidationError`.
    """
    from ..calculations.registry.formula_runtime_ops import read_parameter

    value = read_parameter(
        Modelo.M100.value,
        str(period_year),
        f"renta-{period_year}-rental-rehab-lookback-years",
        date_context={"filing_period": date(period_year, 12, 31)},
    )
    return int(value)


__all__ = [
    "DEFAULT_EJERCICIO_AMENDMENT_YEAR",
    "LEY_12_2023_IN_FORCE_DATE",
    "TierResolution",
    "resolve_reduccion",
]
