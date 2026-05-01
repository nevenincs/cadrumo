"""Unit tests for the Modelo 100 tarifa progresiva post-validator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._tarifa import (
    _TARIFA_ESTATAL_AHORRO_2025,
    _TARIFA_ESTATAL_GENERAL_2025,
    apply_tarifa,
    validate_tarifa_estatal,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_inbound]


class TestApplyTarifa:
    @pytest.mark.parametrize(
        ("base", "expected_state_general"),
        [
            # Zero base → zero cuota.
            ("0.00", "0.00"),
            # Single-bracket (entirely in 9.5% band): 10000 x 0.095 = 950.
            ("10000.00", "950.00"),
            # Two-bracket crossing: 12450 x 0.095 + 2550 x 0.12 = 1182.75 + 306.
            ("15000.00", "1488.75"),
            # Three-bracket crossing: + 4800 x 0.15 = 2832.75.
            ("25000.00", "2832.75"),
            # Top-band entry (400 000): 1182.75 + 930 + 2250 + 4588 + 54000 + 24500.
            ("400000.00", "87450.75"),
        ],
    )
    def test_state_general_scale(self, base: str, expected_state_general: str) -> None:
        result = apply_tarifa(Decimal(base), _TARIFA_ESTATAL_GENERAL_2025)
        assert result == Decimal(expected_state_general)

    def test_savings_scale_first_bracket(self) -> None:
        # 5 000 entirely in the 9.5% band.
        assert apply_tarifa(Decimal("5000.00"), _TARIFA_ESTATAL_AHORRO_2025) == Decimal("475.00")

    def test_negative_base_clamps_to_zero(self) -> None:
        assert apply_tarifa(Decimal("-100.00"), _TARIFA_ESTATAL_GENERAL_2025) == Decimal("0.00")


class TestValidateTarifaEstatal2025:
    def test_no_findings_when_cuota_matches_tarifa(self) -> None:
        findings = validate_tarifa_estatal(
            ejercicio="2025",
            base_liquidable_general=Decimal("15000.00"),
            base_liquidable_ahorro=Decimal("1000.00"),
            cuota_estatal_general=Decimal("1488.75"),
            cuota_estatal_ahorro=Decimal("95.00"),
        )
        assert findings == ()

    def test_discrepancy_when_general_cuota_diverges(self) -> None:
        findings = validate_tarifa_estatal(
            ejercicio="2025",
            base_liquidable_general=Decimal("15000.00"),
            base_liquidable_ahorro=None,
            cuota_estatal_general=Decimal("9999.99"),
            cuota_estatal_ahorro=None,
        )
        assert len(findings) == 1
        assert findings[0].casilla_id == "0550"
        assert findings[0].base_casilla_id == "0545"
        assert findings[0].expected_cuota == Decimal("1488.75")
        assert findings[0].actual_cuota == Decimal("9999.99")

    def test_missing_base_skips_check(self) -> None:
        findings = validate_tarifa_estatal(
            ejercicio="2025",
            base_liquidable_general=None,
            base_liquidable_ahorro=None,
            cuota_estatal_general=Decimal("999.99"),
            cuota_estatal_ahorro=None,
        )
        assert findings == ()

    def test_tolerance_accepts_rounding_drift(self) -> None:
        findings = validate_tarifa_estatal(
            ejercicio="2025",
            base_liquidable_general=Decimal("15000.00"),
            base_liquidable_ahorro=None,
            cuota_estatal_general=Decimal("1488.76"),  # +0.01 rounding
            cuota_estatal_ahorro=None,
        )
        assert findings == ()

    def test_unknown_ejercicio_raises(self) -> None:
        with pytest.raises(ValueError, match="tarifa progresiva estatal"):
            validate_tarifa_estatal(
                ejercicio="2027",
                base_liquidable_general=Decimal("15000.00"),
                base_liquidable_ahorro=None,
                cuota_estatal_general=Decimal("1488.75"),
                cuota_estatal_ahorro=None,
            )

    def test_ejercicio_2024_uses_same_state_scale(self) -> None:
        # Art. 63/66 brackets unchanged 2024 → 2025; 2024 validates identically.
        findings = validate_tarifa_estatal(
            ejercicio="2024",
            base_liquidable_general=Decimal("15000.00"),
            base_liquidable_ahorro=None,
            cuota_estatal_general=Decimal("1488.75"),
            cuota_estatal_ahorro=None,
        )
        assert findings == ()
