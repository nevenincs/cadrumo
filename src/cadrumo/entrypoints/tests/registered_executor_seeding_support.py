"""Seed the real local state used by registered-executor scenarios."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.notification_documents import notification_document_repository
from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...adapters.persistence.profile.tests.cross_period_seeding import (
    SEEDED_SOURCE_TAX_ID,
    seed_clean_cross_period_sources,
)
from ...adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from ...application.ledger.lifecycle_contracts import LedgerLifecycleOperationId
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.live.expedientes import ExpedientesCapture, ExpedientesService
from ...application.live.expedientes_ports import ExpedientesDeclaration
from ...application.live.notification_documents import NotificationDocumentRecord
from ...application.live.notification_ports import NotificationsSnapshot, NotificationType, RemoteNotification
from ...application.live.notifications import NotificationsService
from ...application.modelo.calculation_actions import calculate_modelo_revision
from ...application.modelo.edit_apply_contracts import ModeloEditApplySubmissionV1
from ...application.modelo.external_import_actions import import_external_filing_evidence
from ...application.modelo.operation_definitions import resolve_active_workflow_profile
from ...application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ...application.operator_actions.models import ConditionEvidence, PreconditionVerdict
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.section_rows import add_profile_repeatable_section_row
from ...application.workflow.abort import WorkflowAbortReason
from ...application.workflow.run_models import WorkflowObligationFacts, WorkflowResult, WorkflowStage, WorkflowStep
from ...core.config import load_settings
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ...domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from ...domain.deadlines.models import ObligationStatus
from ...domain.invoices.enums import IvaRate, PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.iva.classification import InvoiceKind
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.filing_record import ExternalEvidenceKind
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from ...domain.notifications.sancion import SancionLiquidacion
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...tests.aeat_literal_fixtures import aeat_url
from ..adapter_composition import (
    build_calculation_action_ports,
    build_expedientes_ports,
    build_prorrata_register_repository,
    build_verification_repository_bundle,
)
from ..justificante_composition import build_justificante_capture_service
from ..ledger_action_composition import compose_ledger_action_ports
from ..live_state_composition import compose_notifications_ports
from ..operation_composition import build_production_operation_registry
from . import modelo_operation_test_support
from .ledger_lifecycle_operation_test_support import (
    LedgerLifecycleOperationConformanceCase,
    prepare_ledger_lifecycle_operation_conformance_case,
)
from .profile_persistence.verification_repository_support import build_test_certificate_secret_backend_factory
from .prorrata_operation_test_support import (
    ProrrataOperationConformanceCase,
    prepare_prorrata_operation_conformance_case,
)
from .registered_executor_scenario_constants import _OPERATOR_SCOPE_PORTS


def _seeded_modelo_filing_record(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> tuple[str, str]:
    """File one real revision and return its filing-record and casilla ids.

    Amendment corrects something already FILED, so its fixture cannot stop at a
    verified revision: it needs the filing record that amendment is addressed
    to. Reached through the same filing authority the `file` operation uses, so
    the record amendment corrects is one the product actually produces.

    The casilla is taken from the revision's own declared inputs rather than
    named, for the reason the edit fixture gives: the M130 casilla mapping is
    revision-scoped, and a literal here would be silently wrong the moment the
    governing revision changes.
    """
    unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
    revision = resolved_revision(
        modelo=modelo_operation_test_support.MODELO,
        filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
        period=modelo_operation_test_support.MODELO_PERIOD,
    )
    casilla_id = sorted(casilla.id for casilla in revision.casillas)[0]
    evidence_reference_id = f"CSV{modelo_operation_test_support.MODELO}{modelo_operation_test_support.MODELO_FILING_YEAR}{modelo_operation_test_support.MODELO_PERIOD}".upper()
    # The unit is created at the live clock, so the evidence cannot be stamped
    # with the profile's fixed seeding clock: the catalogue refuses a work unit
    # whose updated_at precedes its created_at, and rightly so.
    evidence_clock = now()

    # Amendment refuses a baseline with no external evidence
    # (`AmendmentEvidenceMissingError`), and that refusal is correct: an
    # amendment corrects a return the authority already holds, so the baseline
    # has to be one AEAT evidenced rather than one this process filed locally.
    # The record therefore comes through the external-import door, exactly as
    # the cross-period seeder produces its own sources.
    persist_justificante_metadata(
        evidence_reference_id,
        modelo=modelo_operation_test_support.MODELO,
        filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
        period=modelo_operation_test_support.MODELO_PERIOD,
        captured_at=evidence_clock,
        tax_id=SEEDED_SOURCE_TAX_ID,
    )
    record = import_external_filing_evidence(
        work_unit_id=unit.work_unit_id,
        casilla_values={casilla_id: Decimal("100")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=evidence_reference_id,
        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        filing_repository=ModeloRecordCatalogueRepository(),
        bucket_event_repository=BucketEventHistoryRepository(),
        observation_repository=CalculationObservationRepository(),
        expected_tax_id=SEEDED_SOURCE_TAX_ID,
        clock=evidence_clock,
    ).filing_record
    return str(record.filing_record_id), str(casilla_id)


def _seeded_ledger_track_with_finalized_participation(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> str:
    """Create one ledger transaction consumed by a real, verified calculation."""
    unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
    seed_clean_cross_period_sources(
        unit,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        filing_repository=ModeloRecordCatalogueRepository(),
        bucket_event_repository=BucketEventHistoryRepository(),
        operation=operation,
    )
    ledger_ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=str(profile_id),
            booked_date=date(2025, 1, 15),
            amount=Decimal("12.00"),
            direction=TransactionDirection.INCOMING,
            description="conformance track participation seed",
            business_classification=BusinessClassification.BUSINESS,
            taxable_base=Decimal("12.00"),
            iva_rate=Decimal("0"),
            iva_amount=Decimal("0"),
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        ),
        ports=ledger_ports,
        occurred_at=now(),
    )
    transaction_id = created.ref.transaction_id
    calculation = calculate_modelo_revision(
        unit.work_unit_id,
        ports=build_calculation_action_ports(bucket_id=unit.bucket_id, operation=operation),
        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        casilla_inputs={},
        binding_values=modelo_operation_test_support.FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
        source_transaction_ids=(transaction_id,),
    )
    report = verify_modelo_revision_with_preconditions(
        calculation.calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_verification_repository_bundle(unit.bucket_id, operation=operation),
        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        workflow_profile=resolve_active_workflow_profile(operation),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        operation=operation,
    ).report
    if report.completeness_status is not VerificationCompletenessStatus.COMPLETE:
        findings = "; ".join(finding.kind.value for finding in report.findings) or "no findings reported"
        raise AssertionError(f"track participation seed did not verify completely: {findings}")
    persisted = (
        CalculationRevisionCatalogueRepository().load(operation=operation).get(calculation.calculation_revision_id)
    )
    assert persisted is not None
    assert persisted.source_transaction_ids == (transaction_id,)
    assert persisted.state is CalculationRevisionState.VERIFICADO_COMPLETO
    index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(transaction_id)
    assert len(index.participations) == 1
    assert index.participations[0].calculation_revision_id == persisted.calculation_revision_id
    return transaction_id


def seeded_modelo_edit_submission(
    profile_id: UUID, *, operation: PinnedAuthorityOperation
) -> tuple[str, ModeloEditApplySubmissionV1]:
    """Build one canonical edit DTO over the revision this fixture just persisted."""
    from ...adapters.persistence.profile.modelos_calculation import (
        CalculationRevisionCatalogueRepository,
    )
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
    from ...application.modelo.edit_admission import admit_modelo_edit_baseline
    from ...application.modelo.edit_contract import ModeloEditMutationFamily
    from ...application.modelo.edit_models import (
        ModeloEditAdmittedV1,
        ModeloEditScalarAddressV1,
        ModeloEditScalarIntentKind,
        ModeloEditSubmissionV1,
        ModeloScalarEditIntentV1,
    )
    from ...core.casilla_id import validated_casilla_id

    unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
    seeded_casilla_id = validated_casilla_id("06")
    with bundled_indexed_authority().operation() as operation:
        calculate_modelo_revision(
            unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=unit.bucket_id, operation=operation),
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            casilla_inputs={seeded_casilla_id: Decimal("0")},
            binding_values=modelo_operation_test_support.FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
        )
    objects = secure_object_repository_for_active_bucket()
    work_catalogue = WorkUnitCatalogueRepository(objects=objects).load()
    calculation_catalogue = CalculationRevisionCatalogueRepository(objects=objects).load()
    current_unit = work_catalogue.get(unit.work_unit_id)
    if current_unit is None:
        raise AssertionError("the edit conformance fixture lost its seeded work unit")
    casilla_id = seeded_casilla_id
    admission = admit_modelo_edit_baseline(
        work_unit_id=unit.work_unit_id,
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
        operation=operation,
        operation_contracts=build_production_operation_registry().public_contract_set,
    )
    assert isinstance(admission, ModeloEditAdmittedV1)
    baseline = admission.baseline
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=casilla_id),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value="100.00",
            ),
        ),
    )
    return unit.work_unit_id, ModeloEditApplySubmissionV1.from_submission(submission)


def _profile_baseline(profile_id: UUID, *, decode_context: ProfileDecodeContext) -> dict[str, object]:
    """Use the actual encrypted record's CAS coordinates for a manager write."""
    record = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode_context).load(
        profile_id
    )
    return {"expected_revision": record.record_revision, "expected_content_digest": record.content_digest}


def _seeded_repeatable_row(
    profile_id: UUID, *, operation: PinnedAuthorityOperation, decode_context: ProfileDecodeContext
) -> tuple[str, dict[str, object]]:
    """Create a real schema row so update/remove target a stored identity."""
    baseline = _profile_baseline(profile_id, decode_context=decode_context)
    mutation = add_profile_repeatable_section_row(
        profile_id=str(profile_id),
        section_key="activities",
        values={"description": "Consultoria"},
        expected_revision=cast(int, baseline["expected_revision"]),
        expected_content_digest=cast(str, baseline["expected_content_digest"]),
        schema=operation.profile_schema(),
        profile_decode_context=decode_context,
    )
    return str(mutation.row_index), {
        "expected_revision": mutation.record.record_revision,
        "expected_content_digest": mutation.record.content_digest,
    }


def _workflow_obligation(modelo: str, period: Period) -> WorkflowObligationFacts:
    """Build a locale-neutral, period-consistent run obligation for encrypted fixtures."""
    return WorkflowObligationFacts(
        modelo=Modelo(modelo),
        period=period,
        opens_on=date(period.filing_year, 1, 1),
        closes_on=date(period.filing_year, 12, 31),
        status=ObligationStatus.UPCOMING,
    )


def _workflow_result(
    run_id: str,
    *,
    modelo: str,
    period: Period,
    started_at: datetime,
    aborted_reason: WorkflowAbortReason | None = None,
) -> WorkflowResult:
    """Create one valid persisted terminal record without private prose."""
    obligation = _workflow_obligation(modelo, period)
    if aborted_reason is None:
        return WorkflowResult(
            run_id=run_id,
            started_at=started_at,
            ended_at=started_at,
            final_stage=WorkflowStage.DONE,
            obligation=obligation,
            steps=(),
            summary_locale_key="application.workflow.results.completed",
        )

    condition_id = "workflow.execution.completed"
    verdict = PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id="workflow.execution.error_code",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values={"completed": False, "error_code": "workflow.execution.site_unavailable"},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    step = WorkflowStep(
        stage=WorkflowStage.BUILDING_DRAFT,
        started_at=started_at,
        ended_at=started_at,
        success=False,
        summary_locale_key="application.workflow.steps.workflow_failure",
        precondition_verdict=verdict,
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=started_at,
        ended_at=started_at,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=aborted_reason,
        obligation=obligation,
        steps=(step,),
        summary_locale_key="application.workflow.results.aborted",
    )


def _seeded_justificante_snapshot(profile_id: UUID):
    """Persist one synthetic receipt for local list/show executor scenarios."""
    pdf_bytes = b"%PDF-1.4\nregistered executor conformance\n%%EOF"
    return build_justificante_capture_service(str(profile_id)).capture(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        expediente_id="202613000010001A",
        csv="ABCD1234EFGH5678",
        pdf_bytes=pdf_bytes,
        pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        captured_at=now(),
    )


def _seeded_expedientes_snapshot(profile_id: UUID):
    """Persist one synthetic declaration-register snapshot without opening AEAT."""
    bucket_id = str(profile_id)
    captured_at = now()
    capture = ExpedientesCapture(
        declarations=(
            ExpedientesDeclaration(
                modelo="303",
                ejercicio=2025,
                period=Period.from_year_and_code(2025, "1T"),
                expediente_id="12345678901234567890",
                estado="ALTA",
                tipo_solicitud="PresentaciÃ³n",
                observaciones="Conformance snapshot",
                presented_at=captured_at,
                justificante_link_text="Justificante",
                archive_link_text="Archivo",
                declaration_copy_link_text="Copia",
            ),
        ),
        captured_at=captured_at,
        source_url=str(aeat_url("sede", "/declaraciones")),
        authenticated_identity="12345678Z",
    )
    return ExpedientesService(ports=build_expedientes_ports(bucket_id=bucket_id)).capture(
        bucket_id=bucket_id,
        capture=capture,
    )


def _seeded_notifications_snapshot(profile_id: UUID):
    """Persist one synthetic local notification snapshot; its query port is never called."""
    captured_at = now()
    return NotificationsService(ports=compose_notifications_ports(settings=load_settings())).capture(
        bucket_id=str(profile_id),
        snapshot=NotificationsSnapshot(
            rows=(
                RemoteNotification(
                    certificado_id="1234567890",
                    tipo=NotificationType.NOTIFICACION,
                    concepto="Conformance notification",
                    titular_nif="12345678Z",
                    titular_nombre="Synthetic taxpayer",
                    destinatario_nif="12345678Z",
                    destinatario_nombre="Synthetic taxpayer",
                    fecha_emision=captured_at.date(),
                    fecha_notificacion=None,
                    modo_notificacion=None,
                    leida=False,
                    source_url="https://sede.example/notification/1234567890",
                ),
            ),
            captured_at=captured_at,
            source_url="https://sede.example/notifications",
        ),
        authenticated_identity="12345678Z",
    )


def _seeded_notification_document(profile_id: UUID) -> NotificationDocumentRecord:
    """Persist one synthetic document custody index row for local read scenarios."""
    certificado_id = "2699101808461"
    digest = "c" * 64
    record = NotificationDocumentRecord(
        certificado_id=certificado_id,
        bucket_id=str(profile_id),
        attachment_id=digest,
        document_sha256=digest,
        byte_size=4096,
        source_url=f"https://sede.example/notification/{certificado_id}",
        fetched_at=now(),
        sancion=SancionLiquidacion(
            certificado_id=certificado_id,
            clave_liquidacion="A2860024500012345",
            referencia="2024/0001234",
            nif="12345678Z",
            objeto_tributario="sancion",
            base_sancion=Decimal("3687.120"),
            porcentaje_minimo=Decimal("50.00"),
            sancion_resultante=Decimal("1843.560"),
            reduccion_conformidad=Decimal("553.070"),
            reduccion_pronto_pago=Decimal("516.20"),
            diferencia=Decimal("774.290"),
            importe_a_ingresar=Decimal("774.290"),
            document_sha256=digest,
        ),
    )
    notification_document_repository(str(profile_id), load_settings()).save(record)
    return record


def _ledger_lifecycle_case(
    definition_id: str, *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> LedgerLifecycleOperationConformanceCase:
    operation_ids: tuple[LedgerLifecycleOperationId, ...] = (
        "ledger.archive",
        "ledger.stash",
        "ledger.restore",
        "ledger.exclude",
    )
    for operation_id in operation_ids:
        if definition_id == operation_id:
            return prepare_ledger_lifecycle_operation_conformance_case(operation_id, profile_id, operation=operation)
    raise ValueError(f"unsupported ledger lifecycle conformance case: {definition_id}")


def _prorrata_case(
    definition_id: str, *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> ProrrataOperationConformanceCase:
    return prepare_prorrata_operation_conformance_case(
        definition_id,
        profile_id,
        repository_factory=build_prorrata_register_repository,
        operation=operation,
        observation_repository=(
            build_calculation_action_ports(bucket_id=str(profile_id), operation=operation).observation_repository
            if definition_id == "ledger.prorrata.seed"
            else None
        ),
    )


def _seed_conformance_invoice(profile_id: UUID) -> Invoice:
    """Persist one domain-valid invoice for registered catalogue read scenarios."""
    invoice = Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": str(profile_id),
            "invoice_number": "CONFORMANCE-INVOICE-2025-001",
            "issued_at": date(2025, 5, 1),
            "counterparty_name": "Conformance Supplier",
            "notes": "Conformance note preserved by partial update",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
            "lines": (
                InvoiceLine(
                    description="Conformance catalogue invoice",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    subtotal=Decimal("100.00"),
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=Decimal("21.00"),
                ),
            ),
        }
    )
    InvoiceCatalogueRepository(bucket_id=str(profile_id)).save(InvoiceCatalogue(invoices={invoice.invoice_id: invoice}))
    return invoice
