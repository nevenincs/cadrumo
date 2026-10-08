"""Project retained IVA supporting-authority and annual compensation evidence failures."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.aggregation import BindingSourceKind
from ...core.iva_deduction_fact import IvaDeductionEvidenceAuthority
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.iva.deduction_facts import deduction_evidence_authority_for_row
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
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from .action_errors import (
    WORKFLOW_GATE_LEGAL_REFS,
)
from .preconditions import ModeloPreconditionFailure
from .verification_finding_contracts import (
    ABSENT_FACT,
    LEDGER_TRANSACTION_SOURCE_REF_PREFIX,
    UNRECORDABLE_DEDUCTION_SCENARIOS,
)
from .verification_preconditions import (
    build_verification_precondition_failure,
)

if TYPE_CHECKING:
    pass


def iva_selected_scope_evidence_issues(target: CalculationRevision) -> tuple[CalculationSourceIssue, ...]:
    """Select the persisted IVA evidence failures retained by this revision.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).
    """
    return tuple(
        issue
        for issue in target.source_issues
        if issue.binding_source is BindingSourceKind.LEDGER_IVA_AGGREGATION
        and issue.reason == "iva_selected_scope_evidence_failure"
    )


@dataclass(frozen=True, slots=True)
class UnrecordableDeductionDocument:
    """A retained invoice row whose required supporting authority cannot be recorded."""

    transaction: Transaction
    authority: IvaDeductionEvidenceAuthority
    scenario_code: str


def unrecordable_deduction_documents(
    target: CalculationRevision,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
) -> tuple[UnrecordableDeductionDocument, ...]:
    """Read each held-back row's registry-required supporting authority.

    Only authorities no production supporting-document writer records get a
    terminal refusal. Missing rows and unresolved authorities keep the general
    finding; removing a row never erases its persisted evidence failure.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).
    """
    transaction_ids = selected_scope_transaction_ids(target)
    if not transaction_ids:
        return ()
    catalogue = transaction_repository.load()
    documents: list[UnrecordableDeductionDocument] = []
    for transaction_id in sorted(transaction_ids):
        transaction = catalogue.get(transaction_id)
        if transaction is None or not transaction.raw.amount.is_finite():
            continue
        authority = deduction_evidence_authority_for_row(
            kind=transaction.deduction_fact_kind,
            category=transaction.iva_category,
        )
        scenario = None if authority is None else UNRECORDABLE_DEDUCTION_SCENARIOS.get(authority.value)
        if authority is None or scenario is None:
            continue
        documents.append(UnrecordableDeductionDocument(transaction, authority, scenario))
    return tuple(documents)


def general_selected_scope_evidence_issues(
    target: CalculationRevision,
    unrecordable_transaction_ids: tuple[str, ...],
) -> tuple[CalculationSourceIssue, ...]:
    """Keep evidence failures outside the separately refused unrecordable rows.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).
    """
    unrecordable_source_refs = frozenset(
        f"{LEDGER_TRANSACTION_SOURCE_REF_PREFIX}{transaction_id}" for transaction_id in unrecordable_transaction_ids
    )
    return tuple(
        issue
        for issue in iva_selected_scope_evidence_issues(target)
        if issue.source_ref not in unrecordable_source_refs
    )


def iva_selected_scope_evidence_finding(
    target: CalculationRevision,
    *,
    unrecordable_transaction_ids: tuple[str, ...] = (),
) -> ModeloVerificationFinding | None:
    """Return the blocking finding for persisted selected-scope IVA evidence failures.

    Rows named in ``unrecordable_transaction_ids`` are left to their own finding.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).
    """
    issues = general_selected_scope_evidence_issues(target, unrecordable_transaction_ids)
    if not issues:
        return None
    source_refs = tuple(issue.source_ref for issue in issues if issue.source_ref is not None)
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.iva_selected_scope_evidence_failure",
        message_facts={
            "source_ref_count": len(source_refs),
            "unidentified_source_count": len(issues) - len(source_refs),
            "source_ref_ids": "|".join(source_refs) if source_refs else ABSENT_FACT,
        },
        legal_refs=WORKFLOW_GATE_LEGAL_REFS,
    )


def unrecordable_deduction_document_finding(document: UnrecordableDeductionDocument) -> ModeloVerificationFinding:
    """Keep each unsupported supporting document visible under its exact ledger subject."""
    transaction = document.transaction
    facts: dict[str, str | int | Decimal] = {
        "transaction_count": 1,
        "transaction_ids": transaction.transaction_id,
        "transaction_date": transaction.raw.booked_date.isoformat(),
        "transaction_amount": transaction.raw.amount,
        "transaction_currency": transaction.raw.currency,
        "required_evidence_authority": document.authority.value,
    }
    if document.scenario_code == "intra_eu_self_assessment_unrecordable":
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.iva_intra_eu_self_assessment_unrecordable",
            message_facts=facts,
            legal_refs=WORKFLOW_GATE_LEGAL_REFS,
        )
    if document.scenario_code == "import_document_unrecordable":
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.iva_import_document_unrecordable",
            message_facts=facts,
            legal_refs=WORKFLOW_GATE_LEGAL_REFS,
        )
    if document.scenario_code == "reagp_document_unrecordable":
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.iva_reagp_document_unrecordable",
            message_facts=facts,
            legal_refs=WORKFLOW_GATE_LEGAL_REFS,
        )
    if document.scenario_code == "rectification_document_unrecordable":
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.iva_rectification_document_unrecordable",
            message_facts=facts,
            legal_refs=WORKFLOW_GATE_LEGAL_REFS,
        )
    raise ValueError("unrecordable deduction document must identify a declared scenario")


def append_iva_selected_scope_evidence_finding(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    """Append specific and general IVA evidence refusals without dropping persisted issues.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).
    """
    documents = unrecordable_deduction_documents(target, transaction_repository)
    unrecordable_transaction_ids = tuple(document.transaction.transaction_id for document in documents)
    for document in documents:
        finding = unrecordable_deduction_document_finding(document)
        findings.append(finding)
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=work_unit.work_unit_id,
            condition_id="modelo.work.verify.iva_selected_scope_evidence.complete",
            scenario_id=f"modelo.work.verify.iva_selected_scope_evidence.{document.scenario_code}",
            evidence_id="modelo.work.verify.iva_selected_scope_evidence",
            evidence_values={
                "modelo": str(work_unit.modelo),
                **finding.message_facts,
            },
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        )
    finding = iva_selected_scope_evidence_finding(target, unrecordable_transaction_ids=unrecordable_transaction_ids)
    if finding is None:
        return
    findings.append(finding)
    failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
        calculation_revision_id=target.calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
        condition_id="modelo.work.verify.iva_selected_scope_evidence.complete",
        scenario_id="modelo.work.verify.iva_selected_scope_evidence.unresolved",
        evidence_id="modelo.work.verify.iva_selected_scope_evidence",
        evidence_values={
            "modelo": str(work_unit.modelo),
            "source_issue_count": len(general_selected_scope_evidence_issues(target, unrecordable_transaction_ids)),
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )


def iva_compensation_annual_source_evidence_finding(
    target: CalculationRevision,
) -> ModeloVerificationFinding | None:
    """Return the blocking finding for missing or stale required M390 partition evidence.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).
    """
    issues = tuple(
        issue
        for issue in target.source_issues
        if issue.binding_source is BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
        and issue.reason == "iva_compensation_annual_source_evidence_failure"
    )
    if not issues:
        return None
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.iva_compensation_annual_source_evidence_failure",
        message_facts={"source_issue_count": len(issues)},
        legal_refs=WORKFLOW_GATE_LEGAL_REFS,
    )


def append_iva_compensation_annual_source_evidence_finding(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    """Append the annual compensation evidence finding when its source remains unresolved.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).
    """
    finding = iva_compensation_annual_source_evidence_finding(target)
    if finding is None:
        return
    findings.append(finding)
    failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
        calculation_revision_id=target.calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
        condition_id="modelo.work.verify.iva_compensation_annual_source_evidence.complete",
        scenario_id="modelo.work.verify.iva_compensation_annual_source_evidence.unresolved",
        evidence_id="modelo.work.verify.iva_compensation_annual_source_evidence",
        evidence_values={"modelo": str(work_unit.modelo)},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )


def selected_scope_transaction_ids(target: CalculationRevision) -> set[str]:
    """Read exact ledger references retained by selected-scope evidence failures.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).
    """
    transaction_ids = {
        issue.source_ref.removeprefix(LEDGER_TRANSACTION_SOURCE_REF_PREFIX)
        for issue in iva_selected_scope_evidence_issues(target)
        if issue.source_ref is not None and issue.source_ref.startswith(LEDGER_TRANSACTION_SOURCE_REF_PREFIX)
    }
    return transaction_ids
