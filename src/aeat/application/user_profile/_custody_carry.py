"""Generic per-bucket secure-object custody carry for portable bundles.

The portable bundle's five typed categories (profile, work units, ledger,
calculation revisions, filing records) are carried by dedicated typed fields.
Every *other* durable per-bucket secure-object store is carried generically by
this module so an export/import round-trip restores the whole bucket: evidence
bytes, the cross-period calculation inputs, the live captures, and the audit
trail.

Mechanism. Each carried row is read from the encrypted substrate with its
decrypted ``Envelope`` payload bytes intact and re-keyed by its **natural**
object key (never the stored HMAC digest, which is derived from the per-bucket
data-encryption key and is therefore unreadable in a recipient bucket — see the
custody roundtrip tests). On import each row is re-saved through the raw
secure-object substrate under that natural key, which the recipient bucket
re-digests under its own DEK and re-encrypts. This is the substrate-level
counterpart of the typed categories' ``repository.save`` re-encrypt-on-import
path and honours the same ``D2`` decrypted-payload custody contract.

The set of carried namespaces is registry-driven: it is exactly the namespaces
whose :class:`StorageCustodyDisposition` is in the requested custody profile,
minus the five typed-category namespaces this module deliberately leaves to the
typed bundle fields. A populated, carried-disposition namespace with no natural
key resolver fails the export fail-closed, so a newly-registered durable store
cannot be silently dropped.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from ...adapters.persistence.storage._namespace_registry import (
    STORAGE_NAMESPACE_REGISTRY,
    SecureObjectNamespaceDefinition,
    StorageCustodyProfile,
)
from ...core.hashing import sha256_hex

if TYPE_CHECKING:
    from ...adapters.persistence.storage.sql._secure_object_records import SecureObjectRecord
    from ...domain.user_profile._portable_export import CarriedSecureObject

#: Namespaces carried by the typed bundle fields; the generic carry skips them so
#: they are not double-carried.
_TYPED_CATEGORY_NAMESPACES: frozenset[str] = frozenset(
    {
        "aeat.application.user_profile.value",
        "aeat.domain.transactions.bucket",
        "aeat.domain.modelos.work_units",
        "aeat.domain.modelos.calculation_revisions",
        "aeat.domain.modelos.filing_records",
    },
)


# A natural-key resolver maps one decrypted substrate record (in the active
# bucket session) to its natural object key.
NaturalKeyResolver = Callable[["SecureObjectRecord", str], str]


def _canonical_b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _envelope_payload(record: SecureObjectRecord, payload_type: type) -> object:
    from ...adapters.persistence.storage.envelope._envelope import Envelope

    envelope_cls = Envelope.for_payload_type(payload_type)
    return envelope_cls.model_validate_json(record.payload.decode("utf-8")).payload


def _bound_resolver(repo_factory: Callable[[], object]) -> NaturalKeyResolver:
    """Resolver for a ``SecureBoundRepository`` store: parse, then extract_identifier."""

    def _resolve(record: SecureObjectRecord, _bucket_id: str) -> str:
        repo = repo_factory()
        payload = _envelope_payload(record, repo.payload_model())  # type: ignore[attr-defined]
        return repo.extract_identifier(payload)  # type: ignore[attr-defined]

    return _resolve


def _snapshot_resolver(
    payload_type_factory: Callable[[], type],
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
    from ...adapters.persistence.storage.attachment import _unwrap_blob_payload

    return sha256_hex(_unwrap_blob_payload(record.payload))


# ---------------------------------------------------------------------------
# Per-namespace natural-key resolver registry
# ---------------------------------------------------------------------------


def _natural_key_resolvers() -> dict[str, NaturalKeyResolver]:
    """Return the natural-key resolver for every generically-carried namespace.

    Lazily imports each owning repository so the user-profile package import
    stays light. Keyed by the persisted namespace string.
    """
    from ...adapters.persistence.storage._namespace_registry import SECURE_OBJECT_CATALOGUE_KEY

    resolvers: dict[str, NaturalKeyResolver] = {}

    # --- Attachments (evidence bytes + manifests) ----------------------------
    resolvers["aeat.domain.attachments.blobs"] = _blob_resolver

    def _attachment_manifest(record: SecureObjectRecord, _bucket_id: str) -> str:
        from ...domain.attachments import Attachment

        return _envelope_payload(record, Attachment).attachment_id  # type: ignore[attr-defined]

    resolvers["aeat.domain.attachments.manifests"] = _attachment_manifest

    # --- Cross-period calculation inputs (SecureBoundRepository) --------------
    def _observations_repo() -> object:
        from ..calculations import CalculationObservationRepository

        return CalculationObservationRepository()

    resolvers["aeat.calculations.observations"] = _bound_resolver(_observations_repo)

    def _iva_history_repo() -> object:
        from ..calculations import IvaCompensationHistoryRepository

        return IvaCompensationHistoryRepository()

    resolvers["aeat.calculations.iva_compensation.history"] = _bound_resolver(_iva_history_repo)

    def _iva_wallet_repo() -> object:
        from ..calculations import IvaWalletDecisionRepository

        return IvaWalletDecisionRepository()

    resolvers["aeat.calculations.iva_wallet.reconciliation_decisions"] = _bound_resolver(_iva_wallet_repo)

    def _iva_wallet_event_key(record: SecureObjectRecord, _bucket_id: str) -> str:
        from ..calculations import iva_wallet_decision_event_key
        from ..calculations._observations_repository import _IvaWalletDecisionEnvelopePayload

        payload = _envelope_payload(record, _IvaWalletDecisionEnvelopePayload)
        return iva_wallet_decision_event_key(payload.decision)  # type: ignore[attr-defined]

    resolvers["aeat.calculations.iva_wallet.reconciliation_decision_events"] = _iva_wallet_event_key

    # --- Audit trail ---------------------------------------------------------
    resolvers["aeat.domain.buckets.event_history"] = _fixed_resolver(SECURE_OBJECT_CATALOGUE_KEY)

    # --- Live captures (SecureSnapshotRepository) ----------------------------
    def _censo_payload() -> type:
        from ..live._censo import CensoSnapshot

        return CensoSnapshot

    def _censo_key(bucket_id: str, snapshot_id: str) -> str:
        from ..live._censo import censo_snapshot_object_key

        return censo_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["aeat.application.live.censo_snapshot"] = _snapshot_resolver(_censo_payload, _censo_key)

    def _justificante_payload() -> type:
        from ..live import JustificanteCaptureSnapshot

        return JustificanteCaptureSnapshot

    def _justificante_key(bucket_id: str, snapshot_id: str) -> str:
        from ..live._justificante import justificante_capture_snapshot_object_key

        return justificante_capture_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["aeat.application.live.justificante_capture_snapshot"] = _snapshot_resolver(
        _justificante_payload,
        _justificante_key,
    )

    def _notifications_payload() -> type:
        from ..live._notifications import PersistedNotificationsSnapshot

        return PersistedNotificationsSnapshot

    def _notifications_key(bucket_id: str, snapshot_id: str) -> str:
        from ..live._notifications import notifications_snapshot_object_key

        return notifications_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["aeat.application.live.notifications_snapshot"] = _snapshot_resolver(
        _notifications_payload,
        _notifications_key,
    )

    def _expedientes_payload() -> type:
        from ..live._expedientes import PersistedExpedientesSnapshot

        return PersistedExpedientesSnapshot

    def _expedientes_key(bucket_id: str, snapshot_id: str) -> str:
        from ..live._expedientes import expedientes_snapshot_object_key

        return expedientes_snapshot_object_key(bucket_id, snapshot_id)

    resolvers["aeat.application.live.expedientes_snapshot"] = _snapshot_resolver(
        _expedientes_payload,
        _expedientes_key,
    )

    # --- Justificante metadata (SecureBoundRepository) -----------------------
    def _justificante_metadata_repo() -> object:
        from ...domain.justificante import JustificanteRepository

        return JustificanteRepository()

    resolvers["aeat.domain.justificante.metadata"] = _bound_resolver(_justificante_metadata_repo)

    return resolvers


# ---------------------------------------------------------------------------
# Serialise / restore
# ---------------------------------------------------------------------------


def carried_namespace_definitions(
    profile: StorageCustodyProfile,
) -> tuple[SecureObjectNamespaceDefinition, ...]:
    """Return the carried namespace definitions for ``profile`` (typed categories excluded)."""
    return tuple(
        definition
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces_for_custody_profile(profile)
        if definition.namespace not in _TYPED_CATEGORY_NAMESPACES
    )


def serialize_carried_objects(
    *,
    bucket_id: str,
    profile: StorageCustodyProfile,
) -> tuple[CarriedSecureObject, ...]:
    """Serialise every generically-carried secure-object row for ``profile``.

    Reads each carried namespace from the active bucket's encrypted substrate,
    resolving each row's natural key. A populated carried namespace with no
    resolver raises, fail-closed, so the carry can never silently drop a store.
    """
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ...domain.user_profile._portable_export import CarriedSecureObject

    repository = secure_object_repository_for_bucket(bucket_id)
    resolvers = _natural_key_resolvers()
    carried: list[CarriedSecureObject] = []
    for definition in carried_namespace_definitions(profile):
        keys = repository.list_keys(definition.namespace)
        if not keys:
            continue
        resolver = resolvers.get(definition.namespace)
        if resolver is None:
            from ...domain.user_profile._errors import ProfileExportError

            raise ProfileExportError(
                "carried secure-object namespace has no natural-key resolver",
                context={"namespace": definition.namespace, "custody_profile": profile.value},
            )
        for record in repository.list_records(
            definition.namespace,
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        ):
            carried.append(
                CarriedSecureObject(
                    namespace=record.namespace,
                    object_key=resolver(record, bucket_id),
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
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

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
    "carried_namespace_definitions",
    "restore_carried_objects",
    "serialize_carried_objects",
]
