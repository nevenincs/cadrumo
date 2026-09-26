"""Runtime authority behavior at the published indexed boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority, bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
)
from cadrumo.domain.calculations.registry.provenance import NormativeCorpusProvenance
from cadrumo.domain.calculations.registry.tests.artifact_runtime_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
    synthetic_build_receipts,
)
from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.pipeline.authority_publication import install_validated_authority_database

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUILD_IDENTITY, _COMPILER_CLOSURE = synthetic_build_receipts("fixture authority sources")
_LEGAL_ID = "ley-35-2006:art-1"


def _stage_runtime_publication(
    root: Path,
    *,
    citation_text: str,
    provenance: NormativeCorpusProvenance = NormativeCorpusProvenance.OUT_OF_SCOPE,
) -> Path:
    """Install one package-independent indexed generation."""
    artifact = AuthorityArtifact(
        modelos=(minimal_modelo(minimal_revision()),),
        catalogues=minimal_catalogues(),
        build_identity=_BUILD_IDENTITY,
        compiler_closure=_COMPILER_CLOSURE,
        identity_digest=_BUILD_IDENTITY.identity_digest,
        evidence=AuthorityEvidenceProjection(
            legal=(
                PublishedLegalEvidence(
                    legal_reference_id=_LEGAL_ID,
                    anchored_text=citation_text,
                    text_sha256=sha256_hex(citation_text.encode("utf-8")),
                    provenance=provenance,
                ),
            )
        ),
        profile_schema=compiled_bundled_authority().profile_schema(),
    )
    destination = root / "registry" / "authority"
    install_validated_authority_database(artifact, destination=destination, require_current=lambda: None)
    return destination / "authority.current.json"


def test_the_committed_bundled_descriptor_opens_the_indexed_authority() -> None:
    """The shipped descriptor admits a non-empty typed modelo directory."""
    with bundled_indexed_authority().operation() as authority:
        assert authority.modelo_ids()


def test_runtime_answers_a_citation_from_indexed_evidence_without_a_corpus_root(tmp_path: Path) -> None:
    """The runtime evidence API reads an indexed component, not package corpus files."""
    descriptor = _stage_runtime_publication(tmp_path, citation_text="validated published provision")
    authority = IndexedRegistryAuthority(descriptor)
    try:
        with authority.operation() as operation:
            assert "published provision" in operation.legal_evidence(_LEGAL_ID).anchored_text
    finally:
        authority.close()


def test_runtime_reads_indexed_provenance_without_a_corpus_tree(tmp_path: Path) -> None:
    """The runtime reads publisher-captured provenance from the indexed generation."""
    descriptor = _stage_runtime_publication(
        tmp_path,
        citation_text="validated published provision",
        provenance=NormativeCorpusProvenance.BOE_ATTESTED,
    )
    authority = IndexedRegistryAuthority(descriptor)
    try:
        with authority.operation() as operation:
            provenance = operation.legal_evidence(_LEGAL_ID).provenance
    finally:
        authority.close()

    assert provenance is NormativeCorpusProvenance.BOE_ATTESTED
