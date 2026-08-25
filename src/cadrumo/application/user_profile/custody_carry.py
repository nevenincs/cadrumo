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
    SecureObjectWrite,
    StorageCustodyProfile,
    secure_object_repository_for_bucket,
    unwrap_blob_payload,
)
from ...adapters.persistence.storage.envelope import Envelope
from ...core.external_constants import UTF_8_ENCODING as _UTF_8
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...domain.evidence_consent import (
    EvidenceConsentLedgerEntry,
    evidence_consent_ledger_entry_object_key,
)
from ...domain.user_profile.errors import ProfileExportError
from ...domain.user_profile.portable_export import CarriedSecureObject
from ...domain.user_profile.values import UserProfileSnapshot
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
from ..ledger.confirmation_record import ConfirmationRecordRepository
from ..ledger.counterparty_establishment import ConfirmedCounterpartyFactsRepository
from ..ledger.evidence import PurchaseInvoiceEvidenceRepository
from ..ledger.extracted_document_cache import ExtractedDocumentCacheRepository
from ..ledger.extraction_draft_store import ExtractionDraftRepository
from ..ledger.rule_repository import LedgerClassificationRuleRepository
from ..live.borrador_100 import Borrador100Snapshot, borrador_100_snapshot_object_key
from ..live.deudas import PersistedDeudasSnapshot, deudas_snapshot_object_key
from ..live.expedientes import PersistedExpedientesSnapshot, expedientes_snapshot_object_key
from ..live.iva_remote_state import IvaRemoteStateAcquisitionManifestRepository
from ..live.justificante import JustificanteCaptureSnapshot, justificante_capture_snapshot_object_key
from ..live.notifications import PersistedNotificationsSnapshot, notifications_snapshot_object_key
from ..live.verify import VerifyObservation, verify_observation_object_key
from ..modelo import (
    M036DeclarationResult,
    M145CommunicationRecord,
    ModeloReconciliationRecordRepository,
    m036_declaration_object_key,
    m145_communication_record_object_key,
)
from .repository import user_profile_snapshot_object_key

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
    envelope_cls = Envelope[T].for_payload_type(payload_type)
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
    return sha256_hex(unwrap_blob_payload(record.payload))


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

    # --- Modelo reconciliation records (SecureBoundRepository) ----------------
    # The key is composite (work unit plus the co-written bucket event id), but
    # the resolver never parses a key: it re-derives one from the decrypted
    # payload, and both components are stored fields. So the generic bound
    # resolver recovers it exactly.
    def _reconciliation_records_repo() -> ModeloReconciliationRecordRepository:
        return ModeloReconciliationRecordRepository()

    resolvers["cadrumo.modelo.reconciliation.records"] = _bound_resolver(_reconciliation_records_repo)

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

    resolvers.update(_ledger_extraction_and_live_deudas_natural_key_resolvers())

    return resolvers


def _ledger_extraction_and_live_deudas_natural_key_resolvers() -> dict[str, NaturalKeyResolver]:
    """Return the natural-key resolvers for the ledger extraction pipeline, live deudas, and the consent ledger.

    Split out of :func:`_natural_key_resolvers` to keep that function inside
    its declared size budget; these three namespaces share no dependency on
    each other or on the resolvers registered above them.
    """
    resolvers: dict[str, NaturalKeyResolver] = {}

    # --- Ledger extraction pipeline (SecureBoundRepository) --------------------
    def _extracted_document_cache_repo() -> ExtractedDocumentCacheRepository:
        return ExtractedDocumentCacheRepository()

    resolvers["cadrumo.application.ledger.extracted_document_cache"] = _bound_resolver(
        _extracted_document_cache_repo,
    )

    def _extraction_draft_repo() -> ExtractionDraftRepository:
        return ExtractionDraftRepository()

    resolvers["cadrumo.application.ledger.extraction_draft"] = _bound_resolver(_extraction_draft_repo)

    def _confirmation_record_repo() -> ConfirmationRecordRepository:
        return ConfirmationRecordRepository()

    resolvers["cadrumo.application.ledger.confirmation_record"] = _bound_resolver(_confirmation_record_repo)

    def _confirmed_counterparty_facts_repo() -> ConfirmedCounterpartyFactsRepository:
        return ConfirmedCounterpartyFactsRepository()

    resolvers["cadrumo.application.ledger.confirmed_counterparty_facts"] = _bound_resolver(
        _confirmed_counterparty_facts_repo,
    )

    # --- Live deudas snapshot (SecureSnapshotRepository) -----------------------
    def _deudas_payload() -> type[PersistedDeudasSnapshot]:
        return PersistedDeudasSnapshot

    def _deudas_key(bucket_id: str, snapshot_id: str) -> str:
        return deudas_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["cadrumo.application.live.deudas_snapshot"] = _snapshot_resolver(_deudas_payload, _deudas_key)

    # --- Off-host evidence-consent audit ledger --------------------------------
    def _evidence_consent_ledger_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        entry_payload = json.loads(record.payload.decode(_UTF_8))["entry"]
        entry = EvidenceConsentLedgerEntry.model_validate_json(json.dumps(entry_payload))
        return evidence_consent_ledger_entry_object_key(entry)

    resolvers["cadrumo.outbound.llm.evidence_consent_ledger"] = _evidence_consent_ledger_key

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
                # A resolver fault (e.g. an unexpected payload shape) must surface as
                # a typed, attributable export error naming the namespace, not a bare
                # pydantic/parse error bubbling out of the sealed-archive export.
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


def restore_carried_objects(
    carried_objects: Iterable[CarriedSecureObject],
    *,
    target_bucket_id: str,
) -> None:
    """Re-save every carried secure-object row into ``target_bucket_id``.

    Each row is written through the raw secure-object substrate under its
    natural key, so the recipient bucket re-digests the key under its own DEK
    and re-encrypts the payload. The caller holds the target bucket session.

    The whole set commits as ONE unit of work. Saving row by row made a
    failure partway through leave every earlier row durable while the call
    raised, which is the worst of both outcomes for a custody boundary: the
    caller is told the restore did not happen, and the target nonetheless
    holds part of another bucket's key material. A retry then had to reason
    about which rows already existed rather than about whether the restore
    ran, and nothing recorded where it stopped.

    Batching is not merely an optimisation here -- it is what makes the
    failure legible. Either the target has all the carried custody rows or
    it has none of them, so "did this restore happen" is answerable from the
    target alone.
    """
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
    if not writes:
        return
    secure_object_repository_for_bucket(target_bucket_id).save_many(writes)


def _rebound_payload(carried: CarriedSecureObject, *, target_bucket_id: str) -> bytes:
    """Rebind a carried attachment manifest's ``bucket_id`` to its new home.

    Every other carried namespace is transported as opaque bytes, but the
    attachment manifest's ``bucket_id`` is a self-describing ownership claim
    (:func:`~adapters.persistence.storage.attachment.AttachmentStore.load_manifest`
    refuses a manifest whose ``bucket_id`` disagrees with the active bucket).
    A custody carry is a deliberate, authorised move to a new bucket, so the
    restored manifest must claim ``target_bucket_id`` -- the one case where
    rewriting a carried payload's content is correct, rather than leaving a
    manifest that faithfully, and now wrongly, still claims the source bucket.
    """
    if carried.namespace != ATTACHMENT_MANIFEST_NAMESPACE.namespace:
        return carried.payload
    envelope = json.loads(carried.payload.decode(_UTF_8))
    envelope["payload"]["bucket_id"] = target_bucket_id
    return canonical_json_bytes(envelope)


__all__ = [
    "TYPED_CATEGORY_NAMESPACES",
    "carried_namespace_definitions",
    "restore_carried_objects",
    "serialize_carried_objects",
]
