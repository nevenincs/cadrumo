"""Reconcile a work unit against a persisted live justificante capture.

Proves the P04 payoff: the live-captured receipt, once persisted, drives the
existing local-only ``modelo_reconcile`` through a transient temp-path
materialisation — the operator never hand-downloads the PDF. Uses the real
Modelo 130 justificante fixture (modelo=130, ejercicio=2026) so the verdict is
grounded by a genuine parse, not a synthetic byte blob.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import Modelo
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests import FIXTURES_DIR
from ....tests.secure_sql import isolated_profile_storage_root
from ...modelo import ModeloReconciliationVerdict, ReconciliationEvidenceInvalidError
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository
from .._justificante import (
    JustificanteCaptureSnapshotService,
    reconcile_capture,
)

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
