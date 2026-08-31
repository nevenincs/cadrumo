"""Ciphertext-payload-at-rest tests for the substrate envelope.

Exercises the ciphertext path of :mod:`cadrumo.adapters.persistence.storage.envelope`
end-to-end. Each test in the module asserts one invariant of the
at-rest encryption contract:

- A ``FINANCIAL`` / ``AUDIT`` payload encrypted via
  :func:`save_encrypted_envelope` leaks no plaintext leaf in the
  on-disk JSON (NIF, Decimal-stringified amount, and arbitrary string
  canaries).
- :func:`load_encrypted_envelope` round-trips back to the typed payload.
- The classification gate fires *before* the master key is consulted
  (a wrong-class envelope is rejected up front).
- The AAD binding makes ciphertext non-portable across consumers
  (different HKDF context raises :exc:`DecryptionError`).
- The AAD binding makes ciphertext non-portable across classes
  (a relabelled classification raises :exc:`DecryptionError` because
  the AAD changed).
- A wrong master key raises :exc:`DecryptionError`, never recovers
  plaintext.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from ......core.classification.policies import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ......tests.master_key import EphemeralMasterKeyProvider
from ...errors import ClassificationError, DecryptionError, StorageValidationError
from .._envelope import CipherEnvelope, Envelope, load_encrypted_envelope, save_encrypted_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NIF_CANARY = "12345678Z"
_AMOUNT_CANARY = "987654.32"
_HKDF_CONTEXT_TEST = b"cadrumo.adapters.persistence.storage.test.envelope.v1"


class _SamplePayload(BaseModel):
    """Synthetic payload for the ciphertext-at-rest tests."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    taxpayer_nif: str
    amount_total: str = Field(default="0.00")


@pytest.fixture
def provider() -> EphemeralMasterKeyProvider:
    return EphemeralMasterKeyProvider()


@pytest.fixture(autouse=True)
def _patch_master_key(provider: EphemeralMasterKeyProvider) -> Iterator[None]:
    with provider:
        yield


def _build_envelope(classification: SensitivityClass = SensitivityClass.FINANCIAL) -> Envelope[_SamplePayload]:
    return Envelope[_SamplePayload](
        schema_version=1,
        written_at=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
        classification=classification,
        payload=_SamplePayload(taxpayer_nif=_NIF_CANARY, amount_total=_AMOUNT_CANARY),
    )


class TestCiphertextRoundTrip:
    def test_round_trip_recovers_typed_payload(self, tmp_path: Path, provider: EphemeralMasterKeyProvider) -> None:
        envelope = _build_envelope()
        target = tmp_path / "record.cipher.json"
        save_encrypted_envelope(
            envelope,
            target,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TEST,
        )
        loaded = load_encrypted_envelope(
            target,
            Envelope[_SamplePayload],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TEST,
            max_supported_version=1,
        )
        assert loaded.payload.taxpayer_nif == _NIF_CANARY
        assert loaded.payload.amount_total == _AMOUNT_CANARY
        assert loaded.classification is SensitivityClass.FINANCIAL

    def test_save_write_failure_raises_storage_validation_without_path(
        self,
        tmp_path: Path,
        provider: EphemeralMasterKeyProvider,
    ) -> None:
        parent_file = tmp_path / "not-a-directory"
        parent_file.write_text("occupied", encoding=UTF_8_ENCODING)
        target = parent_file / "record.cipher.json"

        with pytest.raises(StorageValidationError) as excinfo:
            save_encrypted_envelope(
                _build_envelope(),
                target,
                master_key_provider=provider,
                hkdf_context=_HKDF_CONTEXT_TEST,
            )

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
        assert str(tmp_path) not in str(excinfo.value)


class TestNoPlaintextLeak:
    """The defining no plaintext leaf survives encryption."""

    def test_nif_canary_does_not_appear_in_on_disk_ciphertext(
        self,
        tmp_path: Path,
        provider: EphemeralMasterKeyProvider,
    ) -> None:
        envelope = _build_envelope()
        target = tmp_path / "record.cipher.json"
        save_encrypted_envelope(
            envelope,
            target,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TEST,
        )
        text = target.read_text(encoding=UTF_8_ENCODING)
        assert _NIF_CANARY not in text
        assert _AMOUNT_CANARY not in text

    def test_on_disk_shape_is_cipher_envelope(
        self,
        tmp_path: Path,
        provider: EphemeralMasterKeyProvider,
    ) -> None:
        envelope = _build_envelope()
        target = tmp_path / "record.cipher.json"
        save_encrypted_envelope(
            envelope,
            target,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TEST,
        )
        # Re-parse the on-disk JSON via the public CipherEnvelope model
        # to confirm the wire shape carries no payload field.
        text = target.read_text(encoding=UTF_8_ENCODING)
        cipher_envelope = CipherEnvelope.model_validate_json(text)
        assert cipher_envelope.classification is SensitivityClass.FINANCIAL
        assert cipher_envelope.encryption.ciphertext_b64
        assert "payload" not in text or '"payload":' not in text


class TestClassificationGate:
    def test_wrong_expected_class_rejected_before_decrypt(
        self,
        tmp_path: Path,
        provider: EphemeralMasterKeyProvider,
    ) -> None:
        envelope = _build_envelope(classification=SensitivityClass.FINANCIAL)
        target = tmp_path / "record.cipher.json"
        save_encrypted_envelope(
            envelope,
            target,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TEST,
        )
        with pytest.raises(ClassificationError) as excinfo:
            load_encrypted_envelope(
                target,
                Envelope[_SamplePayload],
                expected_class=SensitivityClass.AUDIT,
                master_key_provider=provider,
                hkdf_context=_HKDF_CONTEXT_TEST,
                max_supported_version=1,
            )
        assert str(tmp_path) not in str(excinfo.value)


class TestAadBinding:
    def test_wrong_hkdf_context_fails_decrypt(
        self,
        tmp_path: Path,
        provider: EphemeralMasterKeyProvider,
    ) -> None:
        """Different consumer HKDF context → AAD mismatch → DecryptionError."""
        envelope = _build_envelope()
        target = tmp_path / "record.cipher.json"
        save_encrypted_envelope(
            envelope,
            target,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TEST,
        )
        with pytest.raises(DecryptionError) as excinfo:
            load_encrypted_envelope(
                target,
                Envelope[_SamplePayload],
                expected_class=SensitivityClass.FINANCIAL,
                master_key_provider=provider,
                hkdf_context=b"cadrumo.adapters.persistence.storage.test.envelope.OTHER",
                max_supported_version=1,
            )
        assert str(tmp_path) not in str(excinfo.value)

    def test_invalid_persisted_aad_base64_raises_decryption_error_without_path(
        self,
        tmp_path: Path,
        provider: EphemeralMasterKeyProvider,
    ) -> None:
        envelope = _build_envelope()
        target = tmp_path / "record.cipher.json"
        save_encrypted_envelope(
            envelope,
            target,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TEST,
        )
        cipher_envelope = CipherEnvelope.model_validate_json(target.read_text(encoding=UTF_8_ENCODING))
        broken_encryption = cipher_envelope.encryption.model_copy(update={"associated_data_b64": "not-base64!!"})
        broken_envelope = cipher_envelope.model_copy(update={"encryption": broken_encryption})
        target.write_text(broken_envelope.model_dump_json(), encoding=UTF_8_ENCODING)

        with pytest.raises(DecryptionError) as excinfo:
            load_encrypted_envelope(
                target,
                Envelope[_SamplePayload],
                expected_class=SensitivityClass.FINANCIAL,
                master_key_provider=provider,
                hkdf_context=_HKDF_CONTEXT_TEST,
                max_supported_version=1,
            )

        assert str(tmp_path) not in str(excinfo.value)


class TestKeyMismatch:
    def test_wrong_master_key_fails_decrypt(
        self,
        tmp_path: Path,
        provider: EphemeralMasterKeyProvider,
    ) -> None:
        envelope = _build_envelope()
        target = tmp_path / "record.cipher.json"
        save_encrypted_envelope(
            envelope,
            target,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TEST,
        )
        # Build a different ephemeral provider with a different master
        # key; the same ciphertext must not decrypt under the wrong key.
        other_provider = EphemeralMasterKeyProvider()
        with pytest.raises(DecryptionError):
            load_encrypted_envelope(
                target,
                Envelope[_SamplePayload],
                expected_class=SensitivityClass.FINANCIAL,
                master_key_provider=other_provider,
                hkdf_context=_HKDF_CONTEXT_TEST,
                max_supported_version=1,
            )


class TestEnvelopeVersionGate:
    def test_inner_version_higher_than_consumer_rejected(
        self,
        tmp_path: Path,
        provider: EphemeralMasterKeyProvider,
    ) -> None:
        from ...errors import EnvelopeVersionError

        envelope = Envelope[_SamplePayload](
            schema_version=99,
            written_at=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=_SamplePayload(taxpayer_nif=_NIF_CANARY),
        )
        target = tmp_path / "record.cipher.json"
        save_encrypted_envelope(
            envelope,
            target,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TEST,
        )
        with pytest.raises(EnvelopeVersionError):
            load_encrypted_envelope(
                target,
                Envelope[_SamplePayload],
                expected_class=SensitivityClass.FINANCIAL,
                master_key_provider=provider,
                hkdf_context=_HKDF_CONTEXT_TEST,
                max_supported_version=1,
            )


class TestRelabelTampering:
    """An attacker who edits the cipher envelope to swap the
    ``classification`` field must hit DecryptionError because the AAD
    binds the original class."""

    def test_classification_relabel_fails_decrypt(
        self,
        tmp_path: Path,
        provider: EphemeralMasterKeyProvider,
    ) -> None:
        envelope = _build_envelope()
        target = tmp_path / "record.cipher.json"
        save_encrypted_envelope(
            envelope,
            target,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TEST,
        )
        # Mutate the on-disk classification to AUDIT but keep the same
        # ciphertext (= an attacker swap).
        cipher_envelope = CipherEnvelope.model_validate_json(target.read_text(encoding=UTF_8_ENCODING))
        relabelled = cipher_envelope.model_copy(update={"classification": SensitivityClass.AUDIT})
        target.write_text(relabelled.model_dump_json(), encoding=UTF_8_ENCODING)
        with pytest.raises(DecryptionError):
            load_encrypted_envelope(
                target,
                Envelope[_SamplePayload],
                expected_class=SensitivityClass.AUDIT,
                master_key_provider=provider,
                hkdf_context=_HKDF_CONTEXT_TEST,
                max_supported_version=1,
            )
