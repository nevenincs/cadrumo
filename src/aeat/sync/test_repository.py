"""Unit tests for the divergence repository."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ..storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from . import (
    CasillaAddedWithDefault,
    DivergenceClassification,
    DivergenceRecord,
    DivergenceRepositoryError,
    JsonFileDivergenceRepository,
    ModeloIdentifier,
    ResolutionState,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


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


def test_divergence_envelope_is_ciphertext_at_audit_class(tmp_path: Path) -> None:
    """The on-disk record must be a CipherEnvelope; the modelo / casilla canaries
    must not survive in plaintext on disk (LEAK-005 regression)."""
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    record = DivergenceRecord(
        record_id=uuid.uuid4().hex,
        detected_at=datetime.now(tz=UTC),
        modelo=ModeloIdentifier("100"),
        classification=DivergenceClassification.ADDITIVE,
        payload=CasillaAddedWithDefault(
            modelo=ModeloIdentifier("100"),
            casilla_id="LEAK-CANARY-CASILLA",
            default="0",
            label={"es": "x", "en": "x", "hu": "x"},
        ),
    )
    repo.save(record)
    target = repo._path_for(record.record_id)
    on_disk = target.read_text(encoding="utf-8")
    assert '"classification":"audit"' in on_disk
    assert '"encryption":' in on_disk
    assert "LEAK-CANARY-CASILLA" not in on_disk


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


def test_json_file_repository_roundtrip(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    record = _record()
    repo.save(record)
    loaded = repo.load(record.record_id)
    assert loaded == record


def test_json_file_repository_list_returns_saved(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    r1 = _record()
    r2 = _record()
    repo.save(r1)
    repo.save(r2)
    listing = repo.list()
    assert {rec.record_id for rec in listing} == {r1.record_id, r2.record_id}


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


def test_json_file_repository_missing_record(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    with pytest.raises(DivergenceRepositoryError):
        repo.load("does-not-exist")


def test_json_file_repository_rejects_traversal_on_load(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    with pytest.raises(DivergenceRepositoryError, match="simple filename token"):
        repo.load("../escape")


def test_json_file_repository_rejects_traversal_on_save(tmp_path: Path) -> None:
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    record = _record().model_copy(update={"record_id": "../escape"})
    with pytest.raises(DivergenceRepositoryError, match="simple filename token"):
        repo.save(record)
