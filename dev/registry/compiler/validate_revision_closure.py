"""Revision closure and reference-surface validation helpers.

Runs closure validators for one
:class:`~domain.calculations.registry.ModeloRevision`, checking application
links, constructs, formulas, completeness-manifest references, continuity
references, and revision-level invariants against a prebuilt
:class:`~domain.calculations.registry._validate_revision_context.RevisionValidationContext`.

The reference-surface pass checks revision-level
:class:`~domain.calculations.registry.LegalReference` and
:class:`~domain.calculations.registry.SourceReference` ids with the
:class:`~domain.calculations.registry.validate_evidence.EvidenceValidator`.

See Also:
    :func:`domain.calculations.registry._validate_application_links.validate_application_link_closure`
        Application-link surface closure invoked by this module.
    :func:`dev.registry.compiler.validate_constructs.validate_construct_closure`
        Construct member and grounding closure invoked by this module.
    :func:`dev.registry.compiler.validate_formulas.validate_formula_dag`
        Formula dependency-cycle guard invoked by this module.
"""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.casilla_structural_succession import endpoint_source_context_failures
from cadrumo.domain.calculations.registry.orden_applicability import orden_aplicabilidad_hard_failures
from cadrumo.domain.calculations.registry.revision_context import ConstructMemberObject, RevisionValidationContext
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference
from cadrumo.domain.calculations.registry.temporal import revision_endpoint_source_ids

from ._validate_application_links import validate_application_link_closure
from ._validate_helpers import missing_refs as _missing_refs
from .validate_constructs import validate_construct_closure
from .validate_evidence import EvidenceValidator
from .validate_formulas import validate_formula_dag
from .validate_parameter_temporal import validate_bracket_table_temporal_coverage
from .validate_revision_rules import validate_reconciliation_total_closure

_REVISION_REFERENCE_SOURCE_TIERS = ("official_source_guidance", "layout_authority")


def validate_revision_closure_sections(
    failures: list[str],
    *,
    prefix: str,
    modelo_id: str,
    revision: ModeloRevision,
    context: RevisionValidationContext,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append section-closure failures for one registry revision.

    The :class:`~domain.calculations.registry.ModeloRevision` is evaluated
    with its precomputed
    :class:`~domain.calculations.registry._validate_revision_context.RevisionValidationContext`
    so member ids, application links, constructs, formula dependencies, and
    revision rules share one closure view.
    """
    failures.extend(validate_application_link_closure(prefix, revision, modelo_id=modelo_id))
    failures.extend(validate_reconciliation_total_closure(prefix, revision))
    failures.extend(validate_bracket_table_temporal_coverage(prefix, revision))
    # orden_aplicabilidad gate.
    failures.extend(orden_aplicabilidad_hard_failures(prefix, modelo_id, revision, legal_refs))
    failures.extend(
        validate_construct_closure(
            prefix,
            revision,
            member_objects=_construct_member_objects(context),
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(validate_formula_dag(prefix, revision))


def validate_revision_reference_surfaces(
    failures: list[str],
    *,
    prefix: str,
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append completeness-manifest and continuity reference failures.

    :class:`~domain.calculations.registry.LegalReference` and
    :class:`~domain.calculations.registry.SourceReference` maps provide id
    closure, while
    :class:`~domain.calculations.registry.validate_evidence.EvidenceValidator`
    enforces the source-tier requirements for revision-level reference surfaces.
    """
    manifest = revision.completeness_manifest
    if manifest is not None:
        failures.extend(
            _missing_refs(prefix, "calculation-completeness manifest", manifest.legal_refs, legal_refs, "legal"),
        )
        failures.extend(
            _missing_refs(prefix, "calculation-completeness manifest", manifest.source_refs, source_refs, "source"),
        )
        failures.extend(
            evidence.require_any_source_tier(
                prefix,
                "calculation-completeness manifest",
                manifest.source_refs,
                _REVISION_REFERENCE_SOURCE_TIERS,
            ),
        )
    for relation in revision.casilla_structural_successions:
        owner = f"casilla structural succession {relation.id!r}"
        failures.extend(_missing_refs(prefix, owner, relation.legal_refs, legal_refs, "legal"))
        for endpoint_id, endpoint_refs in (
            (relation.from_revision, relation.from_source_refs),
            (relation.to_revision, relation.to_source_refs),
        ):
            failures.extend(_missing_refs(prefix, owner, endpoint_refs, source_refs, "source"))
            failures.extend(
                evidence.require_any_source_tier(prefix, owner, endpoint_refs, _REVISION_REFERENCE_SOURCE_TIERS),
            )
            endpoint = modelo.revisions.get(endpoint_id)
            if endpoint is None:
                continue  # The structural endpoint validator owns this refusal.
            failures.extend(
                endpoint_source_context_failures(
                    f"{prefix}: {owner}",
                    endpoint=endpoint,
                    enrolled_source_ids=revision_endpoint_source_ids(modelo, endpoint),
                    source_ids=endpoint_refs,
                    sources=source_refs,
                ),
            )
    for evolution in revision.casilla_continuidad_evolutions:
        owner = f"casilla continuidad evolution {evolution.id!r}"
        failures.extend(_missing_refs(prefix, owner, evolution.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, evolution.source_refs, source_refs, "source"))
        failures.extend(
            evidence.require_any_source_tier(prefix, owner, evolution.source_refs, _REVISION_REFERENCE_SOURCE_TIERS),
        )


def _construct_member_objects(
    context: RevisionValidationContext,
) -> Mapping[str, Mapping[str, ConstructMemberObject]]:
    """Return construct-member indexes grouped by schema kind."""
    return {
        "casilla": context.casilla_by_id,
        "formula": context.formula_by_id,
        "parameter": context.parameter_by_id,
        "binding": context.binding_by_id,
        "export layout": context.export_layout_by_id,
        "extraction profile": context.extraction_profile_by_id,
        "cross-reference": context.cross_reference_by_id,
        "workbook parity reference": context.workbook_parity_by_id,
        "verification expectation": context.verification_expectation_by_id,
        "application link": context.application_link_by_id,
        "deadline window": context.deadline_window_by_id,
        "filing schedule": context.filing_schedule_by_id,
        "dependency classification": context.dependency_classification_by_id,
    }
