from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import Declaracion, Expediente, JustificanteRef, SedeCapture
from ....core import Period
from ....core.config import Settings
from ....domain.modelos import (
    ExternalEvidence,
    ModeloRecord,
    ModeloRecordCatalogueRepository,
    ModeloRecordStatus,
    derive_filing_record_id,
    upsert_filing_record,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests import FIXTURES_DIR
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository

if TYPE_CHECKING:
    from ....adapters.outbound.aeat.auth import AeatSession

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"
_EXP_130_1T = "202613000010001A"
_AEAT = Settings.external_constants().aeat


@contextmanager
def isolated_justificante_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("11111111-1111-4111-8111-111111111111"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="11111111-1111-4111-8111-111111111111",
                overrides={"identity.tax_id": "00000000T"},
            ),
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
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def _persist_capture(*, pdf_bytes: bytes, modelo: str, filing_year: int, period: str):
    from .._justificante import JustificanteCaptureSnapshotService

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
        filed_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
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


def _capture_providers(*, pdf_bytes: bytes):
    async def _session() -> tuple[AeatSession, Settings]:
        return cast("tuple[AeatSession, Settings]", (object(), object()))

    async def _declarations(session: object, settings: object, *, modelo: str, year: int):
        return (
            Declaracion(
                modelo="130",
                ejercicio=2026,
                period=Period.from_year_and_code(2026, "1T"),
                expediente_id=_EXP_130_1T,
                estado="ALTA",
                presented_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
            ),
        )

    async def _expedientes(session: object, settings: object, *, modelo: str):
        return (
            Expediente(
                expediente_id=_EXP_130_1T,
                modelo="130",
                ejercicio=2026,
                category_path=("AEAT", "Modelo 130"),
                detail_url=AnyHttpUrl(
                    f"{_AEAT.domains.sede}"
                    f"{_AEAT.sede_paths.expediente_detail_template.format(expediente_id=_EXP_130_1T)}",
                ),
            ),
        )

    async def _capture(session: object, settings: object, *, expediente: Expediente):
        ref = JustificanteRef(
            csv="ABCD1234EFGH5678",
            expediente_id=expediente.expediente_id,
            cotejo_url=AnyHttpUrl(f"{_AEAT.domains.sede}{_AEAT.sede_paths.cotejo_query}?CSV=ABCD1234EFGH5678"),
            pdf_url=AnyHttpUrl(f"{_AEAT.domains.sede}{_AEAT.sede_paths.cotejo_document}?CSV=ABCD1234EFGH5678"),
        )
        return SedeCapture(
            expediente=expediente,
            ref=ref,
            pdf_bytes=pdf_bytes,
            pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            captured_at=datetime(2026, 4, 18, 10, 0, tzinfo=UTC),
        )

    return _session, _declarations, _expedientes, _capture
