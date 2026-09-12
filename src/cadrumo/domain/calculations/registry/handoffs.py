"""Declared consumption channels for cross-model relation-prefill handoffs.

A handoff is a coordinate in the registry: the source and target
:class:`ModeloRevision` a value crosses between, resolved against the
:class:`RegistrySnapshot` the authority compiled. This module names the closed
set of channels through which a folded value reaches the casilla that consumes
it, so "which model feeds which, and how" is a declared fact rather than one
re-derived per caller.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, NamedTuple

from .ids import BindingId
from .runtime_graph import expression_binding_refs
from .schema import ModeloRevision

__all__ = [
    "RelationConsumptionChannel",
    "RelationConsumptionChannelKind",
    "relation_consumption_channels",
    "relation_consumption_index",
]


class RelationConsumptionChannelKind(StrEnum):
    """How a relation-prefill binding's value reaches the target that consumes it."""

    PRIMARY_BINDING = "primary_binding"
    ALTERNATE_BINDING = "alternate_binding"
    FORMULA_BINDING = "formula_binding"


RelationConsumptionChannel = Literal[
    RelationConsumptionChannelKind.PRIMARY_BINDING,
    RelationConsumptionChannelKind.ALTERNATE_BINDING,
    RelationConsumptionChannelKind.FORMULA_BINDING,
]
"""Canonical closed channels through which a folded value feeds a casilla."""


class _RelationConsumptionIndex(NamedTuple):
    primary_bindings: frozenset[BindingId]
    alternate_bindings: frozenset[BindingId]
    formula_bindings: frozenset[BindingId]


def relation_consumption_index(revision: ModeloRevision) -> _RelationConsumptionIndex:
    """Return the binding channels that consume relation-prefill values."""
    primary_bindings: set[BindingId] = set()
    alternate_bindings: set[BindingId] = set()
    for casilla in revision.casillas:
        if casilla.binding is not None:
            primary_bindings.add(casilla.binding)
        alternate_bindings.update(casilla.alternate_bindings)

    formula_bindings: set[BindingId] = set()
    for formula in revision.formulas:
        formula_bindings.update(expression_binding_refs(formula.expression))
    return _RelationConsumptionIndex(
        primary_bindings=frozenset(primary_bindings),
        alternate_bindings=frozenset(alternate_bindings),
        formula_bindings=frozenset(formula_bindings),
    )


def relation_consumption_channels(
    binding_id: BindingId,
    index: _RelationConsumptionIndex,
) -> tuple[RelationConsumptionChannel, ...]:
    """Return every declared channel that consumes ``binding_id`` in stable order.

    An empty result means the binding is declared but nothing reads it, which
    is the orphan condition consumers report rather than tolerate.
    """
    channels: list[RelationConsumptionChannel] = []
    if binding_id in index.primary_bindings:
        channels.append(RelationConsumptionChannelKind.PRIMARY_BINDING)
    if binding_id in index.alternate_bindings:
        channels.append(RelationConsumptionChannelKind.ALTERNATE_BINDING)
    if binding_id in index.formula_bindings:
        channels.append(RelationConsumptionChannelKind.FORMULA_BINDING)
    return tuple(channels)
