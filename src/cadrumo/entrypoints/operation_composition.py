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

import secrets
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import timedelta
from functools import cached_property, partial
from typing import TYPE_CHECKING
from uuid import UUID

from ..application.operations.contract_manifest import (
    ManifestOperationRegistry,
    OperationContractManifestV1,
    OperationGroupBuild,
    load_operation_contract_manifest,
)
from ..application.operations.registry import OperationPublicContractSetV1, OperationRegistry
from ..application.operations.registry_schema_validation import operation_schema_compilation_scope
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
    from ..application.ledger.import_operation import LedgerImportOperationPorts
    from ..application.ledger.llm_review_execution import LedgerLlmOperationPorts
    from ..application.ledger.own_account_ports import OwnAccountRepositoryFactory
    from ..application.ledger.participation_read import TransactionParticipationIndexRepositoryFactory
    from ..application.ledger.read_ports import LedgerReadPortsFactory
    from ..application.ledger.rule_repository import LedgerClassificationRuleRepositoryFactory
    from ..application.live.justificante_capture_operation import JustificanteCapturePorts
    from ..application.live.notification_documents import NotificationDocumentService
    from ..application.live.notification_ports import NotificationsPorts
    from ..application.live.verify import VerifySurface
    from ..application.live.verify_capture_operation import VerifyLiveObservation
    from ..application.local_reader_provisioning import RuntimeServerOwnerStart
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
    from ..application.modelo.operation_definitions import ModeloWorkVerifyProfileResolver
    from ..application.modelo.participation_index_rebuild_ports import ParticipationIndexRebuildPortsFactory
    from ..application.modelo.query_read_contracts import ModeloQueryReadPortsFactory
    from ..application.modelo.review_package_recipient_registry_ports import RecipientFingerprintRegistryPortsFactory
    from ..application.modelo.verification_repository_ports import VerificationRepositoryBundleFactory
    from ..application.modelo.work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
    from ..application.modelo.workbench_read import ModeloWorkbenchReadPorts, ModeloWorkbenchReadPortsFactory
    from ..application.operations.authorization import OperationExecutionAuthority
    from ..application.operations.composition import OperationComposedServices
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
    from ..core.hex import Hex64Str
    from ..core.identity_check_verdict import IdentityCheckVerdictValue
    from ..domain.attachments.protocols import AttachmentStoreProtocol
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..domain.deadlines.festivos import CalendarCCAA

_LEASE_DURATION = timedelta(minutes=10)
_EXECUTION_TIMEOUT = timedelta(hours=1)
_CLEANUP_TIMEOUT = timedelta(minutes=2)


def _supplied[T](value: T | None, default: T) -> T:
    """Return the injected capability, else its production default."""
    return default if value is None else value


def _build_profile_history_read_ports(
    *, bucket_id: str, operation: PinnedAuthorityOperation
) -> ProfileHistoryReadPorts:
    """Bind canonical event history to the worker's exact profile and authority pin."""
    from ..adapters.persistence.profile.buckets import build_bucket_event_history_repository
    from ..application.user_profile.history_operation import ProfileHistoryReadPorts

    return ProfileHistoryReadPorts(
        bucket_id=bucket_id,
        operation=operation,
        event_repository=build_bucket_event_history_repository(bucket_id=bucket_id),
    )


def _build_modelo_invoice_withholding_capture_ports(*, profile_id: str) -> ModeloInvoiceWithholdingCapturePorts:
    """Bind canonical withholding services to the selected encrypted profile."""
    from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ..application.modelo.invoice_withholding_capture_contracts import ModeloInvoiceWithholdingCapturePorts
    from .adapter_composition import build_retencion_observation_ports, build_withholding_observation_service

    return ModeloInvoiceWithholdingCapturePorts(
        profile_id=profile_id,
        invoice_catalogue_repository=InvoiceCatalogueRepository(bucket_id=profile_id),
        retencion_observation_repository=build_retencion_observation_ports(bucket_id=profile_id).repository,
        withholding_observation_service=build_withholding_observation_service(bucket_id=profile_id),
    )


def _build_modelo_workbench_read_ports(bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloWorkbenchReadPorts:
    """Bind the repositories one declaration's workbench reads from to the worker's profile."""
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.workbench_read import ModeloWorkbenchReadPorts
    from .adapter_composition import build_borrador_100_snapshot_repository, build_calculation_action_ports
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
        holiday_territory=partial(_profile_holiday_territory, bucket_id, operation),
        bucket_events=ports.bucket_event_repository,
    )


def _profile_holiday_territory(bucket_id: str, operation: PinnedAuthorityOperation) -> CalendarCCAA | None:
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


def _build_modelo_aggregate_operation_ports(*, profile_id: str) -> ModeloAggregateOperationPorts:
    """Bind the existing aggregate and ledger-payment services to one profile."""
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..application.modelo.aggregate_ports import ModeloAggregateOperationPorts
    from .adapter_composition import (
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
    from .adapter_composition import build_operator_probe_ports

    return AuthOperationPorts(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        browser_session_factory=default_browser_session_factory,
        operator_probe_ports=build_operator_probe_ports(),
        operator_scope_ports=operator_scope_ports or build_operator_scope_ports(),
    )


async def _acquire_registry_verify_observation(
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


def _verify_live_preflight(settings: Settings, profile_id: UUID, operation: PinnedAuthorityOperation) -> None:
    """Refuse a live identity check the access gate does not allow."""
    from ..core.access_gate.gate import AeatAccessGate

    del profile_id, operation
    AeatAccessGate(settings).require_live_read()


def _verify_persistence(settings: Settings, bucket_id: str) -> VerifyObservationRepository:
    """Bind the verify observation store to one profile."""
    from ..adapters.persistence.profile.verify_observations import VerifyObservationRepository

    return VerifyObservationRepository(bucket_id=bucket_id, settings=settings)


def _notification_ports(settings: Settings) -> NotificationsPorts:
    """Compose the notification read ports under the resolved settings."""
    from .live_state_composition import compose_notifications_ports

    return compose_notifications_ports(settings=settings)


def _notification_document_service(settings: Settings) -> NotificationDocumentService:
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
    runtime_server_owner_start: RuntimeServerOwnerStart | None = None
    connectivity_probe: ConnectivityProbePort | None = None

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
        from .adapter_composition import build_calculation_action_ports

        return _supplied(self.calculation_action_ports_factory, build_calculation_action_ports)

    def work_lifecycle(self) -> ActiveWorkLifecyclePortsFactory:
        """The injected active-work lifecycle ports factory or the production adapter."""
        from .adapter_composition import build_active_work_lifecycle_ports

        return _supplied(self.work_lifecycle_ports_factory, build_active_work_lifecycle_ports)

    def verification_bundle(self) -> VerificationRepositoryBundleFactory:
        """The injected verification repository bundle factory or the production adapter."""
        from .adapter_composition import build_verification_repository_bundle

        return _supplied(self.verification_repository_bundle_factory, build_verification_repository_bundle)

    def modelo_history(self) -> ModeloHistoryPortsFactory:
        """The injected Modelo history ports factory or the production adapter."""
        from .adapter_composition import build_modelo_history_ports

        return _supplied(self.modelo_history_ports_factory, build_modelo_history_ports)

    def workflow_runs(self) -> WorkflowRunReadPortsFactory:
        """The injected workflow-run read ports factory or the production adapter."""
        from .workflow_run_composition import build_workflow_run_read_ports

        return _supplied(self.workflow_run_read_ports_factory, build_workflow_run_read_ports)

    def attachments(self) -> Callable[[str], AttachmentStoreProtocol]:
        """The injected attachment store factory or the production adapter."""
        from .adapter_composition import build_attachment_store

        return _supplied(self.attachment_store_factory, build_attachment_store)

    def modelo_exports(self) -> ModeloExportPortsFactory:
        """The injected Modelo export ports factory or the production adapter."""
        from .adapter_composition import build_modelo_export_ports

        return _supplied(self.modelo_export_ports_factory, build_modelo_export_ports)

    def modelo_profile(self) -> ModeloWorkVerifyProfileResolver:
        """The injected Modelo profile resolver or the active workflow profile."""
        from ..application.modelo.operation_definitions import resolve_active_workflow_profile

        return _supplied(self.modelo_profile_resolver, resolve_active_workflow_profile)

    def recipient_registry(self) -> RecipientFingerprintRegistryPortsFactory:
        """The injected recipient fingerprint registry ports factory or the profile adapter."""
        from ..adapters.persistence.profile.review_package_recipient_registry import (
            build_recipient_fingerprint_registry_ports,
        )

        return _supplied(self.recipient_registry_ports_factory, build_recipient_fingerprint_registry_ports)

    def recipient_events(self) -> BucketEventHistoryRepositoryFactory:
        """The injected bucket event repository factory or the profile adapter."""
        from ..adapters.persistence.profile.buckets import build_bucket_event_history_repository

        return _supplied(self.recipient_event_repository_factory, build_bucket_event_history_repository)

    def ledger_actions(self) -> LedgerActionPortsFactory:
        """The injected ledger action ports factory or the production composition."""
        from .ledger_action_composition import compose_ledger_action_ports

        return _supplied(self.ledger_action_ports_factory, compose_ledger_action_ports)

    def ledger_reads(self) -> LedgerReadPortsFactory:
        """The injected ledger read ports factory or the production composition."""
        from .ledger_action_composition import compose_ledger_read_ports

        return _supplied(self.ledger_read_ports_factory, compose_ledger_read_ports)

    def ledger_rules(self) -> LedgerClassificationRuleRepositoryFactory:
        """The injected classification rule repository factory or the profile adapter."""
        from ..adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository

        return _supplied(self.ledger_rule_repository_factory, LedgerClassificationRuleRepository)

    def ledger_participation(self) -> TransactionParticipationIndexRepositoryFactory:
        """The injected participation index repository factory or the profile adapter."""
        from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository

        return _supplied(self.ledger_participation_repository_factory, TransactionParticipationIndexRepository)

    def invoice_lifecycle(self) -> CatalogueLifecyclePortsFactory:
        """The injected invoice catalogue lifecycle ports factory or the profile adapter."""
        from ..adapters.persistence.profile.catalogue_creation import build_catalogue_lifecycle_ports

        return _supplied(self.invoice_lifecycle_ports_factory, build_catalogue_lifecycle_ports)

    def invoice_inspection(self) -> InvoiceInspectionReadPortsFactory:
        """The injected invoice inspection read ports factory or the production composition."""
        from .invoice_inspection_composition import build_invoice_inspection_read_ports

        return _supplied(self.invoice_inspection_read_ports_factory, build_invoice_inspection_read_ports)


#: Build every operation one composition group owns.
type _GroupComposer = Callable[[OperationCompositionInputs], OperationGroupBuild]


def _built(
    definitions: Iterable[OperationDefinition], registrations: Iterable[OperationPublicDefinitionRegistrationV1]
) -> OperationGroupBuild:
    return OperationGroupBuild(definitions=tuple(definitions), registrations=tuple(registrations))


# -- auth --------------------------------------------------------------------------------------------------------------


def _auth_operation_definitions(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.auth.operation_definitions import (
        build_auth_operation_definitions,
        build_auth_operation_registrations,
    )

    definitions = (
        inputs.auth_definitions
        if inputs.auth_definitions is not None
        else build_auth_operation_definitions(
            ports=inputs.auth_ports, finalize_rotation=inputs.profile_rotation_finalizer
        )
    )
    return _built(definitions, build_auth_operation_registrations(definitions))


def _auth_certificate_secret_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.auth.certificate_secret_operation import (
        CertificateSecretOperationPorts,
        build_certificate_secret_operation_definitions,
        build_certificate_secret_operation_registrations,
    )

    definitions = build_certificate_secret_operation_definitions(
        CertificateSecretOperationPorts(
            operator_scope_ports=inputs.scope,
            certificate_secret_backend_factory=inputs.auth_ports.certificate_secret_backend_factory,
        )
    )
    return _built(definitions, build_certificate_secret_operation_registrations(definitions))


def _auth_certificate_source_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.auth.certificate_source_execution import CertificateSourceOperationPorts
    from ..application.auth.certificate_source_operation import (
        build_certificate_source_check_definition,
        build_certificate_source_check_registration,
        build_certificate_source_list_definition,
        build_certificate_source_list_registration,
        build_certificate_source_register_definition,
        build_certificate_source_register_registration,
        build_certificate_source_remove_definition,
        build_certificate_source_remove_registration,
        build_certificate_source_select_definition,
        build_certificate_source_select_registration,
    )

    ports = CertificateSourceOperationPorts(
        operator_scope_ports=inputs.scope,
        operator_probe_ports=inputs.auth_ports.operator_probe_ports,
        certificate_secret_backend_factory=inputs.auth_ports.certificate_secret_backend_factory,
    )
    register = build_certificate_source_register_definition(ports)
    listing = build_certificate_source_list_definition(ports)
    select = build_certificate_source_select_definition(ports)
    remove = build_certificate_source_remove_definition(ports)
    check = build_certificate_source_check_definition(ports)
    return _built(
        (register, listing, select, remove, check),
        (
            build_certificate_source_register_registration(register),
            build_certificate_source_list_registration(listing),
            build_certificate_source_select_registration(select),
            build_certificate_source_remove_registration(remove),
            build_certificate_source_check_registration(check),
        ),
    )


def _auth_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
    from .auth_read_composition import compose_auth_read_ports

    del inputs
    definition = build_auth_read_definition(compose_auth_read_ports)
    return _built((definition,), (build_auth_read_registration(definition),))


def _auth_apoderado_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.auth.apoderado_operation import (
        build_apoderado_operation_definitions,
        build_apoderado_operation_registrations,
    )
    from .auth_apoderado_composition import build_apoderado_operation_ports

    del inputs
    definitions = build_apoderado_operation_definitions(build_apoderado_operation_ports)
    return _built(definitions, build_apoderado_operation_registrations(definitions))


def _auth_diagnostic_report_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.auth.diagnostic_report_operation import (
        build_auth_diagnostic_report_definition,
        build_auth_diagnostic_report_registration,
    )
    from .auth_apoderado_composition import build_auth_diagnostic_report_ports

    del inputs
    definition = build_auth_diagnostic_report_definition(build_auth_diagnostic_report_ports)
    return _built((definition,), (build_auth_diagnostic_report_registration(definition),))


# -- profile-wide registered operations --------------------------------------------------------------------------------


def _review_read_registration(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.review.read_contracts import ReviewReadOperationPorts
    from ..application.review.read_registration import build_review_read_definitions, build_review_read_registrations
    from .adapter_composition import build_draft_review_ports

    definitions = build_review_read_definitions(
        ReviewReadOperationPorts(settings=inputs.resolved_settings, draft_review_ports_factory=build_draft_review_ports)
    )
    return _built(definitions, build_review_read_registrations(definitions))


def _workstation_check_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.workstation_check_operation import (
        build_workstation_check_definition,
        build_workstation_check_registration,
    )
    from .workstation_check_operation_composition import build_workstation_check_operation_ports

    del inputs
    definition = build_workstation_check_definition(build_workstation_check_operation_ports)
    return _built((definition,), (build_workstation_check_registration(definition),))


def _diagnostics_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.diagnostics_operation import (
        build_diagnostics_read_definition,
        build_diagnostics_read_registration,
    )
    from .diagnostics_operation_composition import build_diagnostics_read_ports

    del inputs
    definition = build_diagnostics_read_definition(build_diagnostics_read_ports)
    return _built((definition,), (build_diagnostics_read_registration(definition),))


def _diagnostics_repair_composition(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from .diagnostics_repair_composition import build_diagnostics_repair_operations, probe_aeat_sede_connectivity

    operations = build_diagnostics_repair_operations(
        execution_caller_reader=inputs.execution_caller_reader,
        connectivity_probe=_supplied(inputs.connectivity_probe, probe_aeat_sede_connectivity),
    )
    return _built(operations.definitions, operations.registrations)


def _local_reader_operation_composition(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from .local_reader_operation_composition import build_local_reader_operations

    operations = build_local_reader_operations(owner_start=inputs.runtime_server_owner_start)
    return _built(operations.definitions, operations.registrations)


def _workbench_generation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.workbench_generation_operation import (
        build_workbench_generation_operation_definition,
        build_workbench_generation_operation_registration,
    )

    definition = build_workbench_generation_operation_definition(inputs.workbench_generation_reader)
    return _built((definition,), (build_workbench_generation_operation_registration(definition),))


def _actividad_asset_registered_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.actividad_asset.registered_operations import (
        build_activity_asset_claim_definition,
        build_activity_asset_claim_registration,
        build_activity_asset_correct_definition,
        build_activity_asset_correct_registration,
        build_activity_asset_create_definition,
        build_activity_asset_create_registration,
        build_activity_asset_filing_handoff_definition,
        build_activity_asset_filing_handoff_registration,
        build_activity_asset_forecast_definition,
        build_activity_asset_forecast_registration,
        build_activity_asset_inspect_definition,
        build_activity_asset_inspect_registration,
    )
    from .actividad_asset_composition import build_activity_asset_operation_ports

    del inputs
    ports = build_activity_asset_operation_ports
    create = build_activity_asset_create_definition(ports)
    inspect = build_activity_asset_inspect_definition(ports)
    correct = build_activity_asset_correct_definition(ports)
    forecast = build_activity_asset_forecast_definition(ports)
    claim = build_activity_asset_claim_definition(ports)
    handoff = build_activity_asset_filing_handoff_definition(ports)
    return _built(
        (create, inspect, correct, forecast, claim, handoff),
        (
            build_activity_asset_create_registration(create),
            build_activity_asset_inspect_registration(inspect),
            build_activity_asset_correct_registration(correct),
            build_activity_asset_forecast_registration(forecast),
            build_activity_asset_claim_registration(claim),
            build_activity_asset_filing_handoff_registration(handoff),
        ),
    )


def _inventory_registered_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.inventory.registered_operation import (
        build_inventory_closing_authority_record_definition,
        build_inventory_closing_authority_record_registration,
        build_inventory_create_definition,
        build_inventory_create_registration,
        build_inventory_list_definition,
        build_inventory_list_registration,
        build_inventory_movement_add_definition,
        build_inventory_movement_add_registration,
        build_inventory_valuation_preview_definition,
        build_inventory_valuation_preview_registration,
    )
    from .adapter_composition import build_inventory_service_ports

    caller = inputs.execution_caller_reader
    listing = build_inventory_list_definition(build_inventory_service_ports)
    create = build_inventory_create_definition(build_inventory_service_ports, execution_caller_reader=caller)
    movement = build_inventory_movement_add_definition(build_inventory_service_ports, execution_caller_reader=caller)
    valuation = build_inventory_valuation_preview_definition(
        build_inventory_service_ports, execution_caller_reader=caller
    )
    closing = build_inventory_closing_authority_record_definition(
        build_inventory_service_ports, execution_caller_reader=caller
    )
    return _built(
        (listing, create, movement, valuation, closing),
        (
            build_inventory_list_registration(listing),
            build_inventory_create_registration(create),
            build_inventory_movement_add_registration(movement),
            build_inventory_valuation_preview_registration(valuation),
            build_inventory_closing_authority_record_registration(closing),
        ),
    )


def _bienes_inversion_registered_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.bienes_inversion.registered_operation import (
        build_bienes_inversion_declare_definition,
        build_bienes_inversion_declare_registration,
        build_bienes_inversion_list_definition,
        build_bienes_inversion_list_registration,
    )
    from .adapter_composition import build_bienes_inversion_repository

    del inputs
    listing = build_bienes_inversion_list_definition(build_bienes_inversion_repository)
    declare = build_bienes_inversion_declare_definition(build_bienes_inversion_repository)
    return _built(
        (listing, declare),
        (build_bienes_inversion_list_registration(listing), build_bienes_inversion_declare_registration(declare)),
    )


def _prorrata_register_registered_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.prorrata_register.registered_operations import (
        build_prorrata_declare_sector_definition,
        build_prorrata_elect_especial_definition,
        build_prorrata_elect_general_definition,
        build_prorrata_list_definition,
        build_prorrata_list_registration,
        build_prorrata_mutation_registration,
        build_prorrata_revoke_especial_definition,
        build_prorrata_seed_definition,
        build_prorrata_seed_sector_definition,
        build_prorrata_settle_sector_definition,
    )
    from .adapter_composition import build_prorrata_register_repository

    repository = build_prorrata_register_repository
    listing = build_prorrata_list_definition(repository)
    mutations = (
        build_prorrata_declare_sector_definition(repository),
        build_prorrata_elect_especial_definition(repository),
        build_prorrata_elect_general_definition(repository),
        build_prorrata_revoke_especial_definition(repository),
        build_prorrata_seed_definition(repository, inputs.calculation_actions()),
        build_prorrata_seed_sector_definition(repository),
        build_prorrata_settle_sector_definition(repository),
    )
    return _built(
        (listing, *mutations),
        (
            build_prorrata_list_registration(listing),
            *(build_prorrata_mutation_registration(definition) for definition in mutations),
        ),
    )


# -- user profile ------------------------------------------------------------------------------------------------------


def _user_profile_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.user_profile.operations import (
        build_user_profile_operation_definitions,
        build_user_profile_operation_registrations,
    )

    del inputs
    definitions = build_user_profile_operation_definitions()
    return _built(definitions, build_user_profile_operation_registrations(definitions))


def _user_profile_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.user_profile.history_operation import (
        build_profile_history_definition,
        build_profile_history_registration,
        build_profile_history_timeline_definition,
        build_profile_history_timeline_registration,
    )

    del inputs
    history = build_profile_history_definition(_build_profile_history_read_ports)
    timeline = build_profile_history_timeline_definition(_build_profile_history_read_ports)
    return _built(
        (history, timeline),
        (build_profile_history_registration(history), build_profile_history_timeline_registration(timeline)),
    )


def _user_profile_google_configuration_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.user_profile.google_configuration_operation import (
        build_google_configuration_definitions,
        build_google_configuration_registration,
    )
    from .google_configuration_operation_composition import build_google_configuration_operation_ports

    del inputs
    definitions = build_google_configuration_definitions(build_google_configuration_operation_ports)
    return _built(definitions, (build_google_configuration_registration(definition) for definition in definitions))


def _user_profile_archive_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.user_profile.archive_operation import (
        build_profile_archive_operation_definitions,
        build_profile_archive_operation_registrations,
    )
    from .profile_archive_operation_composition import build_profile_archive_operation_ports

    del inputs
    definitions = build_profile_archive_operation_definitions(build_profile_archive_operation_ports)
    return _built(definitions, build_profile_archive_operation_registrations(definitions))


def _user_profile_recovery_status_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.user_profile.recovery_status_operation import (
        build_recovery_status_definition,
        build_recovery_status_registration,
    )

    del inputs
    definition = build_recovery_status_definition()
    return _built((definition,), (build_recovery_status_registration(definition),))


def _user_profile_recovery_revoke_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.user_profile.recovery_revoke_operation import recovery_revoke_operation

    del inputs
    definition, registration = recovery_revoke_operation()
    return _built((definition,), (registration,))


def _user_profile_automation_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.user_profile.automation_operations import (
        build_automation_operation_definitions,
        build_automation_operation_registrations,
    )

    definitions = build_automation_operation_definitions(
        inputs.automation_administration_factory, inventory_reader=inputs.automation_inventory_reader
    )
    return _built(definitions, build_automation_operation_registrations(definitions))


def _user_profile_censal_certificate_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.inbound.censo.parser import parse_certificado_censal_bytes
    from ..application.user_profile.censal_certificate_operation import censal_certificate_operation

    del inputs
    definition, registration = censal_certificate_operation(parse_certificado_censal_bytes)
    return _built((definition,), (registration,))


def _user_profile_censal_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.user_profile.censal_operation import (
        build_censal_operation_definition,
        build_censal_operation_registration,
    )

    if inputs.censal_definition is not None:
        definition = inputs.censal_definition
    else:
        from ..adapters.outbound.aeat.browser.factory import default_browser_session_factory
        from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
        from .adapter_composition import build_censal_fetch_port
        from .live_state_composition import preflight_filed_history_provider

        definition = build_censal_operation_definition(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            browser_session_factory=default_browser_session_factory,
            operator_scope_ports=inputs.scope,
            censal_fetch_port=build_censal_fetch_port(),
            provider_preflight=preflight_filed_history_provider,
        )
    return _built((definition,), (build_censal_operation_registration(definition),))


def _user_profile_censal_prepare_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.user_profile.censal_prepare_operation import (
        build_censal_prepare_operation_definition,
        build_censal_prepare_operation_registration,
    )
    from .censal_readback_composition import read_stored_censal_observation

    del inputs
    definition = build_censal_prepare_operation_definition(read_stored_censal_observation)
    return _built((definition,), (build_censal_prepare_operation_registration(definition),))


def _user_profile_censal_file_import_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.user_profile.censal_file_import_operation import (
        build_censal_file_import_operation_definition,
        build_censal_file_import_operation_registration,
    )

    del inputs
    definition = build_censal_file_import_operation_definition()
    return _built((definition,), (build_censal_file_import_operation_registration(definition),))


def _user_profile_censal_preview_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, default_browser_session_factory
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..application.user_profile.censal_preview_operation import (
        build_censal_preview_operation_definition,
        build_censal_preview_operation_registration,
    )
    from .adapter_composition import build_censal_fetch_port
    from .live_state_composition import preflight_filed_history_provider

    definition = build_censal_preview_operation_definition(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        browser_session_factory=default_browser_session_factory,
        operator_scope_ports=inputs.scope,
        censal_fetch_port=build_censal_fetch_port(),
        browser_resources_factory=BrowserRuntimeResourceScope,
        provider_preflight=preflight_filed_history_provider,
    )
    return _built((definition,), (build_censal_preview_operation_registration(definition),))


# -- exports -----------------------------------------------------------------------------------------------------------


def _export_google_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.export.google_operation import (
        build_google_sheets_export_operation_definition,
        build_google_sheets_export_operation_registration,
    )

    if inputs.google_export_definition is not None:
        definition = inputs.google_export_definition
    else:
        from .google_export_operation_composition import build_google_sheets_export_prepare_port

        definition = build_google_sheets_export_operation_definition(
            prepare_port=build_google_sheets_export_prepare_port()
        )
    return _built((definition,), (build_google_sheets_export_operation_registration(definition),))


def _export_google_review_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.export.google_review_operation import (
        build_google_review_operation_definition,
        build_google_review_operation_registration,
    )
    from .google_review_operation_composition import build_google_review_ports

    del inputs
    definition = build_google_review_operation_definition(build_google_review_ports)
    return _built((definition,), (build_google_review_operation_registration(definition),))


def _export_calculation_review_xlsx_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.export.calculation_review_xlsx_operation import (
        build_calculation_review_xlsx_definition,
        build_calculation_review_xlsx_registration,
    )
    from .calculation_review_xlsx_operation_composition import build_calculation_review_xlsx_ports

    del inputs
    definition = build_calculation_review_xlsx_definition(build_calculation_review_xlsx_ports)
    return _built((definition,), (build_calculation_review_xlsx_registration(definition),))


# -- live reads and captures -------------------------------------------------------------------------------------------


def _live_borrador_100_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.live.borrador_100_operation import (
        build_borrador_100_operation_definitions,
        build_borrador_100_operation_registrations,
    )
    from .live_borrador_operation_composition import build_borrador_100_operation_ports

    del inputs
    definitions = build_borrador_100_operation_definitions(build_borrador_100_operation_ports)
    return _built(definitions, build_borrador_100_operation_registrations(definitions))


def _live_filed_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..adapters.persistence.profile.sync_runs import SyncRunRecordRepository
    from ..application.live.filed_history_operation import (
        bind_shared_filed_history_pull,
        build_filed_history_operation_definition,
        build_filed_history_operation_registration,
    )
    from .live_state_composition import (
        compose_live_state,
        preflight_filed_history_provider,
        pull_filed_history_with_shared_composition,
    )

    del inputs
    definition = build_filed_history_operation_definition(
        sync_run_repository_factory=SyncRunRecordRepository,
        composition_factory=compose_live_state,
        browser_resources_factory=BrowserRuntimeResourceScope,
        pull=bind_shared_filed_history_pull(pull_filed_history_with_shared_composition),
        provider_preflight=preflight_filed_history_provider,
    )
    return _built((definition,), (build_filed_history_operation_registration(definition),))


def _live_filed_single_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.filed_single_capture_operation import (
        build_filed_single_capture_definition,
        build_filed_single_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_filed_single_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return _built((definition,), (build_filed_single_capture_registration(definition),))


def _live_filed_bulk_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..adapters.persistence.profile.sync_runs import SyncRunRecordRepository
    from ..application.live.filed_bulk_capture_operation import (
        build_filed_bulk_capture_definition,
        build_filed_bulk_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_filed_bulk_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider, SyncRunRecordRepository
    )
    return _built((definition,), (build_filed_bulk_capture_registration(definition),))


def _live_filed_source_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.filed_source_capture_operation import (
        build_filed_source_capture_definition,
        build_filed_source_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_filed_source_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return _built((definition,), (build_filed_source_capture_registration(definition),))


def _live_filed_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.filed_read_operation import (
        build_filed_discover_definition,
        build_filed_discover_registration,
        build_filed_list_definition,
        build_filed_list_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    listing = build_filed_list_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    discover = build_filed_discover_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return _built(
        (listing, discover), (build_filed_list_registration(listing), build_filed_discover_registration(discover))
    )


def _live_iva_wallet_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.live.iva_wallet_history_operation import (
        build_iva_wallet_history_definition,
        build_iva_wallet_history_registration,
    )
    from .live_state_composition import compose_live_state

    del inputs
    definition = build_iva_wallet_history_definition(
        lambda operation: compose_live_state(operation=operation).iva_remote_state_port
    )
    return _built((definition,), (build_iva_wallet_history_registration(definition),))


def _live_iva_wallet_history_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.iva_wallet_history_capture_operation import (
        build_iva_wallet_history_capture_definition,
        build_iva_wallet_history_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_iva_wallet_history_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return _built((definition,), (build_iva_wallet_history_capture_registration(definition),))


def _live_iva_wallet_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.iva_wallet_capture_operation import (
        build_iva_wallet_capture_definition,
        build_iva_wallet_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_iva_wallet_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return _built((definition,), (build_iva_wallet_capture_registration(definition),))


def _live_iva_remote_state_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.iva_remote_state_capture_operation import (
        build_iva_remote_state_capture_definition,
        build_iva_remote_state_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_iva_remote_state_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return _built((definition,), (build_iva_remote_state_capture_registration(definition),))


def _live_notifications_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.notifications_capture_operation import (
        build_notifications_capture_definition,
        build_notifications_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_notifications_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return _built((definition,), (build_notifications_capture_registration(definition),))


def _live_notification_document_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.notification_document_capture_operation import (
        build_notification_document_capture_definition,
        build_notification_document_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    definition = build_notification_document_capture_definition(
        compose_live_state,
        partial(_notification_document_service, inputs.resolved_settings),
        BrowserRuntimeResourceScope,
        preflight_filed_history_provider,
    )
    return _built((definition,), (build_notification_document_capture_registration(definition),))


def _live_notification_document_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.live.notification_document_read_operation import (
        build_notification_document_history_definition,
        build_notification_document_history_registration,
        build_notification_document_view_definition,
        build_notification_document_view_registration,
    )

    service = partial(_notification_document_service, inputs.resolved_settings)
    view = build_notification_document_view_definition(service)
    history = build_notification_document_history_definition(service)
    return _built(
        (view, history),
        (
            build_notification_document_view_registration(view),
            build_notification_document_history_registration(history),
        ),
    )


def _live_notifications_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.live.notifications_read_operation import (
        build_notifications_latest_definition,
        build_notifications_latest_registration,
        build_notifications_list_definition,
        build_notifications_list_registration,
        build_notifications_show_definition,
        build_notifications_show_registration,
    )

    ports = partial(_notification_ports, inputs.resolved_settings)
    listing = build_notifications_list_definition(ports)
    show = build_notifications_show_definition(ports)
    latest = build_notifications_latest_definition(ports)
    return _built(
        (listing, show, latest),
        (
            build_notifications_list_registration(listing),
            build_notifications_show_registration(show),
            build_notifications_latest_registration(latest),
        ),
    )


def _live_expedientes_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.live.expedientes_read_operation import (
        build_expedientes_latest_definition,
        build_expedientes_latest_registration,
        build_expedientes_list_definition,
        build_expedientes_list_registration,
        build_expedientes_show_definition,
        build_expedientes_show_registration,
    )
    from .adapter_composition import build_expedientes_ports

    del inputs
    listing = build_expedientes_list_definition(build_expedientes_ports)
    show = build_expedientes_show_definition(build_expedientes_ports)
    latest = build_expedientes_latest_definition(build_expedientes_ports)
    return _built(
        (listing, show, latest),
        (
            build_expedientes_list_registration(listing),
            build_expedientes_show_registration(show),
            build_expedientes_latest_registration(latest),
        ),
    )


def _live_expedientes_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, default_browser_session_factory
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..application.live.expedientes_capture_operation import (
        build_expedientes_bulk_capture_definition,
        build_expedientes_bulk_capture_registration,
        build_expedientes_single_capture_definition,
        build_expedientes_single_capture_registration,
    )
    from .adapter_composition import build_expedientes_ports
    from .live_state_composition import preflight_filed_history_provider

    single = build_expedientes_single_capture_definition(
        build_expedientes_ports,
        build_certificate_secret_backend,
        default_browser_session_factory,
        inputs.scope,
        BrowserRuntimeResourceScope,
        preflight_filed_history_provider,
    )
    bulk = build_expedientes_bulk_capture_definition(
        build_expedientes_ports,
        build_certificate_secret_backend,
        default_browser_session_factory,
        inputs.scope,
        BrowserRuntimeResourceScope,
        preflight_filed_history_provider,
    )
    return _built(
        (single, bulk),
        (build_expedientes_single_capture_registration(single), build_expedientes_bulk_capture_registration(bulk)),
    )


def _live_verify_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.verify import VerifySurface
    from ..application.live.verify_capture_operation import (
        build_verify_capture_definition,
        build_verify_capture_registration,
    )

    settings = inputs.resolved_settings

    def capture(surface: VerifySurface, injected: OperationDefinition | None) -> OperationDefinition:
        return injected or build_verify_capture_definition(
            surface,
            persistence_factory=partial(_verify_persistence, settings),
            acquire=partial(_acquire_registry_verify_observation, resolved_settings=settings),
            browser_resources_factory=BrowserRuntimeResourceScope,
            provider_preflight=partial(_verify_live_preflight, settings),
        )

    nif_iva = capture(VerifySurface.NIF_IVA, inputs.verify_nif_iva_definition)
    tgvi = capture(VerifySurface.TGVI, inputs.verify_tgvi_definition)
    return _built(
        (nif_iva, tgvi), (build_verify_capture_registration(nif_iva), build_verify_capture_registration(tgvi))
    )


def _live_verify_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.live.verify_read_operation import (
        build_verify_latest_definition,
        build_verify_latest_registration,
        build_verify_list_definition,
        build_verify_list_registration,
        build_verify_view_definition,
        build_verify_view_registration,
    )

    persistence = partial(_verify_persistence, inputs.resolved_settings)
    listing = build_verify_list_definition(persistence)
    view = build_verify_view_definition(persistence)
    latest = build_verify_latest_definition(persistence)
    return _built(
        (listing, view, latest),
        (
            build_verify_list_registration(listing),
            build_verify_view_registration(view),
            build_verify_latest_registration(latest),
        ),
    )


def _live_justificante_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..application.live.justificante_capture_operation import (
        JustificanteCapturePorts,
        build_justificante_capture_definition,
        build_justificante_capture_registration,
    )
    from .justificante_composition import (
        build_justificante_authenticity_verifier,
        build_justificante_capture_service,
        build_justificante_live_read_port,
        build_justificante_registration_ports,
    )
    from .live_state_composition import preflight_filed_history_provider

    scope = inputs.scope

    def capture_ports(bucket_id: str, operation: PinnedAuthorityOperation) -> JustificanteCapturePorts:
        return JustificanteCapturePorts(
            service=build_justificante_capture_service(bucket_id),
            read_port=build_justificante_live_read_port(build_certificate_secret_backend, scope, operation),
            registration_ports=build_justificante_registration_ports(operation),
            verifier=build_justificante_authenticity_verifier(),
        )

    definition = build_justificante_capture_definition(
        capture_ports, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return _built((definition,), (build_justificante_capture_registration(definition),))


def _live_justificante_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.live.justificante_read_operation import (
        build_justificante_list_definition,
        build_justificante_list_registration,
        build_justificante_show_definition,
        build_justificante_show_registration,
    )
    from .justificante_composition import build_justificante_capture_service

    del inputs
    listing = build_justificante_list_definition(build_justificante_capture_service)
    show = build_justificante_show_definition(build_justificante_capture_service)
    return _built(
        (listing, show), (build_justificante_list_registration(listing), build_justificante_show_registration(show))
    )


# -- Modelo work -------------------------------------------------------------------------------------------------------


def _modelo_operation_definitions(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.calculation_summary_pdf.summary_container import write_calculation_summary_pdf
    from ..adapters.persistence.profile.review_package_signing import build_review_package_signing_keypair_capability
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..application.modelo.metadata_operation_access import compose_modelo_metadata_access
    from ..application.modelo.operation_definitions import (
        build_modelo_lifecycle_operation_definitions,
        build_modelo_lifecycle_operation_registrations,
    )
    from ..application.modelo.revision_operation_access import compose_modelo_revision_access
    from .adapter_composition import (
        build_amendment_action_ports,
        build_filing_action_ports,
        build_modelo_edit_receipt_repository,
    )

    definitions = build_modelo_lifecycle_operation_definitions(
        profile_resolver=inputs.modelo_profile(),
        certificate_secret_backend_factory=build_certificate_secret_backend,
        operator_scope_ports=inputs.scope,
        export_ports_factory=inputs.modelo_exports(),
        # The calculation report's provenance key is derived from the profile's
        # existing review-package signing key, so the export enrolment is bound
        # to the adapter that already owns that key's custody.
        signing_keypair_capability_factory=build_review_package_signing_keypair_capability,
        # The summary PDF writer is the same adapter the command line hands the
        # report service, so both surfaces draw one revision's summary with one
        # writer. It imports ReportLab only when it draws.
        calculation_summary_pdf_writer=write_calculation_summary_pdf,
        calculation_action_ports_factory=inputs.calculation_actions(),
        attachment_store_factory=inputs.attachments(),
        amendment_action_ports_factory=_supplied(inputs.amendment_action_ports_factory, build_amendment_action_ports),
        filing_action_ports_factory=_supplied(inputs.filing_action_ports_factory, build_filing_action_ports),
        work_lifecycle_ports_factory=inputs.work_lifecycle(),
        receipt_repository_factory=_supplied(
            inputs.modelo_edit_receipt_repository_factory, build_modelo_edit_receipt_repository
        ),
        verification_repository_bundle_factory=inputs.verification_bundle(),
        edit_prerequisite_observer=inputs.edit_prerequisites.retain,
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return _built(
        definitions,
        build_modelo_lifecycle_operation_registrations(
            definitions,
            metadata_access_resolver=compose_modelo_metadata_access(inputs.work_lifecycle()),
            revision_access_resolver=compose_modelo_revision_access(inputs.verification_bundle()),
        ),
    )


def _modelo_workbench_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.workbench_operations import (
        build_modelo_workbench_operation_definitions,
        build_modelo_workbench_operation_registrations,
        compose_modelo_workbench_access,
    )

    definitions = build_modelo_workbench_operation_definitions(
        ports_factory=_supplied(inputs.modelo_workbench_read_ports_factory, _build_modelo_workbench_read_ports),
        contracts=inputs.registry_contracts,
        prerequisites=inputs.edit_prerequisites,
    )
    return _built(
        definitions,
        build_modelo_workbench_operation_registrations(
            definitions, access_resolver=compose_modelo_workbench_access(inputs.work_lifecycle())
        ),
    )


def _modelo_query_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.query_read_operation import (
        build_modelo_bindings_list_definition,
        build_modelo_bindings_list_registration,
        build_modelo_bindings_resolve_definition,
        build_modelo_bindings_resolve_registration,
        build_modelo_readiness_definition,
        build_modelo_readiness_registration,
        build_modelo_requires_definition,
        build_modelo_requires_registration,
    )
    from .modelo_query_read_operation_composition import build_modelo_query_read_ports

    bindings_list = build_modelo_bindings_list_definition()
    bindings_resolve = build_modelo_bindings_resolve_definition()
    requires = build_modelo_requires_definition()
    readiness = build_modelo_readiness_definition(
        _supplied(inputs.modelo_query_read_ports_factory, build_modelo_query_read_ports)
    )
    return _built(
        (bindings_list, bindings_resolve, requires, readiness),
        (
            build_modelo_bindings_list_registration(bindings_list),
            build_modelo_bindings_resolve_registration(bindings_resolve),
            build_modelo_requires_registration(requires),
            build_modelo_readiness_registration(readiness),
        ),
    )


def _modelo_typed_query_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.typed_query_operation import (
        build_modelo_bindings_resolve_typed_definition,
        build_modelo_bindings_resolve_typed_registration,
        build_modelo_readiness_summary_definition,
        build_modelo_readiness_summary_registration,
    )
    from .modelo_query_read_operation_composition import build_modelo_query_read_ports

    resolve_typed = build_modelo_bindings_resolve_typed_definition()
    readiness_summary = build_modelo_readiness_summary_definition(
        _supplied(inputs.modelo_query_read_ports_factory, build_modelo_query_read_ports)
    )
    return _built(
        (resolve_typed, readiness_summary),
        (
            build_modelo_bindings_resolve_typed_registration(resolve_typed),
            build_modelo_readiness_summary_registration(readiness_summary),
        ),
    )


def _modelo_calculation_report_verification_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.calculation_report_verification_operation import (
        build_modelo_calculation_report_verify_definition,
        build_modelo_calculation_report_verify_registration,
    )
    from .calculation_report_verification_operation_composition import (
        build_modelo_calculation_report_verification_ports,
    )

    del inputs
    definition = build_modelo_calculation_report_verify_definition(build_modelo_calculation_report_verification_ports)
    return _built((definition,), (build_modelo_calculation_report_verify_registration(definition),))


def _modelo_review_package_recipient_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.review_package_recipient_operations import (
        build_review_package_recipient_add_definition,
        build_review_package_recipient_add_registration,
        build_review_package_recipient_list_definition,
        build_review_package_recipient_list_registration,
        build_review_package_recipient_remove_definition,
        build_review_package_recipient_remove_registration,
    )

    registry, events = inputs.recipient_registry(), inputs.recipient_events()
    add = build_review_package_recipient_add_definition(registry, events)
    listing = build_review_package_recipient_list_definition(registry)
    remove = build_review_package_recipient_remove_definition(registry, events)
    return _built(
        (add, listing, remove),
        (
            build_review_package_recipient_add_registration(add),
            build_review_package_recipient_list_registration(listing),
            build_review_package_recipient_remove_registration(remove),
        ),
    )


def _modelo_quickfile_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.quickfile_operation import build_quickfile_definition, build_quickfile_registration
    from .quickfile_operation_composition import build_quickfile_operation_ports

    definition = build_quickfile_definition(
        build_quickfile_operation_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_quickfile_registration(definition),))


def _modelo_m036_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.m036_operation import (
        build_m036_operation_definitions,
        build_m036_operation_registrations,
    )
    from .m036_operation_composition import build_m036_operation_ports

    del inputs
    definitions = build_m036_operation_definitions(build_m036_operation_ports)
    return _built(definitions, build_m036_operation_registrations(definitions))


def _modelo_audit_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.audit_operation import (
        build_modelo_audit_operation_definitions,
        build_modelo_audit_operation_registrations,
    )
    from .modelo_audit_operation_composition import build_modelo_audit_operation_ports

    del inputs
    definitions = build_modelo_audit_operation_definitions(build_modelo_audit_operation_ports)
    return _built(definitions, build_modelo_audit_operation_registrations(definitions))


def _modelo_maritime_preview_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.maritime_preview_operation import (
        build_modelo_maritime_preview_definition,
        build_modelo_maritime_preview_registration,
    )
    from .modelo_maritime_operation_composition import build_modelo_maritime_preview_ports

    del inputs
    definition = build_modelo_maritime_preview_definition(build_modelo_maritime_preview_ports)
    return _built((definition,), (build_modelo_maritime_preview_registration(definition),))


def _modelo_spreadsheet_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.modelo_spreadsheet_operation import build_modelo_spreadsheet_definitions
    from ..application.modelo.modelo_spreadsheet_registration import build_modelo_spreadsheet_registration
    from .modelo_spreadsheet_operation_composition import build_modelo_spreadsheet_operation_ports

    del inputs
    definitions = build_modelo_spreadsheet_definitions(build_modelo_spreadsheet_operation_ports)
    return _built(definitions, (build_modelo_spreadsheet_registration(definition) for definition in definitions))


def _modelo_review_package_exchange_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.review_package_exchange_operation import (
        build_review_package_exchange_operation_definitions,
        build_review_package_exchange_operation_registrations,
    )
    from .review_package_exchange_operation_composition import build_review_package_exchange_operation_ports

    definitions = build_review_package_exchange_operation_definitions(
        build_review_package_exchange_operation_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return _built(definitions, build_review_package_exchange_operation_registrations(definitions))


def _modelo_m145_communication_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.outbound.aeat.export.registry_record_renderer import RegistryFixedWidthRecordRenderer
    from ..adapters.persistence.profile.m145_communication_records import build_m145_communication_records_ports
    from ..application.modelo.m145_communication_operation import (
        build_m145_communication_operation_definitions,
        build_m145_communication_operation_registrations,
    )

    definitions = build_m145_communication_operation_definitions(
        records_ports_factory=build_m145_communication_records_ports,
        renderer_factory=RegistryFixedWidthRecordRenderer,
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return _built(definitions, build_m145_communication_operation_registrations(definitions))


def _modelo_reconciliation_export_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.reconciliation_export_operation import (
        build_reconciliation_export_xlsx_definition,
        build_reconciliation_export_xlsx_registration,
    )
    from .reconciliation_export_operation_composition import build_reconciliation_export_xlsx_ports

    del inputs
    definition = build_reconciliation_export_xlsx_definition(build_reconciliation_export_xlsx_ports)
    return _built((definition,), (build_reconciliation_export_xlsx_registration(definition),))


def _modelo_metadata_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.metadata_read_operation import (
        build_modelo_metadata_definition,
        build_modelo_metadata_registration,
    )

    lifecycle = inputs.work_lifecycle()
    definition = build_modelo_metadata_definition(lifecycle)
    return _built((definition,), (build_modelo_metadata_registration(definition, lifecycle),))


def _modelo_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.history_operation import (
        build_modelo_work_history_definition,
        build_modelo_work_history_registration,
    )

    history = inputs.modelo_history()
    definition = build_modelo_work_history_definition(history)
    return _built((definition,), (build_modelo_work_history_registration(definition, history),))


def _modelo_lifecycle_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.lifecycle_history_operation import (
        build_modelo_history_definition,
        build_modelo_history_registration,
    )

    definition = build_modelo_history_definition(inputs.modelo_history())
    return _built((definition,), (build_modelo_history_registration(definition),))


def _modelo_history_timeline_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.history_timeline_operation import (
        build_modelo_history_timeline_definition,
        build_modelo_history_timeline_registration,
    )

    definition = build_modelo_history_timeline_definition(inputs.modelo_history())
    return _built((definition,), (build_modelo_history_timeline_registration(definition),))


def _modelo_projection_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.persistence.profile.guarded_calculation_revision_migration import (
        GuardedCalculationRevisionMigration,
    )
    from ..application.modelo.projection_operation import (
        build_modelo_compare_definition,
        build_modelo_compare_registration,
        build_modelo_project_definition,
        build_modelo_project_registration,
    )

    migration = GuardedCalculationRevisionMigration()
    project = build_modelo_project_definition(factory=inputs.calculation_actions(), migration=migration)
    compare = build_modelo_compare_definition(factory=inputs.calculation_actions(), migration=migration)
    return _built(
        (project, compare), (build_modelo_project_registration(project), build_modelo_compare_registration(compare))
    )


def _modelo_reconciliation_import_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.reconciliation_import_operation import (
        build_modelo_reconciliation_import_definition,
        build_modelo_reconciliation_import_registration,
    )

    definition = build_modelo_reconciliation_import_definition(execution_caller_reader=inputs.execution_caller_reader)
    return _built((definition,), (build_modelo_reconciliation_import_registration(definition),))


def _modelo_reconciliation_pull_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.reconciliation_pull_operation import (
        build_modelo_reconciliation_pull_definition,
        build_modelo_reconciliation_pull_registration,
    )
    from .justificante_composition import build_justificante_capture_service, load_reconciliation_filed_observation

    definition = build_modelo_reconciliation_pull_definition(
        build_justificante_capture_service,
        load_reconciliation_filed_observation,
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return _built((definition,), (build_modelo_reconciliation_pull_registration(definition),))


def _modelo_reconciliation_list_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.reconciliation_list_operation import (
        build_modelo_reconciliation_list_definition,
        build_modelo_reconciliation_list_registration,
    )

    del inputs
    definition = build_modelo_reconciliation_list_definition()
    return _built((definition,), (build_modelo_reconciliation_list_registration(definition),))


def _modelo_work_inventory_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.work_inventory_operation import (
        build_modelo_work_list_definition,
        build_modelo_work_list_registration,
    )

    definition = build_modelo_work_list_definition(inputs.work_lifecycle())
    return _built((definition,), (build_modelo_work_list_registration(definition),))


def _modelo_work_create_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.work_create_operation import (
        build_modelo_work_create_definition,
        build_modelo_work_create_registration,
    )

    definition = build_modelo_work_create_definition(
        inputs.work_lifecycle(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_modelo_work_create_registration(definition),))


def _modelo_work_review_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.work_review_operation import (
        build_modelo_work_review_definition,
        build_modelo_work_review_registration,
    )

    history = inputs.modelo_history()
    definition = build_modelo_work_review_definition(history)
    return _built((definition,), (build_modelo_work_review_registration(definition, history),))


def _modelo_dependency_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.dependency_operation import (
        build_modelo_dependency_definition,
        build_modelo_dependency_registration,
    )
    from .modelo_dependency_composition import build_dependency_read_ports

    definition = build_modelo_dependency_definition(
        _supplied(inputs.dependency_read_ports_factory, build_dependency_read_ports)
    )
    return _built((definition,), (build_modelo_dependency_registration(definition),))


def _modelo_aggregate_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.aggregate_operation import (
        build_modelo_aggregate_operation_definition,
        build_modelo_aggregate_operation_registration,
    )

    definition = build_modelo_aggregate_operation_definition(
        _supplied(inputs.modelo_aggregate_operation_ports_factory, _build_modelo_aggregate_operation_ports)
    )
    return _built((definition,), (build_modelo_aggregate_operation_registration(definition),))


def _modelo_invoice_withholding_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.invoice_withholding_capture_operation import (
        build_modelo_invoice_withholding_capture_definition,
        build_modelo_invoice_withholding_capture_registration,
    )

    definition = build_modelo_invoice_withholding_capture_definition(
        _supplied(
            inputs.modelo_invoice_withholding_capture_ports_factory, _build_modelo_invoice_withholding_capture_ports
        )
    )
    return _built((definition,), (build_modelo_invoice_withholding_capture_registration(definition),))


def _modelo_wizard_context_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.wizard_context_operation import (
        build_modelo_work_wizard_context_definition,
        build_modelo_work_wizard_context_registration,
    )

    lifecycle = inputs.work_lifecycle()
    definition = build_modelo_work_wizard_context_definition(lifecycle)
    return _built((definition,), (build_modelo_work_wizard_context_registration(definition, lifecycle),))


def _modelo_wizard_attempt_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.wizard_attempt_operation import (
        build_modelo_work_wizard_attempt_definition,
        build_modelo_work_wizard_attempt_registration,
    )

    definition = build_modelo_work_wizard_attempt_definition(
        calculation_action_ports_factory=inputs.calculation_actions(),
        attachment_store_factory=inputs.attachments(),
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return _built((definition,), (build_modelo_work_wizard_attempt_registration(definition, inputs.work_lifecycle()),))


def _modelo_revision_selection_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.revision_selection_operation import (
        build_modelo_work_revision_definition,
        build_modelo_work_revision_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_work_revision_definition(bundle)
    return _built((definition,), (build_modelo_work_revision_registration(definition, bundle),))


def _modelo_revision_inventory_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.revision_inventory_operation import (
        build_modelo_work_revisions_definition,
        build_modelo_work_revisions_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_work_revisions_definition(bundle)
    return _built((definition,), (build_modelo_work_revisions_registration(definition, bundle),))


def _modelo_revision_snapshot_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.revision_operation_access import compose_modelo_revision_access
    from ..application.modelo.revision_snapshot_operation import (
        build_modelo_work_revision_snapshot_definition,
        build_modelo_work_revision_snapshot_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_work_revision_snapshot_definition(bundle)
    return _built(
        (definition,),
        (
            build_modelo_work_revision_snapshot_registration(
                definition, access_resolver=compose_modelo_revision_access(bundle)
            ),
        ),
    )


def _modelo_filing_selection_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.filing_selection_operation import (
        build_modelo_work_filing_record_definition,
        build_modelo_work_filing_record_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_work_filing_record_definition(bundle)
    return _built((definition,), (build_modelo_work_filing_record_registration(definition, bundle),))


def _modelo_filing_record_list_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.filing_record_list_operation import (
        build_modelo_filing_record_list_definition,
        build_modelo_filing_record_list_registration,
    )

    definition = build_modelo_filing_record_list_definition(inputs.verification_bundle())
    return _built((definition,), (build_modelo_filing_record_list_registration(definition),))


def _modelo_filing_record_import_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.filing_record_import_operation import (
        build_modelo_filing_record_import_definition,
        build_modelo_filing_record_import_registration,
    )

    calculations = inputs.calculation_actions()
    definition = build_modelo_filing_record_import_definition(
        calculations, execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_modelo_filing_record_import_registration(definition, calculations),))


def _modelo_filing_record_view_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.filing_record_view_operation import (
        build_modelo_filing_record_view_definition,
        build_modelo_filing_record_view_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_filing_record_view_definition(bundle)
    return _built((definition,), (build_modelo_filing_record_view_registration(definition, bundle),))


def _modelo_taxation_comparison_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.persistence.profile.taxation_comparison import build_taxation_comparison_ports
    from ..application.modelo.taxation_comparison_operation import (
        build_modelo_taxation_comparison_definition,
        build_modelo_taxation_comparison_registration,
    )

    del inputs
    definition = build_modelo_taxation_comparison_definition(build_taxation_comparison_ports)
    return _built(
        (definition,), (build_modelo_taxation_comparison_registration(definition, build_taxation_comparison_ports),)
    )


def _modelo_local_observation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.local_observation_operation import (
        build_modelo_local_observation_definition,
        build_modelo_local_observation_registration,
    )

    definition = build_modelo_local_observation_definition(
        inputs.calculation_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_modelo_local_observation_registration(definition),))


def _modelo_verification_report_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.verification_report_read_operation import (
        build_modelo_verification_report_list_definition,
        build_modelo_verification_report_list_registration,
        build_modelo_verification_report_view_definition,
        build_modelo_verification_report_view_registration,
    )

    bundle = inputs.verification_bundle()
    listing = build_modelo_verification_report_list_definition(bundle)
    view = build_modelo_verification_report_view_definition(bundle)
    return _built(
        (listing, view),
        (
            build_modelo_verification_report_list_registration(listing, bundle),
            build_modelo_verification_report_view_registration(view, bundle),
        ),
    )


def _modelo_amendment_context_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.amendment_context_operation import (
        build_modelo_work_amendment_context_definition,
        build_modelo_work_amendment_context_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_work_amendment_context_definition(bundle)
    return _built((definition,), (build_modelo_work_amendment_context_registration(definition, bundle),))


def _modelo_m303_attestation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.m303_attestation_operation import (
        build_modelo_work_m303_attestation_definition,
        build_modelo_work_m303_attestation_registration,
    )
    from ..application.modelo.metadata_operation_access import compose_modelo_metadata_access

    lifecycle = inputs.work_lifecycle()
    definition = build_modelo_work_m303_attestation_definition(
        work_lifecycle_ports_factory=lifecycle,
        attachment_store_factory=inputs.attachments(),
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return _built(
        (definition,),
        (
            build_modelo_work_m303_attestation_registration(
                definition, access_resolver=compose_modelo_metadata_access(lifecycle)
            ),
        ),
    )


def _modelo_iva_wallet_correction_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.iva_wallet_correction_operation import (
        build_modelo_iva_wallet_correction_definition,
        build_modelo_iva_wallet_correction_registration,
    )
    from .adapter_composition import build_modelo_iva_wallet_seed_ports

    del inputs
    definition = build_modelo_iva_wallet_correction_definition(build_modelo_iva_wallet_seed_ports)
    return _built((definition,), (build_modelo_iva_wallet_correction_registration(definition),))


def _modelo_iva_wallet_balance_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.iva_wallet_balance_operation import (
        build_modelo_iva_wallet_balance_definition,
        build_modelo_iva_wallet_balance_registration,
    )
    from .adapter_composition import build_modelo_iva_wallet_seed_ports

    del inputs
    definition = build_modelo_iva_wallet_balance_definition(build_modelo_iva_wallet_seed_ports)
    return _built((definition,), (build_modelo_iva_wallet_balance_registration(definition),))


def _modelo_iva_wallet_seed_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.iva_wallet_seed_operation import (
        build_modelo_iva_wallet_seed_definition,
        build_modelo_iva_wallet_seed_registration,
    )
    from .adapter_composition import build_modelo_iva_wallet_seed_ports

    del inputs
    definition = build_modelo_iva_wallet_seed_definition(build_modelo_iva_wallet_seed_ports)
    return _built((definition,), (build_modelo_iva_wallet_seed_registration(definition),))


def _modelo_iva_wallet_override_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.iva_wallet_override_operation import (
        build_modelo_iva_wallet_override_definition,
        build_modelo_iva_wallet_override_registration,
    )
    from .adapter_composition import build_modelo_iva_wallet_seed_ports

    del inputs
    definition = build_modelo_iva_wallet_override_definition(build_modelo_iva_wallet_seed_ports)
    return _built((definition,), (build_modelo_iva_wallet_override_registration(definition),))


def _modelo_review_package_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.modelo.review_package_operation import (
        build_modelo_review_package_build_definition,
        build_modelo_review_package_build_registration,
    )
    from ..application.modelo.revision_operation_access import compose_modelo_revision_access

    bundle = inputs.verification_bundle()
    definition = build_modelo_review_package_build_definition(
        profile_resolver=inputs.modelo_profile(),
        export_ports_factory=inputs.modelo_exports(),
        repositories=bundle,
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return _built(
        (definition,),
        (
            build_modelo_review_package_build_registration(
                definition, access_resolver=compose_modelo_revision_access(bundle)
            ),
        ),
    )


def _modelo_m360_solicitud_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.persistence.profile.modelo_360_solicitud import Modelo360SolicitudRepository
    from ..application.modelo.m360_solicitud_operation import (
        build_modelo_360_solicitud_definition,
        build_modelo_360_solicitud_registration,
    )

    definition = build_modelo_360_solicitud_definition(Modelo360SolicitudRepository, inputs.own_accounts)
    return _built((definition,), (build_modelo_360_solicitud_registration(definition),))


# -- workflow and overview ---------------------------------------------------------------------------------------------


def _workflow_run_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.workflow.run_read_operation import (
        build_workflow_run_list_definition,
        build_workflow_run_list_registration,
        build_workflow_run_read_definition,
        build_workflow_run_read_registration,
    )

    runs = inputs.workflow_runs()
    read = build_workflow_run_read_definition(runs)
    listing = build_workflow_run_list_definition(runs)
    return _built(
        (read, listing),
        (build_workflow_run_read_registration(read, runs), build_workflow_run_list_registration(listing, runs)),
    )


def _workflow_resume_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.workflow.resume_operation import (
        build_workflow_resume_definition,
        build_workflow_resume_registration,
    )

    definition = build_workflow_resume_definition(inputs.workflow_runs(), inputs.calculation_actions())
    return _built((definition,), (build_workflow_resume_registration(definition),))


def _overview_pipeline_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.overview.pipeline_operation import (
        build_overview_pipeline_definition,
        build_overview_pipeline_registration,
    )
    from .overview_pipeline_composition import build_pipeline_read_ports

    definition = build_overview_pipeline_definition(
        _supplied(inputs.pipeline_read_ports_factory, build_pipeline_read_ports)
    )
    return _built((definition,), (build_overview_pipeline_registration(definition),))


def _overview_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.overview.read_operation import build_overview_read_definition, build_overview_read_registration
    from ..application.overview.read_request import OverviewReadKind
    from .overview_read_composition import build_overview_read_ports

    ports = _supplied(inputs.overview_read_ports_factory, build_overview_read_ports)
    definitions = tuple(build_overview_read_definition(kind, ports) for kind in OverviewReadKind)
    return _built(definitions, (build_overview_read_registration(definition) for definition in definitions))


# -- invoices ----------------------------------------------------------------------------------------------------------


def _invoices_catalogue_add_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
    from ..application.invoices.catalogue_add_operation import (
        build_invoice_add_definition,
        build_invoice_add_registration,
    )

    definition = build_invoice_add_definition(
        _supplied(inputs.invoice_creation_ports_factory, build_catalogue_creation_ports),
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return _built((definition,), (build_invoice_add_registration(definition),))


def _invoices_catalogue_intake_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.invoices.catalogue_intake_operation import (
        build_invoice_import_definition,
        build_invoice_intake_registration,
        build_invoice_wizard_definition,
    )
    from .invoice_intake_operation_composition import build_invoice_intake_ports

    imported = build_invoice_import_definition(build_invoice_intake_ports)
    wizard = build_invoice_wizard_definition(
        build_invoice_intake_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return _built(
        (imported, wizard), (build_invoice_intake_registration(imported), build_invoice_intake_registration(wizard))
    )


def _invoices_catalogue_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.invoices.catalogue_read_operation import (
        build_invoice_list_definition,
        build_invoice_list_registration,
        build_invoice_view_definition,
        build_invoice_view_registration,
    )

    inspection = inputs.invoice_inspection()
    listing = build_invoice_list_definition(inspection)
    view = build_invoice_view_definition(inspection)
    return _built((listing, view), (build_invoice_list_registration(listing), build_invoice_view_registration(view)))


def _invoices_catalogue_remove_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.invoices.catalogue_remove_operation import (
        build_invoice_remove_definition,
        build_invoice_remove_registration,
    )

    definition = build_invoice_remove_definition(inputs.invoice_lifecycle())
    return _built((definition,), (build_invoice_remove_registration(definition),))


def _invoices_catalogue_update_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.invoices.catalogue_update_operation import (
        build_invoice_update_definition,
        build_invoice_update_registration,
    )

    definition = build_invoice_update_definition(
        inputs.invoice_lifecycle(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_invoice_update_registration(definition),))


# -- ledger ------------------------------------------------------------------------------------------------------------


def _ledger_evidence_followup_registration(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.evidence_followup_registration import (
        build_ledger_evidence_followup_definitions,
        build_ledger_evidence_followup_registrations,
        build_ledger_evidence_review_summary_definition,
        build_ledger_evidence_review_summary_registration,
    )
    from .evidence_followup_operation_composition import build_ledger_evidence_followup_operation_ports

    ports = inputs.evidence_followup_ports or build_ledger_evidence_followup_operation_ports(
        settings=inputs.resolved_settings
    )
    followups = build_ledger_evidence_followup_definitions(ports)
    summary = build_ledger_evidence_review_summary_definition(ports)
    return _built(
        (*followups, summary),
        (
            *build_ledger_evidence_followup_registrations(followups),
            build_ledger_evidence_review_summary_registration(summary),
        ),
    )


def _ledger_evidence_ingestion_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.evidence_ingestion_operation import (
        build_ledger_evidence_ingestion_definitions,
        build_ledger_evidence_ingestion_registrations,
    )
    from .ledger_evidence_ingestion_operation_composition import build_ledger_evidence_ingestion_operation_ports

    del inputs
    definitions = build_ledger_evidence_ingestion_definitions(build_ledger_evidence_ingestion_operation_ports)
    return _built(definitions, build_ledger_evidence_ingestion_registrations(definitions))


def _ledger_ratios_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.ratios_operation import (
        build_ledger_ratios_eligible_definition,
        build_ledger_ratios_eligible_registration,
        build_ledger_ratios_list_definition,
        build_ledger_ratios_list_registration,
        build_ledger_ratios_set_definition,
        build_ledger_ratios_set_registration,
        build_ledger_ratios_unset_definition,
        build_ledger_ratios_unset_registration,
        build_ledger_ratios_validate_definition,
        build_ledger_ratios_validate_registration,
    )

    caller = inputs.execution_caller_reader
    listing = build_ledger_ratios_list_definition()
    ratios_set = build_ledger_ratios_set_definition(execution_caller_reader=caller)
    unset = build_ledger_ratios_unset_definition(execution_caller_reader=caller)
    eligible = build_ledger_ratios_eligible_definition()
    validate = build_ledger_ratios_validate_definition()
    return _built(
        (listing, ratios_set, unset, eligible, validate),
        (
            build_ledger_ratios_list_registration(listing),
            build_ledger_ratios_set_registration(ratios_set),
            build_ledger_ratios_unset_registration(unset),
            build_ledger_ratios_eligible_registration(eligible),
            build_ledger_ratios_validate_registration(validate),
        ),
    )


def _ledger_llm_diagnostics_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.llm_diagnostics_operation import (
        build_ledger_llm_diagnostics_definition,
        build_ledger_llm_diagnostics_registration,
    )
    from .ledger_llm_diagnostics_composition import build_ledger_llm_diagnostics_operation_ports

    del inputs
    definition = build_ledger_llm_diagnostics_definition(build_ledger_llm_diagnostics_operation_ports)
    return _built((definition,), (build_ledger_llm_diagnostics_registration(definition),))


def _ledger_status_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.status_operation import build_ledger_status_definition, build_ledger_status_registration

    definition = build_ledger_status_definition(inputs.ledger_actions(), inputs.verification_bundle())
    return _built((definition,), (build_ledger_status_registration(definition),))


def _ledger_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.history_operation import (
        build_ledger_history_definition,
        build_ledger_history_registration,
        build_ledger_history_typed_definition,
        build_ledger_history_typed_registration,
    )

    reads = inputs.ledger_reads()
    history = build_ledger_history_definition(reads)
    typed = build_ledger_history_typed_definition(reads)
    return _built(
        (history, typed), (build_ledger_history_registration(history), build_ledger_history_typed_registration(typed))
    )


def _ledger_export_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.export_operation import build_ledger_export_definition, build_ledger_export_registration
    from .ledger_export_link_operation_composition import build_ledger_export_link_operation_ports

    definition = build_ledger_export_definition(
        build_ledger_export_link_operation_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_export_registration(definition),))


def _ledger_link_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.link_operation import build_ledger_link_definition, build_ledger_link_registration
    from .ledger_export_link_operation_composition import build_ledger_export_link_operation_ports

    definition = build_ledger_link_definition(
        build_ledger_export_link_operation_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_link_registration(definition),))


def _ledger_import_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.exchange_rate_provider import exchange_rate_provider
    from ..application.ledger.import_operation import (
        LedgerImportOperationPorts,
        build_ledger_import_definition,
        build_ledger_import_registration,
    )
    from ..domain.currency.service import CurrencyNormalizationService
    from .ledger_action_composition import compose_ledger_import_ports

    ledger_actions, own_accounts = inputs.ledger_actions(), inputs.own_accounts

    def import_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerImportOperationPorts:
        ledger_ports = ledger_actions(bucket_id=bucket_id, operation=operation)
        return LedgerImportOperationPorts(
            import_ports=compose_ledger_import_ports(),
            transaction_repository=ledger_ports.transaction_repository,
            bucket_event_repository=ledger_ports.bucket_event_repository,
            currency_normalizer=CurrencyNormalizationService(rate_provider=exchange_rate_provider()),
            operation=operation,
            own_accounts=own_accounts(bucket_id=bucket_id),
        )

    definition = build_ledger_import_definition(import_ports, execution_caller_reader=inputs.execution_caller_reader)
    return _built((definition,), (build_ledger_import_registration(definition),))


def _ledger_add_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.add_operation import build_ledger_add_definition, build_ledger_add_registration
    from .adapter_composition import build_prorrata_register_repository

    definition = build_ledger_add_definition(
        inputs.ledger_actions(),
        build_prorrata_register_repository,
        inputs.own_accounts,
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return _built((definition,), (build_ledger_add_registration(definition),))


def _ledger_allocate_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.allocate_operation import (
        build_ledger_allocate_definition,
        build_ledger_allocate_registration,
    )

    definition = build_ledger_allocate_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_allocate_registration(definition),))


def _ledger_classify_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.classify_operation import (
        build_ledger_classify_definition,
        build_ledger_classify_registration,
    )

    definition = build_ledger_classify_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_classify_registration(definition),))


def _ledger_operator_iva_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.operator_iva_operation import (
        build_ledger_operator_iva_definition,
        build_ledger_operator_iva_registration,
    )

    definition = build_ledger_operator_iva_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_operator_iva_registration(definition),))


def _ledger_llm_review_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.llm_review_contracts import (
        LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
        LEDGER_SPLIT_REVIEW_DEFINITION_ID,
    )
    from ..application.ledger.llm_review_execution import LedgerLlmOperationPorts
    from ..application.ledger.llm_review_operation import (
        build_ledger_llm_review_definition,
        build_ledger_llm_review_registration,
    )

    ledger_actions, settings = inputs.ledger_actions(), inputs.resolved_settings

    def llm_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerLlmOperationPorts:
        from .ledger_llm_composition import compose_ledger_llm

        return LedgerLlmOperationPorts(
            ledger=ledger_actions(bucket_id=bucket_id, operation=operation),
            llm=compose_ledger_llm(bucket_id=bucket_id, settings=settings).ports,
            settings=settings,
        )

    caller = inputs.execution_caller_reader
    classify = build_ledger_llm_review_definition(
        LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, llm_ports, execution_caller_reader=caller
    )
    split = build_ledger_llm_review_definition(
        LEDGER_SPLIT_REVIEW_DEFINITION_ID, llm_ports, execution_caller_reader=caller
    )
    return _built(
        (classify, split), (build_ledger_llm_review_registration(classify), build_ledger_llm_review_registration(split))
    )


def _ledger_bulk_classify_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.bulk_classify_operation import (
        build_ledger_bulk_classify_definition,
        build_ledger_bulk_classify_registration,
    )

    definition = build_ledger_bulk_classify_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_bulk_classify_registration(definition),))


def _ledger_rule_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.rule_operation import (
        build_ledger_rule_add_definition,
        build_ledger_rule_add_registration,
        build_ledger_rule_apply_definition,
        build_ledger_rule_apply_registration,
        build_ledger_rule_list_definition,
        build_ledger_rule_list_registration,
    )

    rules, caller = inputs.ledger_rules(), inputs.execution_caller_reader
    add = build_ledger_rule_add_definition(rules, execution_caller_reader=caller)
    listing = build_ledger_rule_list_definition(rules)
    apply = build_ledger_rule_apply_definition(inputs.ledger_actions(), rules, execution_caller_reader=caller)
    return _built(
        (add, listing, apply),
        (
            build_ledger_rule_add_registration(add),
            build_ledger_rule_list_registration(listing),
            build_ledger_rule_apply_registration(apply),
        ),
    )


def _ledger_evidence_add_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.evidence_add_operation import (
        build_ledger_evidence_add_definition,
        build_ledger_evidence_add_registration,
    )
    from .adapter_composition import build_ledger_evidence_ports

    definition = build_ledger_evidence_add_definition(
        build_ledger_evidence_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_evidence_add_registration(definition),))


def _ledger_evidence_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.evidence_read_operation import (
        build_ledger_evidence_list_definition,
        build_ledger_evidence_list_registration,
        build_ledger_evidence_query_definition,
        build_ledger_evidence_query_registration,
        build_ledger_evidence_view_definition,
        build_ledger_evidence_view_registration,
    )
    from .adapter_composition import build_ledger_evidence_ports

    del inputs
    listing = build_ledger_evidence_list_definition(build_ledger_evidence_ports)
    view = build_ledger_evidence_view_definition(build_ledger_evidence_ports)
    query = build_ledger_evidence_query_definition(build_ledger_evidence_ports)
    return _built(
        (listing, view, query),
        (
            build_ledger_evidence_list_registration(listing),
            build_ledger_evidence_view_registration(view),
            build_ledger_evidence_query_registration(query),
        ),
    )


def _ledger_evidence_mutation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.evidence_mutation_operation import (
        build_ledger_evidence_remove_definition,
        build_ledger_evidence_remove_registration,
        build_ledger_evidence_update_definition,
        build_ledger_evidence_update_registration,
    )
    from .adapter_composition import build_ledger_evidence_ports

    caller = inputs.execution_caller_reader
    update = build_ledger_evidence_update_definition(build_ledger_evidence_ports, execution_caller_reader=caller)
    remove = build_ledger_evidence_remove_definition(build_ledger_evidence_ports, execution_caller_reader=caller)
    return _built(
        (update, remove),
        (build_ledger_evidence_update_registration(update), build_ledger_evidence_remove_registration(remove)),
    )


def _ledger_invoice_evidence_readiness_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.invoice_evidence_readiness_operation import (
        build_ledger_evidence_reader_readiness_definition,
        build_ledger_evidence_reader_readiness_registration,
    )
    from ..application.local_reader import read_local_reader_status

    del inputs
    definition = build_ledger_evidence_reader_readiness_definition(read_local_reader_status)
    return _built((definition,), (build_ledger_evidence_reader_readiness_registration(definition),))


def _ledger_invoice_evidence_extract_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.invoice_evidence_extract_operation import (
        build_ledger_evidence_extract_definition,
        build_ledger_evidence_extract_registration,
    )
    from .invoice_evidence_operation_composition import build_invoice_evidence_operation_ports

    del inputs
    definition = build_ledger_evidence_extract_definition(build_invoice_evidence_operation_ports)
    return _built((definition,), (build_ledger_evidence_extract_registration(definition),))


def _ledger_invoice_evidence_confirm_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.invoice_evidence_confirm_operation import (
        build_ledger_evidence_confirm_definition,
        build_ledger_evidence_confirm_registration,
    )
    from .invoice_evidence_operation_composition import build_invoice_evidence_operation_ports

    del inputs
    definition = build_ledger_evidence_confirm_definition(build_invoice_evidence_operation_ports)
    return _built((definition,), (build_ledger_evidence_confirm_registration(definition),))


def _ledger_split_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.split_operation import build_ledger_split_definition, build_ledger_split_registration

    definition = build_ledger_split_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_split_registration(definition),))


def _ledger_merge_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.merge_operation import build_ledger_merge_definition, build_ledger_merge_registration

    definition = build_ledger_merge_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_merge_registration(definition),))


def _ledger_update_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.update_operation import build_ledger_update_definition, build_ledger_update_registration

    definition = build_ledger_update_definition(
        inputs.ledger_actions(), inputs.own_accounts, execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_update_registration(definition),))


def _ledger_attachment_mutation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.attachment_mutation_operation import (
        build_ledger_attach_definition,
        build_ledger_attach_registration,
        build_ledger_detach_definition,
        build_ledger_detach_registration,
    )

    actions, caller = inputs.ledger_actions(), inputs.execution_caller_reader
    attach = build_ledger_attach_definition(actions, execution_caller_reader=caller)
    detach = build_ledger_detach_definition(actions, execution_caller_reader=caller)
    return _built(
        (attach, detach), (build_ledger_attach_registration(attach), build_ledger_detach_registration(detach))
    )


def _ledger_lifecycle_mutation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.lifecycle_mutation_operation import (
        build_ledger_archive_definition,
        build_ledger_archive_registration,
        build_ledger_exclude_definition,
        build_ledger_exclude_registration,
        build_ledger_restore_definition,
        build_ledger_restore_registration,
        build_ledger_stash_definition,
        build_ledger_stash_registration,
    )

    actions, caller = inputs.ledger_actions(), inputs.execution_caller_reader
    archive = build_ledger_archive_definition(actions, execution_caller_reader=caller)
    stash = build_ledger_stash_definition(actions, execution_caller_reader=caller)
    restore = build_ledger_restore_definition(actions, execution_caller_reader=caller)
    exclude = build_ledger_exclude_definition(actions, execution_caller_reader=caller)
    return _built(
        (archive, stash, restore, exclude),
        (
            build_ledger_archive_registration(archive),
            build_ledger_stash_registration(stash),
            build_ledger_restore_registration(restore),
            build_ledger_exclude_registration(exclude),
        ),
    )


def _ledger_remove_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.remove_operation import build_ledger_remove_definition, build_ledger_remove_registration

    definition = build_ledger_remove_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_remove_registration(definition),))


def _ledger_reset_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.reset_operation import build_ledger_reset_definition, build_ledger_reset_registration

    definition = build_ledger_reset_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_reset_registration(definition),))


def _ledger_counterparty_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.counterparty_operation import (
        build_ledger_counterparty_definition,
        build_ledger_counterparty_registration,
    )

    repository = inputs.counterparty_repository_factory
    if repository is None:
        from ..adapters.persistence.profile.counterparty_establishment import (
            build_counterparty_establishment_repository,
        )

        repository = build_counterparty_establishment_repository
    definition = build_ledger_counterparty_definition(
        repository, execution_caller_reader=inputs.execution_caller_reader
    )
    return _built((definition,), (build_ledger_counterparty_registration(definition),))


def _ledger_own_account_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.own_account_operation import (
        build_ledger_own_account_definition,
        build_ledger_own_account_registration,
    )

    definition = build_ledger_own_account_definition(inputs.own_accounts)
    return _built((definition,), (build_ledger_own_account_registration(definition),))


def _ledger_check_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.check_operation import build_ledger_check_definition, build_ledger_check_registration

    definition = build_ledger_check_definition(inputs.ledger_actions())
    return _built((definition,), (build_ledger_check_registration(definition),))


def _ledger_preflight_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.preflight_operation import (
        build_ledger_preflight_definition,
        build_ledger_preflight_registration,
    )

    definition = build_ledger_preflight_definition(inputs.ledger_actions())
    return _built((definition,), (build_ledger_preflight_registration(definition),))


def _ledger_review_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.review_operation import build_ledger_review_definition, build_ledger_review_registration

    definition = build_ledger_review_definition(inputs.ledger_actions())
    return _built((definition,), (build_ledger_review_registration(definition),))


def _ledger_list_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.list_operation import build_ledger_list_definition, build_ledger_list_registration

    definition = build_ledger_list_definition(inputs.ledger_reads())
    return _built((definition,), (build_ledger_list_registration(definition),))


def _ledger_view_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.view_operation import build_ledger_view_definition, build_ledger_view_registration

    definition = build_ledger_view_definition(inputs.ledger_actions())
    return _built((definition,), (build_ledger_view_registration(definition),))


def _ledger_track_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.track_operation import build_ledger_track_definition, build_ledger_track_registration

    definition = build_ledger_track_definition(inputs.ledger_actions(), inputs.ledger_participation())
    return _built((definition,), (build_ledger_track_registration(definition),))


def _ledger_participation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.participation_operation import (
        build_ledger_participation_definition,
        build_ledger_participation_registration,
    )

    definition = build_ledger_participation_definition(inputs.ledger_actions(), inputs.ledger_participation())
    return _built((definition,), (build_ledger_participation_registration(definition),))


def _ledger_participation_rebuild_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    from ..application.ledger.participation_rebuild_operation import (
        build_ledger_participation_rebuild_definition,
        build_ledger_participation_rebuild_registration,
    )
    from .adapter_composition import build_participation_index_rebuild_ports

    definition = build_ledger_participation_rebuild_definition(
        _supplied(inputs.participation_rebuild_ports_factory, build_participation_index_rebuild_ports)
    )
    return _built((definition,), (build_ledger_participation_rebuild_registration(definition),))


#: Every composition group, keyed by the module that owns its operations. A new
#: operation is enrolled here as well as in its owning module.
_OPERATION_COMPOSITION_GROUPS: Mapping[str, _GroupComposer] = {
    "application.actividad_asset.registered_operations": _actividad_asset_registered_operations,
    "application.auth.apoderado_operation": _auth_apoderado_operation,
    "application.auth.certificate_secret_operation": _auth_certificate_secret_operation,
    "application.auth.certificate_source_operation": _auth_certificate_source_operation,
    "application.auth.diagnostic_report_operation": _auth_diagnostic_report_operation,
    "application.auth.operation_definitions": _auth_operation_definitions,
    "application.auth.read_operation": _auth_read_operation,
    "application.bienes_inversion.registered_operation": _bienes_inversion_registered_operation,
    "application.diagnostics_operation": _diagnostics_operation,
    "application.export.calculation_review_xlsx_operation": _export_calculation_review_xlsx_operation,
    "application.export.google_operation": _export_google_operation,
    "application.export.google_review_operation": _export_google_review_operation,
    "application.inventory.registered_operation": _inventory_registered_operation,
    "application.invoices.catalogue_add_operation": _invoices_catalogue_add_operation,
    "application.invoices.catalogue_intake_operation": _invoices_catalogue_intake_operation,
    "application.invoices.catalogue_read_operation": _invoices_catalogue_read_operation,
    "application.invoices.catalogue_remove_operation": _invoices_catalogue_remove_operation,
    "application.invoices.catalogue_update_operation": _invoices_catalogue_update_operation,
    "application.ledger.add_operation": _ledger_add_operation,
    "application.ledger.allocate_operation": _ledger_allocate_operation,
    "application.ledger.attachment_mutation_operation": _ledger_attachment_mutation_operation,
    "application.ledger.bulk_classify_operation": _ledger_bulk_classify_operation,
    "application.ledger.check_operation": _ledger_check_operation,
    "application.ledger.classify_operation": _ledger_classify_operation,
    "application.ledger.counterparty_operation": _ledger_counterparty_operation,
    "application.ledger.evidence_add_operation": _ledger_evidence_add_operation,
    "application.ledger.evidence_followup_registration": _ledger_evidence_followup_registration,
    "application.ledger.evidence_ingestion_operation": _ledger_evidence_ingestion_operation,
    "application.ledger.evidence_mutation_operation": _ledger_evidence_mutation_operation,
    "application.ledger.evidence_read_operation": _ledger_evidence_read_operation,
    "application.ledger.export_operation": _ledger_export_operation,
    "application.ledger.history_operation": _ledger_history_operation,
    "application.ledger.import_operation": _ledger_import_operation,
    "application.ledger.invoice_evidence_confirm_operation": _ledger_invoice_evidence_confirm_operation,
    "application.ledger.invoice_evidence_extract_operation": _ledger_invoice_evidence_extract_operation,
    "application.ledger.invoice_evidence_readiness_operation": _ledger_invoice_evidence_readiness_operation,
    "application.ledger.lifecycle_mutation_operation": _ledger_lifecycle_mutation_operation,
    "application.ledger.link_operation": _ledger_link_operation,
    "application.ledger.list_operation": _ledger_list_operation,
    "application.ledger.llm_diagnostics_operation": _ledger_llm_diagnostics_operation,
    "application.ledger.llm_review_operation": _ledger_llm_review_operation,
    "application.ledger.merge_operation": _ledger_merge_operation,
    "application.ledger.operator_iva_operation": _ledger_operator_iva_operation,
    "application.ledger.own_account_operation": _ledger_own_account_operation,
    "application.ledger.participation_operation": _ledger_participation_operation,
    "application.ledger.participation_rebuild_operation": _ledger_participation_rebuild_operation,
    "application.ledger.preflight_operation": _ledger_preflight_operation,
    "application.ledger.ratios_operation": _ledger_ratios_operation,
    "application.ledger.remove_operation": _ledger_remove_operation,
    "application.ledger.reset_operation": _ledger_reset_operation,
    "application.ledger.review_operation": _ledger_review_operation,
    "application.ledger.rule_operation": _ledger_rule_operation,
    "application.ledger.split_operation": _ledger_split_operation,
    "application.ledger.status_operation": _ledger_status_operation,
    "application.ledger.track_operation": _ledger_track_operation,
    "application.ledger.update_operation": _ledger_update_operation,
    "application.ledger.view_operation": _ledger_view_operation,
    "application.live.borrador_100_operation": _live_borrador_100_operation,
    "application.live.expedientes_capture_operation": _live_expedientes_capture_operation,
    "application.live.expedientes_read_operation": _live_expedientes_read_operation,
    "application.live.filed_bulk_capture_operation": _live_filed_bulk_capture_operation,
    "application.live.filed_history_operation": _live_filed_history_operation,
    "application.live.filed_read_operation": _live_filed_read_operation,
    "application.live.filed_single_capture_operation": _live_filed_single_capture_operation,
    "application.live.filed_source_capture_operation": _live_filed_source_capture_operation,
    "application.live.iva_remote_state_capture_operation": _live_iva_remote_state_capture_operation,
    "application.live.iva_wallet_capture_operation": _live_iva_wallet_capture_operation,
    "application.live.iva_wallet_history_capture_operation": _live_iva_wallet_history_capture_operation,
    "application.live.iva_wallet_history_operation": _live_iva_wallet_history_operation,
    "application.live.justificante_capture_operation": _live_justificante_capture_operation,
    "application.live.justificante_read_operation": _live_justificante_read_operation,
    "application.live.notification_document_capture_operation": _live_notification_document_capture_operation,
    "application.live.notification_document_read_operation": _live_notification_document_read_operation,
    "application.live.notifications_capture_operation": _live_notifications_capture_operation,
    "application.live.notifications_read_operation": _live_notifications_read_operation,
    "application.live.verify_capture_operation": _live_verify_capture_operation,
    "application.live.verify_read_operation": _live_verify_read_operation,
    "application.modelo.aggregate_operation": _modelo_aggregate_operation,
    "application.modelo.amendment_context_operation": _modelo_amendment_context_operation,
    "application.modelo.audit_operation": _modelo_audit_operation,
    "application.modelo.calculation_report_verification_operation": _modelo_calculation_report_verification_operation,
    "application.modelo.dependency_operation": _modelo_dependency_operation,
    "application.modelo.filing_record_import_operation": _modelo_filing_record_import_operation,
    "application.modelo.filing_record_list_operation": _modelo_filing_record_list_operation,
    "application.modelo.filing_record_view_operation": _modelo_filing_record_view_operation,
    "application.modelo.filing_selection_operation": _modelo_filing_selection_operation,
    "application.modelo.history_operation": _modelo_history_operation,
    "application.modelo.history_timeline_operation": _modelo_history_timeline_operation,
    "application.modelo.invoice_withholding_capture_operation": _modelo_invoice_withholding_capture_operation,
    "application.modelo.iva_wallet_balance_operation": _modelo_iva_wallet_balance_operation,
    "application.modelo.iva_wallet_correction_operation": _modelo_iva_wallet_correction_operation,
    "application.modelo.iva_wallet_override_operation": _modelo_iva_wallet_override_operation,
    "application.modelo.iva_wallet_seed_operation": _modelo_iva_wallet_seed_operation,
    "application.modelo.lifecycle_history_operation": _modelo_lifecycle_history_operation,
    "application.modelo.local_observation_operation": _modelo_local_observation_operation,
    "application.modelo.m036_operation": _modelo_m036_operation,
    "application.modelo.m145_communication_operation": _modelo_m145_communication_operation,
    "application.modelo.m303_attestation_operation": _modelo_m303_attestation_operation,
    "application.modelo.m360_solicitud_operation": _modelo_m360_solicitud_operation,
    "application.modelo.maritime_preview_operation": _modelo_maritime_preview_operation,
    "application.modelo.typed_query_operation": _modelo_typed_query_operation,
    "application.modelo.metadata_read_operation": _modelo_metadata_read_operation,
    "application.modelo.modelo_spreadsheet_operation": _modelo_spreadsheet_operation,
    "application.modelo.operation_definitions": _modelo_operation_definitions,
    "application.modelo.projection_operation": _modelo_projection_operation,
    "application.modelo.query_read_operation": _modelo_query_read_operation,
    "application.modelo.quickfile_operation": _modelo_quickfile_operation,
    "application.modelo.reconciliation_export_operation": _modelo_reconciliation_export_operation,
    "application.modelo.reconciliation_import_operation": _modelo_reconciliation_import_operation,
    "application.modelo.reconciliation_list_operation": _modelo_reconciliation_list_operation,
    "application.modelo.reconciliation_pull_operation": _modelo_reconciliation_pull_operation,
    "application.modelo.review_package_exchange_operation": _modelo_review_package_exchange_operation,
    "application.modelo.review_package_operation": _modelo_review_package_operation,
    "application.modelo.review_package_recipient_operations": _modelo_review_package_recipient_operations,
    "application.modelo.revision_inventory_operation": _modelo_revision_inventory_operation,
    "application.modelo.revision_selection_operation": _modelo_revision_selection_operation,
    "application.modelo.revision_snapshot_operation": _modelo_revision_snapshot_operation,
    "application.modelo.taxation_comparison_operation": _modelo_taxation_comparison_operation,
    "application.modelo.verification_report_read_operation": _modelo_verification_report_read_operation,
    "application.modelo.wizard_attempt_operation": _modelo_wizard_attempt_operation,
    "application.modelo.wizard_context_operation": _modelo_wizard_context_operation,
    "application.modelo.work_create_operation": _modelo_work_create_operation,
    "application.modelo.work_inventory_operation": _modelo_work_inventory_operation,
    "application.modelo.work_review_operation": _modelo_work_review_operation,
    "application.modelo.workbench_operations": _modelo_workbench_operations,
    "application.overview.pipeline_operation": _overview_pipeline_operation,
    "application.overview.read_operation": _overview_read_operation,
    "application.prorrata_register.registered_operations": _prorrata_register_registered_operations,
    "application.review.read_registration": _review_read_registration,
    "application.user_profile.archive_operation": _user_profile_archive_operation,
    "application.user_profile.automation_operations": _user_profile_automation_operations,
    "application.user_profile.censal_certificate_operation": _user_profile_censal_certificate_operation,
    "application.user_profile.censal_file_import_operation": _user_profile_censal_file_import_operation,
    "application.user_profile.censal_operation": _user_profile_censal_operation,
    "application.user_profile.censal_prepare_operation": _user_profile_censal_prepare_operation,
    "application.user_profile.censal_preview_operation": _user_profile_censal_preview_operation,
    "application.user_profile.google_configuration_operation": _user_profile_google_configuration_operation,
    "application.user_profile.history_operation": _user_profile_history_operation,
    "application.user_profile.operations": _user_profile_operations,
    "application.user_profile.recovery_revoke_operation": _user_profile_recovery_revoke_operation,
    "application.user_profile.recovery_status_operation": _user_profile_recovery_status_operation,
    "application.workbench_generation_operation": _workbench_generation_operation,
    "application.workflow.resume_operation": _workflow_resume_operation,
    "application.workflow.run_read_operation": _workflow_run_read_operation,
    "application.workstation_check_operation": _workstation_check_operation,
    "entrypoints.diagnostics_repair_composition": _diagnostics_repair_composition,
    "entrypoints.local_reader_operation_composition": _local_reader_operation_composition,
}


def compose_operation_group(inputs: OperationCompositionInputs, group: str) -> OperationGroupBuild:
    """Build the operations of one named composition group, or refuse an unknown group."""
    composer = _OPERATION_COMPOSITION_GROUPS.get(group)
    if composer is None:
        raise InternalInvariantError(f"no operation composition group is named {group!r}")
    with operation_schema_compilation_scope():
        return composer(inputs)


def _compose_every_group(inputs: OperationCompositionInputs) -> tuple[OperationRegistry, dict[str, str]]:
    """Compose every group eagerly; return the registry and each definition's group."""
    composed_contracts: list[OperationPublicContractSetV1] = []

    def registry_contracts() -> OperationPublicContractSetV1:
        if not composed_contracts:
            raise InternalInvariantError("the operation registry's contracts are read before it is composed")
        return composed_contracts[0]

    bound = replace(inputs, contracts=registry_contracts)
    definitions: list[OperationDefinition] = []
    registrations: list[OperationPublicDefinitionRegistrationV1] = []
    groups: dict[str, str] = {}
    with operation_schema_compilation_scope():
        for group, composer in _OPERATION_COMPOSITION_GROUPS.items():
            built = composer(bound)
            definitions.extend(built.definitions)
            registrations.extend(built.registrations)
            for definition in built.definitions:
                groups[definition.definition_id] = group
    registry = OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda item: item.definition_id)),
        public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
    )
    composed_contracts.append(registry.public_contract_set)
    return registry, groups


def build_production_operation_registry(
    *,
    settings: Settings | None = None,
    auth_definitions: tuple[OperationDefinition, ...] | None = None,
    censal_definition: OperationDefinition | None = None,
    verify_nif_iva_definition: OperationDefinition | None = None,
    verify_tgvi_definition: OperationDefinition | None = None,
    google_export_definition: OperationDefinition | None = None,
    evidence_followup_ports: LedgerEvidenceFollowupOperationPorts | None = None,
    modelo_query_read_ports_factory: ModeloQueryReadPortsFactory | None = None,
    recipient_registry_ports_factory: RecipientFingerprintRegistryPortsFactory | None = None,
    recipient_event_repository_factory: BucketEventHistoryRepositoryFactory | None = None,
    modelo_export_ports_factory: ModeloExportPortsFactory | None = None,
    calculation_action_ports_factory: CalculationActionPortsFactory | None = None,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol] | None = None,
    amendment_action_ports_factory: AmendmentActionPortsFactory | None = None,
    filing_action_ports_factory: FilingActionPortsFactory | None = None,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory | None = None,
    modelo_history_ports_factory: ModeloHistoryPortsFactory | None = None,
    workflow_run_read_ports_factory: WorkflowRunReadPortsFactory | None = None,
    dependency_read_ports_factory: DependencyReadPortsFactory | None = None,
    pipeline_read_ports_factory: PipelineReadPortsFactory | None = None,
    overview_read_ports_factory: OverviewReadPortsFactory | None = None,
    invoice_inspection_read_ports_factory: InvoiceInspectionReadPortsFactory | None = None,
    invoice_creation_ports_factory: CatalogueCreationPortsFactory | None = None,
    modelo_aggregate_operation_ports_factory: ModeloAggregateOperationPortsFactory | None = None,
    modelo_invoice_withholding_capture_ports_factory: ModeloInvoiceWithholdingCapturePortsFactory | None = None,
    invoice_lifecycle_ports_factory: CatalogueLifecyclePortsFactory | None = None,
    modelo_edit_receipt_repository_factory: ModeloEditReceiptRepositoryFactory | None = None,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory | None = None,
    ledger_action_ports_factory: LedgerActionPortsFactory | None = None,
    ledger_read_ports_factory: LedgerReadPortsFactory | None = None,
    ledger_rule_repository_factory: LedgerClassificationRuleRepositoryFactory | None = None,
    counterparty_repository_factory: CounterpartyEstablishmentRepositoryFactory | None = None,
    own_account_repository_factory: OwnAccountRepositoryFactory | None = None,
    ledger_participation_repository_factory: TransactionParticipationIndexRepositoryFactory | None = None,
    participation_rebuild_ports_factory: ParticipationIndexRebuildPortsFactory | None = None,
    operator_scope_ports: OperatorScopePorts | None = None,
    automation_administration_factory: AutomationAdministrationFactory | None = None,
    automation_inventory_reader: AutomationInventoryReader | None = None,
    workbench_generation_reader: WorkbenchGenerationReader | None = None,
    profile_rotation_finalizer: ProfileRotationFinalizer | None = None,
    modelo_profile_resolver: ModeloWorkVerifyProfileResolver | None = None,
    modelo_workbench_read_ports_factory: ModeloWorkbenchReadPortsFactory | None = None,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
    runtime_server_owner_start: RuntimeServerOwnerStart | None = None,
    connectivity_probe: ConnectivityProbePort | None = None,
) -> OperationRegistry:
    """Build the sole immutable production inventory by composing every group eagerly.

    This is the validation authority the contract manifest is generated from.
    A ``None`` capability selects its production default.
    ``runtime_server_owner_start`` is bound by a contained process, which asks
    its owner to start the model runtime's server because one it started
    itself would end with it. ``connectivity_probe`` browses to the site the
    connectivity operation observes.
    """
    inputs = OperationCompositionInputs(
        settings=settings,
        auth_definitions=auth_definitions,
        censal_definition=censal_definition,
        verify_nif_iva_definition=verify_nif_iva_definition,
        verify_tgvi_definition=verify_tgvi_definition,
        google_export_definition=google_export_definition,
        evidence_followup_ports=evidence_followup_ports,
        modelo_query_read_ports_factory=modelo_query_read_ports_factory,
        recipient_registry_ports_factory=recipient_registry_ports_factory,
        recipient_event_repository_factory=recipient_event_repository_factory,
        modelo_export_ports_factory=modelo_export_ports_factory,
        calculation_action_ports_factory=calculation_action_ports_factory,
        attachment_store_factory=attachment_store_factory,
        amendment_action_ports_factory=amendment_action_ports_factory,
        filing_action_ports_factory=filing_action_ports_factory,
        work_lifecycle_ports_factory=work_lifecycle_ports_factory,
        modelo_history_ports_factory=modelo_history_ports_factory,
        workflow_run_read_ports_factory=workflow_run_read_ports_factory,
        dependency_read_ports_factory=dependency_read_ports_factory,
        pipeline_read_ports_factory=pipeline_read_ports_factory,
        overview_read_ports_factory=overview_read_ports_factory,
        invoice_inspection_read_ports_factory=invoice_inspection_read_ports_factory,
        invoice_creation_ports_factory=invoice_creation_ports_factory,
        modelo_aggregate_operation_ports_factory=modelo_aggregate_operation_ports_factory,
        modelo_invoice_withholding_capture_ports_factory=modelo_invoice_withholding_capture_ports_factory,
        invoice_lifecycle_ports_factory=invoice_lifecycle_ports_factory,
        modelo_edit_receipt_repository_factory=modelo_edit_receipt_repository_factory,
        verification_repository_bundle_factory=verification_repository_bundle_factory,
        ledger_action_ports_factory=ledger_action_ports_factory,
        ledger_read_ports_factory=ledger_read_ports_factory,
        ledger_rule_repository_factory=ledger_rule_repository_factory,
        counterparty_repository_factory=counterparty_repository_factory,
        own_account_repository_factory=own_account_repository_factory,
        ledger_participation_repository_factory=ledger_participation_repository_factory,
        participation_rebuild_ports_factory=participation_rebuild_ports_factory,
        operator_scope_ports=operator_scope_ports,
        automation_administration_factory=automation_administration_factory,
        automation_inventory_reader=automation_inventory_reader,
        workbench_generation_reader=workbench_generation_reader,
        profile_rotation_finalizer=profile_rotation_finalizer,
        modelo_profile_resolver=modelo_profile_resolver,
        modelo_workbench_read_ports_factory=modelo_workbench_read_ports_factory,
        execution_caller_reader=execution_caller_reader,
        runtime_server_owner_start=runtime_server_owner_start,
        connectivity_probe=connectivity_probe,
    )
    return _compose_every_group(inputs)[0]


def build_production_operation_contract_manifest() -> OperationContractManifestV1:
    """Record every production operation's contract and composition group from the eager registry."""
    registry, groups = _compose_every_group(OperationCompositionInputs())
    return OperationContractManifestV1.from_registry(registry, groups)


def build_manifest_operation_registry(
    inputs: OperationCompositionInputs | None = None, *, manifest: OperationContractManifestV1 | None = None
) -> ManifestOperationRegistry:
    """Bind the shipped contract manifest to the composition groups that build its operations.

    Contracts are answered from the manifest without composing any operation.
    An operation's group is composed on its first use and admitted only when it
    reproduces the manifest exactly. ``manifest`` defaults to the one shipped
    with this installation.
    """
    resolved = manifest if manifest is not None else load_operation_contract_manifest()
    bound = replace(inputs or OperationCompositionInputs(), contracts=lambda: resolved.contract_set)
    return ManifestOperationRegistry.from_manifest(resolved, partial(compose_operation_group, bound))


def compose_operation_dependencies(
    *,
    authority_operation: PinnedAuthorityOperation,
    operation_owner_id: Hex64Str | None = None,
    settings: Settings | None = None,
    evidence_followup_ports: LedgerEvidenceFollowupOperationPorts | None = None,
    modelo_query_read_ports_factory: ModeloQueryReadPortsFactory | None = None,
    recipient_registry_ports_factory: RecipientFingerprintRegistryPortsFactory | None = None,
    recipient_event_repository_factory: BucketEventHistoryRepositoryFactory | None = None,
    modelo_export_ports_factory: ModeloExportPortsFactory | None = None,
    calculation_action_ports_factory: CalculationActionPortsFactory | None = None,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol] | None = None,
    amendment_action_ports_factory: AmendmentActionPortsFactory | None = None,
    filing_action_ports_factory: FilingActionPortsFactory | None = None,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory | None = None,
    modelo_history_ports_factory: ModeloHistoryPortsFactory | None = None,
    workflow_run_read_ports_factory: WorkflowRunReadPortsFactory | None = None,
    dependency_read_ports_factory: DependencyReadPortsFactory | None = None,
    pipeline_read_ports_factory: PipelineReadPortsFactory | None = None,
    overview_read_ports_factory: OverviewReadPortsFactory | None = None,
    invoice_inspection_read_ports_factory: InvoiceInspectionReadPortsFactory | None = None,
    invoice_creation_ports_factory: CatalogueCreationPortsFactory | None = None,
    modelo_aggregate_operation_ports_factory: ModeloAggregateOperationPortsFactory | None = None,
    modelo_invoice_withholding_capture_ports_factory: ModeloInvoiceWithholdingCapturePortsFactory | None = None,
    invoice_lifecycle_ports_factory: CatalogueLifecyclePortsFactory | None = None,
    modelo_edit_receipt_repository_factory: ModeloEditReceiptRepositoryFactory | None = None,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory | None = None,
    operator_scope_ports: OperatorScopePorts | None = None,
    automation_administration_factory: AutomationAdministrationFactory | None = None,
    automation_inventory_reader: AutomationInventoryReader | None = None,
    workbench_generation_reader: WorkbenchGenerationReader | None = None,
    profile_rotation_finalizer: ProfileRotationFinalizer | None = None,
    execution_authority: OperationExecutionAuthority | None = None,
    execution_authority_factory: Callable[[OperationRegistry], OperationExecutionAuthority] | None = None,
    modelo_profile_resolver: ModeloWorkVerifyProfileResolver | None = None,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
    runtime_server_owner_start: RuntimeServerOwnerStart | None = None,
) -> OperationComposedServices:
    """Compose the manifest-backed production registry and all public services.

    Construction is deliberately explicit: the caller supplies the one
    already-pinned registry operation that every governed executor in this
    graph shares. It opens no browser and starts no supervised operation.
    Profile-bound repositories resolve only when an operation uses them, so
    the same graph can own pre-login and post-login execution without retaining
    a stale profile repository.
    """
    from ..adapters.persistence.operations.durability_router import DurabilityRoutedOperationPersistence
    from ..adapters.persistence.operations.journal import OperationJournalRepository
    from ..adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
    from ..adapters.persistence.operations.secure_references import operation_secure_reference_repository
    from ..adapters.persistence.operations.typed_financial_operand_custody import (
        OperationTypedFinancialOperandCustodyFilesystemRepository,
    )
    from ..application.operations.composition import compose_operation_services
    from ..core.paths import effective_storage_root
    from ..core.time.clock import now

    if execution_authority is not None and execution_authority_factory is not None:
        raise ValueError("operation authority must have one owner")
    inputs = OperationCompositionInputs(
        settings=settings or load_settings(),
        evidence_followup_ports=evidence_followup_ports,
        modelo_query_read_ports_factory=modelo_query_read_ports_factory,
        recipient_registry_ports_factory=recipient_registry_ports_factory,
        recipient_event_repository_factory=recipient_event_repository_factory,
        modelo_export_ports_factory=modelo_export_ports_factory,
        calculation_action_ports_factory=calculation_action_ports_factory,
        attachment_store_factory=attachment_store_factory,
        amendment_action_ports_factory=amendment_action_ports_factory,
        filing_action_ports_factory=filing_action_ports_factory,
        work_lifecycle_ports_factory=work_lifecycle_ports_factory,
        modelo_history_ports_factory=modelo_history_ports_factory,
        workflow_run_read_ports_factory=workflow_run_read_ports_factory,
        dependency_read_ports_factory=dependency_read_ports_factory,
        pipeline_read_ports_factory=pipeline_read_ports_factory,
        overview_read_ports_factory=overview_read_ports_factory,
        invoice_inspection_read_ports_factory=invoice_inspection_read_ports_factory,
        invoice_creation_ports_factory=invoice_creation_ports_factory,
        modelo_aggregate_operation_ports_factory=modelo_aggregate_operation_ports_factory,
        modelo_invoice_withholding_capture_ports_factory=modelo_invoice_withholding_capture_ports_factory,
        invoice_lifecycle_ports_factory=invoice_lifecycle_ports_factory,
        modelo_edit_receipt_repository_factory=modelo_edit_receipt_repository_factory,
        verification_repository_bundle_factory=verification_repository_bundle_factory,
        operator_scope_ports=operator_scope_ports,
        automation_administration_factory=automation_administration_factory,
        automation_inventory_reader=automation_inventory_reader,
        workbench_generation_reader=workbench_generation_reader,
        profile_rotation_finalizer=profile_rotation_finalizer,
        modelo_profile_resolver=modelo_profile_resolver,
        execution_caller_reader=execution_caller_reader,
        runtime_server_owner_start=runtime_server_owner_start,
    )
    resolved_settings = inputs.resolved_settings
    storage_root = effective_storage_root(settings=resolved_settings)
    registry = build_manifest_operation_registry(inputs)
    journal = OperationJournalRepository(storage_root=storage_root)
    if execution_authority_factory is not None:
        execution_authority = execution_authority_factory(registry)
    # Operations declared ephemeral run in this process's memory; every other is journaled durably.
    persistence = DurabilityRoutedOperationPersistence(
        journal=journal,
        event_stream=journal,
        reader=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
        operands=operation_secure_reference_repository(),
    )
    return compose_operation_services(
        registry=registry,
        authority_operation=authority_operation,
        journal=persistence,
        reader=persistence,
        event_stream=persistence,
        leases=persistence,
        operands=persistence,
        ephemeral=persistence,
        owner_id=secrets.token_hex(32) if operation_owner_id is None else operation_owner_id,
        lease_token_factory=lambda: secrets.token_hex(32),
        clock=now,
        lease_duration=_LEASE_DURATION,
        execution_timeout=_EXECUTION_TIMEOUT,
        cleanup_timeout=_CLEANUP_TIMEOUT,
        typed_financial_operand_custody=OperationTypedFinancialOperandCustodyFilesystemRepository(
            settings=resolved_settings
        ),
        execution_authority=execution_authority,
    )


__all__ = [
    "OperationCompositionInputs",
    "build_auth_operation_ports",
    "build_manifest_operation_registry",
    "build_production_operation_contract_manifest",
    "build_production_operation_registry",
    "compose_operation_dependencies",
    "compose_operation_group",
]
