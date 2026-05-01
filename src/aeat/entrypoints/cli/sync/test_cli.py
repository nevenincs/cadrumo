"""Unit tests for the ``aeat sync`` CLI sub-app."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ....application.sync import (
    CasillaAddedWithDefault,
    DivergenceClassification,
    DivergenceRecord,
    JsonFileDivergenceRepository,
    ModeloIdentifier,
    ResolutionState,
)
from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
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


@pytest.fixture()
def repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the sync CLI at an isolated JSON repository."""
    root = tmp_path / "divergences"
    monkeypatch.setenv("AEAT_SYNC_DIVERGENCE_FILE_DIR", str(root))
    return root


def _make_record() -> DivergenceRecord:
    payload = CasillaAddedWithDefault(
        modelo=ModeloIdentifier("100"),
        casilla_id="C9",
        default="0",
        label={"es": "x", "en": "x", "hu": "x"},
    )
    return DivergenceRecord(
        record_id=uuid.uuid4().hex,
        detected_at=datetime.now(tz=UTC),
        modelo=ModeloIdentifier("100"),
        classification=DivergenceClassification.ADDITIVE,
        payload=payload,
    )


def test_sync_run_refuses_until_dependencies_merge(repo_root: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--modelo", "100"])
    assert result.exit_code == 2
    assert "runner prerequisites pending" in result.stdout


def test_sync_list_divergences_empty(repo_root: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["list-divergences"])
    assert result.exit_code == 0
    assert "0 record(s)" in result.stdout


def test_sync_list_and_show_divergence(repo_root: Path) -> None:
    repo = JsonFileDivergenceRepository(repo_root)
    record = _make_record()
    repo.save(record)

    runner = CliRunner()
    result = runner.invoke(app, ["list-divergences"])
    assert result.exit_code == 0
    # rich truncates long IDs with an ellipsis; assert on the first 16 chars.
    assert record.record_id[:16] in result.stdout

    show = runner.invoke(app, ["show-divergence", record.record_id])
    assert show.exit_code == 0
    assert record.record_id in show.stdout
    assert "casilla_added_with_default" in show.stdout


def test_sync_show_divergence_missing(repo_root: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    result = runner.invoke(app, ["show-divergence", "does-not-exist"])
    assert result.exit_code == 1


def test_sync_resolve_divergence_approve(repo_root: Path) -> None:
    repo = JsonFileDivergenceRepository(repo_root)
    record = _make_record()
    repo.save(record)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "resolve-divergence",
            record.record_id,
            "--action",
            "approve",
            "--notes",
            "approved in cli test",
        ],
    )
    assert result.exit_code == 0
    reloaded = repo.load(record.record_id)
    assert reloaded.resolution_state == ResolutionState.HUMAN_APPROVED
    assert reloaded.notes == "approved in cli test"


def test_sync_resolve_divergence_reject(repo_root: Path) -> None:
    repo = JsonFileDivergenceRepository(repo_root)
    record = _make_record()
    repo.save(record)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["resolve-divergence", record.record_id, "--action", "reject"],
    )
    assert result.exit_code == 0
    reloaded = repo.load(record.record_id)
    assert reloaded.resolution_state == ResolutionState.REJECTED


def test_sync_list_filters_by_state(repo_root: Path) -> None:
    repo = JsonFileDivergenceRepository(repo_root)
    r1 = _make_record()
    r2 = _make_record()
    repo.save(r1)
    repo.save(r2)
    repo.update_resolution(
        r2.record_id,
        resolution_state=ResolutionState.HUMAN_APPROVED,
        notes="approved",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["list-divergences", "--state", "pending"])
    assert result.exit_code == 0
    assert r1.record_id[:16] in result.stdout
    assert r2.record_id[:16] not in result.stdout
    assert "1 record(s)" in result.stdout
