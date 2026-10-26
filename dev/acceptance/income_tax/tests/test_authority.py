"""Focused P01 resolver checks for static authority and runtime producer identity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.core.declaracion_idioma import DeclaracionIdioma
from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.domain.calculations.registry.authority_artifact import AuthorityGenerationPin
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportLayoutDefinition,
    ExportLineEnding,
    ExportRecordDefinition,
)

from ..authority import resolve_income_tax_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DICTIONARY_SOURCE = "aeat-dr-100-dictionary"
_LEGAL_REF = "ley-35-2006:art-1"


@dataclass(frozen=True, slots=True)
class _Support:
    floor: int


@dataclass(frozen=True, slots=True)
class _Revision:
    id: str
    export_layouts: tuple[ExportLayoutDefinition, ...]


@dataclass(frozen=True, slots=True)
class _Snapshot:
    revision: _Revision


def _xml_layout() -> ExportLayoutDefinition:
    return ExportLayoutDefinition(
        id="modelo-100-xml-dictionary",
        format=ExportLayoutFormat.XML_DICTIONARY,
        dictionary_source_ref=_DICTIONARY_SOURCE,
        source_refs=(_DICTIONARY_SOURCE,),
        legal_refs=(_LEGAL_REF,),
        aux_idioma=DeclaracionIdioma.CASTELLANO,
    )


def _fixed_width_layout(*, records: bool) -> ExportLayoutDefinition:
    record = ExportRecordDefinition(
        id="modelo-130-record",
        record_type="130",
        order=0,
        encoding=ExportEncoding.ISO_8859_1,
        line_ending=ExportLineEnding.CRLF,
    )
    return ExportLayoutDefinition(
        id="modelo-130-fichero-boe",
        format=ExportLayoutFormat.FIXED_WIDTH,
        source_refs=("aeat-dr-130",),
        legal_refs=(_LEGAL_REF,),
        records=(record,) if records else (),
    )


class _Operation:
    def __init__(self, *, missing_years: frozenset[int] = frozenset(), m130_records: bool = True) -> None:
        self._missing_years = missing_years
        self._m130_records = m130_records

    @property
    def generation(self) -> AuthorityGenerationPin:
        return AuthorityGenerationPin(logical_generation="a" * 64, reader_incarnation="b" * 64)

    def supported_filing_years(self) -> _Support:
        return _Support(floor=2022)

    def snapshot(self, modelo: str, /, *, filing_year: int, period: str) -> _Snapshot:
        if filing_year in self._missing_years:
            raise RegistryError("coordinate unavailable")
        layout = _xml_layout() if modelo == "100" else _fixed_width_layout(records=self._m130_records)
        return _Snapshot(revision=_Revision(id=f"{modelo}-{filing_year}", export_layouts=(layout,)))


def test_latest_mode_keeps_the_latest_completed_year_when_runtime_aux_identity_replaces_static_layout_token() -> None:
    report = resolve_income_tax_authority(_Operation(), as_of=date(2026, 9, 21))

    assert report.latest_completed_year == report.selected_year == 2025
    assert report.support_gap_years == 0
    assert report.authority_generation == "a" * 64
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


def test_xml_layout_cannot_be_declared_without_aux_idioma() -> None:
    with pytest.raises(ValidationError, match="must declare aux_idioma"):
        ExportLayoutDefinition(
            id="modelo-100-xml-dictionary",
            format=ExportLayoutFormat.XML_DICTIONARY,
            dictionary_source_ref=_DICTIONARY_SOURCE,
            source_refs=(_DICTIONARY_SOURCE,),
            legal_refs=(_LEGAL_REF,),
        )


def test_xml_layout_cannot_be_declared_without_the_official_dictionary_source() -> None:
    with pytest.raises(ValidationError, match="must declare dictionary_source_ref"):
        ExportLayoutDefinition(
            id="modelo-100-xml-dictionary",
            format=ExportLayoutFormat.XML_DICTIONARY,
            source_refs=(_DICTIONARY_SOURCE,),
            legal_refs=(_LEGAL_REF,),
            aux_idioma=DeclaracionIdioma.CASTELLANO,
        )


def test_fixed_width_layout_without_records_remains_blocked() -> None:
    report = resolve_income_tax_authority(_Operation(m130_records=False), as_of=date(2026, 9, 21))

    assert report.selected_year == 2025
    assert {
        (export.admission, export.renderability, export.refusal_code)
        for m130 in report.modelo_130
        for export in m130.exports
    } == {("blocked", "no_export_records", "application.filing.export.errors.layout_not_renderable")}


def test_explicit_year_keeps_the_completed_year_gap_visible() -> None:
    report = resolve_income_tax_authority(_Operation(), as_of=date(2026, 9, 21), year=2024)

    assert (report.selection_mode, report.requested_year, report.selected_year) == ("explicit_year", 2024, 2024)
    assert (report.latest_completed_year, report.support_gap_years) == (2025, 1)


def test_latest_mode_reports_a_missing_newest_coordinate_before_selecting_an_older_one() -> None:
    report = resolve_income_tax_authority(_Operation(missing_years=frozenset({2025})), as_of=date(2026, 9, 21))

    assert report.selected_year == 2024
    assert report.support_gap_years == 1
    assert report.excluded_years == ((2025, "RegistryError: coordinate unavailable"),)
