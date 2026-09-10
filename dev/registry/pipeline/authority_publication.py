"""Development-only publication of a validated registry authority artifact.

The runtime reader deliberately has no access to this module.  Publication
compiles and validates an explicit development candidate first, then commits
the resulting immutable authority through the artifact writer's atomic file
replacement.
"""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
    collect_registry_identity_fingerprints,
)
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    write_authority_artifact,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.identity import resolve_registry_identity

__all__ = ["publish_validated_authority_candidate"]


def publish_validated_authority_candidate(
    *,
    registry_root: Path,
    source_root: Path,
    artifact_path: Path,
    signing_private_key_hex: str,
) -> AuthorityArtifact:
    """Validate one development candidate and atomically publish its authority.

    ``registry_root`` and ``source_root`` are development inputs.  They are
    compiled through the real registry authority before this function creates
    an artifact.  A compiler or validation refusal returns before the writer
    touches ``artifact_path``, preserving any earlier publication.  The
    signing key and destination are explicit release-workflow inputs: this
    module neither stores private material nor chooses a runtime location.
    """
    authority = ValidatedRegistryAuthority.load(registry_root, source_root=source_root)
    identity = resolve_registry_identity(
        registry_root,
        collect_fingerprints=collect_registry_identity_fingerprints,
    )
    if authority._identity_digest != identity.digest:
        raise RegistryValidationError(
            "registry candidate changed while it was being validated; authority publication is refused",
        )
    artifact = AuthorityArtifact(
        modelos=authority.modelos,
        catalogues=authority.catalogues,
        identity_digest=identity.digest,
    )
    write_authority_artifact(
        artifact_path,
        artifact,
        signing_private_key_hex=signing_private_key_hex,
    )
    return artifact
