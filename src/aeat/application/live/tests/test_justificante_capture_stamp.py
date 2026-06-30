"""Persisted justificante filing-evidence stamping tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import Modelo, Period
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
from .._justificante import register_capture_as_filing_evidence
from .._snapshot_base import SnapshotLifecycleState
from ._justificante_reconcile_support import (
    MODELO_130_FIXTURE,
    _active_bucket_id,
    _persist_capture,
    _seed_unverified_filing,
    _seed_work_unit,
    isolated_justificante_backend,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_justificante_backend(tmp_path):
        yield


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
    events = (
        BucketEventHistoryRepository()
        .load()
        .for_bucket(bucket_id, event_types=(BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,))
    )
    assert len(events) == 1
    assert events[0].payload_version == 2
    assert events[0].payload["evidence_kind"] == "aeat_live_capture"
    assert events[0].payload["evidence_reference_id"] == "ABCD1234EFGH5678"
    assert events[0].payload["snapshot_id"] == snapshot.snapshot_id
    assert events[0].payload["source_kind"] == "aeat_sede_live_capture"
    assert events[0].payload["pdf_sha256"] == snapshot.pdf_sha256
    assert events[0].payload["captured_at"] == "2026-04-18T10:00:00+00:00"
    assert events[0].payload["expediente_id"] == "202613000010001A"


def test_stamp_keeps_existing_matching_aeat_evidence_without_rewriting_event() -> None:
    """A repeated live capture for the same CSV is idempotent and registers metadata."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(
        work_unit_id=work_unit_id,
        modelo="130",
        filing_year=2026,
        period="1T",
        aeat_accepted=True,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="ABCD1234EFGH5678",
            imported_at=datetime(2026, 4, 18, 9, 30, tzinfo=UTC),
        ),
    )
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    stamped = register_capture_as_filing_evidence(snapshot=snapshot)

    assert stamped.external_evidence is not None
    assert stamped.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert stamped.external_evidence.reference_id == "ABCD1234EFGH5678"
    assert JustificanteRepository().load("ABCD1234EFGH5678") is not None
    bucket_id = _active_bucket_id()
    events = (
        BucketEventHistoryRepository()
        .load()
        .for_bucket(bucket_id, event_types=(BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,))
    )
    assert events == ()


def test_stamp_refuses_to_overwrite_existing_different_aeat_evidence() -> None:
    """Direct live capture must not replace a different official evidence reference."""
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
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(LiveApplicationInputError, match="cannot overwrite existing AEAT evidence"):
        register_capture_as_filing_evidence(snapshot=snapshot)

    assert JustificanteRepository().load("ABCD1234EFGH5678") is None
    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=_active_bucket_id(),
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )
    )
    assert filing is not None
    assert filing.external_evidence is not None
    assert filing.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert filing.external_evidence.reference_id == "DIFFERENTCSV12345"


def test_stamp_refuses_when_snapshot_csv_disagrees_with_parsed_receipt() -> None:
    """Snapshot metadata cannot replace the CSV parsed from the official receipt bytes."""
    from .._errors import LiveApplicationInputError

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    ).model_copy(update={"csv": "DIFFERENTCSV12345"})

    with pytest.raises(LiveApplicationInputError, match="does not match live snapshot csv"):
        register_capture_as_filing_evidence(snapshot=snapshot)

    assert JustificanteRepository().load("ABCD1234EFGH5678") is None
    assert JustificanteRepository().load("DIFFERENTCSV12345") is None
    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=_active_bucket_id(),
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )
    )
    assert filing is not None
    assert filing.external_evidence is None
    assert filing.aeat_accepted is False


def test_stamp_refuses_when_parsed_receipt_does_not_match_filing_modelo() -> None:
    """A capture cannot stamp a filing when the parsed receipt targets another modelo."""
    from .._errors import LiveApplicationInputError

    work_unit_id = _seed_work_unit(modelo="303", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="303", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo="303",
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(LiveApplicationInputError, match="does not match current filing record"):
        register_capture_as_filing_evidence(snapshot=snapshot)

    assert JustificanteRepository().load("ABCD1234EFGH5678") is None
    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=_active_bucket_id(),
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )
    )
    assert filing is not None
    assert filing.external_evidence is None
    assert filing.aeat_accepted is False


def test_stamp_refuses_non_active_live_capture_snapshot() -> None:
    """Only the current ACTIVE live capture may become filing evidence."""
    from .._errors import LiveApplicationInputError

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    active_snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )
    superseded_snapshot = active_snapshot.model_copy(
        update={
            "state": SnapshotLifecycleState.SUPERSEDED,
            "superseded_by_snapshot_id": "successor-snapshot-id",
        },
    )

    with pytest.raises(LiveApplicationInputError, match="cannot stamp superseded live-capture snapshot"):
        register_capture_as_filing_evidence(snapshot=superseded_snapshot)

    assert JustificanteRepository().load("ABCD1234EFGH5678") is None
    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=_active_bucket_id(),
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )
    )
    assert filing is not None
    assert filing.external_evidence is None
    assert filing.aeat_accepted is False


def test_stamp_refuses_when_parsed_receipt_does_not_match_filing_year() -> None:
    """A capture cannot stamp a filing when the parsed receipt targets another year."""
    from .._errors import LiveApplicationInputError

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2025, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2025, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2025,
        period="1T",
    )

    with pytest.raises(LiveApplicationInputError, match="does not match current filing record"):
        register_capture_as_filing_evidence(snapshot=snapshot)

    assert JustificanteRepository().load("ABCD1234EFGH5678") is None
    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=_active_bucket_id(),
            modelo="130",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
        )
    )
    assert filing is not None
    assert filing.external_evidence is None
    assert filing.aeat_accepted is False


def test_stamp_refuses_when_parsed_receipt_does_not_match_filing_period() -> None:
    """A capture cannot stamp a filing when the parsed receipt targets another period."""
    from .._errors import LiveApplicationInputError

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="2T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="2T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="2T",
    )

    with pytest.raises(LiveApplicationInputError, match="does not match current filing record"):
        register_capture_as_filing_evidence(snapshot=snapshot)

    assert JustificanteRepository().load("ABCD1234EFGH5678") is None
    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=_active_bucket_id(),
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "2T"),
        )
    )
    assert filing is not None
    assert filing.external_evidence is None
    assert filing.aeat_accepted is False


def test_stamp_refuses_when_parsed_receipt_does_not_match_profile_tax_id() -> None:
    """A live-captured receipt cannot stamp a filing for a different taxpayer profile."""
    from .._errors import LiveApplicationInputError

    workflow_state_repository().update(
        lambda state: set_active_fields(
            state,
            (UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        ),
    )
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(LiveApplicationInputError, match="does not match current filing record"):
        register_capture_as_filing_evidence(snapshot=snapshot)

    assert JustificanteRepository().load("ABCD1234EFGH5678") is None
    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=_active_bucket_id(),
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )
    )
    assert filing is not None
    assert filing.external_evidence is None
    assert filing.aeat_accepted is False


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
