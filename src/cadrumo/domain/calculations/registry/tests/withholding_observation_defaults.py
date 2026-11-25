"""Neutral incapacity and foral-retention inputs for withholding tests."""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict


class ZeroIncapacityAndForalFields(TypedDict):
    """The exact observation fields supplied when neither case is exercised."""

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
    base_retenciones: Decimal


def zero_incapacity_and_foral_fields() -> ZeroIncapacityAndForalFields:
    """Return fresh zero values with the observation's exact keyword shape."""
    return {
        "incapacity_cash_perception": Decimal("0"),
        "incapacity_cash_withholding": Decimal("0"),
        "incapacity_kind_value": Decimal("0"),
        "incapacity_kind_ingreso_a_cuenta": Decimal("0"),
        "incapacity_kind_repercutido": Decimal("0"),
        "foral_retention_estatal": Decimal("0"),
        "foral_retention_navarra": Decimal("0"),
        "foral_retention_araba": Decimal("0"),
        "foral_retention_gipuzkoa": Decimal("0"),
        "foral_retention_bizkaia": Decimal("0"),
        "base_retenciones": Decimal("0"),
    }
