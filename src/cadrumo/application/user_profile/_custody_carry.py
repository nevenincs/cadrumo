"""Generic per-bucket secure-object custody carry for portable bundles.

The portable bundle's five typed categories (profile, work units, ledger,
calculation revisions, filing records) are carried by dedicated typed fields.
Every *other* durable per-bucket secure-object store is carried generically by
this module so an export/import round-trip restores the whole bucket: evidence
bytes, the cross-period calculation inputs, the live captures, and the audit
trail.

Mechanism. Each carried row is read from the encrypted substrate with its
decrypted :class:`Envelope` payload bytes intact and re-keyed by its **natural**
object key (never the stored HMAC digest, which is derived from the per-bucket
data-encryption key and is therefore unreadable in a recipient bucket — see the
custody roundtrip tests). On import each row is re-saved through the raw
secure-object substrate under that natural key, which the recipient bucket
re-digests under its own DEK and re-encrypts. This is the substrate-level
counterpart of the typed categories' ``repository.save`` re-encrypt-on-import
path and honours the same ``D2`` decrypted-payload custody contract.

The set of carried namespaces is registry-driven: it is exactly the namespaces
whose
:class:`~adapters.persistence.storage.StorageCustodyDisposition`
is in the requested custody profile, minus the five typed-category namespaces
this module deliberately leaves to the typed bundle fields. A populated,
carried-disposition namespace with no natural key resolver fails the export
fail-closed, so a newly-registered durable store cannot be silently dropped.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...adapters.outbound.aeat.sede import (
    FiledDeclaracionObservation,
    IvaCompensationWalletObservation,
    filed_declaracion_observation_object_key,
    iva_compensation_wallet_observation_object_key,
)
from ...adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ...adapters.persistence.profile.justificante import JustificanteRepository
from ...adapters.persistence.profile.submission import SubmissionRepository
from ...adapters.persistence.storage import (
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
    MODELO_FILING_RECORD_CATALOGUE_NAMESPACE,
    MODELO_WORK_UNIT_CATALOGUE_NAMESPACE,
    SECURE_OBJECT_CATALOGUE_KEY,
    STORAGE_NAMESPACE_REGISTRY,
    TRANSACTION_CATALOGUE_NAMESPACE,
    USER_PROFILE_VALUE_NAMESPACE,
    SecureBoundRepository,
    SecureObjectNamespaceDefinition,
    StorageCustodyProfile,
    secure_object_repository_for_bucket,
)
from ...adapters.persistence.storage.attachment import _unwrap_blob_payload
from ...adapters.persistence.storage.envelope import Envelope
from ...core.external_constants import UTF_8_ENCODING as _UTF_8
from ...core.hashing import sha256_hex
from ...domain.user_profile import CarriedSecureObject, ProfileExportError, UserProfileSnapshot
from ..aggregation import PercepcionObservationRepository, RetencionObservationRepository
from ..calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    IvaWalletDecisionEnvelopePayload,
    IvaWalletDecisionRepository,
    iva_wallet_decision_event_key,
)
from ..evidence import EvidenceBundleRepository
from ..filing import ModeloHistoryRepository
from ..ledger import (
    BusinessOperationInvoiceRepository,
    LedgerClassificationRuleRepository,
    PurchaseInvoiceEvidenceRepository,
)
from ..live import (
    Borrador100Snapshot,
    IvaRemoteStateAcquisitionManifestRepository,
    JustificanteCaptureSnapshot,
    PersistedExpedientesSnapshot,
    PersistedNotificationsSnapshot,
    VerifyObservation,
    borrador_100_snapshot_object_key,
    expedientes_snapshot_object_key,
    justificante_capture_snapshot_object_key,
    notifications_snapshot_object_key,
    verify_observation_object_key,
)
from ..modelo import (
    M036DeclarationResult,
    M145CommunicationRecord,
    m036_declaration_object_key,
    m145_communication_record_object_key,
)
from ._repository import user_profile_snapshot_object_key

if TYPE_CHECKING:
    from ...adapters.persistence.storage.sql import SecureObjectRecord

#: Namespaces carried by the typed bundle fields; the generic carry skips them so
#: they are not double-carried, and the bundle's coverage manifest counts them as
#: covered. Both decisions read this one set, and each member names its registered
#: definition rather than restating the namespace string: an entry that drifted
#: from the registry would silently re-admit a typed store into the generic carry,
#: which no coverage gate would catch.
TYPED_CATEGORY_NAMESPACES: frozenset[str] = frozenset(
    {
        USER_PROFILE_VALUE_NAMESPACE.namespace,
        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.namespace,
        MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
        MODELO_FILING_RECORD_CATALOGUE_NAMESPACE.namespace,
    },
)


# A natural-key resolver maps one decrypted substrate record (in the active
# bucket session) to its natural object key.
NaturalKeyResolver = Callable[["SecureObjectRecord", str], str]


def _canonical_b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _envelope_payload[T: BaseModel](record: SecureObjectRecord, payload_type: type[T]) -> T:
    envelope_cls = Envelope.for_payload_type(payload_type)
    return envelope_cls.model_validate_json(record.payload.decode(_UTF_8)).payload


def _bound_resolver[T: BaseModel](repo_factory: Callable[[], SecureBoundRepository[T]]) -> NaturalKeyResolver:
    """Resolver for a ``SecureBoundRepository`` store: parse, then extract_identifier."""

    def _resolve(record: SecureObjectRecord, _bucket_id: str) -> str:
        repo = repo_factory()
        payload = _envelope_payload(record, repo.payload_model())
        return repo.extract_identifier(payload)

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
    return sha256_hex(_unwrap_blob_payload(record.payload))


def _json_field_resolver(field: str) -> NaturalKeyResolver:
    """Resolver for an :class:`Envelope` row whose natural key is one top-level payload field."""

    def _resolve(record: SecureObjectRecord, _bucket_id: str) -> str:
        envelope = json.loads(record.payload.decode(_UTF_8))
        return str(envelope["payload"][field])

    return _resolve


def _bucket_template_resolver(template: str) -> NaturalKeyResolver:
    def _resolve(_record: SecureObjectRecord, bucket_id: str) -> str:
        return template.format(bucket_id=bucket_id)

    return _resolve


def _sha256_payload_resolver(record: SecureObjectRecord, _bucket_id: str) -> str:
    """Resolver for a raw-bytes row content-addressed by the SHA-256 of its payload."""
    return sha256_hex(record.payload)


# ---------------------------------------------------------------------------
# Per-namespace natural-key resolver registry
# ---------------------------------------------------------------------------


def _natural_key_resolvers() -> dict[str, NaturalKeyResolver]:
    """Return the natural-key resolver for every generically-carried namespace.

    Keyed by the persisted namespace string.
    """
    resolvers: dict[str, NaturalKeyResolver] = {}

    # --- Attachments (evidence bytes + manifests) ----------------------------
    resolvers["cadrumo.domain.attachments.blobs"] = _blob_resolver

    # The manifest store strips ``attachment_id`` from the persisted payload (it is
    # the object key, re-injected on load) so ``Envelope[Attachment]`` will not parse;
    # the natural key is recoverable from the retained content-addressed ``sha256``,
    # which the model enforces to equal ``attachment_id``.
    resolvers["cadrumo.domain.attachments.manifests"] = _json_field_resolver("sha256")

    # --- Cross-period calculation inputs (SecureBoundRepository) --------------
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

    # --- Audit trail ---------------------------------------------------------
    resolvers["cadrumo.domain.buckets.event_history"] = _fixed_resolver(SECURE_OBJECT_CATALOGUE_KEY)

    # --- Live captures (SecureSnapshotRepository) ----------------------------
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

    # --- Justificante metadata (SecureBoundRepository) -----------------------
    def _justificante_metadata_repo() -> JustificanteRepository:
        return JustificanteRepository()

    resolvers["cadrumo.domain.justificante.metadata"] = _bound_resolver(_justificante_metadata_repo)

    # --- Withholding / retencion observations (SecureBoundRepository) ---------
    def _retencion_repo() -> RetencionObservationRepository:
        return RetencionObservationRepository()

    resolvers["cadrumo.retenciones.observations"] = _bound_resolver(_retencion_repo)

    def _percepciones_repo() -> PercepcionObservationRepository:
        return PercepcionObservationRepository()

    resolvers["cadrumo.withholding.observations"] = _bound_resolver(_percepciones_repo)

    # --- Filing/ledger/submission state (SecureBoundRepository) ---------------
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

    resolvers["cadrumo.application.ledger.purchase_invoice_evidence"] = _bound_resolver(_purchase_invoice_evidence_repo)

    def _business_operation_invoice_repo() -> BusinessOperationInvoiceRepository:
        return BusinessOperationInvoiceRepository()

    resolvers["cadrumo.application.ledger.business_operation_invoices"] = _bound_resolver(
        _business_operation_invoice_repo
    )

    def _classification_rule_repo() -> LedgerClassificationRuleRepository:
        return LedgerClassificationRuleRepository()

    resolvers["cadrumo.ledger.classification.rules"] = _bound_resolver(_classification_rule_repo)

    def _submission_repo() -> SubmissionRepository:
        return SubmissionRepository()

    resolvers["cadrumo.domain.submission.records"] = _bound_resolver(_submission_repo)

    def _draft_repo() -> ModeloDraftRepository:
        return ModeloDraftRepository()

    resolvers["cadrumo.domain.filing.drafts"] = _bound_resolver(_draft_repo)

    # --- Filing amendments (union payload; key is a top-level field) ----------
    resolvers["cadrumo.domain.filing.amendments"] = _json_field_resolver("amendment_id")

    # --- Per-bucket single-document stores -----------------------------------
    resolvers["cadrumo.domain.usage_ratios"] = _bucket_template_resolver("profile:{bucket_id}")
    resolvers["cadrumo.auth.apoderado"] = _bucket_template_resolver("{bucket_id}")

    # --- Live snapshot captures (SecureSnapshotRepository) --------------------
    def _borrador_payload() -> type[Borrador100Snapshot]:
        return Borrador100Snapshot

    def _borrador_key(bucket_id: str, snapshot_id: str) -> str:
        return borrador_100_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["cadrumo.application.live.borrador_100_snapshot"] = _snapshot_resolver(_borrador_payload, _borrador_key)

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

    # --- AEAT-outbound filed-declaration state -------------------------------
    resolvers["cadrumo.outbound.aeat.sede.filed_declaration.artefacts"] = _sha256_payload_resolver

    def _filed_observation_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        obs = _envelope_payload(record, FiledDeclaracionObservation)
        return filed_declaracion_observation_object_key(
            obs.modelo,
            obs.ejercicio,
            obs.period,
            obs.expediente_id,
        )

    resolvers["cadrumo.outbound.aeat.sede.filed_declaration.observations"] = _filed_observation_key

    def _iva_wallet_observation_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        obs = _envelope_payload(record, IvaCompensationWalletObservation)
        return iva_compensation_wallet_observation_object_key(
            obs.taxpayer_nif,
            obs.target_year,
            obs.target_period,
            obs.captured_at.isoformat(),
        )

    resolvers["cadrumo.outbound.aeat.sede.iva_compensation_wallet.observations"] = _iva_wallet_observation_key

    return resolvers


# ---------------------------------------------------------------------------
# Serialise / restore
# ---------------------------------------------------------------------------


def carried_namespace_definitions(
    profile: StorageCustodyProfile,
) -> tuple[SecureObjectNamespaceDefinition, ...]:
    """Return carried :class:`SecureObjectNamespaceDefinition` rows for ``profile``."""
    return tuple(
        definition
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces_for_custody_profile(profile)
        if definition.namespace not in TYPED_CATEGORY_NAMESPACES
    )


def serialize_carried_objects(
    *,
    bucket_id: str,
    profile: StorageCustodyProfile,
) -> tuple[CarriedSecureObject, ...]:
    """Serialise every generically-carried :class:`CarriedSecureObject` row for ``profile``.

    Reads each carried namespace from the active bucket's encrypted substrate,
    resolving each row's natural key. A populated carried namespace with no
    resolver raises, fail-closed, so the carry can never silently drop a store.
    """
    repository = secure_object_repository_for_bucket(bucket_id)
    resolvers = _natural_key_resolvers()
    carried: list[CarriedSecureObject] = []
    for definition in carried_namespace_definitions(profile):
        keys = repository.list_keys(definition.namespace)
        if not keys:
            continue
        resolver = resolvers.get(definition.namespace)
        if resolver is None and definition.default_object_key is not None:
            # Single-document / catalogue stores have a fixed natural key.
            resolver = _fixed_resolver(definition.default_object_key)
        if resolver is None:
            raise ProfileExportError(
                "carried secure-object namespace has no natural-key resolver",
                context={"namespace": definition.namespace, "custody_profile": profile.value},
            )
        for record in repository.list_records(
            definition.namespace,
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        ):
            try:
                object_key = resolver(record, bucket_id)
            except Exception as exc:
                # A resolver fault (e.g. an unexpected payload shape) must surface as
                # a typed, attributable export error naming the namespace, not a bare
                # pydantic/parse error bubbling out of the sealed-archive export.
                raise ProfileExportError(
                    "could not resolve the natural key for a carried secure-object row",
                    context={"namespace": definition.namespace, "error": str(exc)},
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


def restore_carried_objects(
    carried_objects: Iterable[CarriedSecureObject],
    *,
    target_bucket_id: str,
) -> None:
    """Re-save every carried secure-object row into ``target_bucket_id``.

    Each row is written through the raw secure-object substrate under its
    natural key, so the recipient bucket re-digests the key under its own DEK
    and re-encrypts the payload. The caller holds the target bucket session.
    """
    repository = secure_object_repository_for_bucket(target_bucket_id)
    for carried in carried_objects:
        repository.save(
            namespace=carried.namespace,
            object_key=carried.object_key,
            classification=carried.classification,
            schema_version=carried.schema_version,
            written_at=carried.written_at,
            payload=carried.payload,
        )


__all__ = [
    "TYPED_CATEGORY_NAMESPACES",
    "carried_namespace_definitions",
    "restore_carried_objects",
    "serialize_carried_objects",
]
