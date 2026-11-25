"""Closed value set for the rental expense concept a ledger row carries.

A row that pays for a property let out is routed to a Modelo 100 casilla by the
kind of expense it is, and no amount, category or counterparty on the row says
which kind. The concept is therefore declared on the row.
"""

from __future__ import annotations

from .registry_token import StrictRegistryToken

__all__ = ["GastoCapitalInmobiliario"]


class GastoCapitalInmobiliario(StrictRegistryToken):
    """Opaque rental-expense concept token projected from the governed facts registry.

    The dated facts catalogue owns the vocabulary and the casilla each concept
    feeds. This core type carries only the typed wire token; callers must obtain
    instances through the registry projection.
    """

    __slots__ = ()
