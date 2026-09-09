"""Typed inventory of canonical cross-model relation handoffs.

A handoff is a coordinate in the registry: the source and target
:class:`ModeloRevision` a value crosses between, resolved against the
:class:`RegistrySnapshot` the authority compiled. The inventory is what makes
"which model feeds which" a declared fact rather than one re-derived per caller.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, NamedTuple

from pydantic import BaseModel, Field, model_validator

from ....core.aggregation import BindingSourceKind, RelationAggregationOp
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import RegistryValidationError
from .ids import BindingId, LegalRefId, ModeloId, RelationId, RevisionId, SourceRefId
from .relation_dependency import (
    RelationDependencyRoleField,
    RelationKindField,
)
from .runtime_graph import expression_binding_refs, expression_relation_refs
from .schema import (
    ModeloRevision,
)
from .schema_surfaces import RelationDefinition, RelationPeriodAlignment, RelationRevisionSelector

__all__ = [
    "RelationConsumptionChannel",
    "RelationHandoffRecord",
    "relation_consumption_channels",
    "relation_consumption_index",
]


class RelationConsumptionChannelKind(StrEnum):
    """How a relation's value reaches the target that consumes it."""

    PRIMARY_BINDING = "primary_binding"
    ALTERNATE_BINDING = "alternate_binding"
    FORMULA_RELATION = "formula_relation"
    FORMULA_BINDING = "formula_binding"


RelationConsumptionChannel = Literal[
    RelationConsumptionChannelKind.PRIMARY_BINDING,
    RelationConsumptionChannelKind.ALTERNATE_BINDING,
    RelationConsumptionChannelKind.FORMULA_RELATION,
    RelationConsumptionChannelKind.FORMULA_BINDING,
]
"""The channels as a strict record field."""


"""The same applicability as a strict record field."""


"""The same mode as a strict record field."""


"""The same classification as a strict record field."""


"""The same owner as a strict record field."""
"""Canonical closed channels through which a relation feeds a casilla."""


class _RelationConsumptionIndex(NamedTuple):
    primary_bindings: frozenset[BindingId]
    alternate_bindings: frozenset[BindingId]
    formula_relations: frozenset[RelationId]
    formula_bindings: frozenset[BindingId]


def relation_consumption_index(revision: ModeloRevision) -> _RelationConsumptionIndex:
    """Return the binding and formula channels that consume relation values."""
    primary_bindings: set[BindingId] = set()
    alternate_bindings: set[BindingId] = set()
    for casilla in revision.casillas:
        if casilla.binding is not None:
            primary_bindings.add(casilla.binding)
        alternate_bindings.update(casilla.alternate_bindings)

    formula_relations: set[RelationId] = set()
    formula_bindings: set[BindingId] = set()
    for formula in revision.formulas:
        formula_relations.update(expression_relation_refs(formula.expression))
        formula_bindings.update(expression_binding_refs(formula.expression))
    return _RelationConsumptionIndex(
        primary_bindings=frozenset(primary_bindings),
        alternate_bindings=frozenset(alternate_bindings),
        formula_relations=frozenset(formula_relations),
        formula_bindings=frozenset(formula_bindings),
    )


def relation_consumption_channels(
    relation: RelationDefinition,
    index: _RelationConsumptionIndex,
) -> tuple[RelationConsumptionChannel, ...]:
    """Return every declared channel that consumes ``relation`` in stable order."""
    channels: list[RelationConsumptionChannel] = []
    if relation.target_binding in index.primary_bindings:
        channels.append(RelationConsumptionChannelKind.PRIMARY_BINDING)
    if relation.target_binding in index.alternate_bindings:
        channels.append(RelationConsumptionChannelKind.ALTERNATE_BINDING)
    if relation.id in index.formula_relations:
        channels.append(RelationConsumptionChannelKind.FORMULA_RELATION)
    if relation.target_binding in index.formula_bindings:
        channels.append(RelationConsumptionChannelKind.FORMULA_BINDING)
    return tuple(channels)


class RelationHandoffRecord(BaseModel):
    """One validated relation handoff with source, target, period, and provenance axes."""

    model_config = STRICT_FROZEN_CONFIG

    target_modelo: ModeloId
    target_revision: RevisionId
    relation_id: RelationId
    relation_kind: RelationKindField
    dependency_role: RelationDependencyRoleField
    source_modelo: ModeloId
    source_revision_selector: RelationRevisionSelector
    source_casilla_id: CasillaId
    target_binding: BindingId
    target_binding_source: BindingSourceKind | None
    target_casilla_ids: tuple[CasillaId, ...]
    consumption_channels: tuple[RelationConsumptionChannel, ...]
    period_alignment: RelationPeriodAlignment
    source_periods: tuple[str, ...]
    target_periods: tuple[str, ...]
    source_period_offset_from_target: int | None
    aggregation_op: RelationAggregationOp
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    target_binding_legal_refs: tuple[LegalRefId, ...] = ()
    target_binding_source_refs: tuple[SourceRefId, ...] = ()

    @model_validator(mode="after")
    def _target_casilla_ids_are_unique(self) -> RelationHandoffRecord:
        if len(self.target_casilla_ids) != len(set(self.target_casilla_ids)):
            raise RegistryValidationError(
                f"relation handoff {self.relation_id!r} repeats a target casilla identity",
            )
        return self
