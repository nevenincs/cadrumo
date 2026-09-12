"""The relation-prefill provider: one cross-filing fold declared in one place.

A ``relation_prefill`` binding folds values filed on another modelo -- or on an
earlier period of this one -- into a form slot of the target filing. The
declaration carries every axis of that fold: which modelo and casilla are read,
what kind of dependency it is, and, through the shared closed temporal member,
when the source was filed relative to the target.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_temporal import (
    BindingTemporalSelector,
    temporal_max_year_delta,
    temporal_period_anchors,
)
from .errors import RegistryValidationError
from .ids import ModeloId
from .relation_dependency import RelationDependencyRoleField, RelationKindField

__all__ = ["RelationPrefillProvider"]


class RelationPrefillProvider(BaseModel):
    """Strict validator for a ``relation_prefill`` binding declaration.

    The fold used to be split across two identified families: a binding that
    named the slot and a relation that named the source, the periods, the year
    alignment, and the aggregation. Every axis except :attr:`relation_kind` and
    :attr:`dependency_role` was declared on both sides, and the two could
    disagree. They are one declaration now.

    :attr:`temporal` is the shared closed member, so the source window is
    stated relative to the target filing context. An absolute source year is
    unspellable rather than merely rejected: no member of the union carries
    one, which is what keeps an inherited row from silently naming a year its
    successor edition does not file.

    Aggregation stays on the binding: it is a property of the value channel the
    slot yields, not of the source coordinate this provider names.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.RELATION_PREFILL] = BindingSourceKind.RELATION_PREFILL

    relation_kind: RelationKindField
    dependency_role: RelationDependencyRoleField
    source_modelo: ModeloId
    temporal: BindingTemporalSelector
    source_casilla_id: CasillaId | None = Field(default=None, min_length=1)
    source_casilla_ids: tuple[CasillaId, ...] = ()

    @property
    def max_year_delta(self) -> int | None:
        """Return the absolute bound on anchor year deltas the member declares."""
        return temporal_max_year_delta(self.temporal)

    def required_period_anchors_for_target(self, target_period: str) -> tuple[tuple[int, str], ...]:
        """Return source year-offset and period anchors for a target period.

        Each year offset is the TOTAL distance from the target filing year. An
        empty result means this provider names no source window for the target
        period at all, which is a scope-out and never a zero.
        """
        return temporal_period_anchors(self.temporal, target_period=target_period)

    @property
    def declared_source_casilla_ids(self) -> tuple[CasillaId, ...]:
        """Return the source casillas this provider reads, however they were declared."""
        if self.source_casilla_id is not None:
            return (self.source_casilla_id,)
        return self.source_casilla_ids

    @model_validator(mode="after")
    def _validate_source_shape(self) -> RelationPrefillProvider:
        if self.source_casilla_id is not None and self.source_casilla_ids:
            raise RegistryValidationError(
                "relation_prefill provider cannot declare both source_casilla_id and source_casilla_ids",
            )
        if self.source_casilla_id is None and not self.source_casilla_ids:
            raise RegistryValidationError(
                "relation_prefill provider must declare source_casilla_id or source_casilla_ids",
            )
        if len(set(self.source_casilla_ids)) != len(self.source_casilla_ids):
            raise RegistryValidationError("relation_prefill provider source_casilla_ids entries must be unique")
        return self

    @model_validator(mode="after")
    def _validate_dependency_role(self) -> RelationPrefillProvider:
        """Keep the annual-summary fold on the role that names it.

        An annual summary reads the periodic filings it summarises; declaring
        it under any other dependency role would misreport the fold to every
        consumer that classifies sources by role.
        """
        if self.relation_kind == "annual_summary" and self.dependency_role != "periodic_to_annual_summary":
            raise RegistryValidationError(
                "annual_summary relation_prefill must use the periodic_to_annual_summary dependency role",
                context={"dependency_role": str(self.dependency_role)},
            )
        return self
