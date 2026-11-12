"""Closed value set for the capital-mobiliario concept a ledger row carries.

A row linked to a savings position is routed to a Modelo 100 detail record by
the kind of income or expense it is, and no amount, category or counterparty on
the row says which kind. The concept is therefore declared on the row.
"""

from __future__ import annotations

from .registry_token import StrictRegistryToken

__all__ = ["ConceptoCapitalMobiliario"]


class ConceptoCapitalMobiliario(StrictRegistryToken):
    """Opaque capital-mobiliario concept token projected from the governed facts registry.

    The dated facts catalogue owns the vocabulary and the detail record each
    concept feeds. This core type carries only the typed wire token; callers
    must obtain instances through the registry projection.
    """

    __slots__ = ()
