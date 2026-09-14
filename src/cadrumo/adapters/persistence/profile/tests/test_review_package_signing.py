"""Persistence-bound proofs for the review-package signing adapter."""

from __future__ import annotations

import contextvars
import functools
import threading
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select

from cadrumo.adapters.persistence.profile.review_package_signing import ReviewPackageSigningKeypairAdapter
from cadrumo.adapters.persistence.profile.tests._review_package_bytes_support import build_package_path
from cadrumo.adapters.persistence.storage.secure_object_namespaces import (
    MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE,
)
from cadrumo.adapters.persistence.storage.sql.orm import SecureObjectRow
from cadrumo.adapters.persistence.storage.sql.session import session_scope
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.review_package_signing import (
    ReviewPackageSigningError,
    ReviewPackageSigningKeypair,
    sign_review_package,
    verify_review_package_signature,
)
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.core.period import Period
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

_NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
_BASE_CASILLA = validated_casilla_id("base", surface="test_review_package_signing_adapter")
_CUOTA_CASILLA = validated_casilla_id("cuota", surface="test_review_package_signing_adapter")
_DRAFT_BYTES = b"FICHERO-BOE-BYTES-FOR-REVIEW-PACKAGE-SIGNING-ADAPTER-TEST"
_OWNER_BUCKET_ID = "2e510000-0000-4000-8000-000000000001"
_FOREIGN_BUCKET_ID = "2e510000-0000-4000-8000-000000000002"
_CONCURRENT_BUCKET_ID = "2e510000-0000-4000-8000-000000000003"


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
                source_refs=("test-review-package-signing-adapter",),
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
    """A second adapter call returns the same bucket singleton without rotation."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f1671beb-ff26-411d-b81c-76ccfb3af59c") as profile:
        capability = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=profile.bucket_id,
        )
        first = capability.ensure_keypair(bucket_id=profile.bucket_id)
        second = capability.ensure_keypair(bucket_id=profile.bucket_id)

    assert first.bucket_id == profile.bucket_id
    assert first.private_key_hex == second.private_key_hex
    assert first.public_key_hex == second.public_key_hex
    assert first.created_at == second.created_at
    message = b"adapter-anti-tautology-probe"
    signature = first.private_key().sign(message)
    second.public_key().verify(signature, message)


def test_private_key_is_never_stored_as_plaintext(tmp_path: Path) -> None:
    """The adapter persists the signing private key only as ciphertext."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="225abfcd-a133-4652-8f32-18f7494de580") as profile:
        capability = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=profile.bucket_id,
        )
        keypair = capability.ensure_keypair(bucket_id=profile.bucket_id)

        raw_record = profile.repository.load(
            MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.object_key_grammar.format(
                bucket_id=profile.bucket_id,
            ),
            expected_class=SensitivityClass.SECRET,
            max_supported_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
        )
        assert raw_record is not None
        assert keypair.private_key_hex.encode("utf-8") in raw_record.payload

        with session_scope(profile.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(
                    SecureObjectRow.namespace == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
                ),
            ).scalar_one()
            ciphertext_bytes = bytes(row.payload)

        assert keypair.private_key_hex.encode("utf-8") not in ciphertext_bytes
        assert bytes.fromhex(keypair.private_key_hex) not in ciphertext_bytes


def test_two_buckets_mint_independent_keypairs(tmp_path: Path) -> None:
    """Two adapter bindings keep their bucket keypairs independent."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="6e572448-849d-487e-adcb-de9c2f6fb3b3") as profile_one:
        first = ReviewPackageSigningKeypairAdapter(
            repository=profile_one.repository,
            bucket_id=profile_one.bucket_id,
        ).ensure_keypair(bucket_id=profile_one.bucket_id)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="83a9a3da-d37f-4e1e-a338-9c5bdd5601ec") as profile_two:
        second = ReviewPackageSigningKeypairAdapter(
            repository=profile_two.repository,
            bucket_id=profile_two.bucket_id,
        ).ensure_keypair(bucket_id=profile_two.bucket_id)

    assert first.public_key_hex != second.public_key_hex
    assert first.private_key_hex != second.private_key_hex


@pytest.mark.parametrize("stored_bucket_id", (pytest.param(_FOREIGN_BUCKET_ID, id="foreign"),))
def test_signing_keypair_refuses_foreign_payload_bucket(tmp_path: Path, stored_bucket_id: str) -> None:
    """A stored keypair claiming another bucket is rejected by the adapter."""
    private_key = Ed25519PrivateKey.generate()
    misplaced = ReviewPackageSigningKeypair(
        bucket_id=stored_bucket_id,
        private_key_hex=private_key.private_bytes_raw().hex(),
        public_key_hex=private_key.public_key().public_bytes_raw().hex(),
        created_at=_NOW,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OWNER_BUCKET_ID) as profile:
        object_key = MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.object_key_grammar.format(
            bucket_id=_OWNER_BUCKET_ID,
        )
        misplaced_payload = misplaced.model_dump_json().encode("utf-8")
        profile.repository.save(
            namespace=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key=object_key,
            classification=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            schema_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=misplaced_payload,
            write_provenance="test.review_package_signing_adapter.foreign_payload",
        )

        capability = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=_OWNER_BUCKET_ID,
        )
        with pytest.raises(ReviewPackageSigningError, match="does not belong"):
            capability.ensure_keypair(bucket_id=_OWNER_BUCKET_ID)

        unchanged = profile.repository.load(
            MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key,
            expected_class=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            max_supported_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
        )
        assert unchanged is not None
        assert unchanged.payload == misplaced_payload


def test_signing_keypair_accepts_a_whitespace_wrapped_spelling_as_the_same_bucket(tmp_path: Path) -> None:
    """The public namespace key contract normalizes one padded bucket spelling."""
    padded = f" {_OWNER_BUCKET_ID} "
    private_key = Ed25519PrivateKey.generate()
    stored = ReviewPackageSigningKeypair(
        bucket_id=padded,
        private_key_hex=private_key.private_bytes_raw().hex(),
        public_key_hex=private_key.public_key().public_bytes_raw().hex(),
        created_at=_NOW,
    )

    assert stored.bucket_id == _OWNER_BUCKET_ID

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OWNER_BUCKET_ID) as profile:
        profile.repository.save(
            namespace=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.object_key_grammar.format(
                bucket_id=_OWNER_BUCKET_ID,
            ),
            classification=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            schema_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=stored.model_dump_json().encode("utf-8"),
            write_provenance="test.review_package_signing_adapter.whitespace_payload",
        )
        loaded = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=_OWNER_BUCKET_ID,
        ).ensure_keypair(bucket_id=_OWNER_BUCKET_ID)

    assert loaded.bucket_id == _OWNER_BUCKET_ID
    assert loaded.public_key_hex == stored.public_key_hex


def test_concurrent_signing_keypair_mint_reuses_one_encrypted_key_and_signs_package(tmp_path: Path) -> None:
    """Concurrent first use returns one persisted adapter keypair."""
    worker_count = 12
    gate = threading.Barrier(worker_count)
    result_lock = threading.Lock()
    minted: list[ReviewPackageSigningKeypair] = []
    errors: list[str] = []

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CONCURRENT_BUCKET_ID) as profile:
        capability = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=_CONCURRENT_BUCKET_ID,
        )

        def worker() -> None:
            try:
                gate.wait(timeout=60)
                keypair = capability.ensure_keypair(bucket_id=_CONCURRENT_BUCKET_ID, generated_at=_NOW)
                with result_lock:
                    minted.append(keypair)
            except Exception as exc:  # surface a real worker failure below
                with result_lock:
                    errors.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=contextvars.copy_context().run, args=(worker,)) for _ in range(worker_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert not [thread for thread in threads if thread.is_alive()]
        assert errors == []
        assert len(minted) == worker_count

        loaded = capability.ensure_keypair(bucket_id=_CONCURRENT_BUCKET_ID)
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

        package_path = _build_package(tmp_path, bucket_id=_CONCURRENT_BUCKET_ID)
        signed = sign_review_package(package_path, keypair=loaded, signed_at=_NOW)
        assert verify_review_package_signature(package_path, signed, public_key_hex=loaded.public_key_hex) is True


def test_counter_signer_keys_never_stored_as_plaintext(tmp_path: Path) -> None:
    """The adapter's accountant keypair is persisted only as ciphertext."""
    from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_two_bucket_runtime

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime, runtime.switch_to_secondary():
        accountant_keypair = ReviewPackageSigningKeypairAdapter(
            repository=runtime.secondary.repository,
            bucket_id=runtime.secondary.bucket_id,
        ).ensure_keypair(bucket_id=runtime.secondary.bucket_id)

        from sqlalchemy import select

        with session_scope(runtime.secondary.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(
                    SecureObjectRow.namespace == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
                ),
            ).scalar_one()
            ciphertext_bytes = bytes(row.payload)

    assert accountant_keypair.private_key_hex.encode("utf-8") not in ciphertext_bytes
    assert bytes.fromhex(accountant_keypair.private_key_hex) not in ciphertext_bytes


__all__: list[str] = []
