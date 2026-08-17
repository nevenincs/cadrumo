"""Tests for the governed-persistence :class:`~cadrumo.adapters.persistence.profile.filing_amendments.ModeloAmendmentRepository`.

Exercises the round-trip save/load API, list/iter/delete behaviour,
the AUDIT classification gate, the unsafe-id rejection, the
per-amendment lock isolation of
:class:`~cadrumo.adapters.persistence.profile.filing_amendments.ModeloAmendmentRepository`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.filing_amendments import ModeloAmendmentRepository
from ....adapters.persistence.storage import Envelope, SensitivityClass
from ....adapters.persistence.storage.bucket import bucket_paths
from ....adapters.persistence.storage.errors import ClassificationError
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.calculations.registry import RegistrySnapshotRef
from ....domain.filing import (
    CasillaChange,
    ModeloComplementaria,
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
_AMENDMENT_CASILLA: CasillaId = validated_casilla_id("01", surface="_AMENDMENT_CASILLA")
_FOREIGN_CLASS_WRITTEN_AT = datetime(2026, 5, 26, 17, 0, 0, tzinfo=UTC)


def _snapshot_ref(*, modelo: str, period: Period, revision_id: str) -> RegistrySnapshotRef:
    return RegistrySnapshotRef(
        modelo=modelo,
        revision_id=revision_id,
        modelo_year=period.filing_year,
        period=period.registry_token,
    )


def _make_amendment(*, amendment_id: str = "amend-001") -> ModeloComplementaria:
    now = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    values = (
        ModeloValue(
            casilla_id=_AMENDMENT_CASILLA,
            value=Decimal("13000"),
            kind=ModeloValueKind.LITERAL,
            source="test correction",
        ),
    )
    _period = Period.from_year_and_code(2026, "1T")
    snapshot_ref = _snapshot_ref(modelo="130", period=_period, revision_id="2019-y-siguientes")
    amended_draft = ModeloDraft(
        draft_id=compute_modelo_draft_id(
            modelo="130",
            period=_period,
            profile_tax_id="00000000T",
            snapshot_ref=snapshot_ref,
            values=values,
        ),
        modelo="130",
        period=_period,
        profile_tax_id="00000000T",
        subject_tax_id="00000000T",
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.VALIDADO,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version=registry_schema_version(modelo="130", revision_id="2019-y-siguientes"),
    )
    return ModeloComplementaria(
        amendment_id=amendment_id,
        submission_id="sub-abc",
        original_csv="CSVORIG0000001",
        original_model="130",
        original_period=_period,
        delta=(
            CasillaChange(
                casilla_id=_AMENDMENT_CASILLA,
                old_value=Decimal("12500"),
                new_value=Decimal("13000"),
                reason="Test correction.",
            ),
        ),
        amended_draft=amended_draft,
        created_at=now,
    )


def _save_two_amendments(repo: ModeloAmendmentRepository) -> tuple[ModeloComplementaria, ModeloComplementaria]:
    a1 = _make_amendment(amendment_id="amend-a")
    a2 = _make_amendment(amendment_id="amend-b")
    repo.save(a1)
    repo.save(a2)
    return a1, a2


@pytest.fixture
def repo() -> ModeloAmendmentRepository:
    return ModeloAmendmentRepository()


def _database_bytes(storage_root: Path) -> bytes:
    from ....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(bucket_paths(storage_root, _BUCKET_ID).database_file)


class TestEmptyState:
    def test_load_returns_none_when_absent(self, repo: ModeloAmendmentRepository) -> None:
        assert repo.load("missing-id") is None

    def test_object_marker_identifies_secure_backend(self, repo: ModeloAmendmentRepository) -> None:
        assert repo.envelope_path_for("xyz").as_posix().endswith("cadrumo.domain.filing.amendments/xyz")


class TestSaveLoad:
    def test_round_trip(self, repo: ModeloAmendmentRepository) -> None:
        amendment = _make_amendment()
        repo.save(amendment)
        loaded = ModeloAmendmentRepository().load(amendment.amendment_id)
        assert loaded == amendment


class TestListIter:
    def test_list_and_iter(self, repo: ModeloAmendmentRepository) -> None:
        a1, a2 = _save_two_amendments(repo)
        ids = repo.list_amendment_ids()
        assert ids == ("amend-a", "amend-b")
        loaded = {a.amendment_id: a for a in repo.iter_amendments()}
        assert loaded == {a1.amendment_id: a1, a2.amendment_id: a2}


class TestDelete:
    def test_delete_removes(self, repo: ModeloAmendmentRepository) -> None:
        amendment = _make_amendment()
        repo.save(amendment)
        assert repo.delete(amendment.amendment_id) is True
        assert repo.load(amendment.amendment_id) is None

    def test_delete_missing_returns_false(self, repo: ModeloAmendmentRepository) -> None:
        assert repo.delete("nope") is False


class TestClassificationGate:
    def test_database_payload_is_encrypted_audit_data(
        self,
        repo: ModeloAmendmentRepository,
        _active_bucket_runtime: TestRuntimeProfile,
    ) -> None:
        amendment = _make_amendment()
        repo.save(amendment)
        raw = _database_bytes(_active_bucket_runtime.storage_root)
        assert b"secure_objects" in raw
        assert b"CSVORIG0000001" not in raw
        assert b"Test correction" not in raw
        assert amendment.amendment_id.encode("utf-8") not in raw

    def test_foreign_class_object_refused(self, repo: ModeloAmendmentRepository) -> None:
        amendment = _make_amendment()
        bad = Envelope[ModeloComplementaria](
            schema_version=1,
            written_at=_FOREIGN_CLASS_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=amendment,
        )
        SecureObjectRepository().save(
            namespace="cadrumo.domain.filing.amendments",
            object_key=amendment.amendment_id,
            classification=SensitivityClass.OPERATIONAL,
            schema_version=1,
            written_at=bad.written_at,
            payload=bad.model_dump_json().encode("utf-8"),
        )
        with pytest.raises(ClassificationError):
            repo.load(amendment.amendment_id)


class TestUnsafeAmendmentIds:
    def test_unsafe_id_rejected(self, repo: ModeloAmendmentRepository) -> None:
        for bad in ("", "..", ".", ".hidden", "../escape", "a/b", "a\\b"):
            with pytest.raises(ValueError):
                repo.envelope_path_for(bad)
