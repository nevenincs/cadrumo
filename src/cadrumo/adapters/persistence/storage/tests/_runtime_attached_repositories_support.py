"""Shared support for split adapter tests."""

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

from .....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from .....adapters.persistence.profile.filing_amendments import ModeloAmendmentRepository
from .....adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from .....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from .....adapters.persistence.profile.justificante import JustificanteRepository
from .....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from .....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from .....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from .....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from .....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from .....application.auth.apoderado_service import ApoderadoService
from .....application.auth.diagnostics import list_auth_diagnostics
from .....application.calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    IvaWalletDecisionRepository,
)
from .....application.diagnostics import (
    preview_quarantine_unreadable_secure_objects,
    secure_object_unreadable_total,
)
from .....application.filing import ModeloHistory, ModeloHistoryEntry, ModeloHistoryRepository
from .....application.live.borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    derive_borrador_100_snapshot_id,
)
from .....application.live.snapshot_base import SnapshotLifecycleState
from .....application.modelo._review_package_recipient_registry import RecipientFingerprintRegistryRepository
from .....application.repair_integrity import (
    RepairRemediationDecision,
    RepairRemediationDecisionRepository,
    repair_remediation_decision_id,
)
from .....application.workflow.persistence import WorkflowRunRepository, WorkflowStateRepository
from .....application.workflow.run_models import WorkflowResult, WorkflowStage, WorkflowStep
from .....application.workflow.state_models import DeclaracionPointer, WorkflowState
from .....core import CasillaId, IvaCompensationStateProvenance, validated_casilla_id
from .....core import Period as _Period
from .....core.config import override_settings
from .....domain.attachments import AttachmentNotFoundError
from .....domain.buckets import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from .....domain.calculations.registry import (
    CasillaObservation,
    RegistryModeloObservation,
    RegistrySnapshotRef,
)
from .....domain.categories import SpendingCategory
from .....domain.contribuyente.assets import AmortizacionEntry, AmortizacionLedger, AssetClass, AssetRecord
from .....domain.contribuyente.inventory import InventoryLedger, ValuationMethod
from .....domain.filing import (
    AmendmentKind,
    CasillaChange,
    ModeloComplementaria,
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
    make_amendment_id,
    registry_schema_version,
)
from .....domain.identifiers import ModeloIdentifier
from .....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus, derive_invoice_id
from .....domain.iva import InvoiceKind
from .....domain.iva_compensation import IvaCompensationPeriodState, IvaCompensationReconciliationDecision
from .....domain.justificante import Justificante
from .....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloCode,
    ModeloRecord,
    ModeloRecordCatalogue,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    WorkUnit,
    WorkUnitCatalogue,
    WorkUnitState,
    derive_calculation_revision_id,
    derive_filing_record_id,
    derive_verification_report_id,
    derive_work_unit_id,
)
from .....domain.submission import (
    ModeloDraftStatus,
    ModeloPresentado,
    SubmissionAttempt,
    SubmissionStatus,
    make_submission_id,
)
from .....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from .....domain.usage_ratios import UsageRatioProfile
from .....llm import LLMProvider, LLMRequest, LLMResponse, UsageRecord
from .....tests.aeat_literal_fixtures import (
    AEAT_HOST_SUFFIX_EXPECTED,
    AUTH_DIAGNOSTIC_PATH_FIXTURE,
    BORRADOR_STORAGE_PATH_FIXTURE,
    FILED_ARTEFACT_PATH_FIXTURE,
    JUSTIFICANTE_VERIFY_PATH_FIXTURE,
    aeat_url,
)
from .....tests.master_key import EphemeralMasterKeyProvider
from ....outbound.aeat.auth import session_store as _session_store
from ....outbound.aeat.sede import ExpedienteNotFoundError, FiledDeclaracionArtefact, FiledDeclaracionObservationStore
from ....outbound.google import (
    REQUIRED_SCOPES,
    DriveConfig,
    OAuthClient,
    OAuthMetadata,
    OAuthToken,
)
from ....outbound.google import session_store as google_session_store
from ....outbound.llm import EvidenceConsentLedger, LLMCache, LLMRunTelemetryRecorder, UsageRecorder
from ...profile.assets import load_amortizacion_ledger, load_assets, save_amortizacion_ledger, save_assets
from ...profile.inventory import load_inventory, save_inventory
from ...profile.recipient_replay_guard import RecipientReplayGuardRepository
from ...profile.submission import SubmissionRepository
from ...profile.usage_ratios import load_usage_ratios, save_usage_ratios
from .. import CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE, AttachmentStore, SensitivityClass, StorageValidationError
from .._namespace_registry import LLM_USAGE_NAMESPACE
from ..master_key import BucketSession, activate_session
from ..runtime_repository import secure_object_repository_for_active_bucket
from ..sql.engine import dispose_engine
from .registered_bucket import ensure_registered_bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

__all__ = [
    "LLM_USAGE_NAMESPACE",
    "_BUCKET_A_ATTACHMENT_PAYLOAD",
    "_BUCKET_A_ID",
    "_BUCKET_B_ATTACHMENT_PAYLOAD",
    "_BUCKET_B_ID",
    "_WALLET_SUBJECT_ID",
    "AmortizacionLedger",
    "ApoderadoService",
    "AttachmentNotFoundError",
    "AttachmentStore",
    "Borrador100SnapshotRepository",
    "BucketEventHistoryCatalogue",
    "BucketEventHistoryRepository",
    "CalculationObservationRepository",
    "CalculationRevisionCatalogueRepository",
    "Callable",
    "EvidenceConsentLedger",
    "ExpedienteNotFoundError",
    "FiledDeclaracionObservationStore",
    "InvoiceCatalogue",
    "InvoiceCatalogueRepository",
    "IvaCompensationHistoryRepository",
    "IvaWalletDecisionRepository",
    "JustificanteRepository",
    "LLMCache",
    "LLMProvider",
    "LLMRunTelemetryRecorder",
    "ModeloAmendmentRepository",
    "ModeloDraftRepository",
    "ModeloHistoryRepository",
    "ModeloRecordCatalogueRepository",
    "Path",
    "RecipientFingerprintRegistryRepository",
    "RecipientReplayGuardRepository",
    "RegistryModeloObservation",
    "RepairRemediationDecisionRepository",
    "SpendingCategory",
    "StorageValidationError",
    "SubmissionRepository",
    "TransactionCatalogue",
    "TransactionCatalogueRepository",
    "UsageRatioProfile",
    "UsageRecorder",
    "VerificationReportCatalogueRepository",
    "WorkUnitCatalogue",
    "WorkUnitCatalogueRepository",
    "WorkflowRunRepository",
    "WorkflowStateRepository",
    "_session_store",
    "activate_session",
    "google_session_store",
    "list_auth_diagnostics",
    "load_amortizacion_ledger",
    "load_assets",
    "load_inventory",
    "load_usage_ratios",
    "preview_quarantine_unreadable_secure_objects",
    "save_amortizacion_ledger",
    "save_assets",
    "save_inventory",
    "save_usage_ratios",
    "secure_object_unreadable_total",
]

_KEK = b"k" * 32

_DEK = b"d" * 32

_MASTER_KEY = b"m" * 32

_GOOGLE_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"
_BUCKET_A_ID = "0f60a84e-d1ac-4c0e-9e91-c094a33df00a"
_BUCKET_B_ID = "9b22bbfd-d870-4207-a1a7-30a2b4b3600b"
_WALLET_SUBJECT_ID = "ES12345678Z"
_BUCKET_A_ATTACHMENT_PAYLOAD = f"{_BUCKET_A_ID} attachment payload".encode("ascii")
_BUCKET_B_ATTACHMENT_PAYLOAD = f"{_BUCKET_B_ID} attachment payload".encode("ascii")


_CALCULATION_INPUT_CASILLA: CasillaId = validated_casilla_id("base")
_CALCULATION_OUTPUT_CASILLA: CasillaId = validated_casilla_id("casilla-01")


@contextmanager
def _active_runtime(tmp_path: Path, bucket_id: str) -> Iterator[None]:
    # The repositories below open a real engine inside the bucket root, and the
    # engine refuses to create that root: a bucket exists only once its profile
    # capsule is published. Registering here is that publication, so every span
    # runs against a bucket directory an operator's profile could actually own.
    ensure_registered_bucket(tmp_path, bucket_id)
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=bucket_id) as settings:
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
    period = _Period.from_year_and_code(2026, "1T")
    return WorkflowState(
        declarations={
            f"303:{period.filing_year}:{period.registry_token}": DeclaracionPointer(
                modelo="303",
                period=period,
                draft_id=(label.replace("-", "")[-1:] or "d") * 64,
                status="BORRADOR",
                updated_at=now,
            ),
        },
        updated_at=now,
    )


def _transaction(label: str) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=f"tx-{label}",
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description=f"runtime attached repository {label}",
        provenance=RawProvenance(
            source_path=Path(f"/bank/{label}.csv"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime.now(UTC).replace(microsecond=0),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": f"runtime attached repository {label}"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )


def _asset(identifier: str) -> AssetRecord:
    return AssetRecord(
        identifier=identifier,
        description=f"runtime attached asset {identifier}",
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
                "domain": f".{AEAT_HOST_SUFFIX_EXPECTED}",
                "path": "/",
            },
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
        summary_locale_key="application.workflow.steps.profile_loaded",
    )
    return WorkflowResult(
        run_id=_hex(f"workflow-run-{label}")[:16],
        started_at=when,
        ended_at=when,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        steps=(step,),
        summary_locale_key="application.workflow.results.completed",
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
        description=f"runtime attached invoice line {label}",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    invoice_id = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number=f"INV-{label.upper()}",
        issued_at=date(2026, 4, 1),
        counterparty_tax_id="B12345674",
        currency="EUR",
        grand_total=Decimal("121.00"),
    )
    return Invoice(
        invoice_id=invoice_id,
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
    period = _Period.from_year_and_code(2026, "1T")
    profile_tax_id = "12345678Z"
    snapshot_ref = RegistrySnapshotRef(
        modelo="303",
        revision_id="2026-y-siguientes",
        modelo_year=2026,
        period="1T",
    )
    values = (
        ModeloValue(
            casilla_id=validated_casilla_id(f"iva.devengado.{label}"),
            value=Decimal("100.00"),
            kind=ModeloValueKind.LITERAL,
            source="runtime attached repository test",
        ),
    )
    draft_id = compute_modelo_draft_id(
        modelo="303",
        period=period,
        profile_tax_id=profile_tax_id,
        snapshot_ref=snapshot_ref,
        values=values,
    )
    return ModeloDraft(
        draft_id=draft_id,
        modelo="303",
        period=period,
        profile_tax_id=profile_tax_id,
        subject_tax_id="12345678Z",
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.BORRADOR,
        values=values,
        binding_values=(),
        findings=(),
        created_at=now,
        updated_at=now,
        schema_version=registry_schema_version(modelo="303", revision_id="2026-y-siguientes"),
    )


def _modelo_amendment(label: str) -> ModeloComplementaria:
    draft = _modelo_draft(label)
    delta = (
        CasillaChange(
            casilla_id=validated_casilla_id("iva.devengado"),
            old_value=Decimal("100.00"),
            new_value=Decimal("121.00"),
            reason=f"runtime attached amendment {label}",
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
        original_period=draft.period,
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
        period=_Period.from_year_and_code(2026, "1T"),
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
        period=_Period.from_year_and_code(2026, "1T"),
        ejercicio="2026",
        presentation_id=None,
        presented_at=datetime(2026, 4, 10, 11, 23, 45, tzinfo=UTC),
        tax_id="00000000T",
        total_a_ingresar=Decimal("10.00"),
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(aeat_url("sede", JUSTIFICANTE_VERIFY_PATH_FIXTURE)),
        source_pdf_path=pdf,
        source_pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
        parsed_at=datetime(2026, 4, 12, tzinfo=UTC),
    )


def _work_unit(bucket_id: str, label: str) -> WorkUnit:
    now = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    modelo = ModeloCode("303")
    period = _Period.from_year_and_code(2026, "1T")
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


def _calculation_revision_id_for(label: str) -> str:
    """Return the same content-addressed revision id `_calculation_catalogue` persists.

    `_verification_catalogue` must reference this exact id: the verification-report
    save path resolves `calculation_revision_id` against the bucket's real
    calculation-revision catalogue, so an unrelated invented id is refused.
    """
    return derive_calculation_revision_id(
        work_unit_id=_hex(f"work-unit-{label}"),
        input_values_by_casilla_id={_CALCULATION_INPUT_CASILLA: "100.00"},
        binding_overrides={},
        casilla_values={_CALCULATION_OUTPUT_CASILLA: Decimal("100.00")},
        source_transaction_ids=(),
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _calculation_catalogue(label: str) -> CalculationRevisionCatalogue:
    work_unit_id = _hex(f"work-unit-{label}")
    input_values_by_casilla_id = {_CALCULATION_INPUT_CASILLA: "100.00"}
    values = {_CALCULATION_OUTPUT_CASILLA: Decimal("100.00")}
    revision_id = _calculation_revision_id_for(label)
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides={},
        source_transaction_ids=(),
        casilla_values=values,
        observations=(
            CasillaObservation(
                casilla_id=_CALCULATION_OUTPUT_CASILLA,
                value=Decimal("100.00"),
                legal_refs=("ley-58-2003:art-93",),
                source_refs=("runtime-attached-repository-test",),
            ),
        ),
        created_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevisionCatalogue(revisions={revision_id: revision})


def _filing_record_catalogue(bucket_id: str, label: str) -> ModeloRecordCatalogue:
    filed_at = datetime(2026, 5, 26, 11, 0, tzinfo=UTC)
    work_unit_id = _hex(f"filing-work-unit-{label}")
    revision_id = _hex(f"filing-revision-{label}")
    record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat.cli.modelo.file",
    )
    record = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=_Period.from_year_and_code(2026, "1T"),
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
        notes=f"runtime attached filing record {label}",
        aeat_accepted=True,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id=f"justificante-{label}",
            imported_at=filed_at,
        ),
    )
    return ModeloRecordCatalogue(records={record_id: record})


def _verification_catalogue(label: str) -> VerificationReportCatalogue:
    run_at = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
    revision_id = _calculation_revision_id_for(label)
    report_id = derive_verification_report_id(
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.COMPLETE,
        findings=(),
        verified_by="aeat.cli.modelo.verify",
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.COMPLETE,
        findings=(),
        resolved_casilla_ids=(validated_casilla_id("iva.devengado"),),
        missing_required_casilla_ids=(),
        run_at=run_at,
        verified_by="aeat.cli.modelo.verify",
        granted_verificado_completo=True,
    )
    return VerificationReportCatalogue(reports={report_id: report})


def _history(label: str) -> ModeloHistory:
    submitted_at = datetime(2026, 5, 26, 13, 0, tzinfo=UTC)
    period = "1T" if label.endswith("a") else "2T"
    return ModeloHistory(
        modelo=ModeloIdentifier("303"),
        entries=(
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
                period=_Period.from_year_and_code(2026, period),
                submitted_at=submitted_at,
                status="presentada",
            ),
        ),
    )


def _iva_state(label: str) -> IvaCompensationPeriodState:
    period = "1T" if label.endswith("a") else "2T"
    return IvaCompensationPeriodState(
        provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
        taxpayer_nif="00000000T",
        filing_year=2026,
        period=_Period.from_year_and_code(2026, period),
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
        closing_authority_record=None,
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
            },
        ),
        OAuthToken.model_validate({"refresh_token": f"1//refresh-token-{label}", "token_uri": _GOOGLE_OAUTH_ENDPOINT}),
        OAuthMetadata(
            account_email=f"{label}@example.com",
            granted_scopes=REQUIRED_SCOPES,
            issued_at=issued_at,
            last_refresh_at=issued_at,
        ),
        DriveConfig(root_folder_id=f"drive-folder-{label}"),
    )


def _llm_request() -> LLMRequest:
    return LLMRequest(prompt="Summarise a runtime storage routing", cache_key="runtime-storage")


def _llm_response(label: str) -> LLMResponse:
    return LLMResponse(
        text=f"runtime attached response {label}",
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
    body = f"runtime attached sede artefact {label}".encode()
    return (
        FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=TypeAdapter(AnyHttpUrl).validate_python(aeat_url("sede", FILED_ARTEFACT_PATH_FIXTURE)),
            content_type="application/pdf",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        ),
        body,
    )


def _borrador_snapshot(bucket_id: str) -> Borrador100Snapshot:
    filing_year = 2026
    period = _Period.from_year_and_code(2026, "0A")
    captured_at = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    source_url = aeat_url("sede", BORRADOR_STORAGE_PATH_FIXTURE)
    binding_values = {"casilla-001": Decimal("1.00")}
    snapshot_id = derive_borrador_100_snapshot_id(
        filing_year=filing_year,
        period=period,
        captured_at=captured_at,
        source_url=source_url,
        binding_values=binding_values,
    )
    return Borrador100Snapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        modelo="100",
        filing_year=filing_year,
        period=period,
        captured_at=captured_at,
        source_url=source_url,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=binding_values,
    )


def _repair_decision(label: str) -> RepairRemediationDecision:
    decided_at = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    target_namespace = "cadrumo-test.runtime.attached"
    reason = f"runtime attached repair decision {label}"
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


def _iva_wallet_decision(label: str, *, target_period: str = "2T") -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=_WALLET_SUBJECT_ID,
        target_year=2026,
        target_period=_Period.from_year_and_code(2026, target_period),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("1200.00"),
        wallet_amount=Decimal("1200.00"),
        local_recurrence_amount=Decimal("1200.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_validated",
        wallet_captured_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        decided_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
    )


def _save_auth_diagnostic(label: str) -> None:
    payload = {
        "diagnostic_id": f"diagnostic-{label}",
        "reason": "runtime attached auth diagnostic",
        "url": aeat_url("sede", AUTH_DIAGNOSTIC_PATH_FIXTURE),
        "captured_at": datetime(2026, 5, 26, 9, 0, tzinfo=UTC).isoformat(),
        "auth_attempt": {"auth_mode": "clave", "headless": True},
    }
    secure_object_repository_for_active_bucket().save(
        namespace=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace,
        object_key=payload["diagnostic_id"],
        classification=SensitivityClass.SESSION,
        schema_version=1,
        written_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        payload=json.dumps(payload, sort_keys=True).encode(),
    )


def _save_diagnostic_probe_row(label: str) -> None:
    secure_object_repository_for_active_bucket().save(
        namespace=LLM_USAGE_NAMESPACE.namespace,
        object_key=f"diagnostic-probe-{label}",
        classification=LLM_USAGE_NAMESPACE.sensitivity,
        schema_version=LLM_USAGE_NAMESPACE.schema_version,
        written_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        payload=f"diagnostic-probe-{label}".encode(),
    )
