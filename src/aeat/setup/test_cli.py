"""Smoke tests for ``aeat setup`` Typer surface (#61)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.auth import CertificateBackend
from aeat.cli import app
from aeat.deadlines import IVARegime
from aeat.i18n import Language
from aeat.setup import SetupAnswers

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

_runner = CliRunner()


def _seed_answers_file(tmp_path: Path) -> tuple[Path, SetupAnswers]:
    cert = tmp_path / "cert.p12"
    cert.write_bytes(b"x")
    answers = SetupAnswers(
        tax_id="12345678Z",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        certificate_path=cert,
        certificate_password_secret_var_name="AEAT_TEST_PW",
        certificate_backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
        default_language=Language.EN,
        output_language=Language.HU,
        aeat_drafts_dir=tmp_path / "drafts",
        aeat_submissions_dir=tmp_path / "subs",
        aeat_manuals_root=tmp_path / "manuals",
        default_profile_path=tmp_path / "profile.json",
    )
    path = tmp_path / "answers.json"
    path.write_text(answers.model_dump_json(), encoding="utf-8")
    return path, answers


def test_setup_help() -> None:
    result = _runner.invoke(app, ["setup", "--help"])
    assert result.exit_code == 0


def test_setup_verify_help() -> None:
    result = _runner.invoke(app, ["setup", "verify", "--help"])
    assert result.exit_code == 0


def test_setup_show_roundtrip(tmp_path: Path) -> None:
    path, _ = _seed_answers_file(tmp_path)
    result = _runner.invoke(app, ["setup", "show", "--from", str(path)])
    assert result.exit_code == 0
    assert "12345678Z" in result.output


def test_setup_non_interactive_runs_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_TEST_PW", "x")
    path, answers = _seed_answers_file(tmp_path)
    env_file = tmp_path / ".env"
    result = _runner.invoke(
        app,
        [
            "setup",
            "--env-file",
            str(env_file),
            "--non-interactive",
            "--from",
            str(path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert env_file.exists()
    assert answers.default_profile_path.exists()


def test_setup_non_interactive_requires_from(
    tmp_path: Path,
) -> None:
    result = _runner.invoke(
        app,
        ["setup", "--env-file", str(tmp_path / ".env"), "--non-interactive"],
    )
    assert result.exit_code != 0


def test_setup_verify_reports_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_TEST_PW", "x")
    path, _ = _seed_answers_file(tmp_path)
    result = _runner.invoke(app, ["setup", "verify", "--from", str(path)])
    # Profile JSON not present → at least a WARNING, exit 0 or 2.
    assert result.exit_code in (0, 2)
