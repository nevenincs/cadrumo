"""The adapter composition shared by the CLI and TUI entrypoints.

A frontend process must bind the persistence and outbound adapters the
application layer resolves through explicitly composed ports before it serves
any work. That inventory is a property of the product, not of the frontend, so
it is declared once here and entered by the CLI root and the TUI devtools
fixture. The separately shipped external client distribution owns its independent
composition root and does not import this entrypoint module.

An entrypoint that forgets this scope fails on every custody-touching verb,
which is exactly the symptom that made the original external client gap visible.

Core types:
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`,
:class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from decimal import Decimal

    from ..adapters.outbound.aeat.sede.declarations import DeclaracionesRegisterSession
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.confirmation_records import ConfirmationRecordRepository
    from ..adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
    from ..application.aggregation.ledger_membership import LedgerMembershipPorts
    from ..application.auth.session_types import AeatSession
    from ..application.diagnostics_ports import DiagnosticsPorts
    from ..application.ledger.column_roles import ColumnRoleMappingPort, ColumnRoleReaderUnavailable
    from ..application.ledger.evidence_ports import LedgerEvidencePorts
    from ..application.ledger.statement_reading import StatementReaderPort
    from ..application.live.expedientes_ports import ExpedientesPorts
    from ..application.modelo.amendment_action_ports import AmendmentActionPorts
    from ..application.modelo.calculation_action_ports import CalculationActionPorts
    from ..application.modelo.filing_action_ports import FilingActionPorts
    from ..application.modelo.reconciliation_records import ModeloReconciliationPersistencePort
    from ..application.modelo.verification_repository_ports import (
        VerificationRepositoryBundle,
    )
    from ..application.modelo.work_lifecycle_ports import WorkLifecyclePorts
    from ..application.state_projection_ports import StateProjectionReadPorts
    from ..core.config import Settings
    from ..core.tabular import NormalizedTable
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..domain.calculations.registry.tax_id_format import SubjectTaxId
    from ..domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
    from ..domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
    from ..domain.usage_ratios.model import UsageRatioProfile


from .adapter_composition_ports import (
    build_borrador_100_snapshot_repository,
    build_diagnostics_ports,
    build_draft_review_ports,
    build_pinned_profile_read_ports,
    build_retencion_observation_ports,
)


def build_state_projection_read_ports(
    *,
    operation: PinnedAuthorityOperation | None,
    diagnostics_ports: DiagnosticsPorts | None = None,
    objects: SecureObjectRepository | None = None,
    bucket_id: str | None = None,
) -> StateProjectionReadPorts:
    """Compose the state-projection read ports over the persistence adapters.

    Module-level so a caller that is not holding a
    :class:`ProfileAdapterComposition` -- the TUI's own workspace admission,
    for one -- reaches the same composition rather than assembling a second
    one from the same adapters.

    Parameter types: ``objects``
    (:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`).
    """
    from ..adapters.persistence.profile.state_projection import StateProjectionPersistenceAdapter
    from ..adapters.persistence.profile.usage_ratios import load_usage_ratios
    from ..application.state_projection_ports import StateProjectionReadPorts
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    taxpayer_tax_id: SubjectTaxId | None = None
    if operation is not None:
        if objects is None or bucket_id is None:
            raise ValueError("a bound state projection needs its profile, repository and retained authority together")
        calculation_binding = bind_calculation_revision_persistence_from_profile(
            bucket_id=bucket_id,
            objects=objects,
            operation=operation,
        )
        taxpayer_tax_id = calculation_binding.taxpayer_tax_id

    projection_adapter = StateProjectionPersistenceAdapter(
        diagnostics_ports=diagnostics_ports or build_diagnostics_ports(bucket_id=bucket_id),
        operation=operation,
        objects=objects,
        bucket_id=bucket_id,
        m303_rectificativa_taxpayer_tax_id=taxpayer_tax_id,
    )
    return StateProjectionReadPorts(
        workspace=projection_adapter,
        profile=projection_adapter,
        usage_ratio_profile_loader=load_usage_ratios,
    )


def build_calculation_action_ports(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile_record: object | None = None,
    objects: SecureObjectRepository | None = None,
) -> CalculationActionPorts:
    """Compose every persisted authority required by one Modelo calculation.

    Parameter types: ``objects``
    (:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`).
    """
    from ..adapters.persistence.profile.actividad_asset import ActividadAssetHistoryRepository
    from ..adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..adapters.persistence.profile.calculation_revision_override_migration import (
        migrate_stored_relation_overrides_to_binding_ids,
    )
    from ..adapters.persistence.profile.catalogue_reads import build_invoice_catalogue_read_ports
    from ..adapters.persistence.profile.foreign_assets import ForeignAssetRegisterRepository
    from ..adapters.persistence.profile.inventory import InventoryLedgerRepository
    from ..adapters.persistence.profile.invoice_source_resolver import InvoiceCatalogueSourceResolverAdapter
    from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ..adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
    from ..adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.profile.usage_ratios import load_usage_ratios
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.aggregation.percepciones_observations_repository import PercepcionObservationPorts
    from ..application.invoices.source_resolver_ports import InvoiceSourceResolverPorts
    from ..application.modelo.calculation_action_ports import CalculationActionPorts
    from ..application.modelo.work_lifecycle_ports import WorkLifecyclePorts
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    normalized_bucket_id = bucket_id.strip()
    objects = objects if objects is not None else secure_object_repository_for_bucket(normalized_bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=normalized_bucket_id,
        objects=objects,
        operation=operation,
        profile_record=profile_record,
    )

    class RelationOverrideMigration:
        """Adapt the existing migration implementation to the application port."""

        def migrate(
            self,
            repository: CalculationRevisionCatalogueRepositoryProtocol,
            *,
            operation: PinnedAuthorityOperation,
        ) -> None:
            migrate_stored_relation_overrides_to_binding_ids(repository, operation=operation)

    invoice_repository = InvoiceCatalogueRepository(
        bucket_id=normalized_bucket_id,
        objects=objects,
    )
    work_unit_repository = WorkUnitCatalogueRepository(
        bucket_id=normalized_bucket_id,
        objects=objects,
    )
    bucket_event_repository = BucketEventHistoryRepository(objects=objects)
    bienes_inversion_repository = BienesInversionIvaRegisterRepository(
        bucket_id=normalized_bucket_id,
        objects=objects,
    )

    return CalculationActionPorts(
        operation=operation,
        work_unit_repository=work_unit_repository,
        work_lifecycle_ports=WorkLifecyclePorts(
            work_unit_repository=work_unit_repository,
            bucket_event_repository=bucket_event_repository,
        ),
        calculation_repository=calculation_binding.calculation_repository(),
        bucket_event_repository=bucket_event_repository,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        activity_asset_history_repository=ActividadAssetHistoryRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        usage_ratio_profile_loader=load_usage_ratios,
        profile_read_ports=build_pinned_profile_read_ports(bucket_id=normalized_bucket_id, operation=operation),
        invoice_repository=invoice_repository,
        invoice_catalogue_read_ports=build_invoice_catalogue_read_ports(
            bucket_id=normalized_bucket_id, objects=objects
        ),
        invoice_source_ports=InvoiceSourceResolverPorts(
            catalogue_reader=InvoiceCatalogueSourceResolverAdapter(
                repository=invoice_repository,
            ),
        ),
        filing_repository=ModeloRecordCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        bienes_inversion_repository=bienes_inversion_repository,
        foreign_asset_register_repository=ForeignAssetRegisterRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        inventory_repository=InventoryLedgerRepository(objects=objects),
        observation_repository=CalculationObservationRepository(objects=objects),
        percepciones_observation_ports=PercepcionObservationPorts(
            repository=PercepcionObservationRepositoryAdapter(objects=objects),
        ),
        iva_compensation_history_repository=IvaCompensationHistoryRepository(objects=objects),
        iva_compensation_decision_repository=IvaWalletDecisionRepository(objects=objects, operation=operation),
        borrador_snapshot_repository=build_borrador_100_snapshot_repository(
            bucket_id=normalized_bucket_id, objects=objects
        ),
        retencion_observation_ports=build_retencion_observation_ports(bucket_id=normalized_bucket_id, objects=objects),
        relation_override_migration=RelationOverrideMigration(),
    )


def build_work_lifecycle_ports(*, bucket_id: str) -> WorkLifecyclePorts:
    """Compose the two required Modelo work-lifecycle authorities."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.work_lifecycle_ports import WorkLifecyclePorts

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return WorkLifecyclePorts(
        work_unit_repository=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def build_active_work_lifecycle_ports() -> WorkLifecyclePorts:
    """Compose lifecycle authorities for the active profile operation scope."""
    from ..core.bucket_pointer import require_active_bucket_id

    return build_work_lifecycle_ports(bucket_id=require_active_bucket_id())


def build_amendment_action_ports(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> AmendmentActionPorts:
    """Compose every persisted authority required by one Modelo amendment."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import CalculationObservationRepository
    from ..adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.amendment_action_ports import AmendmentActionPorts
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=normalized_bucket_id,
        objects=objects,
        operation=operation,
    )
    return AmendmentActionPorts(
        work_unit_repository=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        calculation_repository=calculation_binding.calculation_repository(),
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
        observation_repository=CalculationObservationRepository(bucket_id=normalized_bucket_id, objects=objects),
        iva_compensation_history_repository=IvaCompensationHistoryRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
    )


def build_filing_action_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> FilingActionPorts:
    """Compose every persisted authority required by one Modelo filing."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from ..adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ..adapters.persistence.profile.workflow_gate import build_workflow_gate_ports
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.filing_action_ports import FilingActionPorts
    from ..application.workflow.persistence import WorkflowRunRepository
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=normalized_bucket_id,
        objects=objects,
        operation=operation,
    )
    return FilingActionPorts(
        work_unit_repository=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        calculation_repository=calculation_binding.calculation_repository(),
        filing_repository=ModeloRecordCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        verification_repository=calculation_binding.verification_repository(),
        justificante_repository=JustificanteRepository(objects=objects),
        observation_repository=CalculationObservationRepository(objects=objects),
        participation_index_repository=TransactionParticipationIndexRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        iva_compensation_history_repository=IvaCompensationHistoryRepository(objects=objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        iva_compensation_decision_repository=IvaWalletDecisionRepository(objects=objects, operation=operation),
        workflow_run_repository=WorkflowRunRepository(objects=objects),
        draft_review_ports=build_draft_review_ports(
            bucket_id=normalized_bucket_id, operation=operation, objects=objects
        ),
        workflow_gate_ports=build_workflow_gate_ports(bucket_id=normalized_bucket_id),
        retencion_observation_ports=build_retencion_observation_ports(bucket_id=normalized_bucket_id),
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
    from ..application.live.errors import LiveApplicationError, LiveApplicationInputError
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
    from ..application.user_profile.access_errors import ProfileAccessRefusedError

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

    class SedeExpedientesRegister(ExpedientesRegisterProtocol):
        """Expose the concrete Sede register session, which yields application rows."""

        def __init__(self, register: DeclaracionesRegisterSession) -> None:
            self._register = register

        @override
        async def walk(self, *, modelo: str, ejercicio: int) -> tuple[ExpedientesDeclaration, ...]:
            try:
                return await self._register.walk(modelo=modelo, ejercicio=ejercicio)
            except (LiveApplicationError, ProfileAccessRefusedError):
                raise
            except Exception as exc:
                raise LiveApplicationError(
                    translated_message="errors.error.error_application_live",
                    context={"surface": "expedientes", "stage": "declaration_read"},
                ) from exc

    class SedeExpedientesDeclarationReader(ExpedientesDeclarationReaderProtocol):
        """Adapt the browser register lifecycle to the application port."""

        @asynccontextmanager
        @override
        async def open_register(
            self, session: AeatSession, *, settings: Settings, authority_operation: PinnedAuthorityOperation
        ):
            try:
                async with (
                    shared_playwright(session) as playwright,
                    open_declarations_register(
                        session,
                        operation=authority_operation,
                        settings=settings,
                        playwright=playwright,
                    ) as register,
                ):
                    yield SedeExpedientesRegister(register)
            except (LiveApplicationError, ProfileAccessRefusedError):
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


def build_ledger_membership_ports(
    *,
    bucket_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    objects: SecureObjectRepository | None = None,
) -> LedgerMembershipPorts:
    """Compose read-only source admission capabilities over the verification bucket.

    Parameter types: ``objects``
    (:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`).
    """
    from ..adapters.persistence.profile.actividad_asset import ActividadAssetHistoryRepository
    from ..adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
    from ..adapters.persistence.profile.catalogue_reads import build_invoice_catalogue_read_ports
    from ..adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ..adapters.persistence.profile.usage_ratios import load_usage_ratios
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.aggregation.ledger_membership import LedgerMembershipPorts

    normalized_bucket_id = bucket_id.strip()
    objects = objects if objects is not None else secure_object_repository_for_bucket(normalized_bucket_id)
    return LedgerMembershipPorts(
        transaction_repository=transaction_repository,
        invoice_catalogue_read_ports=build_invoice_catalogue_read_ports(bucket_id=normalized_bucket_id),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=normalized_bucket_id, objects=objects),
        bienes_inversion_repository=BienesInversionIvaRegisterRepository(
            bucket_id=normalized_bucket_id, objects=objects
        ),
        activity_asset_history_repository=ActividadAssetHistoryRepository(
            bucket_id=normalized_bucket_id, objects=objects
        ),
        usage_ratio_profile_loader=load_usage_ratios,
    )


def build_verification_repository_bundle(
    bucket_id: str, *, operation: PinnedAuthorityOperation, objects: SecureObjectRepository | None = None
) -> VerificationRepositoryBundle:
    """Bind one profile's repositories and rectificativa identity to the held authority.

    Parameter types: ``objects``
    (:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`).
    """
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.profile.workflow_gate import build_workflow_gate_ports
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.verification_repository_ports import VerificationRepositoryBundle
    from ..application.workflow.persistence import WorkflowRunRepository
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    normalized_bucket_id = bucket_id.strip()
    objects = objects if objects is not None else secure_object_repository_for_bucket(normalized_bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=normalized_bucket_id,
        objects=objects,
        operation=operation,
    )
    transaction_repository = TransactionCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects)
    return VerificationRepositoryBundle(
        calculation=calculation_binding.calculation_repository(),
        work_unit=WorkUnitCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects),
        filing=ModeloRecordCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects),
        transaction=transaction_repository,
        verification=calculation_binding.verification_repository(),
        bucket_event=BucketEventHistoryRepository(objects=objects),
        observation=CalculationObservationRepository(objects=objects),
        iva_compensation_history=IvaCompensationHistoryRepository(objects=objects),
        iva_compensation_decision=IvaWalletDecisionRepository(objects=objects, operation=operation),
        participation_index=TransactionParticipationIndexRepository(bucket_id=normalized_bucket_id, objects=objects),
        workflow_run=WorkflowRunRepository(objects=objects),
        justificante=JustificanteRepository(objects=objects),
        draft_review_ports=build_draft_review_ports(
            bucket_id=normalized_bucket_id, operation=operation, objects=objects
        ),
        workflow_gate_ports=build_workflow_gate_ports(bucket_id=normalized_bucket_id, objects=objects),
        retencion_observation_ports=build_retencion_observation_ports(bucket_id=normalized_bucket_id, objects=objects),
        ledger_membership_ports=build_ledger_membership_ports(
            bucket_id=normalized_bucket_id, transaction_repository=transaction_repository, objects=objects
        ),
    )


def bucket_event_history_repository(*, bucket_id: str) -> BucketEventHistoryRepository:
    """Compose bucket event history repository for the operation scope."""
    from ..adapters.persistence.profile.buckets import build_bucket_event_history_repository

    return build_bucket_event_history_repository(bucket_id=bucket_id)


def load_usage_ratios(*, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
    """Compose load usage ratios for the operation scope."""
    from ..adapters.persistence.profile.usage_ratios import load_usage_ratios

    return load_usage_ratios(bucket_id=bucket_id, operation=operation)


def save_usage_ratios(profile: UsageRatioProfile, *, bucket_id: str) -> None:
    """Compose save usage ratios for the operation scope."""
    from ..adapters.persistence.profile.usage_ratios import save_usage_ratios

    save_usage_ratios(profile, bucket_id=bucket_id)


def load_usage_ratios_with_censo_guard(
    *,
    bucket_id: str,
    raw_afectacion_ratio: Decimal | None,
    year: int,
    operation: PinnedAuthorityOperation,
) -> UsageRatioProfile:
    """Compose load usage ratios with censo guard for the operation scope."""
    from ..adapters.persistence.profile.usage_ratios import load_usage_ratios_with_censo_guard

    return load_usage_ratios_with_censo_guard(
        bucket_id=bucket_id,
        raw_afectacion_ratio=raw_afectacion_ratio,
        year=year,
        operation=operation,
    )


def confirmation_record_repository(*, bucket_id: str, settings: Settings | None) -> ConfirmationRecordRepository:
    """Compose confirmation record repository for the operation scope."""
    from ..adapters.persistence.profile.confirmation_records import ConfirmationRecordRepository

    return ConfirmationRecordRepository(bucket_id=bucket_id, settings=settings)


def extraction_draft_repository(*, bucket_id: str, settings: Settings) -> ExtractionDraftRepository:
    """Compose extraction draft repository for the operation scope."""
    from ..adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository

    return ExtractionDraftRepository(bucket_id=bucket_id, settings=settings)


def transaction_participation_index_repository(
    *,
    bucket_id: str | None = None,
) -> TransactionParticipationIndexRepository:
    """Compose transaction participation index repository for the operation scope."""
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository

    return TransactionParticipationIndexRepository(bucket_id=bucket_id)


def ledger_classification_rule_repository(*, bucket_id: str) -> LedgerClassificationRuleRepository:
    """Compose ledger classification rule repository for the operation scope."""
    from ..adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository

    return LedgerClassificationRuleRepository(bucket_id=bucket_id)


def transaction_catalogue_repository(*, bucket_id: str) -> TransactionCatalogueRepository:
    """Compose transaction catalogue repository for the operation scope."""
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository

    return TransactionCatalogueRepository(bucket_id=bucket_id)


def calculation_revision_catalogue_repository(
    *, bucket_id: str, operation: PinnedAuthorityOperation | None
) -> CalculationRevisionCatalogueRepository:
    """Compose calculation revision catalogue repository for the operation scope."""
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    return bind_calculation_revision_persistence_from_profile(
        bucket_id=bucket_id,
        objects=secure_object_repository_for_bucket(bucket_id.strip()),
        operation=operation,
    ).calculation_repository()


def modelo_record_catalogue_repository(*, bucket_id: str) -> ModeloRecordCatalogueRepository:
    """Compose modelo record catalogue repository for the operation scope."""
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository

    return ModeloRecordCatalogueRepository(bucket_id=bucket_id)


def justificante_repository(*, bucket_id: str) -> JustificanteRepository:
    """Compose justificante repository for the operation scope."""
    from ..adapters.persistence.profile.justificante import JustificanteRepository

    return JustificanteRepository(bucket_id=bucket_id)


def work_unit_catalogue_repository(*, bucket_id: str) -> WorkUnitCatalogueRepository:
    """Compose work unit catalogue repository for the operation scope."""
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository

    return WorkUnitCatalogueRepository(bucket_id=bucket_id)


def modelo_reconciliation_persistence() -> ModeloReconciliationPersistencePort:
    """Compose modelo reconciliation persistence for the operation scope."""
    from ..adapters.persistence.profile.modelo_reconciliation import build_modelo_reconciliation_persistence

    return build_modelo_reconciliation_persistence()


def resolve_column_roles(table: NormalizedTable) -> ColumnRoleMappingPort | ColumnRoleReaderUnavailable | None:
    """Compose resolve column roles for the operation scope."""
    from ..adapters.outbound.llm import column_role_mapping

    return column_role_mapping.resolve_column_roles(table)


def statement_reader() -> StatementReaderPort:
    """Compose statement reader for the operation scope."""
    from ..adapters.outbound.llm.statement_reading import StatementReader

    return StatementReader()
