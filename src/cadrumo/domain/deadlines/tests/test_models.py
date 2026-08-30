"""Unit tests for the strict pydantic v2 models in :mod:`cadrumo.domain.deadlines.models`.

Verifies the strictness invariants of
:class:`cadrumo.domain.deadlines.TaxpayerProfile` (extra fields,
immutability, strict bool/enum coercion), the date-ordering
invariants of :class:`cadrumo.domain.deadlines.ModeloDeadline`, and
that :class:`cadrumo.domain.deadlines.Schedule` survives a JSON round
trip.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import Period
from ..models import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloDeadline,
    ModeloEnrollment,
    ModeloIVAProfile,
    ObligationStatus,
    Schedule,
    TaxpayerProfile,
)
from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_P_2026_1T = Period.from_year_and_code(2026, "1T")


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=True,
        pays_professionals_with_retencion=False,
        professional_income_withholding_ge_70pct=False,
        art109_activity_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=True,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        notes="example",
    )


class TestTaxpayerProfile:
    """Strictness invariants for :class:`TaxpayerProfile`."""

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            TaxpayerProfile.model_validate(
                {
                    "tax_id": "X",
                    "iva_regime": "GENERAL",
                    "has_employees": True,
                    "pays_professionals_with_retencion": False,
                    "professional_income_withholding_ge_70pct": False,
                    "art109_activity_income_withholding_ge_70pct": False,
                    "pays_rent_with_retencion": False,
                    "does_intracomunitario": False,
                    "third_party_transactions_above_347_threshold": False,
                    "bienes_extranjero_above_threshold": False,
                    "extra_field": "nope",
                },
            )

    def test_frozen(self) -> None:
        profile = _profile()
        with pytest.raises(ValidationError, match=r"frozen"):
            profile.tax_id = "Y9876543K"

    def test_strict_rejects_int_for_bool(self) -> None:
        with pytest.raises(ValidationError, match=r"valid boolean"):
            TaxpayerProfile.model_validate(
                {
                    "tax_id": "X",
                    "iva_regime": "GENERAL",
                    "has_employees": 1,
                    "pays_professionals_with_retencion": False,
                    "professional_income_withholding_ge_70pct": False,
                    "art109_activity_income_withholding_ge_70pct": False,
                    "pays_rent_with_retencion": False,
                    "does_intracomunitario": False,
                    "third_party_transactions_above_347_threshold": False,
                    "bienes_extranjero_above_threshold": False,
                },
            )

    def test_iva_regime_must_be_known(self) -> None:
        with pytest.raises(ValidationError, match=r"IVARegime"):
            TaxpayerProfile.model_validate(
                {
                    "tax_id": "X",
                    "iva_regime": "WHATEVER",
                    "has_employees": False,
                    "pays_professionals_with_retencion": False,
                    "professional_income_withholding_ge_70pct": False,
                    "art109_activity_income_withholding_ge_70pct": False,
                    "pays_rent_with_retencion": False,
                    "does_intracomunitario": False,
                    "third_party_transactions_above_347_threshold": False,
                    "bienes_extranjero_above_threshold": False,
                },
            )

    def test_modelo_iva_profile_requires_explicit_redeme_authority(self) -> None:
        with pytest.raises(ValidationError, match="redeme_enrolled"):
            ModeloIVAProfile.model_validate(
                {
                    "tax_territory": M303TaxTerritory.COMMON_REGIME,
                    "regime_composition": M303RegimeComposition.GENERAL,
                    "cash_accounting_regime_enrolled": False,
                    "voluntary_sii_enrolled": False,
                    "hydrocarbon_deposit_advance_payment_deduction_entitled": False,
                },
            )

    def test_mapping_projection_preserves_enrollment_and_schedule_facts(self) -> None:
        profile = taxpayer_profile_from_mapping(
            {
                "tax.id": "12345678Z",
                "activity": "design",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "SIMPLIFICADO",
                "iva.m303_regime_composition": "simplified",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
                "has_employees": "true",
                "art109_activity_income_withholding_ge_70pct": "true",
                "pays_rent_with_retencion": "true",
                "does_intracomunitario": "true",
                "iva.roi_enrolled": "true",
                "iva.oss_enrolled": "false",
                "iva.group_member_enrolled": "true",
                "iva.group_dominant_entity_enrolled": "true",
                "iva.intracommunity_operations_exceed_50000_eur": "true",
                "enrollment.large_company": "true",
                "enrollment.public_administration_budget_gt_6000000": "false",
            },
            tax_id_default="00000000T",
        )

        assert profile.tax_id == "12345678Z"
        assert profile.iva_regime is IVARegime.SIMPLIFICADO
        assert profile.has_employees is True
        assert profile.art109_activity_income_withholding_ge_70pct is True
        assert profile.pays_rent_with_retencion is True
        assert profile.does_intracomunitario is True
        assert profile.iva == ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.SIMPLIFIED,
            roi_enrolled=True,
            oss_enrolled=False,
            group_member_enrolled=True,
            group_dominant_entity_enrolled=True,
            intracommunity_operations_exceed_50000_eur=True,
            redeme_enrolled=False,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        )
        assert profile.enrollment == ModeloEnrollment(large_company=True)

    def test_mapping_projection_reads_pagadores_axes(self) -> None:
        # The three Art. 96 LIRPF pagadores axes flow from the canonical mapping
        # into the typed profile, including the total-work-income leg.
        profile = taxpayer_profile_from_mapping(
            {
                "tax.id": "12345678Z",
                "irpf.pagadores_count": "2",
                "irpf.pagadores_secondary_income": "1600",
                "irpf.pagadores_total_work_income": "18000",
            },
            tax_id_default="00000000T",
        )

        assert profile.irpf_pagadores_count == 2
        assert profile.irpf_pagadores_secondary_income == Decimal("1600")
        assert profile.irpf_pagadores_total_work_income == Decimal("18000")


class TestModeloDeadline:
    """Window-order and field invariants for :class:`ModeloDeadline`."""

    def test_opens_after_closes_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"opens_on .* is after closes_on"):
            ModeloDeadline(
                modelo="303",
                period=_P_2026_1T,
                opens_on=date(2026, 4, 21),
                closes_on=date(2026, 4, 20),
                payment_cutoff_on=None,
                status=ObligationStatus.UPCOMING,
                applies_because="x",
            )

    def test_payment_after_closes_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"payment_cutoff_on .* is after closes_on"):
            ModeloDeadline(
                modelo="303",
                period=_P_2026_1T,
                opens_on=date(2026, 4, 1),
                closes_on=date(2026, 4, 20),
                payment_cutoff_on=date(2026, 4, 25),
                status=ObligationStatus.UPCOMING,
                applies_because="x",
            )


class TestScheduleRoundTrip:
    """Pydantic v2 JSON round-trip preserves the full schedule shape."""

    def test_round_trip_equality(self) -> None:
        obligation = ModeloDeadline(
            modelo="303",
            period=_P_2026_1T,
            opens_on=date(2026, 4, 1),
            closes_on=date(2026, 4, 20),
            payment_cutoff_on=date(2026, 4, 15),
            status=ObligationStatus.UPCOMING,
            applies_because="Régimen general de IVA.",
            boe_references=("BOE-Orden-IVA-autoliquidacion",),
        )
        schedule = Schedule(
            profile=_profile(),
            year=2026,
            obligations=(obligation,),
            generated_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        payload = schedule.model_dump_json()
        restored = Schedule.model_validate_json(payload)
        assert restored == schedule
