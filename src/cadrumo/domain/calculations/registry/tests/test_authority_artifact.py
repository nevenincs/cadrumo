"""Behavioral contract tests for the versioned, digest-checked authority publication."""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from pathlib import Path
from typing import cast

import pytest

from .....core.hashing import canonical_json_bytes, sha256_hex
from ..authority_artifact import (
    AUTHORITY_ARTIFACT_SCHEMA_VERSION,
    AuthorityArtifact,
    AuthorityArtifactFormatError,
    AuthorityArtifactIntegrityError,
    AuthorityArtifactUnavailableError,
    read_authority_artifact,
    read_shared_authority_artifact,
    write_authority_artifact,
)
from ._referential_integrity_support import _minimal_catalogues, _minimal_modelo, _minimal_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IDENTITY_DIGEST = "e4c712d347701b34615314b6e3f8fdfd75ca5ee3eabe9c1c651668549fb7f66f"


def _validated_authority_payload() -> AuthorityArtifact:
    """Build a real typed registry payload without requiring the authoring corpus."""
    return AuthorityArtifact(
        modelos=(_minimal_modelo(_minimal_revision()),),
        catalogues=_minimal_catalogues(),
        identity_digest=_IDENTITY_DIGEST,
    )


def _publish(path: Path) -> None:
    """Publish one typed authority through the real writer."""
    write_authority_artifact(path, _validated_authority_payload())


def _write_frame(path: Path, schema_version: str, payload: object, **extra: object) -> None:
    """Write a frame whose digest is consistent with its content, as a correct publisher would."""
    document = {"schema_version": schema_version, "payload": payload}
    path.write_bytes(
        canonical_json_bytes({**document, "payload_sha256": sha256_hex(canonical_json_bytes(document)), **extra})
    )


def test_published_authority_round_trips_as_the_complete_typed_payload(tmp_path: Path) -> None:
    """A consumer receives the complete authority the writer published."""
    artifact_path = tmp_path / "authority.json"
    published = _validated_authority_payload()

    write_authority_artifact(artifact_path, published)

    consumed = read_authority_artifact(artifact_path)

    assert consumed == published
    assert consumed.modelos[0].title_localization_key == published.modelos[0].title_localization_key
    assert consumed.catalogues.legal == published.catalogues.legal


def test_the_frame_carries_exactly_a_version_a_payload_and_its_digest(tmp_path: Path) -> None:
    """The publication is generated output: no signature, key, or certificate rides in it."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)

    frame = json.loads(artifact_path.read_bytes())

    assert set(frame) == {"schema_version", "payload", "payload_sha256"}
    assert frame["schema_version"] == AUTHORITY_ARTIFACT_SCHEMA_VERSION == "cadrumo-authority-artifact-v3"
    assert frame["payload_sha256"] == sha256_hex(
        canonical_json_bytes({"schema_version": frame["schema_version"], "payload": frame["payload"]})
    )


def test_a_payload_edited_without_its_digest_is_refused_as_corrupt(tmp_path: Path) -> None:
    """A changed payload under the old recorded digest is a corrupt artifact, never a readable one."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    corrupted = json.loads(artifact_path.read_bytes())
    corrupted["payload"]["identity_digest"] = "0" * 64
    artifact_path.write_bytes(canonical_json_bytes(corrupted))

    with pytest.raises(AuthorityArtifactIntegrityError, match="content digest"):
        read_authority_artifact(artifact_path)


def test_a_digest_consistent_frame_does_not_admit_an_invalid_typed_payload(tmp_path: Path) -> None:
    """A matching digest never substitutes for strict authority reconstruction."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    frame = json.loads(artifact_path.read_bytes())
    frame["payload"]["catalogues"] = {}
    _write_frame(artifact_path, frame["schema_version"], frame["payload"])

    with pytest.raises(AuthorityArtifactFormatError, match="invalid authority payload"):
        read_authority_artifact(artifact_path)


@pytest.mark.parametrize("superseded", ["cadrumo-authority-artifact-v1", "cadrumo-authority-artifact-v2"])
def test_a_frame_of_an_earlier_format_is_refused_by_name(tmp_path: Path, superseded: str) -> None:
    """An earlier frame, including a signed one, names the format to republish in."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    payload = json.loads(artifact_path.read_bytes())["payload"]
    _write_frame(artifact_path, superseded, payload, signature="00" * 64)

    with pytest.raises(AuthorityArtifactFormatError, match=f"superseded format '{superseded}'"):
        read_authority_artifact(artifact_path)


def test_a_current_frame_with_an_extra_member_is_refused(tmp_path: Path) -> None:
    """The reader accepts exactly the three frame members; a leftover signature is not ignored."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    payload = json.loads(artifact_path.read_bytes())["payload"]
    _write_frame(artifact_path, AUTHORITY_ARTIFACT_SCHEMA_VERSION, payload, signature="00" * 64)

    with pytest.raises(AuthorityArtifactFormatError, match="unexpected members \\['signature'\\]"):
        read_authority_artifact(artifact_path)


@pytest.mark.parametrize("artifact_bytes", [b"not-json", b'{"schema_version":"unsupported"}'])
def test_malformed_or_unsupported_artifact_frame_is_refused(tmp_path: Path, artifact_bytes: bytes) -> None:
    """Malformed and unsupported wire inputs never reach authority reconstruction."""
    artifact_path = tmp_path / "authority.json"
    artifact_path.write_bytes(artifact_bytes)

    with pytest.raises(AuthorityArtifactFormatError):
        read_authority_artifact(artifact_path)


def test_consumer_mutation_cannot_change_a_later_authority_read(tmp_path: Path) -> None:
    """A read authority graph refuses mutation, so a later read, shared or fresh, observes the publication."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    first = read_authority_artifact(artifact_path)
    with pytest.raises(TypeError):
        cast("MutableMapping[str, object]", first.catalogues.legal)["consumer-injected"] = object()

    later = read_authority_artifact(artifact_path)
    shared = read_shared_authority_artifact(artifact_path)
    with pytest.raises(TypeError):
        cast("MutableMapping[str, object]", shared.catalogues.legal)["consumer-injected"] = object()

    assert "consumer-injected" not in later.catalogues.legal
    assert read_shared_authority_artifact(artifact_path) is shared
    assert "consumer-injected" not in shared.catalogues.legal
    assert shared == later == _validated_authority_payload()


def test_shared_read_refuses_a_missing_publication(tmp_path: Path) -> None:
    """The shared reader refuses an absent artifact exactly as the strict reader does."""
    with pytest.raises(AuthorityArtifactUnavailableError):
        read_shared_authority_artifact(tmp_path / "missing-authority.json")


def test_missing_publication_refuses_without_rebuilding_from_authoring_inputs(tmp_path: Path) -> None:
    """An absent artifact is a deterministic runtime refusal at the publication boundary."""
    with pytest.raises(AuthorityArtifactUnavailableError):
        read_authority_artifact(tmp_path / "missing-authority.json")
