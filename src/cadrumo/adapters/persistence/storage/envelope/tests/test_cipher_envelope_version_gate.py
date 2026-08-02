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
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel

from ......core.classification import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ......tests.master_key import EphemeralMasterKeyProvider
from ...errors import ClassificationError, EnvelopeVersionError
from .._envelope import (
    CIPHER_ENVELOPE_SCHEMA_VERSION,
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


def test_a_written_envelope_round_trips_at_the_declared_version(tmp_path: Path) -> None:
    """Positive control: the writer stamps the one supported outer version."""
    provider = _provider()
    path = tmp_path / "round-trip.envelope.json"
    written = _write(path, provider)

    document = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    assert document["cipher_schema_version"] == CIPHER_ENVELOPE_SCHEMA_VERSION
    assert _read(path, provider) == written


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
    """The gate runs ahead of key use, like the classification gate beside it.

    Discriminating: a version check placed *after* decryption would satisfy the
    refusal test above while leaving the crypto attempt -- and the master-key
    access -- happening on bytes this build has already decided it cannot
    interpret. A provider that raises on access proves the ordering, because
    reaching it at all would surface that error instead of the version error.
    """

    class _RefusingProvider:
        """Master-key provider that fails loudly if the gate lets execution reach it."""

        def get_master_key(self) -> bytes:
            raise AssertionError("master key consulted before the outer version gate refused")

    provider = _provider()
    path = tmp_path / "ordering.envelope.json"
    _write(path, provider)
    _rewrite_outer_version(path, CIPHER_ENVELOPE_SCHEMA_VERSION + 1)

    with pytest.raises(EnvelopeVersionError):
        load_encrypted_envelope(
            path,
            Envelope[_Payload],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=_RefusingProvider(),
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
