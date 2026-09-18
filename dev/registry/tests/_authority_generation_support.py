"""One minimal publishable authority artifact, shared by the generation tests."""

from __future__ import annotations

from cadrumo.core.hashing import sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityBuildIdentity,
    AuthorityEvidenceProjection,
)
from cadrumo.domain.calculations.registry.tests.artifact_runtime_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
)

from ..compiler.profile_schema import capture_profile_schema

__all__ = ["publishable_artifact"]


def publishable_artifact(label: str) -> AuthorityArtifact:
    """Return a publishable artifact whose identity and profile title carry ``label``.

    Each label yields a distinct build identity, so two publications into one
    destination are two generations rather than a re-publication of the same
    content-addressed bytes.
    """
    build = AuthorityBuildIdentity.from_inputs(
        sha256_hex(f"source:{label}".encode()),
        sha256_hex(b"compiler"),
    )
    profile = capture_profile_schema(bundled_path("registry", "cadrumo", "user_profile", "schema.toml"))[1].model_copy(
        update={"title": f"Profile schema {label}"}
    )
    return AuthorityArtifact(
        modelos=(minimal_modelo(minimal_revision()),),
        catalogues=minimal_catalogues(),
        identity_digest=build.identity_digest,
        build_identity=build,
        evidence=AuthorityEvidenceProjection(),
        profile_schema=profile,
    )
