"""The adapter composition shared by the CLI and TUI entrypoints.

A frontend process must bind the persistence and outbound adapters the
application layer resolves through explicitly composed ports before it serves
any work. That inventory is a property of the product, not of the frontend, so
it is declared once here and entered by the CLI root and the TUI devtools
fixture. The separately shipped MCP harness owns its independent composition
root and does not import this entrypoint module.

An entrypoint that forgets this scope fails on every custody-touching verb,
which is exactly the symptom that made the original MCP gap visible.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..application.auth.apoderado_repository import ApoderadoConfigurationRepositoryFactory
    from ..application.auth.certificate_secret_backend import CertificateSecretBackendFactory
    from ..application.auth.operator_probe_ports import OperatorProbePorts
    from ..application.auth.operator_scope_ports import OperatorScopePorts
    from ..application.modelo.calculation_action_ports import CalculationActionPorts, CalculationActionPortsFactory
    from ..application.modelo.amendment_action_ports import AmendmentActionPorts, AmendmentActionPortsFactory
    from ..application.modelo.filing_action_ports import FilingActionPorts, FilingActionPortsFactory
    from ..application.modelo.export_ports import ModeloExportPorts, ModeloExportPortsFactory
    from ..application.modelo.history_ports import ModeloHistoryPorts, ModeloHistoryPortsFactory
    from ..application.live.expedientes_ports import ExpedientesPorts, ExpedientesPortsFactory
    from ..application.ledger.evidence_ports import LedgerEvidencePorts, LedgerEvidencePortsFactory
    from ..application.modelo.recipient_encryption import RecipientEncryptionCapabilityFactory
    from ..application.modelo.verification_repository_ports import (
        VerificationRepositoryBundleFactory,
    )
    from ..application.state_projection_ports import StateProjectionReadPorts
    from ..domain.calculations.registry.tax_id_format import SubjectTaxId


@dataclass(frozen=True, slots=True)
class ProfileAdapterComposition:
    """Concrete capabilities composed for one executable profile session."""

    state_projection_read_ports: StateProjectionReadPorts
    certificate_secret_backend_factory: CertificateSecretBackendFactory
    operator_probe_ports: OperatorProbePorts
    operator_scope_ports: OperatorScopePorts
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory
    calculation_action_ports_factory: CalculationActionPortsFactory
    amendment_action_ports_factory: AmendmentActionPortsFactory
    filing_action_ports_factory: FilingActionPortsFactory
    expedientes_ports_factory: ExpedientesPortsFactory
    ledger_evidence_ports_factory: LedgerEvidencePortsFactory
    modelo_export_ports_factory: ModeloExportPortsFactory
    modelo_history_ports_factory: ModeloHistoryPortsFactory
    recipient_encryption_capability_factory: RecipientEncryptionCapabilityFactory
    apoderado_config_repository_factory: ApoderadoConfigurationRepositoryFactory


def build_modelo_export_ports(
    *,
    bucket_id: str,
    m303_rectificativa_taxpayer_tax_id: SubjectTaxId,
) -> ModeloExportPorts:
    """Compose every persisted authority required by one Modelo export."""
    from ..adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )

    from ..application.modelo.export_ports import ModeloExportPorts

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return ModeloExportPorts(
        calculation=CalculationRevisionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
            m303_rectificativa_taxpayer_tax_id=m303_rectificativa_taxpayer_tax_id,
        ),
        work_unit=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        filing=ModeloRecordCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        verification=VerificationReportCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        bucket_event=BucketEventHistoryRepository(objects=objects),
        observation=CalculationObservationRepository(objects=objects),
        iva_compensation_decision=IvaWalletDecisionRepository(objects=objects),
        justificante=JustificanteRepository(objects=objects),
        prorrata_register=ProrrataRegisterRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        bienes_inversion=BienesInversionIvaRegisterRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        transaction=TransactionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
    )


def build_modelo_history_ports(*, bucket_id: str) -> ModeloHistoryPorts:
    """Compose every persisted authority required by Modelo history reads."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.history_ports import ModeloHistoryPorts

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return ModeloHistoryPorts(
        work_unit_repository=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        calculation_repository=CalculationRevisionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        filing_repository=ModeloRecordCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        verification_repository=VerificationReportCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def build_calculation_action_ports(*, bucket_id: str) -> CalculationActionPorts:
    """Compose every persisted authority required by one Modelo calculation."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_revision_override_migration import (
        migrate_stored_relation_overrides_to_binding_ids,
    )
    from ..adapters.persistence.profile.inventory import InventoryLedgerRepository
    from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..application.live.borrador_100 import Borrador100SnapshotRepository
    from ..application.modelo.calculation_action_ports import CalculationActionPorts

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)

    class RelationOverrideMigration:
        """Adapt the existing migration implementation to the application port."""

        def migrate(self, repository: object) -> None:
            migrate_stored_relation_overrides_to_binding_ids(repository)

    return CalculationActionPorts(
        work_unit_repository=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        calculation_repository=CalculationRevisionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        invoice_repository=InvoiceCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        filing_repository=ModeloRecordCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        inventory_repository=InventoryLedgerRepository(objects=objects),
        observation_repository=CalculationObservationRepository(objects=objects),
        iva_compensation_decision_repository=IvaWalletDecisionRepository(objects=objects),
        borrador_snapshot_repository=Borrador100SnapshotRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        relation_override_migration=RelationOverrideMigration(),
    )


def build_amendment_action_ports(*, bucket_id: str) -> AmendmentActionPorts:
    """Compose every persisted authority required by one Modelo amendment."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.amendment_action_ports import AmendmentActionPorts
    from ..application.modelo.profile_export_binding import resolve_export_identity

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    export_identity = resolve_export_identity(bucket_id=normalized_bucket_id)
    taxpayer_tax_id = export_identity[0].tax_id if export_identity is not None else None
    return AmendmentActionPorts(
        work_unit_repository=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        calculation_repository=CalculationRevisionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
            m303_rectificativa_taxpayer_tax_id=taxpayer_tax_id,
        ),
        filing_repository=ModeloRecordCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        justificante_repository=JustificanteRepository(objects=objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
    )


def build_filing_action_ports(*, bucket_id: str) -> FilingActionPorts:
    """Compose every persisted authority required by one Modelo filing."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.filing_action_ports import FilingActionPorts
    from ..application.workflow.persistence import WorkflowRunRepository

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return FilingActionPorts(
        work_unit_repository=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        calculation_repository=CalculationRevisionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        filing_repository=ModeloRecordCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        verification_repository=VerificationReportCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        observation_repository=CalculationObservationRepository(objects=objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        iva_compensation_decision_repository=IvaWalletDecisionRepository(objects=objects),
        workflow_run_repository=WorkflowRunRepository(objects=objects),
    )


def build_ledger_evidence_ports(*, bucket_id: str) -> LedgerEvidencePorts:
    """Compose the encrypted catalogue, attachment custody, and event sink."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.purchase_invoice_evidence import (
        LedgerEvidenceAttachmentIngestor,
        LedgerEvidenceRepositoryAdapter,
    )
    from ..adapters.persistence.storage.attachment import AttachmentStore
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.ledger.evidence_ports import LedgerEvidencePorts

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return LedgerEvidencePorts(
        evidence_repository=LedgerEvidenceRepositoryAdapter(objects=objects),
        attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=AttachmentStore(objects=objects)),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def build_expedientes_ports(*, bucket_id: str) -> ExpedientesPorts:
    """Compose translated Sede reading and encrypted expedientes persistence."""
    from ..adapters.outbound.aeat.sede.declarations import open_declarations_register, shared_playwright
    from ..adapters.persistence.profile.snapshots import SecureSnapshotRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..adapters.persistence.storage.secure_object_namespaces import LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE
    from ..application.live.expedientes import (
        ExpedientesSnapshotNotFoundError,
        PersistedExpedientesSnapshot,
        expedientes_snapshot_object_key,
    )
    from ..application.live.expedientes_ports import (
        ExpedientesDeclaration,
        ExpedientesDeclarationReaderProtocol,
        ExpedientesPorts,
        ExpedientesRegisterProtocol,
    )
    from ..application.live.errors import LiveApplicationError, LiveApplicationInputError
    from ..core.config import Settings

    def snapshot_repository_factory(bucket: str) -> SecureSnapshotRepository[PersistedExpedientesSnapshot]:
        """Bind one encrypted snapshot repository to the requested bucket."""
        normalized = bucket.strip()
        return SecureSnapshotRepository(
            bucket_id=normalized,
            payload_model=PersistedExpedientesSnapshot,
            namespace_definition=LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE,
            object_key=expedientes_snapshot_object_key,
            not_found_factory=lambda snapshot_id: ExpedientesSnapshotNotFoundError(
                translated_message="application.live.expedientes.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            ),
            ambiguous_prefix_factory=lambda snapshot_id, full_ids: ExpedientesSnapshotNotFoundError(
                translated_message="application.live.expedientes.errors.snapshot_prefix_ambiguous",
                context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
            ),
            domain_label="expedientes",
            input_error_cls=LiveApplicationInputError,
            objects=secure_object_repository_for_bucket(normalized),
        )

    def translate_declaration(row: object) -> ExpedientesDeclaration:
        """Translate the Sede row DTO before it enters application state."""
        try:
            return ExpedientesDeclaration(
                modelo=getattr(row, "modelo"),
                ejercicio=getattr(row, "ejercicio"),
                period=getattr(row, "period"),
                expediente_id=getattr(row, "expediente_id"),
                estado=getattr(row, "estado"),
                tipo_solicitud=getattr(row, "tipo_solicitud"),
                observaciones=getattr(row, "observaciones"),
                presented_at=getattr(row, "presented_at"),
                justificante_link_text=getattr(row, "justificante_link_text"),
                archive_link_text=getattr(row, "archive_link_text"),
                declaration_copy_link_text=getattr(row, "declaration_copy_link_text"),
                justificante_cell_index=getattr(row, "justificante_cell_index"),
                archive_cell_index=getattr(row, "archive_cell_index"),
                declaration_copy_cell_index=getattr(row, "declaration_copy_cell_index"),
                mode=getattr(row, "mode"),
            )
        except Exception as exc:
            raise LiveApplicationError(
                translated_message="errors.error.error_application_live",
                context={"surface": "expedientes", "stage": "declaration_translation"},
            ) from exc

    class SedeExpedientesRegister(ExpedientesRegisterProtocol):
        """Translate rows returned by the concrete Sede register session."""

        def __init__(self, register: object) -> None:
            self._register = register

        async def walk(self, *, modelo: str, ejercicio: int) -> tuple[ExpedientesDeclaration, ...]:
            try:
                rows = await getattr(self._register, "walk")(modelo=modelo, ejercicio=ejercicio)
                return tuple(translate_declaration(row) for row in rows)
            except LiveApplicationError:
                raise
            except Exception as exc:
                raise LiveApplicationError(
                    translated_message="errors.error.error_application_live",
                    context={"surface": "expedientes", "stage": "declaration_read"},
                ) from exc

    class SedeExpedientesDeclarationReader(ExpedientesDeclarationReaderProtocol):
        """Adapt the browser register lifecycle to the application port."""

        @asynccontextmanager
        async def open_register(self, session: object, *, settings: Settings):
            try:
                async with (
                    shared_playwright(session) as playwright,
                    open_declarations_register(session, settings=settings, playwright=playwright) as register,
                ):
                    yield SedeExpedientesRegister(register)
            except LiveApplicationError:
                raise
            except Exception as exc:
                raise LiveApplicationError(
                    translated_message="errors.error.error_application_live",
                    context={"surface": "expedientes", "stage": "register_open"},
                ) from exc

    return ExpedientesPorts(
        declaration_reader=SedeExpedientesDeclarationReader(),
        snapshot_repository_factory=snapshot_repository_factory,
    )


__all__ = [
    "ProfileAdapterComposition",
    "build_amendment_action_ports",
    "build_calculation_action_ports",
    "build_expedientes_ports",
    "build_filing_action_ports",
    "build_ledger_evidence_ports",
    "build_modelo_export_ports",
    "build_modelo_history_ports",
    "profile_adapter_composition",
]


@contextmanager
def profile_adapter_composition() -> Generator[ProfileAdapterComposition]:
    """Bind every adapter port a frontend session resolves, and unbind after.

    The imports are function-local because entering this scope is what pulls the
    adapter layer into the process: a frontend that never serves work should not
    pay for the persistence and outbound trees at import time.
    """
    from ..adapters.inbound.reconciliation_parser import InboundReconciliationEvidenceParser
    from ..adapters.outbound.aeat.auth.certificate import CertificateHealthProbeAdapter
    from ..adapters.outbound.aeat.auth.clave_movil_support import ClaveIdentityProbeAdapter
    from ..adapters.outbound.aeat.auth.provider_selection import select_provider as select_outbound_auth_provider
    from ..adapters.outbound.aeat.auth.session_store import build_session_store
    from ..adapters.outbound.llm.column_role_mapping import resolve_column_roles as resolve_outbound_column_roles
    from ..adapters.persistence.profile.apoderado import build_apoderado_config_repository
    from ..adapters.persistence.profile.buckets import (
        BucketEventHistoryRepository,
        build_bucket_event_history_repository,
    )
    from ..adapters.persistence.profile.confirmation_records import ConfirmationRecordRepository
    from ..adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
    from ..adapters.persistence.profile.modelo_reconciliation import build_modelo_reconciliation_persistence
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from ..adapters.persistence.profile.review_package_recipient_encryption import (
        build_recipient_encryption_capability,
    )
    from ..adapters.persistence.profile.state_projection import StateProjectionPersistenceAdapter
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.profile.usage_ratios import (
        load_usage_ratios,
        load_usage_ratios_with_censo_guard,
        save_usage_ratios,
    )
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..adapters.persistence.storage.master_key.active_session import ActiveProfileSessionPresenceAdapter
    from ..adapters.persistence.storage.profile_custody import build_profile_custody_port
    from ..adapters.persistence.storage.profile_login_session import build_profile_login_session_port
    from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..adapters.persistence.workflow import build_workflow_persistence_port
    from ..application.auth.operator_probe_ports import OperatorProbePorts
    from ..application.auth.protocols import bind_session_store
    from ..application.auth.providers import bind_auth_provider_selector
    from ..application.bucket_event_repository import bind_bucket_event_history_repository_factory
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..application.ledger.column_roles import bind_column_role_mapping_resolver
    from ..application.ledger.confirmation_record import bind_confirmation_record_repository_factory
    from ..application.ledger.extraction_draft_store import bind_extraction_draft_repository_factory
    from ..application.ledger.participation_read import bind_transaction_participation_index_repository_factory
    from ..application.ledger.rule_repository import bind_ledger_classification_rule_repository_factory
    from ..application.ledger.transaction_repository import bind_transaction_catalogue_repository_factory
    from ..application.ledger.usage_ratio_repository import (
        bind_usage_ratio_censo_guard_loader,
        bind_usage_ratio_profile_persistence,
    )
    from ..application.modelo.calculation_repository import bind_calculation_revision_catalogue_repository_factory
    from ..application.modelo.filing_repository import bind_modelo_record_catalogue_repository_factory
    from ..application.modelo.justificante_repository import bind_justificante_repository_factory
    from ..application.modelo.reconciliation_parsing import bind_reconciliation_evidence_parser
    from ..application.modelo.reconciliation_records import bind_modelo_reconciliation_persistence_factory
    from ..application.modelo.verification_repository_ports import VerificationRepositoryBundle
    from ..application.modelo.work_unit_repository import bind_work_unit_catalogue_repository_factory
    from ..application.state_projection_ports import StateProjectionReadPorts
    from ..application.user_profile.custody_ports import bind_profile_custody_port
    from ..application.user_profile.language_resolver import register_language_resolver
    from ..application.user_profile.login_session_port import bind_profile_login_session_port
    from ..application.workflow.persistence import WorkflowRunRepository, bind_workflow_persistence_port

    projection_adapter = StateProjectionPersistenceAdapter()
    projection_ports = StateProjectionReadPorts(
        workspace=projection_adapter,
        profile=projection_adapter,
    )

    def build_verification_repository_bundle(bucket_id: str) -> VerificationRepositoryBundle:
        """Compose every verification repository against one bucket store."""
        normalized_bucket_id = bucket_id.strip()
        objects = secure_object_repository_for_bucket(normalized_bucket_id)
        return VerificationRepositoryBundle(
            calculation=CalculationRevisionCatalogueRepository(
                bucket_id=normalized_bucket_id,
                objects=objects,
            ),
            work_unit=WorkUnitCatalogueRepository(
                bucket_id=normalized_bucket_id,
                objects=objects,
            ),
            filing=ModeloRecordCatalogueRepository(
                bucket_id=normalized_bucket_id,
                objects=objects,
            ),
            transaction=TransactionCatalogueRepository(
                bucket_id=normalized_bucket_id,
                objects=objects,
            ),
            verification=VerificationReportCatalogueRepository(
                bucket_id=normalized_bucket_id,
                objects=objects,
            ),
            bucket_event=BucketEventHistoryRepository(objects=objects),
            observation=CalculationObservationRepository(objects=objects),
            iva_compensation_decision=IvaWalletDecisionRepository(objects=objects),
            participation_index=TransactionParticipationIndexRepository(
                bucket_id=normalized_bucket_id,
                objects=objects,
            ),
            workflow_run=WorkflowRunRepository(objects=objects),
        )

    with ExitStack() as composition:
        composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
        composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
        composition.enter_context(bind_workflow_persistence_port(build_workflow_persistence_port()))
        composition.enter_context(bind_bucket_event_history_repository_factory(build_bucket_event_history_repository))
        composition.enter_context(bind_confirmation_record_repository_factory(ConfirmationRecordRepository))
        composition.enter_context(bind_column_role_mapping_resolver(resolve_outbound_column_roles))
        composition.enter_context(bind_extraction_draft_repository_factory(ExtractionDraftRepository))
        composition.enter_context(
            bind_transaction_participation_index_repository_factory(TransactionParticipationIndexRepository)
        )
        composition.enter_context(
            bind_ledger_classification_rule_repository_factory(LedgerClassificationRuleRepository)
        )
        composition.enter_context(bind_transaction_catalogue_repository_factory(TransactionCatalogueRepository))
        composition.enter_context(
            bind_usage_ratio_profile_persistence(loader=load_usage_ratios, saver=save_usage_ratios)
        )
        composition.enter_context(bind_usage_ratio_censo_guard_loader(load_usage_ratios_with_censo_guard))
        composition.enter_context(
            bind_calculation_revision_catalogue_repository_factory(CalculationRevisionCatalogueRepository)
        )
        composition.enter_context(bind_modelo_record_catalogue_repository_factory(ModeloRecordCatalogueRepository))
        composition.enter_context(bind_justificante_repository_factory(JustificanteRepository))
        composition.enter_context(bind_work_unit_catalogue_repository_factory(WorkUnitCatalogueRepository))
        composition.enter_context(bind_reconciliation_evidence_parser(InboundReconciliationEvidenceParser()))
        composition.enter_context(
            bind_modelo_reconciliation_persistence_factory(build_modelo_reconciliation_persistence)
        )
        composition.enter_context(bind_auth_provider_selector(select_outbound_auth_provider))
        composition.enter_context(bind_session_store(build_session_store()))
        register_language_resolver()
        yield ProfileAdapterComposition(
            state_projection_read_ports=projection_ports,
            certificate_secret_backend_factory=build_certificate_secret_backend,
            operator_probe_ports=OperatorProbePorts(
                active_profile_session=ActiveProfileSessionPresenceAdapter(),
                certificate_health=CertificateHealthProbeAdapter(),
                clave_identity=ClaveIdentityProbeAdapter(),
            ),
            operator_scope_ports=build_operator_scope_ports(),
            verification_repository_bundle_factory=build_verification_repository_bundle,
            calculation_action_ports_factory=build_calculation_action_ports,
            amendment_action_ports_factory=build_amendment_action_ports,
            filing_action_ports_factory=build_filing_action_ports,
            expedientes_ports_factory=build_expedientes_ports,
            ledger_evidence_ports_factory=build_ledger_evidence_ports,
            modelo_export_ports_factory=build_modelo_export_ports,
            modelo_history_ports_factory=build_modelo_history_ports,
            recipient_encryption_capability_factory=build_recipient_encryption_capability,
            apoderado_config_repository_factory=build_apoderado_config_repository,
        )
