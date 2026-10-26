"""Minimal publishable authority artifacts, shared by the publication and generation tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityEvidenceProjection,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.tests.artifact_runtime_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
    synthetic_legal_identity,
)

from ..compiler.profile_schema import capture_profile_schema

__all__ = ["publishable_artifact", "synthetic_authority_artifact"]


def synthetic_authority_artifact(
    revision: ModeloRevision | None = None,
    *,
    source_label: str = "source",
    facts_restated_on: date | None = None,
) -> AuthorityArtifact:
    """Return a one-modelo artifact whose declared selectors pass their snapshot checks.

    ``revision`` replaces the miniature revision, for example to declare a
    grade it cannot satisfy; ``source_label`` names its synthetic legal
    identity; ``facts_restated_on`` restates the snapshot-checked facts in a
    new variant from that date.
    """
    return AuthorityArtifact(
        modelos=(minimal_modelo(revision or minimal_revision()),),
        catalogues=minimal_catalogues(facts_restated_on=facts_restated_on),
        identity_digest=synthetic_legal_identity(source_label),
        evidence=AuthorityEvidenceProjection(),
        profile_schema=capture_profile_schema(bundled_path("registry", "cadrumo", "user_profile", "schema.toml"))[1],
    )


def publishable_artifact(label: str) -> AuthorityArtifact:
    """Return a publishable artifact whose identity and profile title carry ``label``.

    Each label yields a distinct legal identity, so two publications into one
    destination are two generations rather than a re-publication of the same
    content-addressed bytes.
    """
    artifact = synthetic_authority_artifact(source_label=f"source:{label}")
    return replace(
        artifact, profile_schema=artifact.profile_schema.model_copy(update={"title": f"Profile schema {label}"})
    )
