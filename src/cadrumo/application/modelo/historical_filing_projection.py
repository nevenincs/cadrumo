"""Read the saved content selected by a filing record without current-source substitution."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceIssue,
    CalculationSourceRef,
    derive_calculation_revision_id_from_revision,
)
from ...domain.modelos.calculation_revision_identity import (
    outputs_for_hash_from_mapping,
    outputs_for_hash_from_observations,
)
from ...domain.modelos.filing_record import ModeloRecord
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .verification_report_public_facts import ModeloVerificationRegistrySnapshotProjection


class ModeloHistoricalDetailRowProjection(BaseModel):
    """Lossless saved row payload, without revalidation against today's registry."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    row_index: int = Field(ge=1)
    payload_json: str


class ModeloHistoricalCasillaProjection(BaseModel):
    """Saved box value and formula trace as immutable wire scalars."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: CasillaId
    value_kind: Literal["decimal", "text"]
    value: str
    formula_id: str | None
    op: str | None
    operand_refs: tuple[str, ...]
    operand_casilla_refs: tuple[CasillaId, ...]
    operand_values: tuple[str, ...]
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    absent_by_design: bool


class ModeloHistoricalRowProvenanceProjection(BaseModel):
    """Captured source identity for a saved repeating box."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    source_binding_id: str
    source_row_index: int
    source_kind: str
    source_row_identity: str
    fingerprint: str
    row_set_grouping: str | None
    materialization_rule_id: str
    materialization_rule_version: str


class ModeloHistoricalUnresolvedProjection(BaseModel):
    """Immutable saved unresolved formula outcome and its grounded context."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: CasillaId
    payload_json: str


class ModeloHistoricalRowCasillaProjection(BaseModel):
    """One immutable repeating box value with its captured source attribution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: CasillaId
    row_index: int = Field(ge=1)
    value: str
    provenance: ModeloHistoricalRowProvenanceProjection


class ModeloHistoricalFilingContentProjection(BaseModel):
    """Content of the selected filing's saved revision; missing stays unknown.

    Registry coordinates identify the saved calculation. They do not recover its
    original authority generation, official form labels, units, or rounding rules.
    Observation grounding and unresolved source conditions are copied as stored.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    calculation_revision_id: CalculationRevisionId
    availability: Literal["available", "missing"]
    registry_snapshot_ref: ModeloVerificationRegistrySnapshotProjection | None = None
    state: CalculationRevisionState | None = None
    observations: tuple[ModeloHistoricalCasillaProjection, ...] = ()
    row_casilla_values: tuple[ModeloHistoricalRowCasillaProjection, ...] = ()
    detail_rows: tuple[ModeloHistoricalDetailRowProjection, ...] = ()
    source_provenance: tuple[CalculationSourceRef, ...] = ()
    source_issues: tuple[CalculationSourceIssue, ...] = ()
    unresolved_outcomes: tuple[ModeloHistoricalUnresolvedProjection, ...] = ()

    @model_validator(mode="after")
    def _available_content_is_bound(self) -> Self:
        if self.availability == "available":
            if self.registry_snapshot_ref is None or self.state is None:
                raise ValueError("available historical filing content requires its saved coordinate and state")
        elif any(
            (
                self.registry_snapshot_ref,
                self.state,
                self.observations,
                self.row_casilla_values,
                self.detail_rows,
                self.source_provenance,
                self.source_issues,
                self.unresolved_outcomes,
            )
        ):
            raise ValueError("missing historical filing content cannot carry substituted content")
        keys = tuple(row.casilla_id for row in self.observations)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("historical observations must be unique and sorted")
        row_keys = tuple((row.casilla_id, row.row_index) for row in self.row_casilla_values)
        if row_keys != tuple(sorted(set(row_keys))):
            raise ValueError("historical repeating boxes must be unique and sorted")
        return self


def project_historical_filing_content(
    record: ModeloRecord, revision: CalculationRevision | None
) -> ModeloHistoricalFilingContentProjection:
    """Project exactly the record's saved revision, refusing identity or coordinate drift."""
    if revision is None:
        return ModeloHistoricalFilingContentProjection(
            calculation_revision_id=record.calculation_revision_id,
            availability="missing",
        )
    coordinate = revision.registry_snapshot_ref
    if (
        revision.calculation_revision_id != record.calculation_revision_id
        or revision.work_unit_id != record.work_unit_id
        or coordinate.modelo != record.modelo
        or coordinate.modelo_year != record.filing_year
        or coordinate.period != record.period.registry_token
        or derive_calculation_revision_id_from_revision(revision) != record.calculation_revision_id
        or outputs_for_hash_from_observations(revision.observations)
        != outputs_for_hash_from_mapping(revision.casilla_values)
        or set(revision.row_casilla_values) != set(revision.row_casilla_provenance)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return ModeloHistoricalFilingContentProjection(
        calculation_revision_id=revision.calculation_revision_id,
        availability="available",
        registry_snapshot_ref=ModeloVerificationRegistrySnapshotProjection.from_snapshot(coordinate),
        state=revision.state,
        observations=tuple(
            ModeloHistoricalCasillaProjection(
                casilla_id=item.casilla_id,
                value_kind=item.value_kind.value,
                value=str(item.value),
                formula_id=item.formula_id,
                op=item.op,
                operand_refs=item.operand_refs,
                operand_casilla_refs=item.operand_casilla_refs,
                operand_values=tuple(str(value) for value in item.operand_values),
                legal_refs=item.legal_refs,
                source_refs=item.source_refs,
                absent_by_design=item.absent_by_design,
            )
            for item in sorted(revision.observations, key=lambda item: item.casilla_id)
        ),
        row_casilla_values=tuple(
            ModeloHistoricalRowCasillaProjection(
                casilla_id=casilla_id,
                row_index=row_index,
                value=str(value),
                provenance=_row_provenance(revision, casilla_id, row_index),
            )
            for (casilla_id, row_index), value in sorted(revision.row_casilla_values.items())
        ),
        detail_rows=tuple(
            ModeloHistoricalDetailRowProjection(row_index=index, payload_json=row.model_dump_json())
            for index, row in enumerate(revision.detail_rows, 1)
        ),
        source_provenance=revision.source_provenance,
        source_issues=revision.source_issues,
        unresolved_outcomes=tuple(
            ModeloHistoricalUnresolvedProjection(casilla_id=row.casilla_id, payload_json=row.model_dump_json())
            for row in revision.unresolved_outcomes
        ),
    )


def _row_provenance(
    revision: CalculationRevision, casilla_id: CasillaId, row_index: int
) -> ModeloHistoricalRowProvenanceProjection:
    source = revision.row_casilla_provenance[(casilla_id, row_index)]
    identity = source.source_identity
    return ModeloHistoricalRowProvenanceProjection(
        source_binding_id=source.source_binding_id,
        source_row_index=source.source_row_index,
        source_kind=identity.source_kind.value,
        source_row_identity=identity.source_row_identity,
        fingerprint=str(identity.fingerprint),
        row_set_grouping=identity.row_set_grouping,
        materialization_rule_id=source.materialization_rule_id,
        materialization_rule_version=source.materialization_rule_version,
    )
