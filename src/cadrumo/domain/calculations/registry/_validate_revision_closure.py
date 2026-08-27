"""Revision closure and reference-surface validation helpers.

Runs closure validators for one
:class:`~domain.calculations.registry.ModeloRevision`, checking application
links, constructs, formulas, completeness-manifest references, continuity
references, and revision-level invariants against a prebuilt
:class:`~domain.calculations.registry._validate_revision_context.RevisionValidationContext`.

The reference-surface pass checks revision-level
:class:`~domain.calculations.registry.LegalReference` and
:class:`~domain.calculations.registry.SourceReference` ids with the
:class:`~domain.calculations.registry._validate_evidence.EvidenceValidator`.

See Also:
    :func:`domain.calculations.registry._validate_application_links.validate_application_link_closure`
        Application-link surface closure invoked by this module.
    :func:`domain.calculations.registry._validate_constructs.validate_construct_closure`
        Construct member and grounding closure invoked by this module.
    :func:`domain.calculations.registry._validate_formulas.validate_formula_dag`
        Formula dependency-cycle guard invoked by this module.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._validate_application_links import validate_application_link_closure
from ._validate_constructs import validate_construct_closure
from ._validate_evidence import EvidenceValidator
from ._validate_formulas import validate_formula_dag
from ._validate_helpers import missing_refs as _missing_refs
from ._validate_orden_aplicabilidad import orden_aplicabilidad_hard_failures
from ._validate_revision_context import RevisionValidationContext
from ._validate_revision_rules import (
    validate_bracket_table_temporal_coverage,
    validate_reconciliation_total_closure,
)
from .schema import ModeloRevision
from .schema_references import LegalReference, SourceReference

_REVISION_REFERENCE_SOURCE_TIERS = ("official_source_guidance", "layout_authority")


def _validate_revision_closure_sections(
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
            member_objects=context.construct_member_objects,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        ),
    )
    failures.extend(validate_formula_dag(prefix, revision))


def _validate_revision_reference_surfaces(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append completeness-manifest and continuity reference failures.

    :class:`~domain.calculations.registry.LegalReference` and
    :class:`~domain.calculations.registry.SourceReference` maps provide id
    closure, while
    :class:`~domain.calculations.registry._validate_evidence.EvidenceValidator`
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
    for evolution in revision.casilla_continuidad_evolutions:
        owner = f"casilla continuidad evolution {evolution.id!r}"
        failures.extend(_missing_refs(prefix, owner, evolution.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, evolution.source_refs, source_refs, "source"))
        failures.extend(
            evidence.require_any_source_tier(prefix, owner, evolution.source_refs, _REVISION_REFERENCE_SOURCE_TIERS),
        )


validate_revision_closure_sections = _validate_revision_closure_sections
validate_revision_reference_surfaces = _validate_revision_reference_surfaces
