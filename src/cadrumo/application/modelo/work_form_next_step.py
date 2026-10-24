"""What a declaration's form asks of the filer, counted once, and the one thing to do next.

Every frontend counts what blocks filing, what is missing and what waits to be
confirmed with these functions, and offers the action :func:`form_next_step`
names, so a header's chips, a next-action line and a list row never disagree.

The ladder follows the application's own gates. The file for the AEAT and
recording the filing are offered only once the current calculation is
verified and nothing blocks filing: an assumed value, a finding that blocks, a
calculation note the export or filing gate refuses on, or a result box the
calculation could not produce. A calculation note only the check can decide
waits for the check, so while it is all that blocks an unchecked calculation
the next action is the check, never "resolve". Recording a filing only records
it in Cadrumo, so a verified declaration is first offered the file to take to
the AEAT, and recording once a file made from the current calculation exists;
a file made from an earlier calculation is to be created again, never recorded.

What a page that does not apply this period holds is never to do: its missing
and assumed boxes are not counted. Once a filing is recorded, the one step
left is adding its AEAT receipt until the receipt is verified; recording the
filing sends nothing to the AEAT, so the receipt is what shows the AEAT holds
it. A frontend that cannot take a receipt shows the declaration as recorded.

Two steps come from what only a frontend holds, so the read model never states
them and each frontend adds them the same way. Changes held unapplied come
before everything else: that frontend offers :attr:`ModeloFormNextAction.APPLY`.
An apply refused because a value it would keep needs its source fixed first is
retained by the worker for that frontend's own session, and while its changes
still stand the step is resolving it, as :func:`held_prerequisite_step` says.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from .calculation_notes import CHECK_REFUSED_REASONS
from .edit_models import (
    ModeloEditAdmissionResultV1,
    ModeloEditDomainRefusalV1,
    ModeloEditRefusalCode,
    ModeloEditRefusedV1,
)
from .work_form_models import (
    ModeloFormAttention,
    ModeloFormCasillaAddressV1,
    ModeloFormCounts,
    ModeloFormField,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloFormRepeatingBlock,
    ModeloWorkForm,
    section_fields,
)

_REGISTRY_GRADE_FACT: Final[str] = "registry_authority_grade"
"""The admission fact that says the registry rules for the revision stop short of calculation grade."""
_UNRESOLVED_VERDICTS: Final[frozenset[VerificationCompletenessStatus]] = frozenset(
    {VerificationCompletenessStatus.INCOMPLETE, VerificationCompletenessStatus.BLOCKED}
)


class ModeloFormNextAction(StrEnum):
    """The one action a form offers the filer next."""

    #: Apply the changes a frontend holds; offered by that frontend, never by the read model.
    APPLY = "apply"
    FILL = "fill"
    CONFIRM = "confirm"
    CALCULATE = "calculate"
    RECALCULATE = "recalculate"
    RESOLVE = "resolve"
    VERIFY = "verify"
    EXPORT = "export"
    EXPORT_AGAIN = "export_again"
    RECORD_AFTER_FILE = "record_after_file"
    RECORDED = "recorded"


class ModeloFormNextStep(BaseModel):
    """The next action, what it counts, and the dates its words name."""

    model_config = STRICT_FROZEN_CONFIG

    action: ModeloFormNextAction
    #: What the action resolves, counted as the header's chips count it; zero for an action that counts nothing.
    count: int = Field(ge=0)
    #: Whether only findings name the values still to fill in, such as a table's record values, so the
    #: findings list, not the next box, leads to them.
    findings_lead: bool = False
    #: When the filing was recorded, for :attr:`ModeloFormNextAction.RECORDED`, when the revision says.
    recorded_at: datetime | None = None
    #: When the latest file for the AEAT was created, once one was.
    file_created_at: datetime | None = None
    #: For :attr:`ModeloFormNextAction.RECORDED`, whether the recorded filing's AEAT receipt is still to be
    #: added, so that is the step left where a frontend can take a receipt; ``False`` when it is verified or
    #: the read did not say.
    receipt_to_add: bool = False


def inapplicable_pages(form: ModeloWorkForm) -> frozenset[str]:
    """The official pages the read model states do not apply to this filing, by id."""
    return frozenset(page.id for page in form.pages if page.applies is False)


def applicable_fields(form: ModeloWorkForm) -> tuple[ModeloFormField, ...]:
    """Every field the filer may be asked about: all but those on pages the read model states do not apply.

    It is the population :func:`to_do_counts` counts over, so a list of what
    is missing or assumed names exactly the boxes the counts count.
    """
    set_aside = inapplicable_pages(form)
    kept = [
        field
        for page in form.pages
        if page.id not in set_aside
        for section in page.sections
        for field in section_fields(section)
    ]
    kept.extend(form.working_figures)
    kept.extend(item.field for item in form.unplaced)
    return tuple(kept)


def to_do_counts(form: ModeloWorkForm) -> ModeloFormCounts:
    """The form's counts without what the pages that do not apply hold as missing or assumed.

    Those pages ask nothing of the filer, so their boxes are never to do; every
    other count, blockers included, stays as the read model states it.
    """
    set_aside = [page.counts for page in form.pages if page.applies is False]
    if not set_aside:
        return form.counts
    counts = form.counts
    return counts.model_copy(
        update={
            "needs_input": max(counts.needs_input - sum(item.needs_input for item in set_aside), 0),
            "default_to_confirm": max(
                counts.default_to_confirm - sum(item.default_to_confirm for item in set_aside), 0
            ),
        }
    )


def result_fields(form: ModeloWorkForm) -> dict[str, ModeloFormField]:
    """The boxes that state the declaration's result, by casilla, each once."""
    wanted = {str(casilla_id) for casilla_id in form.result_addresses}
    if form.result is not None:
        wanted.add(str(form.result.casilla_id))
    fields: dict[str, ModeloFormField] = {}
    for field in form.fields():
        address = field.address
        if isinstance(address, ModeloFormCasillaAddressV1) and str(address.casilla_id) in wanted:
            fields.setdefault(str(address.casilla_id), field)
    return fields


def is_result_field(form: ModeloWorkForm, field: ModeloFormField) -> bool:
    """Whether ``field`` is one of the boxes that state the declaration's result."""
    address = field.address
    if not isinstance(address, ModeloFormCasillaAddressV1):
        return False
    settling = form.result.casilla_id if form.result is not None else None
    return address.casilla_id == settling or address.casilla_id in form.result_addresses


def failed_results(form: ModeloWorkForm) -> tuple[ModeloFormField, ...]:
    """The result boxes the calculation could not produce that no blocking finding or note already names.

    Each blocks filing on its own: the counts count it once, and the check view
    lists it as its own line.
    """
    named = {issue.box for issue in form.issues if issue.attention is ModeloFormAttention.BLOCKS and issue.box} | {
        note.box for note in form.blocking_calculation_notes if note.box is not None
    }
    return tuple(
        field
        for field in result_fields(form).values()
        if field.origin is ModeloFormOrigin.CALCULATION_FAILED
        and field.box not in named
        and is_result_field(form, field)
    )


def blocking_count(form: ModeloWorkForm) -> int:
    """How many things block filing: the check's blocking findings, the calculation's blocking notes, and failed boxes.

    A result box the calculation could not produce counts once, when neither a
    finding nor a note already names it. The chips, the next action and the
    gate on the file and the recording all count with this.
    """
    blocking = sum(1 for issue in form.issues if issue.attention is ModeloFormAttention.BLOCKS)
    return blocking + len(form.blocking_calculation_notes) + len(failed_results(form))


def confirm_count(form: ModeloWorkForm) -> int:
    """How many values wait for the filer to confirm: the assumed values on pages that apply."""
    return to_do_counts(form).default_to_confirm


def check_count(form: ModeloWorkForm) -> int:
    """How many things are worth checking: the check's warnings and the calculation's notes at that level."""
    findings = sum(1 for issue in form.issues if issue.attention is ModeloFormAttention.CHECK)
    return findings + sum(1 for note in form.calculation_notes if note.attention is ModeloFormAttention.CHECK)


def _record_casillas(form: ModeloWorkForm) -> frozenset[str]:
    """The casillas a table of records carries a value of, in every record."""
    return frozenset(
        casilla_id
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock)
        for casilla_id in block.column_casilla_ids
        if casilla_id is not None
    )


def _missing_boxes(form: ModeloWorkForm) -> frozenset[str]:
    """The casillas of the missing boxes the counts list; none once the declaration is recorded as filed."""
    if form.filing is not None:
        return frozenset[str]()
    return frozenset(
        str(field.address.casilla_id)
        for field in applicable_fields(form)
        if field.origin is ModeloFormOrigin.NEEDS_INPUT and isinstance(field.address, ModeloFormCasillaAddressV1)
    )


def _named_by_a_missing_box(issue: ModeloFormIssue, listed: frozenset[str], records: frozenset[str]) -> bool:
    casilla_id = issue.finding.casilla_id
    if casilla_id is None or str(casilla_id) in records:
        return False
    return str(casilla_id) in listed


def missing_findings(form: ModeloWorkForm) -> int:
    """How many missing values only a finding or a calculation note names, such as a record's value.

    A finding about a box the missing boxes already list is not counted again:
    that box names it.
    """
    listed = _missing_boxes(form)
    records = _record_casillas(form)
    findings = sum(
        1
        for issue in form.issues
        if issue.attention is ModeloFormAttention.MISSING and not _named_by_a_missing_box(issue, listed, records)
    )
    notes = sum(1 for note in form.calculation_notes if note.attention is ModeloFormAttention.MISSING)
    return findings + notes


def missing_count(form: ModeloWorkForm) -> int:
    """How many values the declaration still needs: boxes on pages that apply, and findings no such box answers."""
    return to_do_counts(form).needs_input + missing_findings(form)


def awaiting_the_check(form: ModeloWorkForm) -> int:
    """How many of what blocks filing are calculation notes only the check can decide, the calculation unchecked.

    Once the current calculation is checked the form leaves these notes out
    and the check's own finding of the same cause stands in their place.
    """
    if form.verification is not None:
        return 0
    return sum(1 for note in form.blocking_calculation_notes if note.reason in CHECK_REFUSED_REASONS)


def registry_grade_refusal(admission: ModeloEditAdmissionResultV1) -> bool:
    """Whether the declaration's registry rules fall short of calculation grade, so nothing can be worked out."""
    if not isinstance(admission, ModeloEditRefusedV1):
        return False
    refusal = admission.refusal
    return (
        isinstance(refusal, ModeloEditDomainRefusalV1)
        and refusal.code is ModeloEditRefusalCode.ADMISSION_DENIED
        and _REGISTRY_GRADE_FACT in refusal.facts
    )


def form_next_step(
    form: ModeloWorkForm, *, verified: bool, filed: bool, receipt_confirmed: bool | None = None
) -> ModeloFormNextStep:
    """The one action the form offers next, from its own facts and its lifecycle.

    A declaration recorded as filed is done whatever its form still marks; its
    receipt is still to be added while ``receipt_confirmed`` is ``False``, and
    ``None`` says nothing about it. When nothing blocks and only values are
    missing, the next action is filling them in, never resolving what blocks;
    where findings alone name those values, the findings list leads to them.
    """
    action, count, findings_lead = _next(form, verified=verified, filed=filed)
    recorded = action is ModeloFormNextAction.RECORDED
    return ModeloFormNextStep(
        action=action,
        count=count,
        findings_lead=findings_lead,
        recorded_at=form.filing.recorded_at if recorded and form.filing is not None else None,
        file_created_at=None if form.last_export is None else form.last_export.exported_at,
        receipt_to_add=recorded and receipt_confirmed is False,
    )


def held_prerequisite_step(step: ModeloFormNextStep) -> ModeloFormNextStep:
    """The next step while an apply's retained prerequisite still stands: resolving it, from the findings.

    The worker holds the prerequisite for the frontend session whose apply was
    refused, so only that frontend knows it stands; it counts as the one thing
    that blocks, and the findings list, which names it, leads there.
    """
    return step.model_copy(
        update={"action": ModeloFormNextAction.RESOLVE, "count": 1, "findings_lead": True, "receipt_to_add": False}
    )


def _next(form: ModeloWorkForm, *, verified: bool, filed: bool) -> tuple[ModeloFormNextAction, int, bool]:
    counts = to_do_counts(form)
    to_fill = counts.needs_input
    unboxed = missing_findings(form)
    if filed:
        return ModeloFormNextAction.RECORDED, 0, False
    if form.calculation_revision_id is not None and form.calculation_out_of_date:
        return ModeloFormNextAction.RECALCULATE, 0, False
    if to_fill and not verified:
        return ModeloFormNextAction.FILL, to_fill + unboxed, False
    if counts.default_to_confirm:
        # The count is the chips': the assumed boxes, the only values a filer confirms.
        return ModeloFormNextAction.CONFIRM, confirm_count(form), False
    return _next_after_review(form, unboxed=unboxed, to_fill=to_fill, blocked=counts.blocked, verified=verified)


def _next_after_review(
    form: ModeloWorkForm, *, unboxed: int, to_fill: int, blocked: int, verified: bool
) -> tuple[ModeloFormNextAction, int, bool]:
    blocking = blocking_count(form)
    awaiting = awaiting_the_check(form)
    if verified and not blocking:
        export = form.last_export
        if export is None:
            return ModeloFormNextAction.EXPORT, 0, False
        action = ModeloFormNextAction.RECORD_AFTER_FILE if export.current else ModeloFormNextAction.EXPORT_AGAIN
        return action, 0, False
    if form.calculation_revision_id is None:
        return ModeloFormNextAction.CALCULATE, 0, False
    if awaiting and awaiting == blocking and not blocked:
        # Only the check can say whether what blocks stands, and it also judges
        # whether the values still missing are ones the declaration needs.
        return ModeloFormNextAction.VERIFY, 0, False
    if unboxed and not (blocked or blocking or form.verification is VerificationCompletenessStatus.BLOCKED):
        # Only values are missing, so the step is filling them in, counted as the
        # missing chip counts them; findings name them, so they lead there.
        return ModeloFormNextAction.FILL, to_fill + unboxed, True
    if blocked or blocking or unboxed or form.verification in _UNRESOLVED_VERDICTS:
        # The chips count what blocks filing and the missing values only a
        # finding names; boxes the check marked stand in only when no finding is
        # left to count.
        return ModeloFormNextAction.RESOLVE, (blocking + unboxed) or blocked, False
    return ModeloFormNextAction.VERIFY, 0, False


__all__ = [
    "ModeloFormNextAction",
    "ModeloFormNextStep",
    "applicable_fields",
    "awaiting_the_check",
    "blocking_count",
    "check_count",
    "confirm_count",
    "failed_results",
    "form_next_step",
    "held_prerequisite_step",
    "inapplicable_pages",
    "is_result_field",
    "missing_count",
    "missing_findings",
    "registry_grade_refusal",
    "result_fields",
    "to_do_counts",
]
