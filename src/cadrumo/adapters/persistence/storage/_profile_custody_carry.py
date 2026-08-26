"""Concrete portable-profile custody carry over the encrypted substrate."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from types import MappingProxyType

from pydantic import BaseModel

from ....application.aggregation import PercepcionObservationRepository, RetencionObservationRepository
from ....application.calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    IvaWalletDecisionEnvelopePayload,
    IvaWalletDecisionRepository,
    iva_wallet_decision_event_key,
)
from ....application.evidence import EvidenceBundleRepository
from ....application.filing import ModeloHistoryRepository
from ....application.ledger.confirmation_record import ConfirmationRecordRepository
from ....application.ledger.counterparty_establishment import ConfirmedCounterpartyFactsRepository
from ....application.ledger.evidence import PurchaseInvoiceEvidenceRepository
from ....application.ledger.extracted_document_cache import (
    ExtractedDocumentCacheDocument,
    extracted_document_cache_object_key,
)
from ....application.ledger.extraction_draft_store import ExtractionDraftDocument, extraction_draft_object_key
from ....application.ledger.rule_repository import ledger_classification_rule_object_key
from ....application.live.borrador_100 import Borrador100Snapshot, borrador_100_snapshot_object_key
from ....application.live.deudas import PersistedDeudasSnapshot, deudas_snapshot_object_key
from ....application.live.expedientes import PersistedExpedientesSnapshot, expedientes_snapshot_object_key
from ....application.live.iva_remote_state import IvaRemoteStateAcquisitionManifestRepository
from ....application.live.justificante import JustificanteCaptureSnapshot, justificante_capture_snapshot_object_key
from ....application.live.notifications import PersistedNotificationsSnapshot, notifications_snapshot_object_key
from ....application.live.verify import VerifyObservation, verify_observation_object_key
from ....application.modelo._m036_lifecycle import M036DeclarationResult, m036_declaration_object_key
from ....application.modelo._m145_communication_records import (
    M145CommunicationRecord,
    m145_communication_record_object_key,
)
from ....application.modelo._reconciliation_records import ModeloReconciliationRecordRepository
from ....application.user_profile.custody_ports import ProfileCustodyCarryMaterial
from ....application.user_profile.repository import user_profile_snapshot_object_key
from ....core import SecureObjectWrite, StorageCustodyProfile
from ....core.external_constants import UTF_8_ENCODING as _UTF_8
from ....core.hashing import canonical_json_bytes, sha256_hex
from ....domain.evidence_consent import EvidenceConsentLedgerEntry, evidence_consent_ledger_entry_object_key
from ....domain.transactions import LedgerClassificationRule
from ....domain.user_profile.errors import ProfileExportError
from ....domain.user_profile.portable_export import CarriedSecureObject
from ....domain.user_profile.values import UserProfileSnapshot
from ...outbound.aeat.sede import (
    FiledDeclaracionObservation,
    IvaCompensationWalletObservation,
    filed_declaracion_observation_object_key,
    iva_compensation_wallet_observation_object_key,
)
from ..profile.filing_drafts import ModeloDraftRepository
from ..profile.justificante import JustificanteRepository
from ..profile.submission import SubmissionRepository
from . import (
    ATTACHMENT_MANIFEST_NAMESPACE,
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
    MODELO_FILING_RECORD_CATALOGUE_NAMESPACE,
    MODELO_WORK_UNIT_CATALOGUE_NAMESPACE,
    SECURE_OBJECT_CATALOGUE_KEY,
    STORAGE_NAMESPACE_REGISTRY,
    TRANSACTION_CATALOGUE_NAMESPACE,
    USER_PROFILE_VALUE_NAMESPACE,
    SecureBoundRepository,
    SecureObjectNamespaceDefinition,
    secure_object_repository_for_bucket,
    unwrap_blob_payload,
)
from .envelope import Envelope
from .sql import SecureObjectRecord

_TYPED_CATEGORY_NAMESPACES: frozenset[str] = frozenset(
    {
        USER_PROFILE_VALUE_NAMESPACE.namespace,
        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.namespace,
        MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
        MODELO_FILING_RECORD_CATALOGUE_NAMESPACE.namespace,
    },
)

NaturalKeyResolver = Callable[[SecureObjectRecord, str], str]


def _canonical_b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _envelope_payload[T: BaseModel](record: SecureObjectRecord, payload_type: type[T]) -> T:
    envelope_cls = Envelope[T].for_payload_type(payload_type)
    return envelope_cls.model_validate_json(record.payload.decode(_UTF_8)).payload


def _bound_resolver[T: BaseModel](repo_factory: Callable[[], SecureBoundRepository[T]]) -> NaturalKeyResolver:
    """Parse one bound repository payload and recover its natural identifier."""

    def _resolve(record: SecureObjectRecord, _bucket_id: str) -> str:
        repository = repo_factory()
        payload = _envelope_payload(record, repository.payload_model())
        return repository.extract_identifier(payload)

    return _resolve


def _snapshot_resolver[T: BaseModel](
    payload_type_factory: Callable[[], type[T]],
    object_key: Callable[[str, str], str],
    snapshot_id_attr: str = "snapshot_id",
) -> NaturalKeyResolver:
    def _resolve(record: SecureObjectRecord, bucket_id: str) -> str:
        payload = _envelope_payload(record, payload_type_factory())
        return object_key(bucket_id, getattr(payload, snapshot_id_attr))

    return _resolve


def _fixed_resolver(natural_key: str) -> NaturalKeyResolver:
    def _resolve(_record: SecureObjectRecord, _bucket_id: str) -> str:
        return natural_key

    return _resolve


def _blob_resolver(record: SecureObjectRecord, _bucket_id: str) -> str:
    return sha256_hex(unwrap_blob_payload(record.payload))


def _json_field_resolver(field: str) -> NaturalKeyResolver:
    def _resolve(record: SecureObjectRecord, _bucket_id: str) -> str:
        envelope = json.loads(record.payload.decode(_UTF_8))
        return str(envelope["payload"][field])

    return _resolve


def _bucket_template_resolver(template: str) -> NaturalKeyResolver:
    def _resolve(_record: SecureObjectRecord, bucket_id: str) -> str:
        return template.format(bucket_id=bucket_id)

    return _resolve


def _sha256_payload_resolver(record: SecureObjectRecord, _bucket_id: str) -> str:
    return sha256_hex(record.payload)


def _natural_key_resolvers() -> dict[str, NaturalKeyResolver]:
    """Return the single natural-key resolver registry for carried namespaces."""
    resolvers: dict[str, NaturalKeyResolver] = {}

    resolvers["cadrumo.domain.attachments.blobs"] = _blob_resolver
    resolvers["cadrumo.domain.attachments.manifests"] = _json_field_resolver("sha256")

    def _observations_repo() -> CalculationObservationRepository:
        return CalculationObservationRepository()

    resolvers["cadrumo.calculations.observations"] = _bound_resolver(_observations_repo)

    def _iva_history_repo() -> IvaCompensationHistoryRepository:
        return IvaCompensationHistoryRepository()

    resolvers["cadrumo.calculations.iva_compensation.history"] = _bound_resolver(_iva_history_repo)

    def _iva_wallet_repo() -> IvaWalletDecisionRepository:
        return IvaWalletDecisionRepository()

    resolvers["cadrumo.calculations.iva_wallet.reconciliation_decisions"] = _bound_resolver(_iva_wallet_repo)

    def _iva_wallet_event_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        payload = _envelope_payload(record, IvaWalletDecisionEnvelopePayload)
        return iva_wallet_decision_event_key(payload.decision)

    resolvers["cadrumo.calculations.iva_wallet.reconciliation_decision_events"] = _iva_wallet_event_key

    def _reconciliation_records_repo() -> ModeloReconciliationRecordRepository:
        return ModeloReconciliationRecordRepository()

    resolvers["cadrumo.modelo.reconciliation.records"] = _bound_resolver(_reconciliation_records_repo)
    resolvers["cadrumo.domain.buckets.event_history"] = _fixed_resolver(SECURE_OBJECT_CATALOGUE_KEY)

    def _justificante_payload() -> type[JustificanteCaptureSnapshot]:
        return JustificanteCaptureSnapshot

    def _justificante_key(bucket_id: str, snapshot_id: str) -> str:
        return justificante_capture_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["cadrumo.application.live.justificante_capture_snapshot"] = _snapshot_resolver(
        _justificante_payload,
        _justificante_key,
    )

    def _notifications_payload() -> type[PersistedNotificationsSnapshot]:
        return PersistedNotificationsSnapshot

    def _notifications_key(bucket_id: str, snapshot_id: str) -> str:
        return notifications_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["cadrumo.application.live.notifications_snapshot"] = _snapshot_resolver(
        _notifications_payload,
        _notifications_key,
    )

    def _expedientes_payload() -> type[PersistedExpedientesSnapshot]:
        return PersistedExpedientesSnapshot

    def _expedientes_key(bucket_id: str, snapshot_id: str) -> str:
        return expedientes_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["cadrumo.application.live.expedientes_snapshot"] = _snapshot_resolver(
        _expedientes_payload,
        _expedientes_key,
    )

    def _justificante_metadata_repo() -> JustificanteRepository:
        return JustificanteRepository()

    resolvers["cadrumo.domain.justificante.metadata"] = _bound_resolver(_justificante_metadata_repo)

    def _retencion_repo() -> RetencionObservationRepository:
        return RetencionObservationRepository()

    resolvers["cadrumo.retenciones.observations"] = _bound_resolver(_retencion_repo)

    def _percepciones_repo() -> PercepcionObservationRepository:
        return PercepcionObservationRepository()

    resolvers["cadrumo.withholding.observations"] = _bound_resolver(_percepciones_repo)

    def _filing_history_repo() -> ModeloHistoryRepository:
        return ModeloHistoryRepository()

    resolvers["cadrumo.application.filing.history"] = _bound_resolver(_filing_history_repo)

    def _iva_remote_state_repo() -> IvaRemoteStateAcquisitionManifestRepository:
        return IvaRemoteStateAcquisitionManifestRepository()

    resolvers["cadrumo.application.live.iva_remote_state_acquisitions"] = _bound_resolver(_iva_remote_state_repo)

    def _evidence_bundle_repo() -> EvidenceBundleRepository:
        return EvidenceBundleRepository()

    resolvers["cadrumo.application.evidence.bundles"] = _bound_resolver(_evidence_bundle_repo)

    def _purchase_invoice_evidence_repo() -> PurchaseInvoiceEvidenceRepository:
        return PurchaseInvoiceEvidenceRepository()

    resolvers["cadrumo.application.ledger.purchase_invoice_evidence"] = _bound_resolver(
        _purchase_invoice_evidence_repo,
    )

    def _classification_rule_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        rule = _envelope_payload(record, LedgerClassificationRule)
        return ledger_classification_rule_object_key(rule)

    resolvers["cadrumo.ledger.classification.rules"] = _classification_rule_key

    def _submission_repo() -> SubmissionRepository:
        return SubmissionRepository()

    resolvers["cadrumo.domain.submission.records"] = _bound_resolver(_submission_repo)

    def _draft_repo() -> ModeloDraftRepository:
        return ModeloDraftRepository()

    resolvers["cadrumo.domain.filing.drafts"] = _bound_resolver(_draft_repo)
    resolvers["cadrumo.domain.filing.amendments"] = _json_field_resolver("amendment_id")
    resolvers["cadrumo.domain.usage_ratios"] = _bucket_template_resolver("profile:{bucket_id}")
    resolvers["cadrumo.auth.apoderado"] = _bucket_template_resolver("{bucket_id}")

    def _borrador_payload() -> type[Borrador100Snapshot]:
        return Borrador100Snapshot

    def _borrador_key(bucket_id: str, snapshot_id: str) -> str:
        return borrador_100_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["cadrumo.application.live.borrador_100_snapshot"] = _snapshot_resolver(
        _borrador_payload,
        _borrador_key,
    )

    def _m036_payload() -> type[M036DeclarationResult]:
        return M036DeclarationResult

    def _m036_key(bucket_id: str, declaration_id: str) -> str:
        return m036_declaration_object_key(bucket_id, declaration_id)

    resolvers["cadrumo.application.modelo.m036_declaration"] = _snapshot_resolver(
        _m036_payload,
        _m036_key,
        snapshot_id_attr="declaration_id",
    )

    def _m145_communication_key(record: SecureObjectRecord, bucket_id: str) -> str:
        communication = _envelope_payload(record, M145CommunicationRecord)
        if communication.bucket_id != bucket_id:
            raise ValueError("Modelo 145 communication record bucket_id does not match its custody bucket")
        return m145_communication_record_object_key(
            communication.bucket_id,
            communication.communication_record_id,
        )

    resolvers["cadrumo.application.modelo.m145_communication_record"] = _m145_communication_key

    def _verify_payload() -> type[VerifyObservation]:
        return VerifyObservation

    def _verify_key(bucket_id: str, observation_id: str) -> str:
        return verify_observation_object_key(bucket_id, observation_id)

    resolvers["cadrumo.application.live.verify_observations"] = _snapshot_resolver(
        _verify_payload,
        _verify_key,
        snapshot_id_attr="observation_id",
    )

    def _profile_snapshot_payload() -> type[UserProfileSnapshot]:
        return UserProfileSnapshot

    def _profile_snapshot_key(bucket_id: str, snapshot_id: str) -> str:
        return user_profile_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["cadrumo.application.user_profile.snapshot"] = _snapshot_resolver(
        _profile_snapshot_payload,
        _profile_snapshot_key,
    )

    resolvers["cadrumo.outbound.aeat.sede.filed_declaration.artefacts"] = _sha256_payload_resolver

    def _filed_observation_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        observation = _envelope_payload(record, FiledDeclaracionObservation)
        return filed_declaracion_observation_object_key(
            observation.modelo,
            observation.ejercicio,
            observation.period,
            observation.expediente_id,
        )

    resolvers["cadrumo.outbound.aeat.sede.filed_declaration.observations"] = _filed_observation_key

    def _iva_wallet_observation_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        observation = _envelope_payload(record, IvaCompensationWalletObservation)
        return iva_compensation_wallet_observation_object_key(
            observation.taxpayer_nif,
            observation.target_year,
            observation.target_period,
            observation.captured_at.isoformat(),
        )

    resolvers["cadrumo.outbound.aeat.sede.iva_compensation_wallet.observations"] = _iva_wallet_observation_key
    resolvers.update(_ledger_extraction_and_live_deudas_natural_key_resolvers())
    return resolvers


def _ledger_extraction_and_live_deudas_natural_key_resolvers() -> dict[str, NaturalKeyResolver]:
    resolvers: dict[str, NaturalKeyResolver] = {}

    def _extracted_document_cache_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        document = _envelope_payload(record, ExtractedDocumentCacheDocument)
        return extracted_document_cache_object_key(document)

    resolvers["cadrumo.application.ledger.extracted_document_cache"] = _extracted_document_cache_key

    def _extraction_draft_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        document = _envelope_payload(record, ExtractionDraftDocument)
        return extraction_draft_object_key(document)

    resolvers["cadrumo.application.ledger.extraction_draft"] = _extraction_draft_key

    def _confirmation_record_repo() -> ConfirmationRecordRepository:
        return ConfirmationRecordRepository()

    resolvers["cadrumo.application.ledger.confirmation_record"] = _bound_resolver(_confirmation_record_repo)

    def _confirmed_counterparty_facts_repo() -> ConfirmedCounterpartyFactsRepository:
        return ConfirmedCounterpartyFactsRepository()

    resolvers["cadrumo.application.ledger.confirmed_counterparty_facts"] = _bound_resolver(
        _confirmed_counterparty_facts_repo,
    )

    def _deudas_payload() -> type[PersistedDeudasSnapshot]:
        return PersistedDeudasSnapshot

    def _deudas_key(bucket_id: str, snapshot_id: str) -> str:
        return deudas_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["cadrumo.application.live.deudas_snapshot"] = _snapshot_resolver(_deudas_payload, _deudas_key)

    def _evidence_consent_ledger_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        entry_payload = json.loads(record.payload.decode(_UTF_8))["entry"]
        entry = EvidenceConsentLedgerEntry.model_validate_json(json.dumps(entry_payload))
        return evidence_consent_ledger_entry_object_key(entry)

    resolvers["cadrumo.outbound.llm.evidence_consent_ledger"] = _evidence_consent_ledger_key
    return resolvers


def _carried_namespace_definitions(
    profile: StorageCustodyProfile,
) -> tuple[SecureObjectNamespaceDefinition, ...]:
    return tuple(
        definition
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces_for_custody_profile(profile)
        if definition.namespace not in _TYPED_CATEGORY_NAMESPACES
    )


def _serialize_carried_objects(
    *,
    bucket_id: str,
    profile: StorageCustodyProfile,
    definitions: tuple[SecureObjectNamespaceDefinition, ...],
) -> tuple[CarriedSecureObject, ...]:
    repository = secure_object_repository_for_bucket(bucket_id)
    resolvers = _natural_key_resolvers()
    carried: list[CarriedSecureObject] = []
    for definition in definitions:
        keys = repository.list_keys(definition.namespace)
        if not keys:
            continue
        resolver = resolvers.get(definition.namespace)
        if resolver is None and definition.default_object_key is not None:
            resolver = _fixed_resolver(definition.default_object_key)
        if resolver is None:
            raise ProfileExportError(
                translated_message="errors.fail.profile_export",
                context={
                    "namespace": definition.namespace,
                    "custody_profile": profile.value,
                    "natural_key_resolver_present": False,
                },
            )
        for record in repository.list_records(
            definition.namespace,
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        ):
            try:
                object_key = resolver(record, bucket_id)
            except Exception as exc:
                raise ProfileExportError(
                    translated_message="errors.fail.profile_export",
                    context={
                        "namespace": definition.namespace,
                        "resolver_error_type": type(exc).__name__,
                        "natural_key_resolved": False,
                    },
                ) from exc
            carried.append(
                CarriedSecureObject(
                    namespace=record.namespace,
                    object_key=object_key,
                    classification=record.classification,
                    schema_version=record.schema_version,
                    written_at=record.written_at,
                    payload_b64=_canonical_b64(record.payload),
                ),
            )
    return tuple(carried)


def collect_profile_custody_carry(
    *,
    bucket_id: str,
    profile: StorageCustodyProfile,
) -> ProfileCustodyCarryMaterial:
    """Resolve persisted carry rows and coverage facts for one active bucket."""
    repository = secure_object_repository_for_bucket(bucket_id)
    populated_namespaces = tuple(repository.list_namespaces())
    row_counts_by_namespace = {namespace: len(repository.list_keys(namespace)) for namespace in populated_namespaces}
    definitions = _carried_namespace_definitions(profile)
    carried_namespace_set = frozenset(definition.namespace for definition in definitions)
    registered_namespaces = frozenset(definition.namespace for definition in STORAGE_NAMESPACE_REGISTRY.namespaces)
    carried_objects = _serialize_carried_objects(
        bucket_id=bucket_id,
        profile=profile,
        definitions=definitions,
    )
    return ProfileCustodyCarryMaterial(
        carried_objects=carried_objects,
        carried_namespaces=tuple(
            definition.namespace
            for definition in definitions
            if row_counts_by_namespace.get(definition.namespace, 0) > 0
        ),
        excluded_namespaces=tuple(
            namespace for namespace in populated_namespaces if namespace not in carried_namespace_set
        ),
        row_counts_by_namespace=MappingProxyType(row_counts_by_namespace),
        unclassified_namespaces=tuple(
            namespace for namespace in populated_namespaces if namespace not in registered_namespaces
        ),
    )


def restore_profile_custody_carry(
    carried_objects: tuple[CarriedSecureObject, ...],
    *,
    target_bucket_id: str,
) -> None:
    """Atomically re-key and persist every carried row in the target bucket."""
    writes = tuple(
        SecureObjectWrite(
            namespace=carried.namespace,
            object_key=carried.object_key,
            classification=carried.classification,
            schema_version=carried.schema_version,
            written_at=carried.written_at,
            payload=_rebound_payload(carried, target_bucket_id=target_bucket_id),
        )
        for carried in carried_objects
    )
    if writes:
        secure_object_repository_for_bucket(target_bucket_id).save_many(writes)


def _rebound_payload(carried: CarriedSecureObject, *, target_bucket_id: str) -> bytes:
    if carried.namespace != ATTACHMENT_MANIFEST_NAMESPACE.namespace:
        return carried.payload
    envelope = json.loads(carried.payload.decode(_UTF_8))
    envelope["payload"]["bucket_id"] = target_bucket_id
    return canonical_json_bytes(envelope)


__all__ = ["collect_profile_custody_carry", "restore_profile_custody_carry"]
