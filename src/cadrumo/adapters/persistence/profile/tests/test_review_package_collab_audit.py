"""Collaboration bucket-event audit-tag emission: real encrypted-catalogue proofs.

Exercises :mod:`~application.modelo.review_package_collab_audit` against
a REAL encrypted :class:`~adapters.persistence.storage.SecureObjectRepository`-backed
:class:`~adapters.persistence.profile.buckets.BucketEventHistoryRepository`
(:func:`~cadrumo.adapters.persistence.storage.tests.secure_sql.isolated_runtime_profile` -- a genuine
``BUCKET_DEK_V1`` bucket, no mocks): every collaboration boundary (recipient
registered/removed, package encrypted/decrypted, and package counter-signed)
appends a typed
:class:`~domain.buckets.BucketEvent` that survives the encrypted
save/load roundtrip with the exact event type, object type, and payload this
module promises.

See Also:
    :func:`~application.modelo.emit_collab_recipient_registered_event`
        Audit event emitted when a trusted recipient is registered.
    :func:`~application.modelo.emit_collab_package_encrypted_event`
        Trust-boundary event emitted when a package is sealed for a recipient.
    :func:`~application.modelo.emit_collab_package_decrypted_event`
        Privacy event emitted after decrypted package bytes are read.
    :func:`~application.modelo.emit_collab_package_counter_signed_event`
        Collaboration event emitted when the recipient counter-signs.
    :class:`~domain.buckets.BucketEventType`
        Closed event enum whose collaboration and privacy members are asserted.
    :class:`~domain.buckets.BucketEventObjectType`
        Object-type enum asserted on the emitted audit entries.
    :func:`~application.modelo.encrypt_review_package_for_recipient`
        X25519 transport primitive whose encryption event is audited.
    :func:`~application.modelo.counter_sign_review_package`
        Counter-signature primitive whose event is audited.
    :class:`~domain.calculations.registry.CasillaObservation`
        Provenance row embedded in the signed review package fixture.
    :class:`Period`
        Typed filing period used to derive the work-unit identifiers.
"""

from __future__ import annotations

import functools
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.review_package_recipient_encryption import RecipientEncryptionAdapter
from cadrumo.adapters.persistence.profile.review_package_recipient_registry import RecipientFingerprintRegistryAdapter
from cadrumo.adapters.persistence.profile.review_package_signing import ReviewPackageSigningKeypairAdapter
from cadrumo.adapters.persistence.profile.tests._review_package_bytes_support import build_package_bytes
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.review_package_collab_audit import (
    emit_collab_package_counter_signed_event,
    emit_collab_package_decrypted_event,
    emit_collab_package_encrypted_event,
    emit_collab_recipient_registered_event,
    emit_collab_recipient_removed_event,
)
from cadrumo.application.modelo.review_package_counter_sign import counter_sign_review_package
from cadrumo.application.modelo.review_package_recipient_encryption import (
    decrypt_review_package_for_recipient,
    encrypt_review_package_for_recipient,
)
from cadrumo.application.modelo.review_package_recipient_registry import (
    add_recipient_fingerprint,
    get_recipient_fingerprint,
    public_key_hex_from_raw_bytes,
    remove_recipient_fingerprint,
)
from cadrumo.application.modelo.review_package_recipient_registry_ports import RecipientFingerprintRegistryPorts
from cadrumo.application.modelo.review_package_signing import sign_review_package
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
_BASE_CASILLA = validated_casilla_id("base", surface="test_review_package_collab_audit")
_CUOTA_CASILLA = validated_casilla_id("cuota", surface="test_review_package_collab_audit")
_DRAFT_BYTES = b"FICHERO-BOE-BYTES-FOR-COLLAB-AUDIT-TEST"
_CRYPTO_CAPABILITY = RecipientEncryptionAdapter()


def _work_unit(*, bucket_id: str) -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
        name="303-2026-1T",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )


def _revision(work_unit: WorkUnit) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        binding_overrides={},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        source_transaction_ids=(),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        observations=(
            CasillaObservation(
                casilla_id=_CUOTA_CASILLA,
                value=Decimal("21.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("test-review-package-collab-audit",),
            ),
        ),
        ledger_filing_evidence=None,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filed_at=None,
        filed_by=None,
        superseded_at=None,
        filing_instance_evidence=None,
        source_provenance=(),
    )


_build_package_bytes = functools.partial(
    build_package_bytes,
    work_unit_factory=_work_unit,
    revision_factory=_revision,
    draft_bytes=_DRAFT_BYTES,
)


def test_recipient_registered_and_removed_events_roundtrip(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="58dd42a2-eae2-4f4c-834c-880296513648") as profile:
        ports = RecipientFingerprintRegistryPorts(
            registry_repository=RecipientFingerprintRegistryAdapter(repository=profile.repository),
        )
        event_repository = BucketEventHistoryRepository(objects=profile.repository)

        public_key_hex = public_key_hex_from_raw_bytes(X25519PrivateKey.generate().public_key().public_bytes_raw())
        add_recipient_fingerprint(
            recipient_id="my-accountant",
            public_key_hex=public_key_hex,
            label="My Accountant",
            ports=ports,
        )
        record = get_recipient_fingerprint("my-accountant", ports=ports)

        registered_event = emit_collab_recipient_registered_event(
            record,
            bucket_id="58dd42a2-eae2-4f4c-834c-880296513648",
            repository=event_repository,
            occurred_at=_NOW,
        )
        assert registered_event.event_type is BucketEventType.COLLAB_RECIPIENT_REGISTERED
        assert registered_event.object_type is BucketEventObjectType.RECIPIENT
        assert registered_event.object_id == "my-accountant"
        assert registered_event.payload["fingerprint_sha256"] == record.fingerprint_sha256

        remove_recipient_fingerprint("my-accountant", ports=ports)
        removed_event = emit_collab_recipient_removed_event(
            recipient_id="my-accountant",
            bucket_id="58dd42a2-eae2-4f4c-834c-880296513648",
            repository=event_repository,
            occurred_at=_NOW,
        )
        assert removed_event.event_type is BucketEventType.COLLAB_RECIPIENT_REMOVED

        # Real encrypted roundtrip: reload the catalogue from a fresh repository
        # handle and confirm both events survived the save/load cycle intact.
        reloaded = BucketEventHistoryRepository(objects=profile.repository).load()
        stored_types = {event.event_type for event in reloaded.events.values()}
        assert BucketEventType.COLLAB_RECIPIENT_REGISTERED in stored_types
        assert BucketEventType.COLLAB_RECIPIENT_REMOVED in stored_types


def test_package_encrypted_and_decrypted_events_roundtrip(tmp_path: Path) -> None:
    package_bytes = _build_package_bytes(tmp_path, bucket_id="3d18d934-b77f-41af-b276-72240e1f39d2")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="3d18d934-b77f-41af-b276-72240e1f39d2") as profile:
        event_repository = BucketEventHistoryRepository(objects=profile.repository)

        recipient_private_key = X25519PrivateKey.generate()
        recipient_public_key_hex = public_key_hex_from_raw_bytes(
            recipient_private_key.public_key().public_bytes_raw(),
        )
        envelope = encrypt_review_package_for_recipient(
            package_bytes,
            recipient_public_key_hex=recipient_public_key_hex,
            recipient_encryption=_CRYPTO_CAPABILITY,
        )
        encrypted_event = emit_collab_package_encrypted_event(
            envelope,
            bucket_id="3d18d934-b77f-41af-b276-72240e1f39d2",
            repository=event_repository,
            occurred_at=_NOW,
        )
        assert encrypted_event.event_type is BucketEventType.COLLAB_PACKAGE_ENCRYPTED_FOR_RECIPIENT
        assert encrypted_event.payload["envelope_nonce_hex"] == envelope.envelope_nonce_hex
        assert encrypted_event.payload["review_only"] == "false"

        decrypted = decrypt_review_package_for_recipient(
            envelope,
            recipient_private_key_hex=recipient_private_key.private_bytes_raw().hex(),
            recipient_encryption=_CRYPTO_CAPABILITY,
        )
        assert decrypted.package_bytes == package_bytes

        decrypted_event = emit_collab_package_decrypted_event(
            envelope,
            bucket_id="3d18d934-b77f-41af-b276-72240e1f39d2",
            repository=event_repository,
            occurred_at=_NOW,
        )
        assert decrypted_event.event_type is BucketEventType.COLLAB_PACKAGE_DECRYPTED

        reloaded = BucketEventHistoryRepository(objects=profile.repository).load()
        stored_types = {event.event_type for event in reloaded.events.values()}
        assert BucketEventType.COLLAB_PACKAGE_ENCRYPTED_FOR_RECIPIENT in stored_types
        assert BucketEventType.COLLAB_PACKAGE_DECRYPTED in stored_types


def test_package_counter_signed_event_roundtrip(tmp_path: Path) -> None:
    package_bytes = _build_package_bytes(tmp_path, bucket_id="7e0ff69f-8968-409e-89cc-ace755670367")
    package_path = tmp_path / "review-package.zip"
    package_path.write_bytes(package_bytes)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="7e0ff69f-8968-409e-89cc-ace755670367") as profile:
        event_repository = BucketEventHistoryRepository(objects=profile.repository)

        operator_keypair = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id="collab-audit-countersign-operator",
        ).ensure_keypair(bucket_id="collab-audit-countersign-operator")
        signed = sign_review_package(package_path, keypair=operator_keypair)

        counter_signer_keypair = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id="collab-audit-countersign-accountant",
        ).ensure_keypair(bucket_id="collab-audit-countersign-accountant")
        receipt = counter_sign_review_package(
            signed,
            counter_signer_keypair=counter_signer_keypair,
            note="reviewed, no changes",
            counter_signed_at=_NOW,
        )

        counter_signed_event = emit_collab_package_counter_signed_event(
            receipt,
            bucket_id="7e0ff69f-8968-409e-89cc-ace755670367",
            repository=event_repository,
            occurred_at=_NOW,
        )
        assert counter_signed_event.event_type is BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED
        assert counter_signed_event.payload["counter_public_key_hex"] == receipt.counter_public_key_hex
        assert counter_signed_event.payload["has_note"] == "true"

        reloaded = BucketEventHistoryRepository(objects=profile.repository).load()
        stored_types = {event.event_type for event in reloaded.events.values()}
        assert BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED in stored_types


__all__: list[str] = []
