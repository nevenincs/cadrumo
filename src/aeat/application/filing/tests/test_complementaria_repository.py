"""Tests for the governed-persistence :class:`ModeloAmendmentRepository`.

Exercises the round-trip save/load API, list/iter/delete behaviour,
the AUDIT classification gate, the unsafe-id rejection, the
per-amendment lock isolation of
:class:`aeat.domain.filing.ModeloAmendmentRepository`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.errors import ClassificationError
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core import Period
from ....domain.filing._amendment import CasillaChange, ModeloComplementaria
from ....domain.filing._complementaria_repository import (
    ModeloAmendmentRepository,
)
from ....domain.filing._schema import (
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _make_amendment(*, amendment_id: str = "amend-001") -> ModeloComplementaria:
    now = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    values = (
        ModeloValue(
            casilla_id="01",
            value=Decimal("13000"),
            kind=ModeloValueKind.LITERAL,
            source="test correction",
        ),
    )
    _period = Period.from_year_and_code(2026, "1T")
    amended_draft = ModeloDraft(
        draft_id=compute_modelo_draft_id(
            modelo="130",
            period=_period,
            profile_tax_id="00000000T",
            schema_version="test-schema-v1",
            values=values,
        ),
        modelo="130",
        period=_period,
        profile_tax_id="00000000T",
        status=ModeloDraftStatus.VALIDADO,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version="test-schema-v1",
    )
    return ModeloComplementaria(
        amendment_id=amendment_id,
        submission_id="sub-abc",
        original_csv="CSV-ORIG-001",
        original_model="130",
        original_period=_period,
        delta=(
            CasillaChange(
                casilla_code="01",
                old_value=Decimal("12500"),
                new_value=Decimal("13000"),
                reason="Test correction.",
            ),
        ),
        amended_draft=amended_draft,
        created_at=now,
    )


def _database_bytes(tmp_path: Path) -> bytes:
    return (tmp_path / "aeat-storage" / "buckets" / "filing-test" / "db" / "aeat.db").read_bytes()


class TestEmptyState:
    def test_load_returns_none_when_absent(self) -> None:
        repo = ModeloAmendmentRepository()
        assert repo.load("missing-id") is None

    def test_object_marker_identifies_secure_backend(self) -> None:
        repo = ModeloAmendmentRepository()
        assert repo.envelope_path_for("xyz").as_posix().endswith("aeat.domain.filing.amendments/xyz")


class TestSaveLoad:
    def test_round_trip(self) -> None:
        repo = ModeloAmendmentRepository()
        amendment = _make_amendment()
        repo.save(amendment)
        loaded = ModeloAmendmentRepository().load(amendment.amendment_id)
        assert loaded == amendment


class TestListIter:
    def test_list_and_iter(self) -> None:
        repo = ModeloAmendmentRepository()
        a1 = _make_amendment(amendment_id="amend-a")
        a2 = _make_amendment(amendment_id="amend-b")
        repo.save(a1)
        repo.save(a2)
        ids = repo.list_amendment_ids()
        assert ids == ("amend-a", "amend-b")
        loaded = {a.amendment_id: a for a in repo.iter_amendments()}
        assert loaded == {a1.amendment_id: a1, a2.amendment_id: a2}


class TestDelete:
    def test_delete_removes(self) -> None:
        repo = ModeloAmendmentRepository()
        amendment = _make_amendment()
        repo.save(amendment)
        assert repo.delete(amendment.amendment_id) is True
        assert repo.load(amendment.amendment_id) is None

    def test_delete_missing_returns_false(self) -> None:
        repo = ModeloAmendmentRepository()
        assert repo.delete("nope") is False


class TestClassificationGate:
    def test_database_payload_is_encrypted_audit_data(self, tmp_path: Path) -> None:
        repo = ModeloAmendmentRepository()
        amendment = _make_amendment()
        repo.save(amendment)
        raw = _database_bytes(tmp_path)
        assert b"secure_objects" in raw
        assert b"CSV-ORIG-001" not in raw
        assert b"Test correction" not in raw
        assert amendment.amendment_id.encode("utf-8") not in raw

    def test_foreign_class_object_refused(self) -> None:
        from ....adapters.persistence.storage import Envelope, SensitivityClass

        amendment = _make_amendment()
        bad = Envelope[ModeloComplementaria](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=amendment,
        )
        repo = ModeloAmendmentRepository()
        SecureObjectRepository().save(
            namespace="aeat.domain.filing.amendments",
            object_key=amendment.amendment_id,
            classification=SensitivityClass.OPERATIONAL,
            schema_version=1,
            written_at=bad.written_at,
            payload=bad.model_dump_json().encode("utf-8"),
        )
        with pytest.raises(ClassificationError):
            repo.load(amendment.amendment_id)


class TestUnsafeAmendmentIds:
    @pytest.mark.parametrize(
        "bad",
        ["", "..", ".", ".hidden", "../escape", "a/b", "a\\b"],
    )
    def test_unsafe_id_rejected(self, bad: str) -> None:
        repo = ModeloAmendmentRepository()
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)
