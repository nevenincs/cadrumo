"""Zero-valued incapacity and foral fields a withholding observation requires."""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict


class ZeroedWithholdingBlocks(TypedDict):
    incapacity_cash_perception: Decimal
    incapacity_cash_withholding: Decimal
    incapacity_kind_value: Decimal
    incapacity_kind_ingreso_a_cuenta: Decimal
    incapacity_kind_repercutido: Decimal
    foral_retention_estatal: Decimal
    foral_retention_navarra: Decimal
    foral_retention_araba: Decimal
    foral_retention_gipuzkoa: Decimal
    foral_retention_bizkaia: Decimal


def zeroed_withholding_blocks() -> ZeroedWithholdingBlocks:
    zero = Decimal("0")
    return ZeroedWithholdingBlocks(
        incapacity_cash_perception=zero,
        incapacity_cash_withholding=zero,
        incapacity_kind_value=zero,
        incapacity_kind_ingreso_a_cuenta=zero,
        incapacity_kind_repercutido=zero,
        foral_retention_estatal=zero,
        foral_retention_navarra=zero,
        foral_retention_araba=zero,
        foral_retention_gipuzkoa=zero,
        foral_retention_bizkaia=zero,
    )
