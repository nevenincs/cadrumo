"""Build exact typed requests and their real local scenario state."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, SecretStr

from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    seed_modelo_ready_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.tests.cross_period_seeding import SEEDED_SOURCE_TAX_ID
from ...adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from ...adapters.persistence.profile.verify_observations import VerifyObservationRepository
from ...application.actividad_asset.operation_dtos import (
    ActivityAssetRevisionSnapshot,
    ScheduledAmortizationChargeSnapshot,
)
from ...application.auth.certificate_source_operations import (
    register_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from ...application.calculations.iva_compensation_history import seed_iva_compensation_period
from ...application.filing.producer_snapshot_m360 import (
    M360AmbitoEstablecimiento,
    M360CausaPresentacion,
    M360NivelCalidadDatos,
    M360TitularEnCalidadDe,
    Modelo360CuentaTitularFacts,
    Modelo360EstablecimientoFacts,
    Modelo360ProfileFacts,
    Modelo360RepresentanteFacts,
    Modelo360SolicitanteFacts,
    Modelo360SolicitudFacts,
)
from ...application.inventory.tests.registered_operation_conformance_support import (
    prepare_inventory_operation_conformance_case,
)
from ...application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from ...application.invoices.catalogue_read_operation import INVOICE_LIST_OPERATION_DEFINITION_ID
from ...application.invoices.catalogue_remove_operation import INVOICE_REMOVE_OPERATION_DEFINITION_ID
from ...application.invoices.catalogue_update_operation import (
    INVOICE_UPDATE_OPERATION_DEFINITION_ID,
    InvoiceUpdatePatch,
)
from ...application.ledger.actions_import import LedgerProviderID
from ...application.ledger.actions_split_merge import split_transaction
from ...application.ledger.classify_requests import LedgerClassifyPatch
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_mutation_operation import LedgerEvidenceUpdatePatch
from ...application.ledger.llm_classification import reject_llm_suggestion
from ...application.ledger.llm_classification_ports import LLMClassificationSuggestion
from ...application.ledger.models import ManualLedgerTransactionCommand, SplitChildCommand
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.ledger.update_contracts import LedgerUpdatePatch
from ...application.ledger.usage_ratio_repository import save_usage_ratio_profile
from ...application.live.verify import VerifyService, VerifySurface
from ...application.local_reader_contracts import LOCAL_READER_OPERATION_SUBJECT, LocalReaderProvisionAction
from ...application.modelo.aggregate_request import ModeloAggregateOperationRequest
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ...application.modelo.invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
)
from ...application.modelo.local_observation_contracts import ModeloLocalObservationCasillaValue
from ...application.modelo.m360_solicitud_operation import Modelo360RepresentanteAccountInput
from ...application.modelo.reconciliation_records import ModeloReconciliationEvidenceKind
from ...application.modelo.work_calculation_contracts import ModeloWorkCalculateRequest
from ...application.operations.operation_definition import OperationDefinition
from ...application.operations.public_period import PublicPeriod
from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadKind
from ...application.user_profile.automation_operations import build_automation_operation_definitions
from ...application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose
from ...application.user_profile.censal_file_import_operation import CensalFileImportProvenance
from ...application.user_profile.censal_operation import (
    CensalFieldIntent,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
)
from ...application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.recovery_custody import enroll_profile_recovery
from ...application.user_profile.view_operation import ProfileViewPageKind
from ...application.workflow.abort import WorkflowAbortReason
from ...application.workflow.persistence import WorkflowRunRepository
from ...core.auth_provider import AuthProviderKind
from ...core.external_constants import OutputLanguage
from ...core.identity_check_verdict import IdentityCheckVerdict
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.ledger_sort import LedgerSortField
from ...core.model_catalogue import ModelRole
from ...core.operations import profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.invoices.enums import IvaRate, PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.iva.classification import InvoiceKind
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ...domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from ...domain.modelos.filing_record import ExternalEvidenceKind
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.own_accounts import OwnAccountHolding
from ...domain.usage_ratios.model import UsageRatioProfile
from ...domain.user_profile.plantilla_media import PlantillaMediaState
from ...domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ...domain.user_profile.values import UserProfileFact
from ..adapter_composition import (
    build_bienes_inversion_repository,
    build_inventory_service_ports,
    build_ledger_evidence_ports,
)
from ..ledger_action_composition import compose_ledger_action_ports
from . import modelo_operation_test_support
from .activity_asset_operation_test_support import activity_asset_revision, seed_activity_asset
from .aggregate_operation_test_support import aggregate_conformance_command
from .invoice_evidence_operation_test_support import prepare_invoice_evidence_conformance_case
from .invoice_withholding_operation_test_support import seed_invoice_withholding_conformance_case
from .prorrata_bienes_operation_test_support import prepare_bienes_inversion_operation_conformance_case
from .registered_executor_scenario_constants import (
    _CREDENTIAL_INPUT,
    _LEDGER_LIST_PRIVATE_FILTER_SENTINEL,
    _OPERATOR_SCOPE_PORTS,
    _OWN_ACCOUNT_SYNTHETIC_IBAN,
    _ROTATED_CREDENTIAL_INPUT,
)
from .registered_executor_seeding_support import (
    _profile_baseline,
    _prorrata_case,
    _seed_conformance_invoice,
    _seeded_expedientes_snapshot,
    _seeded_justificante_snapshot,
    _seeded_ledger_track_with_finalized_participation,
    _seeded_modelo_filing_record,
    _seeded_notification_document,
    _seeded_notifications_snapshot,
    _seeded_repeatable_row,
    _workflow_result,
    seeded_modelo_edit_submission,
)


def _payload(
    definition: OperationDefinition, *, profile_id: UUID, tmp_path: Path, operation: PinnedAuthorityOperation
) -> tuple[str, BaseModel, bytes | None]:
    """Use only the exact request type exported by the registered definition."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    values: dict[str, object]
    secret: bytes | None = None
    subject_ref = f"profile:{profile_id}"
    if definition.definition_id in {
        "ledger.evidence.reader-readiness",
        "ledger.evidence.extract",
        "ledger.evidence.confirm",
    }:
        evidence_case = prepare_invoice_evidence_conformance_case(
            definition.definition_id, profile_id=profile_id, operation=operation
        )
        return profile_operation_subject(str(profile_id)), evidence_case.request, None
    if definition.definition_id.startswith("ledger.prorrata."):
        prorrata_case = _prorrata_case(definition.definition_id, profile_id=profile_id, operation=operation)
        return profile_operation_subject(str(profile_id)), prorrata_case.request, None
    if definition.definition_id == "modelo.aggregate":
        return (
            profile_operation_subject(str(profile_id)),
            ModeloAggregateOperationRequest.from_inputs(
                profile_id=profile_id, command=aggregate_conformance_command(operation=operation)
            ),
            None,
        )
    if definition.definition_id == MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID:
        withholding_seed = seed_invoice_withholding_conformance_case(profile_id, operation=operation)
        return profile_operation_subject(str(profile_id)), withholding_seed.request, None
    if definition.definition_id in {item.definition_id for item in build_automation_operation_definitions()}:
        # The default production graph has no trusted runtime owner. The
        # dedicated administration integration suite proves positive execution
        # of every member with real custody and an explicitly bound owner.
        return (
            subject_ref,
            definition.request_type.model_validate({"profile_id": profile_id, "request_id": UUID(int=1)}),
            b"synthetic" if definition.ephemeral_secret is not None else None,
        )
    match definition.definition_id:
        case "auth.local-read":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "kind": "diagnostics_list"}
        case "auth.profile.login":
            values = {"profile_id": profile_id}
            secret = _CREDENTIAL_INPUT.encode()
        case "auth.profile.passphrase-rotate":
            values = {"profile_id": profile_id}
            secret = (
                '{"current_passphrase":"'
                + _CREDENTIAL_INPUT
                + '","new_passphrase":"'
                + _ROTATED_CREDENTIAL_INPUT
                + '","new_passphrase_confirmation":"'
                + _ROTATED_CREDENTIAL_INPUT
                + '"}'
            ).encode()
        case "auth.provider.configure":
            values = {"provider": AuthProviderKind.CERTIFICATE}
        case "auth.session.acquire":
            # Named rather than defaulted: an omitted provider resolves from
            # the host's deployment settings, which can select Cl@ve and turn
            # this into an identity refusal against whatever DNI the host holds.
            values = {"provider": AuthProviderKind.CERTIFICATE}
        case (
            "auth.certificate.source.register"
            | "auth.certificate.source.list"
            | "auth.certificate.source.select"
            | "auth.certificate.source.remove"
            | "auth.certificate.source.check"
            | "auth.certificate.secret.set"
            | "auth.certificate.secret.remove"
        ):
            source_name = "supervisor-certificate"
            source_path = tmp_path / "absent-certificate.p12"
            if definition.definition_id != "auth.certificate.source.register":
                register_operator_certificate_source(
                    name=source_name,
                    certificate_path=source_path,
                    operation=operation,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )
            values = {"profile_id": profile_id}
            if definition.definition_id not in {"auth.certificate.source.list", "auth.certificate.source.check"}:
                values["name"] = source_name
            if definition.definition_id == "auth.certificate.source.register":
                values["certificate_path"] = source_path
            if definition.definition_id == "auth.certificate.secret.set":
                secret = _CREDENTIAL_INPUT.encode()
            elif definition.definition_id == "auth.certificate.secret.remove":
                set_operator_certificate_source_secret(
                    name=source_name,
                    secret=SecretStr(_CREDENTIAL_INPUT),
                    certificate_secret_backend_factory=build_certificate_secret_backend,
                    operation=operation,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )
        case "ledger.ratios.list" | "ledger.ratios.eligible":
            values = {"profile_id": profile_id, "year": 2025}
        case "ledger.ratios.validate":
            values = {"profile_id": profile_id}
        case "ledger.ratios.set":
            values = {"profile_id": profile_id, "year": 2025, "category": "vehiculo_combustible", "ratio": "0.5"}
        case "ledger.ratios.unset":
            category = require_spending_category("vehiculo_combustible", authority=operation)
            save_usage_ratio_profile(
                UsageRatioProfile(ratios={category: Decimal("0.50")}),
                bucket_id=str(profile_id),
            )
            values = {"profile_id": profile_id, "category": "vehiculo_combustible"}
        case "auth.session.logout" | "auth.session.reset":
            values = {"all_providers": True}
        case "user-profile.field-mutation":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
                "path": PROFILE_OUTPUT_LANGUAGE_PATH,
                "value": "es",
            }
        case "user-profile.patch":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
                "colegio_concertado": True,
            }
        case "user-profile.plantilla-media":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
                "year": 2025,
                "change": {"kind": "set", "average_workforce": "2.50", "state": PlantillaMediaState.OBSERVED},
            }
        case "user-profile.descendants":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
                "descendants": (),
            }
        case "user-profile.complete-setup":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
            }
        case "user-profile.view":
            values = {"profile_id": profile_id, "page_kind": ProfileViewPageKind.FACTS}
        case "workbench.generation":
            values = {"profile_id": profile_id, "output_language": OutputLanguage.ES}
        case "user-profile.repeatable-row-mutation":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
                "section_key": "activities",
                "values": ({"field_key": "description", "value": "Consultoria"},),
            }
        case "user-profile.repeatable-row-update" | "user-profile.repeatable-row-remove":
            row_key, baseline = _seeded_repeatable_row(
                profile_id, operation=operation, decode_context=_profile_decode_context_for_test
            )
            values = {
                "profile_id": profile_id,
                **baseline,
                "section_key": "activities",
                "row_key": row_key,
            }
            if definition.definition_id == "user-profile.repeatable-row-update":
                values["values"] = ({"field_key": "description", "value": "Assessoria"},)
        case "user-profile.bundle-export":
            values = {
                "profile_id": profile_id,
                "destination": tmp_path / "profile.bundle",
                "purpose": ProfileBundleExportPurpose.PORTABLE_TRANSFER,
            }
            secret = _CREDENTIAL_INPUT.encode()
        case "user-profile.logout":
            values = {"profile_id": profile_id}
        case "local-reader.provision":
            subject_ref = LOCAL_READER_OPERATION_SUBJECT
            values = {"action": LocalReaderProvisionAction.VERIFY, "role": ModelRole.TEXT_EXTRACTION}
        case "live.expedientes.capture.single":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "modelo": "303", "year": 2025}
        case "live.expedientes.capture.bulk":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "modelos": ("303",), "year_from": 2025, "year_to": 2025}
        case "live.filed-capture.single":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "output_root": tmp_path / "filed-single",
                "modelo": "303",
                "year": 2025,
                "period": "1T",
            }
        case "live.filed-capture.bulk":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "output_root": tmp_path / "filed-bulk",
                "year_from": 2025,
                "year_to": 2025,
                "modelos": ("303",),
            }
        case "live.filed-capture.source":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "output_root": tmp_path / "filed-source",
                "modelo": "303",
                "year": 2025,
                "period": "1T",
            }
        case "live.filed-list":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "modelo": "303", "year_from": 2025, "year_to": 2025}
        case "live.filed-discover":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.justificante.list":
            _seeded_justificante_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.justificante.capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "modelo": "130", "year": 2025, "period": "1T"}
        case "live.justificante.show":
            snapshot = _seeded_justificante_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "snapshot_id": snapshot.snapshot_id}
        case "live.expedientes.list":
            _seeded_expedientes_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.expedientes.show":
            snapshot = _seeded_expedientes_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "snapshot_id": snapshot.snapshot_id}
        case "live.expedientes.latest":
            _seeded_expedientes_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.notifications.list" | "live.notifications.latest":
            _seeded_notifications_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.notifications.show":
            snapshot = _seeded_notifications_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "snapshot_id": snapshot.snapshot_id}
        case "live.notifications.document.view":
            record = _seeded_notification_document(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "certificado_id": record.certificado_id}
        case "live.notifications.document.history":
            _seeded_notification_document(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.notifications.capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.notifications.document.capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "certificado_id": "2699101808461"}
        case "live.verify.nif-iva" | "live.verify.tgvi":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "nif": "12345678Z"}
        case "live.verify.list" | "live.verify.view" | "live.verify.latest":
            subject_ref = profile_operation_subject(str(profile_id))
            observation = VerifyService(persistence=VerifyObservationRepository(bucket_id=str(profile_id))).record(
                bucket_id=str(profile_id),
                surface=VerifySurface.NIF_IVA,
                nif="12345678Z",
                verdict=IdentityCheckVerdict.VALID,
                checked_at=now(),
            )
            values = {"profile_id": profile_id}
            if definition.definition_id == "live.verify.view":
                values["observation_id"] = observation.observation_id
            elif definition.definition_id == "live.verify.latest":
                values.update(surface=VerifySurface.NIF_IVA, nif="12345678Z")
        case "live.filed-history.pull":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "output_root": tmp_path / "filed-history", "dry_run": True}
        case "live.iva-wallet.history":
            period = Period.from_year_and_code(2025, "1T")
            history_state = IvaCompensationPeriodState(
                provenance=IvaCompensationStateProvenance.APP_FILING,
                taxpayer_nif="12345678Z",
                filing_year=2025,
                period=period,
                registry_snapshot_ref=operation.snapshot(
                    "303", filing_year=2025, period=period.registry_token
                ).snapshot_ref,
                presented_at=now(),
                prior_pending_amount=Decimal("0"),
                applied_amount=Decimal("0"),
                pending_for_later_amount=Decimal("40.00"),
                period_result_amount=Decimal("-40.00"),
                final_result_amount=Decimal("-40.00"),
                generated_amount=Decimal("40.00"),
                available_end_amount=Decimal("40.00"),
                source_observation_key="conformance:iva-history:2025:1T",
            )
            IvaCompensationHistoryRepository().save_period(history_state)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "as_of_year": 2025}
        case "modelo.iva-wallet.correct":
            period = Period.from_year_and_code(2024, "4T")
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            seed_iva_compensation_period(
                taxpayer_nif=SEEDED_SOURCE_TAX_ID,
                period=period,
                amount=Decimal("500.00"),
                repository=IvaCompensationHistoryRepository(bucket_id=str(profile_id)),
                operation=operation,
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(period),
                "amount": "1200.50",
                "reason": "corrected opening balance",
            }
        case "modelo.iva-wallet.balance":
            period = Period.from_year_and_code(2024, "4T")
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            seed_iva_compensation_period(
                taxpayer_nif=SEEDED_SOURCE_TAX_ID,
                period=period,
                amount=Decimal("500.00"),
                repository=IvaCompensationHistoryRepository(bucket_id=str(profile_id)),
                operation=operation,
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "as_of_year": 2024}
        case "modelo.iva-wallet.seed":
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2024, "4T")),
                "amount": "500.00",
            }
        case "modelo.iva-wallet.override":
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2025, "1T")),
                "amount": "450.00",
                "reason": "operator asserted prior compensation",
                "evidence_locator": "synthetic:conformance:prior-compensation",
            }
        case "live.iva-wallet.capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "target_year": 2025, "target_period": "1T"}
        case "live.iva-wallet.evidence-capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "output_root": tmp_path / "iva-evidence",
                "year_from": 2025,
                "year_to": 2025,
                "target_year": 2025,
                "target_period": "1T",
            }
        case "live.iva-wallet.history-capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "output_root": tmp_path / "iva-history-capture",
                "year_from": 2025,
                "year_to": 2025,
            }
        case "export.google-sheets":
            values = {"profile_id": profile_id, "modelo": "130", "filing_year": 2025, "period": "1T", "dry_run": False}
        case "user-profile.censo-review":
            subject_ref = str(profile_id)
            record = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=_profile_decode_context_for_test
            ).load(profile_id)
            values = {
                "baseline": CensalProfileBaseline.from_record(record),
                "field_intents": tuple(
                    CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT)
                    for path in CENSAL_ADOPTABLE_PATHS
                ),
            }
        case "user-profile.censo-prepare":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "user-profile.censo-file-import":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "facts": (
                    {
                        "path": "contact.fiscal_address",
                        "value": "Calle Mayor 1",
                        "source": CensalFileImportProvenance.ARTEFACT,
                    },
                ),
            }
        case "user-profile.censo-preview":
            subject_ref = profile_operation_subject(str(profile_id))
            record = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=_profile_decode_context_for_test
            ).load(profile_id)
            values = {"baseline": CensalProfileBaseline.from_record(record)}
        case "modelo.reconcile.import":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "work_unit_id": unit.work_unit_id,
                "source_kind": ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                "source_path": str(tmp_path / "missing-evidence.pdf"),
            }
        case "modelo.reconcile.pull":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id, "snapshot_id": "a" * 64}
        case "modelo.reconcile.list":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "work_unit_id": None}
        case "modelo.work.rename":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "work_unit_id": unit.work_unit_id,
                "new_name": "Conformance renamed unit",
                "observed_name": unit.name,
                "observed_updated_at": unit.updated_at,
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.metadata":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id}
        case "modelo.work.create":
            upsert_test_profile_facts(
                profile_id,
                (
                    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                    UserProfileFact(path="identity.name", value="Conformance"),
                    UserProfileFact(path="identity.surnames", value="Natural Person"),
                    UserProfileFact(path="activities.description", value="professional services"),
                    UserProfileFact(path="censo.activity_start_date", value="2025-01-01"),
                    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                    UserProfileFact(path="iva.regime", value="GENERAL"),
                    UserProfileFact(path="iva.m303_regime_composition", value="general"),
                    UserProfileFact(path="iva.redeme_enrolled", value=False),
                    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                ),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "modelo": "202",
                "period": PublicPeriod.from_period(Period.from_year_and_code(2025, "1P")),
                "revision_id": "2025-y-siguientes",
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.list":
            modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "include_discarded": False}
        case "modelo.work.history":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id}
        case "modelo.work.review":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id}
        case "modelo.work.form":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id, "output_language": OutputLanguage.ES}
        case "modelo.work.casilla_help":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "profile_id": profile_id,
                "work_unit_id": unit.work_unit_id,
                "casilla_id": "06",
                "registry_revision_id": str(unit.revision_id),
                "calculation_revision_id": None,
                "output_language": OutputLanguage.ES,
            }
        case "modelo.edit.renew":
            work_unit_id, wire_submission = seeded_modelo_edit_submission(profile_id, operation=operation)
            subject_ref = work_unit_id
            values = {"profile_id": profile_id, "baseline": wire_submission.baseline}
        case "modelo.edit.preflight":
            work_unit_id, wire_submission = seeded_modelo_edit_submission(profile_id, operation=operation)
            subject_ref = work_unit_id
            return subject_ref, ModeloEditOperatorInputV2(submission=wire_submission), None
        case "modelo.edit.apply_prerequisite":
            work_unit_id, wire_submission = seeded_modelo_edit_submission(profile_id, operation=operation)
            subject_ref = work_unit_id
            values = {
                "profile_id": profile_id,
                "work_unit_id": work_unit_id,
                "apply_operation_id": "e" * 64,
                "baseline_id": wire_submission.baseline.baseline_id,
                "calculation_revision_id": wire_submission.baseline.current_calculation_revision_id,
                "registry_revision_id": wire_submission.baseline.law_selected_revision_id,
            }
        case "modelo.work.filing_record":
            filing_record_id, _casilla_id = _seeded_modelo_filing_record(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "filing_record_id": filing_record_id}
        case "modelo.filing_record.view":
            filing_record_id, _casilla_id = _seeded_modelo_filing_record(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "filing_record_id": filing_record_id}
        case "modelo.filing_record.list":
            _seeded_modelo_filing_record(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "modelo.verification_report.list":
            modelo_operation_test_support.seeded_modelo_verification_report(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "modelo.verification_report.view":
            _revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
                profile_id, operation=operation
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "verification_report_id": report_id}
        case "modelo.observation.local":
            modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            revision = resolved_revision(
                modelo=modelo_operation_test_support.MODELO,
                filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
                period=modelo_operation_test_support.MODELO_PERIOD,
            )
            casilla_id = sorted(casilla.id for casilla in revision.casillas)[0]
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "action": "record",
                "modelo": modelo_operation_test_support.MODELO,
                "period": PublicPeriod.from_period(
                    Period.from_year_and_code(
                        modelo_operation_test_support.MODELO_FILING_YEAR,
                        modelo_operation_test_support.MODELO_PERIOD,
                    )
                ),
                "casilla_values": (ModeloLocalObservationCasillaValue(casilla_id=casilla_id, value="100"),),
                "actor": None,
                "reason": "conformance observation",
            }
        case "modelo.filing_record.import":
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            revision = resolved_revision(
                modelo=modelo_operation_test_support.MODELO,
                filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
                period=modelo_operation_test_support.MODELO_PERIOD,
            )
            casilla_id = sorted(casilla.id for casilla in revision.casillas)[0]
            evidence_reference_id = f"CSV{modelo_operation_test_support.MODELO}{modelo_operation_test_support.MODELO_FILING_YEAR}{modelo_operation_test_support.MODELO_PERIOD}".upper()
            persist_justificante_metadata(
                evidence_reference_id,
                modelo=modelo_operation_test_support.MODELO,
                filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
                period=modelo_operation_test_support.MODELO_PERIOD,
                captured_at=now(),
                tax_id=SEEDED_SOURCE_TAX_ID,
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "work_unit_id": unit.work_unit_id,
                "evidence_kind": ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                "evidence_reference_id": evidence_reference_id,
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                "casilla_values": ((casilla_id, "100"),),
            }
        case "modelo.work.amendment_context":
            filing_record_id, _casilla_id = _seeded_modelo_filing_record(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "filing_record_id": filing_record_id}
        case "modelo.work.dependencies":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "filing_year": unit.filing_year,
                "modelo": unit.modelo,
                "period": PublicPeriod.from_period(unit.period),
            }
        case "workflow.run.read":
            run_id = "a" * 16
            period = Period.from_year_and_code(2025, "1T")
            WorkflowRunRepository().save(
                _workflow_result(
                    run_id,
                    modelo="303",
                    period=period,
                    started_at=datetime(2025, 5, 1, tzinfo=UTC),
                )
            )
            subject_ref = run_id
            values = {
                "profile_id": profile_id,
                "run_id": run_id,
                "expected_period": PublicPeriod.from_period(period),
            }
        case overview_definition_id if overview_definition_id in OVERVIEW_READ_DEFINITION_IDS.values():
            kind = OverviewReadKind(overview_definition_id.removeprefix("overview."))
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "kind": kind, "output_language": OutputLanguage.ES}
            if kind is OverviewReadKind.CALENDAR:
                values.update({"from_date": date(2025, 1, 1), "to_date": date(2025, 12, 31)})
            elif kind is OverviewReadKind.AGENDA:
                values.update({"as_of": date(2025, 1, 1), "horizon_days": 30})
            elif kind is OverviewReadKind.BACKLOG:
                values.update({"from_date": date(2025, 1, 1), "to_date": date(2025, 12, 31)})
            elif kind is OverviewReadKind.EXPLAIN:
                values.update({"modelo": "303", "year": 2025})
            elif kind is OverviewReadKind.PREPARE:
                values.update(
                    {"modelo": "303", "period": PublicPeriod.from_period(Period.from_year_and_code(2025, "1T"))}
                )
        case "overview.pipeline":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            for booked_date, description in (
                (date(2025, 1, 15), "conformance overview selected-period seed"),
                (date(2025, 4, 15), "conformance overview other-period seed"),
            ):
                create_manual_transaction(
                    ManualLedgerTransactionCommand(
                        bucket_id=str(profile_id),
                        booked_date=booked_date,
                        amount=Decimal("12.00"),
                        direction=TransactionDirection.INCOMING,
                        description=description,
                        business_classification=BusinessClassification.NOT_YET_PROCESSED,
                        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                    ),
                    ports=ports,
                    occurred_at=now(),
                )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2025, "1T")),
                "output_language": OutputLanguage.ES,
            }
        case "workflow.run.list":
            first_period = Period.from_year_and_code(2025, "1T")
            second_period = Period.from_year_and_code(2025, "2T")
            WorkflowRunRepository().save(
                _workflow_result(
                    "a" * 16,
                    modelo="303",
                    period=first_period,
                    started_at=datetime(2025, 5, 1, tzinfo=UTC),
                )
            )
            WorkflowRunRepository().save(
                _workflow_result(
                    "b" * 16,
                    modelo="130",
                    period=second_period,
                    started_at=datetime(2025, 8, 1, tzinfo=UTC),
                )
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "workflow.resume.context":
            revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
                profile_id, operation=operation
            )
            revision = CalculationRevisionCatalogueRepository().load(operation=operation).get(revision_id)
            assert revision is not None
            unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
            assert unit is not None
            run_id = "c" * 16
            WorkflowRunRepository().save(
                _workflow_result(
                    run_id,
                    modelo=unit.modelo,
                    period=unit.period,
                    started_at=datetime(2026, 1, 1, tzinfo=UTC),
                    aborted_reason=WorkflowAbortReason.SITE_UNAVAILABLE,
                )
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "calculation_revision_id": revision_id}
        case "modelo.work.wizard_context":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "profile_id": profile_id,
                "work_unit_id": unit.work_unit_id,
                "output_language": OutputLanguage.ES,
            }
        case "modelo.work.revision":
            revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
                profile_id, operation=operation
            )
            values = {"profile_id": profile_id, "calculation_revision_id": revision_id}
        case "modelo.work.revision_snapshot":
            revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
                profile_id, operation=operation
            )
            revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
            assert revision is not None
            subject_ref = revision.work_unit_id
            values = {"profile_id": profile_id, "calculation_revision_id": revision_id}
        case "modelo.work.revisions":
            modelo_operation_test_support.seeded_modelo_calculation_revision(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "work_unit_id": None}
        case "modelo.work.compare_taxation":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id}
        case "modelo.review_package.build":
            revision_id, _report_id = modelo_operation_test_support.seeded_modelo_verification_report(
                profile_id, operation=operation
            )
            revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
            assert revision is not None
            subject_ref = revision.work_unit_id
            output_path = (tmp_path / "review-package.zip").resolve()
            values = {
                "profile_id": profile_id,
                "calculation_revision_id": revision_id,
                "output_path": str(output_path),
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.m303_attestation":
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            upsert_test_profile_facts(
                str(profile_id),
                (UserProfileFact(path="censo.activity_start_date", value="2025-01-01"),),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "work_unit_id": None,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2025, "4T")),
                "observed_at": now(),
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "ledger.counterparty":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "action": "confirm",
                "tax_identifier": "B12345674",
                "territorial_scope": "es_canarias",
                "asserted_by": "operator:registered-executor-conformance",
                "note": "synthetic supervisor conformance assertion",
            }
        case "ledger.own_account":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "action": "add",
                "label": "synthetic conformance account",
                "holding": OwnAccountHolding.TITULAR,
                "iban": _OWN_ACCOUNT_SYNTHETIC_IBAN,
            }
        case "modelo.m360_solicitud":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "action": "declare",
                "filing_year": 2025,
                "facts": Modelo360ProfileFacts(
                    solicitud=Modelo360SolicitudFacts(
                        nivel_calidad_datos=M360NivelCalidadDatos.MAXIMA,
                        pais_destino="FR",
                        causa_presentacion=M360CausaPresentacion.INICIAL,
                    ),
                    solicitante=Modelo360SolicitanteFacts(
                        email="solicitante@example.es",
                        establecimiento=Modelo360EstablecimientoFacts(
                            ambito=M360AmbitoEstablecimiento.TERRITORIO_COMUN
                        ),
                    ),
                    representante=Modelo360RepresentanteFacts(tax_id="00000000T", full_name="ASESORES PRUEBA SL"),
                    cuenta=Modelo360CuentaTitularFacts(
                        titular_nombre="ASESORES PRUEBA SL",
                        titular_en_calidad_de=M360TitularEnCalidadDe.REPRESENTANTE,
                        divisa="EUR",
                    ),
                ),
                "representante_account": Modelo360RepresentanteAccountInput(
                    iban=_OWN_ACCOUNT_SYNTHETIC_IBAN, swift_bic="CAIXESBBXXX"
                ),
            }
        case "ledger.remove":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 15),
                    amount=Decimal("12.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance removal dry run seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_id": created.ref.transaction_id,
                "reason": "synthetic conformance dry run",
                "dry_run": True,
            }
        case "ledger.allocate":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 17),
                    amount=Decimal("20.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance business-share allocation seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_id": created.ref.transaction_id,
                "business_pct": "0.5",
            }
        case "ledger.classify.single":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 19),
                    amount=Decimal("22.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance single classification seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_id": created.ref.transaction_id,
                "patch": LedgerClassifyPatch(business_classification="BUSINESS"),
                "patch_fields": ("business_classification",),
            }
        case "ledger.classify.bulk":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created_valid = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 20),
                    amount=Decimal("23.00"),
                    direction=TransactionDirection.OUTGOING,
                    description=f"conformance bulk classification valid {profile_id.hex}",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            created_invalid = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 20),
                    amount=Decimal("24.00"),
                    direction=TransactionDirection.OUTGOING,
                    description=f"conformance bulk classification invalid {profile_id.hex}",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "csv_text": (
                    "transaction_id,classification,iva_category\n"
                    f"{created_valid.ref.transaction_id},BUSINESS,domestic_general\n"
                    f"{created_invalid.ref.transaction_id},BUSINESS,not-a-declared-category\n"
                ),
                "actor": None,
            }
        case "ledger.evidence.add":
            evidence_file = tmp_path / "conformance-purchase-invoice-add.pdf"
            evidence_file.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "source_path": str(evidence_file), "source_directory": str(tmp_path)}
        case "ledger.evidence.list" | "ledger.evidence.view" | "ledger.evidence.update" | "ledger.evidence.remove":
            evidence_file = tmp_path / "conformance-purchase-invoice.pdf"
            evidence_file.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
            evidence = PurchaseInvoiceEvidenceService(
                ports=build_ledger_evidence_ports(bucket_id=str(profile_id)),
            ).add(bucket_id=str(profile_id), source_path=evidence_file)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
            if definition.definition_id == "ledger.evidence.view":
                values["evidence_id"] = evidence.record.evidence_id
            if definition.definition_id == "ledger.evidence.update":
                values.update(
                    evidence_id=evidence.record.evidence_id,
                    patch=LedgerEvidenceUpdatePatch(supplier="Conformance Supplier"),
                    patch_fields=("supplier",),
                )
            if definition.definition_id == "ledger.evidence.remove":
                values["evidence_id"] = evidence.record.evidence_id
        case "ledger.split.manual":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 21),
                    amount=Decimal("20.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance manual split seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_id": created.ref.transaction_id,
                "children": (
                    {"amount": "8", "description": "first split child"},
                    {"amount": "12", "description": "second split child"},
                ),
                "reason": "synthetic conformance split",
            }
        case "ledger.merge":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 22),
                    amount=Decimal("20.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance manual merge seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            split = split_transaction(
                bucket_id=str(profile_id),
                transaction_id=created.ref.transaction_id,
                children=(
                    SplitChildCommand(amount=Decimal("8"), description="first merge child"),
                    SplitChildCommand(amount=Decimal("12"), description="second merge child"),
                ),
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                reason="synthetic conformance merge seed",
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "child_ids": split.child_transaction_ids,
                "reason": "synthetic conformance merge",
            }
        case "ledger.update":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 18),
                    amount=Decimal("21.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance ledger update seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_id": created.ref.transaction_id,
                "patch": LedgerUpdatePatch(description="updated through registered operation"),
                "patch_fields": ("description",),
            }
        case "ledger.reset":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 16),
                    amount=Decimal("13.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance catalogue reset seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "reason": "synthetic conformance reset",
                "dry_run": False,
            }
        case "ledger.import":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "files": (tmp_path / "missing.csv",),
                "provider": LedgerProviderID.CSV,
                "dry_run": True,
                "verify": False,
                "verify_source": None,
                "period": None,
            }
        case "ledger.add":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "booked_date": "2025-01-20",
                "amount": "23.00",
                "direction": TransactionDirection.OUTGOING,
                "description": "conformance manual add",
            }
        case "ledger.status":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "period": None}
        case "ledger.check":
            absent_transaction_id = "f" * 64
            invoice = Invoice.model_validate(
                {
                    "kind": InvoiceKind.RECEIVED,
                    "bucket_id": str(profile_id),
                    "invoice_number": "CHECK-2025-001",
                    "issued_at": date(2025, 5, 1),
                    "counterparty_name": "Conformance Supplier",
                    "counterparty_tax_id": "B12345674",
                    "counterparty_country": "ES",
                    "base_total": Decimal("100.00"),
                    "iva_total": Decimal("21.00"),
                    "grand_total": Decimal("121.00"),
                    "currency": "EUR",
                    "payment_status": PaymentStatus.PAID,
                    "linked_transaction_ids": (absent_transaction_id,),
                    "lines": (
                        InvoiceLine(
                            description="Conformance invoice link",
                            quantity=Decimal("1"),
                            unit_price=Decimal("100.00"),
                            subtotal=Decimal("100.00"),
                            iva_rate=IvaRate.from_registry("RATE_21"),
                            iva_amount=Decimal("21.00"),
                        ),
                    ),
                }
            )
            InvoiceCatalogueRepository(bucket_id=str(profile_id)).save(
                InvoiceCatalogue(invoices={invoice.invoice_id: invoice})
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2026, "1T")),
            }
        case "ledger.preflight":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2026, 1, 15),
                    amount=Decimal("121.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance preflight selected-period issue",
                    business_classification=BusinessClassification.BUSINESS,
                    category_id=None,
                    taxable_base=Decimal("100.00"),
                    iva_rate=Decimal("0.21"),
                    iva_amount=Decimal("21.00"),
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2026, 4, 15),
                    amount=Decimal("242.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance preflight outside-period issue",
                    business_classification=BusinessClassification.BUSINESS,
                    category_id=None,
                    taxable_base=Decimal("200.00"),
                    iva_rate=Decimal("0.21"),
                    iva_amount=Decimal("42.00"),
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now() + timedelta(seconds=1),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2026, "1T")),
            }
        case "ledger.history":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 15),
                    amount=Decimal("12.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance history seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_prefix": created.ref.transaction_id[:12],
                "include_split_siblings": False,
            }
        case "ledger.view":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 15),
                    amount=Decimal("12.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance view seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            reject_llm_suggestion(
                LLMClassificationSuggestion(
                    transaction_id=created.ref.transaction_id,
                    provenance="llm:conformance:test-model",
                    classification=BusinessClassification.BUSINESS,
                    confidence=Decimal("0.9"),
                    reason="conformance suggestion",
                ),
                bucket_id=str(profile_id),
                reason="operator rejected the conformance suggestion",
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                source_command="conformance ledger view seed",
                transaction_repository=ports.transaction_repository,
                bucket_event_repository=ports.bucket_event_repository,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_prefix": created.ref.transaction_id[:12],
            }
        case "ledger.track":
            transaction_id = _seeded_ledger_track_with_finalized_participation(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_prefix": transaction_id[:12],
            }
        case "ledger.list":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            for index, (booked_date, description) in enumerate(
                (
                    (date(2025, 1, 15), "ledger list page A"),
                    (date(2025, 2, 15), "ledger list page B"),
                    (date(2025, 3, 15), "ledger list page C"),
                    (date(2025, 4, 15), "ledger list outside period"),
                )
            ):
                create_manual_transaction(
                    ManualLedgerTransactionCommand(
                        bucket_id=str(profile_id),
                        booked_date=booked_date,
                        amount=Decimal(10 + index),
                        direction=TransactionDirection.OUTGOING,
                        description=description,
                        business_classification=BusinessClassification.NOT_YET_PROCESSED,
                        group_label=_LEDGER_LIST_PRIVATE_FILTER_SENTINEL,
                        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                    ),
                    ports=ports,
                    occurred_at=now() + timedelta(seconds=index),
                )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "filters": ("period=1T", "year=2025", "classification=not_yet_processed"),
                "group": _LEDGER_LIST_PRIVATE_FILTER_SENTINEL,
                "limit": 2,
                "offset": 1,
                "sort_by": LedgerSortField.DESCRIPTION,
            }
        case (
            "ledger.inventory.list"
            | "ledger.inventory.create"
            | "ledger.inventory.movement.add"
            | "ledger.inventory.valuation.preview"
            | "ledger.inventory.closing-authority.record"
        ):
            inventory_case = prepare_inventory_operation_conformance_case(
                definition.definition_id, profile_id, ports_factory=build_inventory_service_ports
            )
            subject_ref = profile_operation_subject(str(profile_id))
            inventory_payload = inventory_case.request
            assert isinstance(inventory_payload, BaseModel)
            assert isinstance(inventory_payload, definition.request_type)
            return subject_ref, inventory_payload, None
        case "ledger.bienes_inversion.list" | "ledger.bienes_inversion.declare":
            bienes_case = prepare_bienes_inversion_operation_conformance_case(
                definition.definition_id,
                profile_id,
                repository_factory=build_bienes_inversion_repository,
                operation=operation,
            )
            assert isinstance(bienes_case.request, definition.request_type)
            return profile_operation_subject(str(profile_id)), bienes_case.request, None
        case "ledger.actividad-asset.create":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "revision": ActivityAssetRevisionSnapshot.from_domain(activity_asset_revision("conformance-create")),
            }
        case (
            "ledger.actividad-asset.inspect"
            | "ledger.actividad-asset.correct"
            | "ledger.actividad-asset.forecast"
            | "ledger.actividad-asset.claim"
            | "ledger.actividad-asset.filing-handoff"
        ):
            action = definition.definition_id.rsplit(".", 1)[1]
            asset_seed = seed_activity_asset(
                profile_id,
                operation=operation,
                asset_id=f"conformance-{action}",
                include_claim=action == "filing-handoff",
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
            if action == "inspect":
                values["asset_id"] = asset_seed.revision.asset_id
            elif action == "correct":
                values["revision"] = ActivityAssetRevisionSnapshot.from_domain(
                    activity_asset_revision(
                        asset_seed.revision.asset_id,
                        revision_number=2,
                        supersedes_revision_id=asset_seed.revision.revision_id,
                    )
                )
            elif action == "forecast":
                values.update(
                    asset_id=asset_seed.revision.asset_id, covered_from=date(2025, 1, 1), covered_until=date(2026, 1, 1)
                )
            elif action == "claim":
                values.update(
                    forecast=ScheduledAmortizationChargeSnapshot.from_domain(asset_seed.forecast),
                    creating_operation="activity-asset-conformance.claim",
                )
            else:
                values.update(tax_year=2025, m130_period="4T")
        case "ledger.invoice.add":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "kind": InvoiceKind.RECEIVED,
                "counterparty_name": "Conformance Supplier",
                "counterparty_tax_id": "B12345674",
                "counterparty_country": "ES",
                "invoice_number": "CONFORMANCE-INVOICE-2025-ADD",
                "issued_at": date(2025, 5, 1),
                "taxable_base": {"decimal": "100.00"},
                "iva_rate": {"decimal": "21"},
                "currency": "EUR",
            }
        case "user-profile.recovery.status":
            enroll_profile_recovery(
                profile_id=profile_id,
                current_passphrase=_CREDENTIAL_INPUT,
                recovery_handover=lambda enrollment: enrollment.recovery_key.code,
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "ledger.invoice.list" | "ledger.invoice.view" | "ledger.invoice.remove" | "ledger.invoice.update":
            invoice = _seed_conformance_invoice(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
            if definition.definition_id == INVOICE_LIST_OPERATION_DEFINITION_ID:
                values["kind"] = None
            elif definition.definition_id in {
                INVOICE_REMOVE_OPERATION_DEFINITION_ID,
                INVOICE_UPDATE_OPERATION_DEFINITION_ID,
            }:
                values["invoice_id"] = invoice.invoice_id
                if definition.definition_id == INVOICE_UPDATE_OPERATION_DEFINITION_ID:
                    values["patch"] = InvoiceUpdatePatch.from_patch(
                        CatalogueInvoicePatch.model_validate(
                            {"counterparty_name": "Updated conformance supplier", "retention_amount": Decimal("0.00")}
                        )
                    )
            else:
                values["invoice_id"] = invoice.invoice_id
        case "ledger.participation":
            transaction_id = _seeded_ledger_track_with_finalized_participation(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "transaction_prefix": transaction_id[:12]}
        case "ledger.participation.rebuild":
            _seeded_ledger_track_with_finalized_participation(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "ledger.review":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 15),
                    amount=Decimal("21.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance review seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "transaction_prefix": created.ref.transaction_id[:12]}
        case "modelo.work.report_verify":
            tmp_path.mkdir(parents=True, exist_ok=True)
            source = (tmp_path / "malformed-calculation-summary.pdf").resolve()
            source_bytes = b"synthetic malformed calculation summary PDF"
            source.write_bytes(source_bytes)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "source_path": str(source),
                "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            }
        case "modelo.export":
            # A DRAFT revision is not exportable. `_require_exportable_revision_state`
            # admits only SEALED states (VERIFICADO_COMPLETO, PRESENTADO,
            # PRESENTADO_SUPERSEDIDO), because a fichero is a filing-grade
            # artefact and a return still being edited has no business becoming
            # one. So this seeds through verification rather than calculation.
            revision_id, _report_id = modelo_operation_test_support.seeded_modelo_verification_report(
                profile_id, operation=operation
            )
            export_revision = CalculationRevisionCatalogueRepository().load(operation=operation).get(revision_id)
            assert export_revision is not None
            subject_ref = export_revision.work_unit_id
            values = {
                "calculation_revision_id": revision_id,
                "output_path": str(tmp_path / "modelo-130-2025-1T.txt"),
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.edit.apply":
            work_unit_id, wire_submission = seeded_modelo_edit_submission(profile_id, operation=operation)
            subject_ref = work_unit_id
            return subject_ref, ModeloEditOperatorInputV2(submission=wire_submission), None
        case "modelo.work.file":
            revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
                profile_id, operation=operation
            )
            revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
            assert revision is not None
            subject_ref = revision.work_unit_id
            values = {
                "approval": {
                    "calculation_revision_id": revision_id,
                    "verification_report_id": report_id,
                },
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.amend":
            filing_record_id, casilla_id = _seeded_modelo_filing_record(profile_id, operation=operation)
            # The subject is the work unit that owns the filed record: the
            # access resolver reads that unit from the stored filing and
            # refuses any other subject.
            filed = ModeloRecordCatalogueRepository().load().get(filing_record_id)
            assert filed is not None
            subject_ref = filed.work_unit_id
            values = {
                "baseline": {"from_filing_record_id": filing_record_id},
                # The request model is strict: the enum instance and a tuple,
                # not their loose equivalents. A `.value` string and a list both
                # round-trip through JSON but are refused at the boundary, which
                # is the point of declaring the schema strict.
                "amendment_kind": CalculationRevisionAmendmentKind.COMPLEMENTARIA,
                "overrides": ({"casilla_id": casilla_id, "value": "150.00"},),
                "reason": "corrected the declared base for the conformance matrix",
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.calculate":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "work_unit_id": unit.work_unit_id,
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.wizard_attempt":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "profile_id": profile_id,
                "output_language": OutputLanguage.ES,
                "calculation": ModeloWorkCalculateRequest(
                    work_unit_id=unit.work_unit_id,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
            }
        case "modelo.work.verify":
            revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
                profile_id, operation=operation
            )
            revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
            assert revision is not None
            subject_ref = revision.work_unit_id
            values = {
                "calculation_revision_id": revision_id,
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.discard":
            # The baseline is the operator's EXACT APPROVAL, so it carries the
            # unit's state as observed rather than as re-read: name and
            # updated_at come off the seeded unit itself. A baseline resolved
            # inside the executor would match by construction and the
            # compare-and-swap this operation declares would never refuse.
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "baseline": {
                    "work_unit_id": unit.work_unit_id,
                    "name": unit.name,
                    "observed_updated_at": unit.updated_at,
                },
                "reason": "discarded by the registered-executor conformance matrix",
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case _:  # pragma: no cover - the coverage census names any definition missing a scenario.
            raise AssertionError(f"no conformance scenario for {definition.definition_id}")
    return subject_ref, definition.request_type.model_validate(values, strict=True), secret
