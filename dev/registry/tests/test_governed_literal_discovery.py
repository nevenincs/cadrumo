"""Detector-teeth tests for report-only governed-literal discovery."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ..analysis.governed_literal_discovery import CandidateKind, discover_governed_literal_candidates, main

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_broad_shapes_include_prior_scanner_blind_spots(tmp_path: Path) -> None:
    (tmp_path / "facts.py").write_text(
        "from decimal import Decimal\n"
        "IVA_RATE = Decimal('0.21')\n"
        "FILING_DEADLINE = '2026-07-20'\n"
        "TAX_RATE_BY_KIND = {'general': 21, 'reduced': 10}\n"
        "class IvaRate:\n"
        "    GENERAL = '21'\n"
        "SIGNED_TAX_RATE = -7\n"
        "COMPOSED_TAX_RATE = 21 / 100\n"
        "def exemption_limit(value: int = 60000) -> int:\n"
        "    return 40000\n"
        "LEGAL_NOTE = 'Artículo 7 de la Ley del impuesto.'\n",
        encoding="utf-8",
    )

    candidates = discover_governed_literal_candidates(tmp_path)

    kinds = {candidate.kind for candidate in candidates}
    assert {CandidateKind.DATE, CandidateKind.DECIMAL, CandidateKind.LEGAL_TEXT, CandidateKind.MAPPING} <= kinds
    assert any(candidate.semantic_role == "value" and candidate.excerpt == "60000" for candidate in candidates)
    assert any(
        candidate.semantic_role == "exemption_limit" and candidate.excerpt == "40000" for candidate in candidates
    )
    assert any(candidate.semantic_role == "GENERAL" and candidate.excerpt == "'21'" for candidate in candidates)
    assert sum(candidate.kind is CandidateKind.DECIMAL for candidate in candidates) == 1
    assert any(candidate.kind is CandidateKind.EXPRESSION and "-7" in candidate.excerpt for candidate in candidates)


def test_tests_are_not_part_of_the_production_discovery_denominator(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_rate.py").write_text("TAX_RATE = 21\n", encoding="utf-8")
    (tmp_path / "policy.py").write_text("TAX_RATE = 10\n", encoding="utf-8")

    candidates = discover_governed_literal_candidates(tmp_path)

    assert {Path(candidate.path).name for candidate in candidates} == {"policy.py"}


def test_cli_is_report_only_even_when_candidates_exist(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "policy.py").write_text("TAX_RATE = 21\n", encoding="utf-8")

    exit_code = main(["--source-root", str(tmp_path)])

    assert exit_code == 0
    assert "1 governed-literal candidate(s); report only" in capsys.readouterr().out


def test_unread_input_is_announced_but_does_not_hide_healthy_candidates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "healthy.py").write_text("TAX_RATE = 21\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    candidates = discover_governed_literal_candidates(tmp_path)

    assert len(candidates) == 1
    assert "broken.py" in capsys.readouterr().err


def test_modelo_specific_scanner_is_left_in_place() -> None:
    from ..analysis.modelo_regulatory_literal_scan import derive_regulatory_literal_findings

    assert callable(derive_regulatory_literal_findings)


@pytest.mark.parametrize(
    "body",
    [
        "SCHEMA_VERSION = 2025\n",
        "PROTOCOL_STATUS_CODE = 400\n",
        "BUILD_DATE = '2026-01-01'\n",
        "def convert_tax_rate(value: int) -> float:\n    return value / 100\n",
        "raise ValueError('Artículo inválido')\n",
        "'''Artículo 7 in a module docstring.'''\n",
    ],
)
def test_common_technical_and_non_policy_literals_are_calibrated_out(body: str, tmp_path: Path) -> None:
    (tmp_path / "technical.py").write_text(body, encoding="utf-8")

    assert discover_governed_literal_candidates(tmp_path) == ()


@pytest.mark.parametrize(
    "body",
    [
        "import decimal as dec\nTAX_RATE = dec.Decimal('0.21')\n",
        "from decimal import Decimal as D\nTAX_RATE = D('0.21')\n",
    ],
)
def test_qualified_and_aliased_decimal_calls_are_discovered_once(body: str, tmp_path: Path) -> None:
    (tmp_path / "policy.py").write_text(body, encoding="utf-8")

    candidates = discover_governed_literal_candidates(tmp_path)

    assert len(candidates) == 1
    assert candidates[0].kind is CandidateKind.DECIMAL


def test_json_output_is_deterministic_and_uses_posix_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "z_policy.py").write_text("TAX_RATE = 21\n", encoding="utf-8")
    (tmp_path / "a_policy.py").write_text("TAX_RATE = 10\n", encoding="utf-8")

    assert main(["--source-root", str(tmp_path), "--json"]) == 0
    first = capsys.readouterr().out
    assert main(["--source-root", str(tmp_path), "--json"]) == 0
    second = capsys.readouterr().out

    assert first == second
    payload = json.loads(first)
    assert [Path(item["path"]).name for item in payload] == ["a_policy.py", "z_policy.py"]
    assert all("\\" not in item["path"] for item in payload)


def test_empty_root_reports_zero_and_missing_root_is_invalid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--source-root", str(tmp_path)]) == 0
    assert "0 governed-literal candidate(s)" in capsys.readouterr().out

    with pytest.raises(SystemExit, match="2"):
        main(["--source-root", str(tmp_path / "missing")])


def test_live_module_entrypoint_remains_report_only(tmp_path: Path) -> None:
    (tmp_path / "policy.py").write_text("TAX_RATE = 21\n", encoding="utf-8")

    completed = subprocess.run(  # noqa: S603 - the interpreter and module are fixed test inputs
        [sys.executable, "-m", "dev.registry.analysis.governed_literal_discovery", "--source-root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "report only" in completed.stdout
