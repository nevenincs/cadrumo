"""Typed inventory of canonical cross-model relation handoffs."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.aggregation import BindingSourceKind, RelationAggregationOp
from ._bindings import bound_casilla_binding_ids
from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId, LegalRefId, ModeloId, RelationId, RevisionId, SourceRefId
from ._relation_aggregation import relation_aggregation_op
from ._schema import (
    ModeloDefinition,
    RegistryCatalogues,
    RelationPeriodAlignment,
    RelationRevisionSelector,
)
from ._authority import ValidatedRegistryAuthority
from ._validate import RegistryValidator

__all__ = [
    "RegistryRelationHandoffApplicabilityAudit",
    "RegistryRelationHandoffAudit",
    "RelationHandoffApplicabilityRecord",
    "RelationHandoffRecord",
    "audit_registry_relation_handoff_applicability",
    "audit_registry_relation_handoffs",
]


class RelationHandoffRecord(BaseModel):
    """One validated relation handoff with source, target, period, and provenance axes."""

    model_config = STRICT_FROZEN_CONFIG

    target_modelo: ModeloId
    target_revision: RevisionId
    relation_id: RelationId
    relation_kind: Literal["previous_period", "annual_summary", "cross_model_output"]
    dependency_role: Literal[
        "profile_schedule",
        "periodic_to_annual_summary",
        "instalment_to_final_settlement",
        "direct_calculation",
        "factual_evidence",
    ]
    source_modelo: ModeloId
    source_revision_selector: RelationRevisionSelector
    source_casilla_id: CasillaId
    target_binding: BindingId
    target_binding_source: BindingSourceKind | None
    target_casilla_ids: tuple[CasillaId, ...]
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


class RegistryRelationHandoffAudit(BaseModel):
    """Finite validated inventory of every declared relation handoff."""

    model_config = STRICT_FROZEN_CONFIG

    records: tuple[RelationHandoffRecord, ...]

    @property
    def relation_count(self) -> int:
        """Return the number of relation declarations measured."""
        return len(self.records)

    @property
    def by_revision(self) -> dict[tuple[ModeloId, RevisionId], tuple[RelationHandoffRecord, ...]]:
        """Group records by their target modelo revision without losing identity."""
        grouped: dict[tuple[ModeloId, RevisionId], list[RelationHandoffRecord]] = {}
        for record in self.records:
            grouped.setdefault((record.target_modelo, record.target_revision), []).append(record)
        return {key: tuple(value) for key, value in grouped.items()}


class RelationHandoffApplicabilityRecord(BaseModel):
    """One relation-period applicability and clean-state contract row."""

    model_config = STRICT_FROZEN_CONFIG

    target_modelo: ModeloId
    target_revision: RevisionId
    relation_id: RelationId
    filing_year: int
    target_period: str
    relation_target_periods: tuple[str, ...]
    applicability: Literal["active", "not_applicable", "unresolved"]
    source_modelo: ModeloId
    source_filing_year: int | None = None
    source_periods: tuple[str, ...] = ()
    source_filing_periods: tuple[str, ...] = ()
    source_casilla_id: CasillaId
    target_binding: BindingId
    requirement_relation_ids: tuple[RelationId, ...] = ()
    dependency_treatment: Literal["direct_annual_settlement", "factual_evidence", "non_dependency"]
    taxpayer_files_source: bool
    conditional_on_economic_activity: bool
    clean_state_mode: Literal["required", "conditional", "advisory"]
    runtime_clean_state: Literal["unmeasured"] = "unmeasured"
    aggregation_op: RelationAggregationOp
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class RegistryRelationHandoffApplicabilityAudit(BaseModel):
    """Finite authority-selected relation-period applicability inventory."""

    model_config = STRICT_FROZEN_CONFIG

    records: tuple[RelationHandoffApplicabilityRecord, ...]

    @property
    def row_count(self) -> int:
        """Return the number of relation-period rows measured."""
        return len(self.records)

    @property
    def active_count(self) -> int:
        """Return relation-period rows that produce a source requirement."""
        return sum(record.applicability == "active" for record in self.records)

    @property
    def not_applicable_count(self) -> int:
        """Return relation-period rows excluded by the relation period selector."""
        return sum(record.applicability == "not_applicable" for record in self.records)

    @property
    def unresolved_count(self) -> int:
        """Return rows whose declared applicability produced no requirement."""
        return sum(record.applicability == "unresolved" for record in self.records)

    @property
    def by_revision(
        self,
    ) -> dict[tuple[ModeloId, RevisionId], tuple[RelationHandoffApplicabilityRecord, ...]]:
        """Group rows by target revision without collapsing periods."""
        grouped: dict[tuple[ModeloId, RevisionId], list[RelationHandoffApplicabilityRecord]] = {}
        for record in self.records:
            grouped.setdefault((record.target_modelo, record.target_revision), []).append(record)
        return {key: tuple(value) for key, value in grouped.items()}


def audit_registry_relation_handoffs(
    modelos: Iterable[ModeloDefinition],
    catalogues: RegistryCatalogues,
    *,
    source_root: Path,
) -> RegistryRelationHandoffAudit:
    """Validate and enumerate canonical relation declarations.

    The function is deli