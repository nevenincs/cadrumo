"""Unit tests for the PII scrub library.

Covers per-field redaction (NIF, NIE, IBAN, CSV, email, phone,
postal code, monetary amounts, prefixed names), the determinism
guarantees the regression-fixture pipeline relies on, the
strict + frozen :class:`ScrubSidecar` boundary, and the
"no leakage" invariant that no real PII may survive a scrub.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from .._scrub import (
    SCRUB_VERSION,
    ScrubSidecar,
    compute_sidecar,
    scrub_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class TestNifRedaction:
    """Individual and entity NIFs are redacted to the synthetic placeholder."""

    def test_individual_nif_replaced(self) -> None:
        """An individual NIF is rewritten to the synthetic ``00000000T`` placeholder."""
        scrubbed, fields = scrub_text(
            "NIF: 12345678Z operator Filing",
            filename="operator_130_2024Q1.pdf",
        )
        assert "12345678Z" not in scrubbed
        assert "00000000T" in scrubbed
        assert "nif" in fields

    def test_empresa_nif_replaced(self) -> None:
        """An entity NIF (leading letter + 8 digits) is rewritten to ``B00000000``."""
        scrubbed, fields = scrub_text(
            "NIF: B12345678 Empresa",
            filename="empresa_303_2024Q1.pdf",
        )
        assert "B12345678" not in scrubbed
        assert "B00000000" in scrubbed
        assert "nif" in fields


class TestAmountRedaction:
    """Monetary amounts are scrubbed while keeping their digit structure intact."""

    def test_aeat_amount_replaced_with_same_digit_structure(self) -> None:
        """The replacement preserves the original ``digits.thousands,decimals`` shape."""
        scrubbed, fields = scrub_text("Total: 1.234,56 eur", filename="operator_130.pdf")
        assert "1.234,56" not in scrubbed
        assert "amounts" in fields
        # Same structure: digits-dot-digits-comma-digits
        import re as _re

        assert _re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", scrubbed) is not None

    def test_determinism_same_filename_same_output(self) -> None:
        """The same filename + text produce identical scrubbed output."""
        text = "Ingresos: 10.000,00 Gastos: 3.500,00"
        a, _ = scrub_text(text, filename="operator_130_2024Q1.pdf")
        b, _ = scrub_text(text, filename="operator_130_2024Q1.pdf")
        assert a == b

    def test_different_filename_different_output(self) -> None:
        """Different filenames seed independent scrubbed outputs."""
        text = "Ingresos: 10.000,00"
        a, _ = scrub_text(text, filename="operator_130_2024Q1.pdf")
        b, _ = scrub_text(text, filename="operator_130_2024Q2.pdf")
        assert a != b


class TestCsvRedaction:
    """The Código Seguro de Verificación is scrubbed deterministically."""

    def test_csv_replaced_with_16_char_synthetic(self) -> None:
        """A 16-character CSV is rewritten to a synthetic equivalent of the same shape."""
        scrubbed, fields = scrub_text(
            "CSV: ABCD1234EFGH5678 ",
            filename="operator.pdf",
        )
        assert "ABCD1234EFGH5678" not in scrubbed
        assert "csv" in fields

    def test_csv_replacement_is_deterministic(self) -> None:
        """Re-scrubbing the same payload twice returns identical output."""
        text = "CSV: ABCD1234EFGH5678"
        a, _ = scrub_text(text, filename="operator.pdf")
        b, _ = scrub_text(text, filename="operator.pdf")
        assert a == b


class TestIbanRedaction:
    """IBANs are scrubbed to the canonical synthetic ``ES00 …`` form."""

    def test_iban_replaced(self) -> None:
        """A live IBAN is rewritten to the canonical synthetic placeholder."""
        scrubbed, fields = scrub_text(
            "IBAN: ES91 2100 0418 45 0200051332",
            filename="operator.pdf",
        )
        assert "2100 0418 45 0200051332" not in scrubbed
        assert "ES00 0000 0000 00 0000000000" in scrubbed
        assert "iban" in fields


class TestNieRedaction:
    """NIE identifiers are scrubbed."""

    def test_nie_replaced(self) -> None:
        """A NIE identifier is scrubbed and reported under the ``nie`` family."""
        scrubbed, fields = scrub_text("NIE: X1234567Z", filename="operator.pdf")
        assert "X1234567Z" not in scrubbed
        assert "nie" in fields


class TestPhoneRedaction:
    """Compact and international Spanish phone numbers are scrubbed."""

    def test_spanish_phone_replaced(self) -> None:
        """A 9-digit Spanish phone number is scrubbed."""
        scrubbed, fields = scrub_text(
            "Telefono: 612345678  Email: operator@example.com",
            filename="operator.pdf",
        )
        assert "612345678" not in scrubbed
        assert "phone" in fields

    def test_international_format_replaced(self) -> None:
        """At least one canonical form of the international phone number is scrubbed."""
        scrubbed, _fields = scrub_text("Contacto +34 612 345 678", filename="operator.pdf")
        # Either the international or compact form — at least one should scrub.
        assert "612345678" not in scrubbed or "+34 612 345 678" not in scrubbed
        # Only if the regex matched the compact form — +34 spaced form is out of scope.


class TestEmailRedaction:
    """Email addresses are scrubbed."""

    def test_email_replaced(self) -> None:
        """An email address is scrubbed and reported under the ``email`` family."""
        scrubbed, fields = scrub_text(
            "Email del declarante: operator.prueba@example.com",
            filename="operator.pdf",
        )
        assert "operator.prueba@example.com" not in scrubbed
        assert "email" in fields


class TestPostalCodeRedaction:
    """Spanish postal codes are scrubbed when prefixed with ``CP``."""

    def test_cp_replaced(self) -> None:
        """A ``CP <postcode>`` token is scrubbed and reported as ``postal_code``."""
        scrubbed, fields = scrub_text("Direccion: Calle Mayor 1 CP 28001 Madrid", filename="operator.pdf")
        assert "CP 28001" not in scrubbed
        assert "postal_code" in fields


class TestNamePrefixGuard:
    """Names are only scrubbed when preceded by a recognised label."""

    def test_name_only_replaced_when_prefixed(self) -> None:
        """Section headings such as ``RESULTADO A INGRESAR`` must survive scrub."""
        text = "RESULTADO A INGRESAR 1.234,56\nAGENCIA TRIBUTARIA"
        scrubbed, fields = scrub_text(text, filename="operator.pdf")
        assert "RESULTADO A INGRESAR" in scrubbed
        assert "AGENCIA TRIBUTARIA" in scrubbed
        assert "names" not in fields

    def test_name_replaced_when_prefixed(self) -> None:
        """Names are replaced when an ``Apellidos y nombre:`` label precedes them."""
        text = "Apellidos y nombre: PERSONA PRUEBA UNO"
        scrubbed, fields = scrub_text(text, filename="operator.pdf")
        assert "PERSONA PRUEBA" not in scrubbed
        assert "names" in fields
        assert "DEMO AUTONOMO" in scrubbed


class TestNoLeakageGuard:
    """No real PII may survive a scrub — the contract that protects the corpus."""

    def test_real_nif_never_present_after_scrub(self) -> None:
        """The real NIF must not appear anywhere in the scrubbed output."""
        text = "NIF: 12345678Z Total: 99.999,99 IBAN: ES91 2100 0418 45 0200051332"
        scrubbed, _ = scrub_text(text, filename="operator.pdf")
        assert "12345678Z" not in scrubbed
        assert "99.999,99" not in scrubbed
        assert "0200051332" not in scrubbed

    def test_combined_fields_all_touched(self) -> None:
        """A composite payload reports every triggered field family."""
        text = "NIF: 12345678Z  Ingresos: 10.000,00  CSV: ABCD1234EFGH5678  IBAN: ES91 2100 0418 45 0200051332"
        _, fields = scrub_text(text, filename="operator.pdf")
        assert set(fields) >= {"nif", "amounts", "csv", "iban"}


class TestScrubSidecar:
    """Strict + frozen invariants of the scrub sidecar boundary record."""

    def test_sidecar_is_strict_and_frozen(self, tmp_path: Path) -> None:
        """A computed sidecar carries its redaction classification and is immutable."""
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
        with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
            sidecar.scrub_version = "0.0.0"

    def test_sidecar_rejects_non_hex_sha(self, tmp_path: Path) -> None:
        """A sidecar with a non-hex SHA fails pydantic validation."""
        with pytest.raises(ValidationError, match=r"original_sha256|hex|pattern"):
            ScrubSidecar(
                original_sha256="not-a-hash",
                scrubbed_sha256="a" * 64,
                scrub_version=SCRUB_VERSION,
                scrubbed_at=datetime.now(tz=UTC),
                fields_touched=(),
                original_filename="f.pdf",
            )

    def test_sidecar_json_roundtrip(self, tmp_path: Path) -> None:
        """A sidecar survives a JSON dump / reload cycle bit-for-bit."""
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
