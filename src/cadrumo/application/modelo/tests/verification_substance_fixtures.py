"""Application-owned fixtures for pure verification-predicate tests."""

from __future__ import annotations

from decimal import Decimal

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile

CASILLA_01: CasillaId = validated_casilla_id("01")
CASILLA_02: CasillaId = validated_casilla_id("02")
_CASILLA_03: CasillaId = validated_casilla_id("03")
_CASILLA_05: CasillaId = validated_casilla_id("05")
CASILLA_06: CasillaId = validated_casilla_id("06")
CASILLA_07: CasillaId = validated_casilla_id("07")
_CASILLA_08: CasillaId = validated_casilla_id("08")
CASILLA_09: CasillaId = validated_casilla_id("09")
CASILLA_10: CasillaId = validated_casilla_id("10")
CASILLA_11: CasillaId = validated_casilla_id("11")
_CASILLA_12: CasillaId = validated_casilla_id("12")
CASILLA_14: CasillaId = validated_casilla_id("14")
CASILLA_15: CasillaId = validated_casilla_id("15")
_CASILLA_16: CasillaId = validated_casilla_id("16")
_CASILLA_18: CasillaId = validated_casilla_id("18")
CASILLA_00501: CasillaId = validated_casilla_id("DP200012:00501")
_ABSENT_REGISTRY_CASILLA: CasillaId = validated_casilla_id("99")
M200_BIN_OPEN_CASILLA: CasillaId = validated_casilla_id("00670")
M200_BIN_CLOSING_CASILLA: CasillaId = validated_casilla_id("00671")
M200_BIN_APPLIED_CASILLA: CasillaId = validated_casilla_id("DP200014:00547")
M200_BIN_GENERATED_CASILLA: CasillaId = validated_casilla_id("DP200014:00552")


def verification_substance_casilla_values(*entries: tuple[CasillaId, str]) -> dict[CasillaId, Decimal]:
    return {casilla_id: Decimal(value) for casilla_id, value in entries}


def workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X0001500M",
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
