"""The outer cipher-envelope version is gated before the master key is used.

``CipherEnvelope.cipher_schema_version`` was parsed into a model field and then
consulted by nothing. ``load_encrypted_envelope`` compared only the *inner*
envelope's version against ``max_supported_version``, so an outer envelope
claiming any version at all was accepted and its payload decrypted and
returned. A version marker no reader compares against anything is not a
compatibility mechanism; the first real format change would have been read by
a build with no way to know it could not understand the bytes.

The gate sits beside the classification check, before the key is consulted,
for the same defence-in-depth reason: an outer format this build cannot
interpret should be refused without a crypto attempt.

The marker is required rather than defaulted, and that is what makes the gate
bite on the payload it most needs to catch. A default equal to the current
version let a stored document that omitted the key hydrate AS current, so the
equality comparison below it passed on a claim no writer had made -- the gate
reading as enforcement while enforcing nothing. Both the omission and the
mismatch are proven here to refuse ahead of key access, separately, because
they fire at different points and neither ordering implies the other.

The version is deliberately not bound into the AEAD associated data, and these
tests pin that reasoning rather than merely tolerating it. With exactly one
accepted value gated ahead of key use, rewriting the field can only produce a
refusal, so it steers nothing; the inner-version and classification bindings
that *do* route behaviour keep their existing enforcement, asserted here so
this change cannot be read as having relaxed them.

Real files, real AES-256-GCM, a real ephemeral master key.
"""

from __future__ import annotations

import json
import secrets
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

import pytest
from pydantic import BaseModel

from ......core.classification.policies import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ......tests.master_key import EphemeralMasterKeyProvider
from ...errors import ClassificationError, EnvelopeVersionError, StorageValidationError
from ...master_key.bucket_session import BucketSession
from ..contract import (
    CIPHER_ENVELOPE_SCHEMA_VERSION,
    AeadAlgorithm,
    CipherEnvelope,
    Envelope,
    load_encrypted_envelope,
    save_encrypted_envelope,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_HKDF_CONTEXT = b"cadrumo.test.cipher-version-gate.v1"
_INNER_VERSION = 3
_WRITTEN_AT = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


class _Payload(BaseModel):
    """Minimal typed payload for the round-trip."""

    label: str
    amount: int


def _provider() -> EphemeralMasterKeyProvider:
    return EphemeralMasterKeyProvider(key=secrets.token_bytes(32))


def _write(path: Path, provider: EphemeralMasterKeyProvider) -> Envelope[_Payload]:
    envelope = Envelope[_Payload](
        schema_version=_INNER_VERSION,
        written_at=_WRITTEN_AT,
        classification=SensitivityClass.FINANCIAL,
        payload=_Payload(label="cipher-version-gate", amount=42),
    )
    save_encrypted_envelope(
        envelope,
        path,
        master_key_provider=provider,
        hkdf_context=_HKDF_CONTEXT,
    )
    return envelope


def _read(path: Path, provider: EphemeralMasterKeyProvider) -> Envelope[_Payload]:
    return load_encrypted_envelope(
        path,
        Envelope[_Payload],
        expected_class=SensitivityClass.FINANCIAL,
        master_key_provider=provider,
        hkdf_context=_HKDF_CONTEXT,
        max_supported_version=_INNER_VERSION,
    )


def _rewrite_outer_version(path: Path, version: int) -> None:
    """Rewrite only ``cipher_schema_version`` on the outer envelope."""
    document = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    document["cipher_schema_version"] = version
    path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)


def _strip_outer_version(path: Path) -> None:
    """Delete ``cipher_schema_version`` from the stored outer envelope.

    The mutation a defaulted marker cannot survive: with a default equal to
    the current version, a document missing the key hydrates AS current and
    the equality gate below it passes on a claim the writer never made.
    """
    document = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    del document["cipher_schema_version"]
    assert "cipher_schema_version" not in document, "the fixture must actually remove the marker"
    path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)


class _TripwireProvider:
    """Master-key provider that fails loudly if a gate lets execution reach it.

    Discriminating for every ordering assertion here: a refusal placed *after*
    decryption would satisfy a plain refusal test while the crypto attempt --
    and the master-key access it needs -- had already happened on bytes this
    build has decided it cannot interpret. Reaching this provider at all
    surfaces its own error instead of the refusal under test.
    """

    def __init__(self) -> None:
        self.session: BucketSession | None = None
        self._activation_cm: AbstractContextManager[None] | None = None

    def get_master_key(self) -> bytes:
        raise AssertionError("master key consulted before the outer envelope gate refused")

    def provision_master_key(self) -> bytes:
        raise AssertionError("master key provisioned before the outer envelope gate refused")

    def __enter__(self) -> _TripwireProvider:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.session = None
        self._activation_cm = None


def test_a_written_envelope_round_trips_at_the_declared_version(tmp_path: Path) -> None:
    """Positive control: the writer stamps the one supported outer version.

    Also holds the outer record's strict round trip. ``CipherEnvelope`` carries
    no defaultable field of its own now that the version marker is required, so
    every field it declares is asserted across the real write-encrypt-read
    cycle rather than a subset of them. Its nested ``EncryptionMetadata``
    still defaults ``algorithm``, and no non-default value exists to populate
    it with -- the AEAD catalogue declares exactly one member -- so it is
    asserted present rather than varied.
    """
    provider = _provider()
    path = tmp_path / "round-trip.envelope.json"
    written = _write(path, provider)

    raw = path.read_text(encoding=UTF_8_ENCODING)
    document = json.loads(raw)
    assert document["cipher_schema_version"] == CIPHER_ENVELOPE_SCHEMA_VERSION

    stored = CipherEnvelope.model_validate_json(raw)
    assert stored.cipher_schema_version == CIPHER_ENVELOPE_SCHEMA_VERSION
    assert stored.written_at == _WRITTEN_AT
    assert stored.classification is SensitivityClass.FINANCIAL
    assert stored.encryption.algorithm is AeadAlgorithm.AES_256_GCM_V1
    assert stored.encryption.nonce_b64 and stored.encryption.ciphertext_b64
    assert stored.encryption.associated_data_b64 == document["encryption"]["associated_data_b64"]

    assert _read(path, provider) == written


def test_a_missing_outer_version_is_refused(tmp_path: Path) -> None:
    """Anti-tautology proof: a stored envelope with no version marker must refuse.

    The marker is required rather than defaulted precisely so this payload has
    nowhere to hide. Under a default the document would hydrate at the current
    version and reach decryption with the gate reporting success.
    """
    provider = _provider()
    path = tmp_path / "missing-version.envelope.json"
    _write(path, provider)
    _strip_outer_version(path)

    with pytest.raises(StorageValidationError):
        _read(path, provider)


@pytest.mark.parametrize("version", [CIPHER_ENVELOPE_SCHEMA_VERSION + 1, 2, 999])
def test_a_future_outer_version_is_refused(tmp_path: Path, version: int) -> None:
    """An outer version this build does not declare fails closed."""
    provider = _provider()
    path = tmp_path / "future-version.envelope.json"
    _write(path, provider)
    _rewrite_outer_version(path, version)

    with pytest.raises(EnvelopeVersionError):
        _read(path, provider)


def test_the_outer_version_is_refused_before_the_master_key_is_consulted(tmp_path: Path) -> None:
    """The gate runs ahead of key use, like the classification gate beside it."""
    provider = _provider()
    path = tmp_path / "ordering.envelope.json"
    _write(path, provider)
    _rewrite_outer_version(path, CIPHER_ENVELOPE_SCHEMA_VERSION + 1)

    with pytest.raises(EnvelopeVersionError):
        load_encrypted_envelope(
            path,
            Envelope[_Payload],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=_TripwireProvider(),
            hkdf_context=_HKDF_CONTEXT,
            max_supported_version=_INNER_VERSION,
        )


def test_a_missing_outer_version_is_refused_before_the_master_key_is_consulted(tmp_path: Path) -> None:
    """The missing-marker refusal must also precede key use.

    The version-mismatch refusal earning its ordering says nothing about this
    one: they fire at different points -- the mismatch at the explicit gate,
    the omission at the parse that builds the record the gate reads. A refusal
    that arrived after derivation would have spent the secret it exists to
    guard, so the ordering is asserted for each door separately rather than
    inferred from the neighbouring one.
    """
    provider = _provider()
    path = tmp_path / "missing-version-ordering.envelope.json"
    _write(path, provider)
    _strip_outer_version(path)

    with pytest.raises(StorageValidationError):
        load_encrypted_envelope(
            path,
            Envelope[_Payload],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=_TripwireProvider(),
            hkdf_context=_HKDF_CONTEXT,
            max_supported_version=_INNER_VERSION,
        )


def test_the_inner_version_gate_is_unchanged(tmp_path: Path) -> None:
    """The inner-envelope version remains enforced.

    Guards against reading this change as having moved enforcement rather than
    added it: the inner version routes the consumer's own payload schema and
    must still be checked.
    """
    provider = _provider()
    path = tmp_path / "inner-version.envelope.json"
    _write(path, provider)

    with pytest.raises(EnvelopeVersionError):
        load_encrypted_envelope(
            path,
            Envelope[_Payload],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT,
            max_supported_version=_INNER_VERSION + 1,
        )


def test_the_classification_gate_is_unchanged(tmp_path: Path) -> None:
    """The classification binding, which does route behaviour, still refuses."""
    provider = _provider()
    path = tmp_path / "classification.envelope.json"
    _write(path, provider)

    with pytest.raises(ClassificationError):
        load_encrypted_envelope(
            path,
            Envelope[_Payload],
            expected_class=SensitivityClass.AUDIT,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT,
            max_supported_version=_INNER_VERSION,
        )
