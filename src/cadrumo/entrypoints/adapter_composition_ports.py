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

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from ..adapters.persistence.storage.sql.secure_object_records import SecureObjectNamespaceIntegrity
    from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
    from ..application.aggregation.percepciones_observations_repository import (
        PercepcionObservationPorts,
    )
    from ..application.aggregation.retencion_observations_repository import (
        RetencionObservationPorts,
    )
    from ..application.aggregation.withholding_observation_service import WithholdingObservationService
    from ..application.auth.operator_probe_ports import OperatorProbePorts
    from ..application.auth.session_types import AeatSession
    from ..application.bienes_inversion.ports import (
        BienesInversionIvaRegisterRepositoryProtocol,
    )
    from ..application.diagnostics_ports import DiagnosticsPorts
    from ..application.filing.draft_review_ports import DraftReviewPorts
    from ..application.inventory.ports import InventoryServicePorts
    from ..application.live.borrador_100 import (
        Borrador100SnapshotRepository,
    )
    from ..application.live.censo_ports import CensalFetchPort
    from ..application.modelo.edit_receipt_ports import (
        ModeloEditReceiptRepositoryPort,
    )
    from ..application.modelo.export_ports import ModeloExportPorts
    from ..application.modelo.history_ports import ModeloHistoryPorts
    from ..application.modelo.iva_wallet_seed_ports import (
        ModeloIvaWalletSeedPorts,
    )
    from ..application.modelo.participation_index_rebuild_ports import (
        ParticipationIndexRebuildPorts,
    )
    from ..application.prorrata_register.ports import (
        ProrrataRegisterServiceRepositoryProtocol,
    )
    from ..application.user_profile.profile_read_ports import ProfileReadPorts
    from ..core.config import Settings
    from ..domain.attachments.protocols import AttachmentStoreProtocol
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..domain.calculations.registry.tax_id_format import SubjectTaxId


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
    from ..application.live.errors import LiveApplicationError, raise_if_aeat_session_ended
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
            raise_if_aeat_session_ended(exc)
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


def build_modelo_export_ports(
    *,
    bucket_id: str,
    m303_rectificativa_taxpayer_tax_id: SubjectTaxId,
    operation: PinnedAuthorityOperation,
    objects: SecureObjectRepository | None = None,
) -> ModeloExportPorts:
    """Compose every persisted authority required by one Modelo export.

    Parameter types: ``objects``
    (:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`).
    """
    from ..adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.modelo_360_solicitud import Modelo360SolicitudRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.own_accounts import OwnAccountRepository
    from ..adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.export_ports import ModeloExportPorts
    from ..domain.filing.software_identity import development_mock_software_identity
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_resolved_identity

    normalized_bucket_id = bucket_id.strip()
    objects = objects if objects is not None else secure_object_repository_for_bucket(normalized_bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_resolved_identity(
        bucket_id=normalized_bucket_id,
        objects=objects,
        operation=operation,
        taxpayer_tax_id=m303_rectificativa_taxpayer_tax_id,
    )
    return ModeloExportPorts(
        calculation=calculation_binding.calculation_repository(),
        work_unit=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        filing=ModeloRecordCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        verification=calculation_binding.verification_repository(),
        bucket_event=BucketEventHistoryRepository(objects=objects),
        observation=CalculationObservationRepository(objects=objects),
        iva_compensation_decision=IvaWalletDecisionRepository(objects=objects, operation=operation),
        iva_compensation_history=IvaCompensationHistoryRepository(objects=objects),
        justificante=JustificanteRepository(objects=objects),
        prorrata_register=ProrrataRegisterRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        bienes_inversion=BienesInversionIvaRegisterRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        m360_solicitud=Modelo360SolicitudRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        own_accounts=OwnAccountRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        transaction=TransactionCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        draft_review_ports=build_draft_review_ports(
            bucket_id=normalized_bucket_id, operation=operation, objects=objects
        ),
        retencion_observation_ports=build_retencion_observation_ports(bucket_id=normalized_bucket_id, objects=objects),
        # No AEAT-registered developer identity exists yet; the mock is graded
        # on every export result so no surface presents its file as presentable.
        product_software_identity=development_mock_software_identity(),
    )


def profile_read_ports_for_bucket(bucket_id: str) -> ProfileReadPorts:
    """Bind profile read ports to the requested bucket."""
    return build_profile_read_ports(bucket_id=bucket_id)


def build_profile_read_ports(*, bucket_id: str) -> ProfileReadPorts:
    """Compose the authenticated profile projection for one calculation bucket."""
    from ..domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        return build_pinned_profile_read_ports(bucket_id=bucket_id, operation=operation)


def build_pinned_profile_read_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ProfileReadPorts:
    """Compose profile decoding under the operation's retained authority pin."""
    from ..adapters.persistence.profile.profile_path_values import ProfilePathValuesPersistenceAdapter
    from ..application.user_profile.profile_read_ports import ProfileReadPorts
    from ..application.user_profile.profile_record_repository import ProfileRecordRepository

    normalized_bucket_id = bucket_id.strip()
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


def build_diagnostics_ports(*, bucket_id: str | None = None) -> DiagnosticsPorts:
    """Compose diagnostics for an exact bucket or the current operator route."""
    from ..adapters.persistence.storage.master_key.active_session import NoActiveBucketSessionError
    from ..adapters.persistence.storage.runtime_repository import (
        secure_object_repository_for_active_bucket,
        secure_object_repository_for_bucket,
    )
    from ..application.diagnostics_ports import DiagnosticSecureObjectNamespace, DiagnosticsPorts

    class SecureObjectDiagnosticsAdapter:
        """Translate storage integrity records into application diagnostic DTOs."""

        @staticmethod
        def _repository() -> SecureObjectRepository:
            if bucket_id is not None:
                return secure_object_repository_for_bucket(bucket_id)
            return secure_object_repository_for_active_bucket()

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


def build_draft_review_ports(
    *, bucket_id: str, operation: PinnedAuthorityOperation | None = None, objects: SecureObjectRepository | None = None
) -> DraftReviewPorts:
    """Compose draft review using the caller's authority pin when supplied.

    Parameter types: ``objects``
    (:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`).
    """
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
    objects = objects if objects is not None else secure_object_repository_for_bucket(normalized_bucket_id)
    if operation is not None:
        profile_decode_context = operation.profile_decode_context()
    else:
        with bundled_indexed_authority().operation() as selected_operation:
            profile_decode_context = selected_operation.profile_decode_context()

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


def build_modelo_history_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloHistoryPorts:
    """Compose every persisted authority required by Modelo history reads."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.history_ports import ModeloHistoryPorts
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=normalized_bucket_id,
        objects=objects,
        operation=operation,
    )
    return ModeloHistoryPorts(
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


def build_participation_index_rebuild_ports(
    *, bucket_id: str, operation: PinnedAuthorityOperation
) -> ParticipationIndexRebuildPorts:
    """Compose every persisted authority required by a participation-index rebuild."""
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.participation_index_rebuild_ports import ParticipationIndexRebuildPorts
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=normalized_bucket_id,
        objects=objects,
        operation=operation,
    )
    return ParticipationIndexRebuildPorts(
        calculation_repository=calculation_binding.calculation_repository(),
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


def build_modelo_iva_wallet_seed_ports(
    *, bucket_id: str, operation: PinnedAuthorityOperation
) -> ModeloIvaWalletSeedPorts:
    """Compose every persisted authority required by IVA-wallet seed operations."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.calculation_observations import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from ..adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.calculations.observations_repository import CalculationObservationPorts
    from ..application.modelo.iva_wallet_seed_ports import ModeloIvaWalletSeedPorts
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=normalized_bucket_id,
        objects=objects,
        operation=operation,
    )
    return ModeloIvaWalletSeedPorts(
        work_unit_repository=WorkUnitCatalogueRepository(
            bucket_id=normalized_bucket_id,
            objects=objects,
        ),
        calculation_repository=calculation_binding.calculation_repository(),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        calculation_observation_ports=CalculationObservationPorts(
            observation_repository=CalculationObservationRepository(objects=objects),
            iva_wallet_decision_repository=IvaWalletDecisionRepository(objects=objects, operation=operation),
        ),
        iva_compensation_history_repository=IvaCompensationHistoryRepository(objects=objects),
    )


def build_inventory_service_ports(*, bucket_id: str) -> InventoryServicePorts:
    """Compose the encrypted inventory repository and bucket-event sink."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.inventory import InventoryLedgerRepository
    from ..adapters.persistence.profile.inventory_documents import attachment_source_file_name
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
        document_file_name=lambda content_digest: attachment_source_file_name(objects, content_digest),
    )


def build_borrador_100_snapshot_repository(
    *, bucket_id: str, objects: SecureObjectRepository | None = None
) -> Borrador100SnapshotRepository:
    """Bind the encrypted borrador snapshot adapter to one profile bucket.

    Parameter types: ``objects``
    (:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`).
    """
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
        objects=objects if objects is not None else secure_object_repository_for_bucket(normalized_bucket_id),
        classification_error_factory=translate_classification_refusal,
        version_error_factory=translate_version_refusal,
    )


def build_retencion_observation_ports(
    *, bucket_id: str, objects: SecureObjectRepository | None = None
) -> RetencionObservationPorts:
    """Compose the encrypted retención observation capability for one bucket.

    Parameter types: ``objects``
    (:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`).
    """
    from ..adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.aggregation.retencion_observations_repository import RetencionObservationPorts

    normalized_bucket_id = bucket_id.strip()
    return RetencionObservationPorts(
        repository=RetencionObservationRepositoryAdapter(
            objects=objects if objects is not None else secure_object_repository_for_bucket(normalized_bucket_id),
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


def build_withholding_observation_service(*, bucket_id: str) -> WithholdingObservationService:
    """Compose the one atomic withholding-window mutation service for a bucket."""
    from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ..adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
    from ..adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.profile.withholding_observation_workflow import WithholdingObservationWorkflowAdapter
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..adapters.persistence.storage.sql.secure_object_records import SecureObjectRevisionAssertion
    from ..application.aggregation.withholding_observation_service import (
        WithholdingObservationMutationError,
        WithholdingObservationService,
        WithholdingSourceCatalogueBaseline,
    )
    from ..application.ledger.persistence_ports import LedgerPersistenceConflictError
    from ..core.aggregation import BindingSourceKind

    objects = secure_object_repository_for_bucket(bucket_id.strip())

    def source_assertions(baseline: WithholdingSourceCatalogueBaseline) -> tuple[SecureObjectRevisionAssertion, ...]:
        if baseline.source_kind is BindingSourceKind.PAYABLE_INVOICE:
            return InvoiceCatalogueRepository(bucket_id=bucket_id, objects=objects).revision_assertions(
                expected_revision_id=baseline.revision_id
            )
        try:
            return TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects).revision_assertions(
                expected_revision_id=baseline.revision_id
            )
        except LedgerPersistenceConflictError as exc:
            raise WithholdingObservationMutationError("source_revision_changed") from exc

    return WithholdingObservationService(
        WithholdingObservationWorkflowAdapter(
            objects=objects,
            retenciones=RetencionObservationRepositoryAdapter(objects=objects),
            percepciones=PercepcionObservationRepositoryAdapter(objects=objects),
            source_catalogue_assertions=source_assertions,
        ),
    )


def build_attachment_store(bucket_id: str) -> AttachmentStoreProtocol:
    """Bind encrypted attachment custody to the profile bucket's secure repository."""
    from ..adapters.persistence.storage.attachment import AttachmentStore
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    normalized_bucket_id = bucket_id.strip()
    return AttachmentStore(objects=secure_object_repository_for_bucket(normalized_bucket_id))
