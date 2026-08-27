"""Unit tests for the LIRPF art. 23.2 tier resolver.

Exercises :func:`cadrumo.domain.fincas.resolve_reduccion` against every BOE
trigger condition, every priority-order edge, every effective-date
branch, the LAU art. 17.6 forfeit sentinel, and the qualifying-share
split for the tier 70-b-1 (joven inquilino) ordinal.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .. import (
    LEY_12_2023_IN_FORCE_DATE,
    Arrendamiento,
    Finca,
    ReduccionTier,
    TierResolutionError,
    UseType,
    resolve_reduccion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _finca(*, is_stressed_area: bool = False) -> Finca:
    return Finca(
        identifier="test-finca",
        address="Calle de Prueba 1",
        valor_catastral_total=Decimal("100000.00"),
        valor_catastral_construccion=Decimal("70000.00"),
        coste_adquisicion=Decimal("200000.00"),
        coste_adquisicion_construccion=Decimal("140000.00"),
        acquisition_date=date(2010, 1, 1),
        use_type=UseType.VIVIENDA_ARRENDADA,
        is_stressed_area=is_stressed_area,
    )


def _contract(
    *,
    finca_id: int = 1,
    celebration: date = date(2024, 6, 1),
    tenant_count: int = 1,
    qualifying: int = 0,
    initial_rent: Decimal = Decimal("1000.00"),
    is_first_rental: bool = False,
    rehabilitation_finished_date: date | None = None,
    prior_contract_last_rent: Decimal | None = None,
    tenant_is_public_admin: bool = False,
    tenant_is_ley_49_2002_entity_with_social_use: bool = False,
    tenant_is_imv_beneficiary: bool = False,
    dwelling_in_public_program: bool = False,
    lau_17_6_compliant: bool = True,
    tenant_min_age: int | None = None,
    tenant_max_age: int | None = None,
) -> Arrendamiento:
    return Arrendamiento(
        finca_id=finca_id,
        contract_celebration_date=celebration,
        tenant_count=tenant_count,
        qualifying_co_tenant_count=qualifying,
        tenant_min_age=tenant_min_age,
        tenant_max_age=tenant_max_age,
        tenant_is_public_admin=tenant_is_public_admin,
        tenant_is_ley_49_2002_entity_with_social_use=tenant_is_ley_49_2002_entity_with_social_use,
        tenant_is_imv_beneficiary=tenant_is_imv_beneficiary,
        dwelling_in_public_program=dwelling_in_public_program,
        prior_contract_last_rent=prior_contract_last_rent,
        initial_rent=initial_rent,
        is_first_rental=is_first_rental,
        rehabilitation_finished_date=rehabilitation_finished_date,
        lau_17_6_compliant=lau_17_6_compliant,
    )


class TestPreAmendmentAndDt38:
    """Effective-date dispatch for ejercicios before the Ley 12/2023 amendment."""

    def test_pre_amendment_ejercicio_returns_flat_60(self) -> None:
        """Filings of ejercicio 2023 use the prior flat 60 % regardless of contract date."""
        result = resolve_reduccion(_contract(celebration=date(2024, 1, 1)), _finca(), period_year=2023)
        assert result.tier is ReduccionTier.TIER_60_GRANDFATHERED_DT38
        assert result.reduccion_pct == Decimal("0.60")
        assert result.legal_refs == ("ley-35-2006:art-23-2021",)

    def test_dt_38_pre_2023_05_26_contract_returns_60(self) -> None:
        """2024+ ejercicio + contract signed on 2023-05-25 → DT 38ª flat 60 %."""
        result = resolve_reduccion(
            _contract(celebration=date(2023, 5, 25)),
            _finca(),
            period_year=2024,
        )
        assert result.tier is ReduccionTier.TIER_60_GRANDFATHERED_DT38
        assert result.reduccion_pct == Decimal("0.60")
        assert result.legal_refs == ("ley-35-2006:dt-38", "ley-35-2006:art-23-2021")

    def test_2024_ejercicio_2023_05_26_contract_uses_new_framework(self) -> None:
        """Boundary: contract signed exactly on 2023-05-26 is in-scope for the new framework."""
        result = resolve_reduccion(
            _contract(celebration=LEY_12_2023_IN_FORCE_DATE),
            _finca(),
            period_year=2024,
        )
        # Default contract has none of the tier triggers → 50 %.
        assert result.tier is ReduccionTier.TIER_50


class TestLau176Forfeit:
    """LAU art. 17.6 non-compliance forfeits the reducción entirely."""

    def test_non_compliant_contract_forfeits_reduccion(self) -> None:
        result = resolve_reduccion(
            _contract(
                lau_17_6_compliant=False,
                is_first_rental=True,
                qualifying=1,
                tenant_min_age=25,
                tenant_max_age=25,
            ),
            _finca(is_stressed_area=True),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.FORFEIT_LAU_17_6
        assert result.reduccion_pct == Decimal("0")
        assert result.qualifying_share == Decimal("0")
        assert result.legal_refs == ("ley-35-2006:art-23",)


class TestTier90:
    """Tier 90-a — same landlord + zona tensionada + > 5 % rebaja triggers."""

    def test_happy_path_more_than_5pct_rebaja(self) -> None:
        """90-a: same landlord + zona tensionada + initial rent 6 % below prior."""
        result = resolve_reduccion(
            _contract(
                celebration=date(2024, 1, 1),
                initial_rent=Decimal("940.00"),
                prior_contract_last_rent=Decimal("1000.00"),
            ),
            _finca(is_stressed_area=True),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_90
        assert result.reduccion_pct == Decimal("0.90")
        assert result.legal_refs == ("ley-35-2006:art-23",)

    def test_exactly_5pct_rebaja_falls_through(self) -> None:
        """90-a wording is 'más de un 5 por ciento' — exactly 5 % does not qualify."""
        result = resolve_reduccion(
            _contract(
                celebration=date(2024, 1, 1),
                initial_rent=Decimal("950.00"),
                prior_contract_last_rent=Decimal("1000.00"),
            ),
            _finca(is_stressed_area=True),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_50

    def test_no_zona_tensionada_falls_through(self) -> None:
        result = resolve_reduccion(
            _contract(
                celebration=date(2024, 1, 1),
                initial_rent=Decimal("800.00"),
                prior_contract_last_rent=Decimal("1000.00"),
            ),
            _finca(is_stressed_area=False),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_50


class TestTier70Joven:
    """Tier 70-b-1 — first-rental + zona tensionada + 18-35 yo qualifying share."""

    def test_single_qualifying_co_tenant_full_share(self) -> None:
        result = resolve_reduccion(
            _contract(
                celebration=date(2024, 6, 1),
                tenant_count=1,
                qualifying=1,
                tenant_min_age=30,
                tenant_max_age=30,
                is_first_rental=True,
            ),
            _finca(is_stressed_area=True),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_70_JOVEN
        assert result.reduccion_pct == Decimal("0.70")
        assert result.qualifying_share == Decimal("1")
        assert result.legal_refs == ("ley-35-2006:art-23",)

    def test_multi_tenant_partial_qualifying_share(self) -> None:
        """2 of 3 tenants qualify → share = 2/3."""
        result = resolve_reduccion(
            _contract(
                celebration=date(2024, 6, 1),
                tenant_count=3,
                qualifying=2,
                tenant_min_age=22,
                tenant_max_age=34,
                is_first_rental=True,
            ),
            _finca(is_stressed_area=True),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_70_JOVEN
        assert result.reduccion_pct == Decimal("0.70")
        assert result.qualifying_share == Decimal("2") / Decimal("3")

    def test_not_first_rental_falls_through(self) -> None:
        result = resolve_reduccion(
            _contract(
                celebration=date(2024, 6, 1),
                tenant_count=1,
                qualifying=1,
                tenant_min_age=30,
                tenant_max_age=30,
                is_first_rental=False,
            ),
            _finca(is_stressed_area=True),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_50

    def test_age_36_with_no_qualifying_co_tenant_falls_through(self) -> None:
        """tenant 36 yo, qualifying=0 → tier 70-b-1 does not apply."""
        result = resolve_reduccion(
            _contract(
                celebration=date(2024, 6, 1),
                tenant_count=1,
                qualifying=0,
                tenant_min_age=36,
                tenant_max_age=36,
                is_first_rental=True,
            ),
            _finca(is_stressed_area=True),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_50

    def test_age_range_outside_window_with_full_qualifying_raises(self) -> None:
        """Inconsistent metadata: every tenant claimed to qualify but age range
        excludes the 18-35 window."""
        with pytest.raises(TierResolutionError):
            resolve_reduccion(
                _contract(
                    celebration=date(2024, 6, 1),
                    tenant_count=1,
                    qualifying=1,
                    tenant_min_age=40,
                    tenant_max_age=40,
                    is_first_rental=True,
                ),
                _finca(is_stressed_area=True),
                period_year=2025,
            )


class TestTier70PublicAdmin:
    """Tier 70-b-2 — Public Admin / Ley 49/2002 / IMV / public-program triggers."""

    def test_public_admin_tenant_qualifies(self) -> None:
        result = resolve_reduccion(
            _contract(celebration=date(2024, 6, 1), tenant_is_public_admin=True),
            _finca(),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_70_PUBLIC_ADMIN
        assert result.reduccion_pct == Decimal("0.70")
        assert result.qualifying_share == Decimal("1")
        assert result.legal_refs == ("ley-35-2006:art-23",)

    def test_ley_49_2002_entity_with_social_use_qualifies(self) -> None:
        result = resolve_reduccion(
            _contract(
                celebration=date(2024, 6, 1),
                tenant_is_ley_49_2002_entity_with_social_use=True,
            ),
            _finca(),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_70_PUBLIC_ADMIN

    def test_imv_beneficiary_qualifies(self) -> None:
        result = resolve_reduccion(
            _contract(celebration=date(2024, 6, 1), tenant_is_imv_beneficiary=True),
            _finca(),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_70_PUBLIC_ADMIN

    def test_dwelling_in_public_program_qualifies(self) -> None:
        result = resolve_reduccion(
            _contract(celebration=date(2024, 6, 1), dwelling_in_public_program=True),
            _finca(),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_70_PUBLIC_ADMIN


class TestTier60Rehab:
    """Tier 60-c — rehabilitation finished within 730 days of contract."""

    def test_rehab_finished_365_days_before_qualifies(self) -> None:
        result = resolve_reduccion(
            _contract(
                celebration=date(2025, 6, 1),
                rehabilitation_finished_date=date(2024, 6, 2),
            ),
            _finca(),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_60_REHAB
        assert result.reduccion_pct == Decimal("0.60")
        assert result.legal_refs == ("ley-35-2006:art-23",)

    def test_rehab_finished_730_days_before_qualifies_boundary(self) -> None:
        """730-day inclusive boundary."""
        celebration = date(2025, 6, 1)
        rehab = date(2023, 6, 2)  # 730 days before celebration
        delta = (celebration - rehab).days
        assert delta == 730
        result = resolve_reduccion(
            _contract(celebration=celebration, rehabilitation_finished_date=rehab),
            _finca(),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_60_REHAB

    def test_rehab_finished_exactly_two_calendar_years_before_still_qualifies(self) -> None:
        """This test previously asserted the defect as the contract.

        2023-06-01 is exactly two calendar years before 2025-06-01, which art. 23.2.c
        admits -- but it is 731 days, because 2024 is a leap year, and the retired
        730-day rule refused it and dropped the filer to letra d). The old assertion
        was TIER_50, so the suite defended the day count against the article.
        """
        celebration = date(2025, 6, 1)
        rehab = date(2023, 6, 1)
        assert (celebration - rehab).days == 731, "the leap span this case exists for has moved"

        result = resolve_reduccion(
            _contract(celebration=celebration, rehabilitation_finished_date=rehab),
            _finca(),
            period_year=2025,
        )

        assert result.tier is ReduccionTier.TIER_60_REHAB

    def test_rehab_finished_one_day_before_the_window_opens_falls_through(self) -> None:
        """The window is still bounded; only its unit changed."""
        celebration = date(2025, 6, 1)
        rehab = date(2023, 5, 31)

        result = resolve_reduccion(
            _contract(celebration=celebration, rehabilitation_finished_date=rehab),
            _finca(),
            period_year=2025,
        )

        assert result.tier is ReduccionTier.TIER_50

    def test_rehab_after_celebration_does_not_apply(self) -> None:
        result = resolve_reduccion(
            _contract(
                celebration=date(2024, 1, 1),
                rehabilitation_finished_date=date(2024, 6, 1),
            ),
            _finca(),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_50


class TestTier50Default:
    """Tier 50 fallback when no higher-priority trigger applies."""

    def test_no_triggers_returns_50(self) -> None:
        result = resolve_reduccion(
            _contract(celebration=date(2024, 6, 1)),
            _finca(),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_50
        assert result.reduccion_pct == Decimal("0.50")
        assert result.legal_refs == ("ley-35-2006:art-23",)


class TestPriorityOrder:
    """BOE priority order — highest applicable tier wins when multiple match."""

    def test_90_wins_over_70_when_both_apply(self) -> None:
        """90-a + 70-b-1 conditions both met → 90-a wins (BOE priority)."""
        result = resolve_reduccion(
            _contract(
                celebration=date(2024, 6, 1),
                tenant_count=1,
                qualifying=1,
                tenant_min_age=25,
                tenant_max_age=25,
                is_first_rental=True,
                initial_rent=Decimal("900.00"),
                prior_contract_last_rent=Decimal("1000.00"),
            ),
            _finca(is_stressed_area=True),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_90

    def test_70_wins_over_60_rehab_when_both_apply(self) -> None:
        """70-b-2 (Public Admin) + 60-c (rehab) both met → 70 wins."""
        result = resolve_reduccion(
            _contract(
                celebration=date(2025, 6, 1),
                tenant_is_public_admin=True,
                rehabilitation_finished_date=date(2024, 6, 2),
            ),
            _finca(),
            period_year=2025,
        )
        assert result.tier is ReduccionTier.TIER_70_PUBLIC_ADMIN


def _finca_with_use_type(use_type: UseType) -> Finca:
    """Construct a baseline :class:`Finca` with the requested ``use_type`` substituted in."""
    return Finca(
        identifier="use-type-test",
        address="Calle Use-Type 1",
        valor_catastral_total=Decimal("100000.00"),
        valor_catastral_construccion=Decimal("70000.00"),
        coste_adquisicion=Decimal("200000.00"),
        coste_adquisicion_construccion=Decimal("140000.00"),
        acquisition_date=date(2010, 1, 1),
        use_type=use_type,
        is_stressed_area=False,
    )


class TestUseTypeReduccionGate:
    """LIRPF art. 23.2 reducción applies only to VIVIENDA_ARRENDADA use type.

    Authority: cross-domain continuity contract
    (R9-ROBERTO-HIGH). The reducción attaches to ``arrendamientos
    destinados a vivienda permanente``; the second paragraph of art.
    23.2 carves out touristic / temporary rentals, and the use-type
    mapping further excludes commercial premises and non-rented use
    types.
    """

    @pytest.mark.parametrize(
        "ineligible_use_type",
        [
            UseType.VIVIENDA_TURISTICA,
            UseType.LOCAL_COMERCIAL,
            UseType.VIVIENDA_HABITUAL,
            UseType.OTRO_INMUEBLE_NO_AFECTO,
            UseType.VIVIENDA_DESOCUPADA,
        ],
    )
    def test_resolve_reduccion_refuses_non_arrendada_use_types(self, ineligible_use_type: UseType) -> None:
        """Any use_type other than VIVIENDA_ARRENDADA refuses the reducción."""
        with pytest.raises(TierResolutionError, match=r"art\. 23\.2 LIRPF"):
            resolve_reduccion(
                _contract(celebration=date(2024, 6, 1)),
                _finca_with_use_type(ineligible_use_type),
                period_year=2025,
            )

    def test_resolve_reduccion_accepts_arrendada(self) -> None:
        """VIVIENDA_ARRENDADA is the sole eligible use_type and dispatches normally."""
        result = resolve_reduccion(
            _contract(celebration=date(2024, 6, 1)),
            _finca_with_use_type(UseType.VIVIENDA_ARRENDADA),
            period_year=2025,
        )
        # Default contract has no stressed-area / tier-90 qualifier and
        # no rehab; falls through to the TIER_50 default. Either way,
        # the call must return rather than raise.
        assert result.tier is ReduccionTier.TIER_50

    def test_vivienda_turistica_is_member_of_use_type(self) -> None:
        """The new VIVIENDA_TURISTICA enum slot exists and is value-stable."""
        assert UseType.VIVIENDA_TURISTICA.value == "VIVIENDA_TURISTICA"
