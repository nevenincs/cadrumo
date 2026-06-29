"""Justificante capture orchestrator filing-evidence tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import Period
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.justificante import JustificanteRepository
from ....domain.modelos import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecordCatalogueRepository,
)
from ....domain.user_profile import UserProfileFact
from ...user_profile._orchestration import set_active_fields
from ...workflow._persistence import workflow_state_repository
from .. import capture_justificante_snapshot, capture_justificante_snapshot_outcome
from ._justificante_reconcile_support import (
    MODELO_130_FIXTURE,
    _active_bucket_id,
    _capture_providers,
    _seed_unverified_filing,
    _seed_work_unit,
    isolated_justificante_backend,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_justificante_backend(tmp_path):
        yield


def test_capture_orchestrator_stamps_evidence_when_period_is_filed() -> None:
    """Per the design, the capture flow stamps official evidence in the same flow."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    bucket_id = _active_bucket_id()
    session, declarations, expedientes, capture = _capture_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

    persisted = asyncio.run(
        capture_justificante_snapshot(
            bucket_id=bucket_id,
            modelo="130",
            year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            session_provider=session,
            declarations_provider=declarations,
            expedientes_provider=expedientes,
            justificante_provider=capture,
        ),
    )

    assert persisted.period == Period.from_year_and_code(2026, "1T")
    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=bucket_id,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )
    )
    assert filing is not None
    assert filing.external_evidence is not None
    assert filing.external_evidence.kind is ExternalEvidenceKind.AEAT_LIVE_CAPTURE
    events = (
        BucketEventHistoryRepository()
        .load()
        .for_bucket(bucket_id, event_types=(BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,))
    )
    assert len(events) == 1


def test_capture_orchestrator_outcome_reports_stamped_filing_record() -> None:
    """The live pull outcome exposes whether the capture locked to a local filing."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    filing = _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    bucket_id = _active_bucket_id()
    session, declarations, expedientes, capture = _capture_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

    outcome = asyncio.run(
        capture_justificante_snapshot_outcome(
            bucket_id=bucket_id,
            modelo="130",
            year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            session_provider=session,
            declarations_provider=declarations,
            expedientes_provider=expedientes,
            justificante_provider=capture,
        ),
    )

    assert outcome.snapshot.csv == "ABCD1234EFGH5678"
    assert outcome.justificante_metadata_registered is True
    assert outcome.filing_evidence_stamped is True
    assert outcome.filing_record_id == filing.filing_record_id


def test_capture_orchestrator_skips_stamp_when_period_not_filed() -> None:
    """A capture for a period with no in-app filing record persists but stamps nothing."""
    _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    bucket_id = _active_bucket_id()
    session, declarations, expedientes, capture = _capture_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

    persisted = asyncio.run(
        capture_justificante_snapshot(
            bucket_id=bucket_id,
            modelo="130",
            year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            session_provider=session,
            declarations_provider=declarations,
            expedientes_provider=expedientes,
            justificante_provider=capture,
        ),
    )

    assert persisted.snapshot_id  # the snapshot is still persisted
    assert JustificanteRepository().load("ABCD1234EFGH5678") is not None
    events = (
        BucketEventHistoryRepository()
        .load()
        .for_bucket(bucket_id, event_types=(BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,))
    )
    assert events == ()


def test_capture_orchestrator_outcome_reports_unstamped_when_period_not_filed() -> None:
    """A persisted capture with no local filing reports no filing evidence enrolment."""
    _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    bucket_id = _active_bucket_id()
    session, declarations, expedientes, capture = _capture_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

    outcome = asyncio.run(
        capture_justificante_snapshot_outcome(
            bucket_id=bucket_id,
            modelo="130",
            year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            session_provider=session,
            declarations_provider=declarations,
            expedientes_provider=expedientes,
            justificante_provider=capture,
        ),
    )

    assert outcome.snapshot.csv == "ABCD1234EFGH5678"
    assert outcome.justificante_metadata_registered is True
    assert outcome.filing_evidence_stamped is False
    assert outcome.filing_record_id is None
    assert JustificanteRepository().load("ABCD1234EFGH5678") is not None


def test_capture_orchestrator_refuses_conflicting_existing_aeat_evidence() -> None:
    """A live pull must not hide a current filing record's conflicting AEAT evidence."""
    from .._errors import LiveApplicationInputError

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(
        work_unit_id=work_unit_id,
        modelo="130",
        filing_year=2026,
        period="1T",
        aeat_accepted=True,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="DIFFERENTCSV12345",
            imported_at=datetime(2026, 4, 18, 9, 30, tzinfo=UTC),
        ),
    )
    bucket_id = _active_bucket_id()
    session, declarations, expedientes, capture = _capture_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

    with pytest.raises(LiveApplicationInputError, match="cannot overwrite existing AEAT evidence"):
        asyncio.run(
            capture_justificante_snapshot(
                bucket_id=bucket_id,
                modelo="130",
                year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                session_provider=session,
                declarations_provider=declarations,
                expedientes_provider=expedientes,
                justificante_provider=capture,
            ),
        )

    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=bucket_id,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )
    )
    assert filing is not None
    assert filing.external_evidence is not None
    assert filing.external_evidence.reference_id == "DIFFERENTCSV12345"


def test_capture_orchestrator_refuses_current_filing_taxpayer_mismatch() -> None:
    """A live pull cannot silently skip a taxpayer mismatch on an existing filing record."""
    from .._errors import LiveApplicationInputError

    workflow_state_repository().update(
        lambda state: set_active_fields(
            state,
            (UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        ),
    )
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    bucket_id = _active_bucket_id()
    session, declarations, expedientes, capture = _capture_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

    with pytest.raises(LiveApplicationInputError, match="does not match current filing record"):
        asyncio.run(
            capture_justificante_snapshot(
                bucket_id=bucket_id,
                modelo="130",
                year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                session_provider=session,
                declarations_provider=declarations,
                expedientes_provider=expedientes,
                justificante_provider=capture,
            ),
        )

    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=bucket_id,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )
    )
    assert filing is not None
    assert filing.external_evidence is None
    assert filing.aeat_accepted is False
