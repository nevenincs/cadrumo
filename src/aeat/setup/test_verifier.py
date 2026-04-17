"""Unit tests for the pure setup-wizard verifier (#61)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.auth import CertificateBackend
from aeat.deadlines import IVARegime
from aeat.i18n import Language
from aeat.setup import (
    SetupAnswers,
    SetupAnswersError,
    Verifier,
    VerifySeverity,
    load_answers_from_file,
)
from aeat.setup._verifier import (
    _check_answers_self_consistency,
    _check_certificate_path,
    _check_directory,
    _check_password_env_var,
    _check_profile_file,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


def _answers(tmp_path: Path) -> SetupAnswers:
    cert = tmp_path / "cert.p12"
    cert.write_bytes(b"x")
    return SetupAnswers(
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


def test_verifier_happy_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_TEST_PW", "something")
    answers = _answers(tmp_path)
    # Pre-seed the profile JSON so the profile check reports OK.
    from aeat.setup import write_profile_file

    write_profile_file(answers, answers.default_profile_path)

    findings = Verifier().run(answers)
    assert findings
    assert not Verifier.has_error(findings)
    assert all(f.severity is VerifySeverity.OK for f in findings)


def test_verifier_flags_missing_certificate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_TEST_PW", "x")
    answers = _answers(tmp_path).model_copy(
        update={"certificate_path": tmp_path / "nope.p12"},
    )
    finding = _check_certificate_path(answers)
    assert finding.severity is VerifySeverity.ERROR


def test_verifier_warns_on_missing_password_env_var(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AEAT_TEST_PW", raising=False)
    answers = _answers(tmp_path)
    finding = _check_password_env_var(answers)
    assert finding.severity is VerifySeverity.WARNING


def test_verifier_creates_output_dirs(tmp_path: Path) -> None:
    finding = _check_directory("drafts_dir", tmp_path / "drafts")
    assert finding.severity is VerifySeverity.OK
    assert (tmp_path / "drafts").is_dir()


def test_verifier_flags_unwritable_profile(
    tmp_path: Path,
) -> None:
    answers = _answers(tmp_path)
    # Write a deliberately invalid profile JSON.
    answers.default_profile_path.write_text("{not json", encoding="utf-8")
    finding = _check_profile_file(answers)
    assert finding.severity is VerifySeverity.ERROR


def test_verifier_flags_missing_profile_as_warning(tmp_path: Path) -> None:
    answers = _answers(tmp_path)
    # Do NOT create the profile file.
    finding = _check_profile_file(answers)
    assert finding.severity is VerifySeverity.WARNING


def test_verifier_self_consistency_ok(tmp_path: Path) -> None:
    finding = _check_answers_self_consistency(_answers(tmp_path))
    assert finding.severity is VerifySeverity.OK


def test_load_answers_from_file_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "answers.json"
    path.write_text(_answers(tmp_path).model_dump_json(), encoding="utf-8")
    loaded = load_answers_from_file(path)
    assert loaded.tax_id == "12345678Z"


def test_load_answers_from_file_missing(tmp_path: Path) -> None:
    with pytest.raises(SetupAnswersError):
        load_answers_from_file(tmp_path / "no.json")


def test_load_answers_from_file_invalid(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(SetupAnswersError):
        load_answers_from_file(path)
