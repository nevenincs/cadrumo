"""Lookup context for per-revision validation.

Builds the ``RevisionValidationContext`` lookup tables from a
:class:`ModeloRevision`, aggregating id sets and by-id mappings used
across every per-section validator.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

from cadrumo.domain.calculations.registry.schema import (
    ApplicationLinkDefinition,
    ConstructDefinition,
    DataBindingDefinition,
    DeadlineWindowDefinition,
    DependencyClassificationDefinition,
    FormulaDefinition,
    ModeloRevision,
    ModeloScheduleDefinition,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.calculations.registry.schema_extraction import ExtractionProfileDefinition
from cadrumo.domain.calculations.registry.schema_formula import ParameterDefinition
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition, RelationDefinition
from cadrumo.domain.calculations.registry.schema_verification import LiveCrossReferenceDecision, WorkbookParityReference

from ....core import CasillaId
from .casilla_membership import casillas_by_id, declared_casilla_ids
from .ids import BindingId, RelationId
from .schema_verification import VerificationExpectationDefinition
from .validate_revision_identity import collect_record_id_lists


class _IdentifiedRecord(Protocol):
    id: str


def _records_by_id[RecordT: _IdentifiedRecord](records: Iterable[RecordT]) -> dict[str, RecordT]:
    return {record.id: record for record in records}


ConstructMemberObject = (
    CasillaDefinition
    | FormulaDefinition
    | ParameterDefinition
    | DataBindingDefinition
    | RelationDefinition
    | ExportLayoutDefinition
    | ExtractionProfileDefinition
    | LiveCrossReferenceDecision
    | WorkbookParityReference
    | VerificationExpectationDefinition
    | ApplicationLinkDefinition
    | DeadlineWindowDefinition
    | ModeloScheduleDefinition
    | DependencyClassificationDefinition
)
"""Every schema class :func:`validate_construct_closure` may look up as a
construct member. Every member of this union declares ``legal_refs`` and
``source_refs`` -- the single source of truth for the type both
:attr:`RevisionValidationContext.construct_member_objects` and
:func:`~._validate_constructs.validate_construct_closure` declare, so the
two stay in lock-step rather than one drifting to a bare ``object``.
"""


def _export_field_ids(revision: ModeloRevision) -> set[str]:
    return {field.id for layout in revision.export_layouts for record in layout.records for field in record.fields}


def _exported_casilla_ids(revision: ModeloRevision) -> set[CasillaId]:
    return {
        field.endpoint_casilla_id
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.endpoint_casilla_id is not None
    }


@dataclass(frozen=True)
class RevisionValidationContext:
    ids_by_kind: dict[str, list[str]]
    export_layout_ids: list[str]
    extraction_profile_ids: list[str]
    cross_reference_ids: list[str]
    workbook_parity_ids: list[str]
    verification_expectation_ids: list[str]
    application_link_ids: list[str]
    deadline_window_ids: list[str]
    filing_schedule_ids: list[str]
    casilla_by_id: dict[CasillaId, CasillaDefinition]
    formula_by_id: dict[str, FormulaDefinition]
    binding_by_id: dict[BindingId, DataBindingDefinition]
    relation_by_id: dict[RelationId, RelationDefinition]
    parameter_by_id: dict[str, ParameterDefinition]
    export_layout_by_id: dict[str, ExportLayoutDefinition]
    extraction_profile_by_id: dict[str, ExtractionProfileDefinition]
    cross_reference_by_id: dict[str, LiveCrossReferenceDecision]
    workbook_parity_by_id: dict[str, WorkbookParityReference]
    verification_expectation_by_id: dict[str, VerificationExpectationDefinition]
    application_link_by_id: dict[str, ApplicationLinkDefinition]
    deadline_window_by_id: dict[str, DeadlineWindowDefinition]
    filing_schedule_by_id: dict[str, ModeloScheduleDefinition]
    construct_by_id: dict[str, ConstructDefinition]
    dependency_classification_by_id: dict[str, DependencyClassificationDefinition]
    casillas: set[CasillaId]
    formulas: dict[str, FormulaDefinition]
    bindings: set[BindingId]
    relations: set[RelationId]
    parameters: set[str]
    resolvable_values: set[BindingId | CasillaId | RelationId | str]
    export_field_ids: set[str]
    exported_casillas: set[CasillaId]

    @property
    def construct_member_objects(self) -> Mapping[str, Mapping[str, ConstructMemberObject]]:
        return {
            "casilla": self.casilla_by_id,
            "formula": self.formula_by_id,
            "parameter": self.parameter_by_id,
            "binding": self.binding_by_id,
            "relation": self.relation_by_id,
            "export layout": self.export_layout_by_id,
            "extraction profile": self.extraction_profile_by_id,
            "cross-reference": self.cross_reference_by_id,
            "workbook parity reference": self.workbook_parity_by_id,
            "verification expectation": self.verification_expectation_by_id,
            "application link": self.application_link_by_id,
            "deadline window": self.deadline_window_by_id,
            "filing schedule": self.filing_schedule_by_id,
            "dependency classification": self.dependency_classification_by_id,
        }


def build_revision_validation_context(revision: ModeloRevision) -> RevisionValidationContext:
    ids_by_kind = collect_record_id_lists(revision)
    formula_by_id = _records_by_id(revision.formulas)
    binding_by_id = _records_by_id(revision.bindings)
    relation_by_id = _records_by_id(revision.relations)
    parameter_by_id = _records_by_id(revision.parameters)
    casillas = set(declared_casilla_ids(revision))
    bindings = set(binding_by_id)
    relations = set(relation_by_id)
    parameters = set(parameter_by_id)

    return RevisionValidationContext(
        ids_by_kind=ids_by_kind,
        export_layout_ids=ids_by_kind["export layout"],
        extraction_profile_ids=ids_by_kind["extraction profile"],
        cross_reference_ids=ids_by_kind["cross-reference"],
        workbook_parity_ids=ids_by_kind["workbook parity reference"],
        verification_expectation_ids=ids_by_kind["verification expectation"],
        application_link_ids=ids_by_kind["application link"],
        deadline_window_ids=ids_by_kind["deadline window"],
        filing_schedule_ids=ids_by_kind["filing schedule"],
        casilla_by_id=casillas_by_id(revision),
        formula_by_id=formula_by_id,
        binding_by_id=binding_by_id,
        relation_by_id=relation_by_id,
        parameter_by_id=parameter_by_id,
        export_layout_by_id=_records_by_id(revision.export_layouts),
        extraction_profile_by_id=_records_by_id(revision.extraction_profiles),
        cross_reference_by_id=_records_by_id(revision.live_cross_references),
        workbook_parity_by_id=_records_by_id(revision.workbook_parity_refs),
        verification_expectation_by_id=_records_by_id(revision.verification_expectations),
        application_link_by_id=_records_by_id(revision.application_links),
        deadline_window_by_id=_records_by_id(revision.deadline_windows),
        filing_schedule_by_id=_records_by_id(revision.filing_schedules),
        construct_by_id=_records_by_id(revision.constructs),
        dependency_classification_by_id=_records_by_id(revision.dependency_classifications),
        casillas=casillas,
        formulas=formula_by_id,
        bindings=bindings,
        relations=relations,
        parameters=parameters,
        resolvable_values=casillas | bindings | relations | parameters,
        export_field_ids=_export_field_ids(revision),
        exported_casillas=_exported_casilla_ids(revision),
    )
