"""Detector teeth for the bounded artifact identity compiler.

The catalog compiler deliberately receives an explicit set of bundled relative
paths.  These tests construct that boundary in a temporary ``_data`` tree and
pass only the paths the caller owns; they do not let a filesystem walk turn an
unrelated file into implicit compiler input.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path, PurePosixPath

import pytest
from test_support.registry_authoring import RegistryValidator, load_registry_tree

from .....core.resources.bundled_data import bundled_path
from ..artifact_catalogue import (
    ArtifactDiagnosticKind,
    ArtifactDisposition,
    ArtifactIdentity,
    ArtifactIdentityInput,
    ArtifactRole,
    DerivedArtifact,
    SemanticAnnotation,
    compile_artifact_catalogue,
)
from ..errors import RegistryValidationError
from ..facts.schema import GovernedFactCatalogue
from ..schema import RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OFFICIAL_PATH = PurePosixPath("corpus/official/source.pdf")
_DERIVED_PATH = PurePosixPath("corpus/official/source.pdf.extracted.json")
_ANNOTATION_PATH = PurePosixPath("corpus/official/source.pdf.annotation.json")
_DISPOSITION_PATH = PurePosixPath("corpus/official/historical_exclusions.json")
_FIXTURE_PATH = PurePosixPath("tests/fixtures/synthetic-source.pdf")
_UNCLASSIFIED_PATH = PurePosixPath("corpus/official/unclassified.txt")
_SOURCE_DIGEST = "a" * 64


def _temporary_bundled_paths(tmp_path: Path, *additional_paths: PurePosixPath) -> tuple[PurePosixPath, ...]:
    """Create a bounded sample tree and enumerate its deliberately named members."""
    root = tmp_path / "_data"
    paths = (
        _OFFICIAL_PATH,
        _DERIVED_PATH,
        _ANNOTATION_PATH,
        _DISPOSITION_PATH,
        _FIXTURE_PATH,
        *additional_paths,
    )
    for relative_path in paths:
        file_path = root.joinpath(*relative_path.parts)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("test artifact\n", encoding="utf-8")
    return tuple(
        PurePosixPath(file_path.relative_to(root).as_posix())
        for file_path in sorted(root.rglob("*"))
        if file_path.is_file()
    )


def test_compiler_assigns_exactly_one_declared_role_to_every_bounded_temp_artifact(tmp_path: Path) -> None:
    """Normal compilation preserves each role without reading beyond its boundary."""
    known_paths = _temporary_bundled_paths(tmp_path)
    official = ArtifactIdentity(
        path=_OFFICIAL_PATH,
        sha256=_SOURCE_DIGEST,
        bytes=14,
        source_url="https://www.example.test/official/source.pdf",
        publisher="Example authority",
        retrieved_at=date(2026, 9, 10),
    )

    catalogue = compile_artifact_catalogue(
        known_paths=known_paths,
        official_identities=(official,),
        derived_artifacts=(
            DerivedArtifact(
                path=_DERIVED_PATH,
                input_path=_OFFICIAL_PATH,
                input_sha256=_SOURCE_DIGEST,
                producer="tests.artifact_catalogue",
            ),
        ),
        semantic_annotations=(SemanticAnnotation(path=_ANNOTATION_PATH, target_path=_OFFICIAL_PATH),),
        dispositions=(
            ArtifactDisposition(
                declaration_path=_DISPOSITION_PATH,
                target_path=_OFFICIAL_PATH,
                reason="historical acquisition is outside the supported window",
            ),
        ),
        fixture_paths=(_FIXTURE_PATH,),
    )

    assert catalogue.diagnostics == ()
    assert catalogue.identities == {_OFFICIAL_PATH: official}
    assert catalogue.roles == {
        _OFFICIAL_PATH: ArtifactRole.OFFICIAL_ARTIFACT,
        _DERIVED_PATH: ArtifactRole.DERIVED_ARTIFACT,
        _ANNOTATION_PATH: ArtifactRole.SEMANTIC_ANNOTATION,
        _DISPOSITION_PATH: ArtifactRole.DISPOSITION,
        _FIXTURE_PATH: ArtifactRole.FIXTURE,
    }
    assert set(catalogue.roles) == set(known_paths)


def test_compiler_reports_distinct_conflict_orphan_and_unknown_file_diagnostics(tmp_path: Path) -> None:
    """Independent bad claims remain typed findings rather than a coverage boolean."""
    known_paths = _temporary_bundled_paths(tmp_path, _UNCLASSIFIED_PATH)
    official = ArtifactIdentity(
        path=_OFFICIAL_PATH,
        sha256=_SOURCE_DIGEST,
        bytes=14,
        source_url="https://www.example.test/official/source.pdf",
        publisher="Example authority",
        retrieved_at=date(2026, 9, 10),
    )
    conflicting_official = ArtifactIdentity(
        path=_OFFICIAL_PATH,
        sha256="b" * 64,
        bytes=14,
        source_url="https://www.example.test/official/source.pdf",
        publisher="Example authority",
        retrieved_at=date(2026, 9, 10),
    )

    catalogue = compile_artifact_catalogue(
        known_paths=known_paths,
        official_identities=(official, conflicting_official),
        derived_artifacts=(
            DerivedArtifact(
                path=_DERIVED_PATH,
                input_path=_OFFICIAL_PATH,
                input_sha256=_SOURCE_DIGEST,
                producer="tests.artifact_catalogue",
            ),
        ),
        semantic_annotations=(
            SemanticAnnotation(
                path=_ANNOTATION_PATH,
                target_path=PurePosixPath("corpus/official/missing-source.pdf"),
            ),
        ),
        dispositions=(
            ArtifactDisposition(
                declaration_path=_DISPOSITION_PATH,
                target_path=_OFFICIAL_PATH,
                reason="historical acquisition is outside the supported window",
            ),
        ),
        fixture_paths=(_FIXTURE_PATH,),
    )

    assert {(diagnostic.kind, diagnostic.path) for diagnostic in catalogue.diagnostics} == {
        (ArtifactDiagnosticKind.CONFLICTING_IDENTITY, _OFFICIAL_PATH),
        (ArtifactDiagnosticKind.ORPHANED_TARGET, _ANNOTATION_PATH),
        (ArtifactDiagnosticKind.UNKNOWN_FILE, _UNCLASSIFIED_PATH),
    }
    assert catalogue.roles[_OFFICIAL_PATH] is ArtifactRole.OFFICIAL_ARTIFACT
    assert _UNCLASSIFIED_PATH not in catalogue.roles


def test_compiler_reports_a_malformed_official_identity_claim(tmp_path: Path) -> None:
    """Malformed source claims remain typed findings at the public compiler boundary."""
    catalogue = compile_artifact_catalogue(
        known_paths=_temporary_bundled_paths(tmp_path),
        official_identities=(
            ArtifactIdentityInput(
                path=_OFFICIAL_PATH,
                sha256="not-a-sha256",
                bytes=14,
                source_url="https://www.example.test/official/source.pdf",
                publisher="Example authority",
                retrieved_at=date(2026, 9, 10),
            ),
        ),
    )

    assert (ArtifactDiagnosticKind.MALFORMED_IDENTITY, _OFFICIAL_PATH) in {
        (diagnostic.kind, diagnostic.path) for diagnostic in catalogue.diagnostics
    }
    assert _OFFICIAL_PATH not in catalogue.roles


def test_compiler_reports_a_raw_claim_with_an_invalid_retrieval_date(tmp_path: Path) -> None:
    """Raw claim validation refuses a timestamp in place of a plain date."""
    catalogue = compile_artifact_catalogue(
        known_paths=_temporary_bundled_paths(tmp_path),
        official_identities=(
            ArtifactIdentityInput(
                path=_OFFICIAL_PATH,
                sha256=_SOURCE_DIGEST,
                bytes=14,
                source_url="https://www.example.test/official/source.pdf",
                publisher="Example authority",
                retrieved_at=datetime(2026, 9, 10, 12, 0),
            ),
        ),
    )

    assert (ArtifactDiagnosticKind.MALFORMED_IDENTITY, _OFFICIAL_PATH) in {
        (diagnostic.kind, diagnostic.path) for diagnostic in catalogue.diagnostics
    }
    assert _OFFICIAL_PATH not in catalogue.roles


def test_identity_model_still_rejects_malformed_values_at_construction() -> None:
    """The raw compiler route does not weaken direct identity construction."""
    with pytest.raises(ValueError, match="sha256"):
        ArtifactIdentity(
            path=_OFFICIAL_PATH,
            sha256="not-a-sha256",
            bytes=14,
            source_url="https://www.example.test/official/source.pdf",
            publisher="Example authority",
            retrieved_at=date(2026, 9, 10),
        )


def test_compiler_reports_a_derivative_when_its_input_digest_has_changed(tmp_path: Path) -> None:
    """A derivative is stale when its recorded input no longer has the official digest."""
    official = ArtifactIdentity(
        path=_OFFICIAL_PATH,
        sha256=_SOURCE_DIGEST,
        bytes=14,
        source_url="https://www.example.test/official/source.pdf",
        publisher="Example authority",
        retrieved_at=date(2026, 9, 10),
    )

    catalogue = compile_artifact_catalogue(
        known_paths=_temporary_bundled_paths(tmp_path),
        official_identities=(official,),
        derived_artifacts=(
            DerivedArtifact(
                path=_DERIVED_PATH,
                input_path=_OFFICIAL_PATH,
                input_sha256="b" * 64,
                producer="tests.artifact_catalogue",
            ),
        ),
        semantic_annotations=(SemanticAnnotation(path=_ANNOTATION_PATH, target_path=_OFFICIAL_PATH),),
        dispositions=(
            ArtifactDisposition(
                declaration_path=_DISPOSITION_PATH,
                target_path=_OFFICIAL_PATH,
                reason="historical acquisition is outside the supported window",
            ),
        ),
        fixture_paths=(_FIXTURE_PATH,),
    )

    assert {(diagnostic.kind, diagnostic.path) for diagnostic in catalogue.diagnostics} == {
        (ArtifactDiagnosticKind.STALE_DERIVATIVE, _DERIVED_PATH),
    }


def test_compiler_reports_a_registry_identity_that_diverges_from_catalogue(tmp_path: Path) -> None:
    """A registry projection must bind the exact catalog byte identity, not a similar source."""
    official = ArtifactIdentity(
        path=_OFFICIAL_PATH,
        sha256=_SOURCE_DIGEST,
        bytes=14,
        source_url="https://www.example.test/official/source.pdf",
        publisher="Example authority",
        retrieved_at=date(2026, 9, 10),
    )
    divergent_registry_identity = ArtifactIdentity(
        path=_OFFICIAL_PATH,
        sha256="b" * 64,
        bytes=14,
        source_url="https://www.example.test/official/source.pdf",
        publisher="Example authority",
        retrieved_at=date(2026, 9, 10),
    )

    catalogue = compile_artifact_catalogue(
        known_paths=_temporary_bundled_paths(tmp_path),
        official_identities=(official,),
        derived_artifacts=(
            DerivedArtifact(
                path=_DERIVED_PATH,
                input_path=_OFFICIAL_PATH,
                input_sha256=_SOURCE_DIGEST,
                producer="tests.artifact_catalogue",
            ),
        ),
        semantic_annotations=(SemanticAnnotation(path=_ANNOTATION_PATH, target_path=_OFFICIAL_PATH),),
        dispositions=(
            ArtifactDisposition(
                declaration_path=_DISPOSITION_PATH,
                target_path=_OFFICIAL_PATH,
                reason="historical acquisition is outside the supported window",
            ),
        ),
        fixture_paths=(_FIXTURE_PATH,),
        registry_identities=(divergent_registry_identity,),
    )

    assert {(diagnostic.kind, diagnostic.path) for diagnostic in catalogue.diagnostics} == {
        (ArtifactDiagnosticKind.BROKEN_REGISTRY_BINDING, _OFFICIAL_PATH),
    }


def test_registry_validator_rejects_a_conflicting_record_design_manifest_identity(tmp_path: Path) -> None:
    """The live validator must not let a first matching manifest row hide a conflict."""
    _modelos, committed_catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    source = next(
        source
        for source in committed_catalogues.sources.values()
        if source.corpus_path.startswith("corpus/aeat_official/disenos_registro/")
    )
    payload = b"official record design"
    source = source.model_copy(
        update={
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
    )
    parts = PurePosixPath(source.corpus_path).parts
    manifest_path = tmp_path.joinpath(*parts[:4], "manifest.json")
    manifest_path.parent.mkdir(parents=True)
    stored_path = PurePosixPath(*parts[4:]).as_posix()
    manifest_path.write_text(
        json.dumps(
            {
                "source": "AEAT",
                "retrieved_at": "2026-09-10",
                "artefacts": [
                    {
                        "stored_path": stored_path,
                        "sha256": source.sha256,
                        "bytes": source.bytes,
                        "url": source.source_url,
                    },
                    {
                        "stored_path": stored_path,
                        "sha256": "f" * 64,
                        "bytes": source.bytes,
                        "url": source.source_url,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    catalogues = RegistryCatalogues(
        legal={},
        sources={source.id: source},
        facts=GovernedFactCatalogue(),
    )

    with pytest.raises(RegistryValidationError, match="conflicting_identity"):
        RegistryValidator(catalogues, source_root=tmp_path).validate_registry(())
