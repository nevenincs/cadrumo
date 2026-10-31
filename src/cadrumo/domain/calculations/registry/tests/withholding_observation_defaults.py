"""The incapacity and foral-retention amounts a withholding observation carries when a test exercises neither."""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType
from typing import Final

ZERO_INCAPACITY_AND_FORAL_FIELDS: Final = MappingProxyType(
    {
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
    },
)
