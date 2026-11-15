"""The generated-revision verifier compares through the canonical joiner's compiled semantic map.

An authored map may spell a numeric casilla without its leading zeroes; the
canonical joiner pads it to the unique declared id and the pipeline generates
the export tree from that compiled map. The verifier must admit such a tree,
and must still refuse an authored map that attests different casillas.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ..diagnostic_classification import RegistryDiagnosticFilingRevision, derive_filing_revision_classifications
from ..filing_export_generated_verification import ConformanceGenerationEntry, verify_generated_revision
from ..pipeline.export_fragment_provenance import (
    ExportFragmentProvenanceManifest,
    load_export_fragment_provenance_manifest,
)
from ..pipeline.export_fragment_provenance_projection import semantic_map_digest
from ..pipeline.semantic_map import load_semantic_map_for_revision

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "200"
_REGISTRY_ROOT = bundled_path("registry", "aeat")
_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
_UNPADDED_CASILLA = re.compile(r'^casilla_id = "([1-9][0-9]*)"$', re.MULTILINE)


def _manifest(revision: RegistryDiagnosticFilingRevision) -> ExportFragmentProvenanceManifest:
    path = (
        _REGISTRY_ROOT
        / "modelos"
        / str(revision.modelo)
        / "revisions"
        / str(revision.revision)
        / "export"
        / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    )
    return load_export_fragment_provenance_manifest(path.read_bytes())


def _mapping_epoch(workspace_root: Path, manifest: ExportFragmentProvenanceManifest) -> Path:
    return workspace_root / "dev/registry/mappings" / f"modelo_{manifest.modelo}" / manifest.design_epoch


def _padded_revision(authority: ValidatedRegistryAuthority) -> RegistryDiagnosticFilingRevision:
    """Select a filing revision of the modelo whose committed tree was generated from a padded map.

    The manifest digests the compiled map the tree was generated from, so an
    authored map whose digest differs is one the joiner rewrote.
    """
    for revision in derive_filing_revision_classifications(authority):
        if str(revision.modelo) != _MODELO or revision.refusal_reason is not None:
            continue
        manifest = _manifest(revision)
        semantic_map = load_semantic_map_for_revision(_mapping_epoch(_WORKSPACE_ROOT, manifest), revision.revision)
        if semantic_map_digest(semantic_map) != manifest.semantic_map_sha256:
            return revision
    raise AssertionError(f"no filing revision of modelo {_MODELO} has an authored map the joiner pads")


def _verify(
    authority: ValidatedRegistryAuthority,
    revision: RegistryDiagnosticFilingRevision,
    *,
    workspace_root: Path,
) -> None:
    assert revision.layout_json is not None
    assert revision.inspection is not None
    verify_generated_revision(
        workspace_root=workspace_root,
        registry_root=_REGISTRY_ROOT,
        source_root=bundled_path(),
        authority=authority,
        inspection=revision.inspection,
        entry=ConformanceGenerationEntry(
            modelo=revision.modelo,
            revision=revision.revision,
            design_epoch=_manifest(revision).design_epoch,
            filing_year=revision.selection_coordinates[0][0],
        ),
        layout=ExportLayoutDefinition.model_validate_json(revision.layout_json),
    )


def _swap_two_unpadded_casillas(epoch: Path) -> None:
    """Exchange the casilla ids of two entries, so each names another declared casilla."""
    for fragment in sorted(epoch.rglob("*.toml")):
        text = fragment.read_text(encoding="utf-8")
        matches = list(_UNPADDED_CASILLA.finditer(text))
        distinct = [match for match in matches if match.group(1) != matches[0].group(1)] if matches else []
        if not distinct:
            continue
        first, second = matches[0], distinct[0]
        swapped = (
            text[: first.start(1)]
            + second.group(1)
            + text[first.end(1) : second.start(1)]
            + first.group(1)
            + text[second.end(1) :]
        )
        fragment.write_bytes(swapped.encode("utf-8"))
        return
    raise AssertionError("no mapping fragment carries two distinct unpadded casilla ids")


def test_a_tree_generated_from_a_padded_map_is_admitted(registry_authority: ValidatedRegistryAuthority) -> None:
    _verify(registry_authority, _padded_revision(registry_authority), workspace_root=_WORKSPACE_ROOT)


def test_an_authored_map_attesting_other_casillas_is_refused(
    tmp_path: Path,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    revision = _padded_revision(registry_authority)
    manifest = _manifest(revision)
    for tree in ("mappings", "render_profiles"):
        relative = Path("dev/registry") / tree / f"modelo_{manifest.modelo}" / manifest.design_epoch
        shutil.copytree(_WORKSPACE_ROOT / relative, tmp_path / relative)
    _swap_two_unpadded_casillas(_mapping_epoch(tmp_path, manifest))

    with pytest.raises(RegistryValidationError, match="semantic_map_sha256"):
        _verify(registry_authority, revision, workspace_root=tmp_path)
