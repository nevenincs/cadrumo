"""Per-revision registry section validation dispatch.

Orchestrates all per-section validators for a single
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` within its
:class:`~cadrumo.domain.calculations.registry.ModeloDefinition`, collecting every
failure into a flat list returned to the registry-level validator.

The dispatcher builds a
:class:`~cadrumo.domain.calculations.registry._validate_revision_context.RevisionValidationContext`
once and reuses it across record, surface, dependency, algorithm, completeness,
and closure validators. Legal/source refs are checked through the shared
:class:`~cadrumo.domain.calculations.registry._validate_evidence.EvidenceValidator`.

See Also:
    :class:`cadrumo.domain.calculations.registry.RegistryValidator`
        Registry-level validator that calls :func:`validate_revision_definition`.
    :mod:`cadrumo.domain.calculations.registry._validate_record_sections`
        Record-section validators dispatched from this module.
    :mod:`cadrumo.domain.calculations.registry._validate_revision_closure`
        Closure validators dispatched after section-level checks.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ._schema import LegalReference, ModeloDefinition, ModeloRevision, SourceReference
from ._validate_algorithms import validate_algorithm_binding_section, validate_algorithm_provider_section
from ._validate_completeness import emit_completeness_gate_failures as _emit_completeness_gate_failures
from ._validate_dependency_sections import (
    validate_dependency_classification_section,
    validate_filing_schedule_section,
    validate_relation_section,
)
from ._validate_evidence import EvidenceValidator
from ._validate_exports import validate_export_layout_section
from ._validate_helpers import missing_refs as _missing_refs
from ._validate_record_sections import (
    validate_binding_section,
    validate_casilla_section,
    validate_extraction_profile_section,
    validate_formula_section,
    validate_parameter_section,
)
from ._validate_revision_closure import (
    validate_revision_closure_sections as _validate_revision_closure_sections,
)
from ._validate_revision_closure import (
    validate_revision_reference_surfaces as _validate_revision_reference_surfaces,
)
from ._validate_revision_context import RevisionValidationContext, build_revision_validation_context
from ._validate_revision_identity import (
    emit_revision_payload_failures as _emit_revision_payload_failures,
)
from ._validate_revision_identity import (
    revision_reference_identity_failures,
)
from ._validate_surfaces import (
    validate_application_link_section,
    validate_cross_reference_section,
    validate_deadline_window_section,
    validate_verification_expectation_section,
    validate_workbook_parity_section,
)

_REVISION_SOURCE_TIERS = ("official_source_guidance", "layout_authority")


def _validate_revision_surface_sections(
    failures: list[str],
    *,
    prefix: str,
    modelo_id: str,
    revision: ModeloRevision,
    context: RevisionValidationContext,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
    justificante_corpus_root: Path | None,
) -> None:
    """Append section-surface failures for one revision.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` is validated
    with a shared
    :class:`~cadrumo.domain.calculations.registry._validate_revision_context.RevisionValidationContext`
    so record, surface, dependency, algorithm, export, and extraction-profile
    checks consume the same declared-id indexes.
    """
    validate_casilla_section(
        failures,
        prefix=prefix,
        revision=revision,
        formulas=context.formulas,
        bindings=context.bindings,
        export_field_ids=context.export_field_ids,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_formula_section(
        failures,
        prefix=prefix,
        revision=revision,
        casillas=context.casillas,
        bindings=context.bindings,
        parameters=context.parameters,
        relations=context.relations,
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
        bindings=context.bindings,
        binding_by_id=context.binding_by_id,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_dependency_classification_section(
        failures,
        prefix=prefix,
        revision=revision,
        construct_by_id=context.construct_by_id,
        relation_by_id=context.relation_by_id,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_filing_schedule_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_algorithm_provider_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_algorithm_binding_section(
        failures,
        prefix=prefix,
        revision=revision,
        provider_by_id=context.provider_by_id,
        casillas=context.casillas,
        resolvable_values=context.resolvable_values,
        parameters=context.parameters,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_export_layout_section(
        failures,
        prefix=prefix,
        revision=revision,
        casillas=context.casillas,
        bindings=context.bindings,
        casilla_by_id=context.casilla_by_id,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_extraction_profile_section(
        failures,
        prefix=prefix,
        modelo_id=modelo_id,
        revision=revision,
        casillas=context.casillas,
        exported_casillas=context.exported_casillas,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
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
        casillas=context.casillas,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_application_link_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    validate_deadline_window_section(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
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
    failures.extend(evidence.require_any_source_tier(prefix, "revision", revision.source_refs, _REVISION_SOURCE_TIERS))
    _validate_revision_reference_surfaces(
        failures,
        prefix=prefix,
        revision=revision,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    context = build_revision_validation_context(revision)
    if not context.ids_by_kind["workbook parity reference"]:
        failures.append(f"{prefix}: revision must declare official workbook parity coverage")
    failures.extend(revision_reference_identity_failures(prefix, revision))
    _emit_revision_payload_failures(failures, prefix, revision)
    _emit_completeness_gate_failures(failures, prefix, revision, modelo_id=modelo.id)
    _validate_revision_surface_sections(
        failures,
        prefix=prefix,
        modelo_id=modelo.id,
        revision=revision,
        context=context,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
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
    return failures
