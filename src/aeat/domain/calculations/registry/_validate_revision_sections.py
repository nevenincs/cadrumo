"""Per-revision registry section validation dispatch."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from ._schema import (
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    SourceReference,
)
from ._validate_algorithms import validate_algorithm_binding_section, validate_algorithm_provider_section
from ._validate_application_links import validate_application_link_closure
from ._validate_constructs import validate_construct_closure, validate_support_removal_decisions
from ._validate_dependency_sections import (
    validate_dependency_classification_section,
    validate_filing_schedule_section,
    validate_relation_section,
)
from ._validate_evidence import EvidenceValidator
from ._validate_exports import validate_export_layout_section
from ._validate_formulas import validate_formula_dag
from ._validate_record_sections import (
    validate_binding_section,
    validate_casilla_section,
    validate_extraction_profile_section,
    validate_formula_section,
    validate_parameter_section,
)
from ._validate_revision_identity import (
    _collect_record_id_lists,
    _emit_casilla_identity_failures,
    _emit_combined_primary_id_failures,
    _emit_completeness_gate_failures,
    _emit_per_kind_duplicate_failures,
    _resolvable_casilla_references,
)
from ._validate_revision_rules import validate_reconciliation_total_closure
from ._validate_surfaces import (
    validate_application_link_section,
    validate_cross_reference_section,
    validate_deadline_window_section,
    validate_verification_expectation_section,
    validate_workbook_parity_section,
)


def validate_revision_definition(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    *,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
    justificante_corpus_root: Path | None,
) -> list[str]:
    failures: list[str] = []
    prefix = f"modelo {modelo.id} revision {revision.id}"
    failures.extend(_missing_refs(prefix, "revision", revision.legal_refs, legal_refs, "legal"))
    failures.extend(_missing_refs(prefix, "revision", revision.source_refs, source_refs, "source"))

    ids_by_kind = _collect_record_id_lists(revision)
    if not ids_by_kind["workbook parity reference"]:
        failures.append(f"{prefix}: revision must declare official workbook parity coverage")
    _emit_per_kind_duplicate_failures(failures, prefix, ids_by_kind)
    _emit_combined_primary_id_failures(failures, prefix, ids_by_kind)
    _emit_casilla_identity_failures(failures, prefix, revision)
    _emit_completeness_gate_failures(failures, prefix, revision)

    export_layout_ids = ids_by_kind["export layout"]
    extraction_profile_ids = ids_by_kind["extraction profile"]
    cross_reference_ids = ids_by_kind["cross-reference"]
    workbook_parity_ids = ids_by_kind["workbook parity reference"]
    verification_expectation_ids = ids_by_kind["verification expectation"]
    application_link_ids = ids_by_kind["application link"]
    deadline_window_ids = ids_by_kind["deadline window"]
    filing_schedule_ids = ids_by_kind["filing schedule"]

    casilla_by_id = {casilla.id: casilla for casilla in revision.casillas}
    formula_by_id = {formula.id: formula for formula in revision.formulas}
    binding_by_id = {binding.id: binding for binding in revision.bindings}
    relation_by_id = {relation.id: relation for relation in revision.relations}
    parameter_by_id = {parameter.id: parameter for parameter in revision.parameters}
    provider_by_id = {provider.id: provider for provider in revision.algorithm_providers}
    algorithm_binding_by_id = {binding.id: binding for binding in revision.algorithm_bindings}
    export_layout_by_id = {layout.id: layout for layout in revision.export_layouts}
    extraction_profile_by_id = {profile.id: profile for profile in revision.extraction_profiles}
    cross_reference_by_id = {
        cross_reference.id: cross_reference for cross_reference in revision.live_cross_references
    }
    workbook_parity_by_id = {workbook.id: workbook for workbook in revision.workbook_parity_refs}
    verification_expectation_by_id = {
        expectation.id: expectation for expectation in revision.verification_expectations
    }
    application_link_by_id = {link.id: link for link in revision.application_links}
    deadline_window_by_id = {window.id: window for window in revision.deadline_windows}
    filing_schedule_by_id = {schedule.id: schedule for schedule in revision.filing_schedules}
    support_removal_decision_by_id = {decision.id: decision for decision in revision.support_removal_decisions}
    construct_by_id = {construct.id: construct for construct in revision.constructs}
    dependency_classification_by_id = {
        classification.id: classification for classification in revision.dependency_classifications
    }

    casillas = set(_resolvable_casilla_references(revision))
    formulas = {formula.id: formula for formula in revision.formulas}
    bindings = set(binding_by_id)
    relations = set(relation_by_id)
    parameters = set(parameter_by_id)
    providers = set(provider_by_id)
    resolvable_values = casillas | bindings | relations | parameters
    export_field_ids = {
        field.id for layout in revision.export_layouts for record in layout.records for field in record.fields
    }
    exported_casillas = {
        field.casilla
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla is not None
    }

    validate_casilla_section(
        failures,
        prefix=prefix,
        revision=revision,
        formulas=formulas,
        bindings=bindings,
        export_field_ids=export_field_ids,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )
    validate_formula_section(
        failures,
        prefix=prefix,
        revision=revision,
        casillas=casillas,
        bindings=bindings,
        parameters=parameters,
        relations=relations,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_parameter_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_binding_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_relation_section(
        failures,
        prefix=prefix,
        revision=revision,
        bindings=bindings,
        binding_by_id=binding_by_id,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )

    validate_dependency_classification_section(
        failures,
        prefix=prefix,
        revision=revision,
        construct_by_id=construct_by_id,
        relation_by_id=relation_by_id,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )
    validate_filing_schedule_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )
    validate_algorithm_provider_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )
    validate_algorithm_binding_section(
        failures,
        prefix=prefix,
        revision=revision,
        providers=providers,
        casillas=casillas,
        resolvable_values=resolvable_values,
        parameters=parameters,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )

    validate_export_layout_section(
        failures,
        prefix=prefix,
        revision=revision,
        casillas=casillas,
        bindings=bindings,
        casilla_by_id=casilla_by_id,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_extraction_profile_section(
        failures,
        prefix=prefix,
        modelo_id=modelo.id,
        revision=revision,
        casillas=casillas,
        exported_casillas=exported_casillas,
        legal_refs=legal_refs,
        source_refs=source_refs,
        corpus_root=justificante_corpus_root,
    )
    validate_cross_reference_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_workbook_parity_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )
    validate_verification_expectation_section(
        failures,
        prefix=prefix,
        revision=revision,
        casillas=casillas,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )
    validate_application_link_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )
    validate_deadline_window_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )

    failures.extend(
        validate_support_removal_decisions(
            prefix,
            revision,
            export_layout_ids=export_layout_ids,
            extraction_profile_ids=extraction_profile_ids,
            cross_reference_ids=cross_reference_ids,
            workbook_parity_ids=workbook_parity_ids,
            verification_expectation_ids=verification_expectation_ids,
            application_link_ids=application_link_ids,
            deadline_window_ids=deadline_window_ids,
            filing_schedule_ids=filing_schedule_ids,
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
    )
    failures.extend(validate_application_link_closure(prefix, revision, modelo_id=modelo.id))
    failures.extend(validate_reconciliation_total_closure(prefix, revision))
    failures.extend(
        validate_construct_closure(
            prefix,
            revision,
            member_objects={
                "casilla": casilla_by_id,
                "formula": formula_by_id,
                "parameter": parameter_by_id,
                "binding": binding_by_id,
                "algorithm provider": provider_by_id,
                "algorithm binding": algorithm_binding_by_id,
                "relation": relation_by_id,
                "export layout": export_layout_by_id,
                "extraction profile": extraction_profile_by_id,
                "cross-reference": cross_reference_by_id,
                "workbook parity reference": workbook_parity_by_id,
                "verification expectation": verification_expectation_by_id,
                "application link": application_link_by_id,
                "deadline window": deadline_window_by_id,
                "filing schedule": filing_schedule_by_id,
                "support removal decision": support_removal_decision_by_id,
                "dependency classification": dependency_classification_by_id,
            },
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
    )
    failures.extend(validate_formula_dag(prefix, revision))
    return failures


def _missing_refs(
    scope: str,
    owner: str,
    refs: Iterable[str],
    catalogue: Mapping[str, LegalReference] | Mapping[str, SourceReference],
    ref_kind: str,
) -> list[str]:
    return [f"{scope}: {owner} references unknown {ref_kind} id {ref!r}" for ref in refs if ref not in catalogue]
