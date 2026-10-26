"""Opaque capital-goods vocabulary tokens projected from fact 0130.

The token classes intentionally carry no local membership list.  Membership,
descriptions, legal scope, and the acquisition-year floor are selected by the
dated LIVA capital-goods fact at the registry boundary.
"""

from __future__ import annotations

from ...core.registry_token import StrictRegistryToken


class BienInversionKind(StrictRegistryToken):
    """Opaque LIVA capital-goods kind token projected from fact 0130."""

    __slots__ = ()


class BienInversionDisposalRegime(StrictRegistryToken):
    """Opaque LIVA disposal-regime token projected from fact 0130."""

    __slots__ = ()


__all__ = ["BienInversionDisposalRegime", "BienInversionKind"]
