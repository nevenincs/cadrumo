"""Project calculation notes and verification findings onto the work form."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext

from collections.abc import Iterable, Mapping
from typing import Final

from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .calculation_notes import CHECK_REFUSED_REASONS, note_attention
from .work_form_models import (
    ModeloFormAttention,
    ModeloFormCalculationNote,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormIssue,
)
from .work_review import ModeloWorkReview

_FINDINGS_OF_THE_SAME_CAUSE: Final[Mapping[str, frozenset[str]]] = {
    "unresolved_binding": frozenset({"application.modelo.findings.missing_required_casilla"}),
    "unresolved_derived_binding": frozenset({"application.modelo.findings.missing_required_casilla"}),
    "unrouted_observation": frozenset(
        {
            "application.modelo.findings.cuota_less_ledger_row_base_missing",
            "application.modelo.findings.oss_source_unrouted",
        }
    ),
    "unrouted_declarable_quantity": frozenset({"application.modelo.findings.cuota_less_ledger_row_base_missing"}),
    "iva_selected_scope_evidence_failure": frozenset(
        {
            "application.modelo.findings.iva_selected_scope_evidence_failure",
            "application.modelo.findings.iva_intra_eu_self_assessment_unrecordable",
            "application.modelo.findings.iva_import_document_unrecordable",
            "application.modelo.findings.iva_reagp_document_unrecordable",
            "application.modelo.findings.iva_rectification_document_unrecordable",
        }
    ),
    "iva_compensation_annual_source_evidence_failure": frozenset(
        {"application.modelo.findings.iva_compensation_annual_source_evidence_failure"}
    ),
    "withholding_detail_absent": frozenset(
        {
            "application.modelo.findings.withholding_detail_absent_unproven",
            "application.modelo.findings.withholding_detail_absent_against_ledger_evidence",
            "application.modelo.findings.withholding_detail_absent_attested",
        }
    ),
    "missing_transaction_evidence": frozenset(
        {
            "application.modelo.findings.transaction_evidence_missing_deductible",
            "application.modelo.findings.transaction_evidence_missing_output",
        }
    ),
}

"""The check's findings that say the same thing as a calculation note, by the note's reason."""

_ATTENTION_ORDER: Final[tuple[ModeloFormAttention, ...]] = tuple(ModeloFormAttention)


def collect_note_sources(
    revision: CalculationRevision | None, diagnostics: tuple[CalculationSourceDiagnostic, ...] | None
) -> tuple[tuple[str, str | None], ...]:
    """Each latest-calculation reason with the box it names: every diagnostic when held, else the durable ones."""
    if diagnostics is not None:
        return tuple(
            (diagnostic.reason, None if diagnostic.casilla_id is None else str(diagnostic.casilla_id))
            for diagnostic in diagnostics
        )
    if revision is None:
        return ()
    return tuple(
        (issue.reason, None if issue.casilla_id is None else str(issue.casilla_id)) for issue in revision.source_issues
    )


def _said_by_a_finding(reason: str, casilla_id: str | None, findings: Iterable[ModeloVerificationFinding]) -> bool:
    """Whether a finding of the check already says what this note says, about the same box."""
    causes = _FINDINGS_OF_THE_SAME_CAUSE.get(reason, frozenset())
    return any(
        finding.message_locale_key in causes
        and (None if finding.casilla_id is None else str(finding.casilla_id)) == casilla_id
        for finding in findings
    )


def project_calculation_notes(
    context: WorkFormContext, sources: tuple[tuple[str, str | None], ...], fields: Iterable[ModeloFormField]
) -> tuple[ModeloFormCalculationNote, ...]:
    """The latest calculation's notes on the filer's scale, once each, leaving out what a finding already says.

    A reason the check decides on its own evidence waits for the check: once
    the current calculation has been checked, the check's finding of the same
    cause is what stands, blocking where the check refused and worth checking
    where it accepted an attestation, so the note is left out.
    """
    checked = context.review.verification_outcome is not None
    boxes = {
        str(field.address.casilla_id): field.box
        for field in fields
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    notes: dict[tuple[str, str | None], ModeloFormCalculationNote] = {}
    for reason, casilla_id in sources:
        if (reason, casilla_id) in notes or _said_by_a_finding(reason, casilla_id, context.review.findings):
            continue
        if checked and reason in CHECK_REFUSED_REASONS:
            continue
        box = None if casilla_id is None else boxes.get(casilla_id)
        attention = note_attention(reason, box=box)
        notes[(reason, casilla_id)] = ModeloFormCalculationNote(
            reason=reason,
            attention=attention,
            casilla_id=casilla_id,
            box=box,
        )
    return tuple(sorted(notes.values(), key=lambda note: _ATTENTION_ORDER.index(note.attention)))


def project_verification_issues(
    review: ModeloWorkReview, fields: Iterable[ModeloFormField]
) -> tuple[ModeloFormIssue, ...]:
    """The review's verification findings, blocking first, each with the box it names."""
    boxes = {
        str(field.address.casilla_id): field.box
        for field in fields
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    ordered = sorted(
        review.findings, key=lambda finding: finding.severity is not ModeloVerificationFindingSeverity.BLOCKING
    )
    return tuple(
        ModeloFormIssue(finding=finding, box=None if finding.casilla_id is None else boxes.get(str(finding.casilla_id)))
        for finding in ordered
    )
