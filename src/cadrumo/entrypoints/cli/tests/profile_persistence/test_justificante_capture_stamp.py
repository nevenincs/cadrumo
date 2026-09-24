"""Persisted justificante filing-evidence stamping tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.adapters.inbound.justificante.parser import parse_justificante_bytes
from cadrumo.adapters.outbound.aeat.sede.filed_observation_persistence import FilingReconciliationAdapter
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.entrypoints.cli.tests.profile_persistence._justificante_reconcile_support import (
    MODELO_130_FIXTURE,
    _active_bucket_id,
    _persist_capture,
    _seed_unverified_filing,
    _seed_work_unit,
)
from cadrumo.adapters.persistence.storage.tests.active_profile_isolated_backend_fixture import (
    active_profile_isolated_backend_fixture,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import set_active_test_profile_facts
from cadrumo.application.live.errors import LiveApplicationInputError
from cadrumo.application.live.justificante import register_capture_as_filing_evidence
from cadrumo.application.live.justificante_ports import JustificanteRegistrationPorts
from cadrumo.application.live.snapshot_base import SnapshotLifecycleState
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.modelos.filing_record import ExternalEvidence, ExternalEvidenceKind
from cadrumo.domain.user_profile.values import UserProfileFact

isolated_backend = active_profile_isolated_backend_fixture(profile_overrides={"identity.tax_id": "00000000T"})

__all__ = ["isolated_backend"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


def _registration_ports() -> JustificanteRegistrationPorts:
    filing = ModeloRecordCatalogueRepository()
    justificantes = JustificanteRepository()
    return JustificanteRegistrationPorts(
        parse_pdf=parse_justificante_bytes,
        metadata=justificantes,
        filing=filing,
        filing_reconciliation=FilingReconciliationAdapter(
            work_lifecycle_ports=WorkLifecyclePorts(
                work_unit_repository=WorkUnitCatalogueRepository(),
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            filing_repository=filing,
            justificante_repository=justificantes,
            observation_repository=CalculationObservationRepository(),
        ),
    )


def _current_filing(*, filing_year: int = 2026, period: str = "1T"):
    return (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=_active_bucket_id(),
            modelo="130",
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, period),
        )
    )


def test_a_receipt_without_comparable_totals_does_not_confirm_a_pending_filing() -> None:
    """A receipt alone is not proof that the pending local filing is what AEAT holds.

    Modelo 130 declares no receipt-total reconciliation map, so the receipt
    cannot be compared with the local figures. The receipt is registered, the
    pending filing stays unconfirmed, and the reconciliation is recorded.
    """
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo("130").value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.filing_record_unconfirmed",
    ):
        register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

    assert JustificanteRepository().load("ABCD1234EFGH5678") is not None
    filing = _current_filing()
    assert filing is not None
    assert filing.external_evidence is None
    assert filing.aeat_accepted is False
    events = (
        BucketEventHistoryRepository()
        .load()
        .for_bucket(_active_bucket_id(), event_types=(BucketEventType.MODELO_FILING_RECONCILED,))
    )
    assert [
        (event.payload["outcome"], event.payload["notice_count"], event.payload["notice_codes_sha256"])
        for event in events
    ] == [
        ("unverifiable", "1", sha256_hex(b"receipt_totals_not_reconciled")),
    ]


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
        modelo=Modelo("130").value,
        filing_year=2026,
        period="1T",
    )

    stamped = register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

    assert stamped.external_evidence is not None
    assert stamped.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert stamped.external_evidence.reference_id == "ABCD1234EFGH5678"
    assert JustificanteRepository().load("ABCD1234EFGH5678") is not None
    bucket_id = _active_bucket_id()
    events = (
        BucketEventHistoryRepository()
        .load()
        .for_bucket(bucket_id, event_types=(BucketEventType.MODELO_FILING_RECONCILED,))
    )
    assert events == ()


def test_stamp_refuses_to_overwrite_existing_different_aeat_evidence() -> None:
    """Direct live capture must not replace a different official evidence reference."""
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
        modelo=Modelo("130").value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.evidence_overwrite_refused",
    ):
        register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

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
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo("130").value,
        filing_year=2026,
        period="1T",
    ).model_copy(update={"csv": "DIFFERENTCSV12345"})

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.csv_mismatch",
    ):
        register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

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


def test_a_capture_whose_expediente_is_not_the_receipt_presentation_id_reaches_reconciliation() -> None:
    """A divergent register expediente id is not a receipt mismatch; the csv is the axis.

    The expediente id and the receipt's Número de justificante are different
    AEAT identifier namespaces, so their disagreement must not be refused as a
    mismatch. The capture reaches the reconciliation, which records the
    expediente it was given.
    """
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    captured = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo("130").value,
        filing_year=2026,
        period="1T",
    )
    snapshot = captured.model_copy(update={"expediente_id": "13020260410DIFFERENTIDENT"})
    assert snapshot.expediente_id != captured.expediente_id, (
        "the expediente id was not actually changed, so nothing diverges here"
    )

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.filing_record_unconfirmed",
    ):
        register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

    assert JustificanteRepository().load("ABCD1234EFGH5678") is not None
    events = (
        BucketEventHistoryRepository()
        .load()
        .for_bucket(_active_bucket_id(), event_types=(BucketEventType.MODELO_FILING_RECONCILED,))
    )
    assert [event.payload["aeat_expediente_id"] for event in events] == ["13020260410DIFFERENTIDENT"]


def test_stamp_refuses_when_parsed_receipt_does_not_match_filing_modelo() -> None:
    """A capture cannot stamp a filing when the parsed receipt targets another modelo."""
    work_unit_id = _seed_work_unit(modelo="303", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="303", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo="303",
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.filing_record_mismatch",
    ):
        register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

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
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    active_snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo("130").value,
        filing_year=2026,
        period="1T",
    )
    superseded_snapshot = active_snapshot.model_copy(
        update={
            "state": SnapshotLifecycleState.SUPERSEDED,
            "superseded_by_snapshot_id": "successor-snapshot-id",
        },
    )

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.evidence_snapshot_not_active",
    ):
        register_capture_as_filing_evidence(
            snapshot=superseded_snapshot,
            ports=_registration_ports(),
        )

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
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2025, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2025, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo("130").value,
        filing_year=2025,
        period="1T",
    )

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.filing_record_mismatch",
    ):
        register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

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
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="2T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="2T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo("130").value,
        filing_year=2026,
        period="2T",
    )

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.filing_record_mismatch",
    ):
        register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

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
    set_active_test_profile_facts(
        (UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo("130").value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.filing_record_mismatch",
    ):
        register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

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
    _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo("130").value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.filing_record_missing",
    ):
        register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())
