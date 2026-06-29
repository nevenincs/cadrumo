"""Revision closure and reference-surface validation helpers.

Runs closure validators for one :class:`ModeloRevision`, checking application
links, constructs, formulas, completeness-manifest references, continuity
references, and revision-level invariants against a prebuilt validation context.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._schema import LegalReference, ModeloRevision, SourceReference
from ._validate_application_links import validate_application_link_closure
from ._validate_constructs import validate_construct_closure, validate_support_removal_decisions
from ._validate_formulas import validate_formula_dag
from ._validate_helpers import _missing_refs
from ._validate_orden_aplicabilidad import orden_aplicabilidad_hard_failures
from ._validate_revision_context import RevisionValidationContext
from ._validate_revision_rules import (
    validate_bracket_table_temporal_coverage,
    validate_reconciliation_total_closure,
)


def _validate_revision_closure_sections(
    failures: list[str],
    *,
    prefix: str,
    modelo_id: str,
    revision: ModeloRevision,
    context: RevisionValidationContext,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> None:
    failures.extend(
        validate_support_removal_decisions(
            prefix,
            revision,
            export_layout_ids=context.export_layout_ids,
            extraction_profile_ids=context.extraction_profile_ids,
            cross_reference_ids=context.cross_reference_ids,
            workbook_parity_ids=context.workbook_parity_ids,
            verification_expectation_ids=context.verification_expectation_ids,
            application_link_ids=context.application_link_ids,
            deadline_window_ids=context.deadline_window_ids,
            filing_schedule_ids=context.filing_schedule_ids,
            legal_refs=legal_refs,
            source_refs=source_refs,
        ),
    )
    failures.extend(validate_application_link_closure(prefix, revision, modelo_id=modelo_id))
    failures.extend(validate_reconciliation_total_closure(prefix, revision))
    failures.extend(validate_bracket_table_temporal_coverage(prefix, revision))
    # D3 / S05: orden_aplicabilidad ratchet gate (hard, load-blocking failures only).
    failures.extend(orden_aplicabilidad_hard_failures(prefix, modelo_id, revision, legal_refs))
    failures.extend(
        validate_construct_closure(
            prefix,
            revision,
            member_objects=context.construct_member_objects,
            legal_refs=legal_refs,
            source_refs=source_refs,
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
) -> None:
    manifest = revision.completeness_manifest
    if manifest is not None:
        failures.extend(
            _missing_refs(prefix, "calculation-completeness manifest", manifest.legal_refs, legal_refs, "legal"),
        )
        failures.extend(
            _missing_refs(prefix, "calculation-completeness manifest", manifest.source_refs, source_refs, "source"),
        )
    for evolution in revision.casilla_continuidad_evolutions:
        owner = f"casilla continuidad evolution {evolution.id!r}"
        failures.extend(_missing_refs(prefix, owner, evolution.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, evolution.source_refs, source_refs, "source"))
