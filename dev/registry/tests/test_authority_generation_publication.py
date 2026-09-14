"""Publication acceptance for held readers and atomic generation cutover."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.hashing import sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityBuildIdentity,
    AuthorityEvidenceProjection,
)
from cadrumo.domain.calculations.registry.tests._artifact_runtime_support import (
    _minimal_catalogues,
    _minimal_modelo,
    _minimal_revision,
)

from ..compiler.profile_schema import capture_profile_schema
from ..pipeline.authority_publication import install_validated_authority_database

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain, pytest.mark.windows_only]


def _artifact(label: str) -> AuthorityArtifact:
    build = AuthorityBuildIdentity.from_inputs(
        sha256_hex(f"source:{label}".encode()),
        sha256_hex(b"compiler"),
    )
    profile = capture_profile_schema(bundled_path("registry", "cadrumo", "user_profile", "schema.toml"))[1].model_copy(
        update={"title": f"Profile schema {label}"}
    )
    return AuthorityArtifact(
        modelos=(_minimal_modelo(_minimal_revision()),),
        catalogues=_minimal_catalogues(),
        identity_digest=build.identity_digest,
        build_identity=build,
        evidence=AuthorityEvidenceProjection(),
        profile_schema=profile,
    )


def test_held_reader_finishes_across_atomic_descriptor_cutover(tmp_path: Path) -> None:
    first = install_validated_authority_database(_artifact("first"), destination=tmp_path, require_current=lambda: None)
    authority = IndexedRegistryAuthority(tmp_path / "authority.current.json")
    try:
        with authority.operation() as held:
            assert held.profile_schema().title == "Profile schema first"
            second = install_validated_authority_database(
                _artifact("second"),
                destination=tmp_path,
                require_current=lambda: None,
            )
            assert second.database != first.database
            assert held.profile_schema().title == "Profile schema first"
            with authority.operation() as current:
                assert current.profile_schema().title == "Profile schema second"
    finally:
        authority.close()
