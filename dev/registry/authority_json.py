"""Development-only eager JSON baseline for indexed-authority comparison."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from cadrumo.core.atomic_write import hardened_staged_publication
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityArtifactUnavailableError,
    _decode_artifact,
    _encode_artifact,
)


def bundled_authority_json_path() -> Path:
    """Return the repository-only eager comparison baseline path."""
    return bundled_path("registry", "authority", "authority.json")


def write_authority_artifact(
    path: Path,
    artifact: AuthorityArtifact,
    *,
    before_replace: Callable[[], None] | None = None,
) -> None:
    """Write one profile-complete v5 development baseline atomically."""
    if artifact.profile_schema is None:
        raise ValueError("development authority JSON requires an enrolled profile schema")
    encoded = _encode_artifact(artifact)
    _decode_artifact(encoded)
    with hardened_staged_publication(path) as publication:
        with publication.path.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if before_replace is not None:
            before_replace()
        publication.publish()


def read_authority_artifact(path: Path) -> AuthorityArtifact:
    """Read one profile-complete v5 development baseline without fallback."""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise AuthorityArtifactUnavailableError(f"development authority baseline is unavailable at {path}") from exc
    artifact = _decode_artifact(payload)
    if artifact.profile_schema is None:
        raise ValueError("development authority JSON lacks the required enrolled profile schema")
    return artifact


def published_authority(path: Path) -> ValidatedRegistryAuthority:
    """Materialize the eager development baseline used only by paired benchmarks."""
    artifact = read_authority_artifact(path)
    return ValidatedRegistryAuthority.from_validated_components(
        modelos=artifact.modelos,
        catalogues=artifact.catalogues,
        identity_digest=artifact.identity_digest,
        evidence=artifact.evidence,
        profile_schema=artifact.profile_schema,
    )


__all__ = [
    "bundled_authority_json_path",
    "published_authority",
    "read_authority_artifact",
    "write_authority_artifact",
]
