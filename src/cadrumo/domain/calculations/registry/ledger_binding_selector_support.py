"""Shared selector primitives for ledger aggregation binding families."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Literal, get_args

from ....core.casilla_id import CasillaId, validated_casilla_id


def mapping_lacks_fact(value: object) -> bool:
    """Whether *value* is a mapping with no ``fact`` key."""
    return isinstance(value, Mapping) and "fact" not in value


def literal_fact_values(fact_type: object) -> frozenset[str]:
    """Return the string tokens of a closed ``Literal`` fact vocabulary."""
    return frozenset(str(fact) for fact in get_args(fact_type))


def casilla_id_set(surface: str, *values: object) -> frozenset[CasillaId]:
    """Validate a closed family of registry casilla identifiers."""
    return frozenset(validated_casilla_id(value, surface=surface) for value in values)


class LedgerIncomeFact(StrEnum):
    """A figure a ledger-income binding can total out of matched rows."""

    INGRESOS_INTEGROS_SUM = "ingresos_integros_sum"
    CASH_RECEIVED_SUM = "cash_received_sum"
    TAXABLE_BASE_SUM = "taxable_base_sum"
    DECLARED_WITHHELD_AMOUNT_SUM = "declared_withheld_amount_sum"
    """Totals only the retención a linked sales invoice itself declares.

    A ledger row never records a retención, so every other figure on that
    surface is reconstructed from invoice gross minus cash received. A
    reconstruction is not a recorded fact, and a credit against the cuota rests
    on one, so this fact reads the declared figure alone. The rows it leaves out
    stay visible through their derivation marker rather than becoming zeroes.
    """


LedgerIncomeFactValue = Literal[
    LedgerIncomeFact.INGRESOS_INTEGROS_SUM,
    LedgerIncomeFact.CASH_RECEIVED_SUM,
    LedgerIncomeFact.TAXABLE_BASE_SUM,
    LedgerIncomeFact.DECLARED_WITHHELD_AMOUNT_SUM,
]
"""Every income fact, for a selector that can total any of them."""

LEDGER_INCOME_FACTS: frozenset[str] = literal_fact_values(LedgerIncomeFactValue)

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

IMPATRIADO_LEDGER_INCOME_FACTS: frozenset[str] = literal_fact_values(ImpatriadoLedgerIncomeFact)


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

LEDGER_IVA_FACTS: frozenset[str] = literal_fact_values(LedgerIvaFactValue)

OssIossLedgerFact = Literal[
    LedgerIvaFact.IVA_AMOUNT_SUM,
    LedgerIvaFact.BASE_AMOUNT_SUM,
]
"""The IVA facts an OSS/IOSS binding totals.

Narrower because recargo de equivalencia does not arise in the one-stop-shop regimes,
so a recargo total is not merely unused there -- it is not a thing that exists.
"""

OSS_IOSS_LEDGER_FACTS: frozenset[str] = literal_fact_values(OssIossLedgerFact)
