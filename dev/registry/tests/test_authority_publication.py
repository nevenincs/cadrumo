"""Behavioral publication guarantees for the development authority publisher."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.ed25519_signing import generate_ed25519_keypair_hex
from cadrumo.domain.calculations.registry.authority_artifact import AuthorityArtifact, write_authority_artifact
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.tests._referential_integrity_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
)

from ..pipeline.authority_publication import publish_validated_authority_candidate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _previous_publication() -> AuthorityArtifact:
    """Return a complete typed authority representing an already published release."""
    return AuthorityArtifact(
        modelos=(minimal_modelo(minimal_revision()),),
        catalogues=minimal_catalogues(),
        identity_digest="e4c712d347701b34615314b6e3f8fdfd75ca5ee3eabe9c1c651668549fb7f66f",
    )


def test_defective_candidate_refuses_before_replacing_the_previous_artifact(tmp_path: Path) -> None:
    """A real compiler refusal leaves the prior published artifact byte-for-byte intact."""
    keys = generate_ed25519_keypair_hex()
    artifact_path = tmp_path / "authority.json"
    write_authority_artifact(
        artifact_path,
        _previous_publication(),
        signing_private_key_hex=keys.private_key_hex,
    )
    previous_bytes = artifact_path.read_bytes()

    with pytest.raises(RegistryError):
        publish_validated_authority_candidate(
            registry_root=tmp_path / "defective-registry",
            source_root=tmp_path / "defective-sources",
            artifact_path=artifact_path,
            signing_private_key_hex=keys.private_key_hex,
        )

    assert artifact_path.read_bytes() == previous_bytes
