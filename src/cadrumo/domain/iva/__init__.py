"""IVA: rates, regimes, classification and the cuota rules that follow from them.

Inert namespace. Every contract is reached at its own defining module:
``catalogue``, ``classification``, ``components``, ``corpus``, ``deduction_facts``,
``errors``, ``establishment``, ``flow``, ``identification``, ``invoice_classification``,
``legend_derivation``, ``lookup``, ``m303_settlement``, ``oss``, ``place_of_supply``,
``prorrata``, ``rates``, ``recargo_equivalencia``, ``refund_eligibility``,
``regime_legend``, ``regimen_simplificado_rows``, ``saturation``, ``schema``,
``sepa_marca``, ``supply_nature``, ``verify``.

This package re-exported its surface through the namespace. The map is
retired: a consumer names the module that defines what it imports.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
