"""Inventory ledgers for actividad economica stock valuation.

Defines strict pydantic v2 records for tracking opening stock,
period movements (purchases, COGS, counts), and closing stock per
activity / year, plus the FIFO and weighted-average (PMP / coste
medio) valuation engines required by LIS art. 17.1. LIFO is rejected
explicitly via :class:`LIFOForbiddenError`.

Public functions:
    :func:`parse_valuation_method` — coerce user input into a
    :class:`ValuationMethod`, refusing LIFO.
    :func:`compute_inventory_valuation` — value closing stock and
    COGS for one ledger.
    :func:`compute_inventory_anexo_d_projection` — project complete 2025
    acquisition cost and stock variation to ``0181``, ``0177``, and ``0182``.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
