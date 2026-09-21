"""Focused P01 resolver checks for static authority and runtime producer identity."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.domain.calculations.registry.errors import RegistryError

from ..authority import resolve_income_tax_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _Operation:
    generation = SimpleNamespace(logical_generation="a" * 64)

    def __init__(
        self,
        *,
        missing_years: frozenset[int] = frozenset(),
        aux_idioma: str | None = "E",
        dictionary_source_ref: str | None = "aeat-dr-100-dictionary",
    ) -> None:
        self._missing_years = missing_years
        self._aux_idioma = aux_idioma
        self._dictionary_source_ref = dictionary_source_ref

    def supported_filing_years(self) -> SimpleNamespace:
        return SimpleNamespace(floor=2022)

    def snapshot(self, modelo: str, *, filing_year: int, period: str) -> SimpleNamespace:
        if filing_year in self._missing_years:
            raise RegistryError("coordinate unavailable")
        if modelo == "100":
            layout = SimpleNamespace(
                id="modelo-100-xml-dictionary",
                format=ExportLayoutFormat.XML_DICTIONARY,
                dictionary_source_ref=self._dictionary_source_ref,
                aux_idioma=self._aux_idioma,
                records=(),
            )
        else:
            layout = SimpleNamespace(
                id="modelo-130-fichero-boe",
                format=ExportLayoutFormat.FIXED_WIDTH,
                dictionary_source_ref=None,
                aux_idioma=None,
                records=(object(),),
            )
        revision = SimpleNamespace(id=f"{modelo}-{filing_year}", export_layouts=(layout,))
        return SimpleNamespace(revision=revision)


def test_latest_mode_keeps_the_latest_completed_year_when_runtime_aux_identity_replaces_static_layout_token() -> None:
    report = resolve_income_tax_authority(_Operation(), as_of=date(2026, 9, 21))

    assert report.latest_completed_year == report.selected_year == 2025
    assert report.support_gap_years == 0
    assert [item.revision for item in report.modelo_130] == ["130-2025", "130-2025"]
    assert report.modelo_100 is not None
    (m100_export,) = report.modelo_100.exports
    assert (m100_export.admission, m100_export.refusal_code, m100_export.undeclared_fields) == ("admitted", None, ())


def test_runtime_aux_contract_does_not_require_an_obsolete_static_layout_field() -> None:
    operation = _Operation()
    layout = operation.snapshot("100", filing_year=2025, period="0A").revision.export_layouts[0]

    assert not hasattr(layout, "aux_version")
    report = resolve_income_tax_authority(operation, as_of=date(2026, 9, 21))
    assert report.modelo_100 is not None
    assert report.modelo_100.exports[0].admission == "admitted"


def test_xml_layout_without_declared_aux_idioma_remains_blocked() -> None:
    report = resolve_income_tax_authority(_Operation(aux_idioma=None), as_of=date(2026, 9, 21))

    assert report.modelo_100 is not None
    (m100_export,) = report.modelo_100.exports
    assert (m100_export.admission, m100_export.refusal_code, m100_export.undeclared_fields) == (
        "blocked",
        "application.filing.export_parity.errors.aux_block_undeclared",
        ("aux_idioma",),
    )


def test_xml_layout_without_the_official_dictionary_source_remains_blocked() -> None:
    report = resolve_income_tax_authority(_Operation(dictionary_source_ref=None), as_of=date(2026, 9, 21))

    assert report.modelo_100 is not None
    (m100_export,) = report.modelo_100.exports
    assert (m100_export.admission, m100_export.refusal_code) == (
        "blocked",
        "application.filing.export.errors.layout_not_renderable",
    )


def test_explicit_year_keeps_the_completed_year_gap_visible() -> None:
    report = resolve_income_tax_authority(_Operation(), as_of=date(2026, 9, 21), year=2024)

    assert (report.selection_mode, report.requested_year, report.selected_year) == ("explicit_year", 2024, 2024)
    assert (report.latest_completed_year, report.support_gap_years) == (2025, 1)


def test_latest_mode_reports_a_missing_newest_coordinate_before_selecting_an_older_one() -> None:
    report = resolve_income_tax_authority(_Operation(missing_years=frozenset({2025})), as_of=date(2026, 9, 21))

    assert report.selected_year == 2024
    assert report.support_gap_years == 1
    assert report.excluded_years == ((2025, "RegistryError: coordinate unavailable"),)
