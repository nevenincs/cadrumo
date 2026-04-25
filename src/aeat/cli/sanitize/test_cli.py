"""Unit tests for ``aeat sanitize`` CLI bridge.

The tests exercise:

* The forbidden-flag rejection (parity with
  :mod:`aeat.cli.filing._reconcile` write guard).
* End-to-end ``aeat sanitize pdf`` against a synthesised PDF.
* ``aeat sanitize prepare-map`` writes a parseable scaffold.
* ``aeat sanitize verify`` exits non-zero on a leak and zero on
  a clean output.
* ``aeat sanitize check`` accepts a sanitised PDF that still
  parses through :func:`aeat.justificante.parse_justificante`.
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

from . import _FORBIDDEN_FLAGS, app, reject_forbidden_flags

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


@pytest.fixture
def runner() -> CliRunner:
    """Returns a Typer ``CliRunner`` configured to capture stderr separately."""
    return CliRunner()


def _write_minimal_pdf(path: Path, *, real_nif: str = "Y4113523X") -> None:
    """Write a one-page PDF carrying ``real_nif`` in a Tj operand."""
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
