"""Canonical target relationships for registry data bindings.

Binding declarations name the factual source that can populate a casilla.
This module owns both directions of that relationship so registry consumers do
not reconstruct the ``BOUND`` predicate independently.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.casilla_id import CasillaId
from .errors import RegistryValidationError
from .ids import BindingId
from .schema import ModeloRevision
from .schema_input_kind import InputKind
from .schema_surfaces import CasillaDefinition

__all__ = ["bound_casilla_binding_ids", "casillas_by_binding"]


def bound_casilla_binding_ids(casilla: CasillaDefinition) -> tuple[BindingId, ...]:
    """Return primary plus reviewed equivalent bindings for one bound casilla."""
    if casilla.input_kind != InputKind.BOUND:
        return ()
    if casilla.binding is None:
        raise RegistryValidationError(f"bound casilla {casilla.id!r} has no binding")
    return (casilla.binding, *casilla.alternate_bindings)


def casillas_by_binding(revision: ModeloRevision) -> Mapping[BindingId, tuple[CasillaId, ...]]:
    """Return every binding id mapped to its declaration-ordered target casillas."""
    mapping: dict[BindingId, list[CasillaId]] = {}
    for casilla in revision.casillas:
        for binding_id in bound_casilla_binding_ids(casilla):
            populated_by = mapping.setdefault(binding_id, [])
            if casilla.id not in populated_by:
                populated_by.append(casilla.id)
    return {binding_id: tuple(casilla_ids) for binding_id, casilla_ids in mapping.items()}
