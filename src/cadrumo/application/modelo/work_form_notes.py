"""Project calculation notes and verification findings onto the work form."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext

from collections.abc import Iterable, Mapping
from typing import Final

from ...core.aggregation import BindingSourceKind, BindingValueOutcome
from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, element_names_of
from ...domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..operator_actions.projection import PreconditionVerdictSnapshot
from .calculation_note_gate import SOURCE_DISAGREEMENT_FINDING_ID_LENGTH, gate_refuses
from .calculation_notes import (
    CALCULATION_SCREEN_OUTDATED_REASON,
    CHECK_REFUSED_REASONS,
    FILED_BEFORE_GRADE_CAP_REASON,
    durable_binding_source,
    note_attention,
    note_record_verdict,
)
from .work_form_declaration_facts import ModeloFormCalculationNote, ModeloFormResolutionAnswer
from .work_form_field_vocabulary import ModeloFormCasillaAddressV1
from .work_form_findings import ModeloFormAttention, ModeloFormIssue
from .work_form_models import ModeloFormField
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
            "application.modelo.findings.iva_import_document_unrecordable",
            "application.modelo.findings.iva_cuota_disagrees_with_rate",
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


type NoteSource = tuple[
    str,
    str | None,
    BindingSourceKind | None,
    CalculationNoteFact | None,
    BindingValueOutcome | None,
    tuple[str, OutputLanguage] | None,
    str | None,
]
"""One latest-calculation reason, the box it names, the binding source that raised it, its own facts,
the outcome its resolver stated for a capped value, the message its resolver worded for the filer
with the language it is worded in, and the finding key of the source disagreement it states."""


def _derived_leading_sources(
    revision: CalculationRevision | None, screen_outdated: bool, filed_before_grade_cap: CasillaId | None
) -> tuple[NoteSource, ...]:
    """The reasons derived from the revision's standing, not from a note: they lead every other source."""
    outdated: tuple[NoteSource, ...] = (
        ((CALCULATION_SCREEN_OUTDATED_REASON, None, None, None, None, None, None),)
        if screen_outdated and revision is not None
        else ()
    )
    capped: tuple[NoteSource, ...] = (
        ((FILED_BEFORE_GRADE_CAP_REASON, filed_before_grade_cap, None, None, None, None, None),)
        if filed_before_grade_cap is not None and revision is not None
        else ()
    )
    return outdated + capped


def _diagnostic_source(diagnostic: CalculationSourceDiagnostic) -> NoteSource:
    """One held diagnostic as a note source, carrying its message only when it is worded in a language."""
    worded = (
        None
        if diagnostic.message_language is None or not diagnostic.message
        else (diagnostic.message, diagnostic.message_language)
    )
    return (
        diagnostic.reason,
        diagnostic.casilla_id,
        durable_binding_source(diagnostic),
        diagnostic.fact,
        diagnostic.value_outcome,
        worded,
        None if diagnostic.disagreement is None else diagnostic.disagreement.finding_key,
    )


def collect_note_sources(
    revision: CalculationRevision | None,
    diagnostics: tuple[CalculationSourceDiagnostic, ...] | None,
    *,
    screen_outdated: bool = False,
    filed_before_grade_cap: CasillaId | None = None,
) -> tuple[NoteSource, ...]:
    """Each latest-calculation reason with the box it names: every diagnostic when held, else the durable ones.

    ``screen_outdated`` says the gate refuses ``revision`` as stale before it
    reads any note, so the derived reason leads them. ``filed_before_grade_cap``
    is the capped box whose figure keeps a revision filed before screens existed
    from being exported, which leads them the same way.

    Parameter types: ``revision`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).
    """
    stale = _derived_leading_sources(revision, screen_outdated, filed_before_grade_cap)
    if diagnostics is not None:
        return stale + tuple(_diagnostic_source(diagnostic) for diagnostic in diagnostics)
    if revision is None:
        return ()
    # A persisted note keeps the outcome its resolver stated, so a proven zero still reads as one. Its stored
    # message is a technical account in no language of the filer's, so the note is worded by its reason alone.
    return stale + tuple(
        (
            issue.reason,
            issue.casilla_id,
            issue.binding_source,
            issue.fact,
            issue.value_outcome,
            None,
            None if issue.disagreement is None else issue.disagreement.finding_key,
        )
        for issue in revision.source_issues
    )


def _said_by_a_finding(reason: str, casilla_id: str | None, findings: Iterable[ModeloVerificationFinding]) -> bool:
    """Whether a finding of the check already says what this note says, about the same box."""
    causes = _FINDINGS_OF_THE_SAME_CAUSE.get(reason, frozenset())
    return any(finding.message_locale_key in causes and finding.casilla_id == casilla_id for finding in findings)


def _boxes_by_casilla(fields: Iterable[ModeloFormField]) -> dict[CasillaId, str | None]:
    """The printed box of each casilla-addressed field."""
    return {
        field.address.casilla_id: field.box for field in fields if isinstance(field.address, ModeloFormCasillaAddressV1)
    }


def _message_in_language(worded: tuple[str, OutputLanguage] | None, language: OutputLanguage) -> str | None:
    """The resolver's message when it is worded in the form's own language, else nothing."""
    return worded[0] if worded is not None and worded[1] is language else None


def _resolution_answer(finding_key: str | None, context: WorkFormContext) -> ModeloFormResolutionAnswer | None:
    """The answer a disagreement note offers: take back the acceptance covering it, else accept the amount in use."""
    if finding_key is None:
        return None
    return (
        ModeloFormResolutionAnswer.REVOKE
        if context.resolutions.covers(finding_key)
        else ModeloFormResolutionAnswer.ACCEPT
    )


def note_recovery(
    reason: str, fact: CalculationNoteFact | None, language: OutputLanguage
) -> PreconditionVerdictSnapshot | None:
    """The way out a note opens, served in ``language`` through the verdict snapshot a refusal crosses with."""
    verdict = note_record_verdict(reason, fact)
    return None if verdict is None else PreconditionVerdictSnapshot.from_verdict(verdict, language)


def _projected_note(
    source: NoteSource, message: str | None, context: WorkFormContext, boxes: dict[CasillaId, str | None]
) -> ModeloFormCalculationNote:
    """One note source on the filer's scale, with the box it prints in and whether it withholds filing."""
    reason, casilla_id, binding_source, fact, outcome, _worded, finding_key = source
    box = None if casilla_id is None else boxes.get(casilla_id)
    return ModeloFormCalculationNote(
        reason=reason,
        attention=note_attention(reason, box=box, outcome=outcome, accepted=context.resolutions.covers(finding_key)),
        casilla_id=casilla_id,
        box=box,
        withholds_filing=gate_refuses(
            reason, binding_source, outcome, finding_key=finding_key, resolutions=context.resolutions
        ),
        finding_id=None if finding_key is None else finding_key[:SOURCE_DISAGREEMENT_FINDING_ID_LENGTH],
        resolution_answer=_resolution_answer(finding_key, context),
        fact=fact,
        element_names=element_names_of(fact, context.element_names),
        message=message,
        recovery=note_recovery(reason, fact, context.language),
    )


def project_calculation_notes(
    context: WorkFormContext, sources: tuple[NoteSource, ...], fields: Iterable[ModeloFormField]
) -> tuple[ModeloFormCalculationNote, ...]:
    """The latest calculation's notes on the filer's scale, once each, leaving out what a finding already says.

    Notes of one reason about one box are one note unless their facts differ: two
    elements with a gap in the same box are two things to read. A note without
    facts is told apart by its message instead, so two different accounts of one
    reason are both read. A message is carried only in the form's own language.

    A reason the check decides on its own evidence waits for the check: once
    the current calculation has been checked, the check's finding of the same
    cause is what stands, blocking where the check refused and worth checking
    where it accepted an attestation, so the note is left out.
    """
    checked = context.review.verification_outcome is not None
    boxes = _boxes_by_casilla(fields)
    notes: dict[tuple[str, str | None, tuple[str, ...], str], ModeloFormCalculationNote] = {}
    for source in sources:
        reason, casilla_id, _binding_source, fact, _outcome, worded, finding_key = source
        message = _message_in_language(worded, context.language)
        key = (
            reason,
            casilla_id,
            (message or "",) if fact is None else fact.identity(),
            "" if finding_key is None else finding_key,
        )
        if key in notes or _said_by_a_finding(reason, casilla_id, context.review.findings):
            continue
        if checked and reason in CHECK_REFUSED_REASONS:
            continue
        notes[key] = _projected_note(source, message, context, boxes)
    return tuple(sorted(notes.values(), key=lambda note: _ATTENTION_ORDER.index(note.attention)))


def project_verification_issues(
    review: ModeloWorkReview, fields: Iterable[ModeloFormField]
) -> tuple[ModeloFormIssue, ...]:
    """The review's verification findings, blocking first, each with the box it names."""
    boxes = _boxes_by_casilla(fields)
    ordered = sorted(
        review.findings, key=lambda finding: finding.severity is not ModeloVerificationFindingSeverity.BLOCKING
    )
    return tuple(
        ModeloFormIssue(finding=finding, box=None if finding.casilla_id is None else boxes.get(finding.casilla_id))
        for finding in ordered
    )
