"""Real-behavior gates for repositories migrated to storage runtime defaults."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from aeat.adapters.outbound.aeat.auth import _session_store
from aeat.adapters.outbound.aeat.auth._clave_movil import CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE
from aeat.adapters.outbound.aeat.sede import ExpedienteNotFoundError
from aeat.adapters.outbound.aeat.sede._observation_store import FiledDeclaracionObservationStore
from aeat.adapters.outbound.aeat.sede._schema import FiledDeclaracionArtefact
from aeat.adapters.outbound.google import _session_store as google_session_store
from aeat.adapters.outbound.google._records import REQUIRED_SCOPES, DriveConfig, OAuthClient, OAuthMetadata, OAuthToken
from aeat.adapters.outbound.llm._cache import LLMCache
from aeat.adapters.outbound.llm._models import LLMProvider, LLMRequest, LLMResponse, UsageRecord
from aeat.adapters.outbound.llm._usage import UsageRecorder
from aeat.adapters.persistence.profile.assets import (
    load_amortizacion_ledger,
    load_assets,
    save_amortizacion_ledger,
    save_assets,
)
from aeat.adapters.persistence.profile.inventory import load_inventory, save_inventory
from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider, SensitivityClass
from aeat.adapters.persistence.storage.attachment import AttachmentStore
from aeat.adapters.persistence.storage.errors import StorageValidationError
from aeat.adapters.persistence.storage.master_key._active_session import activate_session
from aeat.adapters.persistence.storage.master_key._bucket_session import BucketSession
from aeat.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.auth._diagnostics import list_auth_diagnostics
from aeat.application.calculations._iva_compensation_history import (
    IvaCompensationHistoryRepository,
    IvaCompensationPeriodState,
)
from aeat.application.calculations._observations_repository import CalculationObservationRepository
from aeat.application.diagnostics import preview_quarantine_unreadable_secure_objects
from aeat.application.filing import ModeloHistory, ModeloHistoryEntry
from aeat.application.filing._history_repository import ModeloHistoryRepository
from aeat.application.live._borrador_100 import Borrador100Snapshot, Borrador100SnapshotRepository
from aeat.application.live._snapshot_base import SnapshotLifecycleState
from aeat.application.repair_integrity import (
    RepairRemediationDecision,
    RepairRemediationDecisionRepository,
    repair_remediation_decision_id,
)
from aeat.application.workflow import DeclaracionPointer, WorkflowResult, WorkflowStage, WorkflowState, WorkflowStep
from aeat.application.workflow._persistence import WorkflowRunRepository, WorkflowStateRepository
from aeat.core.config import override_settings
from aeat.domain.attachments import AttachmentNotFoundError
from aeat.domain.buckets import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from aeat.domain.calculations.registry import RegistrySnapshotRef
from aeat.domain.calculations.registry import RegistryModeloObservation
from aeat.domain.categories import SpendingCategory
from aeat.domain.filing import (
    AmendmentKind,
    CasillaChange,
    ModeloAmendmentRepository,
    ModeloComplementaria,
    ModeloDraft,
    ModeloDraftRepository,
    ModeloDraftStatus,
    ModeloValue,
    ModeloValueKind,
    make_amendment_id,
)
from aeat.domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceKind,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from aeat.domain.justificante import Justificante
from aeat.domain.justificante._repository import JustificanteRepository
from aeat.domain.modelos import ModeloCode
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from aeat.domain.modelos._filing_record import (
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from aeat.domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.domain.modelos._verification_report import (
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from aeat.domain.modelos._verification_repository import VerificationReportCatalogueRepository
from aeat.domain.modelos._work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from aeat.domain.profile.assets import AmortizacionEntry, AmortizacionLedger, AssetClass, AssetRecord
from aeat.domain.profile.inventory import InventoryLedger, ValuationMethod
from aeat.domain.submission import (
    ModeloPresentado,
    SubmissionAttempt,
    SubmissionRepository,
    SubmissionStatus,
    make_submission_id,
)
from aeat.domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from aeat.domain.usage_ratios import UsageRatioProfile, load_usage_ratios, save_usage_ratios

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

_KEK = b"k" * 32
_DEK = b"d" * 32
_MASTER_KEY = b"m" * 32
_GOOGLE_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path) -> Iterator[None]:
    with override_settings(aeat_local_storage_root=tmp_path) as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


@contextmanager
def _active_runtime(tmp_path: Path, bucket_id: str) -> Iterator[None]:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=bucket_id) as settings:
        dispose_engine(settings)
        with EphemeralMasterKeyProvider(key=_MASTER_KEY):
            try:
                yield
            finally:
                dispose_engine(settings)


def _session(bucket_id: str) -> BucketSession:
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def _workflow_state(label: str) -> WorkflowState:
    now = datetime.now(UTC).replace(microsecond=0)
    return WorkflowState(
        declarations={
            f"303:{label}": DeclaracionPointer(
                modelo="303",
                period=label,
                draft_id="d" * 64,
                status="BORRADOR",
                updated_at=now,
            )
        },
        updated_at=now,
    )


def _transaction(label: str) -> Transaction:
    raw = RawTransaction(
        transaction_id=f"tx-{label}",
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=Decimal("-121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description=f"runtime migrated repository {label}",
        provenance=RawProvenance(
            source_path=Path(f"/bank/{label}.csv"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime.now(UTC).replace(microsecond=0),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": f"runtime migrated repository {label}"},
    )
    return Transaction.model_validate({"raw": raw, "direction": TransactionDirection.OUTGOING})


def _asset(identifier: str) -> AssetRecord:
    return AssetRecord(
        identifier=identifier,
        description=f"runtime migrated asset {identifier}",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2026, 1, 1),
        cost_basis=Decimal("1000.00"),
    )


def _storage_state(label: str) -> dict[str, object]:
    return {
        "cookies": [
            {
                "name": "AEAT_SESSION",
                "value": label,
                "domain": ".agenciatributaria.gob.es",
                "path": "/",
            }
        ],
        "origins": [],
    }


def _hex(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _workflow_run(label: str) -> WorkflowResult:
    when = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    step = WorkflowStep(
        stage=WorkflowStage.LOADING_PROFILE,
        started_at=when,
        ended_at=when,
        success=True,
        summary=f"runtime migrated workflow run {label}",
    )
    return WorkflowResult(
        run_id=_hex(f"workflow-run-{label}")[:16],
        started_at=when,
        ended_at=when,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        steps=(step,),
        summary=f"runtime migrated workflow run {label}",
    )


def _bucket_event(label: str) -> BucketEvent:
    occurred_at = datetime(2026, 5, 26, 10, 0, tzinfo=UTC)
    payload = {"label": label}
    return BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=label,
            event_type=BucketEventType.PROFILE_SELECTED,
            occurred_at=occurred_at,
            actor="operator",
            object_type=BucketEventObjectType.PROFILE,
            object_id=label,
            payload=payload,
        ),
        bucket_id=label,
        event_type=BucketEventType.PROFILE_SELECTED,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=label,
        payload_version=1,
        payload=payload,
    )


def _invoice(label: str) -> Invoice:
    line = InvoiceLine(
        description=f"runtime migrated invoice line {label}",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    return Invoice(
        kind=InvoiceKind.ISSUED,
        invoice_number=f"INV-{label.upper()}",
        issued_at=date(2026, 4, 1),
        counterparty_name="Cliente SL",
        counterparty_tax_id="B12345674",
        counterparty_country="ES",
        base_total=Decimal("100.00"),
        iva_total=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="EUR",
        lines=(line,),
        payment_status=PaymentStatus.PENDING,
        linked_transaction_ids=(),
    )


def _modelo_draft(label: str) -> ModeloDraft:
    now = datetime.now(UTC).replace(microsecond=0)
    return ModeloDraft(
        draft_id=_hex(f"draft-{label}"),
        modelo="303",
        period="2026Q1",
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id="2026-y-siguientes",
            modelo_year=2026,
            period="1T",
        ),
        status=ModeloDraftStatus.BORRADOR,
        values=(
            ModeloValue(
                casilla_id=f"iva.devengado.{label}",
                value=Decimal("100.00"),
                kind=ModeloValueKind.LITERAL,
                source="runtime migrated repository test",
            ),
        ),
        binding_values=(),
        findings=(),
        created_at=now,
        updated_at=now,
        schema_version="schema-2026-1",
    )


def _modelo_amendment(label: str) -> ModeloComplementaria:
    draft = _modelo_draft(label)
    delta = (
        CasillaChange(
            casilla_code="iva.devengado",
            old_value=Decimal("100.00"),
            new_value=Decimal("121.00"),
            reason=f"runtime migrated amendment {label}",
        ),
    )
    submission_id = f"S-{label}"
    return ModeloComplementaria(
        amendment_id=make_amendment_id(
            submission_id=submission_id,
            amendment_kind=AmendmentKind.COMPLEMENTARIA,
            delta=delta,
        ),
        submission_id=submission_id,
        original_csv="ABCD12345678EFGH",
        original_model="303",
        original_period="2026Q1",
        delta=delta,
        amended_draft=draft,
        created_at=datetime.now(UTC).replace(microsecond=0),
    )


def _submission(label: str) -> ModeloPresentado:
    submitted_at = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    draft_id = f"draft-{label}"
    submission_id = make_submission_id(draft_id, 1)
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=draft_id,
        modelo="303",
        period="2026Q1",
        profile_tax_id="00000000T",
        status=SubmissionStatus.PRESENTADA,
        submitted_at=submitted_at,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{submission_id}.1",
                started_at=submitted_at,
                ended_at=submitted_at,
                status=SubmissionStatus.PRESENTADA,
            ),
        ),
    )


def _justificante(tmp_path: Path, label: str) -> Justificante:
    csv = f"CSV{_hex(label)[:13].upper()}"
    pdf = tmp_path / f"{csv}.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%EOF\n")
    return Justificante(
        csv=csv,
        modelo="303",
        period="1T",
        ejercicio="2026",
        presentation_id=None,
        presented_at=datetime(2026, 4, 10, 11, 23, 45, tzinfo=UTC),
        tax_id="00000000T",
        total_a_ingresar=Decimal("10.00"),
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python("https://sede.agenciatributaria.gob.es/verify"),
        source_pdf_path=pdf,
        source_pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
        parsed_at=datetime(2026, 4, 12, tzinfo=UTC),
    )


def _work_unit(bucket_id: str, label: str) -> WorkUnit:
    now = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    modelo = ModeloCode("303")
    period = "1T"
    revision_id = f"revision-{label}"
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=2026,
        period=period,
        revision_id=revision_id,
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name=f"IVA 2026 {label}",
        created_at=now,
        updated_at=now,
        state=WorkUnitState.BORRADOR,
    )


def _calculation_catalogue(label: str) -> CalculationRevisionCatalogue:
    work_unit_id = _hex(f"work-unit-{label}")
    values = {"casilla-01": Decimal("100.00")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={"base": "100.00"},
        binding_overrides={},
        casilla_values=values,
        source_transaction_ids=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        inputs_snapshot={"base": "100.00"},
        binding_overrides={},
        source_transaction_ids=(),
        casilla_values=values,
        created_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
    )
    return CalculationRevisionCatalogue(revisions={revision_id: revision})


def _filing_record_catalogue(bucket_id: str, label: str) -> ModeloRecordCatalogue:
    filed_at = datetime(2026, 5, 26, 11, 0, tzinfo=UTC)
    work_unit_id = _hex(f"filing-work-unit-{label}")
    revision_id = _hex(f"filing-revision-{label}")
    record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
    )
    record = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period="1T",
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
        notes=f"runtime migrated filing record {label}",
        aeat_accepted=True,
    )
    return ModeloRecordCatalogue(records={record_id: record})


def _verification_catalogue(label: str) -> VerificationReportCatalogue:
    run_at = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
    revision_id = _hex(f"verification-revision-{label}")
    report_id = derive_verification_report_id(
        calculation_revision_id=revision_id,
        run_at=run_at,
        verified_by="aeat.cli.modelo.verify",
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.COMPLETE,
        findings=(),
        resolved_casillas=("iva.devengado",),
        missing_required_casillas=(),
        run_at=run_at,
        verified_by="aeat.cli.modelo.verify",
        granted_verificado_completo=True,
    )
    return VerificationReportCatalogue(reports={report_id: report})


def _history(label: str) -> ModeloHistory:
    submitted_at = datetime(2026, 5, 26, 13, 0, tzinfo=UTC)
    return ModeloHistory(
        modelo="303",
        entries=(
            ModeloHistoryEntry(
                modelo="303",
                period=f"2026Q1-{label}",
                submitted_at=submitted_at,
                status="presentada",
            ),
        ),
    )


def _iva_state(label: str) -> IvaCompensationPeriodState:
    period = "1TA" if label.endswith("a") else "1TB"
    return IvaCompensationPeriodState(
        taxpayer_nif="00000000T",
        filing_year=2026,
        period=period,
        expediente_id="202610013522456T",
        status="presentada",
        presented_at=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
        generated_amount=Decimal("10.00"),
        available_end_amount=Decimal("10.00"),
        source_observation_key=f"303:2026:1T:{label}",
    )


def _usage_profile(category: SpendingCategory, ratio: str) -> UsageRatioProfile:
    return UsageRatioProfile(ratios={category: Decimal(ratio)})


def _inventory_ledger(label: str) -> InventoryLedger:
    return InventoryLedger(
        actividad_id=f"retail-{label}",
        year=2026,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("0.00"),
    )


def _amortizacion_ledger(label: str) -> AmortizacionLedger:
    entry = AmortizacionEntry(asset_id=f"asset-{label}", year=2026, amount=Decimal("1.00"))
    return AmortizacionLedger(entries=(entry,))


def _google_records(label: str) -> tuple[OAuthClient, OAuthToken, OAuthMetadata, DriveConfig]:
    issued_at = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    return (
        OAuthClient.model_validate(
            {
                "client_id": f"desktop-{label}.apps.googleusercontent.com",
                "client_secret": f"secret-{label}",
                "project_id": f"aeat-vault-{label}",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": _GOOGLE_OAUTH_ENDPOINT,
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ("http://127.0.0.1:8765/callback",),
            }
        ),
        OAuthToken.model_validate(
            {"refresh_token": f"1//refresh-token-{label}", "token_uri": _GOOGLE_OAUTH_ENDPOINT}
        ),
        OAuthMetadata(
            account_email=f"{label}@example.com",
            granted_scopes=REQUIRED_SCOPES,
            issued_at=issued_at,
            last_refresh_at=issued_at,
        ),
        DriveConfig(root_folder_id=f"drive-folder-{label}"),
    )


def _llm_request() -> LLMRequest:
    return LLMRequest(prompt="Summarise a runtime storage migration", cache_key="runtime-storage")


def _llm_response(label: str) -> LLMResponse:
    return LLMResponse(
        text=f"runtime migrated response {label}",
        provider=LLMProvider.OPENAI,
        model="gpt-test",
        input_tokens=10,
        output_tokens=5,
        cost_estimate_usd=Decimal("0.01"),
        cache_hit=False,
        created_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        request_id=f"request-{label}",
    )


def _usage_record(label: str) -> UsageRecord:
    response = _llm_response(label)
    return UsageRecord(
        prompt_id="runtime-storage",
        caller="s87",
        text=response.text,
        provider=response.provider,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_estimate_usd=response.cost_estimate_usd,
        cache_hit=response.cache_hit,
        created_at=response.created_at,
        request_id=response.request_id,
    )


def _sede_artefact(label: str) -> tuple[FiledDeclaracionArtefact, bytes]:
    body = f"runtime migrated sede artefact {label}".encode()
    return (
        FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=TypeAdapter(AnyHttpUrl).validate_python("https://sede.agenciatributaria.gob.es/file"),
            content_type="application/pdf",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        ),
        body,
    )


def _borrador_snapshot(bucket_id: str, label: str) -> Borrador100Snapshot:
    return Borrador100Snapshot(
        snapshot_id=f"snapshot-{label}",
        bucket_id=bucket_id,
        modelo="100",
        filing_year=2026,
        period="0A",
        captured_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        source_url="https://sede.agenciatributaria.gob.es/borrador/100",
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={"casilla-001": Decimal("1.00")},
    )


def _repair_decision(label: str) -> RepairRemediationDecision:
    decided_at = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    target_namespace = "aeat.test.runtime.migrated"
    reason = f"runtime migrated repair decision {label}"
    likely_origin = "runtime family gate"
    decision_id = repair_remediation_decision_id(
        target_namespace=target_namespace,
        target_object_key_digest=None,
        outcome="preserve",
        decided_at=decided_at,
        decided_by="operator",
        reason=reason,
        likely_origin=likely_origin,
        replacement_evidence_requirements=(),
        verified_replacement_evidence_refs=(),
    )
    return RepairRemediationDecision(
        decision_id=decision_id,
        target_namespace=target_namespace,
        target_object_key_digest=None,
        outcome="preserve",
        decided_at=decided_at,
        decided_by="operator",
        reason=reason,
        likely_origin=likely_origin,
        replacement_evidence_requirements=(),
        verified_replacement_evidence_refs=(),
    )


def _save_auth_diagnostic(label: str) -> None:
    payload = {
        "diagnostic_id": f"diagnostic-{label}",
        "reason": "runtime migrated auth diagnostic",
        "url": "https://sede.agenciatributaria.gob.es/auth",
        "captured_at": datetime(2026, 5, 26, 9, 0, tzinfo=UTC).isoformat(),
        "auth_attempt": {"auth_mode": "clave", "headless": True},
    }
    secure_object_repository_for_active_bucket().save(
        namespace=CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
        object_key=payload["diagnostic_id"],
        classification=SensitivityClass.SESSION,
        schema_version=1,
        written_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        payload=json.dumps(payload, sort_keys=True).encode(),
    )


def _save_diagnostic_probe_row(label: str) -> None:
    secure_object_repository_for_active_bucket().save(
        namespace="aeat.test.runtime.migrated.diagnostics",
        object_key=f"diagnostic-probe-{label}",
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        payload=f"diagnostic-probe-{label}".encode(),
    )


@pytest.mark.parametrize(
    ("case_name", "operation"),
    (
        ("workflow_state", lambda: WorkflowStateRepository().load()),
        ("workflow_runs", lambda: WorkflowRunRepository().list()),
        ("bucket_events", lambda: BucketEventHistoryRepository().load()),
        ("auth_diagnostics", list_auth_diagnostics),
        ("auth_session", lambda: _session_store.load(Path("/profile/active/aeat-session"))),
        ("google_oauth_client", lambda: google_session_store.load_client("operator-google")),
        ("google_oauth_token", lambda: google_session_store.load_token("operator-google")),
        ("google_oauth_metadata", lambda: google_session_store.load_metadata("operator-google")),
        ("google_drive_config", lambda: google_session_store.load_drive_config("operator-google")),
        ("llm_cache_stats", lambda: LLMCache(root_dir=Path("runtime-cache")).stats()),
        ("llm_usage_load", lambda: UsageRecorder(root_dir=Path("runtime-usage")).load_records()),
        (
            "sede_artefact",
            lambda: FiledDeclaracionObservationStore(Path("sede-cache")).load_artefact(
                "secure-object:financial:" + "a" * 64
            ),
        ),
        (
            "sede_observation",
            lambda: FiledDeclaracionObservationStore(Path("sede-cache")).load_observation(Path("observation")),
        ),
        ("attachment", lambda: AttachmentStore().read_bytes("a" * 64)),
        ("transactions", lambda: TransactionCatalogueRepository(bucket_id="bucket-a").load()),
        ("invoices", lambda: InvoiceCatalogueRepository().load()),
        ("filing_drafts", lambda: ModeloDraftRepository(bucket_id="bucket-a").load("d" * 64)),
        ("filing_amendments", lambda: ModeloAmendmentRepository(bucket_id="bucket-a").load("amendment-a")),
        ("submission", lambda: SubmissionRepository().list_submission_ids()),
        ("justificante", lambda: JustificanteRepository().list_csvs()),
        ("filing_history", lambda: ModeloHistoryRepository(bucket_id="bucket-a").list_modelos()),
        ("modelo_work_units", lambda: WorkUnitCatalogueRepository(bucket_id="bucket-a").load()),
        ("modelo_calculation_revisions", lambda: CalculationRevisionCatalogueRepository(bucket_id="bucket-a").load()),
        ("modelo_filing_records", lambda: ModeloRecordCatalogueRepository(bucket_id="bucket-a").load()),
        ("modelo_verification_reports", lambda: VerificationReportCatalogueRepository(bucket_id="bucket-a").load()),
        (
            "calculation_observations",
            lambda: CalculationObservationRepository(bucket_id="bucket-a").load_observation("303", 2026, "1T"),
        ),
        ("iva_compensation_history", lambda: IvaCompensationHistoryRepository(bucket_id="bucket-a").list_periods()),
        ("usage_ratios", lambda: load_usage_ratios(bucket_id="bucket-a")),
        ("borrador_100_snapshot", lambda: Borrador100SnapshotRepository(bucket_id="bucket-a").list_snapshots()),
        ("repair_decisions", lambda: RepairRemediationDecisionRepository().list_decisions()),
        ("profile_assets", load_assets),
        ("profile_inventory", load_inventory),
        ("profile_amortizacion", load_amortizacion_ledger),
    ),
)
def test_migrated_runtime_defaults_refuse_missing_session(
    tmp_path: Path,
    case_name: str,
    operation: Callable[[], object],
) -> None:
    del case_name
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="bucket-a"),
        pytest.raises(StorageValidationError, match="no active bucket session"),
    ):
        operation()


@pytest.mark.parametrize(
    ("case_name", "operation"),
    (
        ("workflow_state", lambda: WorkflowStateRepository().load()),
        ("workflow_runs", lambda: WorkflowRunRepository().list()),
        ("bucket_events", lambda: BucketEventHistoryRepository().load()),
        ("auth_diagnostics", list_auth_diagnostics),
        ("auth_session", lambda: _session_store.load(Path("/profile/active/aeat-session"))),
        ("google_oauth_client", lambda: google_session_store.load_client("operator-google")),
        ("google_oauth_token", lambda: google_session_store.load_token("operator-google")),
        ("google_oauth_metadata", lambda: google_session_store.load_metadata("operator-google")),
        ("google_drive_config", lambda: google_session_store.load_drive_config("operator-google")),
        ("llm_cache_stats", lambda: LLMCache(root_dir=Path("runtime-cache")).stats()),
        ("llm_usage_load", lambda: UsageRecorder(root_dir=Path("runtime-usage")).load_records()),
        (
            "sede_artefact",
            lambda: FiledDeclaracionObservationStore(Path("sede-cache")).load_artefact(
                "secure-object:financial:" + "a" * 64
            ),
        ),
        (
            "sede_observation",
            lambda: FiledDeclaracionObservationStore(Path("sede-cache")).load_observation(Path("observation")),
        ),
        ("attachment", lambda: AttachmentStore().read_bytes("a" * 64)),
        ("transactions", lambda: TransactionCatalogueRepository(bucket_id="bucket-a").load()),
        ("invoices", lambda: InvoiceCatalogueRepository().load()),
        ("filing_drafts", lambda: ModeloDraftRepository(bucket_id="bucket-a").load("d" * 64)),
        ("filing_amendments", lambda: ModeloAmendmentRepository(bucket_id="bucket-a").load("amendment-a")),
        ("submission", lambda: SubmissionRepository().list_submission_ids()),
        ("justificante", lambda: JustificanteRepository().list_csvs()),
        ("filing_history", lambda: ModeloHistoryRepository(bucket_id="bucket-a").list_modelos()),
        ("modelo_work_units", lambda: WorkUnitCatalogueRepository(bucket_id="bucket-a").load()),
        ("modelo_calculation_revisions", lambda: CalculationRevisionCatalogueRepository(bucket_id="bucket-a").load()),
        ("modelo_filing_records", lambda: ModeloRecordCatalogueRepository(bucket_id="bucket-a").load()),
        ("modelo_verification_reports", lambda: VerificationReportCatalogueRepository(bucket_id="bucket-a").load()),
        (
            "calculation_observations",
            lambda: CalculationObservationRepository(bucket_id="bucket-a").load_observation("303", 2026, "1T"),
        ),
        ("iva_compensation_history", lambda: IvaCompensationHistoryRepository(bucket_id="bucket-a").list_periods()),
        ("usage_ratios", lambda: load_usage_ratios(bucket_id="bucket-a")),
        ("borrador_100_snapshot", lambda: Borrador100SnapshotRepository(bucket_id="bucket-a").list_snapshots()),
        ("repair_decisions", lambda: RepairRemediationDecisionRepository().list_decisions()),
        ("profile_assets", load_assets),
        ("profile_inventory", load_inventory),
        ("profile_amortizacion", load_amortizacion_ledger),
    ),
)
def test_migrated_runtime_defaults_refuse_route_session_mismatch(
    tmp_path: Path,
    case_name: str,
    operation: Callable[[], object],
) -> None:
    del case_name
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="bucket-a"),
        activate_session(_session("bucket-b")),
        pytest.raises(StorageValidationError, match=r"route does not match|storage runtime is not ready"),
    ):
        operation()


def test_workflow_state_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, "bucket-a"):
        WorkflowStateRepository().save(_workflow_state("bucket-a"))

    with _active_runtime(tmp_path, "bucket-b"):
        assert WorkflowStateRepository().load().declarations == {}
        WorkflowStateRepository().save(_workflow_state("bucket-b"))
        assert "303:bucket-b" in WorkflowStateRepository().load().declarations

    with _active_runtime(tmp_path, "bucket-a"):
        loaded = WorkflowStateRepository().load()

    assert "303:bucket-a" in loaded.declarations
    assert "303:bucket-b" not in loaded.declarations


def test_auth_session_store_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    logical_path = Path("/profile/active/aeat-session")

    with _active_runtime(tmp_path, "bucket-a"):
        _session_store.save(
            logical_path,
            storage_state=_storage_state("bucket-a"),
            metadata={"profile": "bucket-a"},
        )

    with _active_runtime(tmp_path, "bucket-b"):
        assert _session_store.load(logical_path) is None
        _session_store.save(
            logical_path,
            storage_state=_storage_state("bucket-b"),
            metadata={"profile": "bucket-b"},
        )

    with _active_runtime(tmp_path, "bucket-a"):
        loaded = _session_store.load(logical_path)

    assert loaded is not None
    assert loaded.metadata == {"profile": "bucket-a"}
    cookies = loaded.storage_state["cookies"]
    assert isinstance(cookies, list)
    first_cookie = cookies[0]
    assert isinstance(first_cookie, dict)
    assert first_cookie["value"] == "bucket-a"


def test_transaction_repository_default_isolates_bucket_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, "bucket-a"):
        repo = TransactionCatalogueRepository(bucket_id="bucket-a")
        repo.save(TransactionCatalogue.from_transactions((_transaction("bucket-a"),)))

    with _active_runtime(tmp_path, "bucket-b"):
        repo = TransactionCatalogueRepository(bucket_id="bucket-b")
        assert len(repo.load().transactions) == 0
        repo.save(TransactionCatalogue.from_transactions((_transaction("bucket-b"),)))

    with _active_runtime(tmp_path, "bucket-a"):
        loaded = TransactionCatalogueRepository(bucket_id="bucket-a").load()

    assert len(loaded.transactions) == 1
    transaction = next(iter(loaded.transactions.values()))
    assert transaction.raw.description == "runtime migrated repository bucket-a"


def test_attachment_store_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, "bucket-a"):
        digest_a = AttachmentStore().put_bytes(b"bucket-a attachment payload")

    with _active_runtime(tmp_path, "bucket-b"):
        with pytest.raises(AttachmentNotFoundError):
            AttachmentStore().read_bytes(digest_a)
        digest_b = AttachmentStore().put_bytes(b"bucket-b attachment payload")
        assert AttachmentStore().read_bytes(digest_b) == b"bucket-b attachment payload"

    with _active_runtime(tmp_path, "bucket-a"):
        assert AttachmentStore().read_bytes(digest_a) == b"bucket-a attachment payload"
        with pytest.raises(AttachmentNotFoundError):
            AttachmentStore().read_bytes(digest_b)


def test_profile_asset_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, "bucket-a"):
        save_assets((_asset("asset-a"),))

    with _active_runtime(tmp_path, "bucket-b"):
        assert load_assets() == ()
        save_assets((_asset("asset-b"),))

    with _active_runtime(tmp_path, "bucket-a"):
        loaded = load_assets()

    assert tuple(asset.identifier for asset in loaded) == ("asset-a",)


def test_event_and_workflow_run_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    event_a = _bucket_event("bucket-a")
    event_b = _bucket_event("bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        BucketEventHistoryRepository().save(BucketEventHistoryCatalogue(events={event_a.event_id: event_a}))
        WorkflowRunRepository().save(_workflow_run("bucket-a"), runs_dir=tmp_path / "runs-a")

    with _active_runtime(tmp_path, "bucket-b"):
        assert BucketEventHistoryRepository().load().events == {}
        assert WorkflowRunRepository().list() == ()
        BucketEventHistoryRepository().save(BucketEventHistoryCatalogue(events={event_b.event_id: event_b}))
        WorkflowRunRepository().save(_workflow_run("bucket-b"), runs_dir=tmp_path / "runs-b")

    with _active_runtime(tmp_path, "bucket-a"):
        events = BucketEventHistoryRepository().load().events
        runs = WorkflowRunRepository().list()

    assert tuple(events) == (event_a.event_id,)
    assert [run.summary for run in runs] == ["runtime migrated workflow run bucket-a"]


def test_domain_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    draft_a = _modelo_draft("bucket-a")
    draft_b = _modelo_draft("bucket-b")
    amendment_a = _modelo_amendment("bucket-a")
    amendment_b = _modelo_amendment("bucket-b")
    submission_a = _submission("bucket-a")
    submission_b = _submission("bucket-b")
    justificante_a = _justificante(tmp_path, "bucket-a")
    justificante_b = _justificante(tmp_path, "bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((_invoice("bucket-a"),)))
        ModeloDraftRepository(bucket_id="bucket-a").save(draft_a)
        ModeloAmendmentRepository(bucket_id="bucket-a").save(amendment_a)
        SubmissionRepository().save(submission_a)
        JustificanteRepository().save(justificante_a)

    with _active_runtime(tmp_path, "bucket-b"):
        assert InvoiceCatalogueRepository().load().invoices == {}
        assert ModeloDraftRepository(bucket_id="bucket-b").load(draft_a.draft_id) is None
        assert ModeloAmendmentRepository(bucket_id="bucket-b").load(amendment_a.amendment_id) is None
        assert SubmissionRepository().list_submission_ids() == ()
        assert JustificanteRepository().list_csvs() == ()
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((_invoice("bucket-b"),)))
        ModeloDraftRepository(bucket_id="bucket-b").save(draft_b)
        ModeloAmendmentRepository(bucket_id="bucket-b").save(amendment_b)
        SubmissionRepository().save(submission_b)
        JustificanteRepository().save(justificante_b)

    with _active_runtime(tmp_path, "bucket-a"):
        invoices = InvoiceCatalogueRepository().load().invoices
        loaded_draft_a = ModeloDraftRepository(bucket_id="bucket-a").load(draft_a.draft_id)
        loaded_draft_b = ModeloDraftRepository(bucket_id="bucket-a").load(draft_b.draft_id)
        loaded_amendment_a = ModeloAmendmentRepository(bucket_id="bucket-a").load(amendment_a.amendment_id)
        loaded_amendment_b = ModeloAmendmentRepository(bucket_id="bucket-a").load(amendment_b.amendment_id)
        submissions = SubmissionRepository().list_submission_ids()
        csvs = JustificanteRepository().list_csvs()

    assert tuple(invoice.invoice_number for invoice in invoices.values()) == ("INV-BUCKET-A",)
    assert loaded_draft_a == draft_a
    assert loaded_draft_b is None
    assert loaded_amendment_a == amendment_a
    assert loaded_amendment_b is None
    assert submissions == (submission_a.submission_id,)
    assert csvs == (justificante_a.csv,)


def test_modelo_catalogue_defaults_isolate_bucket_writes(tmp_path: Path) -> None:
    work_a = _work_unit("bucket-a", "bucket-a")
    work_b = _work_unit("bucket-b", "bucket-b")
    calc_a = _calculation_catalogue("bucket-a")
    calc_b = _calculation_catalogue("bucket-b")
    filing_a = _filing_record_catalogue("bucket-a", "bucket-a")
    filing_b = _filing_record_catalogue("bucket-b", "bucket-b")
    verification_a = _verification_catalogue("bucket-a")
    verification_b = _verification_catalogue("bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        WorkUnitCatalogueRepository(bucket_id="bucket-a").save(
            WorkUnitCatalogue(work_units={work_a.work_unit_id: work_a})
        )
        CalculationRevisionCatalogueRepository(bucket_id="bucket-a").save(calc_a)
        ModeloRecordCatalogueRepository(bucket_id="bucket-a").save(filing_a)
        VerificationReportCatalogueRepository(bucket_id="bucket-a").save(verification_a)

    with _active_runtime(tmp_path, "bucket-b"):
        assert WorkUnitCatalogueRepository(bucket_id="bucket-b").load().work_units == {}
        assert CalculationRevisionCatalogueRepository(bucket_id="bucket-b").load().revisions == {}
        assert ModeloRecordCatalogueRepository(bucket_id="bucket-b").load().records == {}
        assert VerificationReportCatalogueRepository(bucket_id="bucket-b").load().reports == {}
        WorkUnitCatalogueRepository(bucket_id="bucket-b").save(
            WorkUnitCatalogue(work_units={work_b.work_unit_id: work_b})
        )
        CalculationRevisionCatalogueRepository(bucket_id="bucket-b").save(calc_b)
        ModeloRecordCatalogueRepository(bucket_id="bucket-b").save(filing_b)
        VerificationReportCatalogueRepository(bucket_id="bucket-b").save(verification_b)

    with _active_runtime(tmp_path, "bucket-a"):
        work_loaded = WorkUnitCatalogueRepository(bucket_id="bucket-a").load().work_units
        calc_loaded = CalculationRevisionCatalogueRepository(bucket_id="bucket-a").load().revisions
        filing_loaded = ModeloRecordCatalogueRepository(bucket_id="bucket-a").load().records
        verification_loaded = VerificationReportCatalogueRepository(bucket_id="bucket-a").load().reports

    assert tuple(work_loaded) == (work_a.work_unit_id,)
    assert tuple(calc_loaded) == tuple(calc_a.revisions)
    assert tuple(filing_loaded) == tuple(filing_a.records)
    assert tuple(verification_loaded) == tuple(verification_a.reports)


def test_application_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    observation_a = RegistryModeloObservation(modelo="303", filing_year=2026, period="1T")
    observation_b = RegistryModeloObservation(modelo="303", filing_year=2026, period="2T")
    history_a = _history("bucket-a")
    history_b = _history("bucket-b")
    usage_a = _usage_profile(SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ, "0.21")
    usage_b = _usage_profile(SpendingCategory.TELEFONIA_MOVIL, "0.60")

    with _active_runtime(tmp_path, "bucket-a"):
        ModeloHistoryRepository(bucket_id="bucket-a").save(history_a)
        CalculationObservationRepository(bucket_id="bucket-a").save_observation(
            observation_a,
            source_kind="operator_manual",
        )
        IvaCompensationHistoryRepository(bucket_id="bucket-a").save_period(_iva_state("bucket-a"))
        save_usage_ratios(usage_a, bucket_id="bucket-a")

    with _active_runtime(tmp_path, "bucket-b"):
        assert ModeloHistoryRepository(bucket_id="bucket-b").list_modelos() == ()
        assert CalculationObservationRepository(bucket_id="bucket-b").load_observation("303", 2026, "1T") is None
        assert IvaCompensationHistoryRepository(bucket_id="bucket-b").list_periods() == ()
        assert load_usage_ratios(bucket_id="bucket-b") == UsageRatioProfile()
        ModeloHistoryRepository(bucket_id="bucket-b").save(history_b)
        CalculationObservationRepository(bucket_id="bucket-b").save_observation(
            observation_b,
            source_kind="operator_manual",
        )
        IvaCompensationHistoryRepository(bucket_id="bucket-b").save_period(_iva_state("bucket-b"))
        save_usage_ratios(usage_b, bucket_id="bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        modelo_ids = ModeloHistoryRepository(bucket_id="bucket-a").list_modelos()
        observed = CalculationObservationRepository(bucket_id="bucket-a").load_observation("303", 2026, "1T")
        iva_periods = IvaCompensationHistoryRepository(bucket_id="bucket-a").list_periods()
        usage = load_usage_ratios(bucket_id="bucket-a")

    assert modelo_ids == ("303",)
    assert observed is not None
    assert observed.observation == observation_a
    assert tuple(state.period for state in iva_periods) == ("1TA",)
    assert usage == usage_a


def test_s85_runtime_default_surfaces_isolate_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, "bucket-a"):
        Borrador100SnapshotRepository(bucket_id="bucket-a").save(_borrador_snapshot("bucket-a", "bucket-a"))
        RepairRemediationDecisionRepository().save_decision(_repair_decision("bucket-a"))
        _save_auth_diagnostic("bucket-a")
        _save_diagnostic_probe_row("bucket-a")

    with _active_runtime(tmp_path, "bucket-b"):
        assert Borrador100SnapshotRepository(bucket_id="bucket-b").list_snapshots() == ()
        assert RepairRemediationDecisionRepository().list_decisions() == ()
        assert list_auth_diagnostics().row_count == 0
        assert preview_quarantine_unreadable_secure_objects().namespaces == ()
        Borrador100SnapshotRepository(bucket_id="bucket-b").save(_borrador_snapshot("bucket-b", "bucket-b"))
        RepairRemediationDecisionRepository().save_decision(_repair_decision("bucket-b"))
        _save_auth_diagnostic("bucket-b")
        _save_diagnostic_probe_row("bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        snapshots = Borrador100SnapshotRepository(bucket_id="bucket-a").list_snapshots()
        decisions = RepairRemediationDecisionRepository().list_decisions()
        auth_report = list_auth_diagnostics()
        diagnostic_report = preview_quarantine_unreadable_secure_objects()

    assert tuple(snapshot.snapshot_id for snapshot in snapshots) == ("snapshot-bucket-a",)
    assert tuple(decision.reason for decision in decisions) == ("runtime migrated repair decision bucket-a",)
    assert auth_report.row_count == 1
    assert tuple(row.diagnostic_id for row in auth_report.rows) == ("diagnostic-bucket-a",)
    assert "aeat.test.runtime.migrated.diagnostics" in tuple(item.namespace for item in diagnostic_report.namespaces)


def test_adapter_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    profile = "operator-google"
    google_a = _google_records("bucket-a")
    google_b = _google_records("bucket-b")
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    usage = UsageRecorder(root_dir=tmp_path / "llm-usage")
    request = _llm_request()
    artefact_a, body_a = _sede_artefact("bucket-a")
    artefact_b, body_b = _sede_artefact("bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        google_session_store.save_client(profile, google_a[0])
        google_session_store.save_token(profile, google_a[1])
        google_session_store.save_metadata(profile, google_a[2])
        google_session_store.save_drive_config(profile, google_a[3])
        cache.write(request, _llm_response("bucket-a"))
        usage.record(_usage_record("bucket-a"))
        save_inventory((_inventory_ledger("bucket-a"),))
        save_amortizacion_ledger(_amortizacion_ledger("bucket-a"))
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        stored_a = store.persist_artefact(("303", 2026, "1T", "202610013522456T"), artefact_a, body_a)

    with _active_runtime(tmp_path, "bucket-b"):
        assert google_session_store.load_client(profile) is None
        assert cache.read(request, LLMProvider.OPENAI, "gpt-test") is None
        assert usage.load_records() == ()
        assert load_inventory() == ()
        assert load_amortizacion_ledger() == AmortizacionLedger()
        with pytest.raises(ExpedienteNotFoundError):
            FiledDeclaracionObservationStore(tmp_path / "sede-cache").load_artefact(stored_a.storage_ref or "")
        google_session_store.save_client(profile, google_b[0])
        google_session_store.save_token(profile, google_b[1])
        google_session_store.save_metadata(profile, google_b[2])
        google_session_store.save_drive_config(profile, google_b[3])
        cache.write(request, _llm_response("bucket-b"))
        usage.record(_usage_record("bucket-b"))
        save_inventory((_inventory_ledger("bucket-b"),))
        save_amortizacion_ledger(_amortizacion_ledger("bucket-b"))
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        store.persist_artefact(("303", 2026, "2T", "202610013522457T"), artefact_b, body_b)

    with _active_runtime(tmp_path, "bucket-a"):
        cached = cache.read(request, LLMProvider.OPENAI, "gpt-test")
        usage_records = usage.load_records()
        inventory = load_inventory()
        amortizacion = load_amortizacion_ledger()
        loaded_body = FiledDeclaracionObservationStore(tmp_path / "sede-cache").load_artefact(
            stored_a.storage_ref or ""
        )
        assert google_session_store.load_client(profile) == google_a[0]
        assert google_session_store.load_token(profile) == google_a[1]
        assert google_session_store.load_metadata(profile) == google_a[2]
        assert google_session_store.load_drive_config(profile) == google_a[3]

    assert cached is not None
    assert cached.text == "runtime migrated response bucket-a"
    assert tuple(record.request_id for record in usage_records) == ("request-bucket-a",)
    assert tuple(ledger.actividad_id for ledger in inventory) == ("retail-bucket-a",)
    assert amortizacion == _amortizacion_ledger("bucket-a")
    assert loaded_body == body_a
