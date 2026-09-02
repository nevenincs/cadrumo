"""Shared selector primitives for ledger aggregation binding families."""

from __future__ import annotations

from collections.abc import Mapping

from ....core.casilla_id import CasillaId, validated_casilla_id


def mapping_lacks_fact(value: object) -> bool:
    """Whether *value* is a mapping with no ``fact`` key."""
    return isinstance(value, Mapping) and "fact" not in value


def casilla_id_set(surface: str, *values: object) -> frozenset[CasillaId]:
    """Validate a closed family of registry casilla identifiers."""
    return frozenset(validated_casilla_id(value, surface=surface) for value in values)
