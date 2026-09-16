"""The publisher embeds exactly the source bytes the runtime availability contract declares."""

from __future__ import annotations

import pytest

from cadrumo.core.hashing import sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityBuildIdentity,
    AuthorityEvidenceProjection,
)
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.source_byte_availability import source_bytes_are_embedded
from dev.registry.compiler.authority import compiled_bundled_authority

from ..pipeline.authority_publication import _project_evidence, _project_source_evidence, require_evidence_closure

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BUILD_IDENTITY = AuthorityBuildIdentity.from_inputs(
    source_identity_digest=sha256_hex(b"source byte availability fixture sources"),
    compiler_identity_digest=sha256_hex(b"source byte availability fixture compiler"),
)


@pytest.fixture(scope="module")
def compiled() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


@pytest.fixture(scope="module")
def projection(compiled: ValidatedRegistryAuthority) -> AuthorityEvidenceProjection:
    return _project_evidence(compiled.catalogues.legal, compiled.catalogues.sources, source_root=bundled_path())


def _artifact(compiled: ValidatedRegistryAuthority, evidence: AuthorityEvidenceProjection) -> AuthorityArtifact:
    return AuthorityArtifact(
        modelos=compiled.modelos,
        catalogues=compiled.catalogues,
        identity_digest=_BUILD_IDENTITY.identity_digest,
        build_identity=_BUILD_IDENTITY,
        profile_schema=compiled.profile_schema(),
        evidence=evidence,
    )


def test_publisher_selects_exactly_the_contract_embedded_sources(
    compiled: ValidatedRegistryAuthority, projection: AuthorityEvidenceProjection
) -> None:
    sources = compiled.catalogues.sources
    expected = {str(source_id) for source_id, source in sources.items() if source_bytes_are_embedded(source)}
    published = {item.source_reference_id for item in projection.sources}

    assert expected
    assert len(expected) < len(sources)
    assert published == expected


def test_evidence_closure_accepts_the_publisher_projection_and_rejects_drift(
    compiled: ValidatedRegistryAuthority, projection: AuthorityEvidenceProjection
) -> None:
    sources = compiled.catalogues.sources
    require_evidence_closure(_artifact(compiled, projection))

    dictionary_id = next(
        item.source_reference_id
        for item in projection.sources
        if sources[item.source_reference_id].kind is RegistrySourceKind.DICTIONARY
    )
    missing_dictionary = AuthorityEvidenceProjection(
        legal=projection.legal,
        sources=tuple(item for item in projection.sources if item.source_reference_id != dictionary_id),
    )
    with pytest.raises(ValueError, match="runtime source catalogue"):
        require_evidence_closure(_artifact(compiled, missing_dictionary))

    record_design = next(source for source in sources.values() if source.kind is RegistrySourceKind.RECORD_DESIGN)
    extra_record_design = AuthorityEvidenceProjection(
        legal=projection.legal,
        sources=(*projection.sources, _project_source_evidence(record_design, source_root=bundled_path())),
    )
    with pytest.raises(ValueError, match="runtime source catalogue"):
        require_evidence_closure(_artifact(compiled, extra_record_design))
