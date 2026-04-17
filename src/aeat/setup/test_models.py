"""Unit tests for the setup-wizard pydantic models (#61)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ..auth import CertificateBackend
from ..deadlines import IVARegime
from ..i18n import Language
from . import SetupAnswers, SetupOutcome, SetupStep, VerifyFinding, VerifySeverity

pytestmark = pytest.mark.unit


def _canonical_answers(tmp_path: Path) -> SetupAnswers:
    cert = tmp_path / "cert.p12"
    cert.write_bytes(b"not-a-real-cert")
    return SetupAnswers(
        tax_id="12345678Z",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        certificate_path=cert,
        certificate_password_secret_var_name="AEAT_TEST_PW",
        certificate_friendly_name="test cert",
        certificate_backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
        default_language=Language.EN,
        output_language=Language.HU,
        aeat_drafts_dir=tmp_path / "drafts",
        aeat_submissions_dir=tmp_path / "subs",
        aeat_manuals_root=tmp_path / "manuals",
        default_profile_path=tmp_path / "profile.json",
    )


def test_setup_answers_roundtrip(tmp_path: Path) -> None:
    """``SetupAnswers`` round-trips through strict JSON validation."""
    answers = _canonical_answers(tmp_path)
    reparsed = SetupAnswers.model_validate_json(answers.model_dump_json())
    assert reparsed == answers


def test_setup_answers_is_frozen(tmp_path: Path) -> None:
    answers = _canonical_answers(tmp_path)
    with pytest.raises(ValidationError):
        answers.tax_id = "X"  # type: ignore[misc]


def test_setup_answers_rejects_extra_fields(tmp_path: Path) -> None:
    answers = _canonical_answers(tmp_path)
    payload = answers.model_dump(mode="json")
    payload["password_plaintext"] = "should never exist"
    with pytest.raises(ValidationError):
        SetupAnswers.model_validate(payload)


def test_setup_answers_has_no_password_field(tmp_path: Path) -> None:
    """The model MUST NOT carry any field that would hold the passphrase itself."""
    answers = _canonical_answers(tmp_path)
    dump = answers.model_dump(mode="json")
    for key in dump:
        assert "password" not in key or key.endswith("_var_name")


def test_verify_finding_roundtrip() -> None:
    finding = VerifyFinding(
        name="demo",
        severity=VerifySeverity.OK,
        message={"en": "ok", "es": "ok", "hu": "rendben"},
    )
    assert finding.severity is VerifySeverity.OK
    assert VerifyFinding.model_validate_json(finding.model_dump_json()) == finding


def test_setup_step_catalogue_is_closed() -> None:
    """The 10-step catalogue from issue #61 is fixed and closed."""
    assert {step.value for step in SetupStep} == {
        "WELCOME",
        "PROFILE",
        "CERTIFICATE",
        "LANGUAGE",
        "OUTPUT_DIRS",
        "LIVE_TESTS_OPT_IN",
        "FIXTURE_PROVISIONING",
        "VERIFY",
        "FIRST_RUN",
        "DONE",
    }


def test_setup_outcome_catalogue_is_closed() -> None:
    assert {o.value for o in SetupOutcome} == {
        "COMPLETED",
        "SKIPPED",
        "ABORTED_BY_USER",
        "ABORTED_VERIFY_FAILED",
    }
