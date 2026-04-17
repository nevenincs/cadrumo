"""Unit tests for the divergence repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.sync import (
    CasillaAddedWithDefault,
    DivergenceClassification,
    DivergenceRecord,
    DivergenceRepositoryError,
    JsonFileDivergenceRepository,
    ModeloIdentifier,
    ResolutionState,
    StorageDivergenceRepository,
)


def _record() -> DivergenceRecord:
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


@pytest.mark.unit
def test_json_file_repository_roundtrip(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    record = _record()
    repo.save(record)
    loaded = repo.load(record.record_id)
    assert loaded == record


@pytest.mark.unit
def test_json_file_repository_list_returns_saved(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    r1 = _record()
    r2 = _record()
    repo.save(r1)
    repo.save(r2)
    listing = repo.list()
    assert {rec.record_id for rec in listing} == {r1.record_id, r2.record_id}


@pytest.mark.unit
def test_json_file_repository_update_resolution(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    record = _record()
    repo.save(record)
    updated = repo.update_resolution(
        record.record_id,
        resolution_state=ResolutionState.HUMAN_APPROVED,
        notes="approved in unit test",
    )
    assert updated.resolution_state == ResolutionState.HUMAN_APPROVED
    assert updated.notes == "approved in unit test"
    reloaded = repo.load(record.record_id)
    assert reloaded.resolution_state == ResolutionState.HUMAN_APPROVED


@pytest.mark.unit
def test_json_file_repository_missing_record(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    with pytest.raises(DivergenceRepositoryError):
        repo.load("does-not-exist")


@pytest.mark.unit
def test_json_file_repository_rejects_traversal_on_load(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    with pytest.raises(DivergenceRepositoryError, match="simple filename token"):
        repo.load("../escape")


@pytest.mark.unit
def test_json_file_repository_rejects_traversal_on_save(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    record = _record().model_copy(update={"record_id": "../escape"})
    with pytest.raises(DivergenceRepositoryError, match="simple filename token"):
        repo.save(record)


@pytest.mark.unit
def test_storage_repository_stub_refuses_construction() -> None:
    with pytest.raises(NotImplementedError):
        StorageDivergenceRepository()
