"""One minimal publishable authority artifact, shared by the generation tests."""

from __future__ import annotations

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityEvidenceProjection,
)
from cadrumo.domain.calculations.registry.tests.artifact_runtime_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
    synthetic_build_receipts,
)

from ..compiler.profile_schema import capture_profile_schema

__all__ = ["publishable_artifact"]


def publishable_artifact(label: str) -> AuthorityArtifact:
    """Return a publishable artifact whose identity and profile title carry ``label``.

    Each label yields a distinct build identity, so two publications into one
    destination are two generations rather than a re-publication of the same
    content-addressed bytes.
    """
    build, closure = synthetic_build_receipts(f"source:{label}")
    profile = capture_profile_schema(bundled_path("registry", "cadrumo", "user_profile", "schema.toml"))[1].model_copy(
        update={"title": f"Profile schema {label}"}
    )
    return AuthorityArtifact(
        modelos=(minimal_modelo(minimal_revision()),),
        catalogues=minimal_catalogues(),
        identity_digest=build.identity_digest,
        build_identity=build,
        compiler_closure=closure,
        evidence=AuthorityEvidenceProjection(),
        profile_schema=profile,
    )
