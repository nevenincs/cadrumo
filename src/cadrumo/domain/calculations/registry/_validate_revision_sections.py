"""Per-revision registry section validation.

Orchestrates validators for a modelo revision and collects their failures. The dispatcher builds a
:class:`~cadrumo.domain.calculations.registry.validate_revision_context.RevisionValidationContext`
once and reuses it across record, surface, dependency, algorithm, completeness,
and closure validators. Legal/source refs are checked through the shared
:class:`~cadrumo.domain.calculations.registry.validate_evidence.EvidenceValidator`.

See Also:
    :class:`cadrumo.domain.calculations.registry.RegistryValidator`
        Registry-level validator that calls :func:`validate_revision_definition`.
    :mod:`cadrumo.domain.calculations.registry.validate_revision_closure`
        Closure validators dispatched after section-level checks.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ....core import RegistryAuthorityGrade
from ._validate_applicability_section import validate_applicability_section
from ._validate_authority_grade import validate_authority_grade_section
from ._validate_completeness import emit_completeness_gate_failures as _emit_completeness_gate_failures
from ._validate_dependency_sections import (
    validate_dependency_classification_section,
    validate_filing_schedule_section,
    validate_relation_section,
)
from ._validate_evidence import EvidenceValidator
from ._validate_export_exemption import (
    modelo_publishes_a_record_design,
    validate_export_exemption_declarations,
)
from ._validate_export_layout_coverage import validate_export_layout_record_coverage
from ._validate_exports import validate_export_layout_section
from ._validate_formulas import validate_formula_section
from ._validate_helpers import missing_refs as _missing_refs
from ._validate_record_sections import (
    validate_binding_section,
    validate_casilla_section,
    validate_extraction_profile_section,
    validate_parameter_section,
)
from ._validate_revision_closure import validate_revision_closure_sections as _validate_revision_closure_sections
from ._validate_revision_closure import validate_revision_reference_surfaces as _validate_revision_reference_surfaces
from ._validate_revision_context import RevisionValidationContext, build_revision_validation_context
from ._validate_revision_id_window_agreement import validate_revision_id_window_agreement
from ._validate_surfaces import (
    validate_application_link_section,
    validate_cross_reference_section,
    validate_deadline_window_section,
    validate_verification_expectation_section,
    validate_workbook_parity_section,
)
from ._validate_valid_from_ejercicio_convention import validate_valid_from_ejercicio_convention
from .export import derive_export_layouts_from_bindings
from .schema import ModeloDefinition, ModeloRevision
from .schema_base import REGISTRY_SOURCE_GROUNDING_TIERS
from .schema_references import LegalReference, SourceReference
from .validate_revision_identity import (
    emit_revision_payload_failures as _emit_revision_payload_failures,
)
from .validate_revision_identity import (
    revision_reference_identity_failures,
)


def _requires_workbook_parity_coverage(revision: ModeloRevision) -> bool:
    """Whether the revision asserts a filing output that needs a parity anchor.

    A declared filing grade promises a draft/export even when a malformed
    revision currently materialises no layout; it must therefore retain the
    parity prerequisite.  Conversely, an applicability-only revision with no
    materialised layout makes no output claim, and requiring it to cite a
    layout would force an unsupported era to backdate an unrelated design.
    Binding-derived layouts count because they are the layout the renderer uses.
    """
    return revision.effective_authority_grade is RegistryAuthorityGrade.FILING or bool(
        derive_export_layouts_from_bindings(revision)
    )


def _validate_revision_surface_sections(
    failures: list[str],
    *,
    prefix: str,
    modelo_id: str,
    revision: ModeloRevision,
    publishes_record_design: bool,
    context: RevisionValidationContext,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
    source_root: Path | None,
    justificante_corpus_root: Path | None,
) -> None:
    """Append section-surface failures for one revision.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` is validated
    with a shared
    :class:`~cadrumo.domain.calculations.registry.validate_revision_context.RevisionValidationContext`
    so record, surface, dependency, algorithm, export, and extraction-profile
    checks consume the same declared-id indexes.
    """
    failures.extend(
        validate_casilla_section(
            prefix=prefix,
            revision=revision,
            formulas=context.formulas,
            bindings=context.bindings,
            export_field_ids=context.export_field_ids,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(
        validate_formula_section(
            prefix=prefix,
            revision=revision,
            casillas=context.casillas,
            casilla_by_id=context.casilla_by_id,
            bindings=context.bindings,
            parameters=context.parameters,
            relations=context.relations,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(
        validate_parameter_section(
            prefix=prefix,
            revision=revision,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(
        validate_binding_section(
            prefix=prefix,
            revision=revision,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(
        validate_relation_section(
            prefix=prefix,
            revision=revision,
            bindings=context.bindings,
            binding_by_id=context.binding_by_id,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(
        validate_dependency_classification_section(
            prefix=prefix,
            revision=revision,
            construct_by_id=context.construct_by_id,
            relation_by_id=context.relation_by_id,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(
        validate_applicability_section(
            prefix=prefix,
            modelo=modelo_id,
            revision=revision,
            legal_refs=legal_refs,
        ),
    )
    failures.extend(
        validate_filing_schedule_section(
            prefix=prefix,
            revision=revision,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(
        validate_export_layout_section(
            prefix=prefix,
            revision=revision,
            casillas=context.casillas,
            bindings=context.bindings,
            casilla_by_id=context.casilla_by_id,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
            source_root=source_root,
        ),
    )
    failures.extend(
        validate_export_exemption_declarations(
            prefix=prefix,
            modelo_id=modelo_id,
            revision=revision,
            publishes_record_design=publishes_record_design,
        ),
    )
    failures.extend(
        validate_export_layout_record_coverage(prefix=prefix, revision=revision, source_refs=source_refs),
    )
    failures.extend(validate_revision_id_window_agreement(prefix=prefix, revision=revision))
    failures.extend(validate_valid_from_ejercicio_convention(prefix=prefix, revision=revision))
    failures.extend(
        validate_extraction_profile_section(
            prefix=prefix,
            modelo_id=modelo_id,
            revision=revision,
            casillas=context.casillas,
            exported_casillas=context.exported_casillas,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
            corpus_root=justificante_corpus_root,
        ),
    )
    failures.extend(
        validate_cross_reference_section(
            prefix=prefix,
            revision=revision,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(
        validate_workbook_parity_section(
            prefix=prefix,
            revision=revision,
            legal_refs=legal_refs,
            source_refs=source_refs,
        ),
    )
    failures.extend(
        validate_verification_expectation_section(
            prefix=prefix,
            revision=revision,
            casillas=context.casillas,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(
        validate_application_link_section(
            prefix=prefix,
            revision=revision,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(
        validate_deadline_window_section(
            prefix=prefix,
            revision=revision,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )


def validate_revision_definition(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    *,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
    source_root: Path | None,
    justificante_corpus_root: Path | None,
) -> list[str]:
    """Return all registry validation failures for one modelo revision.

    The :class:`~cadrumo.domain.calculations.registry.ModeloDefinition` supplies the
    modelo scope and the
    :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies the
    revision payload. The function applies revision-level reference/evidence
    gates, builds the validation context, dispatches all section validators, then
    runs closure validators before returning the accumulated failures.
    """
    failures: list[str] = []
    prefix = f"modelo {modelo.id} revision {revision.id}"
    failures.extend(_missing_refs(prefix, "revision", revision.legal_refs, legal_refs, "legal"))
    failures.extend(_missing_refs(prefix, "revision", revision.source_refs, source_refs, "source"))
    failures.extend(
        evidence.require_any_source_tier(prefix, "revision", revision.source_refs, REGISTRY_SOURCE_GROUNDING_TIERS),
    )
    _validate_revision_reference_surfaces(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    context = build_revision_validation_context(revision)
    if _requires_workbook_parity_coverage(revision) and not context.ids_by_kind["workbook parity reference"]:
        failures.append(f"{prefix}: revision must declare official workbook parity coverage")
    failures.extend(revision_reference_identity_failures(prefix, revision))
    _emit_revision_payload_failures(failures, prefix, revision)
    _emit_completeness_gate_failures(failures, prefix, revision, modelo_id=modelo.id)
    _validate_revision_surface_sections(
        failures,
        prefix=prefix,
        modelo_id=modelo.id,
        revision=revision,
        publishes_record_design=modelo_publishes_a_record_design(modelo, source_refs),
        context=context,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
        source_root=source_root,
        justificante_corpus_root=justificante_corpus_root,
    )
    _validate_revision_closure_sections(
        failures,
        prefix=prefix,
        modelo_id=modelo.id,
        revision=revision,
        context=context,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    failures.extend(validate_authority_grade_section(prefix, modelo_id=modelo.id, revision=revision))
    return failures
