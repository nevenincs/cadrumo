"""A continuity-witnessed candidate validates against the compiled governed facts.

A generated candidate for a multi-revision modelo is validated through its
continuity witness rather than through a full authority build. That route must
still validate the target against the same compiled catalogues the authority
publishes: the governed facts are compiled from the candidate's own ``facts``
directory, so a candidate staged with them validates and a candidate missing a
migrated legal-parameter fact is refused by name.

The tests drive the real candidate staging, continuity staging and validation
over a temporary copy of the bundled registry, with no substituted component.
The staged candidate receives the published export tree in place of a fresh
render, which is the tree the generated check requires a render to reproduce.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.loader import load_modelo_directory
from ._tree_validation import GeneratedExportTreeValidationContext, _validated_target_snapshot
from .candidate_staging import stage_continuity_metadata, stage_generated_export_candidate
from .cli import _supporting_modelos
from .export_fragment_provenance import ExportFragmentTarget

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODELO = "210"
_REVISION = "2026-y-siguientes"
_FILING_YEAR = 2026
_PERIOD = "EVENT-N"
_MIGRATED_FACT_ID = "lirpf-art-101:retencion-administrador-general"
_MIGRATED_FACT_FILE = "0001-lirpf-art-101-retencion-administrador-general.toml"


def _staged_candidate(work: Path) -> tuple[Path, Path]:
    source_root = bundled_path("registry", "aeat")
    candidate_root = work / "candidate" / "registry" / "aeat"
    stage_generated_export_candidate(
        source_root,
        candidate_root,
        modelo=_MODELO,
        revision=_REVISION,
        supporting_modelos=_supporting_modelos(_MODELO),
    )
    shutil.copytree(
        source_root / "modelos" / _MODELO / "revisions" / _REVISION / "export",
        candidate_root / "modelos" / _MODELO / "revisions" / _REVISION / "export",
    )
    witness = stage_continuity_metadata(source_root / "modelos" / _MODELO, work, revision=_REVISION)
    assert witness is not None, f"modelo {_MODELO} must have sibling editions, or the continuity route is not taken"
    return candidate_root, witness


def _validate(candidate_root: Path, witness: Path) -> str:
    context = GeneratedExportTreeValidationContext(
        registry_root=candidate_root,
        source_root=bundled_path(),
        target=ExportFragmentTarget(modelo=_MODELO, revision_id=_REVISION, design_epoch="unused-by-selection"),
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        supporting_modelos=_supporting_modelos(_MODELO),
        continuity_metadata_modelo_root=witness,
        required_grade=RegistryAuthorityGrade.CALCULATION,
    )
    snapshot = _validated_target_snapshot(
        context=context,
        registry_root=candidate_root,
        source_root=bundled_path(),
        modelo_id=_MODELO,
        revision_id=_REVISION,
        target_definition=load_modelo_directory(candidate_root / "modelos" / _MODELO),
    )
    return str(snapshot.revision.id)


def test_a_continuity_witnessed_candidate_validates_with_its_staged_facts(tmp_path: Path) -> None:
    candidate_root, witness = _staged_candidate(tmp_path)
    assert (candidate_root / "facts" / _MIGRATED_FACT_FILE).is_file()

    assert _validate(candidate_root, witness) == _REVISION


def test_a_continuity_witnessed_candidate_missing_a_migrated_fact_is_refused(tmp_path: Path) -> None:
    candidate_root, witness = _staged_candidate(tmp_path)
    (candidate_root / "facts" / _MIGRATED_FACT_FILE).unlink()

    with pytest.raises(RegistryValidationError, match=f"migrated legal-parameter fact '{_MIGRATED_FACT_ID}' is not"):
        _validate(candidate_root, witness)


def test_a_continuity_witnessed_candidate_without_its_facts_directory_is_refused(tmp_path: Path) -> None:
    candidate_root, witness = _staged_candidate(tmp_path)
    shutil.rmtree(candidate_root / "facts")

    with pytest.raises(RegistryValidationError, match="migrated legal-parameter fact"):
        _validate(candidate_root, witness)
