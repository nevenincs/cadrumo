"""Lookup context for per-revision validation.

Builds the ``RevisionValidationContext`` lookup tables from a
:class:`ModeloRevision`, aggregating id sets and by-id mappings used
across every per-section validator.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ._casilla_membership import casillas_by_id
from ._ids import BindingId, CasillaId, RelationId
from ._schema import (
    AlgorithmBindingDefinition,
    AlgorithmProviderDefinition,
    ApplicationLinkDefinition,
    CasillaDefinition,
    ConstructDefinition,
    DataBindingDefinition,
    DeadlineWindowDefinition,
    DependencyClassificationDefinition,
    ExportLayoutDefinition,
    ExtractionProfileDefinition,
    FormulaDefinition,
    LiveCrossReferenceDecision,
    ModeloRevision,
    ModeloScheduleDefinition,
    ParameterDefinition,
    RelationDefinition,
    SupportRemovalDecisionDefinition,
    VerificationExpectationDefinition,
    WorkbookParityReference,
)
from ._validate_revision_identity import _collect_record_id_lists, _resolvable_casilla_references


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
    provider_by_id: dict[str, AlgorithmProviderDefinition]
    algorithm_binding_by_id: dict[str, AlgorithmBindingDefinition]
    export_layout_by_id: dict[str, ExportLayoutDefinition]
    extraction_profile_by_id: dict[str, ExtractionProfileDefinition]
    cross_reference_by_id: dict[str, LiveCrossReferenceDecision]
    workbook_parity_by_id: dict[str, WorkbookParityReference]
    verification_expectation_by_id: dict[str, VerificationExpectationDefinition]
    application_link_by_id: dict[str, ApplicationLinkDefinition]
    deadline_window_by_id: dict[str, DeadlineWindowDefinition]
    filing_schedule_by_id: dict[str, ModeloScheduleDefinition]
    support_removal_decision_by_id: dict[str, SupportRemovalDecisionDefinition]
    construct_by_id: dict[str, ConstructDefinition]
    dependency_classification_by_id: dict[str, DependencyClassificationDefinition]
    casillas: set[CasillaId]
    formulas: dict[str, FormulaDefinition]
    bindings: set[BindingId]
    relations: set[RelationId]
    parameters: set[str]
    providers: set[str]
    resolvable_values: set[BindingId | CasillaId | RelationId | str]
    export_field_ids: set[str]
    exported_casillas: set[CasillaId]

    @property
    def construct_member_objects(
        self,
    ) -> Mapping[
        str,
        Mapping[
            str,
            CasillaDefinition
            | FormulaDefinition
            | ParameterDefinition
            | DataBindingDefinition
            | AlgorithmProviderDefinition
            | AlgorithmBindingDefinition
            | RelationDefinition
            | ExportLayoutDefinition
            | ExtractionProfileDefinition
            | LiveCrossReferenceDecision
            | WorkbookParityReference
            | VerificationExpectationDefinition
            | ApplicationLinkDefinition
            | DeadlineWindowDefinition
            | ModeloScheduleDefinition
            | SupportRemovalDecisionDefinition
            | DependencyClassificationDefinition,
        ],
    ]:
        return {
            "casilla": self.casilla_by_id,
            "formula": self.formula_by_id,
            "parameter": self.parameter_by_id,
            "binding": self.binding_by_id,
            "algorithm provider": self.provider_by_id,
            "algorithm binding": self.algorithm_binding_by_id,
            "relation": self.relation_by_id,
            "export layout": self.export_layout_by_id,
            "extraction profile": self.extraction_profile_by_id,
            "cross-reference": self.cross_reference_by_id,
            "workbook parity reference": self.workbook_parity_by_id,
            "verification expectation": self.verification_expectation_by_id,
            "application link": self.application_link_by_id,
            "deadline window": self.deadline_window_by_id,
            "filing schedule": self.filing_schedule_by_id,
            "support removal decision": self.support_removal_decision_by_id,
            "dependency classification": self.dependency_classification_by_id,
        }


def build_revision_validation_context(revision: ModeloRevision) -> RevisionValidationContext:
    ids_by_kind = _collect_record_id_lists(revision)
    formula_by_id = {formula.id: formula for formula in revision.formulas}
    binding_by_id = {binding.id: binding for binding in revision.bindings}
    relation_by_id = {relation.id: relation for relation in revision.relations}
    parameter_by_id = {parameter.id: parameter for parameter in revision.parameters}
    provider_by_id = {provider.id: provider for provider in revision.algorithm_providers}
    casillas = set(_resolvable_casilla_references(revision))
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
        provider_by_id=provider_by_id,
        algorithm_binding_by_id={binding.id: binding for binding in revision.algorithm_bindings},
        export_layout_by_id={layout.id: layout for layout in revision.export_layouts},
        extraction_profile_by_id={profile.id: profile for profile in revision.extraction_profiles},
        cross_reference_by_id={
            cross_reference.id: cross_reference for cross_reference in revision.live_cross_references
        },
        workbook_parity_by_id={workbook.id: workbook for workbook in revision.workbook_parity_refs},
        verification_expectation_by_id={
            expectation.id: expectation for expectation in revision.verification_expectations
        },
        application_link_by_id={link.id: link for link in revision.application_links},
        deadline_window_by_id={window.id: window for window in revision.deadline_windows},
        filing_schedule_by_id={schedule.id: schedule for schedule in revision.filing_schedules},
        support_removal_decision_by_id={decision.id: decision for decision in revision.support_removal_decisions},
        construct_by_id={construct.id: construct for construct in revision.constructs},
        dependency_classification_by_id={
            classification.id: classification for classification in revision.dependency_classifications
        },
        casillas=casillas,
        formulas=formula_by_id,
        bindings=bindings,
        relations=relations,
        parameters=parameters,
        providers=set(provider_by_id),
        resolvable_values=casillas | bindings | relations | parameters,
        export_field_ids={
            field.id for layout in revision.export_layouts for record in layout.records for field in record.fields
        },
        exported_casillas={
            field.casilla_id
            for layout in revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.casilla_id is not None
        },
    )
