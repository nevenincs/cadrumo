"""Tests for the governed-persistence :class:`ModeloDraftRepository`.

Exercises round-trip save/load, idempotent saves, list/iter, deletion,
the FINANCIAL classification gate, the unsafe-id rejection, and the
per-draft lock marker isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.errors import ClassificationError
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core import Period
from ....domain.filing._repository import ModeloDraftRepository
from ....domain.filing._schema import (
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_P_Q1 = Period.from_year_and_code(2026, "1T")
_P_Q2 = Period.from_year_and_code(2026, "2T")


def _make_draft(*, period: Period = _P_Q1, ingresos: int = 12500) -> ModeloDraft:
    now = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    values = (
        ModeloValue(
            casilla_id="01",
            value=Decimal(ingresos),
            kind=ModeloValueKind.LITERAL,
            source="test input",
        ),
    )
    draft_id = compute_modelo_draft_id(
        modelo="130",
        period=period,
        profile_tax_id="00000000T",
        schema_version="test-schema-v1",
        values=values,
    )
    return ModeloDraft(
        draft_id=draft_id,
        modelo="130",
        period=period,
        profile_tax_id="00000000T",
        status=ModeloDraftStatus.VALIDADO,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version="test-schema-v1",
    )


def _database_bytes(tmp_path: Path) -> bytes:
    from ....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(tmp_path / "aeat-storage" / "buckets" / "filing-test" / "db" / "aeat.db")


class TestEmptyState:
    def test_load_returns_none_when_absent(self) -> None:
        repo = ModeloDraftRepository()
        assert repo.load("does-not-exist") is None

    def test_object_marker_identifies_secure_backend(self) -> None:
        repo = ModeloDraftRepository()
        assert repo.envelope_path_for("abc123").as_posix().endswith("aeat.domain.filing.drafts/abc123")

    def test_list_draft_ids_empty(self) -> None:
        repo = ModeloDraftRepository()
        assert repo.list_draft_ids() == ()


class TestSaveLoad:
    def test_round_trip_preserves_payload(self) -> None:
        repo = ModeloDraftRepository()
        draft = _make_draft()
        repo.save(draft)

        repo_b = ModeloDraftRepository()
        loaded = repo_b.load(draft.draft_id)
        assert loaded == draft

    def test_save_is_idempotent(self) -> None:
        repo = ModeloDraftRepository()
        draft = _make_draft()
        repo.save(draft)
        repo.save(draft)
        assert repo.list_draft_ids() == (draft.draft_id,)


class TestListAndIter:
    def test_list_returns_persisted_ids_sorted(self) -> None:
        repo = ModeloDraftRepository()
        d1 = _make_draft(period=_P_Q1, ingresos=10000)
        d2 = _make_draft(period=_P_Q2, ingresos=20000)
        repo.save(d1)
        repo.save(d2)
        ids = repo.list_draft_ids()
        assert set(ids) == {d1.draft_id, d2.draft_id}
        assert ids == tuple(sorted(ids))

    def test_iter_drafts_yields_payloads(self) -> None:
        repo = ModeloDraftRepository()
        d1 = _make_draft(period=_P_Q1, ingresos=10000)
        d2 = _make_draft(period=_P_Q2, ingresos=20000)
        repo.save(d1)
        repo.save(d2)
        loaded = {payload.draft_id: payload for payload in repo.iter_drafts()}
        assert loaded[d1.draft_id] == d1
        assert loaded[d2.draft_id] == d2


class TestDelete:
    def test_delete_removes_object(self) -> None:
        repo = ModeloDraftRepository()
        draft = _make_draft()
        repo.save(draft)
        assert repo.delete(draft.draft_id) is True
        assert repo.load(draft.draft_id) is None

    def test_delete_missing_returns_false(self) -> None:
        repo = ModeloDraftRepository()
        assert repo.delete("never-existed") is False


class TestClassificationGate:
    def test_database_payload_is_encrypted_financial_data(self, tmp_path: Path) -> None:
        repo = ModeloDraftRepository()
        draft = _make_draft()
        repo.save(draft)
        raw = _database_bytes(tmp_path)
        assert b"secure_objects" in raw
        assert b"00000000T" not in raw
        assert b"2026Q1" not in raw
        assert draft.draft_id.encode("utf-8") not in raw

    def test_foreign_class_object_refused(self) -> None:
        from ....adapters.persistence.storage import Envelope, SensitivityClass

        draft = _make_draft()
        bad = Envelope[ModeloDraft](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=draft,
        )
        repo = ModeloDraftRepository()
        SecureObjectRepository().save(
            namespace="aeat.domain.filing.drafts",
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

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "..",
            ".",
            ".hidden",
            "../escape",
            "a/b",
            "a\\b",
        ],
    )
    def test_unsafe_draft_id_rejected(self, bad: str) -> None:
        repo = ModeloDraftRepository()
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)


class TestPerDraftLockIsolation:
    """Per-draft locks so concurrent saves of distinct drafts do not contend.

    Asserts logical lock markers stay distinct while SQL transactions
    govern the actual write isolation.
    """

    def test_lock_target_per_draft(self) -> None:
        repo = ModeloDraftRepository()
        a = repo.lock_target_for("draft-a")
        b = repo.lock_target_for("draft-b")
        assert a != b
        assert a.parent == b.parent
        assert a.parent == repo.store_dir
        assert a.as_posix().endswith("aeat.domain.filing.drafts/draft-a.lock")
        assert b.as_posix().endswith("aeat.domain.filing.drafts/draft-b.lock")
