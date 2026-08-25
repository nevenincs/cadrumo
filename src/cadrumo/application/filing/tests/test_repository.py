"""Tests for the governed-persistence :class:`~cadrumo.adapters.persistence.profile.filing_drafts.ModeloDraftRepository`.

Exercises round-trip save/load, idempotent saves, list/iter, deletion,
the FINANCIAL classification gate, the unsafe-id rejection, and the
per-draft lock marker isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef

from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ....adapters.persistence.storage import Envelope, SensitivityClass
from ....adapters.persistence.storage.bucket import bucket_paths
from ....adapters.persistence.storage.errors import ClassificationError
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.filing import (
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
    registry_schema_version,
)
from ....domain.submission import ModeloDraftStatus
from ....tests.secure_sql import TestRuntimeProfile
from ..conftest import _BUCKET_ID

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_P_Q1 = Period.from_year_and_code(2026, "1T")
_P_Q2 = Period.from_year_and_code(2026, "2T")
_DRAFT_INPUT_CASILLA: CasillaId = validated_casilla_id("01", surface="_DRAFT_INPUT_CASILLA")
_FOREIGN_CLASS_WRITTEN_AT = datetime(2026, 5, 26, 16, 30, 0, tzinfo=UTC)


def _snapshot_ref(*, modelo: str, period: Period, revision_id: str) -> RegistrySnapshotRef:
    return RegistrySnapshotRef(
        modelo=modelo,
        revision_id=revision_id,
        modelo_year=period.filing_year,
        period=period.registry_token,
    )


def _make_draft(*, period: Period = _P_Q1, ingresos: int = 12500) -> ModeloDraft:
    now = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    values = (
        ModeloValue(
            casilla_id=_DRAFT_INPUT_CASILLA,
            value=Decimal(ingresos),
            kind=ModeloValueKind.LITERAL,
            source="test input",
        ),
    )
    snapshot_ref = _snapshot_ref(modelo="130", period=period, revision_id="2019-y-siguientes")
    draft_id = compute_modelo_draft_id(
        modelo="130",
        period=period,
        profile_tax_id="00000000T",
        snapshot_ref=snapshot_ref,
        values=values,
    )
    return ModeloDraft(
        draft_id=draft_id,
        modelo="130",
        period=period,
        profile_tax_id="00000000T",
        subject_tax_id="00000000T",
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.VALIDADO,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version=registry_schema_version(modelo="130", revision_id="2019-y-siguientes"),
    )


def _save_two_drafts(repo: ModeloDraftRepository) -> tuple[ModeloDraft, ModeloDraft]:
    d1 = _make_draft(period=_P_Q1, ingresos=10000)
    d2 = _make_draft(period=_P_Q2, ingresos=20000)
    repo.save(d1)
    repo.save(d2)
    return d1, d2


@pytest.fixture
def repo() -> ModeloDraftRepository:
    return ModeloDraftRepository()


def _database_bytes(storage_root: Path) -> bytes:
    from ....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(bucket_paths(storage_root, _BUCKET_ID).database_file)


class TestEmptyState:
    def test_load_returns_none_when_absent(self, repo: ModeloDraftRepository) -> None:
        assert repo.load("does-not-exist") is None

    def test_object_marker_identifies_secure_backend(self, repo: ModeloDraftRepository) -> None:
        assert repo.envelope_path_for("abc123").as_posix().endswith("cadrumo.domain.filing.drafts/abc123")

    def test_list_draft_ids_empty(self, repo: ModeloDraftRepository) -> None:
        assert repo.list_draft_ids() == ()


class TestSaveLoad:
    def test_round_trip_preserves_payload(self, repo: ModeloDraftRepository) -> None:
        draft = _make_draft()
        repo.save(draft)

        repo_b = ModeloDraftRepository()
        loaded = repo_b.load(draft.draft_id)
        assert loaded == draft

    def test_save_is_idempotent(self, repo: ModeloDraftRepository) -> None:
        draft = _make_draft()
        repo.save(draft)
        repo.save(draft)
        assert repo.list_draft_ids() == (draft.draft_id,)


class TestListAndIter:
    def test_list_returns_persisted_ids_sorted(self, repo: ModeloDraftRepository) -> None:
        d1, d2 = _save_two_drafts(repo)
        ids = repo.list_draft_ids()
        assert set(ids) == {d1.draft_id, d2.draft_id}
        assert ids == tuple(sorted(ids))

    def test_iter_drafts_yields_payloads(self, repo: ModeloDraftRepository) -> None:
        d1, d2 = _save_two_drafts(repo)
        loaded = {payload.draft_id: payload for payload in repo.iter_drafts()}
        assert loaded[d1.draft_id] == d1
        assert loaded[d2.draft_id] == d2


class TestDelete:
    def test_delete_removes_object(self, repo: ModeloDraftRepository) -> None:
        draft = _make_draft()
        repo.save(draft)
        assert repo.delete(draft.draft_id) is True
        assert repo.load(draft.draft_id) is None

    def test_delete_missing_returns_false(self, repo: ModeloDraftRepository) -> None:
        assert repo.delete("never-existed") is False


class TestClassificationGate:
    def test_database_payload_is_encrypted_financial_data(
        self,
        repo: ModeloDraftRepository,
        _active_bucket_runtime: TestRuntimeProfile,
    ) -> None:
        draft = _make_draft()
        repo.save(draft)
        raw = _database_bytes(_active_bucket_runtime.storage_root)
        assert b"secure_objects" in raw
        assert b"00000000T" not in raw
        assert b"2026Q1" not in raw
        assert draft.draft_id.encode("utf-8") not in raw

    def test_foreign_class_object_refused(self, repo: ModeloDraftRepository) -> None:
        draft = _make_draft()
        bad = Envelope[ModeloDraft](
            schema_version=1,
            written_at=_FOREIGN_CLASS_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=draft,
        )
        SecureObjectRepository().save(
            namespace="cadrumo.domain.filing.drafts",
            object_key=draft.draft_id,
            classification=SensitivityClass.OPERATIONAL,
            schema_version=1,
            written_at=bad.written_at,
            payload=bad.model_dump_json().encode("utf-8"),
        )
        with pytest.raises(ClassificationError):
            repo.load(draft.draft_id)


class TestUnsafeDraftIds:
    """Per-draft envelope paths must not compose into traversal."""

    def test_unsafe_draft_id_rejected(self, repo: ModeloDraftRepository) -> None:
        for bad in (
            "",
            "..",
            ".",
            ".hidden",
            "../escape",
            "a/b",
            "a\\b",
        ):
            with pytest.raises(ValueError):
                repo.envelope_path_for(bad)


class TestPerDraftLockIsolation:
    """Per-draft locks so concurrent saves of distinct drafts do not contend.

    Asserts logical lock markers stay distinct while SQL transactions
    govern the actual write isolation.
    """

    def test_lock_target_per_draft(self, repo: ModeloDraftRepository) -> None:
        a = repo.lock_target_for("draft-a")
        b = repo.lock_target_for("draft-b")
        assert a != b
        assert a.parent == b.parent
        assert a.parent == repo.store_dir
        assert a.as_posix().endswith("cadrumo.domain.filing.drafts/draft-a.lock")
        assert b.as_posix().endswith("cadrumo.domain.filing.drafts/draft-b.lock")
