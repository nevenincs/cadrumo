"""Every string a calculation summary's pages show, decided once.

A calculation summary is the report rendered for a person: the same header facts
and casilla rows, set in the report's language with the chrome an accountant
needs to read them. This module decides exactly which words and figures appear;
the PDF adapter decides only where they go on the page. Keeping the two apart is
what lets a verifier holding nothing but the file re-derive the text a genuine
summary shows and compare it with the page, without a renderer.

Everything here is a pure function of the report's canonical JSON form and three
digests. Values are formatted from the JSON spelling of each row's value -- not
from its in-memory Python type -- because the JSON is what the summary embeds and
what a verifier re-reads, so both directions format the same token the same way.

Three value states stay three different texts, not three colours of one: a
proven zero prints as a formatted zero, an absent value and a not-applicable one
each print their own words. A local calculation is never presented as an AEAT
value: the local-calculation statement the report carries is shown on the first
page and again in every footer.

See Also:
    :mod:`cadrumo.application.modelo.calculation_report`:
        The report this module presents.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.filing.software_identity import (
    DEVELOPMENT_MOCK_DEVELOPER_TAX_ID,
    DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER,
    AeatSoftwareIdentityGrade,
)
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from .calculation_report import (
    CalculationReportRowRole,
    CalculationReportValueState,
    ModeloCalculationReport,
    ModeloCalculationReportRow,
)
from .value_presentation import group_decimal_text

TITLE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.title"
SUBTITLE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.subtitle"
NOTICE_TITLE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.notice_title"
IDENTITY_DEVELOPMENT_MOCK_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.identity_development_mock"
IDENTITY_REVIEWED_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.identity_reviewed"
IDENTITY_NONE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.identity_none"
FACT_REVISION_STATE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.fact_revision_state"
FACT_VERIFICATION_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.fact_verification"
FACT_FILING_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.fact_filing"
FACT_EXPORTED_AT_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.fact_exported_at"
FACT_TAXPAYER_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.fact_taxpayer"
VERIFICATION_NONE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.verification_none"
FILING_RECORDED_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.filing_recorded"
FILING_NONE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.filing_none"
LEGEND_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.legend"
COLUMN_CASILLA_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.column_casilla"
COLUMN_CONCEPT_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.column_concept"
COLUMN_AMOUNT_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.column_amount"
VALUE_ABSENT_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.value_absent"
VALUE_NOT_APPLICABLE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.value_not_applicable"
VALUE_TRUE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.value_true"
VALUE_FALSE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.value_false"
SECTION_UNNAMED_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.section_unnamed"
TRACE_HEADING_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_heading"
TRACE_NONE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_none"
TRACE_CALCULATION_REVISION_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_calculation_revision"
TRACE_WORK_UNIT_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_work_unit"
TRACE_VERIFICATION_REPORT_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_verification_report"
TRACE_FILING_RECORD_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_filing_record"
TRACE_REGISTRY_SNAPSHOT_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_registry_snapshot"
TRACE_AUTHORITY_GENERATION_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_authority_generation"
TRACE_LEDGER_SNAPSHOT_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_ledger_snapshot"
TRACE_SOFTWARE_IDENTITY_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_software_identity"
TRACE_REPORT_SHA256_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_report_sha256"
TRACE_CSV_SHA256_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_csv_sha256"
TRACE_SIGNING_KEY_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.trace_signing_key"
SIGNATURE_MEANING_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.signature_meaning"
FOOTER_NOTICE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.footer_notice"
PAGE_COUNTER_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.page_counter"

REVISION_STATE_LOCALE_KEYS: Final[Mapping[CalculationRevisionState, str]] = MappingProxyType(
    {
        CalculationRevisionState.BORRADOR: "application.modelo.calculation_summary.state_borrador",
        CalculationRevisionState.VERIFICADO_COMPLETO: (
            "application.modelo.calculation_summary.state_verificado_completo"
        ),
        CalculationRevisionState.PRESENTADO: "application.modelo.calculation_summary.state_presentado",
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO: (
            "application.modelo.calculation_summary.state_presentado_supersedido"
        ),
        CalculationRevisionState.DESCARTADO: "application.modelo.calculation_summary.state_descartado",
    },
)
"""The label each revision state is shown with; total over the state axis."""

VERIFICATION_OUTCOME_LOCALE_KEYS: Final[Mapping[VerificationCompletenessStatus, str]] = MappingProxyType(
    {
        VerificationCompletenessStatus.COMPLETE: "application.modelo.calculation_summary.verification_complete",
        VerificationCompletenessStatus.INCOMPLETE: "application.modelo.calculation_summary.verification_incomplete",
        VerificationCompletenessStatus.BLOCKED: "application.modelo.calculation_summary.verification_blocked",
    },
)
"""The label each verification verdict is shown with; total over the verdict axis."""

SOFTWARE_IDENTITY_GRADE_LOCALE_KEYS: Final[Mapping[AeatSoftwareIdentityGrade, str]] = MappingProxyType(
    {
        AeatSoftwareIdentityGrade.REVIEWED: "application.modelo.calculation_summary.grade_reviewed",
        AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK: "application.modelo.calculation_summary.grade_development_mock",
    },
)
"""The short label each software-identity grade is shown with in the trace section."""


_SECTION_SEPARATOR: Final[str] = " \u203a "
_REVISION_PREFIX_LENGTH: Final[int] = 16


class CalculationSummaryChromeUnavailableError(CadrumoError):
    """The catalogue carries no text for a string the summary must show.

    Refused rather than rendered with a humanised key: a summary whose notice,
    legend or state labels are missing would misstate what it is.
    """


class CalculationSummaryFact(BaseModel):
    """One labelled fact of the summary's facts or traceability table."""

    model_config = STRICT_FROZEN_CONFIG

    label: str = Field(min_length=1)
    value: str = Field(min_length=1)


class CalculationSummaryRow(BaseModel):
    """One casilla row as it reads on the page."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_number: str = Field(min_length=1)
    label: str
    value_text: str = Field(min_length=1)
    value_state: CalculationReportValueState
    row_role: CalculationReportRowRole


class CalculationSummarySection(BaseModel):
    """One registry section: its heading and its rows, in registry order."""

    model_config = STRICT_FROZEN_CONFIG

    heading: str = Field(min_length=1)
    rows: tuple[CalculationSummaryRow, ...] = Field(min_length=1)


class CalculationSummaryPresentation(BaseModel):
    """Every string the summary's pages show, in the report's language.

    ``page_counter_template`` is the catalogue's own template with ``{page}`` and
    ``{pages}`` still open, because only the layout knows how many pages there
    are; :meth:`page_counter` closes it.
    """

    model_config = STRICT_FROZEN_CONFIG

    language: OutputLanguage
    brand: str = Field(min_length=1)
    title: str = Field(min_length=1)
    subtitle: str = Field(min_length=1)
    notice_title: str = Field(min_length=1)
    notice_body: str = Field(min_length=1)
    software_identity_notice: str = Field(min_length=1)
    facts: tuple[CalculationSummaryFact, ...]
    legend: str = Field(min_length=1)
    column_casilla: str = Field(min_length=1)
    column_concept: str = Field(min_length=1)
    column_amount: str = Field(min_length=1)
    sections: tuple[CalculationSummarySection, ...]
    trace_heading: str = Field(min_length=1)
    trace: tuple[CalculationSummaryFact, ...]
    signature_meaning: str = Field(min_length=1)
    footer_notice: str = Field(min_length=1)
    page_counter_template: str = Field(min_length=1)
    revision_prefix: str = Field(min_length=1)

    def page_counter(self, page: int, pages: int) -> str:
        """Return the ``page n of N`` text for one page."""
        return self.page_counter_template.format(page=page, pages=pages)


class _Chrome:
    """Resolve the summary's catalogue strings in one language, refusing gaps."""

    def __init__(self, language: OutputLanguage) -> None:
        self._language = language

    def text(self, translation_key: str, /, **values: object) -> str:
        template = self._template(translation_key)
        return template.format(**values) if values else template

    def raw(self, translation_key: str, /) -> str:
        return self._template(translation_key)

    def _template(self, translation_key: str) -> str:
        value = lookup_translation(translation_key, locale=self._language.value)
        if value is None:
            raise CalculationSummaryChromeUnavailableError(
                translated_message="application.modelo.errors.calculation_summary_chrome_unavailable",
                context={"report_language": self._language.value, "translation_key": translation_key},
            )
        return value


def format_summary_value(value: object, *, language: OutputLanguage, true_text: str, false_text: str) -> str:
    """Format one row's JSON-spelled value in ``language``.

    A JSON string that spells a decimal number is a figure and gets the
    language's grouping and decimal marks, keeping every fractional digit it has:
    nothing is rounded, so ``0.00`` prints as a zero with its two places. A JSON
    integer is a figure without a fraction. A boolean is a yes or a no. Anything
    else -- a date, a code, a name -- is shown exactly as the report spells it.
    """
    if isinstance(value, bool):
        return true_text if value else false_text
    text = str(value)
    return group_decimal_text(text, language) or text


def _section_heading(section_path: tuple[str, ...], chrome: _Chrome) -> str:
    """Return the heading of one registry section.

    The report carries the registry's section tokens rather than titles, so the
    heading is the token itself, spelled for reading: underscores become spaces
    and the first letter is capitalised. No title is invented.
    """
    if not section_path:
        return chrome.raw(SECTION_UNNAMED_LOCALE_KEY)
    parts = [part.replace("_", " ").strip() for part in section_path]
    return _SECTION_SEPARATOR.join(part[:1].upper() + part[1:] for part in parts if part) or chrome.raw(
        SECTION_UNNAMED_LOCALE_KEY
    )


def _row_value_text(row: ModeloCalculationReportRow, *, language: OutputLanguage, chrome: _Chrome) -> str:
    if row.value_state is CalculationReportValueState.ABSENT:
        return chrome.raw(VALUE_ABSENT_LOCALE_KEY)
    if row.value_state is CalculationReportValueState.NOT_APPLICABLE:
        return chrome.raw(VALUE_NOT_APPLICABLE_LOCALE_KEY)
    return format_summary_value(
        row.model_dump(mode="json")["value"],
        language=language,
        true_text=chrome.raw(VALUE_TRUE_LOCALE_KEY),
        false_text=chrome.raw(VALUE_FALSE_LOCALE_KEY),
    )


def _sections(report: ModeloCalculationReport, *, chrome: _Chrome) -> tuple[CalculationSummarySection, ...]:
    """Group consecutive rows sharing a section path, keeping registry order."""
    language = report.header.report_language
    grouped: list[tuple[tuple[str, ...], list[CalculationSummaryRow]]] = []
    for row in report.rows:
        presented = CalculationSummaryRow(
            casilla_number=row.number,
            label=row.label,
            value_text=_row_value_text(row, language=language, chrome=chrome),
            value_state=row.value_state,
            row_role=row.row_role,
        )
        if grouped and grouped[-1][0] == row.section_path:
            grouped[-1][1].append(presented)
        else:
            grouped.append((row.section_path, [presented]))
    return tuple(
        CalculationSummarySection(heading=_section_heading(path, chrome), rows=tuple(rows)) for path, rows in grouped
    )


def _software_identity_notice(grade: AeatSoftwareIdentityGrade | None, *, chrome: _Chrome) -> str:
    if grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK:
        return chrome.text(
            IDENTITY_DEVELOPMENT_MOCK_LOCALE_KEY,
            program=DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER,
            developer_tax_id=DEVELOPMENT_MOCK_DEVELOPER_TAX_ID,
        )
    if grade is AeatSoftwareIdentityGrade.REVIEWED:
        return chrome.raw(IDENTITY_REVIEWED_LOCALE_KEY)
    return chrome.raw(IDENTITY_NONE_LOCALE_KEY)


def _exported_at_text(report: ModeloCalculationReport) -> str:
    """Return the export instant as ``YYYY-MM-DD HH:MM:SS UTC``: unambiguous in every language."""
    return report.header.exported_at.strftime("%Y-%m-%d %H:%M:%S UTC")


def build_calculation_summary_presentation(
    report: ModeloCalculationReport,
    *,
    csv_sha256: str,
    signing_key_fingerprint: str,
    brand: str,
) -> CalculationSummaryPresentation:
    """Decide every string of ``report``'s summary pages, in the report's language.

    Args:
        report: The report being presented. Its language selects the chrome.
        csv_sha256: Digest of the CSV the summary embeds, printed in the trace.
        signing_key_fingerprint: Fingerprint of the key the summary is signed
            with, printed so a recipient can compare it out of band.
        brand: The product name set in the page's brand rule.

    Raises:
        CalculationSummaryChromeUnavailableError: The catalogue lacks a string
            the summary must show in the report's language.
    """
    header = report.header
    language = header.report_language
    chrome = _Chrome(language)
    none_text = chrome.raw(TRACE_NONE_LOCALE_KEY)
    snapshot = header.registry_snapshot_ref
    facts = (
        CalculationSummaryFact(
            label=chrome.raw(FACT_REVISION_STATE_LOCALE_KEY),
            value=chrome.raw(REVISION_STATE_LOCALE_KEYS[header.calculation_revision_state]),
        ),
        CalculationSummaryFact(
            label=chrome.raw(FACT_VERIFICATION_LOCALE_KEY),
            value=(
                chrome.raw(VERIFICATION_NONE_LOCALE_KEY)
                if header.verification_outcome is None
                else chrome.raw(VERIFICATION_OUTCOME_LOCALE_KEYS[header.verification_outcome])
            ),
        ),
        CalculationSummaryFact(
            label=chrome.raw(FACT_FILING_LOCALE_KEY),
            value=chrome.raw(FILING_NONE_LOCALE_KEY if header.filing_record_id is None else FILING_RECORDED_LOCALE_KEY),
        ),
        CalculationSummaryFact(label=chrome.raw(FACT_EXPORTED_AT_LOCALE_KEY), value=_exported_at_text(report)),
        CalculationSummaryFact(
            label=chrome.raw(FACT_TAXPAYER_LOCALE_KEY),
            value=f"{header.taxpayer_tax_id} \u00b7 {header.taxpayer_name}",
        ),
    )
    trace = (
        (TRACE_CALCULATION_REVISION_LOCALE_KEY, header.calculation_revision_id),
        (TRACE_WORK_UNIT_LOCALE_KEY, header.work_unit_id),
        (TRACE_VERIFICATION_REPORT_LOCALE_KEY, header.verification_report_id),
        (TRACE_FILING_RECORD_LOCALE_KEY, header.filing_record_id),
        (
            TRACE_REGISTRY_SNAPSHOT_LOCALE_KEY,
            f"{snapshot.modelo} \u00b7 {snapshot.revision_id} \u00b7 {snapshot.modelo_year} \u00b7 {snapshot.period}",
        ),
        (TRACE_AUTHORITY_GENERATION_LOCALE_KEY, header.authority_logical_generation),
        (TRACE_LEDGER_SNAPSHOT_LOCALE_KEY, header.ledger_filing_snapshot_fingerprint),
        (
            TRACE_SOFTWARE_IDENTITY_LOCALE_KEY,
            None
            if header.software_identity_grade is None
            else chrome.raw(SOFTWARE_IDENTITY_GRADE_LOCALE_KEYS[header.software_identity_grade]),
        ),
        (TRACE_REPORT_SHA256_LOCALE_KEY, report.report_sha256),
        (TRACE_CSV_SHA256_LOCALE_KEY, csv_sha256),
        (TRACE_SIGNING_KEY_LOCALE_KEY, signing_key_fingerprint),
    )
    return CalculationSummaryPresentation(
        language=language,
        brand=brand,
        title=chrome.text(TITLE_LOCALE_KEY, modelo=str(header.modelo)),
        subtitle=chrome.text(
            SUBTITLE_LOCALE_KEY,
            year=str(header.filing_year),
            period=header.period.registry_token,
            registry_revision=str(snapshot.revision_id),
        ),
        notice_title=chrome.raw(NOTICE_TITLE_LOCALE_KEY),
        notice_body=header.local_calculation_notice,
        software_identity_notice=_software_identity_notice(header.software_identity_grade, chrome=chrome),
        facts=facts,
        legend=chrome.raw(LEGEND_LOCALE_KEY),
        column_casilla=chrome.raw(COLUMN_CASILLA_LOCALE_KEY),
        column_concept=chrome.raw(COLUMN_CONCEPT_LOCALE_KEY),
        column_amount=chrome.raw(COLUMN_AMOUNT_LOCALE_KEY),
        sections=_sections(report, chrome=chrome),
        trace_heading=chrome.raw(TRACE_HEADING_LOCALE_KEY),
        trace=tuple(
            CalculationSummaryFact(label=chrome.raw(key), value=none_text if value is None else str(value))
            for key, value in trace
        ),
        signature_meaning=chrome.raw(SIGNATURE_MEANING_LOCALE_KEY),
        footer_notice=chrome.raw(FOOTER_NOTICE_LOCALE_KEY),
        page_counter_template=chrome.raw(PAGE_COUNTER_LOCALE_KEY),
        revision_prefix=header.calculation_revision_id[:_REVISION_PREFIX_LENGTH],
    )


__all__ = [
    "REVISION_STATE_LOCALE_KEYS",
    "SOFTWARE_IDENTITY_GRADE_LOCALE_KEYS",
    "VERIFICATION_OUTCOME_LOCALE_KEYS",
    "CalculationSummaryChromeUnavailableError",
    "CalculationSummaryFact",
    "CalculationSummaryPresentation",
    "CalculationSummaryRow",
    "CalculationSummarySection",
    "build_calculation_summary_presentation",
    "format_summary_value",
]
