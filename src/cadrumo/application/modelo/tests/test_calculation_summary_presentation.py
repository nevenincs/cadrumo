"""Every string a calculation summary shows, decided from the report alone.

Figure formatting is checked against hand-written expectations in each
language's convention, and the three value states against each other, so a
regression that merged two states or dropped a grouping mark cannot pass by
agreeing with the formatter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import override_locales_root
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.verification_report import VerificationCompletenessStatus
from ..calculation_report import CalculationReportValueState
from ..calculation_summary_presentation import (
    REVISION_STATE_LOCALE_KEYS,
    VERIFICATION_OUTCOME_LOCALE_KEYS,
    CalculationSummaryChromeUnavailableError,
    build_calculation_summary_presentation,
    format_summary_value,
)
from ..value_presentation import LOCALE_NUMBER_FORMATS
from ._calculation_report_fixture import (
    MEASURED_CASILLA,
    NOT_APPLICABLE_CASILLA,
    TAXPAYER_NAME,
    TAXPAYER_TAX_ID,
    ZERO_CASILLA,
    build_fixture_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NBSP = "\u00a0"


@pytest.mark.parametrize(
    ("language", "expected"),
    (
        (OutputLanguage.ES, ("1.234.567,89", "-2.750,40", "0,00", "21", "1.234")),
        (OutputLanguage.CA, ("1.234.567,89", "-2.750,40", "0,00", "21", "1.234")),
        (OutputLanguage.EN, ("1,234,567.89", "-2,750.40", "0.00", "21", "1,234")),
        (
            OutputLanguage.HU,
            (f"1{_NBSP}234{_NBSP}567,89", f"-2{_NBSP}750,40", "0,00", "21", f"1{_NBSP}234"),
        ),
    ),
)
def test_figures_follow_the_language_convention_and_keep_their_places(
    language: OutputLanguage,
    expected: tuple[str, ...],
) -> None:
    values = ("1234567.89", "-2750.40", "0.00", 21, 1234)

    rendered = tuple(format_summary_value(value, language=language, true_text="Y", false_text="N") for value in values)

    assert rendered == expected


def test_non_figure_values_are_shown_as_the_report_spells_them() -> None:
    def shown(value: object) -> str:
        return format_summary_value(value, language=OutputLanguage.ES, true_text="Sí", false_text="No")

    assert shown(True) == "Sí"
    assert shown(False) == "No"
    assert shown("2026-06-30") == "2026-06-30"
    assert shown("01A") == "01A"
    assert shown("1.2.3") == "1.2.3"


def test_every_language_axis_is_enrolled() -> None:
    assert set(LOCALE_NUMBER_FORMATS) == set(OutputLanguage)
    assert set(REVISION_STATE_LOCALE_KEYS) == set(CalculationRevisionState)
    assert set(VERIFICATION_OUTCOME_LOCALE_KEYS) == set(VerificationCompletenessStatus)


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_the_three_value_states_read_differently_in_every_language(
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> None:
    report, _ = build_fixture_report(operation, report_language=language)
    presentation = build_calculation_summary_presentation(
        report,
        csv_sha256="c" * 64,
        signing_key_fingerprint="d" * 64,
        brand="CADRUMO",
    )
    rows = {row.casilla_number: row for section in presentation.sections for row in section.rows}

    measured = rows[MEASURED_CASILLA]
    zero = rows[ZERO_CASILLA]
    not_applicable = rows[NOT_APPLICABLE_CASILLA]
    absent = next(row for row in rows.values() if row.value_state is CalculationReportValueState.ABSENT)
    assert measured.value_text == format_summary_value("10000.00", language=language, true_text="", false_text="")
    assert zero.value_text == format_summary_value("0.00", language=language, true_text="", false_text="")
    assert len({zero.value_text, absent.value_text, not_applicable.value_text}) == 3
    assert presentation.language is language
    assert presentation.notice_body == report.header.local_calculation_notice
    facts = " ".join(fact.value for fact in presentation.facts)
    assert TAXPAYER_TAX_ID in facts
    assert TAXPAYER_NAME in facts
    assert "d" * 64 in {fact.value for fact in presentation.trace}
    assert report.report_sha256 in {fact.value for fact in presentation.trace}
    assert presentation.page_counter(2, 3).count("2") == 1
    assert "3" in presentation.page_counter(2, 3)


def test_section_headings_spell_the_registry_token_without_inventing_a_title(
    operation: PinnedAuthorityOperation,
) -> None:
    report, _ = build_fixture_report(operation)
    presentation = build_calculation_summary_presentation(
        report,
        csv_sha256="c" * 64,
        signing_key_fingerprint="d" * 64,
        brand="CADRUMO",
    )
    tokens = [row.section_path[0] for row in report.rows if row.section_path]

    assert presentation.sections
    for section in presentation.sections:
        spelled = section.heading.replace(" ", "_").lower()
        assert spelled in tokens
    assert sum(len(section.rows) for section in presentation.sections) == len(report.rows)


def test_a_catalogue_without_the_summary_chrome_refuses_the_presentation(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    """Detector teeth: the shipped catalogues carry every string, so absence needs a fixture catalogue."""
    report, _ = build_fixture_report(operation, report_language=OutputLanguage.EN)
    (tmp_path / "en.yml").write_text("application: {}\n", encoding="utf-8")

    with override_locales_root(tmp_path), pytest.raises(CalculationSummaryChromeUnavailableError) as refusal:
        build_calculation_summary_presentation(
            report,
            csv_sha256="c" * 64,
            signing_key_fingerprint="d" * 64,
            brand="CADRUMO",
        )

    assert refusal.value.context is not None
    assert str(refusal.value.context["translation_key"]).startswith("application.modelo.calculation_summary.")
