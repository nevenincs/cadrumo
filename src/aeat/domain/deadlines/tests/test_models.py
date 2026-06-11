"""Unit tests for the strict pydantic v2 models in :mod:`aeat.domain.deadlines._models`.

Verifies the strictness invariants of
:class:`aeat.domain.deadlines.TaxpayerProfile` (extra fields,
immutability, strict bool/enum coercion), the date-ordering
invariants of :class:`aeat.domain.deadlines.ModeloDeadline`, and
that :class:`aeat.domain.deadlines.Schedule` survives a JSON round
trip.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from ....core import Period
from .. import (
    IVARegime,
    ModeloDeadline,
    ModeloEnrollment,
    ModeloIVAProfile,
    ObligationStatus,
    Schedule,
    TaxpayerProfile,
    taxpayer_profile_from_mapping,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_P_2026_1T = Period.from_year_and_code(2026, "1T")


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=True,
        pays_professionals_with_retencion=False,
        professional_income_withholding_ge_70pct=False,
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
                    "pays_rent_with_retencion": False,
                    "does_intracomunitario": False,
                    "third_party_transactions_above_347_threshold": False,
                    "bienes_extranjero_above_threshold": False,
                },
            )

    def test_mapping_projection_preserves_enrollment_and_schedule_facts(self) -> None:
        profile = taxpayer_profile_from_mapping(
            {
                "tax.id": "12345678Z",
                "activity": "design",
                "iva.regime": "SIMPLIFICADO",
                "has_employees": "true",
                "pays_rent_with_retencion": "true",
                "does_intracomunitario": "true",
                "iva.roi_enrolled": "true",
                "iva.oss_enrolled": "false",
                "iva.intracommunity_operations_exceed_50000_eur": "true",
                "enrollment.large_company": "true",
                "enrollment.public_administration_budget_gt_6000000": "false",
            },
            tax_id_default="00000000T",
        )

        assert profile.tax_id == "12345678Z"
        assert profile.iva_regime is IVARegime.SIMPLIFICADO
        assert profile.has_employees is True
        assert profile.pays_rent_with_retencion is True
        assert profile.does_intracomunitario is True
        assert profile.iva == ModeloIVAProfile(
            roi_enrolled=True,
            oss_enrolled=False,
            intracommunity_operations_exceed_50000_eur=True,
        )
        assert profile.enrollment == ModeloEnrollment(large_company=True)


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
