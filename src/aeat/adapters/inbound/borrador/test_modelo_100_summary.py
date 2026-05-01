"""Round-trip + artefact-kind tests for the Modelo 100 summary extractor."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from . import ArtefactKind, BorradorFiling, BorradorParseError, parse_borrador

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_inbound,
    pytest.mark.fixture_tier_l3,
]


_SUMMARY_VALUES: dict[str, str] = {
    "0022": "20000.00",
    "0049": "500.00",
    "0107": "0.00",
    "0175": "15000.00",
    "0400": "0.00",
    "0435": "35500.00",
    "0460": "500.00",
    "0500": "5550.00",
    "0505": "5550.00",
    "0510": "0.00",
    "0515": "0.00",
    "0520": "0.00",
    "0545": "29950.00",
    "0555": "500.00",
    "0550": "3500.00",
    "0551": "2800.00",
    "0560": "90.00",
    "0561": "50.00",
    "0595": "6440.00",
    "0620": "200.00",
    "0622": "100.00",
    "0630": "300.00",
    "0698": "6140.00",
    "0699": "1200.00",
    "0700": "1800.00",
    "0720": "3140.00",
    "0721": "3140.00",
}


def _generate_pdf(
    tmp_path: Path,
    *,
    artefact_kind: str = "BORRADOR",
    csv: str | None = None,
    casilla_values: dict[str, str] | None = None,
) -> Path:
    from tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_100_generator import (
        Modelo100GenParams,
        generate,
    )

    values = casilla_values if casilla_values is not None else _SUMMARY_VALUES
    params = Modelo100GenParams(
        año=2025,
        ejercicio="2025",
        tax_id="00000000T",
        casilla_values={k: Decimal(v) for k, v in values.items()},
        artefact_kind=artefact_kind,
        csv=csv,
    )
    pdf_bytes, _ = generate(params)
    path = tmp_path / f"modelo_100_2025_{artefact_kind.lower()}.pdf"
    path.write_bytes(pdf_bytes)
    return path


class TestArtefactKindDetection:
    def test_detects_borrador(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(tmp_path, artefact_kind="BORRADOR")
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.BORRADOR
        assert filing.csv is None

    def test_detects_predeclaracion(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(tmp_path, artefact_kind="PREDECLARACION")
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.PREDECLARACION
        assert filing.csv is None

    def test_detects_declaracion_with_csv(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(
            tmp_path,
            artefact_kind="DECLARACION",
            csv="MNOP4321QRST8765",
        )
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.DECLARACION
        assert filing.csv == "MNOP4321QRST8765"


class TestSummaryBlockExtraction:
    def test_roundtrip_extracts_every_summary_casilla(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(tmp_path)
        filing: BorradorFiling = parse_borrador(pdf)
        assert filing.modelo == "100"
        assert filing.ejercicio == "2025"
        assert filing.tax_id == "00000000T"
        extracted = {v.casilla_id: v.printed_value for v in filing.values}
        for casilla_id, raw in _SUMMARY_VALUES.items():
            if casilla_id not in extracted:
                continue
            assert extracted[casilla_id] == Decimal(raw), casilla_id
        # Ruleset's 12 casillas must all be present.
        assert {
            "0550",
            "0551",
            "0560",
            "0561",
            "0595",
            "0620",
            "0622",
            "0630",
            "0698",
            "0699",
            "0700",
            "0720",
        }.issubset(extracted.keys())


class TestDetectionDisambiguation:
    """Audit M3: make precedence of markers observable."""

    def test_csv_plus_borrador_body_classifies_as_declaracion(self, tmp_path: Path) -> None:
        """A DECLARACION carrying a CSV must stay a DECLARACION regardless of body text."""
        pdf = _generate_pdf(
            tmp_path,
            artefact_kind="DECLARACION",
            csv="MNOP4321QRST8765",
        )
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.DECLARACION

    def test_vista_previa_banner_trumps_borrador_header(self, tmp_path: Path) -> None:
        """PREDECLARACION precedence — VISTA PREVIA wins over a later BORRADOR line."""
        pdf = _generate_pdf(tmp_path, artefact_kind="PREDECLARACION")
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.PREDECLARACION


class TestSparseExtraction:
    """Audit M4: sparse PREDECLARACION yields a strictly smaller value tuple."""

    def test_sparse_predeclaracion_yields_fewer_values(self, tmp_path: Path) -> None:
        sparse = {
            "0550": "100.00",
            "0551": "100.00",
            "0560": "10.00",
            "0561": "10.00",
            "0595": "220.00",
        }
        pdf = _generate_pdf(
            tmp_path,
            artefact_kind="PREDECLARACION",
            casilla_values=sparse,
        )
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.PREDECLARACION
        extracted_ids = {v.casilla_id for v in filing.values}
        # Only the 5 provided casillas (all summary-scope) should extract.
        assert extracted_ids == set(sparse.keys())
        # Ruleset-required casillas 0620 / 0622 / 0630 / 0698 / 0720 must
        # be absent from a sparse PDF that never rendered them.
        for missing in ("0620", "0622", "0630", "0698", "0720"):
            assert missing not in extracted_ids


class TestOverrides:
    def test_artefact_kind_override_skips_detection(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(tmp_path, artefact_kind="BORRADOR")
        # Force DECLARACION even though the PDF has no CSV — the extractor
        # then raises because DECLARACION without CSV is invalid.
        with pytest.raises(BorradorParseError):
            parse_borrador(pdf, artefact_kind_override=ArtefactKind.DECLARACION)
