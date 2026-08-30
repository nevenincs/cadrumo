"""Fincas: property records, cadastral references and their derived facts.

Inert namespace. Every contract is reached at its own defining module:
``aggregates``, ``amortization_ledger``, ``enums``, ``errors``, ``expense_rollup``,
``imputacion_parameters``, ``models``, ``repository_ports``, ``source_readiness``,
``tier_resolver``.

This package re-exported its whole surface through the namespace. The map
is retired: a consumer names the module that defines what it imports.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
