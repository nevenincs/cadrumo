"""Say what a verification finding found, with every fact written the way the filer reads it.

A finding carries its catalogue key and typed facts: periods as registry tokens
(``4T``, ``0A``), dates in ISO form, boxes by their registry ids, amounts in
their canonical spelling. Interpolated as they are, those tokens reach the
sentence. This module writes each fact in words before the catalogue sees it: a
period by its name, a date in the language's order, an amount with the
language's marks, a box by its printed number or the words the form gives it.
An identifier the filer has no use for, such as a binding, transaction or
predicate id, is never handed to the sentence at all; it stays in the finding
for technical details.

Every fact a producer supplies has one declared kind in
:data:`FINDING_FACT_KINDS`. A fact whose name is not declared there is treated
as an identifier and left out of the sentence, so a new fact never leaks a
token before someone decides how it reads.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...domain.modelos.verification_report import ModeloVerificationFinding
from .value_presentation import format_casilla_value


class FindingFactKind(StrEnum):
    """How one finding fact is written into its sentence."""

    #: A filing period's registry token, written as the period's name without its year.
    PERIOD = "period"
    #: A calendar date in ISO form, written in the language's order.
    DATE = "date"
    #: A casilla id, written as its printed box number or the words the form gives it.
    BOX = "box"
    #: The printed number of the finding's own box, written as the form prints it.
    BOX_NUMBER = "box_number"
    #: A modelo number, kept as its three digits.
    MODELO = "modelo"
    #: A tax year, kept as its four digits.
    YEAR = "year"
    #: An amount of euros, written with the language's marks and two places at least.
    MONEY = "money"
    #: Any other figure, written with the language's marks and its own places.
    NUMBER = "number"
    #: A whole count, written with the language's marks.
    COUNT = "count"
    #: An official code the filer reads on AEAT's own forms, such as a country or income type code.
    OFFICIAL_CODE = "official_code"
    #: An identifier with no meaning to the filer; kept for technical details, never in the sentence.
    TECHNICAL = "technical"


FINDING_FACT_KINDS: Final[Mapping[str, FindingFactKind]] = MappingProxyType(
    {
        # Periods, as registry tokens.
        "period": FindingFactKind.PERIOD,
        "period_code": FindingFactKind.PERIOD,
        "source_period": FindingFactKind.PERIOD,
        "target_period": FindingFactKind.PERIOD,
        # Dates.
        "activity_start_date": FindingFactKind.DATE,
        "transaction_date": FindingFactKind.DATE,
        # Boxes, by casilla id or printed number.
        "casilla_id": FindingFactKind.BOX,
        "box": FindingFactKind.BOX,
        "ingreso_id": FindingFactKind.BOX,
        "reduccion_id": FindingFactKind.BOX,
        "rnt_id": FindingFactKind.BOX,
        "casilla_number": FindingFactKind.BOX_NUMBER,
        # Modelos and years.
        "modelo": FindingFactKind.MODELO,
        "modelo_code": FindingFactKind.MODELO,
        "modelo_id": FindingFactKind.MODELO,
        "source_modelo": FindingFactKind.MODELO,
        "target_modelo": FindingFactKind.MODELO,
        "filing_year": FindingFactKind.YEAR,
        "source_filing_year": FindingFactKind.YEAR,
        "target_filing_year": FindingFactKind.YEAR,
        # Amounts of euros.
        "casilla_value": FindingFactKind.MONEY,
        "computed_value": FindingFactKind.MONEY,
        "current_value_eur": FindingFactKind.MONEY,
        "delta_value_eur": FindingFactKind.MONEY,
        "filed_value": FindingFactKind.MONEY,
        "gap": FindingFactKind.MONEY,
        "ingreso_value": FindingFactKind.MONEY,
        "m303_total": FindingFactKind.MONEY,
        "m349_total": FindingFactKind.MONEY,
        "prior_value_eur": FindingFactKind.MONEY,
        "printed_sum": FindingFactKind.MONEY,
        "redeclaration_increase_threshold_eur": FindingFactKind.MONEY,
        "reduccion_value": FindingFactKind.MONEY,
        "rnt_value": FindingFactKind.MONEY,
        "sublimit": FindingFactKind.MONEY,
        "total_base": FindingFactKind.MONEY,
        # Other figures.
        "declared": FindingFactKind.NUMBER,
        "transaction_amount": FindingFactKind.NUMBER,
        "threshold": FindingFactKind.NUMBER,
        "weighted_count": FindingFactKind.NUMBER,
        # Counts.
        "changed_count": FindingFactKind.COUNT,
        "added_count": FindingFactKind.COUNT,
        "contradicting_invoice_count": FindingFactKind.COUNT,
        "contradicting_ledger_row_count": FindingFactKind.COUNT,
        "removed_count": FindingFactKind.COUNT,
        "settled_prior_accrual_rows": FindingFactKind.COUNT,
        "source_issue_count": FindingFactKind.COUNT,
        "source_modelo_count": FindingFactKind.COUNT,
        "source_ref_count": FindingFactKind.COUNT,
        "unidentified_source_count": FindingFactKind.COUNT,
        # Official codes printed on AEAT's forms.
        "country_code": FindingFactKind.OFFICIAL_CODE,
        "transaction_currency": FindingFactKind.OFFICIAL_CODE,
        "tipo_renta_code": FindingFactKind.OFFICIAL_CODE,
        # Identifiers, for technical details only.
        "anchored": FindingFactKind.TECHNICAL,
        "membership_available": FindingFactKind.TECHNICAL,
        "attestation_profile_path": FindingFactKind.TECHNICAL,
        "attested_periods": FindingFactKind.TECHNICAL,
        "binding_id": FindingFactKind.TECHNICAL,
        "blocker_codes": FindingFactKind.TECHNICAL,
        "condition_id": FindingFactKind.TECHNICAL,
        "declared_grade": FindingFactKind.TECHNICAL,
        "diagnostic_reason_code": FindingFactKind.TECHNICAL,
        "document_id": FindingFactKind.TECHNICAL,
        "error_type": FindingFactKind.TECHNICAL,
        "fact_id": FindingFactKind.TECHNICAL,
        "group_code": FindingFactKind.TECHNICAL,
        "iva_category_code": FindingFactKind.TECHNICAL,
        "mismatch_kind": FindingFactKind.TECHNICAL,
        "origin_code": FindingFactKind.TECHNICAL,
        "origin_ids": FindingFactKind.TECHNICAL,
        "position_key": FindingFactKind.TECHNICAL,
        "predicate_id": FindingFactKind.TECHNICAL,
        "profile_field_id": FindingFactKind.TECHNICAL,
        "reason_code": FindingFactKind.TECHNICAL,
        "requested_grade": FindingFactKind.TECHNICAL,
        "scenario_id": FindingFactKind.TECHNICAL,
        "source_family": FindingFactKind.TECHNICAL,
        "source_kind_code": FindingFactKind.TECHNICAL,
        "source_modelos": FindingFactKind.TECHNICAL,
        "source_ref": FindingFactKind.TECHNICAL,
        "source_ref_ids": FindingFactKind.TECHNICAL,
        "transaction_id": FindingFactKind.TECHNICAL,
        "transaction_ids": FindingFactKind.TECHNICAL,
        "transaction_count": FindingFactKind.TECHNICAL,
        "required_evidence_authority": FindingFactKind.TECHNICAL,
        "unattested_periods": FindingFactKind.TECHNICAL,
    }
)
"""The one kind of every fact a finding producer supplies, which decides how it is written."""

_PERIOD_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "1T": "application.modelo.finding_fact.period.quarter_1",
        "2T": "application.modelo.finding_fact.period.quarter_2",
        "3T": "application.modelo.finding_fact.period.quarter_3",
        "4T": "application.modelo.finding_fact.period.quarter_4",
        "EXT-1T": "application.modelo.finding_fact.period.quarter_1",
        "EXT-2T": "application.modelo.finding_fact.period.quarter_2",
        "EXT-3T": "application.modelo.finding_fact.period.quarter_3",
        "EXT-4T": "application.modelo.finding_fact.period.quarter_4",
        "1P": "application.modelo.finding_fact.period.instalment_1",
        "2P": "application.modelo.finding_fact.period.instalment_2",
        "3P": "application.modelo.finding_fact.period.instalment_3",
        "4P": "application.modelo.finding_fact.period.instalment_4",
        "0A": "application.modelo.finding_fact.period.annual",
        "01": "application.modelo.finding_fact.period.month_01",
        "02": "application.modelo.finding_fact.period.month_02",
        "03": "application.modelo.finding_fact.period.month_03",
        "04": "application.modelo.finding_fact.period.month_04",
        "05": "application.modelo.finding_fact.period.month_05",
        "06": "application.modelo.finding_fact.period.month_06",
        "07": "application.modelo.finding_fact.period.month_07",
        "08": "application.modelo.finding_fact.period.month_08",
        "09": "application.modelo.finding_fact.period.month_09",
        "10": "application.modelo.finding_fact.period.month_10",
        "11": "application.modelo.finding_fact.period.month_11",
        "12": "application.modelo.finding_fact.period.month_12",
    }
)
"""The name of each period a registry token stands for; an OSS extended quarter reads as its quarter."""
_OTHER_PERIOD_LOCALE_KEY: Final[str] = "application.modelo.finding_fact.period.other"
_UNKNOWN_DATE_LOCALE_KEY: Final[str] = "application.modelo.finding_fact.date_unknown"
_UNNUMBERED_BOX_LOCALE_KEY: Final[str] = "application.modelo.finding_fact.box_unnumbered"
_UNKNOWN_MODELO_LOCALE_KEY: Final[str] = "application.modelo.finding_fact.modelo_unknown"
_ABSENT_VALUE_LOCALE_KEY: Final[str] = "application.modelo.finding_fact.value_absent"
_BOX_NUMBER: Final[re.Pattern[str]] = re.compile(r"\d{1,4}[A-Z]?")
_MODELO_NUMBER: Final[re.Pattern[str]] = re.compile(r"\d{3}")
_YEAR: Final[re.Pattern[str]] = re.compile(r"\d{4}")
_MONEY_PLACES: Final[Decimal] = Decimal("0.01")

type FindingFactValue = str | int | bool | Decimal


def _figure(value: FindingFactValue) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        figure = Decimal(value)
    except InvalidOperation:
        return None
    return figure if figure.is_finite() else None


def _in_words(key: str, language: OutputLanguage) -> str:
    return tr(key, locale=language.value)


def _period(value: FindingFactValue, language: OutputLanguage) -> str:
    return _in_words(_PERIOD_LOCALE_KEYS.get(str(value), _OTHER_PERIOD_LOCALE_KEY), language)


def _date(value: FindingFactValue, language: OutputLanguage) -> str:
    try:
        day = date.fromisoformat(str(value))
    except ValueError:
        return _in_words(_UNKNOWN_DATE_LOCALE_KEY, language)
    return format_casilla_value(day, data_type="date", language=language)


def _box(value: FindingFactValue, box_words: Mapping[str, str], language: OutputLanguage) -> str:
    text = str(value)
    words = box_words.get(text)
    if words:
        return words
    if _BOX_NUMBER.fullmatch(text):
        return text
    return _in_words(_UNNUMBERED_BOX_LOCALE_KEY, language)


def _figure_text(value: FindingFactValue, kind: FindingFactKind, language: OutputLanguage) -> str:
    figure = _figure(value)
    if figure is None:
        return _in_words(_ABSENT_VALUE_LOCALE_KEY, language)
    exponent = figure.as_tuple().exponent
    if kind is FindingFactKind.MONEY and isinstance(exponent, int) and exponent > -2:
        figure = figure.quantize(_MONEY_PLACES)
    data_type = "integer" if kind is FindingFactKind.COUNT else "decimal"
    return format_casilla_value(figure, data_type=data_type, language=language)


def _plain(value: FindingFactValue, pattern: re.Pattern[str], fallback_key: str, language: OutputLanguage) -> str:
    text = str(value)
    return text if pattern.fullmatch(text) else _in_words(fallback_key, language)


def fact_text(
    kind: FindingFactKind,
    value: FindingFactValue,
    language: OutputLanguage,
    *,
    box_words: Mapping[str, str],
    own_box: str | None = None,
) -> str | None:
    """Write one fact of ``kind`` the way the filer reads it, or ``None`` for an identifier.

    ``box_words`` names a box by its casilla id, as the form shows it: its
    printed number, or the words the form gives a box that has none.
    ``own_box`` is those words for the finding's own casilla, which a printed
    number fact prefers.
    """
    if kind is FindingFactKind.TECHNICAL:
        return None
    if kind is FindingFactKind.PERIOD:
        return _period(value, language)
    if kind is FindingFactKind.DATE:
        return _date(value, language)
    if kind is FindingFactKind.BOX:
        return _box(value, box_words, language)
    if kind is FindingFactKind.BOX_NUMBER:
        return own_box or _box(value, {}, language)
    if kind is FindingFactKind.MODELO:
        return _plain(value, _MODELO_NUMBER, _UNKNOWN_MODELO_LOCALE_KEY, language)
    if kind is FindingFactKind.YEAR:
        return _plain(value, _YEAR, _ABSENT_VALUE_LOCALE_KEY, language)
    if kind is FindingFactKind.OFFICIAL_CODE:
        return str(value)
    return _figure_text(value, kind, language)


def finding_message_text(
    finding: ModeloVerificationFinding,
    language: OutputLanguage,
    *,
    box_words: Mapping[str, str] | None = None,
) -> str:
    """Render the finding's own sentence in ``language`` with each fact written in words.

    ``box_words`` names boxes by casilla id as the form shows them; a box it
    does not name reads as its printed number when its id is one, and
    otherwise as a box without a number, never as its id.
    """
    words = box_words or {}
    own_box = None if finding.casilla_id is None else words.get(str(finding.casilla_id))
    facts: dict[str, str] = {}
    for name, value in finding.message_facts.items():
        text = fact_text(
            FINDING_FACT_KINDS.get(name, FindingFactKind.TECHNICAL),
            value,
            language,
            box_words=words,
            own_box=own_box,
        )
        if text is not None:
            facts[name] = text
    return tr(finding.message_locale_key, locale=language.value, **facts)


__all__ = ["FINDING_FACT_KINDS", "FindingFactKind", "fact_text", "finding_message_text"]
