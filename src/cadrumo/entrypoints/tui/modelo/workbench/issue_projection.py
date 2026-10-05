"""Project form findings and calculation notes onto the shared issue scale."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from .....application.modelo.calculation_notes import (
    RECORDS_REASONS,
    what_locale_key,
    what_to_do_locale_key,
)
from .....application.modelo.finding_message_text import finding_message_text
from .....application.modelo.source_policy import SourceSurface
from .....application.modelo.work_form_models import (
    ModeloFormCalculationNote,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormIssue,
    ModeloFormPage,
    ModeloFormRepeatingBlock,
    ModeloFormSection,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from .....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
)
from .casilla_list_models import AddressKey
from .editor import open_area_target
from .navigator import presented_form
from .page_items import workbench_pages

if TYPE_CHECKING:
    pass

from .issue_scale import _ATTENTION_LEVELS, _DETAIL_LOCALE_KEYS, IssueLevel, IssueLine, issue_level, unentered_boxes

_BOX_NUMBER: Final[re.Pattern[str]] = re.compile(r"\d{1,4}[A-Z]?")

_RECORDS_NONE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.records.none"

_RECORDS_FIELD_MISSING_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.records.field_missing"

_RECORDS_ACTION_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.action.records_at_source"

_RECORD_VALUE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.where.record_value"

_RECORDS_WHERE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.where.records"

_UNNUMBERED_BOX_LOCALE_KEY: Final[str] = "application.modelo.finding_fact.box_unnumbered"


@dataclass(frozen=True, slots=True)
class _RecordValue:
    """One value every record of a table carries: its heading and whether the table holds any record."""

    heading: str
    has_records: bool


@dataclass(frozen=True, slots=True)
class _FindingTarget:
    box: str
    where: str
    detail: str
    key: AddressKey | None
    field: ModeloFormField | None


def _record_values(form: ModeloWorkForm) -> dict[str, _RecordValue]:
    """Every value a table of records carries, by the casilla its column shows."""
    values: dict[str, _RecordValue] = {}
    for page in form.pages:
        _record_page_values(page, values)
    return values


def _record_page_values(page: ModeloFormPage, values: dict[str, _RecordValue]) -> None:
    for section in page.sections:
        _record_section_values(section, values)


def _record_section_values(section: ModeloFormSection, values: dict[str, _RecordValue]) -> None:
    for block in section.blocks:
        if isinstance(block, ModeloFormRepeatingBlock):
            _record_block_values(block, values)


def _record_block_values(block: ModeloFormRepeatingBlock, values: dict[str, _RecordValue]) -> None:
    for column, casilla_id in zip(block.columns, block.column_casilla_ids, strict=True):
        if casilla_id is not None:
            heading = (
                tr(_RECORD_VALUE_LOCALE_KEY)
                if column.heading.disclosure is ModeloFormTextDisclosure.TECHNICAL
                else column.heading.text
            )
            values.setdefault(casilla_id, _RecordValue(heading=heading, has_records=bool(block.rows)))


def _box_words(form: ModeloWorkForm, records: Mapping[str, _RecordValue]) -> dict[str, str]:
    """How a finding's sentence names each box: its printed number, else the words the form shows it with."""
    words = {casilla_id: value.heading for casilla_id, value in records.items()}
    for field in form.fields():
        if not isinstance(field.address, ModeloFormCasillaAddressV1):
            continue
        if field.box:
            words[str(field.address.casilla_id)] = field.box
        elif field.label.disclosure is not ModeloFormTextDisclosure.TECHNICAL:
            words.setdefault(str(field.address.casilla_id), field.label.text)
    return words


def _field_name(field: ModeloFormField) -> str:
    parts: list[str] = [f"[{field.box}]"] if field.box else []
    if field.label.disclosure is not ModeloFormTextDisclosure.TECHNICAL:
        parts.append(field.label.text)
    return " ".join(parts)


def technical_text(finding: ModeloVerificationFinding) -> str:
    """The finding's codes, facts and references, for the filer who asks for technical details."""
    codes = [
        finding.kind.value,
        finding.severity.value,
        *([] if finding.casilla_id is None else [str(finding.casilla_id)]),
        *([] if finding.expectation_id is None else [str(finding.expectation_id)]),
        *(f"{name}={value}" for name, value in finding.message_facts.items()),
        *(str(ref) for ref in finding.legal_refs),
        *(str(ref) for ref in finding.source_refs),
        finding.message_locale_key,
    ]
    label = tr("tui.modelo.workbench.issues.technical")
    return f"{label}: {' · '.join(codes)}"


def _not_on_form(finding_box: str | None, casilla_id: str) -> tuple[str, str, str]:
    """The box column, where words and detail of a finding whose box the form does not show."""
    number = finding_box or (casilla_id if _BOX_NUMBER.fullmatch(casilla_id) else None)
    if number is None:
        return "·", tr("tui.modelo.workbench.issues.where.not_on_form"), ""
    return number, f"[{number}]", tr("tui.modelo.workbench.issues.box_not_on_form", box=f"[{number}]")


def _record_issue_line(issue: ModeloFormIssue, value: _RecordValue, *, message: str) -> IssueLine:
    """A finding about one value of a table's records, named by that value's heading, leading to the table."""
    finding = issue.finding
    action_key = issue.action_locale_key
    if finding.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA:
        message = tr(_RECORDS_FIELD_MISSING_LOCALE_KEY if value.has_records else _RECORDS_NONE_LOCALE_KEY)
        action_key = _RECORDS_ACTION_LOCALE_KEY
    key = None if finding.casilla_id is None else address_key(ModeloFormCasillaAddressV1(casilla_id=finding.casilla_id))
    return IssueLine(
        level=issue_level(issue),
        box="·",
        where=value.heading,
        message=message,
        action=tr("tui.modelo.workbench.issues.what_to_do", action=tr(action_key)),
        detail=tr(_DETAIL_LOCALE_KEYS[finding.kind]),
        technical=technical_text(finding),
        key=key,
        in_records=True,
    )


def _visible_page_fields(form: ModeloWorkForm) -> dict[AddressKey, ModeloFormField]:
    return {
        address_key(field.address): field for page in workbench_pages(presented_form(form)) for field in page.fields()
    }


def _finding_target(
    issue: ModeloFormIssue,
    *,
    shown: Mapping[AddressKey, ModeloFormField],
    on_pages: frozenset[AddressKey],
    listed: frozenset[AddressKey],
) -> _FindingTarget | None:
    finding = issue.finding
    box = issue.box or "·"
    if finding.casilla_id is None:
        return _declaration_target(issue, box)

    candidate = address_key(ModeloFormCasillaAddressV1(casilla_id=finding.casilla_id))
    if _listed_missing(issue, candidate, listed):
        return None
    field = shown.get(candidate)
    if field is None or candidate not in on_pages:
        return _off_page_target(issue, field)
    return _visible_target(issue, box, field, candidate)


def _declaration_target(issue: ModeloFormIssue, box: str) -> _FindingTarget:
    finding = issue.finding
    locale_key = (
        _RECORDS_WHERE_LOCALE_KEY
        if finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION
        else "tui.modelo.workbench.issues.where.declaration"
    )
    return _FindingTarget(box, tr(locale_key), tr(_DETAIL_LOCALE_KEYS[finding.kind]), None, None)


def _listed_missing(issue: ModeloFormIssue, candidate: AddressKey, listed: frozenset[AddressKey]) -> bool:
    return issue_level(issue) is IssueLevel.MISSING and candidate in listed


def _off_page_target(issue: ModeloFormIssue, field: ModeloFormField | None) -> _FindingTarget:
    finding = issue.finding
    casilla_id = str(finding.casilla_id)
    original_box = issue.box or (None if field is None else field.box)
    box, where, not_shown = _not_on_form(original_box, casilla_id)
    detail = f"{not_shown} {tr(_DETAIL_LOCALE_KEYS[finding.kind])}".strip()
    # A defined off-page field still owns its source area, even though it has no visible row key.
    return _FindingTarget(box, where, detail, None, field)


def _visible_target(issue: ModeloFormIssue, box: str, field: ModeloFormField, candidate: AddressKey) -> _FindingTarget:
    box = field.box or box
    detail = tr(_DETAIL_LOCALE_KEYS[issue.finding.kind])
    return _FindingTarget(box, _field_name(field) or f"[{box}]", detail, candidate, field)


def _finding_line(
    issue: ModeloFormIssue,
    *,
    language: OutputLanguage,
    shown: Mapping[AddressKey, ModeloFormField],
    on_pages: frozenset[AddressKey],
    records: Mapping[str, _RecordValue],
    box_words: Mapping[str, str],
    listed: frozenset[AddressKey],
) -> IssueLine | None:
    finding = issue.finding
    message = finding_message_text(finding, language, box_words=box_words)
    if finding.casilla_id is not None:
        record = records.get(str(finding.casilla_id))
        if record is not None:
            return _record_issue_line(issue, record, message=message)

    target = _finding_target(issue, shown=shown, on_pages=on_pages, listed=listed)
    if target is None:
        return None
    return IssueLine(
        level=issue_level(issue),
        box=target.box,
        where=target.where,
        message=message,
        action=tr("tui.modelo.workbench.issues.what_to_do", action=tr(issue.action_locale_key)),
        detail=target.detail,
        technical=technical_text(finding),
        key=target.key,
        area=None if target.field is None else open_area_target(target.field),
        recalculates=finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION,
    )


def _finding_lines(
    form: ModeloWorkForm,
    *,
    language: OutputLanguage,
    shown: Mapping[AddressKey, ModeloFormField],
    on_pages: frozenset[AddressKey],
    records: Mapping[str, _RecordValue],
    box_words: Mapping[str, str],
    listed: frozenset[AddressKey],
) -> list[IssueLine]:
    lines: list[IssueLine] = []
    for issue in form.issues:
        line = _finding_line(
            issue,
            language=language,
            shown=shown,
            on_pages=on_pages,
            records=records,
            box_words=box_words,
            listed=listed,
        )
        if line is not None:
            lines.append(line)
    return lines


def _note_line(
    note: ModeloFormCalculationNote,
    *,
    on_pages: Mapping[AddressKey, ModeloFormField],
    box_words: Mapping[str, str],
) -> IssueLine:
    """One thing the latest calculation noticed, in the same three parts as a finding."""
    casilla_id = None if note.casilla_id is None else str(note.casilla_id)
    candidate = None if casilla_id is None else address_key(ModeloFormCasillaAddressV1(casilla_id=casilla_id))
    field = None if candidate is None else on_pages.get(candidate)
    box_text = _note_box_text(note, casilla_id, box_words)
    technical_codes = [note.reason, *([] if casilla_id is None else [casilla_id])]
    return IssueLine(
        level=_ATTENTION_LEVELS[note.attention],
        box=note.box or "·",
        where=_note_where(note, field),
        message=tr(what_locale_key(note.reason), box=box_text),
        action=tr(
            "tui.modelo.workbench.issues.what_to_do", action=tr(what_to_do_locale_key(note.reason), box=box_text)
        ),
        detail="",
        technical=f"{tr('tui.modelo.workbench.issues.technical')}: {' · '.join(technical_codes)}",
        key=candidate if field is not None else None,
        area=SourceSurface.LEDGER if note.reason in RECORDS_REASONS else None,
        from_calculation=True,
    )


def _note_box_text(note: ModeloFormCalculationNote, casilla_id: str | None, box_words: Mapping[str, str]) -> str:
    named = None if casilla_id is None else (note.box or box_words.get(casilla_id))
    return named or tr(_UNNUMBERED_BOX_LOCALE_KEY)


def _note_where(note: ModeloFormCalculationNote, field: ModeloFormField | None) -> str:
    if field is not None:
        return _field_name(field) or f"[{note.box}]"
    if note.box is not None:
        return f"[{note.box}]"
    if note.reason in RECORDS_REASONS:
        return tr(_RECORDS_WHERE_LOCALE_KEY)
    return tr("tui.modelo.workbench.issues.where.declaration")


def issue_lines(form: ModeloWorkForm) -> tuple[IssueLine, ...]:
    """The form's findings on the scale, most urgent first, each rendered in the filer's language.

    A missing value's finding whose box the missing values already list is
    left out: that entry names the box, and Enter there leads to it.
    """
    language = OutputLanguage(output_language())
    shown = {address_key(field.address): field for field in form.fields()}
    pages = _visible_page_fields(form)
    on_pages = frozenset(pages)
    records = _record_values(form)
    box_words = _box_words(form, records)
    missing = unentered_boxes(form, IssueLevel.MISSING)
    listed = frozenset(() if missing is None else missing.keys)
    lines = _finding_lines(
        form,
        language=language,
        shown=shown,
        on_pages=on_pages,
        records=records,
        box_words=box_words,
        listed=listed,
    )
    lines.extend(_note_line(note, on_pages=pages, box_words=box_words) for note in form.calculation_notes)
    return _ordered_lines(lines)


def _ordered_lines(lines: list[IssueLine]) -> tuple[IssueLine, ...]:
    order = tuple(IssueLevel)
    return tuple(sorted(lines, key=lambda line: order.index(line.level)))


__all__ = (
    "issue_lines",
    "technical_text",
)
