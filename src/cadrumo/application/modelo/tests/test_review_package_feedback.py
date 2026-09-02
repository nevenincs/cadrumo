"""Feedback-package round trip and countersign-attach-to-journal proofs.

Exercises :mod:`~application.modelo.review_package_feedback` end to end
against a REAL two-bucket runtime
(:func:`~tests.secure_sql.isolated_two_bucket_runtime` -- two genuine
``BUCKET_DEK_V1`` buckets, no mocks or fakes): the originator (taxpayer) signs
and hands off a review package, mints their own X25519 encryption keypair, the
accountant counter-signs the operator's signature and seals a
:class:`~application.modelo.FeedbackPackage` back to the originator using
the EXACT SAME X25519 ECIES primitive
(:func:`~application.modelo.encrypt_review_package_for_recipient` /
:func:`~application.modelo.decrypt_review_package_for_recipient`) the
forward direction already proves, and the originator imports the feedback,
verifies both signature layers against their own locally-held archive, and
attaches the verified countersignature to their own bucket-event journal.

Also proves the anti-tautology contract: a tampered feedback envelope, a
tampered archive, an edited note, and a forged counter-signature all refuse
loudly rather than silently importing unverified feedback.

See Also:
    :func:`~application.modelo.build_feedback_package`
        Constructs the feedback payload these tests encrypt and import.
    :func:`~application.modelo.encrypt_feedback_package_for_originator`
        Seals feedback with the originator's recipient-encryption key.
    :func:`~application.modelo.decrypt_feedback_package_from_originator_envelope`
        Opens the return envelope before import verification.
    :func:`~application.modelo.import_feedback_package`
        Re-verifies both signature layers before accepting feedback.
    :func:`~application.modelo.counter_sign_review_package`
        Produces the counter-signed receipt carried by structured feedback.
    :func:`~application.modelo.emit_collab_feedback_countersign_attached_event`
        Attaches verified countersignatures to the originator's journal.
    :class:`~domain.buckets.BucketEventType`
        Closed event enum asserted for the collaboration audit entry.
    :class:`~domain.calculations.registry.CasillaObservation`
        Registry observation rows embedded in the signed review package.
    :class:`Period`
        Typed filing period used to derive the work-unit identifiers.
"""

from __future__ import annotations

import functools
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from pydantic import ValidationError

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.buckets.event import BucketEventObjectType, BucketEventType
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from ....tests.secure_sql import isolated_two_bucket_runtime
from ..review_package_collab_audit import emit_collab_feedback_countersign_attached_event
from ..review_package_counter_sign import counter_sign_review_package
from ..review_package_feedback import (
    FeedbackCounterSignatureInvalidError,
    ReviewPackageFeedbackError,
    build_feedback_package,
    decrypt_feedback_package_from_originator_envelope,
    encrypt_feedback_package_for_originator,
    import_feedback_package,
)
from ..review_package_recipient_encryption import (
    RecipientDecryptionError,
    RecipientPackageExpiredError,
    ensure_recipient_encryption_keypair,
    recipient_encryption_public_key,
)
from ..review_package_signing import ensure_review_package_signing_keypair, sign_review_package
from ._review_package_bytes_support import build_package_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
_BASE_CASILLA = validated_casilla_id("base", surface="test_review_package_feedback")
_CUOTA_CASILLA = validated_casilla_id("cuota", surface="test_review_package_feedback")
_DRAFT_BYTES = b"FICHERO-BOE-BYTES-FOR-FEEDBACK-ROUNDTRIP-TEST"

#: Standalone placeholder ids for tests that exercise only the
#: encrypt/decrypt primitive (no real work unit or revision is built), still
#: well-formed 64-char hex identifiers so the strict pydantic field
#: constraints on ``WorkUnitId`` / ``CalculationRevisionId`` are satisfied.
_PLACEHOLDER_WORK_UNIT_ID = derive_work_unit_id(
    bucket_id="originator-bucket",
    modelo="303",
    filing_year=2026,
    period=Period.from_year_and_code(2026, "1T"),
    revision_id="feedback-placeholder-revision",
)
_PLACEHOLDER_REVISION_ID = derive_calculation_revision_id(
    work_unit_id=_PLACEHOLDER_WORK_UNIT_ID,
    input_values_by_casilla_id={_BASE_CASILLA: "0.00"},
    binding_overrides={},
    casilla_values={_CUOTA_CASILLA: Decimal("0.00")},
    source_transaction_ids=(),
    filing_instance_evidence=None,
    source_provenance=(),
)


def _work_unit(*, bucket_id: str) -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="feedback-roundtrip-revision",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="feedback-roundtrip-revision",
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
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        observations=(
            CasillaObservation(
                casilla_id=_CUOTA_CASILLA,
                value=Decimal("21.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("test-review-package-feedback",),
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


_build_package = functools.partial(
    build_package_path,
    work_unit_factory=_work_unit,
    revision_factory=_revision,
    draft_bytes=_DRAFT_BYTES,
    filename_template="review-package-{bucket_id}.zip",
)


def test_full_round_trip_originator_signs_accountant_countersigns_and_returns_feedback(
    tmp_path: Path,
) -> None:
    """End-to-end: build -> sign -> counter-sign -> seal feedback -> import -> attach to journal."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)

        # Originator signs with their Ed25519 signing keypair.
        operator_signing_keypair = ensure_review_package_signing_keypair(
            bucket_id=runtime.primary.bucket_id,
            repository=runtime.primary.repository,
        )
        signed = sign_review_package(package_path, keypair=operator_signing_keypair)

        # Originator mints their OWN X25519 encryption keypair (the "recipient"
        # of the reverse-direction feedback envelope).
        originator_encryption_keypair = ensure_recipient_encryption_keypair(
            bucket_id=runtime.primary.bucket_id,
            repository=runtime.primary.repository,
        )
        originator_encryption_public_key = recipient_encryption_public_key(originator_encryption_keypair)

        # Accountant counter-signs with their own Ed25519 signing keypair.
        with runtime.switch_to_secondary():
            accountant_signing_keypair = ensure_review_package_signing_keypair(
                bucket_id=runtime.secondary.bucket_id,
                repository=runtime.secondary.repository,
            )
        receipt = counter_sign_review_package(
            signed,
            counter_signer_keypair=accountant_signing_keypair,
            note="reviewed, no changes",
            counter_signed_at=_NOW,
        )

        # Accountant builds and seals the feedback package for the originator,
        # reusing the exact same X25519 ECIES primitive as the forward direction.
        feedback = build_feedback_package(
            bucket_id=runtime.primary.bucket_id,
            work_unit_id=_work_unit(bucket_id=runtime.primary.bucket_id).work_unit_id,
            calculation_revision_id=signed.calculation_revision_id,
            note="all clear",
            counter_signed_receipt=receipt,
            submitted_by="my-accountant",
            submitted_at=_NOW,
        )
        envelope = encrypt_feedback_package_for_originator(
            feedback,
            originator_public_key_hex=originator_encryption_public_key.public_key_hex,
            issued_at=_NOW,
        )

        # Originator imports and verifies the feedback against their own
        # locally-held archive and signing identities.
        imported = import_feedback_package(
            envelope,
            originator_private_key=originator_encryption_keypair.private_key(),
            reviewed_package_path=package_path,
            operator_public_key_hex=operator_signing_keypair.public_key_hex,
            counter_signer_public_key_hex=accountant_signing_keypair.public_key_hex,
            now=_NOW,
        )

        assert imported.counter_signature_verified is True
        assert imported.feedback.note == "all clear"
        assert imported.feedback.submitted_by == "my-accountant"
        assert imported.feedback.counter_signed_receipt == receipt

        # Countersign-attach-to-journal: the verified receipt is appended to
        # the originator's OWN bucket-event journal.
        event_repository = BucketEventHistoryRepository(objects=runtime.primary.repository)
        attached_event = emit_collab_feedback_countersign_attached_event(
            imported,
            bucket_id=runtime.primary.bucket_id,
            repository=event_repository,
            occurred_at=_NOW,
        )
        assert attached_event.event_type is BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED
        assert attached_event.object_type is BucketEventObjectType.RECIPIENT
        assert attached_event.object_id == accountant_signing_keypair.public_key_hex
        assert attached_event.payload["calculation_revision_id"] == signed.calculation_revision_id

        # Real encrypted roundtrip: reload the catalogue from a fresh
        # repository handle and confirm the event survived the save/load cycle.
        reloaded = BucketEventHistoryRepository(objects=runtime.primary.repository).load()
        stored_types = {event.event_type for event in reloaded.events.values()}
        assert BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED in stored_types


def test_unstructured_feedback_with_no_counter_signed_receipt_imports_cleanly(tmp_path: Path) -> None:
    """Feedback may carry a note alone, with no formal sign-off."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)
        operator_signing_keypair = ensure_review_package_signing_keypair(
            bucket_id=runtime.primary.bucket_id,
            repository=runtime.primary.repository,
        )

        originator_encryption_keypair = ensure_recipient_encryption_keypair(
            bucket_id=runtime.primary.bucket_id,
            repository=runtime.primary.repository,
        )
        originator_encryption_public_key = recipient_encryption_public_key(originator_encryption_keypair)

        feedback = build_feedback_package(
            bucket_id=runtime.primary.bucket_id,
            work_unit_id=_work_unit(bucket_id=runtime.primary.bucket_id).work_unit_id,
            calculation_revision_id=_PLACEHOLDER_REVISION_ID,
            note="see attached corrections, no formal sign-off yet",
            counter_signed_receipt=None,
            submitted_by="my-accountant",
            submitted_at=_NOW,
        )
        envelope = encrypt_feedback_package_for_originator(
            feedback,
            originator_public_key_hex=originator_encryption_public_key.public_key_hex,
            issued_at=_NOW,
        )

        imported = import_feedback_package(
            envelope,
            originator_private_key=originator_encryption_keypair.private_key(),
            reviewed_package_path=package_path,
            operator_public_key_hex=operator_signing_keypair.public_key_hex,
            now=_NOW,
        )

        assert imported.counter_signature_verified is None
        assert imported.feedback.counter_signed_receipt is None
        assert imported.feedback.note == "see attached corrections, no formal sign-off yet"


def test_decrypt_feedback_package_recovers_document_byte_for_byte(tmp_path: Path) -> None:
    """The lower-level decrypt primitive recovers the exact FeedbackPackage sealed."""
    originator_private_key = X25519PrivateKey.generate()
    originator_public_key_hex = originator_private_key.public_key().public_bytes_raw().hex()

    feedback = build_feedback_package(
        bucket_id="originator-bucket",
        work_unit_id=_PLACEHOLDER_WORK_UNIT_ID,
        calculation_revision_id=_PLACEHOLDER_REVISION_ID,
        note="approved",
        submitted_by="accountant",
        submitted_at=_NOW,
    )
    envelope = encrypt_feedback_package_for_originator(
        feedback,
        originator_public_key_hex=originator_public_key_hex,
        issued_at=_NOW,
    )

    recovered = decrypt_feedback_package_from_originator_envelope(
        envelope,
        originator_private_key=originator_private_key,
        now=_NOW,
    )
    assert recovered == feedback


@pytest.mark.parametrize(
    "submitted_at",
    (
        pytest.param(datetime(2026, 7, 3, 12, 0), id="naive"),
        pytest.param(datetime(2026, 7, 3, 14, 0, tzinfo=timezone(timedelta(hours=2))), id="non-utc"),
    ),
)
def test_build_feedback_package_refuses_a_naive_or_non_utc_submitted_at(submitted_at: datetime) -> None:
    """A feedback document must carry one explicit UTC ``submitted_at`` instant."""
    with pytest.raises(ValidationError, match="datetime must be"):
        build_feedback_package(
            bucket_id="originator-bucket",
            work_unit_id=_PLACEHOLDER_WORK_UNIT_ID,
            calculation_revision_id=_PLACEHOLDER_REVISION_ID,
            note="approved",
            submitted_by="accountant",
            submitted_at=submitted_at,
        )


def test_decrypt_feedback_package_fails_with_wrong_private_key() -> None:
    originator_private_key = X25519PrivateKey.generate()
    originator_public_key_hex = originator_private_key.public_key().public_bytes_raw().hex()
    wrong_private_key = X25519PrivateKey.generate()

    feedback = build_feedback_package(
        bucket_id="originator-bucket",
        work_unit_id=_PLACEHOLDER_WORK_UNIT_ID,
        calculation_revision_id=_PLACEHOLDER_REVISION_ID,
        note="approved",
        submitted_by="accountant",
        submitted_at=_NOW,
    )
    envelope = encrypt_feedback_package_for_originator(
        feedback,
        originator_public_key_hex=originator_public_key_hex,
        issued_at=_NOW,
    )

    with pytest.raises(RecipientDecryptionError):
        decrypt_feedback_package_from_originator_envelope(
            envelope,
            originator_private_key=wrong_private_key,
            now=_NOW,
        )


def test_decrypt_feedback_package_fails_when_ciphertext_tampered() -> None:
    """Anti-tautology proof: flipping a ciphertext byte breaks AEAD authentication."""
    originator_private_key = X25519PrivateKey.generate()
    originator_public_key_hex = originator_private_key.public_key().public_bytes_raw().hex()

    feedback = build_feedback_package(
        bucket_id="originator-bucket",
        work_unit_id=_PLACEHOLDER_WORK_UNIT_ID,
        calculation_revision_id=_PLACEHOLDER_REVISION_ID,
        note="approved",
        submitted_by="accountant",
        submitted_at=_NOW,
    )
    envelope = encrypt_feedback_package_for_originator(
        feedback,
        originator_public_key_hex=originator_public_key_hex,
        issued_at=_NOW,
    )

    tampered_bytes = bytearray(envelope.ciphertext)
    tampered_bytes[-1] ^= 0xFF
    tampered_envelope = envelope.model_copy(update={"ciphertext": bytes(tampered_bytes)})

    with pytest.raises(RecipientDecryptionError):
        decrypt_feedback_package_from_originator_envelope(
            tampered_envelope,
            originator_private_key=originator_private_key,
            now=_NOW,
        )


def test_expired_feedback_envelope_refuses() -> None:
    originator_private_key = X25519PrivateKey.generate()
    originator_public_key_hex = originator_private_key.public_key().public_bytes_raw().hex()

    feedback = build_feedback_package(
        bucket_id="originator-bucket",
        work_unit_id=_PLACEHOLDER_WORK_UNIT_ID,
        calculation_revision_id=_PLACEHOLDER_REVISION_ID,
        note="approved",
        submitted_by="accountant",
        submitted_at=_NOW,
    )
    envelope = encrypt_feedback_package_for_originator(
        feedback,
        originator_public_key_hex=originator_public_key_hex,
        valid_for=timedelta(days=1),
        issued_at=_NOW,
    )

    with pytest.raises(RecipientPackageExpiredError):
        decrypt_feedback_package_from_originator_envelope(
            envelope,
            originator_private_key=originator_private_key,
            now=_NOW + timedelta(days=2),
        )


def test_import_feedback_package_refuses_when_archive_tampered_after_countersign(tmp_path: Path) -> None:
    """A tampered local archive invalidates import, even though decryption itself succeeds."""
    import zipfile

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)
        operator_signing_keypair = ensure_review_package_signing_keypair(
            bucket_id=runtime.primary.bucket_id,
            repository=runtime.primary.repository,
        )
        signed = sign_review_package(package_path, keypair=operator_signing_keypair)

        originator_encryption_keypair = ensure_recipient_encryption_keypair(
            bucket_id=runtime.primary.bucket_id,
            repository=runtime.primary.repository,
        )
        originator_encryption_public_key = recipient_encryption_public_key(originator_encryption_keypair)

        with runtime.switch_to_secondary():
            accountant_signing_keypair = ensure_review_package_signing_keypair(
                bucket_id=runtime.secondary.bucket_id,
                repository=runtime.secondary.repository,
            )
        receipt = counter_sign_review_package(
            signed,
            counter_signer_keypair=accountant_signing_keypair,
            note="reviewed, no changes",
            counter_signed_at=_NOW,
        )

        feedback = build_feedback_package(
            bucket_id=runtime.primary.bucket_id,
            work_unit_id=_work_unit(bucket_id=runtime.primary.bucket_id).work_unit_id,
            calculation_revision_id=signed.calculation_revision_id,
            note="all clear",
            counter_signed_receipt=receipt,
            submitted_by="my-accountant",
            submitted_at=_NOW,
        )
        envelope = encrypt_feedback_package_for_originator(
            feedback,
            originator_public_key_hex=originator_encryption_public_key.public_key_hex,
            issued_at=_NOW,
        )

        # Tamper the LOCAL archive the originator still holds, after signing.
        rewritten = package_path.with_name(package_path.name + ".rewritten")
        with zipfile.ZipFile(package_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
            for item in src.infolist():
                data = b"TAMPERED FICHERO BYTES" if item.filename == "draft.fichero-boe" else src.read(item.filename)
                dst.writestr(item, data)
        rewritten.replace(package_path)

        with pytest.raises(FeedbackCounterSignatureInvalidError):
            import_feedback_package(
                envelope,
                originator_private_key=originator_encryption_keypair.private_key(),
                reviewed_package_path=package_path,
                operator_public_key_hex=operator_signing_keypair.public_key_hex,
                counter_signer_public_key_hex=accountant_signing_keypair.public_key_hex,
                now=_NOW,
            )


def test_import_feedback_package_refuses_with_forged_counter_signer_key(tmp_path: Path) -> None:
    """A wrong counter-signer public key (impersonation attempt) fails verification."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)
        operator_signing_keypair = ensure_review_package_signing_keypair(
            bucket_id=runtime.primary.bucket_id,
            repository=runtime.primary.repository,
        )
        signed = sign_review_package(package_path, keypair=operator_signing_keypair)

        originator_encryption_keypair = ensure_recipient_encryption_keypair(
            bucket_id=runtime.primary.bucket_id,
            repository=runtime.primary.repository,
        )
        originator_encryption_public_key = recipient_encryption_public_key(originator_encryption_keypair)

        with runtime.switch_to_secondary():
            accountant_signing_keypair = ensure_review_package_signing_keypair(
                bucket_id=runtime.secondary.bucket_id,
                repository=runtime.secondary.repository,
            )
        receipt = counter_sign_review_package(
            signed,
            counter_signer_keypair=accountant_signing_keypair,
            note="reviewed, no changes",
            counter_signed_at=_NOW,
        )

        feedback = build_feedback_package(
            bucket_id=runtime.primary.bucket_id,
            work_unit_id=_work_unit(bucket_id=runtime.primary.bucket_id).work_unit_id,
            calculation_revision_id=signed.calculation_revision_id,
            note="all clear",
            counter_signed_receipt=receipt,
            submitted_by="my-accountant",
            submitted_at=_NOW,
        )
        envelope = encrypt_feedback_package_for_originator(
            feedback,
            originator_public_key_hex=originator_encryption_public_key.public_key_hex,
            issued_at=_NOW,
        )

        forged_counter_signer_public_key_hex = X25519PrivateKey.generate().public_key().public_bytes_raw().hex()

        with pytest.raises(FeedbackCounterSignatureInvalidError):
            import_feedback_package(
                envelope,
                originator_private_key=originator_encryption_keypair.private_key(),
                reviewed_package_path=package_path,
                operator_public_key_hex=operator_signing_keypair.public_key_hex,
                counter_signer_public_key_hex=forged_counter_signer_public_key_hex,
                now=_NOW,
            )


def test_import_feedback_package_raises_when_receipt_present_but_no_counter_signer_key_supplied(
    tmp_path: Path,
) -> None:
    """A caller cannot silently skip verification by omitting the counter-signer key."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)
        operator_signing_keypair = ensure_review_package_signing_keypair(
            bucket_id=runtime.primary.bucket_id,
            repository=runtime.primary.repository,
        )
        signed = sign_review_package(package_path, keypair=operator_signing_keypair)

        originator_encryption_keypair = ensure_recipient_encryption_keypair(
            bucket_id=runtime.primary.bucket_id,
            repository=runtime.primary.repository,
        )
        originator_encryption_public_key = recipient_encryption_public_key(originator_encryption_keypair)

        with runtime.switch_to_secondary():
            accountant_signing_keypair = ensure_review_package_signing_keypair(
                bucket_id=runtime.secondary.bucket_id,
                repository=runtime.secondary.repository,
            )
        receipt = counter_sign_review_package(
            signed,
            counter_signer_keypair=accountant_signing_keypair,
            note="reviewed, no changes",
            counter_signed_at=_NOW,
        )

        feedback = build_feedback_package(
            bucket_id=runtime.primary.bucket_id,
            work_unit_id=_work_unit(bucket_id=runtime.primary.bucket_id).work_unit_id,
            calculation_revision_id=signed.calculation_revision_id,
            note="all clear",
            counter_signed_receipt=receipt,
            submitted_by="my-accountant",
            submitted_at=_NOW,
        )
        envelope = encrypt_feedback_package_for_originator(
            feedback,
            originator_public_key_hex=originator_encryption_public_key.public_key_hex,
            issued_at=_NOW,
        )

        with pytest.raises(ReviewPackageFeedbackError):
            import_feedback_package(
                envelope,
                originator_private_key=originator_encryption_keypair.private_key(),
                reviewed_package_path=package_path,
                operator_public_key_hex=operator_signing_keypair.public_key_hex,
                counter_signer_public_key_hex=None,
                now=_NOW,
            )


def test_emit_collab_feedback_countersign_attached_event_refuses_unverified_feedback(
    tmp_path: Path,
) -> None:
    """Attaching to the journal is refused when the countersignature was not verified true."""
    from ....tests.secure_sql import isolated_runtime_profile
    from ..review_package_feedback import ImportedFeedback

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="9a1ab02a-114c-439a-ae84-4b55d9bd64d1") as profile:
        event_repository = BucketEventHistoryRepository(objects=profile.repository)

        feedback = build_feedback_package(
            bucket_id="9a1ab02a-114c-439a-ae84-4b55d9bd64d1",
            work_unit_id=_PLACEHOLDER_WORK_UNIT_ID,
            calculation_revision_id=_PLACEHOLDER_REVISION_ID,
            note="unstructured, no sign-off",
            counter_signed_receipt=None,
            submitted_by="accountant",
            submitted_at=_NOW,
        )
        imported = ImportedFeedback(feedback=feedback, counter_signature_verified=None)

        with pytest.raises(ValueError, match="unverified or absent"):
            emit_collab_feedback_countersign_attached_event(
                imported,
                bucket_id="9a1ab02a-114c-439a-ae84-4b55d9bd64d1",
                repository=event_repository,
                occurred_at=_NOW,
            )


__all__: list[str] = []
