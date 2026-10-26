"""Opaque descendant-relationship tokens projected from the facts authority."""

from __future__ import annotations

from .registry_token import StrictRegistryToken


class DescendantRelacion(StrictRegistryToken):
    """Registry-projected relationship token carried by a descendant record.

    Membership, default meaning, and Art. 58.2 entitlement are governed by
    fact ``lirpf-art-81-maternity-descendant-relations``. This type retains
    only the opaque token shape and cannot mint an unprojected value.
    """

    __slots__ = ()


__all__ = ["DescendantRelacion"]
