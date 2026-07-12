"""Typed-id alias re-export for ledger transaction records.

The ``TransactionId`` constraint shape lives in :mod:`aeat.core.identity`
because the alias is consumed by code in a sibling domain
(:mod:`aeat.domain.invoices`) in addition to the owning transaction
domain, the application ledger service, and the persistence adapters.
This module re-exports the alias under its canonical owner-domain
location so transaction-package call sites can continue to import
``TransactionId`` from the domain they expect to own it without
re-routing through ``aeat.core.identity`` at every consumer site.
"""

from __future__ import annotations

from ...core.identity import TransactionId

__all__ = ("TransactionId",)
