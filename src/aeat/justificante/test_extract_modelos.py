"""Regression tests for the per-modelo period / ejercicio extraction.

Real-world AEAT text shapes captured live (2026-04-25) for Modelos
130, 303, 111, 190, 390 differ from the synthetic fixtures in two
ways:

* Quarterly modelos (130, 111, ...) print the period in a positional
  layout that pdfplumber merges as ``[<NIF>] <YYYY> <token>``
  on a single line, with no "Período" label nearby.
* The Modelo 190 *Resumen anual* layout prints the ejercicio with
  a parenthetical leader: ``Ejercicio (con 4 cifras) ....... 2024``.

These tests feed synthesized text shapes (with redacted PII) through
:func:`extract_justificante` so the new fallbacks are exercised
without committing real PDF fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ._extract import extract_justificante

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


# Synthetic PDF text shapes derived from live captures with PII
# token-replaced (Y4113523X → Y0000001S, real CSVs → SANITIZED…).
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
    "https://sede.agenciatributaria.gob.es/Sede/cotejo/CSV=SANITIZED1302024\n"
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
    "https://sede.agenciatributaria.gob.es/Sede/cotejo/CSV=SANITIZED3032024\n"
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
    "https://sede.agenciatributaria.gob.es/Sede/cotejo/CSV=SANITIZED1112024\n"
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
    "https://sede.agenciatributaria.gob.es/Sede/cotejo/CSV=SANITIZED1902024\n"
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
    "https://sede.agenciatributaria.gob.es/Sede/cotejo/CSV=SANITIZED3902023\n"
)


def _stub_path(tmp_path: Path, modelo: str) -> Path:
    """Return a writable path standing in for a real PDF source."""
    pdf = tmp_path / f"m{modelo}.pdf"
    pdf.write_bytes(b"%PDF-1.4 stub\n%%EOF\n")
    return pdf


class TestPeriodPositionalQuarterly:
    """Quarterly modelos lay out the period as ``<YYYY> <token>``."""

    def test_modelo_130_period_positional(self, tmp_path: Path) -> None:
        record = extract_justificante(_SHAPE_M130_QUARTERLY, _stub_path(tmp_path, "130"))
        assert record.modelo == "130"
        assert record.period == "1T"
        assert record.tax_id == "Y0000001S"
        assert record.csv == "SANITIZED1302024"

    def test_modelo_303_labelled_period(self, tmp_path: Path) -> None:
        record = extract_justificante(_SHAPE_M303_QUARTERLY, _stub_path(tmp_path, "303"))
        assert record.modelo == "303"
        assert record.period == "1T"
        assert record.ejercicio == "2024"

    def test_modelo_111_period_positional(self, tmp_path: Path) -> None:
        record = extract_justificante(_SHAPE_M111_QUARTERLY, _stub_path(tmp_path, "111"))
        assert record.modelo == "111"
        assert record.period == "1T"


class TestEjercicioLooseShape:
    """Resumen anuales (M190) print ejercicio with parenthetical leader."""

    def test_modelo_190_ejercicio_loose(self, tmp_path: Path) -> None:
        record = extract_justificante(_SHAPE_M190_RESUMEN_ANUAL, _stub_path(tmp_path, "190"))
        assert record.modelo == "190"
        assert record.ejercicio == "2024"
        # No labelled period and no positional period token; falls
        # back to the ejercicio so the schema's non-empty
        # constraint holds.
        assert record.period == "2024"

    def test_modelo_390_period_falls_back_to_ejercicio(self, tmp_path: Path) -> None:
        record = extract_justificante(_SHAPE_M390_ANUAL, _stub_path(tmp_path, "390"))
        assert record.modelo == "390"
        assert record.ejercicio == "2023"
        assert record.period == "2023"
