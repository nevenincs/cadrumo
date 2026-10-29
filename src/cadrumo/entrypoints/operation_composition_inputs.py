"""Sole production composition seam for the supervised operation platform.

Every registered operation is built by one named composition group, one per
owning operation module. A group imports its builders inside its own function,
so composing one group costs only that operation family's imports. The eager
production registry composes every group; the manifest-backed registry answers
contracts from the generated manifest and composes a group only when one of
its operations is used.

Core types: :class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cached_property, partial
from typing import TYPE_CHECKING
from uuid import UUID

from ..application.operations.contract_manifest import (
    OperationGroupBuild,
)
from ..application.operations.registry import OperationPublicContractSetV1
from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import InternalInvariantError

if TYPE_CHECKING:
    from ..adapters.persistence.profile.verify_observations import VerifyObservationRepository
    from ..application.auth.operation_definitions import AuthOperationPorts, ProfileRotationFinalizer
    from ..application.auth.operator_scope_ports import OperatorScopePorts
    from ..application.bucket_event_repository import BucketEventHistoryRepositoryFactory
    from ..application.connectivity_probe import ConnectivityProbePort
    from ..application.invoices.catalogue_creation_ports import CatalogueCreationPortsFactory
    from ..application.invoices.catalogue_lifecycle_ports import CatalogueLifecyclePortsFactory
    from ..application.invoices.inspection_read_ports import InvoiceInspectionReadPortsFactory
    from ..application.ledger.action_ports import LedgerActionPortsFactory
    from ..application.ledger.counterparty_establishment_ports import CounterpartyEstablishmentRepositoryFactory
    from ..application.ledger.evidence_followup_contracts import LedgerEvidenceFollowupOperationPorts
    from ..application.ledger.own_account_ports import OwnAccountRepositoryFactory
    from ..application.ledger.participation_read import TransactionParticipationIndexRepositoryFactory
    from ..application.ledger.read_ports import LedgerReadPortsFactory
    from ..application.ledger.rule_repository import LedgerClassificationRuleRepositoryFactory
    from ..application.live.notification_documents import NotificationDocumentService
    from ..application.live.notification_ports import NotificationsPorts
    from ..application.live.sede_view_ports import SedeViewStreamOpener
    from ..application.live.verify import VerifySurface
    from ..application.live.verify_capture_operation import VerifyLiveObservation
    from ..application.modelo.aggregate_ports import ModeloAggregateOperationPorts, ModeloAggregateOperationPortsFactory
    from ..application.modelo.amendment_action_ports import AmendmentActionPortsFactory
    from ..application.modelo.calculation_action_ports import CalculationActionPortsFactory
    from ..application.modelo.dependency_read_ports import DependencyReadPortsFactory
    from ..application.modelo.edit_receipt_ports import ModeloEditReceiptRepositoryFactory
    from ..application.modelo.edit_refusal_projection import ModeloEditRefusalProjectionStore
    from ..application.modelo.export_ports import ModeloExportPortsFactory
    from ..application.modelo.filing_action_ports import FilingActionPortsFactory
    from ..application.modelo.history_ports import ModeloHistoryPortsFactory
    from ..application.modelo.invoice_withholding_capture_contracts import (
        ModeloInvoiceWithholdingCapturePorts,
        ModeloInvoiceWithholdingCapturePortsFactory,
    )
    from ..application.modelo.operation_shared import ModeloWorkVerifyProfileResolver
    from ..application.modelo.participation_index_rebuild_ports import ParticipationIndexRebuildPortsFactory
    from ..application.modelo.query_read_contracts import ModeloQueryReadPortsFactory
    from ..application.modelo.review_package_recipient_registry_ports import RecipientFingerprintRegistryPortsFactory
    from ..application.modelo.verification_repository_ports import VerificationRepositoryBundleFactory
    from ..application.modelo.work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
    from ..application.modelo.workbench_read import ModeloWorkbenchReadPorts, ModeloWorkbenchReadPortsFactory
    from ..application.operations.execution_actor import OperationExecutionCallerReader
    from ..application.operations.operation_definition import OperationDefinition
    from ..application.operations.registry import OperationPublicDefinitionRegistrationV1
    from ..application.overview.pipeline_read_ports import PipelineReadPortsFactory
    from ..application.overview.read_ports import OverviewReadPortsFactory
    from ..application.user_profile.automation_operations import (
        AutomationAdministrationFactory,
        AutomationInventoryReader,
    )
    from ..application.user_profile.history_operation import ProfileHistoryReadPorts
    from ..application.workbench_generation_operation import WorkbenchGenerationReader
    from ..application.workflow.run_read_ports import WorkflowRunReadPortsFactory
    from ..core.identity_check_verdict import IdentityCheckVerdictValue
    from ..domain.attachments.protocols import AttachmentStoreProtocol
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..domain.deadlines.festivos import CalendarCCAA


def supplied[T](value: T | None, default: T) -> T:
    """Return the injected capability, else its production default."""
    return default if value is None else value


def build_profile_history_read_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ProfileHistoryReadPorts:
    """Bind canonical event history to the worker's exact profile and authority pin."""
    from ..adapters.persistence.profile.buckets import build_bucket_event_history_repository
    from ..application.user_profile.history_operation import ProfileHistoryReadPorts

    return ProfileHistoryReadPorts(
        bucket_id=bucket_id,
        operation=operation,
        event_repository=build_bucket_event_history_repository(bucket_id=bucket_id),
    )


def build_modelo_invoice_withholding_capture_ports(*, profile_id: str) -> ModeloInvoiceWithholdingCapturePorts:
    """Bind canonical withholding services to the selected encrypted profile."""
    from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ..application.modelo.invoice_withholding_capture_contracts import ModeloInvoiceWithholdingCapturePorts
    from .adapter_composition_ports import build_retencion_observation_ports, build_withholding_observation_service

    return ModeloInvoiceWithholdingCapturePorts(
        profile_id=profile_id,
        invoice_catalogue_repository=InvoiceCatalogueRepository(bucket_id=profile_id),
        retencion_observation_repository=build_retencion_observation_ports(bucket_id=profile_id).repository,
        withholding_observation_service=build_withholding_observation_service(bucket_id=profile_id),
    )


def build_modelo_workbench_read_ports(bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloWorkbenchReadPorts:
    """Bind the repositories one declaration's workbench reads from to the worker's profile."""
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.workbench_read import ModeloWorkbenchReadPorts
    from .adapter_composition_ports import build_borrador_100_snapshot_repository
    from .adapter_composition_work_ports import build_calculation_action_ports
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    objects = secure_object_repository_for_bucket(bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=bucket_id,
        objects=objects,
        operation=operation,
    )
    ports = build_calculation_action_ports(bucket_id=bucket_id, operation=operation, objects=objects)
    return ModeloWorkbenchReadPorts(
        work_units=ports.work_unit_repository,
        calculations=ports.calculation_repository,
        verifications=calculation_binding.verification_repository(),
        borrador_snapshots=build_borrador_100_snapshot_repository(bucket_id=bucket_id),
        holiday_territory=partial(profile_holiday_territory, bucket_id, operation),
        bucket_events=ports.bucket_event_repository,
        filings=ports.filing_repository,
    )


def profile_holiday_territory(bucket_id: str, operation: PinnedAuthorityOperation) -> CalendarCCAA | None:
    """Read the profile's holiday territory, or ``None`` while the profile cannot say.

    An absent or incomplete profile leaves the deadline on the national
    holidays, which the form discloses, rather than keeping the workbench shut.
    """
    from ..application.modelo.action_errors import ModeloProfileReadinessError
    from ..application.modelo.m303_regimen_simplificado_scope import taxpayer_profile_for_work
    from ..application.modelo.profile_readiness_gate import load_modelo_work_profile

    profile = load_modelo_work_profile(bucket_id=bucket_id, profile_decode_context=operation.profile_decode_context())
    try:
        return taxpayer_profile_for_work(profile).holiday_territory
    except ModeloProfileReadinessError:
        return None


def build_modelo_aggregate_operation_ports(*, profile_id: str) -> ModeloAggregateOperationPorts:
    """Bind the existing aggregate and ledger-payment services to one profile."""
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..application.modelo.aggregate_ports import ModeloAggregateOperationPorts
    from .adapter_composition_ports import (
        build_percepcion_observation_ports,
        build_retencion_observation_ports,
        build_withholding_observation_service,
    )

    return ModeloAggregateOperationPorts(
        profile_id=profile_id,
        transaction_catalogue_repository=TransactionCatalogueRepository(bucket_id=profile_id),
        retencion_observation_repository=build_retencion_observation_ports(bucket_id=profile_id).repository,
        percepcion_observation_repository=build_percepcion_observation_ports(bucket_id=profile_id).repository,
        withholding_observation_service=build_withholding_observation_service(bucket_id=profile_id),
    )


def build_auth_operation_ports(operator_scope_ports: OperatorScopePorts | None = None) -> AuthOperationPorts:
    """Compose the outer capabilities the registered auth executors run against."""
    from ..adapters.outbound.aeat.browser.factory import default_browser_session_factory
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports
    from ..application.auth.operation_definitions import AuthOperationPorts
    from .adapter_composition_ports import build_operator_probe_ports

    return AuthOperationPorts(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        browser_session_factory=default_browser_session_factory,
        operator_probe_ports=build_operator_probe_ports(),
        operator_scope_ports=operator_scope_ports or build_operator_scope_ports(),
    )


async def acquire_registry_verify_observation(
    surface: VerifySurface,
    nif: str,
    expected: IdentityCheckVerdictValue | None,
    operation: PinnedAuthorityOperation,
    *,
    resolved_settings: Settings,
) -> VerifyLiveObservation:
    """Acquire exactly one canonical verdict observation under the same resolved settings."""
    from ..application.live.verify import VerifySurface
    from ..application.live.verify_capture_operation import VerifyLiveObservation
    from ..core.identity.tax_id import tax_id_identity_token

    del operation
    expected_by_nif = {tax_id_identity_token(nif): expected or "unknown"}
    if surface is VerifySurface.NIF_IVA:
        from ..adapters.outbound.aeat.sede.nif_iva_check import collect_nif_iva_check_observations

        result = await collect_nif_iva_check_observations(b"", expected=expected_by_nif, settings=resolved_settings)
    else:
        from ..adapters.outbound.aeat.sede.groi_check import collect_groi_observations

        result = await collect_groi_observations(b"", expected=expected_by_nif, settings=resolved_settings)
    if len(result.observations) != 1:
        raise ValueError("verify acquisition must return exactly one observation")
    return VerifyLiveObservation.model_validate(result.observations[0], from_attributes=True)


def verify_live_preflight(settings: Settings, profile_id: UUID, operation: PinnedAuthorityOperation) -> None:
    """Refuse a live identity check that the access gate does not allow."""
    from ..core.access_gate.gate import AeatAccessGate

    del operation, profile_id
    AeatAccessGate(settings).require_live_read()


def verify_persistence(settings: Settings, bucket_id: str) -> VerifyObservationRepository:
    """Bind the verify observation store to one profile."""
    from ..adapters.persistence.profile.verify_observations import VerifyObservationRepository

    return VerifyObservationRepository(bucket_id=bucket_id, settings=settings)


def notification_ports(settings: Settings) -> NotificationsPorts:
    """Compose the notification read ports under the resolved settings."""
    from .live_state_composition import compose_notifications_ports

    return compose_notifications_ports(settings=settings)


def notification_document_service(settings: Settings) -> NotificationDocumentService:
    """Compose the notification-document custody service under the resolved settings."""
    from .live_state_composition import compose_notification_document_service

    return compose_notification_document_service(settings=settings)


@dataclass(kw_only=True, eq=False)
class OperationCompositionInputs:
    """What every composition group shares.

    A ``None`` capability selects its production default, which only the
    group that uses it imports. ``contracts`` answers the composed registry's
    own public contracts; edit admission judges against them.
    """

    settings: Settings | None = None
    contracts: Callable[[], OperationPublicContractSetV1] | None = None
    auth_definitions: tuple[OperationDefinition, ...] | None = None
    censal_definition: OperationDefinition | None = None
    verify_nif_iva_definition: OperationDefinition | None = None
    verify_tgvi_definition: OperationDefinition | None = None
    google_export_definition: OperationDefinition | None = None
    evidence_followup_ports: LedgerEvidenceFollowupOperationPorts | None = None
    modelo_query_read_ports_factory: ModeloQueryReadPortsFactory | None = None
    recipient_registry_ports_factory: RecipientFingerprintRegistryPortsFactory | None = None
    recipient_event_repository_factory: BucketEventHistoryRepositoryFactory | None = None
    modelo_export_ports_factory: ModeloExportPortsFactory | None = None
    calculation_action_ports_factory: CalculationActionPortsFactory | None = None
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol] | None = None
    amendment_action_ports_factory: AmendmentActionPortsFactory | None = None
    filing_action_ports_factory: FilingActionPortsFactory | None = None
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory | None = None
    modelo_history_ports_factory: ModeloHistoryPortsFactory | None = None
    workflow_run_read_ports_factory: WorkflowRunReadPortsFactory | None = None
    dependency_read_ports_factory: DependencyReadPortsFactory | None = None
    pipeline_read_ports_factory: PipelineReadPortsFactory | None = None
    overview_read_ports_factory: OverviewReadPortsFactory | None = None
    invoice_inspection_read_ports_factory: InvoiceInspectionReadPortsFactory | None = None
    invoice_creation_ports_factory: CatalogueCreationPortsFactory | None = None
    modelo_aggregate_operation_ports_factory: ModeloAggregateOperationPortsFactory | None = None
    modelo_invoice_withholding_capture_ports_factory: ModeloInvoiceWithholdingCapturePortsFactory | None = None
    invoice_lifecycle_ports_factory: CatalogueLifecyclePortsFactory | None = None
    modelo_edit_receipt_repository_factory: ModeloEditReceiptRepositoryFactory | None = None
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory | None = None
    ledger_action_ports_factory: LedgerActionPortsFactory | None = None
    ledger_read_ports_factory: LedgerReadPortsFactory | None = None
    ledger_rule_repository_factory: LedgerClassificationRuleRepositoryFactory | None = None
    counterparty_repository_factory: CounterpartyEstablishmentRepositoryFactory | None = None
    own_account_repository_factory: OwnAccountRepositoryFactory | None = None
    ledger_participation_repository_factory: TransactionParticipationIndexRepositoryFactory | None = None
    participation_rebuild_ports_factory: ParticipationIndexRebuildPortsFactory | None = None
    operator_scope_ports: OperatorScopePorts | None = None
    automation_administration_factory: AutomationAdministrationFactory | None = None
    automation_inventory_reader: AutomationInventoryReader | None = None
    workbench_generation_reader: WorkbenchGenerationReader | None = None
    profile_rotation_finalizer: ProfileRotationFinalizer | None = None
    modelo_profile_resolver: ModeloWorkVerifyProfileResolver | None = None
    modelo_workbench_read_ports_factory: ModeloWorkbenchReadPortsFactory | None = None
    execution_caller_reader: OperationExecutionCallerReader | None = None
    connectivity_probe: ConnectivityProbePort | None = None
    sede_view_stream_opener: SedeViewStreamOpener | None = None

    @cached_property
    def resolved_settings(self) -> Settings:
        """The supplied settings or the production default."""
        return self.settings or load_settings()

    @cached_property
    def scope(self) -> OperatorScopePorts:
        """The injected operator scope or the native operator authority."""
        from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports

        return self.operator_scope_ports or build_operator_scope_ports()

    @cached_property
    def auth_ports(self) -> AuthOperationPorts:
        """The auth capabilities, bound to the one operator scope."""
        return build_auth_operation_ports(self.scope)

    @cached_property
    def edit_prerequisites(self) -> ModeloEditRefusalProjectionStore:
        """The refused Apply prerequisites this composition's worker retains in memory.

        A refused Apply's named prerequisite stays here until the workbench
        reads it once; the journal never holds it.
        """
        from ..application.modelo.edit_refusal_projection import ModeloEditRefusalProjectionStore

        return ModeloEditRefusalProjectionStore()

    @cached_property
    def own_accounts(self) -> OwnAccountRepositoryFactory:
        """The injected own-account repository factory or the profile adapter."""
        if self.own_account_repository_factory is not None:
            return self.own_account_repository_factory
        from ..adapters.persistence.profile.own_accounts import OwnAccountRepository

        return OwnAccountRepository

    def registry_contracts(self) -> OperationPublicContractSetV1:
        """Return the composed registry's contracts, refusing before it exists."""
        if self.contracts is None:
            raise InternalInvariantError("the operation registry's contracts are read before it is composed")
        return self.contracts()

    def calculation_actions(self) -> CalculationActionPortsFactory:
        """The injected calculation-action ports factory or the production adapter."""
        from .adapter_composition_work_ports import build_calculation_action_ports

        return supplied(self.calculation_action_ports_factory, build_calculation_action_ports)

    def work_lifecycle(self) -> ActiveWorkLifecyclePortsFactory:
        """The injected active-work lifecycle ports factory or the production adapter."""
        from .adapter_composition_work_ports import build_active_work_lifecycle_ports

        return supplied(self.work_lifecycle_ports_factory, build_active_work_lifecycle_ports)

    def verification_bundle(self) -> VerificationRepositoryBundleFactory:
        """The injected verification repository bundle factory or the production adapter."""
        from .adapter_composition_work_ports import build_verification_repository_bundle

        return supplied(self.verification_repository_bundle_factory, build_verification_repository_bundle)

    def modelo_history(self) -> ModeloHistoryPortsFactory:
        """The injected Modelo history ports factory or the production adapter."""
        from .adapter_composition_ports import build_modelo_history_ports

        return supplied(self.modelo_history_ports_factory, build_modelo_history_ports)

    def workflow_runs(self) -> WorkflowRunReadPortsFactory:
        """The injected workflow-run read ports factory or the production adapter."""
        from .workflow_run_composition import build_workflow_run_read_ports

        return supplied(self.workflow_run_read_ports_factory, build_workflow_run_read_ports)

    def attachments(self) -> Callable[[str], AttachmentStoreProtocol]:
        """The injected attachment store factory or the production adapter."""
        from .adapter_composition_ports import build_attachment_store

        return supplied(self.attachment_store_factory, build_attachment_store)

    def modelo_exports(self) -> ModeloExportPortsFactory:
        """The injected Modelo export ports factory or the production adapter."""
        from .adapter_composition_ports import build_modelo_export_ports

        return supplied(self.modelo_export_ports_factory, build_modelo_export_ports)

    def modelo_profile(self) -> ModeloWorkVerifyProfileResolver:
        """The injected Modelo profile resolver or the active workflow profile."""
        from ..application.modelo.operation_shared import resolve_active_workflow_profile

        return supplied(self.modelo_profile_resolver, resolve_active_workflow_profile)

    def recipient_registry(self) -> RecipientFingerprintRegistryPortsFactory:
        """The injected recipient fingerprint registry ports factory or the profile adapter."""
        from ..adapters.persistence.profile.review_package_recipient_registry import (
            build_recipient_fingerprint_registry_ports,
        )

        return supplied(self.recipient_registry_ports_factory, build_recipient_fingerprint_registry_ports)

    def recipient_events(self) -> BucketEventHistoryRepositoryFactory:
        """The injected bucket event repository factory or the profile adapter."""
        from ..adapters.persistence.profile.buckets import build_bucket_event_history_repository

        return supplied(self.recipient_event_repository_factory, build_bucket_event_history_repository)

    def ledger_actions(self) -> LedgerActionPortsFactory:
        """The injected ledger action ports factory or the production composition."""
        from .ledger_action_composition import compose_ledger_action_ports

        return supplied(self.ledger_action_ports_factory, compose_ledger_action_ports)

    def ledger_reads(self) -> LedgerReadPortsFactory:
        """The injected ledger read ports factory or the production composition."""
        from .ledger_action_composition import compose_ledger_read_ports

        return supplied(self.ledger_read_ports_factory, compose_ledger_read_ports)

    def ledger_rules(self) -> LedgerClassificationRuleRepositoryFactory:
        """The injected classification rule repository factory or the profile adapter."""
        from ..adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository

        return supplied(self.ledger_rule_repository_factory, LedgerClassificationRuleRepository)

    def ledger_participation(self) -> TransactionParticipationIndexRepositoryFactory:
        """The injected participation index repository factory or the profile adapter."""
        from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository

        return supplied(self.ledger_participation_repository_factory, TransactionParticipationIndexRepository)

    def invoice_lifecycle(self) -> CatalogueLifecyclePortsFactory:
        """The injected invoice catalogue lifecycle ports factory or the profile adapter."""
        from ..adapters.persistence.profile.catalogue_creation import build_catalogue_lifecycle_ports

        return supplied(self.invoice_lifecycle_ports_factory, build_catalogue_lifecycle_ports)

    def invoice_inspection(self) -> InvoiceInspectionReadPortsFactory:
        """The injected invoice inspection read ports factory or the production composition."""
        from .invoice_inspection_composition import build_invoice_inspection_read_ports

        return supplied(self.invoice_inspection_read_ports_factory, build_invoice_inspection_read_ports)


#: Build every operation one composition group owns.


def built(
    definitions: Iterable[OperationDefinition], registrations: Iterable[OperationPublicDefinitionRegistrationV1]
) -> OperationGroupBuild:
    """Compose built."""
    return OperationGroupBuild(definitions=tuple(definitions), registrations=tuple(registrations))
