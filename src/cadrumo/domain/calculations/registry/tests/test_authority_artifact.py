"""Behavioral contract tests for signed immutable authority publication."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....core.ed25519_signing import Ed25519KeypairHex, generate_ed25519_keypair_hex, sign_digest_hex
from .....core.hashing import canonical_json_bytes, sha256_hex
from ..authority_artifact import (
    AuthorityArtifact,
    AuthorityArtifactFormatError,
    AuthorityArtifactIntegrityError,
    AuthorityArtifactUnavailableError,
    read_authority_artifact,
    write_authority_artifact,
)
from ._referential_integrity_support import _minimal_catalogues, _minimal_modelo, _minimal_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IDENTITY_DIGEST = "e4c712d347701b34615314b6e3f8fdfd75ca5ee3eabe9c1c651668549fb7f66f"


@pytest.fixture
def publisher_keys() -> Ed25519KeypairHex:
    """Use a real ephemeral publisher identity for each artifact contract run."""
    return generate_ed25519_keypair_hex()


def _validated_authority_payload() -> AuthorityArtifact:
    """Build a real typed registry payload without requiring the authoring corpus."""
    return AuthorityArtifact(
        modelos=(_minimal_modelo(_minimal_revision()),),
        catalogues=_minimal_catalogues(),
        identity_digest=_IDENTITY_DIGEST,
    )


def _publish(path: Path, keys: Ed25519KeypairHex) -> None:
    """Publish one typed authority through the real signed writer."""
    write_authority_artifact(path, _validated_authority_payload(), signing_private_key_hex=keys.private_key_hex)


def _read(path: Path, keys: Ed25519KeypairHex) -> AuthorityArtifact:
    """Read one authority through the real trusted-public-key boundary."""
    return read_authority_artifact(path, verification_public_key_hex=keys.public_key_hex)


def test_published_authority_round_trips_as_the_complete_typed_payload(
    tmp_path: Path, publisher_keys: Ed25519KeypairHex
) -> None:
    """A consumer receives the complete authority authenticated by its publisher."""
    artifact_path = tmp_path / "authority.json"
    published = _validated_authority_payload()

    write_authority_artifact(artifact_path, published, signing_private_key_hex=publisher_keys.private_key_hex)

    consumed = _read(artifact_path, publisher_keys)

    assert consumed == published
    assert consumed.modelos[0].title_localization_key == published.modelos[0].title_localization_key
    assert consumed.catalogues.legal == published.catalogues.legal


def test_recomputed_replacement_frame_is_refused_without_a_publisher_signature(
    tmp_path: Path, publisher_keys: Ed25519KeypairHex
) -> None:
    """A modifier cannot make a replacement authority trusted by recomputing its hash."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path, publisher_keys)
    replacement = json.loads(artifact_path.read_bytes())
    replacement["payload"]["identity_digest"] = "0" * 64
    replacement["payload_sha256"] = sha256_hex(
        canonical_json_bytes({"schema_version": replacement["schema_version"], "payload": replacement["payload"]})
    )
    artifact_path.write_bytes(canonical_json_bytes(replacement))

    with pytest.raises(AuthorityArtifactIntegrityError):
        _read(artifact_path, publisher_keys)


def test_complete_authority_signed_by_another_publisher_is_refused(
    tmp_path: Path, publisher_keys: Ed25519KeypairHex
) -> None:
    """A complete alternate authority is rejected when its signer is not trusted."""
    artifact_path = tmp_path / "authority.json"
    alternate_publisher = generate_ed25519_keypair_hex()

    _publish(artifact_path, alternate_publisher)

    with pytest.raises(AuthorityArtifactIntegrityError):
        _read(artifact_path, publisher_keys)


def test_trusted_signature_does_not_admit_an_invalid_typed_payload(
    tmp_path: Path, publisher_keys: Ed25519KeypairHex
) -> None:
    """Authentication never substitutes for strict authority reconstruction."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path, publisher_keys)
    invalid = json.loads(artifact_path.read_bytes())
    invalid["payload"]["catalogues"] = {}
    signed_document = {"schema_version": invalid["schema_version"], "payload": invalid["payload"]}
    digest = sha256_hex(canonical_json_bytes(signed_document))
    invalid["payload_sha256"] = digest
    invalid["signature"] = sign_digest_hex(private_key_hex=publisher_keys.private_key_hex, digest_hex=digest)
    artifact_path.write_bytes(canonical_json_bytes(invalid))

    with pytest.raises(AuthorityArtifactFormatError):
        _read(artifact_path, publisher_keys)


@pytest.mark.parametrize("artifact_bytes", [b"not-json", b'{"schema_version":"unsupported"}'])
def test_malformed_or_unsupported_artifact_frame_is_refused(
    tmp_path: Path, publisher_keys: Ed25519KeypairHex, artifact_bytes: bytes
) -> None:
    """Malformed and unsupported wire inputs never reach authority reconstruction."""
    artifact_path = tmp_path / "authority.json"
    artifact_path.write_bytes(artifact_bytes)

    with pytest.raises(AuthorityArtifactFormatError):
        _read(artifact_path, publisher_keys)


def test_consumer_mutation_cannot_change_a_later_authority_read(
    tmp_path: Path, publisher_keys: Ed25519KeypairHex
) -> None:
    """Each authenticated read reconstructs an isolated authority graph."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path, publisher_keys)
    first = _read(artifact_path, publisher_keys)
    first.catalogues.legal["consumer-injected"] = next(iter(first.catalogues.legal.values()))

    later = _read(artifact_path, publisher_keys)

    assert "consumer-injected" not in later.catalogues.legal


def test_missing_publication_refuses_without_rebuilding_from_authoring_inputs(
    tmp_path: Path, publisher_keys: Ed25519KeypairHex
) -> None:
    """An absent artifact is a deterministic runtime refusal at the publication boundary."""
    with pytest.raises(AuthorityArtifactUnavailableError):
        _read(tmp_path / "missing-authority.json", publisher_keys)
