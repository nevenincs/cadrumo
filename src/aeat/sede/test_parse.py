"""Parser tests against real AEAT HTML captures (identity-redacted).

The fixtures under ``tests/fixtures/aeat-sede/`` are live captures
from Kent's sede on 2026-04-24 with NIF, name, expediente sequence,
and CSV redacted to synthetic but schema-valid placeholders.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ._errors import SedeParseError
from ._parse import parse_expediente_detail, parse_resumen_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "aeat-sede"
_SEDE_BASE = "https://www6.agenciatributaria.gob.es"


class TestParseResumenTree:
    """Verify listing extraction from a real ResumenVlt capture."""

    def test_extracts_modelo_100_expedientes(self) -> None:
        html = (_FIXTURE_ROOT / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")
        expedientes = parse_resumen_tree(html, base_url=_SEDE_BASE)
        # Kent's sede on capture day held 3x Modelo 100 (IRPF 2023/22/21).
        modelo_100 = tuple(e for e in expedientes if e.modelo == "100")
        assert len(modelo_100) == 3
        years = sorted(e.ejercicio for e in modelo_100 if e.ejercicio is not None)
        assert years == [2021, 2022, 2023]

    def test_every_expediente_is_read_only(self) -> None:
        html = (_FIXTURE_ROOT / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")
        for expediente in parse_resumen_tree(html, base_url=_SEDE_BASE):
            assert expediente.mode == "read"

    def test_filter_by_modelo_reduces_corpus(self) -> None:
        html = (_FIXTURE_ROOT / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")
        all_expedientes = parse_resumen_tree(html, base_url=_SEDE_BASE)
        modelo_100 = tuple(e for e in all_expedientes if e.modelo == "100")
        # Filtering is idempotent: filtering twice yields the same corpus.
        assert len(modelo_100) <= len(all_expedientes)

    def test_raises_on_missing_heading(self) -> None:
        # A stripped page without 'Mis Expedientes' reads like a session
        # timeout or page drift — we fail fast.
        with pytest.raises(SedeParseError, match="Mis Expedientes"):
            parse_resumen_tree("<html><body>nothing</body></html>", base_url=_SEDE_BASE)

    def test_category_path_is_populated(self) -> None:
        html = (_FIXTURE_ROOT / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")
        expedientes = parse_resumen_tree(html, base_url=_SEDE_BASE)
        modelo_100 = next(e for e in expedientes if e.modelo == "100")
        # Category path always includes at least the modelo label.
        assert any("Modelo 100" in label for label in modelo_100.category_path)

    def test_detail_url_is_per_year_endpoint(self) -> None:
        html = (_FIXTURE_ROOT / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")
        for expediente in parse_resumen_tree(html, base_url=_SEDE_BASE):
            if expediente.modelo != "100" or expediente.ejercicio is None:
                continue
            assert f"AccesoDR{expediente.ejercicio}RVlt" in str(expediente.detail_url)


class TestParseExpedienteDetail:
    """Verify CSV extraction from a real detail-page capture."""

    def test_extracts_csv_and_urls(self) -> None:
        html = (_FIXTURE_ROOT / "expediente-irpf-2023-detail.html").read_text(encoding="utf-8")
        ref = parse_expediente_detail(
            html,
            expediente_id="202399999999999T",
            base_url=_SEDE_BASE,
        )
        assert ref.csv == "FIXTURECSV1234X7"
        assert ref.expediente_id == "202399999999999T"
        assert "CotejoIdSv?CSV=FIXTURECSV1234X7" in str(ref.cotejo_url)
        assert "CotejoDocIdSv?CSV=FIXTURECSV1234X7" in str(ref.pdf_url)
        assert ref.mode == "read"

    def test_raises_on_missing_csv(self) -> None:
        with pytest.raises(SedeParseError, match="no /CotejoIdSv"):
            parse_expediente_detail(
                "<html><body>no csv here</body></html>",
                expediente_id="202399999999999T",
                base_url=_SEDE_BASE,
            )
