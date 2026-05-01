"""Unit tests for the citation blocklist (EPIC #305 wave 69)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ._categories import LegalCitationSource
from ._citation_registry import find_known_bad
from ._citations import LegalCitation

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class TestKnownBadBlocklist:
    """Every entry in ``_KNOWN_BAD_CITATIONS`` maps to a real prior miscite."""

    def test_lirpf_103_cuota_diferencial_is_blocklisted(self) -> None:
        """Wave 59c miscite: LIRPF art. 103 for cuota diferencial."""
        match = find_known_bad(
            LegalCitationSource.LEY,
            "103",
            "Artículo 103 LIRPF — base de la cuota diferencial",
        )
        assert match is not None
        assert match.article == "103"
        assert "cuota diferencial" in match.role_substring_es.lower()

    def test_lirpf_77_cuota_integra_autonomica_is_blocklisted(self) -> None:
        """Wave 63a miscite: LIRPF art. 77 for cuota íntegra autonómica."""
        match = find_known_bad(
            LegalCitationSource.LEY,
            "77",
            "Artículo 77 Ley 35/2006 — cuota íntegra autonómica",
        )
        assert match is not None

    def test_lirpf_67_cuota_integra_estatal_is_blocklisted(self) -> None:
        """Wave 65a miscite: LIRPF art. 67 for cuota íntegra estatal."""
        match = find_known_bad(
            LegalCitationSource.LEY,
            "67",
            "Cuota íntegra estatal - art. 67",
        )
        assert match is not None

    def test_lis_125_cuota_liquida_is_blocklisted(self) -> None:
        """Wave 61a miscite: LIS art. 125 for cuota líquida."""
        match = find_known_bad(
            LegalCitationSource.LEY,
            "125",
            "LIS art. 125 define la cuota líquida",
        )
        assert match is not None

    def test_rirpf_100_3a_arrendamientos_is_blocklisted(self) -> None:
        """Wave 67g miscite: RIRPF art. 100.3.a for arrendamientos urbanos."""
        match = find_known_bad(
            LegalCitationSource.REGLAMENTO,
            "100.3.a",
            "19% arrendamientos urbanos per RIRPF 100.3.a",
        )
        assert match is not None

    def test_rirpf_100_3c_ganancias_is_blocklisted(self) -> None:
        """Wave 57b miscite: RIRPF art. 100.3.c for ganancias."""
        match = find_known_bad(
            LegalCitationSource.REGLAMENTO,
            "100.3.c",
            "19% sobre ganancias patrimoniales por arrendamiento",
        )
        assert match is not None

    def test_rirpf_105_1_premios_is_blocklisted(self) -> None:
        """Wave 57b miscite: RIRPF art. 105.1 for premios."""
        match = find_known_bad(
            LegalCitationSource.REGLAMENTO,
            "105.1",
            "19% retención sobre premios en metálico",
        )
        assert match is not None

    def test_rirpf_110_2_agricolas_is_blocklisted(self) -> None:
        """Wave 57b miscite: RIRPF art. 110.2 for agrícolas."""
        match = find_known_bad(
            LegalCitationSource.REGLAMENTO,
            "110.2",
            "2% sobre actividades agrícolas y ganaderas",
        )
        assert match is not None

    def test_rirpf_110_4_modulos_is_blocklisted(self) -> None:
        """Wave 57b miscite: RIRPF art. 110.4 for módulos."""
        match = find_known_bad(
            LegalCitationSource.REGLAMENTO,
            "110.4",
            "2% sobre volumen de ventas en módulos sin datos-base",
        )
        assert match is not None

    def test_lis_125_liquido_a_ingresar_is_blocklisted(self) -> None:
        """Wave 70 miscite: LIS art. 125 for Modelo 200 'líquido a ingresar'."""
        match = find_known_bad(
            LegalCitationSource.LEY,
            "125",
            "Artículo 125 LIS — líquido a ingresar o devolver; incremento por pérdida de beneficios fiscales.",
        )
        assert match is not None
        assert "wave 71c" in match.audit_wave

    def test_liva_71_resumen_anual_is_blocklisted(self) -> None:
        """Wave 70 miscite: LIVA art. 71 for Modelo 390 resumen anual."""
        match = find_known_bad(
            LegalCitationSource.LEY,
            "71",
            "Artículo 71 Ley 37/1992 IVA — obligación de presentar la declaración-resumen anual del IVA.",
        )
        assert match is not None
        assert "wave 71d" in match.audit_wave


class TestAccentFolding:
    """Wave 73b: blocklist matching is diacritic-insensitive.

    Real-world risk: pdfplumber drops diacritics on some PDF fonts,
    and hand-typed quoted_text_es may lose accents. Without folding,
    ``cuota liquida`` (no accent) would defeat a ``cuota líquida``
    (with accent) blocklist entry.
    """

    def test_lis_125_without_accent_still_blocklisted(self) -> None:
        """'cuota liquida' (no diacritic) still matches 'cuota líquida'."""
        match = find_known_bad(
            LegalCitationSource.LEY,
            "125",
            "LIS art. 125 define la cuota liquida del ejercicio",
        )
        assert match is not None

    def test_rirpf_110_2_no_accent_still_blocklisted(self) -> None:
        """'agricolas' (no diacritic) still matches 'agrícolas'."""
        match = find_known_bad(
            LegalCitationSource.REGLAMENTO,
            "110.2",
            "2% sobre actividades agricolas y ganaderas",
        )
        assert match is not None

    def test_lirpf_67_integra_without_accent_still_blocklisted(self) -> None:
        """'cuota integra estatal' (no diacritic) still matches."""
        match = find_known_bad(
            LegalCitationSource.LEY,
            "67",
            "Cuota integra estatal - art. 67",
        )
        assert match is not None

    def test_rirpf_100_capital_mobiliario_is_blocklisted(self) -> None:
        """Wave 74 miscite: RIRPF art. 100 for capital mobiliario (wrong).

        RIRPF art. 100 is arrendamientos inmuebles urbanos only.
        Capital mobiliario retención lives in RIRPF art. 90.
        """
        match = find_known_bad(
            LegalCitationSource.REGLAMENTO,
            "100",
            "tipos de retención sobre rendimientos del capital mobiliario",
        )
        assert match is not None
        assert "wave 75b" in match.audit_wave

    def test_lirpf_66_cuota_integra_general_is_blocklisted(self) -> None:
        """Wave 74 miscite: LIRPF art. 66 for general cuota íntegra.

        Art. 66 is 'Tipos de gravamen del ahorro' (narrow). General
        cuota íntegra is art. 62 (estatal) + art. 73 (autonómica).
        """
        match = find_known_bad(
            LegalCitationSource.LEY,
            "66",
            "Cuota íntegra general - liquidación en art. 66",
        )
        assert match is not None
        assert "wave 75b" in match.audit_wave


class TestBlocklistPrecision:
    """Blocklist does not false-positive on correct article reuse."""

    def test_correct_67_cuota_liquida_estatal_role_is_allowed(self) -> None:
        """LIRPF art. 67 IS valid when cited for 'cuota líquida estatal'.

        The blocklist only fires on the specific wrong role
        ('cuota íntegra estatal'), not on any LIRPF art. 67 citation.
        """
        match = find_known_bad(
            LegalCitationSource.LEY,
            "67",
            "Cuota líquida estatal — art. 67 Ley 35/2006",
        )
        assert match is None

    def test_correct_79_cuota_diferencial_role_is_allowed(self) -> None:
        """LIRPF art. 79 IS valid when cited for 'cuota diferencial'.

        The blocklist only fires on 'cuota líquida' (the wrong role).
        """
        match = find_known_bad(
            LegalCitationSource.LEY,
            "79",
            "Cuota diferencial — art. 79 LIRPF",
        )
        assert match is None

    def test_different_article_passes(self) -> None:
        """A non-blocklisted article is always allowed."""
        match = find_known_bad(
            LegalCitationSource.LEY,
            "29",
            "Tipo de gravamen — art. 29.1 LIS",
        )
        assert match is None

    def test_different_source_passes(self) -> None:
        """Same article on a different source is not blocklisted."""
        match = find_known_bad(
            LegalCitationSource.REAL_DECRETO,
            "103",
            "Artículo 103 RD — cuota diferencial",
        )
        assert match is None


class TestLegalCitationModelValidator:
    """The model-level validator rejects blocklisted constructions."""

    def test_blocklisted_citation_raises_at_construction(self) -> None:
        """Import-time fail for a blocklisted miscite."""
        with pytest.raises(ValidationError) as exc_info:
            LegalCitation(
                source=LegalCitationSource.LEY,
                article="103",
                quoted_text_es="Artículo 103 LIRPF — cuota diferencial",
                retrieval_date=date(2026, 4, 22),
                is_curated_summary=True,
            )
        message = str(exc_info.value)
        assert "Blocklisted citation" in message
        assert "wave 59c" in message

    def test_legitimate_citation_constructs(self) -> None:
        """A correctly-attributed citation survives validation."""
        citation = LegalCitation(
            source=LegalCitationSource.LEY,
            article="62",
            quoted_text_es="Artículo 62 LIRPF — Cuota íntegra estatal",
            retrieval_date=date(2026, 4, 22),
            is_curated_summary=True,
        )
        assert citation.article == "62"

    def test_blocklist_embeds_audit_wave_in_error(self) -> None:
        """Error message names the audit wave for debugging."""
        with pytest.raises(ValidationError) as exc_info:
            LegalCitation(
                source=LegalCitationSource.REGLAMENTO,
                article="100.3.a",
                quoted_text_es="19% arrendamientos urbanos",
                retrieval_date=date(2026, 4, 22),
                is_curated_summary=True,
            )
        assert "wave 29" in str(exc_info.value)
        assert "wave 67g" in str(exc_info.value)
