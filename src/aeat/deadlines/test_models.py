"""Unit tests for the strict pydantic v2 models in :mod:`aeat.deadlines._models`."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from . import (
    AutonomoProfile,
    FilingObligation,
    IVARegime,
    ObligationStatus,
    Schedule,
)

pytestmark = pytest.mark.unit


def _profile() -> AutonomoProfile:
    return AutonomoProfile(
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


class TestAutonomoProfile:
    """Strictness invariants for :class:`AutonomoProfile`."""

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AutonomoProfile.model_validate(
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
                }
            )

    def test_frozen(self) -> None:
        profile = _profile()
        with pytest.raises(ValidationError):
            profile.tax_id = "Y9876543K"  # type: ignore[misc]

    def test_strict_rejects_int_for_bool(self) -> None:
        with pytest.raises(ValidationError):
            AutonomoProfile.model_validate(
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
                }
            )

    def test_iva_regime_must_be_known(self) -> None:
        with pytest.raises(ValidationError):
            AutonomoProfile.model_validate(
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
                }
            )


class TestFilingObligation:
    """Window-order and field invariants for :class:`FilingObligation`."""

    def test_opens_after_closes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilingObligation(
                modelo="303",
                period="2026Q1",
                opens_on=date(2026, 4, 21),
                closes_on=date(2026, 4, 20),
                payment_cutoff_on=None,
                status=ObligationStatus.UPCOMING,
                applies_because="x",
            )

    def test_payment_after_closes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilingObligation(
                modelo="303",
                period="2026Q1",
                opens_on=date(2026, 4, 1),
                closes_on=date(2026, 4, 20),
                payment_cutoff_on=date(2026, 4, 25),
                status=ObligationStatus.UPCOMING,
                applies_because="x",
            )


class TestScheduleRoundTrip:
    """Pydantic v2 JSON round-trip preserves the full schedule shape."""

    def test_round_trip_equality(self) -> None:
        obligation = FilingObligation(
            modelo="303",
            period="2026Q1",
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
