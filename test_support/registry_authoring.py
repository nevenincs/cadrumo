"""Test-only access to registry authoring and publication operations.

The product package consumes only the published registry authority.  Tests that
exercise a deliberately mutable authoring candidate cross into development
tooling here, outside the distributable source tree.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from dev.registry.compiler import (
    _validate_evidence as evidence_cache,
)
from dev.registry.compiler import (
    _validate_export_layout_coverage as coverage,
)
from dev.registry.compiler import (
    _validate_revision_rules as rules,
)
from dev.registry.compiler._validate_constructs import _CONSTRUCT_MEMBER_ATTRS
from dev.registry.compiler._validate_evidence import (
    _CORPUS_TEXT_CACHE_FILENAME,
    EvidenceValidator,
    _corpus_text_cache_path,
    _load_disk_cache,
    _read_manual_pdf_sidecar,
    _validated_sidecar_text,
    _write_disk_cache,
)
from dev.registry.compiler._validate_export_exemption import (
    modelo_publishes_a_record_design,
    validate_export_exemption_declarations,
)
from dev.registry.compiler._validate_export_layout_coverage import validate_export_layout_record_coverage
from dev.registry.compiler._validate_exports import _validate_embedded_envelope_source_authority
from dev.registry.compiler._validate_formulas import validate_formula_dag
from dev.registry.compiler._validate_parameter_temporal import (
    validate_dated_values,
    validate_non_filing_axis_admission,
)
from dev.registry.compiler._validate_record_design_epochs import (
    validate_record_design_epoch_uniqueness,
    validate_record_design_epoch_window,
)
from dev.registry.compiler._validate_relation_periods import select_relation_source_revisions
from dev.registry.compiler._validate_relation_sources import validate_relation_closure, validate_slot_source_hygiene
from dev.registry.compiler._validate_revision_rules import (
    _bracket_coverage_gaps,
    validate_deadline_window_uniqueness,
    validate_revision_windows,
)
from dev.registry.compiler._validate_semantic_role_required import (
    _REQUIRED_ROLE_LABEL_PATTERNS,
    collect_casillas_by_semantic_role,
    required_role_declaration_failures,
)
from dev.registry.compiler.authority import (
    compile_registry_tree,
    compile_validated_authority,
    compiled_bundled_authority,
)
from dev.registry.compiler.convenio import convenio_authority_from_facts
from dev.registry.compiler.corpus_catalogue import verify_source_catalogue, verify_source_file
from dev.registry.compiler.fact_loader import load_governed_facts
from dev.registry.compiler.fact_providers import compile_registered_fact_providers
from dev.registry.compiler.identity import (
    REGISTRY_IDENTITY_SCHEMA_VERSION,
    RegistryIdentityStamp,
    read_registry_identity_stamp,
    registry_identity_stamp_location,
)
from dev.registry.compiler.legal_grounding import legal_reference_quotes_corpus, verify_legal_catalogue
from dev.registry.compiler.loader import load_catalogue_file, load_modelo_directory, load_registry_tree
from dev.registry.compiler.loader_fingerprints import clear_fingerprint_cache
from dev.registry.compiler.m303_orden_manifest import load_m303_annual_orden_authority
from dev.registry.compiler.registry_scope import validate_registry_scope
from dev.registry.compiler.validator import RegistryValidator
from dev.registry.pipeline.authority_publication import publish_authority_candidate
from dev.registry.tests.manual_oracle_support import oracle_declared_figures, read_manual_worked_example

from cadrumo.domain.renta.ledger_expenses import (
    RentaDeductibilityContext,
    RentaDeductibleExpenseFact,
    RentaExpenseDirection,
    build_renta_deductible_expense_observation,
    evaluate_renta_deductibility,
)

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues


_LAZY_EXPORTS = {
    **{name: "dev.registry.compiler.verdict_cache" for name in (
        "RegistryValidationVerdict", "VERDICT_OUTCOME_GREEN", "bundled_verdict_path",
        "certify_registry_validation", "compute_shipped_verdict_key", "compute_verdict_key",
        "read_verdict", "registry_validation_is_certified", "shipped_verdict_location",
        "verdict_cache_path", "write_verdict",
    )},
    **{name: "dev.registry.compiler._validate_export_layout_coverage" for name in (
        "_administration_reserved", "_belongs_to_layout", "_covers", "_design_sources",
        "_missing_report", "_omissible_reason", "_position", "_read_design_sheets",
        "_required_positions", "_sheet_constants",
    )},
    **{name: "dev.registry.compiler._validate_layout_authority_content" for name in (
        "_ANNEX_BLOCK", "_ANNEX_HEADING", "_LAYOUT_VOCABULARY", "_carries_layout_content",
        "validate_layout_authority_content",
    )},
    **{name: "dev.registry.compiler._validate_official_source_guidance_content" for name in (
        "_DEADLINE_VOCABULARY", "_SUPPRESSION_VOCABULARY", "_carries_deadline_content",
        "_carries_suppression_content", "deadline_window_content_failures",
        "validate_suppression_notice_content",
    )},
    **{name: "dev.registry.conformance.tests._registry_schema_support" for name in (
        "_NUMERIC_CASILLA_01", "_as_communication_revision", "_keyed_bracket",
    )},
    **{name: "dev.registry.conformance.tests._loader_directory_mode_support" for name in (
        "_standard_manifest_text", "_standard_revision_preamble_text",
        "write_extracted_corpus_sidecar", "write_fragmented_revision",
    )},
    **{name: "dev.registry.compiler.loader" for name in (
        "_load_registry_tree_cached", "collect_registry_tree_fingerprints", "load_modelo_source",
        "load_shared_catalogues",
    )},
    **{name: "dev.registry.compiler.loader_cache" for name in (
        "is_bundled_registry_root", "registry_disk_cache_dir", "registry_disk_cache_enabled",
    )},
    **{name: "dev.registry.compiler._validate_revision_rules" for name in (
        "validate_deadline_window_cadence", "validate_deadline_window_ownership",
        "validate_periodic_deadline_completeness",
    )},
    "_REVIEWED_PRESUMPTIVE_NORMATIVE_CORPUS": "dev.registry.compiler.legal_grounding",
    "_registry_fingerprint_cache": "dev.registry.compiler.loader_fingerprints",
    "_relation_is_prior_year_filing_carry": "dev.registry.compiler._validate_relation_sources",
    "collect_label_artifact_findings": "dev.registry.compiler._validate_label_artifacts",
    "compile_record_design_manifest_catalogue": "dev.registry.compiler.corpus_catalogue",
    "cross_revision_casilla_consistency_failures": "dev.registry.compiler._validate_cross_revision",
    "declared_cross_revision_continuity_semantic_linkage_failures": "dev.registry.compiler._validate_cross_revision",
    "fact_providers": "dev.registry.compiler",
    "load_convenio_authority": "dev.registry.compiler.convenio",
    "revision_id_claims_open_window": "dev.registry.compiler._validate_revision_id_window_agreement",
    "revision_window_closures": "dev.registry.compiler._validate_revision_id_window_agreement",
    "schema_family_enrollment_failures": "dev.registry.conformance.tests._schema_family_support",
    "semantic_role_consistency_failures": "dev.registry.compiler._validate_semantic_roles",
    "validate_applicability_section": "dev.registry.compiler._validate_applicability_section",
    "validate_authority_grade_section": "dev.registry.compiler._validate_authority_grade",
    "validate_construct_closure": "dev.registry.compiler._validate_constructs",
    "validate_no_label_artifacts": "dev.registry.compiler._validate_label_artifacts",
    "validate_relation_source_coordinate_coverage": "dev.registry.compiler._validate_relation_periods",
    "validate_revision_id_window_agreement": "dev.registry.compiler._validate_revision_id_window_agreement",
    "verify_catalogue_identity_bindings": "dev.registry.compiler.corpus_catalogue",
    "verify_legal_reference_grounding": "dev.registry.compiler.legal_grounding",
}


def __getattr__(name: str):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value
    return value


def _committed_registry_tree():
    from dev.registry.conformance.tests._registry_schema_support import _committed_registry_tree as helper

    return helper()


def _committed_registry():
    from dev.registry.conformance.tests._registry_schema_support import _committed_registry as helper

    return helper()


def _committed_snapshot(*args, **kwargs):
    from dev.registry.conformance.tests._registry_schema_support import _committed_snapshot as helper

    return helper(*args, **kwargs)


def _revision(modelo):
    from dev.registry.conformance.tests._registry_schema_support import _revision as helper

    return helper(modelo)


def _with_revision(modelo, revision):
    from dev.registry.conformance.tests._registry_schema_support import _with_revision as helper

    return helper(modelo, revision)


def _committed_modelo(modelo_id: str) -> tuple[ModeloDefinition, RegistryCatalogues]:
    """Load conformance support lazily to avoid a registry-snapshot import cycle."""
    from dev.registry.conformance.tests._registry_schema_support import _committed_modelo as committed_modelo

    return committed_modelo(modelo_id)


def reset_registry_authoring_caches() -> None:
    """Clear compiler process caches at a pytest-session boundary."""
    from dev.registry.compiler import loader as registry_loader

    registry_loader._load_registry_tree_cached.cache_clear()
    clear_fingerprint_cache()


__all__ = [
    "REGISTRY_IDENTITY_SCHEMA_VERSION",
    "_CONSTRUCT_MEMBER_ATTRS",
    "_CORPUS_TEXT_CACHE_FILENAME",
    "_NUMERIC_CASILLA_01",
    "_REQUIRED_ROLE_LABEL_PATTERNS",
    "EvidenceValidator",
    "RegistryIdentityStamp",
    "RegistryValidator",
    "RentaDeductibilityContext",
    "RentaDeductibleExpenseFact",
    "RentaExpenseDirection",
    "_bracket_coverage_gaps",
    "_committed_modelo",
    "_committed_registry",
    "_committed_registry_tree",
    "_committed_snapshot",
    "_corpus_text_cache_path",
    "_load_disk_cache",
    "_read_manual_pdf_sidecar",
    "_revision",
    "_validate_embedded_envelope_source_authority",
    "_validated_sidecar_text",
    "_with_revision",
    "_write_disk_cache",
    "build_renta_deductible_expense_observation",
    "clear_fingerprint_cache",
    "collect_casillas_by_semantic_role",
    "compile_registered_fact_providers",
    "compile_registry_tree",
    "compile_validated_authority",
    "compiled_bundled_authority",
    "convenio_authority_from_facts",
    "coverage",
    "evaluate_renta_deductibility",
    "evidence_cache",
    "legal_reference_quotes_corpus",
    "load_catalogue_file",
    "load_governed_facts",
    "load_m303_annual_orden_authority",
    "load_modelo_directory",
    "load_registry_tree",
    "modelo_publishes_a_record_design",
    "oracle_declared_figures",
    "publish_authority_candidate",
    "read_manual_worked_example",
    "read_registry_identity_stamp",
    "registry_identity_stamp_location",
    "required_role_declaration_failures",
    "reset_registry_authoring_caches",
    "rules",
    "select_relation_source_revisions",
    "validate_dated_values",
    "validate_deadline_window_uniqueness",
    "validate_export_exemption_declarations",
    "validate_export_layout_record_coverage",
    "validate_formula_dag",
    "validate_non_filing_axis_admission",
    "validate_record_design_epoch_uniqueness",
    "validate_record_design_epoch_window",
    "validate_registry_scope",
    "validate_relation_closure",
    "validate_revision_windows",
    "validate_slot_source_hygiene",
    "verify_legal_catalogue",
    "verify_source_catalogue",
    "verify_source_file",
]
