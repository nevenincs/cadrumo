"""SQLite authority compiler and read-only admission contracts."""

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
    ProfileSchemaComponentQuery,
)
from cadrumo.domain.calculations.registry.authority_store import (
    AuthorityDescriptor,
    AuthorityStoreCorruptionError,
    SQLiteAuthorityReader,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.tests._artifact_runtime_support import (
    _minimal_catalogues,
    _minimal_modelo,
    _minimal_revision,
)
from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition

from ..compiler.authority_database import build_authority_database
from ..compiler.profile_schema import capture_profile_schema
from ..pipeline.authority_publication import install_validated_authority_database

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _artifact() -> AuthorityArtifact:
    build_identity = AuthorityBuildIdentity.from_inputs(sha256_hex(b"source"), sha256_hex(b"compiler"))
    profile_schema = capture_profile_schema(bundled_path("registry", "cadrumo", "user_profile", "schema.toml"))[1]
    return AuthorityArtifact(
        modelos=(_minimal_modelo(_minimal_revision()),),
        catalogues=_minimal_catalogues(),
        identity_digest=build_identity.identity_digest,
        build_identity=build_identity,
        evidence=AuthorityEvidenceProjection(),
        profile_schema=profile_schema,
    )


def _published_candidate(directory: Path) -> Path:
    compiled = build_authority_database(directory / "candidate.sqlite3", _artifact())
    database_name = f"authority-{compiled.physical_sha256}.sqlite3"
    compiled.path.replace(directory / database_name)
    descriptor = AuthorityDescriptor(
        database=database_name,
        database_size=compiled.byte_count,
        database_sha256=compiled.physical_sha256,
        logical_generation=compiled.logical_generation,
    )
    descriptor_path = directory / "authority.current.json"
    descriptor_path.write_bytes(descriptor.to_bytes())
    return descriptor_path


def test_profile_component_load_is_generation_pinned_and_lazy(tmp_path: Path) -> None:
    reader = SQLiteAuthorityReader(_published_candidate(tmp_path), max_connections=2)
    try:
        assert reader.telemetry().entries == 0
        with reader.lease() as pin:
            profile = reader.load(ProfileSchemaComponentQuery(), pin=pin)
        assert isinstance(profile, ProfileSchemaDefinition)
        assert profile.id == "cadrumo.user_profile"
        assert reader.telemetry().entries == 1
        assert reader.active_leases == 0
    finally:
        reader.close()


def test_revision_context_selects_directory_before_one_complete_revision(tmp_path: Path) -> None:
    authority = IndexedRegistryAuthority(_published_candidate(tmp_path))
    try:
        with authority.operation() as operation:
            directory = operation.modelo_directory("130")
            selected = operation.revision_for_context("130", filing_year=2025, period="0A")
            assert str(selected.id) == str(directory.revisions[0].id)
            assert operation.legal_reference("ley-35-2006:art-1").id == "ley-35-2006:art-1"
            assert (
                operation.source_reference("aeat-dr-130-2019-v12").id
                == "aeat-dr-130-2019-v12"
            )
    finally:
        authority.close()


def test_admission_refuses_physical_database_tamper(tmp_path: Path) -> None:
    descriptor_path = _published_candidate(tmp_path)
    descriptor = AuthorityDescriptor.read(descriptor_path)
    database = tmp_path / descriptor.database
    payload = bytearray(database.read_bytes())
    payload[-1] ^= 1
    database.write_bytes(payload)

    with pytest.raises(AuthorityStoreCorruptionError, match="disagree with the published descriptor"):
        SQLiteAuthorityReader(descriptor_path)


def test_failed_currentness_check_preserves_the_previous_descriptor(tmp_path: Path) -> None:
    descriptor_path = tmp_path / "authority.current.json"
    descriptor_path.write_bytes(b"previous descriptor bytes")

    def refuse() -> None:
        raise RuntimeError("candidate changed")

    with pytest.raises(RuntimeError, match="candidate changed"):
        install_validated_authority_database(_artifact(), destination=tmp_path, require_current=refuse)

    assert descriptor_path.read_bytes() == b"previous descriptor bytes"


def test_content_addressed_install_refuses_an_existing_collision(tmp_path: Path) -> None:
    descriptor = install_validated_authority_database(
        _artifact(),
        destination=tmp_path,
        require_current=lambda: None,
    )
    database = tmp_path / descriptor.database
    database.write_bytes(b"different bytes under an accepted digest name")

    with pytest.raises(RegistryValidationError, match="content-addressed authority collision"):
        install_validated_authority_database(
            _artifact(),
            destination=tmp_path,
            require_current=lambda: None,
        )
