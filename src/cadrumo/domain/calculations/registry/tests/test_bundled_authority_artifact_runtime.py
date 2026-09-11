"""Runtime authority behavior at the published-artifact boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.hashing import sha256_hex
from .. import authority as authority_module
from ..authority import bundled_authority, bundled_authority_artifact_path
from ..authority_artifact import (
    AuthorityArtifact,
    AuthorityArtifactIntegrityError,
    AuthorityArtifactUnavailableError,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
    read_authority_artifact,
    write_authority_artifact,
)
from ..corpus_provenance import NormativeCorpusProvenance
from ._referential_integrity_support import _minimal_catalogues, _minimal_modelo, _minimal_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IDENTITY_DIGEST = "e4c712d347701b34615314b6e3f8fdfd75ca5ee3eabe9c1c651668549fb7f66f"


def _stage_runtime_publication(root: Path) -> Path:
    """Create a package-shaped publication without authoring inputs."""
    publication = root / "registry" / "authority"
    publication.mkdir(parents=True)
    artifact_path = publication / "authority.json"
    write_authority_artifact(
        artifact_path,
        AuthorityArtifact(
            modelos=(_minimal_modelo(_minimal_revision()),),
            catalogues=_minimal_catalogues(),
            identity_digest=_IDENTITY_DIGEST,
        ),
    )
    return artifact_path


def _use_staged_package(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Point the real package-resource seam at an isolated staged package."""
    bundled_data_root = authority_module._bundled_path()

    def staged_path(*parts: str) -> Path:
        if parts[:2] == ("registry", "authority"):
            return root.joinpath(*parts)
        return bundled_data_root.joinpath(*parts)

    monkeypatch.setattr(authority_module, "_bundled_path", staged_path)


def test_the_committed_bundled_artifact_loads_and_reads_back_canonically(tmp_path: Path) -> None:
    """The package's own artifact is the runtime authority, and it re-encodes to its exact bytes.

    Read through the real package resource with no staged seam: a product process
    loads it, and a re-publication of what was read is byte-identical, so the
    committed file is a canonical encoding of the authority it decodes to.
    """
    artifact_path = bundled_authority_artifact_path()
    authority = bundled_authority()
    consumed = read_authority_artifact(artifact_path)
    republished = tmp_path / "authority.json"

    write_authority_artifact(republished, consumed)

    assert authority.modelos, "the bundled artifact must carry the registry's modelos"
    assert {modelo.id for modelo in authority.modelos} == {modelo.id for modelo in consumed.modelos}
    assert authority.catalogues == consumed.catalogues
    assert republished.read_bytes() == artifact_path.read_bytes()


def test_runtime_uses_a_published_artifact_and_isolates_later_consumers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A product authority can snapshot a published model without its source tree."""
    _stage_runtime_publication(tmp_path)
    _use_staged_package(monkeypatch, tmp_path)

    first = bundled_authority()
    snapshot = first.snapshot("130", filing_year=2025, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY)
    capture = first.capture_law_selected_projection(
        "130",
        filing_year=2025,
        period="0A",
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    first.catalogues.legal["consumer-injected"] = next(iter(first.catalogues.legal.values()))

    later = bundled_authority()

    assert snapshot.modelo.id == "130"
    assert capture.projection.modelo.id == "130"
    capture.require_current(first.read_current_coordinate())
    assert "consumer-injected" not in later.catalogues.legal


def test_runtime_answers_a_citation_from_published_evidence_without_a_corpus_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runtime evidence API reads the artifact projection, not package corpus files."""
    artifact_path = _stage_runtime_publication(tmp_path)
    citation_text = "validated published provision"
    write_authority_artifact(
        artifact_path,
        AuthorityArtifact(
            modelos=(_minimal_modelo(_minimal_revision()),),
            catalogues=_minimal_catalogues(),
            identity_digest=_IDENTITY_DIGEST,
            evidence=AuthorityEvidenceProjection(
                legal=(
                    PublishedLegalEvidence(
                        legal_reference_id="test:art-1",
                        anchored_text=citation_text,
                        text_sha256=sha256_hex(citation_text.encode("utf-8")),
                    ),
                )
            ),
        ),
    )
    _use_staged_package(monkeypatch, tmp_path)

    authority = bundled_authority()
    authority.source_root = tmp_path / "absent-corpus"

    assert authority.legal_quotation_is_grounded("test:art-1", "published provision")


def test_runtime_keeps_real_bundled_citation_inspection_after_artifact_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The artifact authority retains its package data root for real citation inspection."""
    _stage_runtime_publication(tmp_path)
    _use_staged_package(monkeypatch, tmp_path)
    authority = bundled_authority()
    legal_id = next(iter(authority.catalogues.legal))
    authority.catalogues.legal[legal_id] = authority.catalogues.legal[legal_id].model_copy(
        update={"corpus_ref": "corpus/normatives/html/ley-35-2006-art-85.html#a85"}
    )

    provenance = authority.legal_corpus_provenance(legal_id)

    assert provenance is NormativeCorpusProvenance.BOE_ATTESTED


def test_missing_publication_refuses_before_any_authoring_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An absent runtime artifact fails even when a malformed authoring tree is nearby."""
    malformed_authoring_tree = tmp_path / "registry" / "aeat"
    malformed_authoring_tree.mkdir(parents=True)
    (malformed_authoring_tree / "catalogue.toml").write_text("this is not valid registry input", encoding="utf-8")
    _use_staged_package(monkeypatch, tmp_path)

    with pytest.raises(AuthorityArtifactUnavailableError):
        bundled_authority()


def test_corrupt_publication_refuses_before_any_authoring_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tampering is refused at the artifact boundary, not repaired from nearby sources."""
    artifact_path = _stage_runtime_publication(tmp_path)
    artifact_path.write_bytes(artifact_path.read_bytes().replace(_IDENTITY_DIGEST.encode(), b"0" * 64, 1))
    malformed_authoring_tree = tmp_path / "registry" / "aeat"
    malformed_authoring_tree.mkdir(parents=True)
    (malformed_authoring_tree / "catalogue.toml").write_text("this is not valid registry input", encoding="utf-8")
    _use_staged_package(monkeypatch, tmp_path)

    with pytest.raises(AuthorityArtifactIntegrityError):
        bundled_authority()
