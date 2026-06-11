"""Shared support for split adapter tests."""


from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from .....application.filing import ModeloHistory, ModeloHistoryEntry
from .....application.live._borrador_100 import Borrador100Snapshot
from .....application.live._snapshot_base import SnapshotLifecycleState
from .....application.repair_integrity import (
    RepairRemediationDecision,
    repair_remediation_decision_id,
)
from .....application.workflow import DeclaracionPointer, WorkflowResult, WorkflowStage, WorkflowState, WorkflowStep
from .....core import Period as _Period
from .....core.config import override_settings
from .....core.external_constants import CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE
from .....domain._identifiers import ModeloIdentifier
from .....domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from .....domain.calculations.registry import RegistrySnapshotRef
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
    make_amendment_id,
)
from .....domain.invoices import (
    Invoice,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
    derive_invoice_id,
)
from .....domain.iva import InvoiceKind
from .....domain.iva_compensation._carry_forward import IvaCompensationPeriodState
from .....domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from .....domain.justificante import Justificante
from .....domain.modelos import ModeloCode
from .....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos._filing_record import (
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from .....domain.modelos._verification_report import (
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from .....domain.modelos._work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
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
    TransactionDirection,
)
from .....domain.usage_ratios import UsageRatioProfile
from .....tests.aeat_literal_fixtures import (
    AEAT_HOST_SUFFIX_EXPECTED,
    AUTH_DIAGNOSTIC_PATH_FIXTURE,
    BORRADOR_STORAGE_PATH_FIXTURE,
    FILED_ARTEFACT_PATH_FIXTURE,
    JUSTIFICANTE_VERIFY_PATH_FIXTURE,
    aeat_url,
)
from ....outbound.aeat.sede._schema import FiledDeclaracionArtefact
from ....outbound.google._records import REQUIRED_SCOPES, DriveConfig, OAuthClient, OAuthMetadata, OAuthToken
from ....outbound.llm._models import LLMProvider, LLMRequest, LLMResponse, UsageRecord
from .. import EphemeralMasterKeyProvider, SensitivityClass
from .._namespace_registry import LLM_USAGE_NAMESPACE
from ..master_key._bucket_session import BucketSession
from ..runtime_repository import secure_object_repository_for_active_bucket
from ..sql.engine import dispose_engine

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

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
    period = _Period.from_year_and_code(2026, "1T")
    return WorkflowState(
        declarations={
            f"303:{period.filing_year}:{period.registry_token}": DeclaracionPointer(
                modelo="303",
                period=period,
                draft_id="d" * 64,
                status="BORRADOR",
                updated_at=now,
            ),
        },
        updated_at=now,
    )


def _transaction(label: str) -> Transaction:
    raw = RawTransaction(
        transaction_id=f"tx-{label}",
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=Decimal("121.00"),
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
    return ModeloDraft(
        draft_id=_hex(f"draft-{label}"),
        modelo="303",
        period=_Period.from_year_and_code(2026, "1T"),
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
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(aeat_url("sede", JUSTIFICANTE_VERIFY_PATH_FIXTURE)),
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
        modelo=ModeloIdentifier("303"),
        entries=(
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
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
            source_url=TypeAdapter(AnyHttpUrl).validate_python(aeat_url("sede", FILED_ARTEFACT_PATH_FIXTURE)),
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
        source_url=aeat_url("sede", BORRADOR_STORAGE_PATH_FIXTURE),
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


def _iva_wallet_decision(label: str, *, target_period: str = "2T") -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=f"ES{label.upper()}",
        target_year=2026,
        target_period=target_period,
        selected_authority="aeat_wallet",
        selected_amount=Decimal("1200.00"),
        wallet_amount=Decimal("1200.00"),
        local_recurrence_amount=Decimal("1200.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason=f"Runtime migrated IVA wallet decision {label}.",
        wallet_captured_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        decided_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
    )


def _save_auth_diagnostic(label: str) -> None:
    payload = {
        "diagnostic_id": f"diagnostic-{label}",
        "reason": "runtime migrated auth diagnostic",
        "url": aeat_url("sede", AUTH_DIAGNOSTIC_PATH_FIXTURE),
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
        namespace=LLM_USAGE_NAMESPACE.namespace,
        object_key=f"diagnostic-probe-{label}",
        classification=LLM_USAGE_NAMESPACE.sensitivity,
        schema_version=LLM_USAGE_NAMESPACE.schema_version,
        written_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        payload=f"diagnostic-probe-{label}".encode(),
    )
