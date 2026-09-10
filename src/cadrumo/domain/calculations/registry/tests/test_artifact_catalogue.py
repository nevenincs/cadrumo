"""Detector teeth for the bounded artifact identity compiler.

The catalog compiler deliberately receives an explicit set of bundled relative
paths.  These tests construct that boundary in a temporary ``_data`` tree and
pass only the paths the caller owns; they do not let a filesystem walk turn an
unrelated file into implicit compiler input.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path, PurePosixPath

import pytest

from ..artifact_catalogue import (
    ArtifactDisposition,
    ArtifactIdentity,
    ArtifactRole,
    DerivedArtifact,
    SemanticAnnotation,
    compile_artifact_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OFFICIAL_PATH = PurePosixPath("corpus/official/source.pdf")
_DERIVED_PATH = PurePosixPath("corpus/official/source.pdf.extracted.json")
_ANNOTATION_PATH = PurePosixPath("corpus/official/source.pdf.annotation.json")
_DISPOSITION_PATH = PurePosixPath("corpus/official/historical_exclusions.json")
_FIXTURE_PATH = PurePosixPath("tests/fixtures/synthetic-source.pdf")
_SOURCE_DIGEST = "a" * 64


def _temporary_bundled_paths(tmp_path: Path) -> tuple[PurePosixPath, ...]:
    """Create a bounded sample tree and enumerate its deliberately named members."""
    root = tmp_path / "_data"
    paths = (_OFFICIAL_PATH, _DERIVED_PATH, _ANNOTATION_PATH, _DISPOSITION_PATH, _FIXTURE_PATH)
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
