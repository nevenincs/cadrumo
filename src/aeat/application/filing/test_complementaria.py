"""Unit tests for complementaria registry-boundary behaviour."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...domain.submission import SubmissionAttempt, SubmissionStatus, SubmittedFiling
from . import (
    FilingAmendmentError,
    FilingBuilderError,
    FilingDraft,
    build_complementaria,
    load_amendment,
)
from .testing import default_schema_provider, synthesize_filing_draft

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path):
    """Install an ephemeral master key provider for encrypted test stores."""
    from ...adapters.persistence.storage import (
        EncryptedBlobStore,
        EphemeralMasterKeyProvider,
        SecretStore,
        override_master_key_provider,
        override_secret_store,
    )

    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_master_key_provider(provider)
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


def _persist_original_draft(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, draft: FilingDraft) -> None:
    from ...domain.filing import FilingDraftRepository

    drafts_dir = tmp_path / "drafts"
    submissions_dir = tmp_path / "submissions"
    drafts_dir.mkdir()
    submissions_dir.mkdir()
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(drafts_dir))
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(submissions_dir))
    FilingDraftRepository(store_dir=drafts_dir).save(draft)


def _submitted_filing(draft: FilingDraft, *, submission_id: str = "sub-1") -> SubmittedFiling:
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    return SubmittedFiling(
        submission_id=submission_id,
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        status=SubmissionStatus.SUBMITTED,
        justificante_csv=f"CSV-{submission_id}",
        justificante_pdf_path=None,
        submitted_at=now,
        acknowledged_at=None,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{submission_id}.1",
                started_at=now,
                ended_at=now,
                status=SubmissionStatus.SUBMITTED,
            ),
        ),
    )


def _draft(modelo: str, period: str, casillas: dict[str, Decimal]) -> FilingDraft:
    return synthesize_filing_draft(
        modelo=modelo,
        period=period,
        casilla_values=casillas,
        profile_tax_id="00000000T",
    )


class TestBuildComplementaria:
    def test_modelo_130_requires_registry_snapshot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        original_draft = _draft("130", "2024Q1", {"01": Decimal("12500.00"), "07": Decimal("1400.00")})
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft)

        with pytest.raises(FilingBuilderError, match="validated registry snapshot"):
            build_complementaria(
                original,
                {
                    "01": Decimal("13000.00"),
                    "02": Decimal("3500.00"),
                    "05": Decimal("400.00"),
                    "06": Decimal("0.00"),
                },
                schema_provider=default_schema_provider(),
            )
        assert not (tmp_path / "submissions" / "amendments").exists()

    def test_load_amendment_rejects_traversal_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        submissions_dir = tmp_path / "submissions"
        submissions_dir.mkdir()
        monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(submissions_dir))
        with pytest.raises(FilingAmendmentError, match="simple filename token"):
            load_amendment("../escape")

    def test_modelo_303_requires_registry_snapshot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        original_draft = _draft("303", "2024Q2", {"69": Decimal("1900.00")})
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-303")

        with pytest.raises(FilingBuilderError, match="validated registry snapshot"):
            build_complementaria(
                original,
                {"07": Decimal("11000.00"), "29": Decimal("200.00")},
                schema_provider=default_schema_provider(),
            )
        assert not (tmp_path / "submissions" / "amendments").exists()

    def test_modelo_390_requires_registry_snapshot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        original_draft = _draft("390", "2024", {"109": Decimal("8400.00")})
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-390")

        with pytest.raises(FilingBuilderError, match="validated registry snapshot"):
            build_complementaria(
                original,
                {"01": 2024},
                schema_provider=default_schema_provider(),
            )
        assert not (tmp_path / "submissions" / "amendments").exists()
