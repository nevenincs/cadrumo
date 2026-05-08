"""Unit tests for :class:`aeat.application.setup.SetupWizard`.

Tests cover the non-interactive happy path, the verify-failure path,
and interactive collection through :class:`QueuedPrompter`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from ...adapters.outbound.aeat.auth import CertificateBackend
from ...adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ...adapters.persistence.storage.sql import dispose_engine
from ...domain.deadlines import IVARegime
from ...domain.profile import CCAA
from . import (
    QueuedPrompter,
    SetupAnswers,
    SetupError,
    SetupOutcome,
    SetupWizard,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    """Ensure the wizard's secure-object profile writer can resolve a key in tests."""
    provider = EphemeralMasterKeyProvider()
    old_database_url = os.environ.get("AEAT_DATABASE_URL")
    os.environ["AEAT_DATABASE_URL"] = f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"
    dispose_engine()
    override_master_key_provider(provider)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs-secret",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)
        if old_database_url is None:
            os.environ.pop("AEAT_DATABASE_URL", None)
        else:
            os.environ["AEAT_DATABASE_URL"] = old_database_url
        dispose_engine()


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
        tax_residence_ccaa=CCAA.MADRID,
        certificate_path=cert,
        certificate_password_secret_var_name="AEAT_TEST_PW",
        certificate_backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
        default_language="en",
        output_language="hu",
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
    monkeypatch.setenv("AEAT_TAX_RESIDENCE_PROFILE_PATH", str(tmp_path / "tax-residence.json"))
    env_file = tmp_path / ".env"
    answers = _answers(tmp_path)
    result = SetupWizard().run(
        env_file=env_file,
        non_interactive=True,
        defaults=answers,
    )
    assert result.outcome is SetupOutcome.COMPLETED
    assert env_file.exists()
    assert not answers.default_profile_path.exists()
    assert not (tmp_path / "tax-residence.json").exists()


def test_non_interactive_requires_defaults(tmp_path: Path) -> None:
    with pytest.raises(SetupError):
        SetupWizard().run(env_file=tmp_path / ".env", non_interactive=True)


def test_interactive_requires_prompter(tmp_path: Path) -> None:
    with pytest.raises(SetupError):
        SetupWizard().run(env_file=tmp_path / ".env", non_interactive=False)


def test_verify_failure_short_circuits_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting the certificate after construction triggers an ERROR finding."""
    monkeypatch.setenv("AEAT_TEST_PW", "x")
    monkeypatch.setenv("AEAT_TAX_RESIDENCE_PROFILE_PATH", str(tmp_path / "tax-residence.json"))
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
        CCAA.MADRID.value,
        # cert path
        cert,
        # password env var name
        "AEAT_TEST_PW",
        # friendly name
        "",
        # cert backend
        CertificateBackend.PLAYWRIGHT_CONTEXT.value,
        # languages
        "en",
        "hu",
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
    assert prompter.announcements  # welcome announcement fired


def test_result_env_file_path_is_absolute_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_TEST_PW", "x")
    monkeypatch.setenv("AEAT_TAX_RESIDENCE_PROFILE_PATH", str(tmp_path / "tax-residence.json"))
    target = tmp_path / "sub" / ".env"
    result = SetupWizard().run(
        env_file=target,
        non_interactive=True,
        defaults=_answers(tmp_path),
    )
    assert result.env_file_path == target
    assert target.exists()
