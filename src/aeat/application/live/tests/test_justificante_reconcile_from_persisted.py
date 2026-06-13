"""Reconcile a work unit against a persisted live justificante capture.

Proves the P04 payoff: the live-captured receipt, once persisted, drives the
existing local-only reconciliation logic from secure-storage bytes — the
operator never hand-downloads the PDF and the service never writes decrypted
evidence to a temp file. Uses the real Modelo 130 justificante fixture
(modelo=130, ejercicio=2026) so the verdict is grounded by a genuine parse, not
a synthetic byte blob.
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
from ....core import Modelo, Period
from ....core.config import Settings
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.justificante import JustificanteRepository
from ....domain.modelos import (
    ExternalEvidence,
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
from ....domain.user_profile import UserProfileFact
from ....tests import FIXTURES_DIR
from ....tests.secure_sql import isolated_profile_storage_root
from ...modelo import ModeloReconciliationVerdict, ReconciliationEvidenceInvalidError, list_modelo_reconciliations
from ...user_profile._orchestration import profile_create_storage_span, set_active_fields
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository
from .. import capture_justificante_snapshot, capture_justificante_snapshot_outcome
from .._justificante import (
    JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
    JustificanteCaptureSnapshotService,
    reconcile_capture,
    register_capture_as_filing_evidence,
)
from .._snapshot_base import SnapshotLifecycleState

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from ....adapters.outbound.aeat.auth import AeatSession
    from ....core.config import Settings

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="operator",
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
    bucket_id = _active_bucket_id()
    return JustificanteCaptureSnapshotService(bucket_id=bucket_id).capture(
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
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
    assert report.source_path == f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot.snapshot_id}"
    history = list_modelo_reconciliations(bucket_id=_active_bucket_id(), work_unit_id=work_unit_id)
    assert len(history) == 1
    assert history[0].source_path == report.source_path


def test_reconcile_from_persisted_capture_writes_nothing_to_disk(tmp_path: Path) -> None:
    """The live reconcile parses the receipt from in-memory bytes only.

    Honours ``sensitive-financial-data-secure-storage-only``: the decrypted
    justificante bytes must never touch disk. The real secure store and parser
    run unmocked; this test makes any disk materialisation observable by (a)
    redirecting every ``tempfile`` allocation primitive into a tripwire that
    raises if the reconcile path tries to materialise a plaintext file, and (b)
    snapshotting the process default temp directory and asserting it gains no
    new entries across the reconcile call.
    """
    import tempfile

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    temp_root = Path(tempfile.gettempdir())
    before = {entry.name for entry in temp_root.iterdir()} if temp_root.is_dir() else set()

    def _tripwire(*_args: object, **_kwargs: object):
        raise AssertionError(
            "the live justificante reconcile materialised a decrypted PDF to a "
            "temp file; secure-storage bytes must be parsed in memory only",
        )

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(tempfile, "mkstemp", _tripwire)
        patcher.setattr(tempfile, "NamedTemporaryFile", _tripwire)
        patcher.setattr(tempfile, "TemporaryFile", _tripwire)
        patcher.setattr(tempfile, "mkdtemp", _tripwire)
        report = reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    after = {entry.name for entry in temp_root.iterdir()} if temp_root.is_dir() else set()
    assert after - before == set(), "reconcile left a new file in the temp directory"


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

    The persisted secure object reference is the only source identifier surfaced
    in the error; no plaintext filesystem path is involved.
    """
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=b"%PDF-1.4\nnot a real justificante\n%%EOF\n",
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(ReconciliationEvidenceInvalidError) as exc_info:
        reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)
    message = str(exc_info.value)
    assert f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot.snapshot_id}" in message
    assert "Temp" not in message
    assert ".pdf" not in message


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
    assert events[0].payload["evidence_kind"] == "aeat_live_capture"
    assert events[0].payload["evidence_reference_id"] == "ABCD1234EFGH5678"


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


_EXP_130_1T = "202613000010001A"
_AEAT = Settings.external_constants().aeat


def _seam_providers(*, pdf_bytes: bytes):
    """Seam providers for capture_justificante_snapshot returning real typed records."""

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


def test_capture_orchestrator_stamps_evidence_when_period_is_filed() -> None:
    """Per the design, the capture flow stamps official evidence in the same flow."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _seed_unverified_filing(work_unit_id=work_unit_id, modelo="130", filing_year=2026, period="1T")
    bucket_id = _active_bucket_id()
    session, declarations, expedientes, capture = _seam_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

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
    session, declarations, expedientes, capture = _seam_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

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
    assert outcome.filing_evidence_stamped is True
    assert outcome.filing_record_id == filing.filing_record_id


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
            period=Period.from_year_and_code(2026, "1T"),
            session_provider=session,
            declarations_provider=declarations,
            expedientes_provider=expedientes,
            justificante_provider=capture,
        ),
    )

    assert persisted.snapshot_id  # the snapshot is still persisted
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
    session, declarations, expedientes, capture = _seam_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

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
    assert outcome.filing_evidence_stamped is False
    assert outcome.filing_record_id is None


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
    session, declarations, expedientes, capture = _seam_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

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
    session, declarations, expedientes, capture = _seam_providers(pdf_bytes=MODELO_130_FIXTURE.read_bytes())

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
