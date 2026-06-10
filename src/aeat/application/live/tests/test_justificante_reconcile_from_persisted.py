"""Reconcile a work unit against a persisted live justificante capture.

Proves the P04 payoff: the live-captured receipt, once persisted, drives the
existing local-only ``modelo_reconcile`` through a transient temp-path
materialisation — the operator never hand-downloads the PDF. Uses the real
Modelo 130 justificante fixture (modelo=130, ejercicio=2026) so the verdict is
grounded by a genuine parse, not a synthetic byte blob.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import Declaracion, Expediente, JustificanteRef, SedeCapture
from ....core import Modelo
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.justificante import JustificanteRepository
from ....domain.modelos import (
    ExternalEvidenceKind,
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
from ...modelo import ModeloReconciliationVerdict, ReconciliationEvidenceInvalidError
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository
from .. import capture_justificante_snapshot
from .._justificante import (
    JustificanteCaptureSnapshotService,
    reconcile_capture,
    register_capture_as_filing_evidence,
)

if TYPE_CHECKING:
    from ....adapters.outbound.aeat.auth import AeatSession
    from ....core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
        yield


def _active_bucket_id() -> str:
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _seed_work_unit(*, modelo: str, filing_year: int, period: str) -> str:
    bucket_id = _active_bucket_id()
    revision_id = "r" + "0" * 63
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def _persist_capture(*, pdf_bytes: bytes, modelo: str, filing_year: int, period: str):
    bucket_id = _active_bucket_id()
    return JustificanteCaptureSnapshotService(bucket_id=bucket_id).capture(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        expediente_id="202613000010001A",
        csv="ABCD1234EFGH5678",
        pdf_bytes=pdf_bytes,
        pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        captured_at=datetime(2026, 4, 18, 10, 0, tzinfo=UTC),
    )


def test_reconcile_from_persisted_capture_matches() -> None:
    """A persisted real-fixture capture reconciles to MATCHES against its work unit."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    report = reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert report.diffs == ()
    assert report.work_unit_id == work_unit_id


def test_reconcile_from_persisted_capture_mismatches_on_modelo() -> None:
    """A 303 work unit reconciled against the persisted 130 capture mismatches."""
    work_unit_id = _seed_work_unit(modelo="303", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    report = reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    assert any(diff.field_name == "modelo" for diff in report.diffs)


def test_reconcile_from_malformed_capture_raises_without_leaking_temp_path() -> None:
    """A capture whose bytes are not a parseable justificante refuses cleanly.

    The transient materialisation path is system-generated and deleted after the
    call; the parser redaction keeps any caller-controlled path out of the
    surfaced error.
    """
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=b"%PDF-1.4\nnot a real justificante\n%%EOF\n",
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(ReconciliationEvidenceInvalidError):
        reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)


def _seed_unverified_filing(*, work_unit_id: str, modelo: str, filing_year: int, period: str) -> None:
    bucket_id = _active_bucket_id()
    revision_id = hashlib.sha256(f"rev:{work_unit_id}".encode()).hexdigest()
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
        filed_by="operator",
    )
    repo = ModeloRecordCatalogueRepository()
    repo.save(
        upsert_filing_record(
            repo.load(),
            ModeloRecord(
                filing_record_id=filing_id,
                work_unit_id=work_unit_id,
                calculation_revision_id=revision_id,
                bucket_id=bucket_id,
                modelo=ModeloCode(modelo),
                filing_year=filing_year,
                period=period,
                filed_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
                filed_by="operator",
                aeat_accepted=False,
                status=ModeloRecordStatus.VIGENTE,
                external_evidence=None,
            ),
        )
    )


def test_stamp_registers_justificante_and_marks_filing_live_captured() -> None:
    """register_capture_as_filing_evidence registers the receipt and stamps the filing."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    stamped = register_capture_as_filing_evidence(snapshot=snapshot)

    assert stamped.external_evidence is not None
    assert stamped.external_evidence.kind is ExternalEvidenceKind.AEAT_LIVE_CAPTURE
    assert stamped.external_evidence.reference_id == "ABCD1234EFGH5678"
    assert stamped.aeat_accepted is True
    # The receipt is registered and loadable by the evidence reference id.
    assert JustificanteRepository().load("ABCD1234EFGH5678") is not None
    # The stamp leaves an audit-trail event.
    bucket_id = _active_bucket_id()
    events = BucketEventHistoryRepository().load().for_bucket(
        bucket_id, event_types=(BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,)
    )
    assert len(events) == 1
    assert events[0].payload["evidence_kind"] == "aeat_live_capture"
    assert events[0].payload["evidence_reference_id"] == "ABCD1234EFGH5678"


def test_stamp_refuses_when_no_current_filing_exists() -> None:
    """Stamping refuses when the captured period has no filing record yet."""
    from .._errors import LiveApplicationInputError

    _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(LiveApplicationInputError, match="no current filing record"):
        register_capture_as_filing_evidence(snapshot=snapshot)


_EXP_130_1T = "202613000010001A"


def _seam_providers(*, pdf_bytes: bytes):
    """Seam providers for capture_justificante_snapshot returning real typed records."""

    async def _session() -> tuple[AeatSession, Settings]:
        return cast("tuple[AeatSession, Settings]", (object(), object()))

    async def _declarations(session: object, settings: object, *, modelo: str, year: int):
        return (
            Declaracion(
                modelo="130",
                ejercicio=2026,
                period="1T",
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
                detail_url=AnyHttpUrl(f"https://sede.agenciatributaria.gob.es/acc?exp={_EXP_130_1T}"),
            ),
        )

    async def _capture(session: object, settings: object, *, expediente: Expediente):
        ref = JustificanteRef(
            csv="ABCD1234EFGH5678",
            expediente_id=expediente.expediente_id,
            cotejo_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/cotejo/CotejoIdSv?CSV=ABCD1234EFGH5678"),
            pdf_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/cotejo/CotejoDocIdSv?CSV=ABCD1234EFGH5678"),
        )
        return SedeCapture(
            expediente=expediente,
            ref=ref,
            pdf_bytes=pdf_bytes,
            pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            captured_at=datetime(2026, 4, 18, 10, 0, tzinfo=UTC),
        )

    return _session, _declarations, _expedientes, _capture


def test_capture_orchestrator_stamps_evidence_when_period_is_filed() -> None:
    """Per the ADR, the capture flow stamps official evidence in the same flow."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    bucket_id = _active_bucket_id()
    session, declarations, expedientes, capture = _seam_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

    persisted = asyncio.run(
        capture_justificante_snapshot(
            bucket_id=bucket_id,
            modelo="130",
            year=2026,
            period="1T",
            session_provider=session,
            declarations_provider=declarations,
            expedientes_provider=expedientes,
            justificante_provider=capture,
        )
    )

    assert persisted.period == "1T"
    filing = ModeloRecordCatalogueRepository().load().current_for(
        bucket_id=bucket_id, modelo="130", filing_year=2026, period="1T"
    )
    assert filing is not None
    assert filing.external_evidence is not None
    assert filing.external_evidence.kind is ExternalEvidenceKind.AEAT_LIVE_CAPTURE
    events = BucketEventHistoryRepository().load().for_bucket(
        bucket_id, event_types=(BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,)
    )
    assert len(events) == 1


def test_capture_orchestrator_skips_stamp_when_period_not_filed() -> None:
    """A capture for a period with no in-app filing record persists but stamps nothing."""
    _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    bucket_id = _active_bucket_id()
    session, declarations, expedientes, capture = _seam_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

    persisted = asyncio.run(
        capture_justificante_snapshot(
            bucket_id=bucket_id,
            modelo="130",
            year=2026,
            period="1T",
            session_provider=session,
            declarations_provider=declarations,
            expedientes_provider=expedientes,
            justificante_provider=capture,
        )
    )

    assert persisted.snapshot_id  # the snapshot is still persisted
    events = BucketEventHistoryRepository().load().for_bucket(
        bucket_id, event_types=(BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,)
    )
    assert events == ()
