"""Project OSS source routing and required evidence findings from pinned bindings."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.aggregation import BindingSourceKind
from ...core.modelo import Modelo
from ...domain.calculations.registry.ids import (
    LegalRefId,
    SourceRefId,
)
from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationSourceIssue,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit
from .action_errors import (
    WORKFLOW_GATE_LEGAL_REFS,
)
from .verification_finding_contracts import ABSENT_FACT

if TYPE_CHECKING:
    pass


def m369_oss_bindings(snapshot: RegistrySnapshot) -> tuple[BindingDefinition, ...]:
    """Select the revision’s declared OSS aggregation bindings."""
    return tuple(
        binding for binding in snapshot.revision.bindings if binding.source is BindingSourceKind.LEDGER_OSS_AGGREGATION
    )


def m369_source_issue_finding(
    *,
    target: CalculationRevision,
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> ModeloVerificationFinding | None:
    """Project an OSS routing or missing-evidence source issue."""
    unrouted_issues = tuple(
        issue
        for issue in target.source_issues
        if issue.binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION and issue.reason == "unrouted_observation"
    )
    if unrouted_issues:
        return unrouted_oss_source_finding(unrouted_issues, legal_refs=legal_refs, source_refs=source_refs)
    if any(ref.resolved_binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION for ref in target.source_provenance):
        return None
    return missing_oss_evidence_finding(legal_refs=legal_refs, source_refs=source_refs)


def m369_unresolved_oss_source_finding(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
) -> ModeloVerificationFinding | None:
    """Block Modelo 369 verification when its OSS source remained unresolved.

    The calculate path deliberately persists a zero-valued draft and emits an
    ``oss_no_live_source`` diagnostic when no OSS/IOSS-tagged issued invoice can
    be projected. Diagnostics are operator-facing calculate results, so a
    non-consumed positive observation is retained on the revision as a typed
    source issue, while resolved candidates remain in the positive source-
    provenance trace. This preserves a real zero-valued invoice line while
    refusing both a silent claimed-zero catalogue and a line outside the form.
    """
    if str(work_unit.modelo) != Modelo("369").value:
        return None
    oss_bindings = m369_oss_bindings(snapshot)
    if not oss_bindings:
        return None
    legal_refs, source_refs = oss_binding_grounding(oss_bindings)
    return m369_source_issue_finding(
        target=target,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def oss_binding_grounding(
    oss_bindings: tuple[BindingDefinition, ...],
) -> tuple[tuple[LegalRefId, ...], tuple[SourceRefId, ...]]:
    """Collect the sorted legal_refs / source_refs declared across the OSS bindings."""
    legal_refs = tuple(sorted({ref for binding in oss_bindings for ref in binding.legal_refs}))
    source_refs = tuple(sorted({ref for binding in oss_bindings for ref in binding.source_refs}))
    return legal_refs, source_refs


def unrouted_oss_source_finding(
    unrouted_issues: tuple[CalculationSourceIssue, ...],
    *,
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> ModeloVerificationFinding:
    """Build the blocking finding for OSS observations no aggregation binding consumes."""
    source_ref_ids = tuple(issue.source_ref for issue in unrouted_issues if issue.source_ref is not None)
    message_facts: dict[str, str | int | bool | Decimal] = {
        "source_ref_count": len(source_ref_ids),
        "unidentified_source_count": len(unrouted_issues) - len(source_ref_ids),
        # Unconditional for the same reason as ``binding_id`` above: the message
        # names the unrouted refs, and an issue set carrying none would
        # otherwise render the placeholder itself. Every unrouted issue lacking
        # a source_ref is already counted by ``unidentified_source_count``, so
        # the marker is what distinguishes "none of them could be identified"
        # from a blank id.
        "source_ref_ids": "|".join(source_ref_ids) if source_ref_ids else ABSENT_FACT,
    }
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.oss_source_unrouted",
        message_facts=message_facts,
        legal_refs=legal_refs or WORKFLOW_GATE_LEGAL_REFS,
        source_refs=source_refs,
    )


def missing_oss_evidence_finding(
    *,
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> ModeloVerificationFinding:
    """Build the blocking finding for a declared-OSS revision with no persisted OSS evidence."""
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.oss_evidence_missing",
        message_facts={},
        legal_refs=legal_refs or WORKFLOW_GATE_LEGAL_REFS,
        source_refs=source_refs,
    )
