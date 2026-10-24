"""Words every frontend says about a declaration's boxes: where a value stands, the period, the dates.

A filer reads "1st quarter 2026", "From your records" or "Optional, left at
0", never the transport tokens ``1T``, ``imported`` or ``optional_empty``. The
rules that choose those words live here, once, so a terminal and a window say
the same thing about the same box. Each function renders in the language it is
given, or in the configured output language when none is.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from ...core.aggregation import BindingSourceKind
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation, output_language, tr
from ...core.period import Period, PeriodKind
from .edit_models import ModeloEditNonWritableReason
from .edit_value_grammar import ModeloEditRatioUnit, ratio_unit
from .source_policy import SourceFamily
from .value_presentation import absent_value_text, format_casilla_value
from .work_form_models import (
    ABSENT_FROM_ADMISSION,
    ASKS_FOR_A_VALUE,
    ModeloFormEditability,
    ModeloFormEditClosure,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormPrintedRate,
    ModeloFormRate,
    ModeloFormRateUnit,
    ModeloFormRepeatingBlock,
    ModeloFormRepeatingRow,
    ModeloFormScalar,
    ModeloFormSection,
    ModeloWorkForm,
    holds_zero,
    map_form_fields,
)

PERIOD_WORD_NAMES: Final[tuple[str, ...]] = (
    *(f"quarter_{quarter}" for quarter in range(1, 5)),
    *(f"month_{month:02d}" for month in range(1, 13)),
    "annual",
)
"""Every period named in words; any other period reads as its code and year."""


def _locale(language: OutputLanguage | None) -> str:
    return language.value if language is not None else output_language()


def period_words(period: Period, language: OutputLanguage | None = None) -> str:
    """Name a filing period in the filer's language."""
    code = str(period.code)
    year = period.filing_year
    if period.kind is PeriodKind.QUARTERLY and code[:1].isdigit():
        name = f"quarter_{code[0]}"
    elif period.kind is PeriodKind.MONTHLY and code.isdigit():
        name = f"month_{int(code):02d}"
    elif period.kind is PeriodKind.ANNUAL:
        name = "annual"
    else:
        return f"{code} {year}"
    return tr(f"workspace.modelo.period.{name}", year=year, locale=_locale(language))


def modelo_number(modelo: str, language: OutputLanguage | None = None) -> str:
    """Name a modelo by its number alone, where its title does not fit."""
    return tr("workspace.modelo.modelo_number", modelo=modelo, locale=_locale(language))


def modelo_name(modelo: str, language: OutputLanguage) -> str | None:
    """The modelo's own title without its number, in the filer's language, else in Spanish; ``None`` without one."""
    for locale in (language.value, OutputLanguage.ES.value):
        title = lookup_translation(f"modelo.schema.{modelo}.field.title", locale=locale)
        if title is not None and title:
            return title
    return None


def modelo_title(modelo: str, language: OutputLanguage) -> str:
    """The modelo's number and its own title in the filer's language, else in Spanish, else its number alone."""
    name = modelo_name(modelo, language)
    if name is None:
        return modelo_number(modelo, language)
    return tr("workspace.modelo.modelo_title", modelo=modelo, title=name, locale=language.value)


_NOT_APPLYING_LOCALE_KEYS: Final[Mapping[PeriodKind, str]] = MappingProxyType(
    {
        PeriodKind.QUARTERLY: "workspace.modelo.applicability.quarter",
        PeriodKind.MONTHLY: "workspace.modelo.applicability.month",
        PeriodKind.ANNUAL: "workspace.modelo.applicability.year",
    }
)
_NOT_APPLYING_PERIOD_LOCALE_KEY: Final[str] = "workspace.modelo.applicability.period"


def does_not_apply_words(period: Period, language: OutputLanguage | None = None) -> str:
    """Say that a page does not apply, naming the period the way the filer counts it: this quarter, month or year.

    A period kind without words of its own is said as "this period".
    """
    key = _NOT_APPLYING_LOCALE_KEYS.get(period.kind, _NOT_APPLYING_PERIOD_LOCALE_KEY)
    return tr(key, locale=_locale(language))


def date_text(value: date, language: OutputLanguage) -> str:
    """A date in the order the filer's language writes it, as a box writes one."""
    return format_casilla_value(value, data_type="date", language=language)


def day_text(moment: datetime, language: OutputLanguage) -> str:
    """The day of a moment, in the filer's own time zone, written as :func:`date_text` writes a date."""
    local = moment.astimezone() if moment.tzinfo is not None else moment
    return date_text(local.date(), language)


def origin_words_key(origin: ModeloFormOrigin) -> str:
    """The catalogue key naming one origin in a few words."""
    return f"workspace.modelo.origin.{origin.value}"


#: Origins whose value comes from a source, so their words name the kind of place it is.
SOURCE_WORDED_ORIGINS: Final[tuple[ModeloFormOrigin, ...]] = (
    ModeloFormOrigin.IMPORTED,
    ModeloFormOrigin.NOT_IMPORTED_YET,
    ModeloFormOrigin.OVERRIDES_SOURCE,
)

_FORM_SET_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.IMPORTED, ModeloFormOrigin.INFORMATIONAL}
)
"""Origins whose value, when the form's own design is the source, is the value the form sets."""
_FORM_SET_WORDS_LOCALE_KEY: Final[str] = "workspace.modelo.origin_source.imported.fixed_by_design"
HELD_ZERO_LOCALE_KEYS: Final[Mapping[ModeloFormOrigin, str]] = MappingProxyType(
    {ModeloFormOrigin.OPTIONAL_EMPTY: "workspace.modelo.origin_held_zero.optional_empty"}
)
"""Words for an origin that says nobody entered the box, when the box still holds a zero: never "empty"."""
_AEAT_IMPORTED_ON_LOCALE_KEY: Final[str] = "workspace.modelo.origin_source.aeat_imported_on"


def holds_nothing(value: ModeloFormScalar) -> bool:
    """Whether a box holds no value at all: nothing, an unmarked choice or blank text, but never a zero amount."""
    if value is None or value is False:
        return True
    return isinstance(value, str) and not value.strip()


def set_by_form(field: ModeloFormField) -> bool:
    """Whether the value a field shows is one the official form itself sets."""
    source = field.source
    return field.origin in _FORM_SET_ORIGINS and source is not None and source.family is SourceFamily.FIXED_BY_DESIGN


def aeat_imported_on(form: ModeloWorkForm | None) -> date | None:
    """The day the AEAT tax data the current calculation took values from was imported; ``None`` when not known."""
    data = None if form is None else form.aeat_data
    imported_at = None if data is None else data.imported_at
    if imported_at is None:
        return None
    return imported_at.astimezone().date() if imported_at.tzinfo is not None else imported_at.date()


def _from_aeat_data(field: ModeloFormField) -> bool:
    source = field.source
    return field.origin is ModeloFormOrigin.IMPORTED and source is not None and source.family is SourceFamily.AEAT_DRAFT


_NAMING_CARRY_KINDS: Final[frozenset[BindingSourceKind]] = frozenset(
    {
        BindingSourceKind.PREVIOUS_FILING,
        BindingSourceKind.RELATION_PREFILL,
        BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY,
    }
)
"""Carries whose binding names the earlier declarations it reads for the declaration at hand.

The read model names them through each one's temporal window; a window that
names none for this declaration is a scope-out, so an empty list for one of
these carries means no earlier declaration applies, never that one was not
identified.
"""
_FROM_EARLIER_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.IMPORTED, ModeloFormOrigin.NOT_IMPORTED_YET}
)
"""Origins whose words say where a carried value comes from, so they must not name a declaration that does not exist."""

_NO_EARLIER_WORDS_LOCALE_KEY: Final[str] = "workspace.modelo.origin_source.imported.earlier_filings_none"
_NO_EARLIER_EXPLANATION_LOCALE_KEY: Final[str] = "workspace.modelo.help.origin_no_earlier_declaration"


def no_earlier_filing(field: ModeloFormField) -> bool:
    """Whether a value carried from an earlier declaration has none to carry from: no earlier one applies.

    Only a carry that names its declarations can say so; a value it carries
    is then a zero by rule, not one read from a filing.
    """
    source = field.source
    return (
        field.origin in _FROM_EARLIER_ORIGINS
        and source is not None
        and source.family is SourceFamily.EARLIER_FILINGS
        and source.source_kind in _NAMING_CARRY_KINDS
        and not source.earlier_filings
    )


def origin_explanation(field: ModeloFormField, language: OutputLanguage | None = None) -> str | None:
    """A sentence explaining an origin its few words cannot, or ``None`` when the words suffice.

    A zero carried where no earlier declaration applies is explained as such,
    so the filer does not look for a filing that does not exist.
    """
    if no_earlier_filing(field) and holds_zero(field.value):
        return tr(_NO_EARLIER_EXPLANATION_LOCALE_KEY, locale=_locale(language))
    return None


NAMED_FILING_LOCALE_KEYS: Final[Mapping[ModeloFormOrigin, str]] = MappingProxyType(
    {
        ModeloFormOrigin.IMPORTED: "workspace.modelo.origin_source.imported.named_filing",
        ModeloFormOrigin.NOT_IMPORTED_YET: "workspace.modelo.origin_source.not_imported_yet.named_filing",
        ModeloFormOrigin.OVERRIDES_SOURCE: "workspace.modelo.origin_source.overrides_source.named_filing",
    }
)
"""Words for a value tied to one named earlier declaration, per origin; they take ``{modelo}`` and ``{period}``."""


def origin_source_words_key(origin: ModeloFormOrigin, family: SourceFamily) -> str:
    """The catalogue key naming an origin together with the kind of place its value comes from."""
    return f"workspace.modelo.origin_source.{origin.value}.{family.value}"


FILED_LOCALE_KEYS: Final[Mapping[ModeloFormOrigin, str]] = MappingProxyType(
    {
        ModeloFormOrigin.NEEDS_INPUT: "workspace.modelo.origin_filed.needs_input",
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: "workspace.modelo.origin_filed.default_to_confirm",
    }
)
"""Words for an origin that asks for a value, on a declaration recorded as filed: what the value is, not a request."""


def _special_origin_words(
    field: ModeloFormField,
    *,
    recorded: bool,
    aeat_imported: date | None,
    language: OutputLanguage | None,
) -> str | None:
    locale = _locale(language)
    if recorded and field.origin in FILED_LOCALE_KEYS:
        return tr(FILED_LOCALE_KEYS[field.origin], locale=locale)
    if field.origin in HELD_ZERO_LOCALE_KEYS and holds_zero(field.value):
        return tr(HELD_ZERO_LOCALE_KEYS[field.origin], locale=locale)
    if set_by_form(field):
        return tr(_FORM_SET_WORDS_LOCALE_KEY, locale=locale)
    if aeat_imported is not None and language is not None and _from_aeat_data(field):
        return tr(_AEAT_IMPORTED_ON_LOCALE_KEY, date=date_text(aeat_imported, language), locale=locale)
    if no_earlier_filing(field):
        return tr(_NO_EARLIER_WORDS_LOCALE_KEY, locale=locale)
    return None


def _source_origin_words(field: ModeloFormField, language: OutputLanguage | None) -> str:
    locale = _locale(language)
    source = field.source
    if field.origin not in SOURCE_WORDED_ORIGINS or source is None:
        return tr(origin_words_key(field.origin), locale=locale)
    if source.family is SourceFamily.EARLIER_FILINGS and len(source.earlier_filings) == 1:
        filing = source.earlier_filings[0]
        return tr(
            NAMED_FILING_LOCALE_KEYS[field.origin],
            modelo=filing.modelo,
            period=period_words(filing.period, language),
            locale=locale,
        )
    return tr(origin_source_words_key(field.origin, source.family), locale=locale)


def origin_words(
    field: ModeloFormField,
    *,
    recorded: bool = False,
    aeat_imported: date | None = None,
    language: OutputLanguage | None = None,
) -> str:
    """Say where one field's value stands, in the few words every frontend shows beside it.

    A value from a source names the kind of place, and an earlier declaration by
    its modelo and period when exactly one is known; a value the official form
    sets says so, whatever carries it to the box; any other says its origin. An
    optional box nobody entered that still holds a zero says it was left at
    zero, never that it is empty. On a declaration ``recorded`` as filed nothing
    is asked any more, so a box that would ask for a value says what it holds
    instead. Given the day ``aeat_imported`` the AEAT tax data was imported, a
    value taken from it names that day, written for ``language``.
    """
    special = _special_origin_words(field, recorded=recorded, aeat_imported=aeat_imported, language=language)
    if special is not None:
        return special
    return _source_origin_words(field, language)


NOT_WRITABLE_REASONS: Final[tuple[str, ...]] = (
    *(reason.value for reason in ModeloEditNonWritableReason),
    ABSENT_FROM_ADMISSION,
)
"""Every reason a field that cannot be edited here gives for it."""


def editability_text(field: ModeloFormField, language: OutputLanguage | None = None) -> str:
    """Say what may be done about a field; one that cannot be edited here says why."""
    locale = _locale(language)
    if field.editability is ModeloFormEditability.NOT_WRITABLE and field.not_writable_reason is not None:
        return tr(f"workspace.modelo.not_writable.{field.not_writable_reason}", locale=locale)
    return tr(f"workspace.modelo.editability.{field.editability.value}", locale=locale)


_RATIO_DATA_TYPE: Final[str] = "ratio"
_RATE_UNITS: Final[Mapping[ModeloFormRateUnit, ModeloEditRatioUnit]] = MappingProxyType(
    {ModeloFormRateUnit.FRACTION: ModeloEditRatioUnit.FRACTION}
)
"""How each unit a grounded rate is stated in reads as a percentage."""
_RATE_READINGS: Final[frozenset[ModeloEditRatioUnit]] = frozenset(
    {ModeloEditRatioUnit.PERCENT, ModeloEditRatioUnit.FRACTION}
)
"""The units a ratio's own figure can be read in as a percentage."""
_NO_FIGURE_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.NOT_CALCULATED_YET, ModeloFormOrigin.CALCULATION_FAILED}
)
_ABSENT_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.CLEARED, ModeloFormOrigin.NOT_IMPORTED_YET}
)


def shown_rate(field: ModeloFormField) -> ModeloFormRate | ModeloFormPrintedRate | None:
    """The rate a rate box's row is taxed at: the grounded one, else the one the design prints; ``None`` else."""
    if field.origin is ModeloFormOrigin.NOT_APPLICABLE:
        return None
    return field.grounded_rate or field.printed_rate


def rate_is_value(field: ModeloFormField) -> bool:
    """Whether a box shows its row's rate as its value, as the official form prints it.

    A box the design fixes holds nothing of its own, so it shows its row's
    rate. A calculated rate box in a row grounded on one rate shows that rate
    whatever the base, never a figure worked out from an empty base. Any other
    rate box, typed, failed or empty, or calculated in a row with no grounded
    rate, shows its own value, and its row's rate is said beside it.
    """
    if field.editability is ModeloFormEditability.DESIGN_CONSTANT:
        return shown_rate(field) is not None
    return field.origin is ModeloFormOrigin.CALCULATED and field.grounded_rate is not None


def own_ratio_unit(field: ModeloFormField) -> ModeloEditRatioUnit | None:
    """How a box's own figure reads as a rate: its declared unit, else what its figure and its row's rate establish.

    A ratio whose bounds declare no unit is still read as a rate when the
    figure leaves no doubt: a zero reads the same at any scale, and a figure
    equal to its row's grounded or printed rate at exactly one scale is at that
    scale. Any other undeclared figure keeps its unit undeclared, never guessed.
    ``None`` for a box that is not a ratio.
    """
    maximum = field.constraints.max_value if field.constraints is not None else None
    unit = ratio_unit(field.data_type, maximum)
    if unit is not ModeloEditRatioUnit.UNDECLARED:
        return unit
    value = field.value
    if not isinstance(value, Decimal | int) or isinstance(value, bool):
        return unit
    if holds_zero(value):
        return ModeloEditRatioUnit.PERCENT
    rate = field.grounded_rate or field.printed_rate
    if rate is None:
        return unit
    if value == rate.ratio:
        return ModeloEditRatioUnit.FRACTION
    if value == rate.ratio.scaleb(2):
        return ModeloEditRatioUnit.PERCENT
    return unit


def rate_text(rate: ModeloFormRate | ModeloFormPrintedRate, language: OutputLanguage) -> str:
    """Return a rate as the printed form states it, a percentage in the filer's language."""
    return format_casilla_value(
        rate.ratio, data_type=_RATIO_DATA_TYPE, language=language, ratio_unit=_RATE_UNITS[rate.unit]
    )


def bare_rate(field: ModeloFormField) -> bool:
    """Whether a rate box holds a figure that no declared or grounded unit lets be read as a percentage."""
    return (
        field.data_type == _RATIO_DATA_TYPE
        and field.value is not None
        and not rate_is_value(field)
        and own_ratio_unit(field) not in _RATE_READINGS
    )


def _without_trailing_zeros(value: Decimal) -> Decimal:
    """The same figure without the zeros that end its fraction, and a zero without a sign."""
    if value == 0:
        return Decimal(0)
    return value.quantize(Decimal(1)) if value == value.to_integral_value() else value.normalize()


def field_value_text(field: ModeloFormField, language: OutputLanguage) -> str | None:
    """The figure a box shows, as the filer's language writes it, or ``None`` when it shows none.

    A rate box whose value is its row's rate shows that rate. A box that does
    not apply, waits on a calculation, could not be worked out, was cleared or
    waits on an import shows no figure, whatever it still holds; nor does an
    empty box, a box the design fixes and prints nothing for, or a rate whose
    unit nothing establishes, which a filer could read a hundredfold wrong.
    Each frontend says the absence in its own way, from the box's origin.
    """
    if field.origin is ModeloFormOrigin.NOT_APPLICABLE:
        return None
    rate = shown_rate(field)
    if rate is not None and rate_is_value(field):
        return rate_text(rate, language)
    value = field.value
    if value is None or field.origin in _NO_FIGURE_ORIGINS or field.origin in _ABSENT_ORIGINS or bare_rate(field):
        return None
    unit = own_ratio_unit(field)
    if unit in _RATE_READINGS and isinstance(value, Decimal):
        # A rate reads as the printed form writes one, "2 %" rather than "2.00 %"; dropping zeros rounds nothing.
        value = _without_trailing_zeros(value)
    return format_casilla_value(value, data_type=field.data_type, language=language, ratio_unit=unit)


_CONTEXT_DATA_TYPE: Final[str] = "text"


def context_value_text(value: ModeloFormScalar, language: OutputLanguage, *, period: Period | None = None) -> str:
    """A declared filing-context value in ``language``.

    The period reads in words when the value is the period, a date in the
    language's order, and a value that is not there in the words for nothing.
    """
    if period is not None:
        return period_words(period, language)
    if value is None:
        return absent_value_text(language)
    return format_casilla_value(value, data_type=_CONTEXT_DATA_TYPE, language=language)


def record_value_text(value: ModeloFormScalar, data_type: str, language: OutputLanguage) -> str | None:
    """One value of a table's records as the table shows it; ``None`` when the record holds none."""
    if value is None:
        return None
    return format_casilla_value(value, data_type=data_type, language=language, ratio_unit=ratio_unit(data_type, None))


def _worded_records(block: ModeloFormRepeatingBlock, language: OutputLanguage) -> ModeloFormRepeatingBlock:
    rows: list[ModeloFormRepeatingRow] = [
        row.model_copy(
            update={
                "value_texts": tuple(
                    record_value_text(value, data_type, language)
                    for value, data_type in zip(row.values, block.column_data_types, strict=True)
                )
            }
        )
        for row in block.rows
    ]
    return block.model_copy(update={"rows": tuple(rows)})


def _with_worded_records(form: ModeloWorkForm, language: OutputLanguage) -> ModeloWorkForm:
    def section(part: ModeloFormSection) -> ModeloFormSection:
        blocks = tuple(
            _worded_records(block, language) if isinstance(block, ModeloFormRepeatingBlock) else block
            for block in part.blocks
        )
        return part.model_copy(update={"blocks": blocks})

    pages = tuple(
        page.model_copy(update={"sections": tuple(section(part) for part in page.sections)}) for page in form.pages
    )
    return form.model_copy(update={"pages": pages})


def worded_form(form: ModeloWorkForm) -> ModeloWorkForm:
    """Return ``form`` named in its own language, with every field's value, origin and editability said in it.

    The words are the ones :func:`origin_words`, :func:`origin_explanation` and
    :func:`editability_text` give for the declaration as it stands: recorded as
    filed or not, and naming the day its AEAT tax data was imported.
    """
    language = form.language
    recorded = form.edit_closure is ModeloFormEditClosure.RECORDED_AS_FILED
    imported = aeat_imported_on(form)

    def word(field: ModeloFormField) -> ModeloFormField:
        return field.model_copy(
            update={
                "origin_words": origin_words(field, recorded=recorded, aeat_imported=imported, language=language),
                "origin_explanation": origin_explanation(field, language),
                "editability_words": editability_text(field, language),
                "value_text": field_value_text(field, language),
            }
        )

    worded = map_form_fields(form, word)
    worded = _with_worded_records(worded, language)
    modelo = str(form.modelo)
    not_applying = does_not_apply_words(form.period, language)
    return worded.model_copy(
        update={
            "pages": tuple(
                page.model_copy(update={"applicability_words": not_applying if page.applies is False else None})
                for page in worded.pages
            ),
            "modelo_title": modelo_title(modelo, language),
            "modelo_name": modelo_name(modelo, language),
            "modelo_number": modelo_number(modelo, language),
            "period_words": period_words(form.period, language),
        }
    )


def _require_closed_words() -> None:
    if set(NAMED_FILING_LOCALE_KEYS) != set(SOURCE_WORDED_ORIGINS):
        raise ValueError("every origin worded by its source needs words for a named earlier declaration")
    if frozenset(FILED_LOCALE_KEYS) != ASKS_FOR_A_VALUE:
        raise ValueError("every origin that asks for a value needs words for a declaration recorded as filed")


_require_closed_words()


__all__ = [
    "FILED_LOCALE_KEYS",
    "HELD_ZERO_LOCALE_KEYS",
    "NAMED_FILING_LOCALE_KEYS",
    "NOT_WRITABLE_REASONS",
    "PERIOD_WORD_NAMES",
    "SOURCE_WORDED_ORIGINS",
    "aeat_imported_on",
    "bare_rate",
    "context_value_text",
    "date_text",
    "day_text",
    "does_not_apply_words",
    "editability_text",
    "field_value_text",
    "holds_nothing",
    "modelo_name",
    "modelo_number",
    "modelo_title",
    "no_earlier_filing",
    "origin_explanation",
    "origin_source_words_key",
    "origin_words",
    "origin_words_key",
    "own_ratio_unit",
    "period_words",
    "rate_is_value",
    "rate_text",
    "record_value_text",
    "set_by_form",
    "shown_rate",
    "worded_form",
]
