"""Strict, locale-neutral public facts from one persisted calculation revision.

The snapshot is assembled while the exact registry operation is pinned.  It
contains the facts needed by the existing calculation result presentation,
without carrying a domain revision or selecting a display language.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, model_validator

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.bindings import CasillaObservation, CasillaObservationValueKind
from ...domain.calculations.registry.ids import FormulaId, LegalRefId, SourceRefId
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import PublicDecimal, PublicNamedScalar
from ._calculation_helpers import resolve_registry_snapshot_for_work_unit
from .calculation import visible_calculation_casilla_values, visible_calculation_observations
from .result_summary import ResultSummaryRole, calculation_result_summary
from .verification_projection import ModeloRegistrySnapshotCoordinates


class ModeloCalculationObservationSnapshot(BaseModel):
    """One visible observation with its numeric or textual value type intact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: CasillaId
    value_kind: CasillaObservationValueKind
    value: PublicDecimal | str
    formula_id: FormulaId | None
    op: str | None
    operand_refs: tuple[str, ...]
    operand_casilla_refs: tuple[CasillaId, ...]
    operand_values: tuple[PublicDecimal, ...]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    absent_by_design: bool

    @classmethod
    def from_observation(cls, observation: CasillaObservation) -> Self:
        """Retain the canonical observation, including its scalar discriminator."""
        value = observation.value
        return cls(
            casilla_id=observation.casilla_id,
            value_kind=observation.value_kind,
            value=PublicDecimal(decimal=str(value)) if isinstance(value, Decimal) else value,
            formula_id=observation.formula_id,
            op=observation.op,
            operand_refs=observation.operand_refs,
            operand_casilla_refs=observation.operand_casilla_refs,
            operand_values=tuple(PublicDecimal(decimal=str(item)) for item in observation.operand_values),
            legal_refs=observation.legal_refs,
            source_refs=observation.source_refs,
            absent_by_design=observation.absent_by_design,
        )

    @model_validator(mode="after")
    def _value_matches_kind(self) -> Self:
        if self.value_kind is CasillaObservationValueKind.DECIMAL and not isinstance(self.value, PublicDecimal):
            raise ValueError("decimal observation requires a tagged decimal")
        if self.value_kind is CasillaObservationValueKind.TEXT and not isinstance(self.value, str):
            raise ValueError("text observation requires exact text")
        if any(ref not in self.operand_refs for ref in self.operand_casilla_refs):
            raise ValueError("observation casilla operand is absent from its trace")
        return self


class ModeloCalculationSummarySnapshot(BaseModel):
    """One canonical headline role with keys for later locale selection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    role: ResultSummaryRole
    casilla_id: CasillaId
    value: PublicDecimal
    label_keys: tuple[str, ...]


class ModeloCalculationDetailField(BaseModel):
    """One ordered detail-row field in the existing public spelling."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: str
    value: str | None


class ModeloCalculationDetailSnapshot(BaseModel):
    """One ordered, heterogeneous materialized detail row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    index: int
    row_type: str
    fields: tuple[ModeloCalculationDetailField, ...]

    @model_validator(mode="after")
    def _unique_fields(self) -> Self:
        if self.index < 1 or len({field.key for field in self.fields}) != len(self.fields):
            raise ValueError("invalid detail-row index or duplicate field")
        return self


class ModeloCalculationSourceSnapshot(BaseModel):
    """The source trace already disclosed by calculation result presentation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    resolver_id: str
    resolved_binding_source: BindingSourceKind
    contributor_source_kind: str
    contributor_binding_source: BindingSourceKind | None
    lineage_role: CalculationSourceLineageRole
    source_ref: str
    parent_source_ref: str | None
    fingerprint: str | None
    dependency_treatment: str


class ModeloCalculationSnapshot(BaseModel):
    """Public calculation facts, pinned to the exact parent and registry revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    registry_snapshot_ref: ModeloRegistrySnapshotCoordinates
    modelo: str
    filing_year: FilingYear
    period: PublicPeriod
    state: CalculationRevisionState
    casilla_values: tuple[PublicNamedScalar, ...]
    observations: tuple[ModeloCalculationObservationSnapshot, ...]
    result_summary: tuple[ModeloCalculationSummarySnapshot, ...]
    detail_rows: tuple[ModeloCalculationDetailSnapshot, ...]
    source_provenance: tuple[ModeloCalculationSourceSnapshot, ...]
    binding_overrides: tuple[PublicNamedScalar, ...]
    relation_overrides: tuple[PublicNamedScalar, ...]
    input_values_by_casilla_id: tuple[PublicNamedScalar, ...]
    created_at: datetime
    updated_at: datetime
    verified_at: datetime | None
    verified_by: str | None
    filed_at: datetime | None
    filed_by: str | None
    superseded_at: datetime | None

    @classmethod
    def from_revision(
        cls,
        revision: CalculationRevision,
        *,
        work_unit: WorkUnit,
        operation: PinnedAuthorityOperation,
    ) -> Self:
        """Project existing visibility and headline owners, then validate correlation."""
        snapshot = resolve_registry_snapshot_for_work_unit(
            work_unit, grade=RegistryAuthorityGrade.CALCULATION, operation=operation
        )
        casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
        summary = calculation_result_summary(
            revision, operation=operation, work_unit=work_unit, language=OutputLanguage.ES
        )
        return cls(
            bucket_id=work_unit.bucket_id,
            work_unit_id=work_unit.work_unit_id,
            calculation_revision_id=revision.calculation_revision_id,
            registry_snapshot_ref=ModeloRegistrySnapshotCoordinates.model_validate(
                revision.registry_snapshot_ref.model_dump(mode="python")
            ),
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=PublicPeriod.from_period(work_unit.period),
            state=revision.state,
            casilla_values=_decimal_facts(visible_calculation_casilla_values(revision, operation=operation)),
            observations=tuple(
                ModeloCalculationObservationSnapshot.from_observation(item)
                for item in visible_calculation_observations(revision, operation=operation)
            ),
            result_summary=(
                tuple(
                    ModeloCalculationSummarySnapshot(
                        role=row.role,
                        casilla_id=row.casilla_id,
                        value=PublicDecimal(decimal=str(row.value)),
                        label_keys=casillas[row.casilla_id].localization_keys if row.casilla_id in casillas else (),
                    )
                    for row in summary.rows
                )
                if summary is not None
                else ()
            ),
            detail_rows=tuple(
                ModeloCalculationDetailSnapshot(
                    index=index,
                    row_type=str(row.row_type),
                    fields=tuple(
                        ModeloCalculationDetailField(key=key, value=None if value is None else str(value))
                        for key, value in row.model_dump(mode="json", exclude={"row_type"}).items()
                    ),
                )
                for index, row in enumerate(revision.detail_rows, start=1)
            ),
            source_provenance=tuple(
                ModeloCalculationSourceSnapshot(
                    resolver_id=ref.resolver_id,
                    resolved_binding_source=ref.resolved_binding_source,
                    contributor_source_kind=ref.contributor_source_kind,
                    contributor_binding_source=ref.contributor_binding_source,
                    lineage_role=ref.lineage_role,
                    source_ref=ref.source_ref,
                    parent_source_ref=ref.parent_source_ref,
                    fingerprint=ref.fingerprint,
                    dependency_treatment=ref.dependency_treatment,
                )
                for ref in revision.source_provenance
            ),
            binding_overrides=_text_facts(revision.binding_overrides),
            relation_overrides=_text_facts(revision.relation_overrides),
            input_values_by_casilla_id=_text_facts(revision.input_values_by_casilla_id),
            created_at=revision.created_at,
            updated_at=revision.updated_at,
            verified_at=revision.verified_at,
            verified_by=revision.verified_by,
            filed_at=revision.filed_at,
            filed_by=revision.filed_by,
            superseded_at=revision.superseded_at,
        )

    @model_validator(mode="after")
    def _exact_coordinates_and_fact_types(self) -> Self:
        registry = self.registry_snapshot_ref
        if (
            self.modelo != registry.modelo
            or self.filing_year != registry.modelo_year
            or self.period.code != registry.period
            or self.period.filing_year != self.filing_year
            or self.work_unit_id
            != derive_work_unit_id(
                bucket_id=self.bucket_id,
                modelo=self.modelo,
                filing_year=self.filing_year,
                period=self.period.to_period(),
                revision_id=registry.revision_id,
            )
        ):
            raise ValueError("calculation snapshot has mismatched work-unit or registry coordinates")
        for facts, expected_type in (
            (self.casilla_values, PublicDecimal),
            (self.binding_overrides, str),
            (self.relation_overrides, str),
            (self.input_values_by_casilla_id, str),
        ):
            keys = tuple(item.key for item in facts)
            if keys != tuple(sorted(set(keys))) or any(not isinstance(item.value, expected_type) for item in facts):
                raise ValueError("calculation snapshot has unordered or duplicate names or altered scalar types")
        values = {item.key: item.value for item in self.casilla_values}
        if any(values.get(row.casilla_id) != row.value for row in self.result_summary):
            raise ValueError("calculation headline does not match visible casilla values")
        if len({row.casilla_id for row in self.result_summary}) != len(self.result_summary):
            raise ValueError("duplicate calculation headline casilla")
        if any(row.index != index for index, row in enumerate(self.detail_rows, start=1)):
            raise ValueError("calculation detail rows must retain contiguous indexes")
        return self


def _decimal_facts(values: Mapping[CasillaId, Decimal]) -> tuple[PublicNamedScalar, ...]:
    """Give visible Decimal facts a deterministic immutable order."""
    return tuple(
        PublicNamedScalar(key=str(key), value=PublicDecimal(decimal=str(value)))
        for key, value in sorted(values.items())
    )


def _text_facts(values: Mapping[str, str]) -> tuple[PublicNamedScalar, ...]:
    """Give typed input spellings a deterministic immutable order."""
    return tuple(PublicNamedScalar(key=str(key), value=value) for key, value in sorted(values.items()))
