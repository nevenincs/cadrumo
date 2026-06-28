"""Persistence adapters for profile-scoped asset and inventory ledgers.

Namespace package whose children hold the concrete persistence adapters
for the ledger records a taxpayer profile owns beyond its core identity.
It exposes no symbols of its own; consume the child modules directly:
:mod:`aeat.adapters.persistence.profile.assets` (the actividad-económica
amortización asset ledger) and
:mod:`aeat.adapters.persistence.profile.inventory` (stock-valuation
ledgers).
"""

__all__: list[str] = []
