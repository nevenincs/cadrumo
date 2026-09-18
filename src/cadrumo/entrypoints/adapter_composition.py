"""The adapter composition shared by the CLI and TUI entrypoints.

A frontend process must bind the persistence and outbound adapters the
application layer resolves through explicitly composed ports before it serves
any work. That inventory is a property of the product, not of the frontend, so
it is declared once here and entered by the CLI root and the TUI devtools
fixture. The separately shipped MCP harness owns its independent composition
root and does not import this entrypoint module.

An entrypoint that forgets this scope fails on every custody-touching verb,
which is exactly the symptom that made the original MCP gap visible.

Core types:
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`,
:class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import ExitStack, asynccontextmanager, contextmanager
from functools import cached_property
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from decimal import Decimal

    from google.auth.credentials import Credentials

    from ..adapters.outbound.aeat.sede.declarations import DeclaracionesRegisterSession
    from ..adapters.outbound.aeat.sede.declarations_schema import Declaracion
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
    from ..adapters.persistence.storage.sql.secure_object_records import SecureObjectNamespaceIntegrity
    from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
    from ..application.aggregation.percepciones_observations_repository import (
        PercepcionObservationPorts,
        PercepcionObservationPortsFactory,
    )
    from ..application.aggregation.retencion_observations_repository import (
        RetencionObservationPorts,
        RetencionObservationPortsFactory,
    )
    from ..application.auth.apoderado_repository import ApoderadoConfigurationRepositoryFactory
    from ..application.auth.certificate_secret_backend import CertificateSecretBackendFactory
    from ..application.auth.operator_probe_ports import OperatorProbePorts
    from ..application.auth.operator_scope_ports import OperatorScopePorts
    from ..application.auth.session_types import AeatSession
    from ..application.bienes_inversion.ports import (
        BienesInversionIvaRegisterRepositoryFactory,
        BienesInversionIvaRegisterRepositoryProtocol,
    )
    from ..application.diagnostics_ports import DiagnosticsPorts
    from ..application.filing.draft_review_ports import DraftReviewPorts, DraftReviewPortsFactory
    from ..application.inventory.ports import InventoryServicePorts, InventoryServicePortsFactory
    from ..application.invoices.catalogue_creation_ports import CatalogueCreationPortsFactory
    from ..application.invoices.catalogue_lifecycle_ports import CatalogueLifecyclePortsFactory
    from ..application.ledger.column_roles import ColumnRoleMappingPort
    from ..application.ledger.counterparty_establishment_ports import CounterpartyEstablishmentRepositoryFactory
    from ..application.ledger.evidence_ports import LedgerEvidencePorts, LedgerEvidencePortsFactory
    from ..application.ledger.invoice_confirmation_ports import InvoiceConfirmationPortsFactory
    from ..application.live.borrador_100 import (
        Borrador100SnapshotRepository,
        Borrador100SnapshotRepositoryFactory,
    )
    from ..application.live.censo_ports import CensalFetchPort
    from ..application.live.expedientes_ports import ExpedientesPorts, ExpedientesPortsFactory
    from ..application.modelo.amendment_action_ports import AmendmentActionPorts, AmendmentActionPortsFactory
    from ..application.modelo.calculation_action_ports import CalculationActionPorts, CalculationActionPortsFactory
    from ..application.modelo.edit_receipt_ports import (
        ModeloEditReceiptRepositoryFactory,
        ModeloEditReceiptRepositoryPort,
    )
    from ..application.modelo.export_ports import ModeloExportPorts, ModeloExportPortsFactory
    from ..application.modelo.filing_action_ports import FilingActionPorts, FilingActionPortsFactory
    from ..application.modelo.history_ports import ModeloHistoryPorts, ModeloHistoryPortsFactory
    from ..application.modelo.iva_wallet_seed_ports import (
        ModeloIvaWalletSeedPorts,
        ModeloIvaWalletSeedPortsFactory,
    )
    from ..application.modelo.m036_lifecycle_ports import M036LifecyclePortsFactory
    from ..application.modelo.m145_communication_records_ports import (
        M145CommunicationRecordsPortsFactory,
    )
    from ..application.modelo.participation_index_rebuild_ports import (
        ParticipationIndexRebuildPorts,
        ParticipationIndexRebuildPortsFactory,
    )
    from ..application.modelo.recipient_encryption import RecipientEncryptionCapabilityFactory
    from ..application.modelo.reconciliation_records import ModeloReconciliationPersistencePort
    from ..application.modelo.review_package_recipient_registry_ports import (
        RecipientFingerprintRegistryPortsFactory,
    )
    from ..application.modelo.review_package_signing_ports import (
        ReviewPackageSigningKeypairCapabilityFactory,
    )
    from ..application.modelo.verification_repository_ports import (
        VerificationRepositoryBundle,
        VerificationRepositoryBundleFactory,
    )
    from ..application.modelo.work_lifecycle_ports import WorkLifecyclePorts, WorkLifecyclePortsFactory
    from ..application.prorrata_register.ports import (
        ProrrataRegisterRepositoryFactory,
        ProrrataRegisterServiceRepositoryProtocol,
    )
    from ..application.state_projection_ports import StateProjectionReadPorts
    from ..application.storage.calc_sheets.parity_harness import CalcSheetsParityApplyPort
    from ..application.storage.calc_sheets.records import SheetExportPlan
    from ..application.user_profile.custody_ports import ProfileBucketStoragePort, ProfileCustodyPort
    from ..application.user_profile.profile_read_ports import ProfileReadPorts, ProfileReadPortsFactory
    from ..core.config import Settings
    from ..core.tabular import NormalizedTable
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..domain.calculations.registry.tax_id_format import SubjectTaxId
    from ..domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
    from ..domain.usage_ratios.model import UsageRatioProfile


class ProfileAdapterComposition:
    """Concrete capabilities composed for one executable profile session.

    Each capability resolves on first read, so a command imports only the
    adapter trees it actually uses.
    """

    def __init__(self, *, profile_custody: ProfileCustodyPort) -> None:
        """Hold the custody port the session scope already bound."""
        self._profile_custody = profile_custody

    @cached_property
    def state_projection_read_ports(self) -> StateProjectionReadPorts:
        """Resolve the state projection read ports on first read."""
        from ..adapters.persistence.profile.state_projection import StateProjectionPersistenceAdapter
        from ..adapters.persistence.profile.usage_ratios import load_usage_ratios
        from ..application.state_projection_ports import StateProjectionReadPorts

        projection_adapter = StateProjectionPersistenceAdapter(diagnostics_ports=self.diagnostics_ports)
        return StateProjectionReadPorts(
            workspace=projection_adapter,
            profile=projection_adapter,
            usage_ratio_profile_loader=load_usage_ratios,
        )

    @cached_property
    def diagnostics_ports(self) -> DiagnosticsPorts:
        """Resolve the diagnostics ports on first read."""
        return build_diagnostics_ports()

    @cached_property
    def certificate_secret_backend_factory(self) -> CertificateSecretBackendFactory:
        """Resolve the certificate secret backend factory on first read."""
        from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend

        return build_certificate_secret_backend

    @cached_property
    def operator_probe_ports(self) -> OperatorProbePorts:
        """Resolve the operator probe ports on first read."""
        return build_operator_probe_ports()

    @cached_property
    def operator_scope_ports(self) -> OperatorScopePorts:
        """Resolve the operator scope ports on first read."""
        from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports

        return build_operator_scope_ports()

    @cached_property
    def bucket_storage(self) -> ProfileBucketStoragePort:
        """Resolve the bucket storage on first read."""
        return self._profile_custody.bucket_storage()

    @property
    def verification_repository_bundle_factory(self) -> VerificationRepositoryBundleFactory:
        """Resolve the verification repository bundle factory on first read."""
        return build_verification_repository_bundle

    @property
    def profile_read_ports_factory(self) -> ProfileReadPortsFactory:
        """Resolve the per-bucket profile read ports factory."""
        return _profile_read_ports_for_bucket

    @property
    def calculation_action_ports_factory(self) -> CalculationActionPortsFactory:
        """Resolve the calculation action ports factory on first read."""
        return build_calculation_action_ports

    @property
    def amendment_action_ports_factory(self) -> AmendmentActionPortsFactory:
        """Resolve the amendment action ports factory on first read."""
        return build_amendment_action_ports

    @property
    def filing_action_ports_factory(self) -> FilingActionPortsFactory:
        """Resolve the filing action ports factory on first read."""
        return build_filing_action_ports

    @property
    def bienes_inversion_repository_factory(self) -> BienesInversionIvaRegisterRepositoryFactory:
        """Resolve the bienes inversion repository factory on first read."""
        return build_bienes_inversion_repository

    @property
    def retencion_observation_ports_factory(self) -> RetencionObservationPortsFactory:
        """Resolve the retencion observation ports factory on first read."""
        return build_retencion_observation_ports

    @property
    def percepcion_observation_ports_factory(self) -> PercepcionObservationPortsFactory:
        """Resolve the percepcion observation ports factory on first read."""
        return build_percepcion_observation_ports

    @property
    def borrador_100_snapshot_repository_factory(self) -> Borrador100SnapshotRepositoryFactory:
        """Resolve the borrador 100 snapshot repository factory on first read."""
        return build_borrador_100_snapshot_repository

    @cached_property
    def censal_fetch_port(self) -> CensalFetchPort:
        """Resolve the censal fetch port on first read."""
        return build_censal_fetch_port()

    @property
    def expedientes_ports_factory(self) -> ExpedientesPortsFactory:
        """Resolve the expedientes ports factory on first read."""
        return build_expedientes_ports

    @property
    def ledger_evidence_ports_factory(self) -> LedgerEvidencePortsFactory:
        """Resolve the ledger evidence ports factory on first read."""
        return build_ledger_evidence_ports

    @cached_property
    def invoice_confirmation_ports_factory(self) -> InvoiceConfirmationPortsFactory:
        """Resolve the invoice confirmation ports factory on first read."""
        from ..adapters.persistence.profile.invoice_confirmation import build_invoice_confirmation_ports

        return build_invoice_confirmation_ports

    @cached_property
    def counterparty_establishment_repository_factory(self) -> CounterpartyEstablishmentRepositoryFactory:
        """Resolve the counterparty establishment repository factory on first read."""
        from ..adapters.persistence.profile.counterparty_establishment import (
            build_counterparty_establishment_repository,
        )

        return build_counterparty_establishment_repository

    @property
    def inventory_service_ports_factory(self) -> InventoryServicePortsFactory:
        """Resolve the inventory service ports factory on first read."""
        return build_inventory_service_ports

    @cached_property
    def catalogue_creation_ports_factory(self) -> CatalogueCreationPortsFactory:
        """Resolve the catalogue creation ports factory on first read."""
        from ..adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports

        return build_catalogue_creation_ports

    @cached_property
    def catalogue_lifecycle_ports_factory(self) -> CatalogueLifecyclePortsFactory:
        """Resolve the catalogue lifecycle ports factory on first read."""
        from ..adapters.persistence.profile.catalogue_creation import build_catalogue_lifecycle_ports

        return build_catalogue_lifecycle_ports

    @property
    def draft_review_ports_factory(self) -> DraftReviewPortsFactory:
        """Resolve the draft review ports factory on first read."""
        return build_draft_review_ports

    @property
    def modelo_export_ports_factory(self) -> ModeloExportPortsFactory:
        """Resolve the modelo export ports factory on first read."""
        return build_modelo_export_ports

    @property
    def modelo_edit_receipt_repository_factory(self) -> ModeloEditReceiptRepositoryFactory:
        """Resolve the modelo edit receipt repository factory on first read."""
        return build_modelo_edit_receipt_repository

    @property
    def modelo_history_ports_factory(self) -> ModeloHistoryPortsFactory:
        """Resolve the modelo history ports factory on first read."""
        return build_modelo_history_ports

    @property
    def participation_index_rebuild_ports_factory(self) -> ParticipationIndexRebuildPortsFactory:
        """Resolve the participation index rebuild ports factory on first read."""
        return build_participation_index_rebuild_ports

    @cached_property
    def review_package_signing_keypair_capability_factory(self) -> ReviewPackageSigningKeypairCapabilityFactory:
        """Resolve the review package signing keypair capability factory on first read."""
        from ..adapters.persistence.profile.review_package_signing import (
            build_review_package_signing_keypair_capability,
        )

        return build_review_package_signing_keypair_capability

    @property
    def modelo_iva_wallet_seed_ports_factory(self) -> ModeloIvaWalletSeedPortsFactory:
        """Resolve the modelo IVA wallet seed ports factory on first read."""
        return build_modelo_iva_wallet_seed_ports

    @property
    def prorrata_register_repository_factory(self) -> ProrrataRegisterRepositoryFactory:
        """Resolve the prorrata register repository factory on first read."""
        return build_prorrata_register_repository

    @cached_property
    def m145_communication_records_ports_factory(self) -> M145CommunicationRecordsPortsFactory:
        """Resolve the Modelo 145 communication records ports factory on first read."""
        from ..adapters.persistence.profile.m145_communication_records import (
            build_m145_communication_records_ports,
        )

        return build_m145_communication_records_ports

    @cached_property
    def m036_lifecycle_ports_factory(self) -> M036LifecyclePortsFactory:
        """Resolve the Modelo 036 lifecycle ports factory on first read."""
        from ..adapters.persistence.profile.m036_lifecycle import build_m036_lifecycle_ports

        return build_m036_lifecycle_ports

    @property
    def work_lifecycle_ports_factory(self) -> WorkLifecyclePortsFactory:
        """Resolve the work lifecycle ports factory on first read."""
        return build_work_lifecycle_ports

    @cached_property
    def recipient_fingerprint_registry_ports_factory(self) -> RecipientFingerprintRegistryPortsFactory:
        """Resolve the recipient fingerprint registry ports factory on first read."""
        from ..adapters.persistence.profile.review_package_recipient_registry import (
            build_recipient_fingerprint_registry_ports,
        )

        return build_recipient_fingerprint_registry_ports

    @cached_property
    def recipient_encryption_capability_factory(self) -> RecipientEncryptionCapabilityFactory:
        """Resolve the recipient encryption capability factory on first read."""
        from ..adapters.persistence.profile.review_package_recipient_encryption import (
            build_recipient_encryption_capability,
        )

        return build_recipient_encryption_capability

    @cached_property
    def apoderado_config_repository_factory(self) -> ApoderadoConfigurationRepositoryFactory:
        """Resolve the apoderado config repository factory on first read."""
        from ..adapters.persistence.profile.apoderado import build_apoderado_config_repository

        return build_apoderado_config_repository


def build_operator_probe_ports() -> OperatorProbePorts:
    """Compose the session, certificate and Cl@ve probes the auth flows consult."""
    from ..adapters.outbound.aeat.auth.certificate import CertificateHealthProbeAdapter
    from ..adapters.outbound.aeat.auth.clave_movil_support import ClaveIdentityProbeAdapter
    from ..adapters.persistence.storage.master_key.active_session import ActiveProfileSessionPresenceAdapter
    from ..application.auth.operator_probe_ports import OperatorProbePorts

    return OperatorProbePorts(
        active_profile_session=ActiveProfileSessionPresenceAdapter(),
        certificate_health=CertificateHealthProbeAdapter(),
        clave_identity=ClaveIdentityProbeAdapter(),
    )


def build_censal_fetch_port() -> CensalFetchPort:
    """Bind the concrete Sede censo reader to the application fetch port."""
    from ..adapters.outbound.aeat.sede.censal_datos import fetch_censal_datos
    from ..adapters.outbound.aeat.sede.errors import SedeError, SedeNavigationError, SedeParseError
    from ..application.live.errors import LiveApplicationError
    from ..application.user_profile.censal_observation import CensalObservation

    async def fetch(session: AeatSession, *, taxpayer_nif: str, settings: Settings) -> CensalObservation:
        """Read through Sede and translate its result and failures inward."""
        try:
            captured = await fetch_censal_datos(
                session,
                taxpayer_nif=taxpayer_nif,
                settings=settings,
            )
        except SedeError as exc:
            if isinstance(exc, SedeParseError):
                failure_kind = "parse"
            elif isinstance(exc, SedeNavigationError):
                failure_kind = "navigation"
            else:
                failure_kind = "transport"
            raise LiveApplicationError(
                translated_message="errors.error.error_application_live",
                context={"surface": "censal", "stage": "fetch", "failure_kind": failure_kind},
            ) from exc
        except Exception as exc:
            raise LiveApplicationError(
                translated_message="errors.error.error_application_live",
                context={"surface": "censal", "stage": "fetch", "failure_kind": "unexpected"},
            ) from exc
        try:
            return CensalObservation.model_validate(captured, strict=True)
        except Exception as exc:
            raise LiveApplicationError(
                translated_message="errors.error.error_application_live",
                context={"surface": "censal", "stage": "observation_translation"},
            ) from exc

    return fetch


def build_calc_sheets_parity_apply_port() -> CalcSheetsParityApplyPort:
    """Bind the Google workbook writer to the application parity capability."""
    from ..adapters.outbound.google.calc_sheets_apply import apply_export_plan
    from ..application.storage.calc_sheets.parity_harness import CalcSheetsParityApplyResult

    def apply(
        plan: SheetExportPlan,
        *,
        credentials: Credentials,
        root_folder_id: str,
    ) -> CalcSheetsParityApplyResult:
        """Translate the concrete Google apply record at the outer boundary."""
        applied = apply_export_plan(
            plan,
            credentials=credentials,
            root_folder_id=root_folder_id,
        )
        return CalcSheetsParityApplyResult(
            spreadsheet_id=applied.spreadsheet_id,
            spreadsheet_url=applied.spreadsheet_url,
        )

    return apply


def build_modelo_export_ports(
    *,
    bucket_id: str,
    m303_rectificativa_taxpayer_tax_id: SubjectTaxId,
) -> ModeloExportPorts:
    """Compose every persisted authority required by one Modelo export."""
    from ..adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
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
            m303_rectificativa_taxpayer_tax_id=m303_rectificativa_taxpayer_tax_id,
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
        draft_review_ports=build_draft_review_ports(bucket_id=normalized_bucket_id),
    )


def _profile_read_ports_for_bucket(bucket_id: str) -> ProfileReadPorts:
    return build_profile_read_ports(bucket_id=bucket_id)


def build_profile_read_ports(*, bucket_id: str) -> ProfileReadPorts:
    """Compose the authenticated profile projection for one calculation bucket."""
    from ..adapters.persistence.profile.profile_path_values import ProfilePathValuesPersistenceAdapter
    from ..application.user_profile.profile_read_ports import ProfileReadPorts
    from ..application.user_profile.profile_record_repository import ProfileRecordRepository
    from ..domain.calculations.registry.authority import bundled_indexed_authority

    normalized_bucket_id = bucket_id.strip()
    with bundled_indexed_authority().operation() as operation:
        return ProfileReadPorts(
            path_values=ProfilePathValuesPersistenceAdapter(
                repository=ProfileRecordRepository.for_current_session(
                    normalized_bucket_id,
                    profile_decode_context=operation.profile_decode_context(),
                ),
            ),
        )


def build_bienes_inversion_repository(*, bucket_id: str) -> BienesInversionIvaRegisterRepositoryProtocol:
    """Compose the encrypted register capability for one profile bucket."""
    from ..adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    normalized_bucket_id = bucket_id.strip()
    return BienesInversionIvaRegisterRepository(
        bucket_id=normalized_bucket_id,
        objects=secure_object_repository_for_bucket(normalized_bucket_id),
    )


def build_prorrata_register_repository(*, bucket_id: str) -> ProrrataRegisterServiceRepositoryProtocol:
    """Compose the bucket-bound prorrata register repository capability."""
    from ..adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    normalized_bucket_id = bucket_id.strip()
    return ProrrataRegisterRepository(
        bucket_id=normalized_bucket_id,
        objects=secure_object_repository_for_bucket(normalized_bucket_id),
    )


def build_diagnostics_ports() -> DiagnosticsPorts:
    """Compose the translated secure-object capabilities used by diagnostics."""
    from ..adapters.persistence.storage.master_key.active_session import NoActiveBucketSessionError
    from ..adapters.persistence.storage.runtime_repository import (
        secure_object_repository_for_active_bucket_or_default_route,
    )
    from ..application.diagnostics_ports import DiagnosticSecureObjectNamespace, DiagnosticsPorts

    class SecureObjectDiagnosticsAdapter:
        """Translate storage integrity records into application diagnostic DTOs."""

        @staticmethod
        def _repository() -> SecureObjectRepository:
            return secure_object_repository_for_active_bucket_or_default_route()

        @staticmethod
        def _translate(row: SecureObjectNamespaceIntegrity) -> DiagnosticSecureObjectNamespace:
            return DiagnosticSecureObjectNamespace(
                namespace=row.namespace,
                readable=row.readable,
                unreadable=row.unreadable,
            )

        def list_namespaces(self) -> tuple[str, ...]:
            return self._repository().list_namespaces()

        def probe_namespace_integrity(self, namespace: str) -> DiagnosticSecureObjectNamespace:
            return self._translate(self._repository().probe_namespace_integrity(namespace))

        def quarantine_unreadable_rows(self) -> tuple[DiagnosticSecureObjectNamespace, ...]:
            return tuple(self._translate(row) for row in self._repository().quarantine_unreadable_rows())

    def classify_session_failure(error: BaseException) -> bool:
        """Translate the storage session exception without leaking it inward."""
        seen: set[int] = set()
        pending: list[BaseException] = [error]
        while pending:
            current = pending.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            if isinstance(current, NoActiveBucketSessionError):
                return True
            pending.extend(link for link in (current.__cause__, current.__context__) if link is not None)
        return False

    return DiagnosticsPorts(
        secure_object_repository=SecureObjectDiagnosticsAdapter(),
        session_failure_classifier=classify_session_failure,
    )


def build_draft_review_ports(*, bucket_id: str) -> DraftReviewPorts:
    """Compose the persisted authorities required by draft review."""
    from ..adapters.persistence.profile.calculation_observations import CalculationObservationRepository
    from ..adapters.persistence.profile.filing_drafts import ModeloDraftRepository
    from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.filing.draft_review_ports import DraftReviewPorts
    from ..application.user_profile.profile_record_repository import ProfileRecordRepository
    from ..application.user_profile.projections import record_to_path_values
    from ..domain.calculations.registry.authority import bundled_indexed_authority
    from ..domain.user_profile.errors import ProfileNotFoundError

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    with bundled_indexed_authority().operation() as operation:
        profile_decode_context = operation.profile_decode_context()

    class ProfileActivityReader:
        """Translate the session-bound profile record into an application map."""

        def load_path_values(self, *, bucket_id: str) -> Mapping[str, str] | None:
            try:
                record = ProfileRecordRepository.for_current_session(
                    bucket_id,
                    profile_decode_context=profile_decode_context,
                ).load(bucket_id)
            except ProfileNotFoundError:
                return None
            return record_to_path_values(record)

    return DraftReviewPorts(
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        invoice_repository=InvoiceCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        observation_repository=CalculationObservationRepository(objects=objects),
        draft_repository=ModeloDraftRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        profile_repository=ProfileActivityReader(),
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


def build_modelo_edit_receipt_repository(*, bucket_id: str) -> ModeloEditReceiptRepositoryPort:
    """Compose the encrypted Modelo edit-receipt capability for one bucket."""
    from ..adapters.persistence.profile.modelos_edit_receipts import ModeloEditReceiptRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    normalized_bucket_id = bucket_id.strip()
    return ModeloEditReceiptRepository(
        bucket_id=normalized_bucket_id,
        objects=secure_object_repository_for_bucket(normalized_bucket_id),
    )


def build_participation_index_rebuild_ports(*, bucket_id: str) -> ParticipationIndexRebuildPorts:
    """Compose every persisted authority required by a participation-index rebuild."""
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.participation_index_rebuild_ports import ParticipationIndexRebuildPorts

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return ParticipationIndexRebuildPorts(
        calculation_repository=CalculationRevisionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        work_unit_repository=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        filing_repository=ModeloRecordCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        participation_index_repository=TransactionParticipationIndexRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
    )


def build_modelo_iva_wallet_seed_ports(*, bucket_id: str) -> ModeloIvaWalletSeedPorts:
    """Compose every persisted authority required by IVA-wallet seed operations."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.calculations.observations_repository import CalculationObservationPorts
    from ..application.modelo.iva_wallet_seed_ports import ModeloIvaWalletSeedPorts

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return ModeloIvaWalletSeedPorts(
        work_unit_repository=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        calculation_repository=CalculationRevisionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        calculation_observation_ports=CalculationObservationPorts(
            observation_repository=CalculationObservationRepository(objects=objects),
            iva_wallet_decision_repository=IvaWalletDecisionRepository(objects=objects),
        ),
        iva_compensation_history_repository=IvaCompensationHistoryRepository(objects=objects),
    )


def build_inventory_service_ports(*, bucket_id: str) -> InventoryServicePorts:
    """Compose the encrypted inventory repository and bucket-event sink."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.inventory import InventoryLedgerRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.inventory.ports import InventoryServicePorts

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)

    def inventory_repository_factory(requested_bucket_id: str) -> InventoryLedgerRepository:
        """Resolve each requested bucket through the guarded storage runtime."""
        return InventoryLedgerRepository(
            objects=secure_object_repository_for_bucket(requested_bucket_id),
        )

    return InventoryServicePorts(
        inventory_repository_factory=inventory_repository_factory,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def build_borrador_100_snapshot_repository(*, bucket_id: str) -> Borrador100SnapshotRepository:
    """Bind the encrypted borrador snapshot adapter to one profile bucket."""
    from pydantic import ValidationError

    from ..adapters.persistence.profile.snapshots import SecureSnapshotRepository
    from ..adapters.persistence.storage.errors import StorageError
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..adapters.persistence.storage.secure_object_namespaces import LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE
    from ..application.live.borrador_100 import (
        Borrador100Snapshot,
        BorradorSnapshotNotFoundError,
        borrador_100_snapshot_object_key,
    )
    from ..application.live.errors import LiveApplicationError, LiveApplicationInputError
    from ..application.persistence_errors import PersistenceDegradationError

    normalized_bucket_id = bucket_id.strip()

    def translate_classification_refusal(
        snapshot_id: str,
        actual_classification: object,
        expected_classification: object,
    ) -> LiveApplicationError:
        """Translate storage classification details at the application boundary."""
        return LiveApplicationError(
            translated_message="errors.error.error_application_live",
            context={
                "surface": "borrador",
                "stage": "snapshot_classification",
                "snapshot_id": snapshot_id,
                "actual_classification": str(actual_classification),
                "expected_classification": str(expected_classification),
            },
        )

    def translate_version_refusal(
        snapshot_id: str,
        actual_version: int,
        expected_version: int,
    ) -> LiveApplicationError:
        """Translate storage schema-version details at the application boundary."""
        return LiveApplicationError(
            translated_message="errors.error.error_application_live",
            context={
                "surface": "borrador",
                "stage": "snapshot_schema_version",
                "snapshot_id": snapshot_id,
                "actual_version": actual_version,
                "expected_version": expected_version,
            },
        )

    class Borrador100SnapshotAdapter(SecureSnapshotRepository[Borrador100Snapshot]):
        """Bind the generic secure store while retaining borrador chronology."""

        @override
        def exists(self, snapshot_id: str) -> bool:
            """Check snapshot presence while translating storage failures inward."""
            try:
                return super().exists(snapshot_id)
            except (StorageError, OSError, ValidationError, UnicodeDecodeError) as exc:
                raise PersistenceDegradationError("borrador_snapshot_exists") from exc

        @override
        def load(self, snapshot_id: str) -> Borrador100Snapshot:
            """Load one snapshot while translating storage failures inward."""
            try:
                return super().load(snapshot_id)
            except (StorageError, OSError, ValidationError, UnicodeDecodeError) as exc:
                raise PersistenceDegradationError("borrador_snapshot_load") from exc

        @override
        def list_snapshots(self) -> tuple[Borrador100Snapshot, ...]:
            """List snapshots while translating storage failures inward."""
            try:
                return tuple(
                    sorted(super().list_snapshots(), key=lambda item: (item.captured_at, item.snapshot_id)),
                )
            except (StorageError, OSError, ValidationError, UnicodeDecodeError) as exc:
                raise PersistenceDegradationError("borrador_snapshot_list") from exc

        @override
        def save(self, snapshot: Borrador100Snapshot) -> None:
            """Persist one snapshot while translating storage failures inward."""
            try:
                super().save(snapshot)
            except (StorageError, OSError, ValidationError, UnicodeDecodeError) as exc:
                raise PersistenceDegradationError("borrador_snapshot_save") from exc

    return Borrador100SnapshotAdapter(
        bucket_id=normalized_bucket_id,
        payload_model=Borrador100Snapshot,
        namespace_definition=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE,
        object_key=borrador_100_snapshot_object_key,
        not_found_factory=lambda snapshot_id: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_not_found",
            context={"snapshot_id": snapshot_id},
        ),
        ambiguous_prefix_factory=lambda snapshot_id, full_ids: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
        ),
        domain_label="borrador",
        input_error_cls=LiveApplicationInputError,
        objects=secure_object_repository_for_bucket(normalized_bucket_id),
        classification_error_factory=translate_classification_refusal,
        version_error_factory=translate_version_refusal,
    )


def build_retencion_observation_ports(*, bucket_id: str) -> RetencionObservationPorts:
    """Compose the encrypted retención observation capability for one bucket."""
    from ..adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.aggregation.retencion_observations_repository import RetencionObservationPorts

    normalized_bucket_id = bucket_id.strip()
    return RetencionObservationPorts(
        repository=RetencionObservationRepositoryAdapter(
            objects=secure_object_repository_for_bucket(normalized_bucket_id),
        ),
    )


def build_percepcion_observation_ports(*, bucket_id: str) -> PercepcionObservationPorts:
    """Compose the encrypted percepciones observation capability for one bucket."""
    from ..adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.aggregation.percepciones_observations_repository import PercepcionObservationPorts

    normalized_bucket_id = bucket_id.strip()
    return PercepcionObservationPorts(
        repository=PercepcionObservationRepositoryAdapter(
            objects=secure_object_repository_for_bucket(normalized_bucket_id),
        ),
    )


def build_calculation_action_ports(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> CalculationActionPorts:
    """Compose every persisted authority required by one Modelo calculation."""
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
    from ..adapters.persistence.profile.inventory import InventoryLedgerRepository
    from ..adapters.persistence.profile.invoice_source_resolver import InvoiceCatalogueSourceResolverAdapter
    from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ..adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
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

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)

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
        calculation_repository=CalculationRevisionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
            m303_rectificativa_taxpayer_tax_id=_export_taxpayer_tax_id(
                bucket_id=normalized_bucket_id, operation=operation
            ),
        ),
        bucket_event_repository=bucket_event_repository,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        usage_ratio_profile_loader=load_usage_ratios,
        profile_read_ports=build_profile_read_ports(bucket_id=normalized_bucket_id),
        invoice_repository=invoice_repository,
        invoice_catalogue_read_ports=build_invoice_catalogue_read_ports(bucket_id=normalized_bucket_id),
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
        inventory_repository=InventoryLedgerRepository(objects=objects),
        observation_repository=CalculationObservationRepository(objects=objects),
        percepciones_observation_ports=PercepcionObservationPorts(
            repository=PercepcionObservationRepositoryAdapter(objects=objects),
        ),
        iva_compensation_history_repository=IvaCompensationHistoryRepository(objects=objects),
        iva_compensation_decision_repository=IvaWalletDecisionRepository(objects=objects),
        borrador_snapshot_repository=build_borrador_100_snapshot_repository(bucket_id=normalized_bucket_id),
        retencion_observation_ports=build_retencion_observation_ports(bucket_id=normalized_bucket_id),
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
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.amendment_action_ports import AmendmentActionPorts

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    taxpayer_tax_id = _export_taxpayer_tax_id(bucket_id=normalized_bucket_id, operation=operation)
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
        observation_repository=CalculationObservationRepository(bucket_id=normalized_bucket_id, objects=objects),
        iva_compensation_history_repository=IvaCompensationHistoryRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
    )


def _export_taxpayer_tax_id(*, bucket_id: str, operation: PinnedAuthorityOperation) -> SubjectTaxId | None:
    """Return the profile tax id a stored M303 rectificativa revalidates against, when one is declared."""
    from ..application.modelo.profile_export_binding import resolve_export_identity

    export_identity = resolve_export_identity(bucket_id=bucket_id, operation=operation)
    return export_identity[0].tax_id if export_identity is not None else None


def build_filing_action_ports(*, bucket_id: str) -> FilingActionPorts:
    """Compose every persisted authority required by one Modelo filing."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from ..adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ..adapters.persistence.profile.workflow_gate import build_workflow_gate_ports
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
        iva_compensation_decision_repository=IvaWalletDecisionRepository(objects=objects),
        workflow_run_repository=WorkflowRunRepository(objects=objects),
        draft_review_ports=build_draft_review_ports(bucket_id=normalized_bucket_id),
        workflow_gate_ports=build_workflow_gate_ports(bucket_id=normalized_bucket_id),
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
    from ..domain.calculations.registry.authority import bundled_indexed_authority

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

    def translate_declaration(row: Declaracion) -> ExpedientesDeclaration:
        """Translate the Sede row DTO before it enters application state."""
        try:
            return ExpedientesDeclaration(
                modelo=row.modelo,
                ejercicio=row.ejercicio,
                period=row.period,
                expediente_id=row.expediente_id,
                estado=row.estado,
                tipo_solicitud=row.tipo_solicitud,
                observaciones=row.observaciones,
                presented_at=row.presented_at,
                justificante_link_text=row.justificante_link_text,
                archive_link_text=row.archive_link_text,
                declaration_copy_link_text=row.declaration_copy_link_text,
                justificante_cell_index=row.justificante_cell_index,
                archive_cell_index=row.archive_cell_index,
                declaration_copy_cell_index=row.declaration_copy_cell_index,
                mode=row.mode,
            )
        except Exception as exc:
            raise LiveApplicationError(
                translated_message="errors.error.error_application_live",
                context={"surface": "expedientes", "stage": "declaration_translation"},
            ) from exc

    class SedeExpedientesRegister(ExpedientesRegisterProtocol):
        """Translate rows returned by the concrete Sede register session."""

        def __init__(self, register: DeclaracionesRegisterSession) -> None:
            self._register = register

        @override
        async def walk(self, *, modelo: str, ejercicio: int) -> tuple[ExpedientesDeclaration, ...]:
            try:
                rows = await self._register.walk(modelo=modelo, ejercicio=ejercicio)
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
        @override
        async def open_register(self, session: AeatSession, *, settings: Settings):
            try:
                with bundled_indexed_authority().operation() as operation:
                    async with (
                        shared_playwright(session) as playwright,
                        open_declarations_register(
                            session,
                            operation=operation,
                            settings=settings,
                            playwright=playwright,
                        ) as register,
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


def build_verification_repository_bundle(bucket_id: str) -> VerificationRepositoryBundle:
    """Compose every verification repository against one bucket store."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.profile.workflow_gate import build_workflow_gate_ports
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.verification_repository_ports import VerificationRepositoryBundle
    from ..application.workflow.persistence import WorkflowRunRepository

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return VerificationRepositoryBundle(
        calculation=CalculationRevisionCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects),
        work_unit=WorkUnitCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects),
        filing=ModeloRecordCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects),
        transaction=TransactionCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects),
        verification=VerificationReportCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects),
        bucket_event=BucketEventHistoryRepository(objects=objects),
        observation=CalculationObservationRepository(objects=objects),
        iva_compensation_history=IvaCompensationHistoryRepository(objects=objects),
        iva_compensation_decision=IvaWalletDecisionRepository(objects=objects),
        participation_index=TransactionParticipationIndexRepository(bucket_id=normalized_bucket_id, objects=objects),
        workflow_run=WorkflowRunRepository(objects=objects),
        justificante=JustificanteRepository(objects=objects),
        draft_review_ports=build_draft_review_ports(bucket_id=normalized_bucket_id),
        workflow_gate_ports=build_workflow_gate_ports(bucket_id=normalized_bucket_id),
    )


__all__ = [
    "ProfileAdapterComposition",
    "build_active_work_lifecycle_ports",
    "build_amendment_action_ports",
    "build_bienes_inversion_repository",
    "build_borrador_100_snapshot_repository",
    "build_calc_sheets_parity_apply_port",
    "build_calculation_action_ports",
    "build_censal_fetch_port",
    "build_diagnostics_ports",
    "build_draft_review_ports",
    "build_expedientes_ports",
    "build_filing_action_ports",
    "build_inventory_service_ports",
    "build_ledger_evidence_ports",
    "build_modelo_edit_receipt_repository",
    "build_modelo_export_ports",
    "build_modelo_history_ports",
    "build_modelo_iva_wallet_seed_ports",
    "build_participation_index_rebuild_ports",
    "build_percepcion_observation_ports",
    "build_prorrata_register_repository",
    "build_retencion_observation_ports",
    "build_verification_repository_bundle",
    "build_work_lifecycle_ports",
    "profile_adapter_composition",
    "profile_free_adapter_composition",
]


def _bucket_event_history_repository(*, bucket_id: str) -> BucketEventHistoryRepository:
    from ..adapters.persistence.profile.buckets import build_bucket_event_history_repository

    return build_bucket_event_history_repository(bucket_id=bucket_id)


def _load_usage_ratios(*, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
    from ..adapters.persistence.profile.usage_ratios import load_usage_ratios

    return load_usage_ratios(bucket_id=bucket_id, operation=operation)


def _save_usage_ratios(profile: UsageRatioProfile, *, bucket_id: str) -> None:
    from ..adapters.persistence.profile.usage_ratios import save_usage_ratios

    save_usage_ratios(profile, bucket_id=bucket_id)


def _load_usage_ratios_with_censo_guard(
    *,
    bucket_id: str,
    raw_afectacion_ratio: Decimal | None,
    year: int,
    operation: PinnedAuthorityOperation,
) -> UsageRatioProfile:
    from ..adapters.persistence.profile.usage_ratios import load_usage_ratios_with_censo_guard

    return load_usage_ratios_with_censo_guard(
        bucket_id=bucket_id,
        raw_afectacion_ratio=raw_afectacion_ratio,
        year=year,
        operation=operation,
    )


def _confirmation_record_repository(*, bucket_id: str, settings: Settings | None) -> ConfirmationRecordRepository:
    from ..adapters.persistence.profile.confirmation_records import ConfirmationRecordRepository

    return ConfirmationRecordRepository(bucket_id=bucket_id, settings=settings)


def _extraction_draft_repository(*, bucket_id: str, settings: Settings) -> ExtractionDraftRepository:
    from ..adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository

    return ExtractionDraftRepository(bucket_id=bucket_id, settings=settings)


def _transaction_participation_index_repository(
    *,
    bucket_id: str | None = None,
) -> TransactionParticipationIndexRepository:
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository

    return TransactionParticipationIndexRepository(bucket_id=bucket_id)


def _ledger_classification_rule_repository(*, bucket_id: str) -> LedgerClassificationRuleRepository:
    from ..adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository

    return LedgerClassificationRuleRepository(bucket_id=bucket_id)


def _transaction_catalogue_repository(*, bucket_id: str) -> TransactionCatalogueRepository:
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository

    return TransactionCatalogueRepository(bucket_id=bucket_id)


def _calculation_revision_catalogue_repository(*, bucket_id: str) -> CalculationRevisionCatalogueRepository:
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository

    return CalculationRevisionCatalogueRepository(bucket_id=bucket_id)


def _modelo_record_catalogue_repository(*, bucket_id: str) -> ModeloRecordCatalogueRepository:
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository

    return ModeloRecordCatalogueRepository(bucket_id=bucket_id)


def _justificante_repository(*, bucket_id: str) -> JustificanteRepository:
    from ..adapters.persistence.profile.justificante import JustificanteRepository

    return JustificanteRepository(bucket_id=bucket_id)


def _work_unit_catalogue_repository(*, bucket_id: str) -> WorkUnitCatalogueRepository:
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository

    return WorkUnitCatalogueRepository(bucket_id=bucket_id)


def _modelo_reconciliation_persistence() -> ModeloReconciliationPersistencePort:
    from ..adapters.persistence.profile.modelo_reconciliation import build_modelo_reconciliation_persistence

    return build_modelo_reconciliation_persistence()


def _resolve_column_roles(table: NormalizedTable) -> ColumnRoleMappingPort | None:
    from ..adapters.outbound.llm.column_role_mapping import resolve_column_roles

    return resolve_column_roles(table)


@contextmanager
def profile_free_adapter_composition() -> Generator[None]:
    """Bind only what a command that reads no profile still touches.

    Every envelope names the selected profile from its plaintext summary, and
    output follows its plaintext language hint, so the custody port and the
    language resolver are bound; the persistence and outbound trees a
    profile-bound command needs are not imported at all.
    """
    from ..adapters.persistence.storage.profile_custody import build_profile_custody_port
    from ..application.user_profile.custody_ports import bind_profile_custody_port
    from ..application.user_profile.language_resolver import register_language_resolver
    from ..core.redaction.tax_identity_admission import bind_tax_identity_admission
    from ..domain.calculations.registry.tax_identity_admission import RegistryTaxIdentityAdmission

    with (
        bind_tax_identity_admission(RegistryTaxIdentityAdmission()),
        bind_profile_custody_port(build_profile_custody_port()),
    ):
        register_language_resolver()
        yield


@contextmanager
def profile_adapter_composition() -> Generator[ProfileAdapterComposition]:
    """Bind every adapter port a frontend session resolves, and unbind after.

    The imports are function-local because entering this scope is what pulls the
    adapter layer into the process: a frontend that never serves work should not
    pay for the persistence and outbound trees at import time. The yielded
    capabilities resolve on first read for the same reason.
    """
    from ..adapters.inbound.reconciliation_parser import InboundReconciliationEvidenceParser
    from ..adapters.outbound.aeat.auth.provider_selection import select_provider as select_outbound_auth_provider
    from ..adapters.outbound.aeat.auth.session_store import build_session_store
    from ..adapters.persistence.storage.profile_persistence_composition import (
        composed_profile_persistence_ports,
    )
    from ..application.auth.protocols import bind_session_store
    from ..application.auth.providers import bind_auth_provider_selector
    from ..application.bucket_event_repository import bind_bucket_event_history_repository_factory
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
    from ..application.modelo.work_unit_repository import bind_work_unit_catalogue_repository_factory
    from ..core.redaction.tax_identity_admission import bind_tax_identity_admission
    from ..domain.calculations.registry.tax_identity_admission import RegistryTaxIdentityAdmission

    with ExitStack() as composition:
        composition.enter_context(bind_tax_identity_admission(RegistryTaxIdentityAdmission()))
        profile_custody = composition.enter_context(composed_profile_persistence_ports())
        composition.enter_context(bind_bucket_event_history_repository_factory(_bucket_event_history_repository))
        composition.enter_context(bind_confirmation_record_repository_factory(_confirmation_record_repository))
        composition.enter_context(bind_column_role_mapping_resolver(_resolve_column_roles))
        composition.enter_context(bind_extraction_draft_repository_factory(_extraction_draft_repository))
        composition.enter_context(
            bind_transaction_participation_index_repository_factory(_transaction_participation_index_repository)
        )
        composition.enter_context(
            bind_ledger_classification_rule_repository_factory(_ledger_classification_rule_repository)
        )
        composition.enter_context(bind_transaction_catalogue_repository_factory(_transaction_catalogue_repository))
        composition.enter_context(
            bind_usage_ratio_profile_persistence(loader=_load_usage_ratios, saver=_save_usage_ratios)
        )
        composition.enter_context(bind_usage_ratio_censo_guard_loader(_load_usage_ratios_with_censo_guard))
        composition.enter_context(
            bind_calculation_revision_catalogue_repository_factory(_calculation_revision_catalogue_repository)
        )
        composition.enter_context(bind_modelo_record_catalogue_repository_factory(_modelo_record_catalogue_repository))
        composition.enter_context(bind_justificante_repository_factory(_justificante_repository))
        composition.enter_context(bind_work_unit_catalogue_repository_factory(_work_unit_catalogue_repository))
        composition.enter_context(bind_reconciliation_evidence_parser(InboundReconciliationEvidenceParser()))
        composition.enter_context(bind_modelo_reconciliation_persistence_factory(_modelo_reconciliation_persistence))
        composition.enter_context(bind_auth_provider_selector(select_outbound_auth_provider))
        composition.enter_context(bind_session_store(build_session_store()))
        yield ProfileAdapterComposition(profile_custody=profile_custody)
