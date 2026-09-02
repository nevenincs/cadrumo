from __future__ import annotations

import hashlib
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import ExternalEvidence, ModeloRecord, ModeloRecordStatus, derive_filing_record_id
from ....domain.modelos.filing_repository import upsert_filing_record
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....tests import FIXTURES_DIR
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...workflow.persistence import workflow_state_repository

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"
_EXP_130_1T = "13020260410ABCD1234EFGH5678"
_WORK_UNIT_TIMESTAMP = datetime(2026, 5, 28, 15, 45, tzinfo=UTC)


@contextmanager
def isolated_justificante_backend(tmp_path: Path) -> Generator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session("11111111-1111-4111-8111-111111111111"),
    ):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(
            profile_id="11111111-1111-4111-8111-111111111111",
            overrides={"identity.tax_id": "00000000T"},
        )
        yield


def _active_bucket_id() -> str:
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _seed_work_unit(*, modelo: str, filing_year: int, period: str) -> str:
    bucket_id = _active_bucket_id()
    revision_id = "r" + "0" * 63
    filing_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=_WORK_UNIT_TIMESTAMP,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def _persist_capture(*, pdf_bytes: bytes, modelo: str, filing_year: int, period: str):
    from ..justificante import JustificanteCaptureSnapshotService

    bucket_id = _active_bucket_id()
    return JustificanteCaptureSnapshotService(bucket_id=bucket_id).capture(
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        expediente_id=_EXP_130_1T,
        csv="ABCD1234EFGH5678",
        pdf_bytes=pdf_bytes,
        pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        captured_at=datetime(2026, 4, 18, 10, 0, tzinfo=UTC),
    )


def _seed_unverified_filing(
    *,
    work_unit_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    member_nif: str | None = None,
    aeat_accepted: bool = False,
    external_evidence: ExternalEvidence | None = None,
) -> ModeloRecord:
    bucket_id = _active_bucket_id()
    revision_id = hashlib.sha256(f"rev:{work_unit_id}".encode()).hexdigest()
    filing_period = Period.from_year_and_code(filing_year, period)
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="operator",
        member_nif=member_nif,
    )
    filing = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        member_nif=member_nif,
        filed_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
        filed_by="operator",
        aeat_accepted=aeat_accepted,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=external_evidence,
    )
    repo = ModeloRecordCatalogueRepository()
    repo.save(upsert_filing_record(repo.load(), filing))
    return filing
