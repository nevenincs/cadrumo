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
from decimal import Decimal
from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ..calculation_note_gate import gate_refuses
from ..calculation_notes import (
    CALCULATION_NOTE_ATTENTION,
    CALCULATION_SCREEN_OUTDATED_REASON,
    FILED_BEFORE_GRADE_CAP_REASON,
    PRINTED_BOX_REASONS,
    RECORDS_REASONS,
    note_attention,
    what_locale_key,
    what_to_do_locale_key,
)
from ..finding_message_text import finding_message_text
from ..source_policy import SourceSurface
from ..withholding_total_reconciliation import WITHHOLDING_TOTAL_MISMATCH_KEY
from ..work_form_declaration_facts import ModeloFormCalculationNote
from ..work_form_field_vocabulary import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
)
from ..work_form_findings import ModeloFormAttention, ModeloFormIssue
from ..work_form_header import attention_counts
from ..work_form_issue_lines import DETAIL_LOCALE_KEYS, ModeloFormIssueLine, form_issue_lines, form_verdict
from ..work_form_models import (
    ModeloFormField,
    ModeloWorkForm,
    map_form_fields,
    revised_field,
)
from ..work_form_next_step import blocking_count, is_result_field
from ..workbench_projection import project_modelo_workbench_form, restore_modelo_workbench_form
from .work_form_fixture import built_form, form_casilla, read_before_calculation

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


@pytest.mark.parametrize("reason", [CALCULATION_SCREEN_OUTDATED_REASON, FILED_BEFORE_GRADE_CAP_REASON])
def test_a_note_the_gate_derives_is_put_right_by_calculating_again(
    operation: PinnedAuthorityOperation, reason: str
) -> None:
    """A revision the gate refuses before it reads any note offers calculating again on its line, and blocks."""
    note = ModeloFormCalculationNote(
        reason=reason, attention=note_attention(reason, box=None), withholds_filing=gate_refuses(reason, None)
    )
    other = ModeloFormCalculationNote(reason="source_issue", attention=note_attention("source_issue", box=None))
    form = built_form(operation, "130", 2026, "1T").model_copy(update={"calculation_notes": (note, other)})

    derived, kept = form_issue_lines(form, OutputLanguage.EN)

    assert derived.from_calculation
    assert derived.level is ModeloFormAttention.BLOCKS
    assert derived.recalculates
    assert kept.from_calculation
    assert not kept.recalculates


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
def test_a_calculation_note_without_facts_says_its_kind_then_what_its_resolver_wrote(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    """The catalogue sentence stays first in the form's language; the resolver's own account follows as written."""
    say = _say(language)
    written = "Liquidation 1T declared deductible input IVA, but the ledger holds none for it."
    note = ModeloFormCalculationNote(
        reason="source_issue", attention=note_attention("source_issue", box=None), message=written
    )
    form = built_form(operation, "130", 2026, "1T", language=language).model_copy(update={"calculation_notes": (note,)})

    (line,) = form_issue_lines(form, language)

    assert line.from_calculation
    assert line.message == say(
        what_locale_key("source_issue"), box=say("application.modelo.finding_fact.box_unnumbered")
    )
    assert line.detail == written


def test_the_public_read_carries_each_notes_written_account(operation: PinnedAuthorityOperation) -> None:
    """The workbench read a frontend draws carries the note's message on the note and on its line."""
    written = "The earlier liquidations this regularisation reads are missing."
    note = ModeloFormCalculationNote(
        reason="source_issue", attention=note_attention("source_issue", box=None), message=written
    )
    form = built_form(operation, "130", 2026, "1T").model_copy(update={"calculation_notes": (note,)})

    projection = project_modelo_workbench_form(
        UUID("13000000-0000-4000-8000-000000000456"), form.work_unit_id, read_before_calculation(form, operation)
    )

    assert [shown.message for shown in projection.form.form.calculation_notes] == [written]
    assert [line.detail for line in projection.issue_lines if line.from_calculation] == [written]
    assert type(projection).model_validate_json(projection.model_dump_json()) == projection


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
    read = read_before_calculation(form, operation)

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


_AT_SOURCE_KEY = "workspace.modelo.issues.action.at_source"
_AT_SOURCE_IF_APPLIES_KEY = "workspace.modelo.issues.action.at_source_if_applies"
_ENTRY_NOTE_REASONS = (
    ("unresolved_binding", _AT_SOURCE_KEY),
    ("unhandled_binding_source", _AT_SOURCE_KEY),
    ("prior_payment_not_deducted", _AT_SOURCE_KEY),
    ("deferred_binding_source", _AT_SOURCE_IF_APPLIES_KEY),
)
_FILER_ENTRY_ACTION = "application.modelo.work_form.finding_action.enter_box_value"
_WITHHOLDING_CREDIT = "0596"
_TYPED_BOX = "0597"


def _locked_beside_typed(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> tuple[ModeloWorkForm, str, str]:
    """The Modelo 100 form with the withholding credit as served (locked to its register) beside a box the filer types.

    The built form carries no edit admission, so the second box is the form's own field
    made typeable through the model's re-derivation rather than a hand-built copy.
    """
    built = built_form(operation, "100", 2025, "0A", language=language)

    def typeable(field: ModeloFormField) -> ModeloFormField:
        if field.box == _TYPED_BOX:
            return revised_field(field, editability=ModeloFormEditability.EDITABLE_VALUE)
        return field

    form = map_form_fields(built, typeable)
    by_box = {field.box: field for field in form.fields()}
    assert by_box[_WITHHOLDING_CREDIT].editability is ModeloFormEditability.LOCKED_SOURCE
    assert not by_box[_WITHHOLDING_CREDIT].takes_typed_value
    assert by_box[_TYPED_BOX].takes_typed_value
    return form, _WITHHOLDING_CREDIT, _TYPED_BOX


def _line_of(lines: tuple[ModeloFormIssueLine, ...], form: ModeloWorkForm, box: str) -> ModeloFormIssueLine:
    address = next(field.address for field in form.fields() if field.box == box)
    return next(line for line in lines if line.address == address)


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize(("reason", "key"), _ENTRY_NOTE_REASONS)
def test_a_note_about_a_box_that_takes_no_typed_value_never_offers_to_type_one(
    operation: PinnedAuthorityOperation, language: OutputLanguage, reason: str, key: str
) -> None:
    say = _say(language)
    form, locked, typed = _locked_beside_typed(operation, language)
    notes = tuple(
        ModeloFormCalculationNote(
            reason=reason,
            casilla_id=field.address.casilla_id,
            box=field.box,
            attention=note_attention(reason, box=field.box),
        )
        for field in form.fields()
        if field.box in (locked, typed) and isinstance(field.address, ModeloFormCasillaAddressV1)
    )
    form = form.model_copy(update={"calculation_notes": notes})

    lines = form_issue_lines(form, language)

    on_locked, on_typed = _line_of(lines, form, locked), _line_of(lines, form, typed)
    assert on_locked.action == say("workspace.modelo.issues.what_to_do", action=say(key))
    assert on_typed.action == say(
        "workspace.modelo.issues.what_to_do", action=say(what_to_do_locale_key(reason), box=typed)
    )
    assert on_locked.surface is SourceSurface.WITHHOLDING


@pytest.mark.parametrize(
    ("message_key", "entry_action", "at_source_key"),
    [
        (
            "application.modelo.findings.xml_required_content_missing",
            "application.modelo.work_form.finding_action.enter_required_statement",
            _AT_SOURCE_KEY,
        ),
        (
            "application.modelo.findings.dt12a_reduccion_possible",
            "application.modelo.work_form.finding_action.check_possible_reduction",
            _AT_SOURCE_IF_APPLIES_KEY,
        ),
    ],
)
def test_a_finding_about_a_box_that_takes_no_typed_value_never_offers_to_type_one(
    operation: PinnedAuthorityOperation, message_key: str, entry_action: str, at_source_key: str
) -> None:
    say = _say(OutputLanguage.EN)
    form, locked, typed = _locked_beside_typed(operation, OutputLanguage.EN)
    findings = tuple(_finding(box).model_copy(update={"message_locale_key": message_key}) for box in (locked, typed))
    flagged = _with_issues(form, *findings)
    assert {issue.action_locale_key for issue in flagged.issues} == {entry_action}

    lines = form_issue_lines(flagged, OutputLanguage.EN)

    assert _line_of(lines, flagged, locked).action == say(
        "workspace.modelo.issues.what_to_do", action=say(at_source_key)
    )
    assert _line_of(lines, flagged, typed).action == say("workspace.modelo.issues.what_to_do", action=say(entry_action))


def test_a_withholding_total_apart_from_the_periodic_returns_opens_both_sides(
    operation: PinnedAuthorityOperation,
) -> None:
    """The line leads to the withholding records behind the summary and to the declarations it was compared with."""
    year = filing_year_envelope().years[-1]
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id="decl.retenciones-total",
        message_locale_key=WITHHOLDING_TOTAL_MISMATCH_KEY,
        message_facts={
            "modelo": "190",
            "filing_year": year,
            "source_modelo": "111",
            "checked_periods": "1T|2T|3T|4T",
            "summary_total": Decimal("760.00"),
            "periodic_total": Decimal("9405.00"),
            "gap": Decimal("8645.00"),
        },
        legal_refs=("rd-439-2007:art-108",),
    )
    form = _with_issues(built_form(operation, "190", year, "0A"), finding)

    (line,) = form_issue_lines(form, OutputLanguage.EN)

    assert line.level is ModeloFormAttention.CHECK
    assert line.surface is SourceSurface.WITHHOLDING
    assert line.compared_surface is SourceSurface.DECLARATIONS
    assert "760.00" in line.message
    assert "9,405.00" in line.message
    assert "8,645.00" in line.message
