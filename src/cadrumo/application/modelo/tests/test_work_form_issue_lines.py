"""The check view's lines say each finding where the form shows it, and the verdict says what the check concluded.

Forms are built by the real builder over the published registry, with real
verification findings carrying real catalogue messages: a Modelo 130 with a
finding on a box it shows, one on a box it does not show and one that the
calculation is out of date; a Modelo 347 whose counterpart table carries the
value a finding names; and a calculation note about records the calculation
could not place. Every sentence is read from the catalogue in the form's
language, so a line in Spanish is the Spanish catalogue's.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ..calculation_notes import (
    CALCULATION_NOTE_ATTENTION,
    PRINTED_BOX_REASONS,
    RECORDS_REASONS,
    note_attention,
    what_locale_key,
)
from ..edit_admission import RESPONSIBLE_OWNER
from ..edit_models import ModeloEditDomainRefusalV1, ModeloEditRefusalCode, ModeloEditRefusedV1
from ..finding_message_text import finding_message_text
from ..source_policy import SourceSurface
from ..work_form_findings import ModeloFormAttention, ModeloFormIssue
from ..work_form_header import attention_counts
from ..work_form_issue_lines import DETAIL_LOCALE_KEYS, form_issue_lines, form_verdict
from ..work_form_models import (
    ModeloFormCalculationNote,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloWorkForm,
    map_form_fields,
    revised_field,
)
from ..work_form_next_step import blocking_count, is_result_field
from ..work_form_service import ModeloWorkFormLoadV1
from ..workbench_projection import project_modelo_workbench_form, restore_modelo_workbench_form
from ..workbench_read import ModeloWorkbenchFormReadV1
from .work_form_fixture import built_form, form_casilla

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MESSAGE_KEY = "application.modelo.findings.oss_evidence_missing"
_LEGAL_REF = "ley-37-1992:art-99"
_ABSENT_BOX = "500"
_RECORD_COLUMN = "contraparte.nif"


def _finding(
    casilla_id: str | None,
    kind: ModeloVerificationFindingKind = ModeloVerificationFindingKind.BLOCKING_RULE,
    severity: ModeloVerificationFindingSeverity = ModeloVerificationFindingSeverity.BLOCKING,
) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=kind,
        severity=severity,
        casilla_id=casilla_id,
        message_locale_key=_MESSAGE_KEY,
        legal_refs=(_LEGAL_REF,),
    )


def _with_issues(form: ModeloWorkForm, *findings: ModeloVerificationFinding) -> ModeloWorkForm:
    return form.model_copy(
        update={
            "verification": VerificationCompletenessStatus.BLOCKED,
            "issues": tuple(ModeloFormIssue(finding=finding) for finding in findings),
        }
    )


def _say(language: OutputLanguage) -> Callable[..., str]:
    def say(key: str, /, **values: object) -> str:
        return tr(key, locale=language.value, **values)

    return say


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
def test_each_finding_reads_where_the_form_shows_it_most_urgent_first(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    say = _say(language)
    built = built_form(operation, "130", 2026, "1T", language=language)
    shown = form_casilla(built, "01")
    stale = _finding(None, ModeloVerificationFindingKind.STALE_CALCULATION, ModeloVerificationFindingSeverity.WARNING)
    absent = _finding(
        _ABSENT_BOX, ModeloVerificationFindingKind.RECONCILIATION_MISMATCH, ModeloVerificationFindingSeverity.WARNING
    )
    blocking = _finding("01")
    form = _with_issues(built, stale, absent, blocking)

    lines = form_issue_lines(form, language)

    assert [line.level for line in lines] == [
        ModeloFormAttention.BLOCKS,
        ModeloFormAttention.CHECK,
        ModeloFormAttention.CHECK,
    ]
    on_box, on_records, off_form = lines
    assert on_box.address == shown.address
    assert on_box.box == shown.box
    # The place is the box's words alone; the box number travels in ``box``, for each frontend to draw.
    assert on_box.where == shown.label.text
    assert on_box.message == finding_message_text(blocking, language)
    assert on_box.detail == say(DETAIL_LOCALE_KEYS[ModeloVerificationFindingKind.BLOCKING_RULE])
    assert on_box.surface is shown.bindings[0].policy.surface
    assert not on_box.recalculates

    assert on_records.address is None
    assert on_records.box is None
    assert on_records.where == say("workspace.modelo.issues.where.records")
    assert on_records.recalculates

    assert off_form.address is None
    assert off_form.box == _ABSENT_BOX
    assert off_form.where is None
    assert off_form.detail is not None
    assert off_form.detail.startswith(say("workspace.modelo.issues.box_not_on_form", box=f"[{_ABSENT_BOX}]"))

    for line in lines:
        assert line.action.startswith(say("workspace.modelo.issues.what_to_do", action="").rstrip())
        assert line.technical.startswith(f"{say('workspace.modelo.issues.technical')}: ")
        assert _MESSAGE_KEY in line.technical
        assert not line.from_calculation and not line.in_records


def _asks_for(casilla_id: str) -> Callable[[ModeloFormField], ModeloFormField]:
    def change(field: ModeloFormField) -> ModeloFormField:
        if isinstance(field.address, ModeloFormCasillaAddressV1) and str(field.address.casilla_id) == casilla_id:
            return revised_field(field, origin=ModeloFormOrigin.NEEDS_INPUT, value=None)
        return field

    return change


def test_a_missing_value_the_missing_list_already_names_is_left_out(operation: PinnedAuthorityOperation) -> None:
    built = map_form_fields(built_form(operation, "130", 2026, "1T"), _asks_for("01"))
    missing = _finding("01", ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA)

    assert form_issue_lines(_with_issues(built, missing), OutputLanguage.EN) == ()
    recorded_elsewhere = form_issue_lines(
        _with_issues(built_form(operation, "130", 2026, "1T"), missing), OutputLanguage.EN
    )
    assert [line.address for line in recorded_elsewhere] == [form_casilla(built, "01").address]


def test_a_value_every_record_carries_leads_to_its_table(operation: PinnedAuthorityOperation) -> None:
    say = _say(OutputLanguage.EN)
    form = _with_issues(
        built_form(operation, "347", 2026, "0A"),
        _finding(_RECORD_COLUMN, ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA),
    )

    (line,) = form_issue_lines(form, OutputLanguage.EN)

    assert line.in_records
    assert line.address == ModeloFormCasillaAddressV1(casilla_id=_RECORD_COLUMN)
    assert line.box is None
    # The built table holds no records yet, so the line says every record needs the value.
    assert line.message == say("workspace.modelo.issues.records.none")
    assert line.action == say(
        "workspace.modelo.issues.what_to_do", action=say("workspace.modelo.issues.action.records_at_source")
    )


def test_a_calculation_note_about_records_leads_to_the_ledger(operation: PinnedAuthorityOperation) -> None:
    say = _say(OutputLanguage.EN)
    reason = sorted(RECORDS_REASONS)[0]
    note = ModeloFormCalculationNote(reason=reason, attention=note_attention(reason, box=None))
    form = built_form(operation, "130", 2026, "1T").model_copy(update={"calculation_notes": (note,)})

    (line,) = form_issue_lines(form, OutputLanguage.EN)

    assert line.from_calculation
    assert line.surface is SourceSurface.LEDGER
    assert line.detail is None
    assert line.address is None
    assert line.where == say("workspace.modelo.issues.where.records")
    assert line.message == say(what_locale_key(reason), box=say("application.modelo.finding_fact.box_unnumbered"))
    assert line.technical == f"{say('workspace.modelo.issues.technical')}: {reason}"


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
def test_the_verdict_says_what_the_check_concluded(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    say = _say(language)
    form = built_form(operation, "130", 2026, "1T", language=language)

    unchecked = form_verdict(form, language)
    passed = form_verdict(form.model_copy(update={"verification": VerificationCompletenessStatus.COMPLETE}), language)
    blocked = form_verdict(form.model_copy(update={"verification": VerificationCompletenessStatus.BLOCKED}), language)

    assert (unchecked.status, unchecked.words, unchecked.unapplied_words) == (
        None,
        say("workspace.modelo.issues.verdict.none"),
        None,
    )
    assert passed.words == say("workspace.modelo.issues.verdict.complete")
    assert passed.unapplied_words == say("workspace.modelo.issues.verdict.saved_with_changes")
    assert blocked.status is VerificationCompletenessStatus.BLOCKED
    assert blocked.unapplied_words is None


def test_the_public_read_carries_the_lines_and_verdict_in_the_forms_language(
    operation: PinnedAuthorityOperation,
) -> None:
    built = built_form(operation, "130", 2026, "1T", language=OutputLanguage.ES)
    form = _with_issues(built, _finding("01"), _finding(None, ModeloVerificationFindingKind.ADVISORY))
    read = ModeloWorkbenchFormReadV1(
        load=ModeloWorkFormLoadV1(form=form, verified=False, filed=False),
        admission=ModeloEditRefusedV1(
            refusal=ModeloEditDomainRefusalV1(
                code=ModeloEditRefusalCode.ADMISSION_DENIED,
                facts=("current_calculation_revision_id",),
                responsible_owner=RESPONSIBLE_OWNER,
                reconsideration_condition="calculate the declaration before editing it",
            )
        ),
        calculation_revision_id=None,
        verification_report_id=None,
        asks_m303_evidence=False,
        asks_modelo_390=False,
        registry_revision_id=form.registry_revision_id,
        tax_id_format=runtime_tax_id_format(authority=operation),
    )

    projection = project_modelo_workbench_form(UUID("13000000-0000-4000-8000-000000000455"), form.work_unit_id, read)

    assert projection.issue_lines == form_issue_lines(form, OutputLanguage.ES)
    assert len(projection.issue_lines) == 2
    assert projection.verdict == form_verdict(form, OutputLanguage.ES)
    restored = restore_modelo_workbench_form(projection)
    assert (restored.issue_lines, restored.verdict) == (projection.issue_lines, projection.verdict)
    assert type(projection).model_validate_json(projection.model_dump_json()) == projection


def _failed_results(form: ModeloWorkForm) -> ModeloWorkForm:
    def change(field: ModeloFormField) -> ModeloFormField:
        return (
            revised_field(field, origin=ModeloFormOrigin.CALCULATION_FAILED) if is_result_field(form, field) else field
        )

    return map_form_fields(form, change)


def _checked_notes() -> tuple[ModeloFormCalculationNote, ...]:
    blocking = next(
        reason for reason, attention in CALCULATION_NOTE_ATTENTION.items() if attention is ModeloFormAttention.BLOCKS
    )
    check = next(
        reason for reason, attention in CALCULATION_NOTE_ATTENTION.items() if attention is ModeloFormAttention.CHECK
    )
    return (
        ModeloFormCalculationNote(reason=check, attention=ModeloFormAttention.CHECK),
        ModeloFormCalculationNote(reason=blocking, attention=ModeloFormAttention.BLOCKS),
        # A working figure's unresolved binding: worth checking on the scale, yet the filing gate refuses on it.
        ModeloFormCalculationNote(
            reason=next(iter(PRINTED_BOX_REASONS)), attention=ModeloFormAttention.CHECK, withholds_filing=True
        ),
    )


@pytest.mark.parametrize(("modelo", "period"), [("130", "1T"), ("303", "1T"), ("347", "0A")])
@pytest.mark.parametrize("with_notes", [False, True])
def test_every_block_and_check_the_header_counts_has_its_line(
    operation: PinnedAuthorityOperation, modelo: str, period: str, with_notes: bool
) -> None:
    built = _failed_results(built_form(operation, modelo, 2026, period))
    form = _with_issues(
        built,
        _finding(None, ModeloVerificationFindingKind.ADVISORY, ModeloVerificationFindingSeverity.WARNING),
    )
    if with_notes:
        form = form.model_copy(update={"calculation_notes": _checked_notes()})

    lines = form_issue_lines(form, OutputLanguage.EN)
    counted = {count.level: count.count for count in attention_counts(form, OutputLanguage.EN, recorded=False)}

    for level in (ModeloFormAttention.BLOCKS, ModeloFormAttention.CHECK):
        assert sum(1 for line in lines if line.level is level) == counted.get(level, 0), level
    assert counted.get(ModeloFormAttention.BLOCKS, 0) == blocking_count(form)
    failed = [
        field
        for field in form.fields()
        if field.origin is ModeloFormOrigin.CALCULATION_FAILED and is_result_field(form, field)
    ]
    if modelo == "130":
        assert failed
    for field in failed:
        (line,) = [line for line in lines if line.address == field.address]
        assert line.level is ModeloFormAttention.BLOCKS
        assert line.box == (field.box or None)
        assert line.message == tr("workspace.modelo.issues.failed_result", locale=OutputLanguage.EN.value)
        assert line.where in {None, field.label.text}
    assert all(line.where is None or "[" not in line.where for line in lines)


def test_a_failed_result_a_blocking_finding_already_names_is_not_listed_twice(
    operation: PinnedAuthorityOperation,
) -> None:
    built = _failed_results(built_form(operation, "130", 2026, "1T"))
    (failed,) = [
        field
        for field in built.fields()
        if field.origin is ModeloFormOrigin.CALCULATION_FAILED and is_result_field(built, field)
    ]
    assert isinstance(failed.address, ModeloFormCasillaAddressV1)
    form = built.model_copy(
        update={
            "verification": VerificationCompletenessStatus.BLOCKED,
            "issues": (ModeloFormIssue(finding=_finding(str(failed.address.casilla_id)), box=failed.box),),
        }
    )

    lines = form_issue_lines(form, OutputLanguage.EN)

    assert [line.level for line in lines] == [ModeloFormAttention.BLOCKS]
    assert blocking_count(form) == 1
