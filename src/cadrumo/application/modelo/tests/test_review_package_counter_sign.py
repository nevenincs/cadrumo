"""Counter-signed accountant receipt roundtrip and anti-tautology proofs.

Exercises :mod:`~application.modelo._review_package_counter_sign` end to
end against a REAL built-and-checksummed review package
(:func:`~application.modelo.build_review_package`), a REAL operator
signature (:func:`~application.modelo.sign_review_package`), and a REAL
accountant counter-signature over that signature -- both parties' keypairs
minted and persisted through REAL encrypted
:class:`~adapters.persistence.storage.SecureObjectRepository` instances
scoped to two distinct genuine ``BUCKET_DEK_V1`` buckets
(:func:`~tests.secure_sql.isolated_two_bucket_runtime`, no mocks or
fakes): operator signs, accountant counter-signs, both-layer verify passes;
tamper the archive, the note, the counter-signature, or swap either party's
public key, and verification fails.

Mirrors the anti-tautology discipline established in
``test_review_package_signing.py``: every negative-path test names the exact
way the system deviates from "clean" before asserting the refusal.

See Also:
    :mod:`~application.modelo._review_package_counter_sign`
        Counter-sign receipt implementation exercised by the roundtrip and
        tamper cases.
    :mod:`~application.modelo._review_package_signing`
        Operator Ed25519 signing layer that the accountant receipt signs over.
    :mod:`~application.modelo._review_package`
        Checksum-manifest package builder re-verified before signature checks.
    :mod:`~application.modelo._review_package_feedback`
        Follow-on encrypted feedback-package round trip that can carry a
        counter-signed receipt back to the originator.
    :mod:`~application.modelo.tests.test_review_package_signing`
        Baseline anti-tautology signing tests mirrored by this counter-sign
        slice.
"""

from __future__ import annotations

import functools
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.bindings import CasillaObservation

from ....adapters.persistence.storage import MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....core import Period, validated_casilla_id
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    WorkUnitState,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from ....tests.secure_sql import MultiBucketTestRuntime, isolated_two_bucket_runtime
from .._review_package_counter_sign import (
    CounterSignedReceipt,
    counter_sign_review_package,
    verify_counter_signed_receipt,
)
from .._review_package_signing import (
    ReviewPackageSigningKeypair,
    SignedReviewPackage,
    ensure_review_package_signing_keypair,
    review_package_signing_public_key,
    sign_review_package,
)
from ._review_package_bytes_support import build_package_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
_BASE_CASILLA = validated_casilla_id("base", surface="test_review_package_counter_sign")
_CUOTA_CASILLA = validated_casilla_id("cuota", surface="test_review_package_counter_sign")
_DRAFT_BYTES = b"FICHERO-BOE-BYTES-FOR-REVIEW-PACKAGE-COUNTER-SIGN-TEST"


def _work_unit(*, bucket_id: str) -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="review-package-counter-sign-revision",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="review-package-counter-sign-revision",
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
                source_refs=("test-review-package-counter-sign",),
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


def _raw_public_key_hex(private_key: Ed25519PrivateKey) -> str:
    return private_key.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw).hex()


def _sign_as_operator(
    runtime: MultiBucketTestRuntime,
    package_path: Path,
) -> tuple[ReviewPackageSigningKeypair, SignedReviewPackage]:
    """Mint (or load) the primary (operator) bucket's keypair and sign ``package_path``.

    ``primary`` is already the active session on fixture entry, so no
    ``switch_to_secondary`` is needed here.
    """
    keypair = ensure_review_package_signing_keypair(
        bucket_id=runtime.primary.bucket_id,
        repository=runtime.primary.repository,
    )
    return keypair, sign_review_package(package_path, keypair=keypair)


def _mint_accountant_keypair(runtime: MultiBucketTestRuntime) -> ReviewPackageSigningKeypair:
    """Mint (or load) the secondary (accountant) bucket's keypair.

    The secondary bucket's repository is bound to its own session at
    construction time (see ``isolated_two_bucket_runtime``), so any call
    against it must run inside ``switch_to_secondary`` or the runtime's
    session-freshness guard refuses the stale handle.
    """
    with runtime.switch_to_secondary():
        return ensure_review_package_signing_keypair(
            bucket_id=runtime.secondary.bucket_id,
            repository=runtime.secondary.repository,
        )


def test_operator_signs_accountant_counter_signs_both_layers_verify(tmp_path: Path) -> None:
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)

        operator_keypair, signed = _sign_as_operator(runtime, package_path)
        accountant_keypair = _mint_accountant_keypair(runtime)

        receipt = counter_sign_review_package(
            signed,
            counter_signer_keypair=accountant_keypair,
            note="reviewed, no changes",
            counter_signed_at=_NOW,
        )
        round_tripped = CounterSignedReceipt.model_validate_json(receipt.model_dump_json())

        assert round_tripped == receipt
        assert round_tripped.counter_signed_at == _NOW
        assert round_tripped.note == "reviewed, no changes"
        assert round_tripped.original_signature == signed
        assert len(bytes.fromhex(round_tripped.counter_signature_hex)) == 64
        assert round_tripped.counter_public_key_hex == accountant_keypair.public_key_hex

        operator_public_key = review_package_signing_public_key(operator_keypair)
        accountant_public_key = review_package_signing_public_key(accountant_keypair)

        assert (
            verify_counter_signed_receipt(
                package_path,
                round_tripped,
                operator_public_key_hex=operator_public_key.public_key_hex,
                counter_signer_public_key_hex=accountant_public_key.public_key_hex,
            )
            is True
        )


@pytest.mark.parametrize(
    "counter_signed_at",
    (
        pytest.param(datetime(2026, 7, 3, 12, 0), id="naive"),
        pytest.param(datetime(2026, 7, 3, 14, 0, tzinfo=timezone(timedelta(hours=2))), id="non-utc"),
    ),
)
def test_counter_sign_refuses_a_naive_or_non_utc_envelope_timestamp(
    tmp_path: Path,
    counter_signed_at: datetime,
) -> None:
    """An accountant receipt must carry one explicit UTC instant."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)
        _, signed = _sign_as_operator(runtime, package_path)
        accountant_keypair = _mint_accountant_keypair(runtime)

        with pytest.raises(ValidationError, match="datetime must be"):
            counter_sign_review_package(
                signed,
                counter_signer_keypair=accountant_keypair,
                counter_signed_at=counter_signed_at,
            )


def test_verify_fails_when_original_package_tampered_after_counter_sign(tmp_path: Path) -> None:
    """Archive tamper is caught by the re-run integrity check before either signature layer."""
    import zipfile

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)
        operator_keypair, signed = _sign_as_operator(runtime, package_path)
        accountant_keypair = _mint_accountant_keypair(runtime)
        receipt = counter_sign_review_package(signed, counter_signer_keypair=accountant_keypair, note="ok")

        rewritten = package_path.with_name(package_path.name + ".rewritten")
        with zipfile.ZipFile(package_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
            for item in src.infolist():
                data = b"TAMPERED FICHERO BYTES" if item.filename == "draft.fichero-boe" else src.read(item.filename)
                dst.writestr(item, data)
        rewritten.replace(package_path)

        assert (
            verify_counter_signed_receipt(
                package_path,
                receipt,
                operator_public_key_hex=operator_keypair.public_key_hex,
                counter_signer_public_key_hex=accountant_keypair.public_key_hex,
            )
            is False
        )


def test_verify_fails_when_note_edited_after_counter_sign(tmp_path: Path) -> None:
    """Editing the counter-signer's note invalidates the counter-signature (not just re-parses)."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)
        operator_keypair, signed = _sign_as_operator(runtime, package_path)
        accountant_keypair = _mint_accountant_keypair(runtime)
        receipt = counter_sign_review_package(
            signed,
            counter_signer_keypair=accountant_keypair,
            note="approved as filed",
        )

        tampered_receipt = receipt.model_copy(update={"note": "approved WITH CHANGES"})

        assert (
            verify_counter_signed_receipt(
                package_path,
                tampered_receipt,
                operator_public_key_hex=operator_keypair.public_key_hex,
                counter_signer_public_key_hex=accountant_keypair.public_key_hex,
            )
            is False
        )


def test_verify_fails_when_counter_signature_bytes_are_corrupted(tmp_path: Path) -> None:
    """A structurally-valid but wrong counter-signature (same length, different bytes) must fail."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)
        operator_keypair, signed = _sign_as_operator(runtime, package_path)
        accountant_keypair = _mint_accountant_keypair(runtime)
        receipt = counter_sign_review_package(signed, counter_signer_keypair=accountant_keypair, note="ok")

        corrupted_hex = ("0" if receipt.counter_signature_hex[0] != "0" else "1") + receipt.counter_signature_hex[1:]
        corrupted_receipt = receipt.model_copy(update={"counter_signature_hex": corrupted_hex})

        assert (
            verify_counter_signed_receipt(
                package_path,
                corrupted_receipt,
                operator_public_key_hex=operator_keypair.public_key_hex,
                counter_signer_public_key_hex=accountant_keypair.public_key_hex,
            )
            is False
        )


def test_verify_fails_with_wrong_operator_public_key(tmp_path: Path) -> None:
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)
        _, signed = _sign_as_operator(runtime, package_path)
        accountant_keypair = _mint_accountant_keypair(runtime)
        receipt = counter_sign_review_package(signed, counter_signer_keypair=accountant_keypair, note="ok")

        wrong_operator_public_key_hex = _raw_public_key_hex(Ed25519PrivateKey.generate())

        assert (
            verify_counter_signed_receipt(
                package_path,
                receipt,
                operator_public_key_hex=wrong_operator_public_key_hex,
                counter_signer_public_key_hex=accountant_keypair.public_key_hex,
            )
            is False
        )


def test_verify_fails_with_wrong_counter_signer_public_key(tmp_path: Path) -> None:
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        package_path = _build_package(tmp_path, bucket_id=runtime.primary.bucket_id)
        operator_keypair, signed = _sign_as_operator(runtime, package_path)
        accountant_keypair = _mint_accountant_keypair(runtime)
        receipt = counter_sign_review_package(signed, counter_signer_keypair=accountant_keypair, note="ok")

        wrong_counter_signer_public_key_hex = _raw_public_key_hex(Ed25519PrivateKey.generate())

        assert (
            verify_counter_signed_receipt(
                package_path,
                receipt,
                operator_public_key_hex=operator_keypair.public_key_hex,
                counter_signer_public_key_hex=wrong_counter_signer_public_key_hex,
            )
            is False
        )


def test_counter_signer_keys_never_stored_as_plaintext(tmp_path: Path) -> None:
    """The accountant's counter-signing keypair is persisted only as ciphertext.

    Mirrors ``test_private_key_is_never_stored_as_plaintext`` in
    ``test_review_package_signing.py`` for the counter-signer's identity: this
    module introduces no new key-custody mechanism, so the same guarantee
    that primitive already proves must hold for whichever bucket the
    counter-signer's keypair is scoped to.
    """
    from sqlalchemy import select

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        accountant_keypair = _mint_accountant_keypair(runtime)

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
