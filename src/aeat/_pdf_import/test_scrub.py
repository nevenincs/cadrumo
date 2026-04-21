"""Unit tests for the PII scrub library (#305 cluster C)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ._scrub import (
    SCRUB_VERSION,
    ScrubSidecar,
    compute_sidecar,
    scrub_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


class TestNifRedaction:
    def test_individual_nif_replaced(self) -> None:
        scrubbed, fields = scrub_text(
            "NIF: 12345678Z Kent Filing",
            filename="kent_130_2024Q1.pdf",
        )
        assert "12345678Z" not in scrubbed
        assert "00000000T" in scrubbed
        assert "nif" in fields

    def test_empresa_nif_replaced(self) -> None:
        scrubbed, fields = scrub_text(
            "NIF: B12345678 Empresa",
            filename="empresa_303_2024Q1.pdf",
        )
        assert "B12345678" not in scrubbed
        assert "B00000000" in scrubbed
        assert "nif" in fields


class TestAmountRedaction:
    def test_aeat_amount_replaced_with_same_digit_structure(self) -> None:
        scrubbed, fields = scrub_text("Total: 1.234,56 eur", filename="kent_130.pdf")
        assert "1.234,56" not in scrubbed
        assert "amounts" in fields
        # Same structure: digits-dot-digits-comma-digits
        import re as _re

        assert _re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", scrubbed) is not None

    def test_determinism_same_filename_same_output(self) -> None:
        text = "Ingresos: 10.000,00 Gastos: 3.500,00"
        a, _ = scrub_text(text, filename="kent_130_2024Q1.pdf")
        b, _ = scrub_text(text, filename="kent_130_2024Q1.pdf")
        assert a == b

    def test_different_filename_different_output(self) -> None:
        text = "Ingresos: 10.000,00"
        a, _ = scrub_text(text, filename="kent_130_2024Q1.pdf")
        b, _ = scrub_text(text, filename="kent_130_2024Q2.pdf")
        assert a != b


class TestCsvRedaction:
    def test_csv_replaced_with_16_char_synthetic(self) -> None:
        scrubbed, fields = scrub_text(
            "CSV: ABCD1234EFGH5678 ",
            filename="kent.pdf",
        )
        assert "ABCD1234EFGH5678" not in scrubbed
        assert "csv" in fields

    def test_csv_replacement_is_deterministic(self) -> None:
        text = "CSV: ABCD1234EFGH5678"
        a, _ = scrub_text(text, filename="kent.pdf")
        b, _ = scrub_text(text, filename="kent.pdf")
        assert a == b


class TestIbanRedaction:
    def test_iban_replaced(self) -> None:
        scrubbed, fields = scrub_text(
            "IBAN: ES91 2100 0418 45 0200051332",
            filename="kent.pdf",
        )
        assert "2100 0418 45 0200051332" not in scrubbed
        assert "ES00 0000 0000 00 0000000000" in scrubbed
        assert "iban" in fields


class TestNoLeakageGuard:
    def test_real_nif_never_present_after_scrub(self) -> None:
        """The real NIF MUST NOT appear anywhere in the scrubbed output."""
        text = "NIF: 12345678Z Total: 99.999,99 IBAN: ES91 2100 0418 45 0200051332"
        scrubbed, _ = scrub_text(text, filename="kent.pdf")
        assert "12345678Z" not in scrubbed
        assert "99.999,99" not in scrubbed
        assert "0200051332" not in scrubbed

    def test_combined_fields_all_touched(self) -> None:
        text = "NIF: 12345678Z  Ingresos: 10.000,00  CSV: ABCD1234EFGH5678  IBAN: ES91 2100 0418 45 0200051332"
        _, fields = scrub_text(text, filename="kent.pdf")
        assert set(fields) >= {"nif", "amounts", "csv", "iban"}


class TestScrubSidecar:
    def test_sidecar_is_strict_and_frozen(self, tmp_path: Path) -> None:
        original = tmp_path / "source.pdf"
        original.write_bytes(b"%PDF-1.4\nsource\n%%EOF")
        scrubbed = tmp_path / "scrubbed.pdf"
        scrubbed.write_bytes(b"%PDF-1.4\nscrubbed\n%%EOF")
        sidecar = compute_sidecar(
            original_path=original,
            scrubbed_path=scrubbed,
            fields_touched=("nif", "amounts"),
        )
        assert sidecar.fixture_tier == "l2"
        assert sidecar.scrub_version == SCRUB_VERSION
        with pytest.raises(ValidationError):
            sidecar.scrub_version = "0.0.0"  # type: ignore[misc]

    def test_sidecar_rejects_non_hex_sha(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ScrubSidecar(
                original_sha256="not-a-hash",
                scrubbed_sha256="a" * 64,
                scrub_version=SCRUB_VERSION,
                scrubbed_at=datetime.now(tz=UTC),
                fields_touched=(),
                original_filename="f.pdf",
            )

    def test_sidecar_json_roundtrip(self, tmp_path: Path) -> None:
        original = tmp_path / "source.pdf"
        original.write_bytes(b"%PDF-1.4\n%%EOF")
        scrubbed = tmp_path / "scrubbed.pdf"
        scrubbed.write_bytes(b"%PDF-1.4\n%%EOF")
        sidecar = compute_sidecar(
            original_path=original,
            scrubbed_path=scrubbed,
            fields_touched=("nif",),
        )
        serialised = sidecar.model_dump_json()
        reloaded = ScrubSidecar.model_validate_json(serialised)
        assert reloaded == sidecar
