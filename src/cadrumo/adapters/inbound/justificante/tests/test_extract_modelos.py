"""Regression tests for per-modelo period / ejercicio extraction.

Real-world AEAT text shapes for Modelos 130, 303, 111, 190, 390 differ from
the generated fixture PDFs in two ways:

* Quarterly modelos (130, 111, ...) print the period in a positional layout
  that pdfplumber merges as ``[<NIF>] <YYYY> <token>`` on a single line,
  with no "Período" label nearby.
* The Modelo 190 *Resumen anual* layout prints the ejercicio with a
  parenthetical leader: ``Ejercicio (con 4 cifras) ....... 2024``.

These tests feed representative text shapes with redacted PII through
:func:`cadrumo.adapters.inbound.justificante._extract.extract_justificante`
so the fallbacks are exercised without committing real PDF fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.period import Period
from .....tests.aeat_literal_fixtures import justificante_cotejo_url
from .._extract import extract_justificante

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


# Synthetic PDF text shapes derived from live captures with PII
# token-replaced (Y1234567X -> Y0000001S, real CSVs -> SANITIZED...).
# Each block ends with a verification URL so the URL extractor
# always succeeds.
_SHAPE_M130_QUARTERLY = (
    "INFORMACION DE LA PRESENTACION DE LA DECLARACION\n"
    "Modelo 130\n"
    "Presentacion realizada el: 05-07-2024 a las 16:28:37\n"
    "Expediente/Referencia (n registro asignado): 999913013520146Z\n"
    "Codigo Seguro de Verificacion: SANITIZED1302024\n"
    "Numero de justificante: 1305124255671\n"
    "NIF Presentador: Y0000001S\n"
    "Y0000001S 2024 1T\n"
    f"{justificante_cotejo_url('SANITIZED1302024')}\n"
)

_SHAPE_M303_QUARTERLY = (
    "INFORMACION DE LA PRESENTACION DE LA DECLARACION\n"
    "Modelo 303\n"
    "Presentacion realizada el: 06-07-2024 a las 11:58:02\n"
    "Expediente/Referencia (n registro asignado): 999930313520389Q\n"
    "Codigo Seguro de Verificacion: SANITIZED3032024\n"
    "Numero de justificante: 3050124211223\n"
    "NIF Presentador: Y0000001S\n"
    "Sujeto pasivo (2) Ejercicio 2024 Periodo 1T\n"
    f"{justificante_cotejo_url('SANITIZED3032024')}\n"
)

_SHAPE_M111_QUARTERLY = (
    "INFORMACION DE LA PRESENTACION DE LA DECLARACION\n"
    "Modelo 111\n"
    "Presentacion realizada el: 05-07-2024 a las 16:24:03\n"
    "Expediente/Referencia (n registro asignado): 999911113520259N\n"
    "Codigo Seguro de Verificacion: SANITIZED1112024\n"
    "Numero de justificante: 1114264149320\n"
    "NIF Presentador: Y0000001S\n"
    "MINISTERIO DE HACIENDA\n"
    "2024 1T\n"
    f"{justificante_cotejo_url('SANITIZED1112024')}\n"
)

_SHAPE_M190_RESUMEN_ANUAL = (
    "INFORMACION DE LA PRESENTACION DE LA DECLARACION\n"
    "Modelo 190\n"
    "Presentacion realizada el: 27-03-2025 a las 20:31:00\n"
    "Expediente/Referencia (n registro asignado): 9999190003820000301503\n"
    "Codigo Seguro de Verificacion: SANITIZED1902024\n"
    "Numero de justificante: 1905117526322\n"
    "NIF Presentador: Y0000001S\n"
    "Resumen anual\n"
    "Declarante\n"
    "Ejercicio (con 4 cifras) ....... 2024\n"
    f"{justificante_cotejo_url('SANITIZED1902024')}\n"
)

_SHAPE_M390_ANUAL = (
    "INFORMACION DE LA PRESENTACION DE LA DECLARACION\n"
    "Modelo 390\n"
    "Presentacion realizada el: 31-01-2024 a las 01:44:22\n"
    "Expediente/Referencia (n registro asignado): 999939013520264K\n"
    "Codigo Seguro de Verificacion: SANITIZED3902023\n"
    "Numero de justificante: 3905124211226\n"
    "NIF Presentador: Y0000001S\n"
    "Sujeto pasivo Devengo\n"
    "Ejercicio 2023 Declaracion sustitutiva\n"
    f"{justificante_cotejo_url('SANITIZED3902023')}\n"
)

# English-language layout — AEAT serves these when the user files
# via the English sede UI. Distinct labels:
#   * "FORM <N>" / "Form <N>" instead of "MODELO <N>"
#   * "Secure Verification Code: <csv>" instead of "Codigo Seguro"
#   * "Filed on DD-MM-YYYY at HH:MM:SS" instead of "Presentacion"
#   * "Tax identification number(NIF)of filer:" — value before label
#   * "Financial year <YYYY>" instead of "Ejercicio"
_SHAPE_M130_2021_ENGLISH = (
    "INFORMATION ON FILING THE TAX RETURN\n"
    "FORM 130\n"
    "Register\n"
    "Filed on 31-01-2022 at 22:00:40\n"
    "202113013520603N\n"
    "File/Reference (assigned registration no.):\n"
    "Secure Verification Code: SANITIZED1302021\n"
    "Filer\n"
    "Y0000001S\n"
    "Tax identification number(NIF)of filer:\n"
    "APELLIDO APELLIDO NOMBRE\n"
    "Surname(s) and first name/Company name:\n"
    "Y0000001S 2021 4T\n"  # positional NIF + year + period block
    f"{justificante_cotejo_url('SANITIZED1302021')}\n"
)

_SHAPE_M390_2021_ENGLISH = (
    "INFORMATION ON FILING THE TAX RETURN\n"
    "FORM 390\n"
    "Register\n"
    "Filed on 31-01-2022 at 20:46:29\n"
    "202139013520268G\n"
    "File/Reference (assigned registration no.):\n"
    "Secure Verification Code: SANITIZED3902021\n"
    "Filer\n"
    "Y0000001S\n"
    "Tax identification number(NIF)of filer:\n"
    "Liability\n"
    "Financial year 2021 Replacement tax return\n"
    f"{justificante_cotejo_url('SANITIZED3902021')}\n"
)


def _pdf_path(tmp_path: Path, modelo: str) -> Path:
    """Return a writable PDF path for text-extraction tests."""
    pdf = tmp_path / f"m{modelo}.pdf"
    pdf.write_bytes(b"%PDF-1.4 test-pdf\n%%EOF\n")
    return pdf


class TestPeriodPositionalQuarterly:
    """Quarterly modelos lay out the period as ``<YYYY> <token>``."""

    def test_modelo_130_period_positional(self, tmp_path: Path) -> None:
        """Modelo 130 binds period via the positional ``<NIF> <year> <token>`` line."""
        record = extract_justificante(_SHAPE_M130_QUARTERLY, _pdf_path(tmp_path, "130"))
        assert record.modelo == "130"
        assert record.period == Period.from_year_and_code(2024, "1T")
        assert record.tax_id == "Y0000001S"
        assert record.csv == "SANITIZED1302024"

    def test_modelo_303_labelled_period(self, tmp_path: Path) -> None:
        """Modelo 303 binds period via the labelled ``Periodo`` shape."""
        record = extract_justificante(_SHAPE_M303_QUARTERLY, _pdf_path(tmp_path, "303"))
        assert record.modelo == "303"
        assert record.period == Period.from_year_and_code(2024, "1T")
        assert record.ejercicio == "2024"

    def test_modelo_111_period_positional(self, tmp_path: Path) -> None:
        """Modelo 111 also relies on the positional period shape."""
        record = extract_justificante(_SHAPE_M111_QUARTERLY, _pdf_path(tmp_path, "111"))
        assert record.modelo == "111"
        assert record.period == Period.from_year_and_code(2024, "1T")


class TestPeriodPositionalRejectsMonthlyNoise:
    """The positional-period regex must not over-match casilla numbers.

    Captured edge case (M190 *Resumen anual* receipts): pdfplumber
    emits ``Ejercicio (con 4 cifras) ....... 2024 01 enero`` where
    the trailing ``01`` is a casilla number, not a monthly period.
    An earlier ``0[1-9]|1[0-2]`` alternation incorrectly bound
    ``period="01"`` to that line, mislabelling the annual filing.
    The regex now accepts only ``0A`` or ``[1-4]T``; monthly
    modelos can be added back when one enters the corpus and a
    real layout is available to validate against.
    """

    def test_resumen_anual_does_not_match_casilla_number(self, tmp_path: Path) -> None:
        """The positional regex must not bind ``period="01"`` on a Resumen anual line."""
        text = (
            "INFORMACION DE LA PRESENTACION DE LA DECLARACION\n"
            "Modelo 190\n"
            "Presentacion realizada el: 27-03-2025 a las 20:31:00\n"
            "Codigo Seguro de Verificacion: SANITIZED1902024\n"
            "NIF Presentador: Y0000001S\n"
            "Resumen anual\n"
            "Ejercicio (con 4 cifras) ....... 2024 01 enero\n"
            f"{justificante_cotejo_url('SANITIZED1902024')}\n"
        )
        record = extract_justificante(text, _pdf_path(tmp_path, "190"))
        assert record.period == Period.from_year_and_code(2024, "0A")
        assert record.ejercicio == "2024"

    def test_quarterly_modelos_still_match(self, tmp_path: Path) -> None:
        """Tightening the alternation does not break the quarterly path."""
        text = (
            "INFORMACION DE LA PRESENTACION DE LA DECLARACION\n"
            "Modelo 130\n"
            "Codigo Seguro de Verificacion: SANITIZED1302024\n"
            "Presentacion realizada el: 05-07-2024 a las 16:28:37\n"
            "NIF Presentador: Y0000001S\n"
            "Y0000001S 2024 1T\n"
            f"{justificante_cotejo_url('SANITIZED1302024')}\n"
        )
        record = extract_justificante(text, _pdf_path(tmp_path, "130"))
        assert record.period == Period.from_year_and_code(2024, "1T")


class TestEjercicioLooseShape:
    """Resumen anuales (M190) print ejercicio with a parenthetical leader."""

    def test_modelo_190_ejercicio_loose(self, tmp_path: Path) -> None:
        """The loose-leader regex captures ``Ejercicio (con 4 cifras) ....... 2024``."""
        record = extract_justificante(_SHAPE_M190_RESUMEN_ANUAL, _pdf_path(tmp_path, "190"))
        assert record.modelo == "190"
        assert record.ejercicio == "2024"
        assert record.period == Period.from_year_and_code(2024, "0A")

    def test_modelo_390_period_resolves_observed_year_to_annual_period(self, tmp_path: Path) -> None:
        """Receipts with no period token resolve the printed ejercicio to 0A."""
        record = extract_justificante(_SHAPE_M390_ANUAL, _pdf_path(tmp_path, "390"))
        assert record.modelo == "390"
        assert record.ejercicio == "2023"
        assert record.period == Period.from_year_and_code(2023, "0A")


class TestEnglishLayout:
    """English-language receipts use distinct labels for every field."""

    def test_modelo_130_english_layout(self, tmp_path: Path) -> None:
        """Modelo 130 English receipts bind every field via the English regex set."""
        record = extract_justificante(
            _SHAPE_M130_2021_ENGLISH,
            _pdf_path(tmp_path, "130"),
        )
        assert record.modelo == "130"
        assert record.tax_id == "Y0000001S"
        assert record.csv == "SANITIZED1302021"
        # presented_at parses from "Filed on 31-01-2022 at 22:00:40"
        assert record.presented_at.year == 2022
        assert record.presented_at.month == 1
        assert record.presented_at.day == 31

    def test_modelo_390_english_layout(self, tmp_path: Path) -> None:
        """Modelo 390 English receipts capture ``Financial year``."""
        record = extract_justificante(
            _SHAPE_M390_2021_ENGLISH,
            _pdf_path(tmp_path, "390"),
        )
        assert record.modelo == "390"
        assert record.tax_id == "Y0000001S"
        assert record.csv == "SANITIZED3902021"
        # ejercicio captured from "Financial year 2021"
        assert record.ejercicio == "2021"
        assert record.period == Period.from_year_and_code(2021, "0A")
