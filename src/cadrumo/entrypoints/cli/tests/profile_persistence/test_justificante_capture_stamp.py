"""Persisted justificante filing-evidence stamping tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.inbound.justificante.parser import parse_justificante_bytes
from cadrumo.adapters.outbound.aeat.sede.filed_observation_persistence import FilingReconciliationAdapter
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.storage.tests.active_profile_isolated_backend_fixture import (
    active_profile_isolated_backend_fixture,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import set_active_test_profile_facts
from cadrumo.application.live.errors import LiveApplicationInputError
from cadrumo.application.live.filed_observation_ports import FiledFilingReconciliationPort
from cadrumo.application.live.justificante import register_capture_as_filing_evidence
from cadrumo.application.live.justificante_ports import JustificanteRegistrationPorts
from cadrumo.application.live.snapshot_base import SnapshotLifecycleState
from cadrumo.application.modelo.filing_chain_reconciliation import AeatRegisterEntry, FilingReconciliationResult
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.core.time.clock import MADRID_TZ, madrid_wall_clock_to_utc
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.schema_base import SettlementDirection
from cadrumo.domain.justificante.schema import Justificante
from cadrumo.domain.modelos.filing_record import AeatConfirmationState, ExternalEvidence, ExternalEvidenceKind
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.cli.tests.profile_persistence.justificante_reconcile_support import (
    _M111_EXPEDIENTE_ID,
    MODELO_111_RECEIPT_FIXTURE,
    MODELO_130_FIXTURE,
    active_bucket_id,
    persist_capture,
    seed_unverified_filing,
    seed_work_unit,
)
from cadrumo.tests.fixtures.justificantes.generate_base import MODELO_111_2026_Q1_TOTAL_A_INGRESAR

isolated_backend = active_profile_isolated_backend_fixture(profile_overrides={"identity.tax_id": "00000000T"})

__all__ = ["isolated_backend"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


@dataclass(frozen=True, slots=True)
class _RecordingReconciliation:
    """Observe the register entry the real reconciliation is handed, and delegate."""

    inner: FiledFilingReconciliationPort
    observed: list[AeatRegisterEntry]

    def reconcile(
        self,
        entry: AeatRegisterEntry,
        *,
        actor: str,
        clock: datetime,
        authority_operation: PinnedAuthorityOperation | None = None,
    ) -> FilingReconciliationResult:
        """Record the entry, then let the real reconciliation decide."""
        self.observed.append(entry)
        return self.inner.reconcile(entry, actor=actor, clock=clock, authority_operation=authority_operation)


def _reconciliation_total_target(receipt: Justificante) -> str:
    """Return the casilla the receipt's ``ingresar`` total reconciles against.

    Read from the modelo's own snapshot: the expectation that declares the
    reconciliation total owns which casilla it is, and naming one here would
    put a registry fact in a test.
    """
    snapshot = published_authority_operation().snapshot(
        receipt.modelo,
        filing_year=receipt.period.filing_year,
        period=receipt.period.registry_token,
    )
    targets = {
        str(kind): casilla_id
        for expectation in snapshot.revision.verification_expectations
        for kind, casilla_id in expectation.reconciliation_total_casilla_ids.items()
    }
    target = targets.get(SettlementDirection.INGRESAR.value)
    assert target is not None, f"Modelo {receipt.modelo} declares no ingresar reconciliation total casilla"
    return str(target)


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
            bucket_id=active_bucket_id(),
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
    work_unit_id = seed_work_unit(modelo="130", filing_year=2026, period="1T")
    seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    snapshot = persist_capture(
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
        .for_bucket(active_bucket_id(), event_types=(BucketEventType.MODELO_FILING_RECONCILED,))
    )
    assert [
        (event.payload["outcome"], event.payload["notice_count"], event.payload["notice_codes_sha256"])
        for event in events
    ] == [
        ("unverifiable", "1", sha256_hex(b"receipt_totals_not_reconciled")),
    ]


def test_stamp_keeps_existing_matching_aeat_evidence_without_rewriting_event() -> None:
    """An incomparable repeated receipt preserves prior evidence and registers metadata."""
    work_unit_id = seed_work_unit(modelo="130", filing_year=2026, period="1T")
    existing = seed_unverified_filing(
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
    snapshot = persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo("130").value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.filing_record_unconfirmed",
    ) as exc_info:
        register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

    assert exc_info.value.context is not None
    assert exc_info.value.context["outcome"] == "unverifiable"
    assert exc_info.value.context["notices"] == "receipt_totals_not_reconciled"
    stamped = _current_filing()
    assert stamped == existing
    assert stamped is not None
    assert stamped.external_evidence is not None
    assert stamped.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert stamped.external_evidence.reference_id == "ABCD1234EFGH5678"
    assert JustificanteRepository().load("ABCD1234EFGH5678") is not None
    bucket_id = active_bucket_id()
    events = (
        BucketEventHistoryRepository()
        .load()
        .for_bucket(bucket_id, event_types=(BucketEventType.MODELO_FILING_RECONCILED,))
    )
    assert events == ()


def test_stamp_refuses_to_overwrite_existing_different_aeat_evidence() -> None:
    """Direct live capture must not replace a different official evidence reference."""
    work_unit_id = seed_work_unit(modelo="130", filing_year=2026, period="1T")
    seed_unverified_filing(
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
    snapshot = persist_capture(
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
            bucket_id=active_bucket_id(),
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
    work_unit_id = seed_work_unit(modelo="130", filing_year=2026, period="1T")
    seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    snapshot = persist_capture(
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
            bucket_id=active_bucket_id(),
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
    work_unit_id = seed_work_unit(modelo="130", filing_year=2026, period="1T")
    seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    captured = persist_capture(
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
        .for_bucket(active_bucket_id(), event_types=(BucketEventType.MODELO_FILING_RECONCILED,))
    )
    assert [event.payload["aeat_expediente_id"] for event in events] == ["13020260410DIFFERENTIDENT"]


def test_the_capture_entry_carries_the_receipts_own_presentation_instant() -> None:
    """The register entry says when AEAT stamped the receipt.

    The entry used to carry identifiers only, so a chain entry built from a
    live capture could not say when the declaration was presented, and so could
    not say whether it was presented inside the plazo. The receipt prints that
    timestamp without an offset, as peninsular official time.
    """
    receipt = parse_justificante_bytes(MODELO_130_FIXTURE.read_bytes())
    assert receipt.presented_at.tzinfo is None, "the receipt still prints an offset-free wall clock"
    work_unit_id = seed_work_unit(modelo="130", filing_year=2026, period="1T")
    seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    snapshot = persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo("130").value,
        filing_year=2026,
        period="1T",
    )
    observed: list[AeatRegisterEntry] = []
    ports = _registration_ports()
    recording = replace(ports, filing_reconciliation=_RecordingReconciliation(ports.filing_reconciliation, observed))

    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.filing_record_unconfirmed",
    ):
        register_capture_as_filing_evidence(snapshot=snapshot, ports=recording)

    assert len(observed) == 1
    presented_at = observed[0].register.presented_at
    assert presented_at is not None
    assert presented_at == madrid_wall_clock_to_utc(receipt.presented_at)
    assert presented_at.astimezone(MADRID_TZ).replace(tzinfo=None) == receipt.presented_at


def test_stamp_refuses_when_parsed_receipt_does_not_match_filing_modelo() -> None:
    """A capture cannot stamp a filing when the parsed receipt targets another modelo."""
    work_unit_id = seed_work_unit(modelo="303", filing_year=2026, period="1T")
    seed_unverified_filing(work_unit_id=work_unit_id, modelo="303", filing_year=2026, period="1T")
    snapshot = persist_capture(
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
            bucket_id=active_bucket_id(),
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
    work_unit_id = seed_work_unit(modelo="130", filing_year=2026, period="1T")
    seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    active_snapshot = persist_capture(
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
            bucket_id=active_bucket_id(),
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
    work_unit_id = seed_work_unit(modelo="130", filing_year=2025, period="1T")
    seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2025, period="1T")
    snapshot = persist_capture(
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
            bucket_id=active_bucket_id(),
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
    work_unit_id = seed_work_unit(modelo="130", filing_year=2026, period="2T")
    seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="2T")
    snapshot = persist_capture(
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
            bucket_id=active_bucket_id(),
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
    work_unit_id = seed_work_unit(modelo="130", filing_year=2026, period="1T")
    seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    snapshot = persist_capture(
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
            bucket_id=active_bucket_id(),
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
    seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = persist_capture(
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


def test_a_reconciling_capture_confirms_the_chain_and_keeps_the_presentation_instant() -> None:
    """A receipt whose total reconciles confirms the filing and dates it.

    Every other case in this module ends in a refusal, so nothing here used to
    exercise a COMMITTED AEAT-origin chain entry: the register reference built
    on confirmation was asserted only at the reconciliation seam. This case
    completes it. Modelo 111 is the bundled family whose snapshot declares a
    reconciliation total casilla, so it is the one receipt a confirmation can
    reconcile against; the revision is seeded with the same casilla 30 value the
    receipt prints, read from the fixture rather than repeated here.

    The confirmed entry carries the receipt's own presentation instant, read on
    the Spanish civil clock the receipt prints it in.
    """
    receipt = parse_justificante_bytes(MODELO_111_RECEIPT_FIXTURE.read_bytes())
    printed_total = receipt.total_a_ingresar
    assert printed_total is not None, "the 111 receipt fixture prints a total a ingresar"
    assert printed_total == Decimal(MODELO_111_2026_Q1_TOTAL_A_INGRESAR)
    target = _reconciliation_total_target(receipt)

    work_unit_id = seed_work_unit(modelo="111", filing_year=2026, period="1T")
    pending = seed_unverified_filing(
        work_unit_id=work_unit_id,
        modelo="111",
        filing_year=2026,
        period="1T",
        casilla_values={target: printed_total},
    )
    snapshot = persist_capture(
        pdf_bytes=MODELO_111_RECEIPT_FIXTURE.read_bytes(),
        modelo=Modelo("111").value,
        filing_year=2026,
        period="1T",
        expediente_id=_M111_EXPEDIENTE_ID,
        csv=receipt.csv,
    )

    confirmed = register_capture_as_filing_evidence(snapshot=snapshot, ports=_registration_ports())

    assert confirmed.filing_record_id == pending.filing_record_id
    assert confirmed.confirmation is AeatConfirmationState.CONFIRMADA
    assert confirmed.aeat_accepted is True
    assert confirmed.external_evidence is not None
    assert confirmed.external_evidence.kind is ExternalEvidenceKind.AEAT_LIVE_CAPTURE
    assert confirmed.aeat_register is not None
    assert confirmed.aeat_register.csv == receipt.csv
    presented_at = confirmed.aeat_register.presented_at
    assert presented_at is not None
    assert presented_at == madrid_wall_clock_to_utc(receipt.presented_at)
    assert presented_at.astimezone(MADRID_TZ).replace(tzinfo=None) == receipt.presented_at
