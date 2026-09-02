"""Shared selector primitives for ledger aggregation binding families."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from ....core.casilla_id import CasillaId, validated_casilla_id


def mapping_lacks_fact(value: object) -> bool:
    """Whether *value* is a mapping with no ``fact`` key."""
    return isinstance(value, Mapping) and "fact" not in value


def casilla_id_set(surface: str, *values: object) -> frozenset[CasillaId]:
    """Validate a closed family of registry casilla identifiers."""
    return frozenset(validated_casilla_id(value, surface=surface) for value in values)


class LedgerIncomeFact(StrEnum):
    """A figure a ledger-income binding can total out of matched rows."""

    INGRESOS_INTEGROS_SUM = "ingresos_integros_sum"
    CASH_RECEIVED_SUM = "cash_received_sum"
    TAXABLE_BASE_SUM = "taxable_base_sum"
    WITHHELD_AMOUNT_SUM = "withheld_amount_sum"


LedgerIncomeFactValue = Literal[
    LedgerIncomeFact.INGRESOS_INTEGROS_SUM,
    LedgerIncomeFact.CASH_RECEIVED_SUM,
    LedgerIncomeFact.TAXABLE_BASE_SUM,
    LedgerIncomeFact.WITHHELD_AMOUNT_SUM,
]
"""Every income fact, for a selector that can total any of them."""

ImpatriadoLedgerIncomeFact = Literal[
    LedgerIncomeFact.INGRESOS_INTEGROS_SUM,
    LedgerIncomeFact.CASH_RECEIVED_SUM,
]
"""The income facts the impatriado regime's bindings actually total.

A genuine narrowing, not a separate vocabulary: the two tokens mean exactly what they
mean for renta income, and the impatriado selector simply has no binding that needs a
taxable base or a withheld amount. Rooted here rather than spelled out in its own
module, where the pair looked unrelated to the four it is drawn from.
"""


class LedgerIvaFact(StrEnum):
    """A figure an IVA ledger binding can total out of matched rows."""

    IVA_AMOUNT_SUM = "iva_amount_sum"
    BASE_AMOUNT_SUM = "base_amount_sum"
    RECARGO_AMOUNT_SUM = "recargo_amount_sum"


LedgerIvaFactValue = Literal[
    LedgerIvaFact.IVA_AMOUNT_SUM,
    LedgerIvaFact.BASE_AMOUNT_SUM,
    LedgerIvaFact.RECARGO_AMOUNT_SUM,
]
"""Every IVA fact, for a selector that can total any of them."""

OssIossLedgerFact = Literal[
    LedgerIvaFact.IVA_AMOUNT_SUM,
    LedgerIvaFact.BASE_AMOUNT_SUM,
]
"""The IVA facts an OSS/IOSS binding totals.

Narrower because recargo de equivalencia does not arise in the one-stop-shop regimes,
so a recargo total is not merely unused there -- it is not a thing that exists.
"""
