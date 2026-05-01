"""Unit tests for the ``aeat sanitize`` CLI bridge.

The tests exercise:

* Forbidden-flag rejection (parity with
  :mod:`aeat.entrypoints.cli.filing._reconcile` write guard).
* End-to-end ``aeat sanitize pdf`` against a synthesised PDF.
* ``aeat sanitize prepare-map`` writes a parseable scaffold.
* ``aeat sanitize verify`` exits non-zero on a leak and zero on a
  clean output.
* ``aeat sanitize check`` accepts a sanitised PDF that still parses
  through :func:`aeat.adapters.inbound.justificante.parse_justificante`.
* Help output lists the four expected verbs.
"""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf
import pytest
import typer
import yaml
from typer.testing import CliRunner

from . import (
    _FORBIDDEN_FLAGS,
    _detect_pii_surfaces,
    _synthesise_csv_for,
    app,
    reject_forbidden_flags,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def runner() -> CliRunner:
    """Return a Typer :class:`CliRunner` for one test."""
    return CliRunner()


def _write_minimal_pdf(path: Path, *, real_nif: str = "Y4113523X") -> None:
    """Write a one-page PDF carrying ``real_nif`` in a ``Tj`` operand."""
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    pdf.pages[0].contents_add(
        f"BT /F1 12 Tf 100 700 Td ({real_nif}) Tj ET\n".encode(),
    )
    pdf.docinfo["/Title"] = pikepdf.String(f"Justificante AEAT {real_nif}")
    pdf.save(path)


def _write_mapping(path: Path, *, real_nif: str, synthetic_nif: str) -> None:
    """Write a mapping YAML with one NIF entry."""
    payload = {
        "nif": [
            {
                "real": real_nif,
                "synthetic": synthetic_nif,
                "surface_label": "taxpayer NIE",
            }
        ],
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


class TestRejectForbiddenFlags:
    """Every flag whose name implies AEAT mutation exits 2 before dispatch."""

    @pytest.mark.parametrize("flag", _FORBIDDEN_FLAGS)
    def test_each_forbidden_flag_exits_two(self, flag: str) -> None:
        with pytest.raises(typer.Exit) as exc:
            reject_forbidden_flags((flag,))
        assert exc.value.exit_code == 2

    def test_equal_form_is_rejected(self) -> None:
        with pytest.raises(typer.Exit) as exc:
            reject_forbidden_flags(("--submit=1",))
        assert exc.value.exit_code == 2

    def test_neutral_flags_pass(self) -> None:
        # No exception.
        reject_forbidden_flags(("--mapping", "x.yaml", "--output", "out.pdf"))


class TestSanitizePdfCommand:
    """End-to-end: real PDF → sanitised PDF via the CLI."""

    def test_writes_sanitised_pdf_and_report(self, runner: CliRunner, tmp_path: Path) -> None:
        source = tmp_path / "input.pdf"
        mapping = tmp_path / "mapping.yaml"
        output = tmp_path / "output.pdf"
        report = tmp_path / "output.json"

        _write_minimal_pdf(source)
        _write_mapping(mapping, real_nif="Y4113523X", synthetic_nif="Y0000001S")

        result = runner.invoke(
            app,
            [
                "pdf",
                str(source),
                "--mapping",
                str(mapping),
                "--output",
                str(output),
                "--report",
                str(report),
            ],
        )
        assert result.exit_code == 0, result.output
        assert output.is_file()
        assert report.is_file()

        # Cleartext absent from the output bytes.
        output_bytes = output.read_bytes()
        assert b"Y4113523X" not in output_bytes

        # Decompressed view also clean.
        re_opened = pikepdf.Pdf.open(io.BytesIO(output_bytes))
        contents = re_opened.pages[0].obj["/Contents"].read_bytes()
        assert b"Y4113523X" not in bytes(contents)
        assert b"Y0000001S" in bytes(contents)

        # Report includes hashes but NOT cleartext bytes.
        report_text = report.read_text(encoding="utf-8")
        assert "source_sha256" in report_text
        assert "Y4113523X" not in report_text

    def test_missing_input_exits_two(self, runner: CliRunner, tmp_path: Path) -> None:
        mapping = tmp_path / "mapping.yaml"
        _write_mapping(mapping, real_nif="Y4113523X", synthetic_nif="Y0000001S")
        result = runner.invoke(
            app,
            [
                "pdf",
                str(tmp_path / "missing.pdf"),
                "--mapping",
                str(mapping),
                "--output",
                str(tmp_path / "out.pdf"),
            ],
        )
        assert result.exit_code == 2

    def test_missing_mapping_exits_two(self, runner: CliRunner, tmp_path: Path) -> None:
        source = tmp_path / "input.pdf"
        _write_minimal_pdf(source)
        result = runner.invoke(
            app,
            [
                "pdf",
                str(source),
                "--mapping",
                str(tmp_path / "missing.yaml"),
                "--output",
                str(tmp_path / "out.pdf"),
            ],
        )
        assert result.exit_code == 2


class TestPrepareMapCommand:
    """``prepare-map`` produces a YAML scaffold even for non-justificantes."""

    def test_writes_scaffold_yaml(self, runner: CliRunner, tmp_path: Path) -> None:
        source = tmp_path / "input.pdf"
        _write_minimal_pdf(source)
        output = tmp_path / "mapping.yaml"

        result = runner.invoke(app, ["prepare-map", str(source), "--output", str(output)])
        assert result.exit_code == 0, result.output
        scaffold = yaml.safe_load(output.read_text(encoding="utf-8"))
        assert "nif" in scaffold
        # When the PDF doesn't parse as a justificante (synthesised
        # one-page PDF without modelo metadata), the empty scaffold
        # ships placeholder synthetics for every category.
        assert isinstance(scaffold["nif"], list)


class TestVerifyCommand:
    """``verify`` flags leaks; the clean path exits zero."""

    def test_leak_exits_one(self, runner: CliRunner, tmp_path: Path) -> None:
        leaked = tmp_path / "leaked.pdf"
        _write_minimal_pdf(leaked, real_nif="Y4113523X")
        mapping = tmp_path / "mapping.yaml"
        _write_mapping(mapping, real_nif="Y4113523X", synthetic_nif="Y0000001S")

        result = runner.invoke(app, ["verify", str(leaked), "--against", str(mapping)])
        assert result.exit_code == 1

    def test_clean_exits_zero(self, runner: CliRunner, tmp_path: Path) -> None:
        # Sanitise first, then verify.
        source = tmp_path / "input.pdf"
        mapping = tmp_path / "mapping.yaml"
        sanitised = tmp_path / "sanitised.pdf"
        _write_minimal_pdf(source)
        _write_mapping(mapping, real_nif="Y4113523X", synthetic_nif="Y0000001S")
        runner.invoke(
            app,
            [
                "pdf",
                str(source),
                "--mapping",
                str(mapping),
                "--output",
                str(sanitised),
            ],
        )

        result = runner.invoke(app, ["verify", str(sanitised), "--against", str(mapping)])
        assert result.exit_code == 0


class TestDetectPiiSurfaces:
    """``_detect_pii_surfaces`` auto-fills the operator's mapping scaffold."""

    def test_importe_detection_spanish_decimals(self) -> None:
        text = "Casilla 0171 1.234,56 Casilla 0172 549,52 Casilla 0173 0,00"
        out = _detect_pii_surfaces(text)
        importe_reals = {entry["real"] for entry in out["importe"]}
        assert "1.234,56" in importe_reals
        assert "549,52" in importe_reals
        assert "0,00" in importe_reals

    def test_importe_skips_bare_integers(self) -> None:
        # "Casilla 0171" should not be flagged as a monetary value
        # — only Spanish-shape decimals (with comma + 2 digits).
        text = "Casilla 0171 Casilla 0172 Page 1 of 5"
        out = _detect_pii_surfaces(text)
        assert out["importe"] == []

    def test_importe_handles_negative(self) -> None:
        text = "Saldo neto -2.705,59"
        out = _detect_pii_surfaces(text)
        importe_reals = {entry["real"] for entry in out["importe"]}
        assert "-2.705,59" in importe_reals

    def test_importe_synthetic_is_constant_placeholder(self) -> None:
        text = "549,52 1.234,56 0,00"
        out = _detect_pii_surfaces(text)
        for entry in out["importe"]:
            assert entry["synthetic"] == "1.000,00"

    def test_date_detection_dash_form(self) -> None:
        text = "Filed on 31-01-2022 at 22:00:40"
        out = _detect_pii_surfaces(text)
        # Date detection writes into "arbitrary" (no dedicated category).
        date_entries = [e for e in out["arbitrary"] if "date token" in e["surface_label"]]
        date_reals = {entry["real"] for entry in date_entries}
        assert "31-01-2022" in date_reals

    def test_date_detection_slash_form(self) -> None:
        text = "Born 30/08/1985"
        out = _detect_pii_surfaces(text)
        date_reals = {entry["real"] for entry in out["arbitrary"]}
        assert "30/08/1985" in date_reals

    def test_date_synthetic_preserves_separator(self) -> None:
        # Important for parser round-trip: dash dates → dash synthetic,
        # slash dates → slash synthetic. Captured live failure mode:
        # the parser binds on "DD-MM-YYYY" and a slash synthetic broke it.
        text_dash = "Filed on 31-01-2022 at 22:00"
        text_slash = "Born 30/08/1985"
        dash_entries = [e for e in _detect_pii_surfaces(text_dash)["arbitrary"] if "date" in e["surface_label"]]
        slash_entries = [e for e in _detect_pii_surfaces(text_slash)["arbitrary"] if "date" in e["surface_label"]]
        assert all(e["synthetic"] == "01-01-1900" for e in dash_entries)
        assert all(e["synthetic"] == "01/01/1900" for e in slash_entries)

    def test_catastral_reference_detection(self) -> None:
        # Real catastral shape: 4-5 digits + 2 letters + 4 digits +
        # letter + 4 digits + 2 letters. Sample: 9561760DF2896B0011HW.
        text = "Referencia catastral 9561760DF2896B0011HW"
        out = _detect_pii_surfaces(text)
        catastral_reals = {entry["real"] for entry in out["arbitrary"]}
        assert "9561760DF2896B0011HW" in catastral_reals

    def test_nrc_detection(self) -> None:
        # NRC shape: 13 digits + letter + 6-8 alphanumeric. Sample:
        # 1004231535072J33522H1K (22 chars).
        text = "NRC: 1004231535072J33522H1K IMPORTE: 549,52"
        out = _detect_pii_surfaces(text)
        nrc_reals = {entry["real"] for entry in out["nrc"]}
        assert "1004231535072J33522H1K" in nrc_reals

    def test_dedup_within_category(self) -> None:
        # Multiple occurrences of the same value should appear once.
        text = "549,52 first 549,52 again 549,52 third"
        out = _detect_pii_surfaces(text)
        importe_reals = [entry["real"] for entry in out["importe"]]
        assert importe_reals.count("549,52") == 1

    def test_iban_detection_spaced_form(self) -> None:
        # AEAT prints IBANs in 4-char groups with spaces.
        text = "Bank account ES76 2100 0418 4012 3456 7891 confirmed."
        out = _detect_pii_surfaces(text)
        iban_reals = {e["real"] for e in out["iban"]}
        assert "ES76 2100 0418 4012 3456 7891" in iban_reals

    def test_iban_detection_compact_form(self) -> None:
        # Some renderers strip the spaces.
        text = "ES7621000418401234567891 is your IBAN"
        out = _detect_pii_surfaces(text)
        iban_reals = {e["real"] for e in out["iban"]}
        assert "ES7621000418401234567891" in iban_reals

    def test_phone_detection_spanish_mobile(self) -> None:
        text = "Reach me at +34 678 12 34 56 anytime."
        out = _detect_pii_surfaces(text)
        phone_entries = [e for e in out["arbitrary"] if "phone" in e["surface_label"]]
        assert any("678 12 34 56" in e["real"] for e in phone_entries)

    def test_phone_detection_excludes_aeat_helplines(self) -> None:
        # AEAT's public helpline numbers must NOT be flagged as PII —
        # they're hardcoded across every justificante and redacting
        # them would pollute every fixture for no privacy benefit.
        text = "AEAT helpline: 901 33 55 33 / 915 548 770."
        out = _detect_pii_surfaces(text)
        phone_entries = [e for e in out["arbitrary"] if "phone" in e["surface_label"]]
        assert phone_entries == []


class TestVerifyMaskingDefendsAgainstSubstringFalsePositives:
    """``verify`` masks synthetics before checking for real-value leaks.

    Without masking, a real of ``0,00`` falsely matches the synthetic
    ``1.000,00`` that contains it as a substring. The verifier
    masks longest-first so nested overlaps collapse cleanly.
    """

    def test_no_false_positive_on_zero_substring(self, runner: CliRunner, tmp_path: Path) -> None:
        # Build a mapping where the importe real ``0,00`` would
        # appear inside the importe synthetic ``1.000,00``.
        # Without masking, verify would flag a leak.
        mapping_path = tmp_path / "mapping.yaml"
        mapping_path.write_text(
            yaml.safe_dump(
                {
                    "nif": [
                        {
                            "real": "Y4113523X",
                            "synthetic": "Y0000001S",
                            "surface_label": "nif",
                        }
                    ],
                    "importe": [
                        {
                            "real": "0,00",
                            "synthetic": "1.000,00",
                            "surface_label": "importe",
                        }
                    ],
                },
            ),
            encoding="utf-8",
        )
        # Synthesise an output PDF with ONLY the synthetic value.
        # No leak should be reported.
        sanitised = tmp_path / "sanitised.pdf"
        pdf = pikepdf.Pdf.new()
        pdf.add_blank_page(page_size=(612, 792))
        pdf.pages[0].contents_add(
            b"BT /F1 12 Tf 100 700 Td (Y0000001S) Tj 100 680 Td (1.000,00) Tj ET\n",
        )
        pdf.save(sanitised)

        result = runner.invoke(app, ["verify", str(sanitised), "--against", str(mapping_path)])
        # Without masking this would EXIT 1 (false-positive leak on
        # "0,00" contained in "1.000,00"). With masking it exits 0.
        assert result.exit_code == 0, result.output


class TestPdfCommandRejectsForbiddenFlag:
    """The forbidden-flag guard fires inside the CLI dispatch."""

    def test_write_flag_rejected(self, runner: CliRunner, tmp_path: Path) -> None:
        source = tmp_path / "input.pdf"
        mapping = tmp_path / "mapping.yaml"
        _write_minimal_pdf(source)
        _write_mapping(mapping, real_nif="Y4113523X", synthetic_nif="Y0000001S")

        result = runner.invoke(
            app,
            [
                "pdf",
                str(source),
                "--mapping",
                str(mapping),
                "--output",
                str(tmp_path / "out.pdf"),
                "--write",
            ],
        )
        # Typer rejects unknown flags with code 2 before forbidden-
        # flag scan runs; either way, the call must fail.
        assert result.exit_code != 0


class TestSynthesiseCsvFor:
    """``_synthesise_csv_for`` produces 16-char shape-conforming CSVs.

    The committed fixture corpus (``tests/fixtures/justificantes/<modelo>/``)
    uses ``SANITIZED{modelo}{ejercicio}`` as the CSV synthetic. The
    helper now matches that convention so ``aeat sanitize prepare-map``
    auto-fills the same shape the operator manually edited into the
    earlier fixture waves.
    """

    def test_embed_modelo_and_ejercicio_matches_fixture_corpus(self) -> None:
        # Mirrors the M130 / 2024 fixtures in tests/fixtures/justificantes/130/.
        assert _synthesise_csv_for("130", ejercicio="2024") == "SANITIZED1302024"
        # Mirrors the M100 / 2022 IRPF anual fixture.
        assert _synthesise_csv_for("100", ejercicio="2022") == "SANITIZED1002022"
        # Mirrors the M390 / 2023 IVA anual fixture.
        assert _synthesise_csv_for("390", ejercicio="2023") == "SANITIZED3902023"

    def test_no_ejercicio_falls_back_to_padding(self) -> None:
        assert _synthesise_csv_for("130") == "SANITIZED130XXXX"
        assert _synthesise_csv_for("100") == "SANITIZED100XXXX"

    def test_empty_ejercicio_falls_back_to_padding(self) -> None:
        # When the parsed justificante has no ejercicio (rare but
        # possible), the auto-fill must still produce a 16-char
        # shape-conforming synthetic.
        assert _synthesise_csv_for("130", ejercicio="") == "SANITIZED130XXXX"

    def test_result_is_always_16_chars_uppercase(self) -> None:
        for modelo in ("100", "111", "130", "190", "303", "347", "349", "390"):
            for ejercicio in ("", "2021", "2022", "2023", "2024"):
                synthetic = _synthesise_csv_for(modelo, ejercicio=ejercicio)
                assert len(synthetic) == 16, (modelo, ejercicio, synthetic)
                assert synthetic.isupper()
                assert synthetic.isalnum()


class TestHelpListsFourVerbs:
    """The help screen advertises exactly the four documented verbs."""

    def test_help_mentions_each_verb(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        text = result.output
        assert "pdf" in text
        assert "prepare-map" in text
        assert "verify" in text
        assert "check" in text
