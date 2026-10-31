"""What the check view lists: every finding and calculation note as one line in words, and the check's verdict.

A line says where the finding sits, what is wrong, what to do about it, a
detail for its kind and its technical codes, so every frontend lists the same
sentences in the same order:

* a finding about a value every record of a table carries is named by that
  value's column heading and leads to the table; a missing value there says
  whether the table holds records at all;
* a finding about a box the form shows names the box by its number and label
  and leads to it; one about a box the form does not show says so, by its
  printed number when it has one;
* a finding about the declaration as a whole, or about the filer's records
  when the calculation is out of date, names that instead;
* a missing value whose box the missing values already list is left out, since
  that list names the box;
* a result box the calculation could not work out, that no blocking finding or
  note already names, blocks filing on its own line, so every block the header
  counts is a line here;
* what the latest calculation noticed follows in the same parts, the records
  it could not place leading to the ledger.

Lines are ordered on the attention scale, most urgent first, keeping the
form's order within a level.

The verdict says what the last check concluded. Changes a frontend holds
unapplied are only known to that frontend, so a passed check carries a second
sentence for it to say while it holds them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, Field

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
)
from .calculation_notes import RECORDS_REASONS, note_fact_text, what_locale_key, what_to_do_locale_key
from .finding_message_text import finding_message_text
from .source_policy import SourceSurface
from .work_form_findings import ModeloFormAttention, ModeloFormIssue
from .work_form_models import (
    ModeloFormAddressV1,
    ModeloFormCalculationNote,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormRepeatingBlock,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
)
from .work_form_next_step import applicable_fields, failed_results

_BOX_NUMBER: Final[re.Pattern[str]] = re.compile(r"\d{1,4}[A-Z]?")

_RECORDS_NONE_LOCALE_KEY: Final[str] = "workspace.modelo.issues.records.none"
_RECORDS_FIELD_MISSING_LOCALE_KEY: Final[str] = "workspace.modelo.issues.records.field_missing"
_RECORDS_ACTION_LOCALE_KEY: Final[str] = "workspace.modelo.issues.action.records_at_source"
_RECORD_VALUE_LOCALE_KEY: Final[str] = "workspace.modelo.issues.where.record_value"
_RECORDS_WHERE_LOCALE_KEY: Final[str] = "workspace.modelo.issues.where.records"
_DECLARATION_WHERE_LOCALE_KEY: Final[str] = "workspace.modelo.issues.where.declaration"
_NOT_ON_FORM_WHERE_LOCALE_KEY: Final[str] = "workspace.modelo.issues.where.not_on_form"
_BOX_NOT_ON_FORM_LOCALE_KEY: Final[str] = "workspace.modelo.issues.box_not_on_form"
_WHAT_TO_DO_LOCALE_KEY: Final[str] = "workspace.modelo.issues.what_to_do"
_TECHNICAL_LOCALE_KEY: Final[str] = "workspace.modelo.issues.technical"
_UNNUMBERED_BOX_LOCALE_KEY: Final[str] = "application.modelo.finding_fact.box_unnumbered"
_FAILED_RESULT_LOCALE_KEY: Final[str] = "workspace.modelo.issues.failed_result"
_FAILED_RESULT_ACTION_LOCALE_KEY: Final[str] = "workspace.modelo.issues.action.failed_result"
_FAILED_RESULT_DETAIL_LOCALE_KEY: Final[str] = "workspace.modelo.issues.detail.calculation_failed"
_FAILED_RESULT_CODE: Final[str] = "calculation_failed"

DETAIL_LOCALE_KEYS: Final[Mapping[ModeloVerificationFindingKind, str]] = MappingProxyType(
    {
        ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA: (
            "workspace.modelo.issues.detail.missing_required_casilla"
        ),
        ModeloVerificationFindingKind.RECONCILIATION_MISMATCH: (
            "workspace.modelo.issues.detail.reconciliation_mismatch"
        ),
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN: (
            "workspace.modelo.issues.detail.cross_period_dependency_unclean"
        ),
        ModeloVerificationFindingKind.BLOCKING_RULE: "workspace.modelo.issues.detail.blocking_rule",
        ModeloVerificationFindingKind.ADVISORY: "workspace.modelo.issues.detail.advisory",
        ModeloVerificationFindingKind.STALE_CALCULATION: "workspace.modelo.issues.detail.stale_calculation",
    }
)
"""The detail each finding kind carries; total over the kinds."""

_VERDICT_LOCALE_KEYS: Final[Mapping[VerificationCompletenessStatus, str]] = MappingProxyType(
    {
        VerificationCompletenessStatus.COMPLETE: "workspace.modelo.issues.verdict.complete",
        VerificationCompletenessStatus.INCOMPLETE: "workspace.modelo.issues.verdict.incomplete",
        VerificationCompletenessStatus.BLOCKED: "workspace.modelo.issues.verdict.blocked",
    }
)
_NOT_CHECKED_LOCALE_KEY: Final[str] = "workspace.modelo.issues.verdict.none"
_SAVED_WITH_CHANGES_LOCALE_KEY: Final[str] = "workspace.modelo.issues.verdict.saved_with_changes"

_ATTENTION_ORDER: Final[tuple[ModeloFormAttention, ...]] = tuple(ModeloFormAttention)


class ModeloFormIssueLine(BaseModel):
    """One finding or calculation note as the check view lists it, in the form's language.

    ``box`` is the official box number, ``None`` when there is none to show.
    ``address`` is where choosing the line leads: the box the form shows, or
    with ``in_records`` the table whose records carry the value; ``None`` when
    the line leads nowhere on the form. ``surface`` is the area of the
    application that owns the value, when one does.
    """

    model_config = STRICT_FROZEN_CONFIG

    level: ModeloFormAttention
    box: str | None
    #: The place in words, never the box number; ``None`` when the box alone says where.
    where: str | None = Field(default=None, min_length=1)
    message: str = Field(min_length=1)
    #: What to do, as one sentence that says so.
    action: str = Field(min_length=1)
    #: What this kind of finding means; ``None`` for a calculation note that states no facts of its own.
    detail: str | None
    #: The codes, facts and references, for the filer who asks for technical details.
    technical: str = Field(min_length=1)
    address: ModeloFormAddressV1 | None
    #: ``address`` is a value of a table's records, so choosing the line opens the table rather than a box.
    in_records: bool = False
    surface: SourceSurface | None = None
    #: The latest calculation noticed this, rather than the check.
    from_calculation: bool = False
    #: Calculating again is what puts this right.
    recalculates: bool = False


class ModeloFormVerdict(BaseModel):
    """What the last check concluded about the declaration, in the form's language.

    ``status`` is ``None`` when the declaration has not been checked.
    ``unapplied_words`` replaces ``words`` while a frontend holds changes not
    yet applied, and exists only after a check that passed.
    """

    model_config = STRICT_FROZEN_CONFIG

    status: VerificationCompletenessStatus | None
    words: str = Field(min_length=1)
    unapplied_words: str | None = None


@dataclass(frozen=True, slots=True)
class _RecordValue:
    """One value every record of a table carries: its heading and whether the table holds any record."""

    heading: str
    has_records: bool


@dataclass(frozen=True, slots=True)
class _Target:
    box: str | None
    where: str | None
    detail: str
    address: ModeloFormAddressV1 | None
    field: ModeloFormField | None


@dataclass(frozen=True, slots=True)
class _Context:
    language: OutputLanguage
    shown: Mapping[tuple[str, str], ModeloFormField]
    records: Mapping[str, _RecordValue]
    box_words: Mapping[str, str]
    listed: frozenset[tuple[str, str]]

    def say(self, key: str, /, **values: object) -> str:
        return tr(key, locale=self.language.value, **values)


def _record_values(form: ModeloWorkForm, language: OutputLanguage) -> dict[str, _RecordValue]:
    """Every value a table of records carries, by the casilla its column shows."""
    values: dict[str, _RecordValue] = {}
    for page in form.pages:
        for section in page.sections:
            for block in section.blocks:
                if isinstance(block, ModeloFormRepeatingBlock):
                    _record_block_values(block, values, language)
    return values


def _record_block_values(
    block: ModeloFormRepeatingBlock, values: dict[str, _RecordValue], language: OutputLanguage
) -> None:
    for column, casilla_id in zip(block.columns, block.column_casilla_ids, strict=True):
        if casilla_id is not None:
            heading = (
                tr(_RECORD_VALUE_LOCALE_KEY, locale=language.value)
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
        if field.box is not None and field.box:
            words[str(field.address.casilla_id)] = field.box
        elif field.label.disclosure is not ModeloFormTextDisclosure.TECHNICAL:
            words.setdefault(str(field.address.casilla_id), field.label.text)
    return words


def _listed_missing(form: ModeloWorkForm) -> frozenset[tuple[str, str]]:
    """The boxes the missing values list names, which no finding repeats."""
    if form.filing is not None:
        return frozenset[tuple[str, str]]()
    return frozenset(
        address_key(field.address) for field in applicable_fields(form) if field.origin is ModeloFormOrigin.NEEDS_INPUT
    )


def _field_words(field: ModeloFormField) -> str | None:
    """The words the form shows a box with; ``None`` when it shows only a technical name."""
    if field.label.disclosure is ModeloFormTextDisclosure.TECHNICAL:
        return None
    return field.label.text or None


def _owning_surface(field: ModeloFormField | None) -> SourceSurface | None:
    if field is None or not field.bindings:
        return None
    surface = field.bindings[0].policy.surface
    return None if surface is SourceSurface.NONE else surface


def _technical(finding: ModeloVerificationFinding, context: _Context) -> str:
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
    return f"{context.say(_TECHNICAL_LOCALE_KEY)}: {' · '.join(codes)}"


def _casilla_address(finding: ModeloVerificationFinding) -> ModeloFormCasillaAddressV1 | None:
    return None if finding.casilla_id is None else ModeloFormCasillaAddressV1(casilla_id=finding.casilla_id)


def _record_line(issue: ModeloFormIssue, value: _RecordValue, message: str, context: _Context) -> ModeloFormIssueLine:
    """A finding about one value of a table's records, named by that value's heading, leading to the table."""
    finding = issue.finding
    action_key = issue.action_locale_key
    if finding.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA:
        message = context.say(_RECORDS_FIELD_MISSING_LOCALE_KEY if value.has_records else _RECORDS_NONE_LOCALE_KEY)
        action_key = _RECORDS_ACTION_LOCALE_KEY
    return ModeloFormIssueLine(
        level=issue.attention,
        box=None,
        where=value.heading,
        message=message,
        action=context.say(_WHAT_TO_DO_LOCALE_KEY, action=context.say(action_key)),
        detail=context.say(DETAIL_LOCALE_KEYS[finding.kind]),
        technical=_technical(finding, context),
        address=_casilla_address(finding),
        in_records=True,
    )


def _declaration_target(issue: ModeloFormIssue, context: _Context) -> _Target:
    kind = issue.finding.kind
    where_key = (
        _RECORDS_WHERE_LOCALE_KEY
        if kind is ModeloVerificationFindingKind.STALE_CALCULATION
        else _DECLARATION_WHERE_LOCALE_KEY
    )
    return _Target(issue.box, context.say(where_key), context.say(DETAIL_LOCALE_KEYS[kind]), None, None)


def _off_form_target(issue: ModeloFormIssue, context: _Context) -> _Target:
    """A finding whose box the form does not show, named by its printed number when it has one."""
    finding = issue.finding
    casilla_id = str(finding.casilla_id)
    number = issue.box or (casilla_id if _BOX_NUMBER.fullmatch(casilla_id) else None)
    kind_detail = context.say(DETAIL_LOCALE_KEYS[finding.kind])
    if number is None:
        return _Target(None, context.say(_NOT_ON_FORM_WHERE_LOCALE_KEY), kind_detail, None, None)
    not_shown = context.say(_BOX_NOT_ON_FORM_LOCALE_KEY, box=f"[{number}]")
    return _Target(number, None, f"{not_shown} {kind_detail}".strip(), None, None)


def _shown_target(issue: ModeloFormIssue, field: ModeloFormField, context: _Context) -> _Target:
    box = field.box or issue.box
    detail = context.say(DETAIL_LOCALE_KEYS[issue.finding.kind])
    return _Target(box, _field_words(field), detail, field.address, field)


def _target(issue: ModeloFormIssue, context: _Context) -> _Target | None:
    finding = issue.finding
    if finding.casilla_id is None:
        return _declaration_target(issue, context)
    candidate = address_key(ModeloFormCasillaAddressV1(casilla_id=finding.casilla_id))
    if issue.attention is ModeloFormAttention.MISSING and candidate in context.listed:
        return None
    field = context.shown.get(candidate)
    if field is None:
        return _off_form_target(issue, context)
    return _shown_target(issue, field, context)


def _finding_line(issue: ModeloFormIssue, context: _Context) -> ModeloFormIssueLine | None:
    finding = issue.finding
    message = finding_message_text(finding, context.language, box_words=context.box_words)
    if finding.casilla_id is not None:
        record = context.records.get(str(finding.casilla_id))
        if record is not None:
            return _record_line(issue, record, message, context)
    target = _target(issue, context)
    if target is None:
        return None
    return ModeloFormIssueLine(
        level=issue.attention,
        box=target.box or None,
        where=target.where,
        message=message,
        action=context.say(_WHAT_TO_DO_LOCALE_KEY, action=context.say(issue.action_locale_key)),
        detail=target.detail,
        technical=_technical(finding, context),
        address=target.address,
        surface=_owning_surface(target.field),
        recalculates=finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION,
    )


def _failed_result_line(field: ModeloFormField, context: _Context) -> ModeloFormIssueLine:
    """A result box the calculation could not work out, which blocks filing until it can."""
    box = field.box or None
    codes = [
        _FAILED_RESULT_CODE,
        *(() if not isinstance(field.address, ModeloFormCasillaAddressV1) else (str(field.address.casilla_id),)),
    ]
    return ModeloFormIssueLine(
        level=ModeloFormAttention.BLOCKS,
        box=box,
        where=_field_words(field),
        message=context.say(_FAILED_RESULT_LOCALE_KEY),
        action=context.say(_WHAT_TO_DO_LOCALE_KEY, action=context.say(_FAILED_RESULT_ACTION_LOCALE_KEY)),
        detail=context.say(_FAILED_RESULT_DETAIL_LOCALE_KEY),
        technical=f"{context.say(_TECHNICAL_LOCALE_KEY)}: {' · '.join(codes)}",
        address=field.address,
    )


def _note_identifiers(
    note: ModeloFormCalculationNote, context: _Context
) -> tuple[ModeloFormField | None, str, list[str]]:
    casilla_id = None if note.casilla_id is None else str(note.casilla_id)
    address = None if note.casilla_id is None else ModeloFormCasillaAddressV1(casilla_id=note.casilla_id)
    field = None if address is None else context.shown.get(address_key(address))
    named = None if casilla_id is None else (note.box or context.box_words.get(casilla_id))
    box_text = named or context.say(_UNNUMBERED_BOX_LOCALE_KEY)
    codes = [note.reason, *([] if casilla_id is None else [casilla_id])]
    return field, box_text, codes


def _note_line(note: ModeloFormCalculationNote, context: _Context) -> ModeloFormIssueLine:
    """One thing the latest calculation noticed, in the same parts as a finding."""
    field, box_text, codes = _note_identifiers(note, context)
    what = context.say(what_locale_key(note.reason), box=box_text)
    # What this note is about comes first, so it is read without opening anything; the kind explains it.
    message, detail = (what, None) if note.fact is None else (note_fact_text(note.fact, locale=context.language), what)
    return ModeloFormIssueLine(
        # A note the filing gate refuses on is listed with what blocks filing, as the counts count it.
        level=ModeloFormAttention.BLOCKS if note.withholds_filing else note.attention,
        box=note.box or None,
        where=_note_where(note, field, context),
        message=message,
        action=context.say(
            _WHAT_TO_DO_LOCALE_KEY, action=context.say(what_to_do_locale_key(note.reason), box=box_text)
        ),
        detail=detail,
        technical=f"{context.say(_TECHNICAL_LOCALE_KEY)}: {' · '.join(codes)}",
        address=None if field is None else field.address,
        surface=SourceSurface.LEDGER if note.reason in RECORDS_REASONS else None,
        from_calculation=True,
    )


def _note_where(note: ModeloFormCalculationNote, field: ModeloFormField | None, context: _Context) -> str | None:
    if field is not None:
        return _field_words(field)
    if note.box is not None:
        return None
    if note.reason in RECORDS_REASONS:
        return context.say(_RECORDS_WHERE_LOCALE_KEY)
    return context.say(_DECLARATION_WHERE_LOCALE_KEY)


def form_issue_lines(form: ModeloWorkForm, language: OutputLanguage) -> tuple[ModeloFormIssueLine, ...]:
    """The form's findings, its failed result boxes, then its calculation notes, as lines, most urgent first."""
    records = _record_values(form, language)
    context = _Context(
        language=language,
        shown={address_key(field.address): field for field in form.fields()},
        records=records,
        box_words=_box_words(form, records),
        listed=_listed_missing(form),
    )
    lines = [line for issue in form.issues if (line := _finding_line(issue, context)) is not None]
    lines.extend(_failed_result_line(field, context) for field in failed_results(form))
    lines.extend(_note_line(note, context) for note in form.calculation_notes)
    return tuple(sorted(lines, key=lambda line: _ATTENTION_ORDER.index(line.level)))


def form_verdict(form: ModeloWorkForm, language: OutputLanguage) -> ModeloFormVerdict:
    """What the last check concluded, in ``language``, or that the declaration has not been checked."""
    status = form.verification
    if status is None:
        return ModeloFormVerdict(status=None, words=tr(_NOT_CHECKED_LOCALE_KEY, locale=language.value))
    return ModeloFormVerdict(
        status=status,
        words=tr(_VERDICT_LOCALE_KEYS[status], locale=language.value),
        unapplied_words=(
            tr(_SAVED_WITH_CHANGES_LOCALE_KEY, locale=language.value)
            if status is VerificationCompletenessStatus.COMPLETE
            else None
        ),
    )


def _require_total_tables() -> None:
    if set(DETAIL_LOCALE_KEYS) != set(ModeloVerificationFindingKind):
        raise ValueError("every finding kind needs a detail")
    if set(_VERDICT_LOCALE_KEYS) != set(VerificationCompletenessStatus):
        raise ValueError("every verification verdict needs its words")


_require_total_tables()

__all__ = [
    "DETAIL_LOCALE_KEYS",
    "ModeloFormIssueLine",
    "ModeloFormVerdict",
    "form_issue_lines",
    "form_verdict",
]
