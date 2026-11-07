"""Read the saved content selected by a filing record without current-source substitution.

:class:`CalculationRevision` holds the saved calculation and its evidence.
:class:`ModeloRecord` selects the saved filing content.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.casilla_id import CasillaId
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.formula_runtime import RegistryCalculationUnresolvedOutcome
from ...domain.calculations.registry.formula_runtime_ops import RegistryUnresolvedOutcomeReason
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id_from_revision,
)
from ...domain.modelos.calculation_revision_identity import (
    outputs_for_hash_from_mapping,
    outputs_for_hash_from_observations,
)
from ...domain.modelos.calculation_revision_sources import CalculationSourceIssue, CalculationSourceRef
from ...domain.modelos.filing_record import ModeloRecord
from ..user_profile.access_errors import ProfileAccessRefusedError
from .calculation_projection import ModeloCalculationDetailSnapshot
from .verification_report_public_facts import ModeloVerificationRegistrySnapshotProjection


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


class ModeloHistoricalContextEntryProjection(BaseModel):
    """One name and value the formula engine recorded to explain an unresolved outcome."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    name: Annotated[str, Field(min_length=1, max_length=128)]
    value: Annotated[str, Field(max_length=2_048)]


class ModeloHistoricalUnresolvedProjection(BaseModel):
    """Immutable saved unresolved formula outcome, its lineage and its recorded context.

    The fields are the saved outcome's own, as immutable wire scalars. They are
    copied rather than revalidated: the outcome belongs to the calculation that
    produced it, not to today's registry.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: CasillaId
    reason: RegistryUnresolvedOutcomeReason
    formula_id: str
    op: str
    operand_refs: tuple[str, ...]
    operand_casilla_refs: tuple[CasillaId, ...]
    operand_values: tuple[str, ...]
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    context: tuple[ModeloHistoricalContextEntryProjection, ...]

    @model_validator(mode="after")
    def _context_names_are_unique_and_sorted(self) -> Self:
        names = tuple(entry.name for entry in self.context)
        if names != tuple(sorted(set(names))):
            raise ValueError("unresolved outcome context names must be unique and sorted")
        return self

    @classmethod
    def from_outcome(cls, outcome: RegistryCalculationUnresolvedOutcome) -> Self:
        """Copy every field the saved outcome declares, with its context in name order."""
        return cls(
            casilla_id=outcome.casilla_id,
            reason=outcome.reason,
            formula_id=outcome.formula_id,
            op=outcome.op,
            operand_refs=outcome.operand_refs,
            operand_casilla_refs=outcome.operand_casilla_refs,
            operand_values=tuple(str(value) for value in outcome.operand_values),
            legal_refs=outcome.legal_refs,
            source_refs=outcome.source_refs,
            context=tuple(
                ModeloHistoricalContextEntryProjection(name=name, value=value)
                for name, value in sorted(outcome.context.items())
            ),
        )


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
    detail_rows: tuple[ModeloCalculationDetailSnapshot, ...] = ()
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


class ModeloHistoricalComparisonRowProjection(BaseModel):
    """Exact saved scalar spellings; a missing side remains absent rather than zero."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: CasillaId
    base_value: str | None
    selected_value: str | None
    base_value_kind: Literal["decimal", "text"] | None
    selected_value_kind: Literal["decimal", "text"] | None
    change: Literal["unchanged", "changed", "added", "removed"]

    @model_validator(mode="after")
    def _change_matches_saved_values(self) -> Self:
        if (self.base_value is None) != (self.base_value_kind is None) or (
            (self.selected_value is None) != (self.selected_value_kind is None)
        ):
            raise ValueError("a saved comparison value requires its value kind")
        if self.base_value is None and self.selected_value is None:
            raise ValueError("a saved comparison row must have at least one value")
        expected = (
            "added"
            if self.base_value is None
            else "removed"
            if self.selected_value is None
            else "unchanged"
            if (self.base_value_kind, self.base_value) == (self.selected_value_kind, self.selected_value)
            else "changed"
        )
        if self.change != expected:
            raise ValueError("a saved comparison change must match its values")
        return self


class ModeloHistoricalComparisonProjection(BaseModel):
    """A technical saved-value comparison, with no inferred labels or tax effects."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    base_filing_record_id: FilingRecordId | None
    availability: Literal["available", "no_base", "missing_base", "missing_content", "different_registry_revision"]
    rows: tuple[ModeloHistoricalComparisonRowProjection, ...] = ()

    @model_validator(mode="after")
    def _availability_matches_comparison(self) -> Self:
        if (self.availability == "no_base") != (self.base_filing_record_id is None):
            raise ValueError("saved comparison availability must match its base reference")
        if self.availability != "available" and self.rows:
            raise ValueError("unavailable saved comparisons cannot carry paired values")
        keys = tuple(row.casilla_id for row in self.rows)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("saved comparison casillas must be unique and sorted")
        return self


def compare_historical_filing_content(
    selected: ModeloHistoricalFilingContentProjection,
    base: ModeloHistoricalFilingContentProjection | None,
    *,
    base_filing_record_id: FilingRecordId | None,
) -> ModeloHistoricalComparisonProjection:
    """Pair scalar IDs only inside the same saved registry scope and revision."""
    availability: Literal["no_base", "missing_base", "missing_content", "different_registry_revision"]
    if base_filing_record_id is None:
        availability = "no_base"
    elif base is None:
        availability = "missing_base"
    elif selected.availability != "available" or base.availability != "available":
        availability = "missing_content"
    elif selected.registry_snapshot_ref != base.registry_snapshot_ref:
        availability = "different_registry_revision"
    else:
        before = {item.casilla_id: item for item in base.observations}
        after = {item.casilla_id: item for item in selected.observations}
        rows: list[ModeloHistoricalComparisonRowProjection] = []
        for key in sorted(before.keys() | after.keys()):
            old = before.get(key)
            new = after.get(key)
            change: Literal["unchanged", "changed", "added", "removed"] = (
                "added"
                if old is None
                else "removed"
                if new is None
                else "unchanged"
                if (old.value_kind, old.value) == (new.value_kind, new.value)
                else "changed"
            )
            rows.append(
                ModeloHistoricalComparisonRowProjection(
                    casilla_id=key,
                    base_value=None if old is None else old.value,
                    selected_value=None if new is None else new.value,
                    base_value_kind=None if old is None else old.value_kind,
                    selected_value_kind=None if new is None else new.value_kind,
                    change=change,
                )
            )
        return ModeloHistoricalComparisonProjection(
            base_filing_record_id=base_filing_record_id, availability="available", rows=tuple(rows)
        )
    return ModeloHistoricalComparisonProjection(base_filing_record_id=base_filing_record_id, availability=availability)


def _require_saved_filing_coordinates(record: ModeloRecord, revision: CalculationRevision) -> None:
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


def project_historical_filing_content(
    record: ModeloRecord, revision: CalculationRevision | None
) -> ModeloHistoricalFilingContentProjection:
    """Project exactly the record's saved revision, refusing identity or coordinate drift.

    The ``revision`` parameter uses :class:`CalculationRevision`, which holds the saved calculation and its evidence.
    The ``record`` parameter uses :class:`ModeloRecord`, which selects the saved filing content.
    """
    if revision is None:
        return ModeloHistoricalFilingContentProjection(
            calculation_revision_id=record.calculation_revision_id,
            availability="missing",
        )
    _require_saved_filing_coordinates(record, revision)
    coordinate = revision.registry_snapshot_ref
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
            ModeloCalculationDetailSnapshot.from_row(index, row) for index, row in enumerate(revision.detail_rows, 1)
        ),
        source_provenance=revision.source_provenance,
        source_issues=revision.source_issues,
        unresolved_outcomes=tuple(
            ModeloHistoricalUnresolvedProjection.from_outcome(row) for row in revision.unresolved_outcomes
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
        fingerprint=identity.fingerprint,
        row_set_grouping=identity.row_set_grouping,
        materialization_rule_id=source.materialization_rule_id,
        materialization_rule_version=source.materialization_rule_version,
    )
