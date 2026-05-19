"""Tests for complementaria registry-boundary behaviour."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...domain.filing import ModeloDraftStatus, FilingValue, FilingValueKind
from ...domain.submission import SubmissionAttempt, SubmissionStatus, ModeloPresentado
from . import (
    FilingAmendmentError,
    FilingBuilderError,
    FilingDraft,
    build_complementaria,
    build_draft,
    build_runtime_schema_provider,
    load_amendment,
)
from .testing import FilingTestProfile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path):
    """Install an ephemeral master key provider for encrypted test stores."""
    from ...adapters.persistence.storage import (
        EncryptedBlobStore,
        EphemeralMasterKeyProvider,
        SecretStore,
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
    with provider:
        override_secret_store(secret_store)
        try:
            yield
        finally:
            override_secret_store(None)


def _persist_original_draft(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, draft: FilingDraft) -> None:
    from ...domain.filing import FilingDraftRepository

    drafts_dir = tmp_path / "drafts"
    submissions_dir = tmp_path / "submissions"
    drafts_dir.mkdir()
    submissions_dir.mkdir()
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(drafts_dir))
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(submissions_dir))
    del drafts_dir
    FilingDraftRepository().save(draft)


def _submitted_filing(
    draft: FilingDraft,
    *,
    submission_id: str = "sub-1",
    justificante_csv: str | None = None,
) -> ModeloPresentado:
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        status=SubmissionStatus.SUBMITTED,
        justificante_csv=justificante_csv if justificante_csv is not None else f"CSV-{submission_id}",
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
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    values = tuple(
        FilingValue(
            casilla_id=casilla_id,
            value=value,
            kind=FilingValueKind.LITERAL,
            source="input",
        )
        for casilla_id, value in sorted(casillas.items())
    )
    return FilingDraft(
        draft_id=f"unsupported-{modelo}-{period}",
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        status=ModeloDraftStatus.SUBMITTED,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version=f"registry:{modelo}:missing",
    )


def _registry_draft(*, casillas: dict[str, Decimal]) -> FilingDraft:
    return build_draft(
        modelo="130",
        period="2024Q1",
        profile=FilingTestProfile(
            tax_id="00000000T",
            display_name="Complementaria registry test",
        ),
        inputs=casillas,
        schema_provider=build_runtime_schema_provider(),
    )


class TestBuildComplementaria:
    def test_modelo_130_builds_and_persists_complementaria(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original_draft = _registry_draft(
            casillas={
                "01": Decimal("10000"),
                "02": Decimal("4000"),
                "05": Decimal("250"),
                "06": Decimal("100"),
                "08": Decimal("2000"),
                "10": Decimal("10"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                "13": Decimal("0"),
                "15": Decimal("0"),
                "16": Decimal("0"),
                "18": Decimal("0"),
            }
        )
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft)

        amendment = build_complementaria(
            original,
            {
                "01": Decimal("13000"),
                "02": Decimal("3500"),
                "05": Decimal("400"),
                "06": Decimal("0"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
            schema_provider=build_runtime_schema_provider(),
        )

        changed = {change.casilla_code: change for change in amendment.delta}
        assert amendment.original_model == "130"
        assert amendment.amendment_kind.value == "complementaria"
        assert changed["19"].new_value == Decimal("1530.00")
        assert load_amendment(amendment.amendment_id).amendment_id == amendment.amendment_id

    def test_load_amendment_rejects_traversal_id(self) -> None:
        with pytest.raises(FilingAmendmentError, match="path separators"):
            load_amendment("../escape")

    def test_complementaria_requires_official_justificante_csv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original_draft = _registry_draft(
            casillas={
                "01": Decimal("10000"),
                "02": Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            }
        )
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft, justificante_csv="")

        with pytest.raises(FilingBuilderError, match="official justificante CSV"):
            build_complementaria(
                original,
                {"01": Decimal("11000")},
                schema_provider=build_runtime_schema_provider(),
            )
        assert not (tmp_path / "submissions" / "amendments").exists()

    def test_complementaria_requires_original_registry_snapshot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original_draft = _registry_draft(
            casillas={
                "01": Decimal("10000"),
                "02": Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            }
        ).model_copy(update={"schema_version": "registry:130:wrong-revision"})
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft)

        with pytest.raises(FilingBuilderError, match="active registry snapshot"):
            build_complementaria(
                original,
                {"01": Decimal("11000")},
                schema_provider=build_runtime_schema_provider(),
            )
        assert not (tmp_path / "submissions" / "amendments").exists()

    def test_modelo_303_requires_registry_definition(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        original_draft = _draft("303", "2024Q2", {"69": Decimal("1900.00")})
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-303")

        with pytest.raises(FilingBuilderError, match="not present in the calculation registry"):
            build_complementaria(
                original,
                {"07": Decimal("11000.00"), "29": Decimal("200.00")},
                schema_provider=build_runtime_schema_provider(),
            )
        assert not (tmp_path / "submissions" / "amendments").exists()

    def test_modelo_390_requires_registry_definition(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        original_draft = _draft("390", "2024A", {"109": Decimal("8400.00")})
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-390")

        with pytest.raises(FilingBuilderError, match="not present in the calculation registry"):
            build_complementaria(
                original,
                {"01": 2024},
                schema_provider=build_runtime_schema_provider(),
            )
        assert not (tmp_path / "submissions" / "amendments").exists()
