"""Unit tests for :class:`SetupWizard` (#61).

Tests cover non-interactive happy path, verify-failure path, interactive
collection through :class:`QueuedPrompter`, that every reachable
:class:`SetupStep` lands in ``steps_completed``, and that the optional
first-run runner is wired correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..auth import CertificateBackend
from ..deadlines import IVARegime
from ..i18n import Language
from . import (
    QueuedPrompter,
    SetupAnswers,
    SetupError,
    SetupOutcome,
    SetupStep,
    SetupWizard,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


def _answers(tmp_path: Path) -> SetupAnswers:
    cert = tmp_path / "cert.p12"
    cert.write_bytes(b"x")
    return SetupAnswers(
        tax_id="12345678Z",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_professionals_with_retencion=False,
        professional_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
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


def test_non_interactive_happy_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_TEST_PW", "something")
    env_file = tmp_path / ".env"
    answers = _answers(tmp_path)
    result = SetupWizard().run(
        env_file=env_file,
        non_interactive=True,
        defaults=answers,
    )
    assert result.outcome is SetupOutcome.COMPLETED
    assert env_file.exists()
    assert answers.default_profile_path.exists()


def test_non_interactive_requires_defaults(tmp_path: Path) -> None:
    with pytest.raises(SetupError):
        SetupWizard().run(env_file=tmp_path / ".env", non_interactive=True)


def test_interactive_requires_prompter(tmp_path: Path) -> None:
    with pytest.raises(SetupError):
        SetupWizard().run(env_file=tmp_path / ".env", non_interactive=False)


def test_all_steps_reachable_in_non_interactive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_TEST_PW", "x")

    class NoopRunner:
        def run_read_only(self) -> str:
            return "ok"

    result = SetupWizard().run(
        env_file=tmp_path / ".env",
        non_interactive=True,
        defaults=_answers(tmp_path),
        first_run_runner=NoopRunner(),
    )
    completed = set(result.steps_completed)
    # Every step except FIRST_RUN reachable without a runner;
    # with a runner, FIRST_RUN also lands in completed.
    for step in SetupStep:
        assert step in completed, f"step {step} not reached"


def test_first_run_skipped_when_runner_is_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_TEST_PW", "x")
    result = SetupWizard().run(
        env_file=tmp_path / ".env",
        non_interactive=True,
        defaults=_answers(tmp_path),
    )
    assert SetupStep.FIRST_RUN in result.steps_skipped
    assert SetupStep.FIRST_RUN not in result.steps_completed


def test_verify_failure_short_circuits_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting the certificate after construction triggers an ERROR finding."""
    monkeypatch.setenv("AEAT_TEST_PW", "x")
    answers = _answers(tmp_path)
    answers.certificate_path.unlink()
    result = SetupWizard().run(
        env_file=tmp_path / ".env",
        non_interactive=True,
        defaults=answers,
    )
    assert result.outcome is SetupOutcome.ABORTED_VERIFY_FAILED
    assert any(f.name == "certificate_path_exists" for f in result.verify_findings)


def test_interactive_collects_from_queued_prompter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_TEST_PW", "x")
    cert = tmp_path / "cert.p12"
    cert.write_bytes(b"x")
    drafts = tmp_path / "drafts"
    subs = tmp_path / "subs"
    manuals = tmp_path / "manuals"
    profile = tmp_path / "profile.json"

    answers_queue = [
        # tax_id, iva_regime
        "12345678Z",
        IVARegime.GENERAL.value,
        # bools: has_employees, pays_professionals, 130 exception, pays_rent,
        # intracomunitario, 347 threshold, bienes
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        # cert path
        cert,
        # password env var name
        "AEAT_TEST_PW",
        # friendly name
        "",
        # cert backend
        CertificateBackend.PLAYWRIGHT_CONTEXT.value,
        # languages
        Language.EN.value,
        Language.HU.value,
        # output dirs
        drafts,
        subs,
        manuals,
        profile,
        # opt-ins
        False,
        False,
        False,
    ]
    prompter = QueuedPrompter(answers_queue)

    result = SetupWizard().run(
        env_file=tmp_path / ".env",
        non_interactive=False,
        defaults=None,
        prompter=prompter,
    )
    assert result.outcome is SetupOutcome.COMPLETED
    assert prompter.remaining == 0
    assert prompter.announcements  # welcome announcement fired


def test_result_env_file_path_is_absolute_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_TEST_PW", "x")
    target = tmp_path / "sub" / ".env"
    result = SetupWizard().run(
        env_file=target,
        non_interactive=True,
        defaults=_answers(tmp_path),
    )
    assert result.env_file_path == target
    assert target.exists()
