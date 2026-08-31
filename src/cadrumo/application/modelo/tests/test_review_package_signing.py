"""Ed25519 review-package signing + signature-verify roundtrip and anti-tautology proofs.

Exercises :mod:`~application.modelo._review_package_signing` end to end
against a REAL built-and-checksummed review package
(:func:`~application.modelo.build_review_package`) and a REAL encrypted
:class:`~adapters.persistence.storage.SecureObjectRepository`
(:func:`~tests.secure_sql.isolated_runtime_profile` -- a genuine
``BUCKET_DEK_V1`` bucket, no mocks or fakes): mint a keypair, confirm the
private key is persisted only as ciphertext, sign a package, verify the
signature, then tamper the package/manifest and confirm verification fails.

Mirrors the anti-tautology discipline already established in
``test_review_package.py``: every negative-path test names the exact way the
system deviates from "clean" before asserting the refusal.

See Also:
    :mod:`~application.modelo._review_package_signing`
        Ed25519 authenticity layer exercised by the roundtrip and tamper cases.
    :mod:`~application.modelo.review_package`
        Checksum-manifest package builder whose integrity guarantee is verified
        before signature validation.
    :class:`~adapters.persistence.storage.SecureObjectRepository`
        Encrypted per-bucket storage boundary for the signing private key.
    :mod:`~application.modelo._review_package_counter_sign`
        Accountant receipt layer that signs over this module's original
        signature bytes.
    :mod:`~core.corpus_manifest._bundle_signing`
        Corpus-bundle signing analogue that reuses the same manifest-digest
        signing pattern.
"""

from __future__ import annotations

import contextvars
import functools
import threading
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from ....adapters.persistence.storage._secure_object_namespaces import MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE
from ....adapters.persistence.storage.sql._orm import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....core.casilla_id import validated_casilla_id
from ....core.classification.policies import SensitivityClass
from ....core.period import Period
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from ....tests.secure_sql import isolated_runtime_profile
from .._review_package_signing import (
    ReviewPackageSigningError,
    ReviewPackageSigningKeyNotFoundError,
    ReviewPackageSigningKeypair,
    ReviewPackageSigningPublicKey,
    SignedReviewPackage,
    _signing_key_object_key,
    ensure_review_package_signing_keypair,
    load_review_package_signing_keypair,
    review_package_signing_public_key,
    sign_review_package,
    verify_review_package_signature,
)
from ._review_package_bytes_support import build_package_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Canonical UUIDv4 profile identities. Test buckets publish through
# ``canonical_profile_bucket_id``, which accepts only a version-4 UUID, so
# a readable label cannot address a bucket. The foreign id is a VALID but
# different identity on purpose: the refusal under test is a bucket
# mismatch, and a malformed id would refuse for the wrong reason.
_OWNER_BUCKET_ID = "2e510000-0000-4000-8000-000000000001"
_FOREIGN_BUCKET_ID = "2e510000-0000-4000-8000-000000000002"
_CONCURRENT_BUCKET_ID = "2e510000-0000-4000-8000-000000000003"

_NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
_BASE_CASILLA = validated_casilla_id("base", surface="test_review_package_signing")
_CUOTA_CASILLA = validated_casilla_id("cuota", surface="test_review_package_signing")
_DRAFT_BYTES = b"FICHERO-BOE-BYTES-FOR-REVIEW-PACKAGE-SIGNING-TEST"


def _work_unit(*, bucket_id: str) -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="review-package-signing-revision",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="review-package-signing-revision",
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
                source_refs=("test-review-package-signing",),
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
)


def test_ensure_keypair_mints_then_persists_and_is_idempotent(tmp_path: Path) -> None:
    """A second call against the same bucket returns the SAME keypair (no rotation)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f1671beb-ff26-411d-b81c-76ccfb3af59c") as profile:
        first = ensure_review_package_signing_keypair(bucket_id=profile.bucket_id, repository=profile.repository)
        second = ensure_review_package_signing_keypair(bucket_id=profile.bucket_id, repository=profile.repository)

    assert first.bucket_id == profile.bucket_id
    assert first.private_key_hex == second.private_key_hex
    assert first.public_key_hex == second.public_key_hex
    assert first.created_at == second.created_at
    # Real behavior: the reconstructed live key objects actually sign/verify a
    # message consistently with each other -- not just equal hex strings.
    message = b"anti-tautology-probe"
    signature = first.private_key().sign(message)
    second.public_key().verify(signature, message)


def test_private_key_is_never_stored_as_plaintext(tmp_path: Path) -> None:
    """The persisted row is real ciphertext: the raw private-key bytes never appear on disk."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="225abfcd-a133-4652-8f32-18f7494de580") as profile:
        keypair = ensure_review_package_signing_keypair(bucket_id=profile.bucket_id, repository=profile.repository)

        raw_record = profile.repository.load(
            MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            f"review-package-signing-key:{profile.bucket_id}",
            expected_class=SensitivityClass.SECRET,
            max_supported_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
        )
        assert raw_record is not None
        # The decrypted payload (proving the round trip works) DOES contain the
        # private key hex -- that is expected, this is the decrypted read path.
        assert keypair.private_key_hex.encode("utf-8") in raw_record.payload

        # The point of the guarantee is the AT-REST bytes: read the raw SQL row
        # ciphertext directly (bypassing the repository's decrypt step) and
        # confirm the plaintext private-key hex does NOT appear in it.
        from sqlalchemy import select

        with session_scope(profile.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(
                    SecureObjectRow.namespace == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
                ),
            ).scalar_one()
            ciphertext_bytes = bytes(row.payload)

        assert keypair.private_key_hex.encode("utf-8") not in ciphertext_bytes
        assert bytes.fromhex(keypair.private_key_hex) not in ciphertext_bytes


def test_load_without_ensure_raises_key_not_found(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="a441deaf-8144-4c36-8d07-2de6681ac224") as profile,
        pytest.raises(ReviewPackageSigningKeyNotFoundError),
    ):
        load_review_package_signing_keypair(bucket_id=profile.bucket_id, repository=profile.repository)


def test_sign_then_verify_with_correct_public_key_passes(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f457d34b-e650-41f6-b5ec-446e06eb34c7") as profile:
        package_path = _build_package(tmp_path, bucket_id=profile.bucket_id)
        keypair = ensure_review_package_signing_keypair(bucket_id=profile.bucket_id, repository=profile.repository)

        signed = sign_review_package(package_path, keypair=keypair, signed_at=_NOW)
        public_key = review_package_signing_public_key(keypair)
        round_tripped = SignedReviewPackage.model_validate_json(signed.model_dump_json())

        assert round_tripped == signed
        assert round_tripped.signed_at == _NOW
        assert round_tripped.bucket_id == profile.bucket_id
        assert round_tripped.public_key_hex == public_key.public_key_hex
        assert len(bytes.fromhex(round_tripped.signature_hex)) == 64

        assert (
            verify_review_package_signature(package_path, round_tripped, public_key_hex=public_key.public_key_hex)
            is True
        )


@pytest.mark.parametrize(
    "signed_at",
    (
        pytest.param(datetime(2026, 7, 3, 12, 0), id="naive"),
        pytest.param(datetime(2026, 7, 3, 14, 0, tzinfo=timezone(timedelta(hours=2))), id="non-utc"),
    ),
)
def test_sign_refuses_a_naive_or_non_utc_envelope_timestamp(tmp_path: Path, signed_at: datetime) -> None:
    """A signature envelope must carry one explicit UTC instant."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="8b08f119-2674-41be-819f-5a2908bc97d4") as profile:
        package_path = _build_package(tmp_path, bucket_id=profile.bucket_id)
        keypair = ensure_review_package_signing_keypair(bucket_id=profile.bucket_id, repository=profile.repository)

        with pytest.raises(ValidationError, match="datetime must be"):
            sign_review_package(package_path, keypair=keypair, signed_at=signed_at)


def test_verify_fails_when_package_tampered_after_signing(tmp_path: Path) -> None:
    """Tampering the archive after signing must fail verification (integrity-then-signature)."""
    import zipfile

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="b161bbf5-9bfd-4bcd-b60f-34262a65619b") as profile:
        package_path = _build_package(tmp_path, bucket_id=profile.bucket_id)
        keypair = ensure_review_package_signing_keypair(bucket_id=profile.bucket_id, repository=profile.repository)
        signed = sign_review_package(package_path, keypair=keypair)

        # Tamper one archived member's bytes after the signature was minted.
        rewritten = package_path.with_name(package_path.name + ".rewritten")
        with zipfile.ZipFile(package_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
            for item in src.infolist():
                data = b"TAMPERED FICHERO BYTES" if item.filename == "draft.fichero-boe" else src.read(item.filename)
                dst.writestr(item, data)
        rewritten.replace(package_path)

        assert (
            verify_review_package_signature(
                package_path,
                signed,
                public_key_hex=keypair.public_key_hex,
            )
            is False
        )


def test_verify_fails_with_wrong_public_key(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="6b74a0b8-1ccf-4d16-9b5a-61b769ad9121") as profile:
        package_path = _build_package(tmp_path, bucket_id=profile.bucket_id)
        keypair = ensure_review_package_signing_keypair(bucket_id=profile.bucket_id, repository=profile.repository)
        signed = sign_review_package(package_path, keypair=keypair)

        wrong_public_key = Ed25519PrivateKey.generate().public_key()
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        wrong_public_key_hex = wrong_public_key.public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        ).hex()

        assert verify_review_package_signature(package_path, signed, public_key_hex=wrong_public_key_hex) is False


def test_verify_fails_when_signature_bytes_are_corrupted(tmp_path: Path) -> None:
    """A structurally-valid but wrong signature (same length, different bytes) must fail."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="4bc084cf-35e1-4023-9b27-8f400c615326") as profile:
        package_path = _build_package(tmp_path, bucket_id=profile.bucket_id)
        keypair = ensure_review_package_signing_keypair(bucket_id=profile.bucket_id, repository=profile.repository)
        signed = sign_review_package(package_path, keypair=keypair)

        corrupted_signature_hex = ("0" if signed.signature_hex[0] != "0" else "1") + signed.signature_hex[1:]
        corrupted = signed.model_copy(update={"signature_hex": corrupted_signature_hex})

        assert verify_review_package_signature(package_path, corrupted, public_key_hex=keypair.public_key_hex) is False


def test_two_buckets_mint_independent_keypairs(tmp_path: Path) -> None:
    """Two profiles' signing keys never collide -- confirming the per-bucket object key grammar."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="6e572448-849d-487e-adcb-de9c2f6fb3b3") as profile_one:
        keypair_one = ensure_review_package_signing_keypair(
            bucket_id=profile_one.bucket_id,
            repository=profile_one.repository,
        )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="83a9a3da-d37f-4e1e-a338-9c5bdd5601ec") as profile_two:
        keypair_two = ensure_review_package_signing_keypair(
            bucket_id=profile_two.bucket_id,
            repository=profile_two.repository,
        )

    assert keypair_one.public_key_hex != keypair_two.public_key_hex
    assert keypair_one.private_key_hex != keypair_two.private_key_hex


@pytest.mark.parametrize(
    "stored_bucket_id",
    (pytest.param(_FOREIGN_BUCKET_ID, id="foreign"),),
)
def test_signing_keypair_refuses_foreign_payload_bucket(
    tmp_path: Path,
    stored_bucket_id: str,
) -> None:
    """A real encrypted row cannot claim a different bucket identity.

    A whitespace-wrapped spelling is deliberately NOT part of this refusal.
    :data:`~cadrumo.core.identity.BucketId` declares
    ``StringConstraints(strip_whitespace=True)``, so a padded spelling of a
    valid id IS the same identity -- ``canonical_bucket_id`` exists precisely
    so a wrapped spelling cannot address a second bucket. The padded case is
    proved as normalisation below rather than as a refusal here.
    """
    target_bucket_id = _OWNER_BUCKET_ID
    private_key = Ed25519PrivateKey.generate()
    misplaced = ReviewPackageSigningKeypair(
        bucket_id=stored_bucket_id,
        private_key_hex=private_key.private_bytes_raw().hex(),
        public_key_hex=private_key.public_key().public_bytes_raw().hex(),
        created_at=_NOW,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=target_bucket_id) as profile:
        object_key = _signing_key_object_key(target_bucket_id)
        misplaced_payload = misplaced.model_dump_json().encode("utf-8")
        profile.repository.save(
            namespace=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key=object_key,
            classification=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            schema_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=misplaced_payload,
            write_provenance="test.review_package_signing.foreign_payload",
        )

        with pytest.raises(ReviewPackageSigningError):
            load_review_package_signing_keypair(bucket_id=target_bucket_id, repository=profile.repository)
        with pytest.raises(ReviewPackageSigningError, match="does not belong"):
            ensure_review_package_signing_keypair(bucket_id=target_bucket_id, repository=profile.repository)

        unchanged = profile.repository.load(
            MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key,
            expected_class=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            max_supported_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
        )
        assert unchanged is not None
        assert unchanged.payload == misplaced_payload


def test_signing_keypair_accepts_a_whitespace_wrapped_spelling_as_the_same_bucket(tmp_path: Path) -> None:
    """A padded spelling of a valid id addresses ONE bucket, not a second one.

    This replaces a case that asserted the opposite. It only ever passed
    because the fixture used a readable label, which failed UUID parsing
    before any bucket comparison happened -- a refusal for the wrong reason.
    With canonical identities the documented contract is visible: the stored
    row is accepted, because stripping is what keeps one bucket from wearing
    two addresses.
    """
    padded = f" {_OWNER_BUCKET_ID} "
    private_key = Ed25519PrivateKey.generate()
    stored = ReviewPackageSigningKeypair(
        bucket_id=padded,
        private_key_hex=private_key.private_bytes_raw().hex(),
        public_key_hex=private_key.public_key().public_bytes_raw().hex(),
        created_at=_NOW,
    )

    assert stored.bucket_id == _OWNER_BUCKET_ID, "BucketId must strip surrounding whitespace on construction"

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OWNER_BUCKET_ID) as profile:
        profile.repository.save(
            namespace=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key=_signing_key_object_key(_OWNER_BUCKET_ID),
            classification=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            schema_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=stored.model_dump_json().encode("utf-8"),
            write_provenance="test.review_package_signing.whitespace_payload",
        )

        loaded = load_review_package_signing_keypair(
            bucket_id=_OWNER_BUCKET_ID,
            repository=profile.repository,
        )

    assert loaded is not None
    assert loaded.bucket_id == _OWNER_BUCKET_ID
    assert loaded.public_key_hex == stored.public_key_hex


def test_concurrent_signing_keypair_mint_reuses_one_encrypted_key_and_signs_package(tmp_path: Path) -> None:
    """Concurrent first use returns one persisted Ed25519 keypair, which signs a real package."""
    bucket_id = _CONCURRENT_BUCKET_ID
    worker_count = 12
    gate = threading.Barrier(worker_count)
    result_lock = threading.Lock()
    minted: list[ReviewPackageSigningKeypair] = []
    errors: list[str] = []

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:

        def worker() -> None:
            try:
                gate.wait(timeout=60)
                keypair = ensure_review_package_signing_keypair(
                    bucket_id=bucket_id,
                    repository=profile.repository,
                    generated_at=_NOW,
                )
                with result_lock:
                    minted.append(keypair)
            except Exception as exc:  # surface a real worker failure to the assertion below
                with result_lock:
                    errors.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=contextvars.copy_context().run, args=(worker,)) for _ in range(worker_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert not [thread for thread in threads if thread.is_alive()], "keypair mint workers deadlocked"
        assert errors == [], f"concurrent keypair mint failures: {errors}"
        assert len(minted) == worker_count

        loaded = load_review_package_signing_keypair(bucket_id=bucket_id, repository=profile.repository)
        assert {keypair.private_key_hex for keypair in minted} == {loaded.private_key_hex}
        assert {keypair.public_key_hex for keypair in minted} == {loaded.public_key_hex}

        from sqlalchemy import func, select

        with session_scope(profile.repository._engine) as session:
            persisted_count = session.execute(
                select(func.count())
                .select_from(SecureObjectRow)
                .where(SecureObjectRow.namespace == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace),
            ).scalar_one()
        assert persisted_count == 1

        package_path = _build_package(tmp_path, bucket_id=bucket_id)
        signed = sign_review_package(package_path, keypair=loaded, signed_at=_NOW)
        assert verify_review_package_signature(package_path, signed, public_key_hex=loaded.public_key_hex) is True


__all__: list[str] = []


@pytest.mark.parametrize(
    "instant",
    [
        datetime(2026, 5, 3, 12, 0),  # naive: the shape under test
        datetime(2026, 5, 3, 12, 0, tzinfo=timezone(timedelta(hours=1))),
    ],
)
def test_signing_keypair_refuses_a_non_utc_created_at(instant: datetime) -> None:
    """A key's minting instant is held to the same UTC contract as its signatures.

    ``signed_at`` already refused a naive or offset instant while the key's own
    ``created_at`` accepted one, so "was this signature made after the key
    existed?" was unanswerable across the boundary the signature defends.
    """
    with pytest.raises(ValidationError):
        ReviewPackageSigningKeypair(
            bucket_id="bucket",
            private_key_hex="a" * 64,
            public_key_hex="b" * 64,
            created_at=instant,
        )


@pytest.mark.parametrize(
    "instant",
    [
        datetime(2026, 5, 3, 12, 0),  # naive: the shape under test
        datetime(2026, 5, 3, 12, 0, tzinfo=timezone(timedelta(hours=1))),
    ],
)
def test_signing_public_key_refuses_a_non_utc_created_at(instant: datetime) -> None:
    """The exported half carries the same instant under the same contract."""
    with pytest.raises(ValidationError):
        ReviewPackageSigningPublicKey(
            bucket_id="bucket",
            public_key_hex="b" * 64,
            created_at=instant,
        )


def test_signing_keys_accept_a_utc_created_at() -> None:
    """Positive control: the UTC shape the mint path produces is still accepted."""
    minted_at = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)

    keypair = ReviewPackageSigningKeypair(
        bucket_id="bucket",
        private_key_hex="a" * 64,
        public_key_hex="b" * 64,
        created_at=minted_at,
    )
    public = ReviewPackageSigningPublicKey(
        bucket_id="bucket",
        public_key_hex="b" * 64,
        created_at=minted_at,
    )

    assert keypair.created_at == minted_at
    assert public.created_at == minted_at
