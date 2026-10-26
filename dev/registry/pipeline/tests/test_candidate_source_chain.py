"""Actual lineage evidence survives isolated staging without mutating siblings."""

from pathlib import Path

import pytest
import tomlkit

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from ...export_clearance import prepare_export_clearance_retirement
from .._export_tree import render_complete_export_tree
from ..candidate_source_chain import require_source_chain_unchanged, requires_source_chain, stage_source_chain
from ..candidate_staging import stage_generated_export_candidate
from ..render_check import GeneratedExportBootstrapTransport, _revision_render_inputs
from ..semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE = Path("src/cadrumo/_data/registry/aeat/modelos/194")


@pytest.fixture
def pending_source(tmp_path: Path) -> Path:
    """Keep the prepublication case stable after the shipped target is installed."""
    root = stage_generated_export_candidate(
        _SOURCE.parents[1],
        tmp_path / "pending/registry/aeat",
        modelo="194",
        revision="2023",
        supporting_modelos=(),
        retain_source_chain=True,
    )
    path = root / "revisions/2023/revision.toml"
    document = tomlkit.parse(path.read_text("utf-8"))
    document["revisions"]["2023"]["cleared_families"] = [
        {
            "family": "export_layouts",
            "cause": "not_authored_for_this_edition",
            "reason": "Isolated first-publication fixture awaits its own generated export.",
        }
    ]
    path.write_text(tomlkit.dumps(document), encoding="utf-8")
    return root


def test_distinct_lineage_evidence_retains_the_real_revision_chain(tmp_path: Path, pending_source: Path) -> None:
    source = load_modelo_directory(pending_source)
    assert not requires_source_chain(source.revisions["2019"])
    assert requires_source_chain(source.revisions["2023"])
    staged = stage_source_chain(pending_source, tmp_path / "194", revision="2023", include_target_export=False)
    candidate = load_modelo_directory(staged)
    assert candidate == source
    assert (staged / "revisions/2019/export/_generation.provenance.json").is_file()
    assert not (staged / "revisions/2023/export").exists()
    require_source_chain_unchanged(source, candidate, revision="2023")
    assert candidate.revisions["2023"].lineage_attestations == source.revisions["2023"].lineage_attestations


def test_pipeline_staging_preserves_distinct_attestations(tmp_path: Path, pending_source: Path) -> None:
    staged = stage_generated_export_candidate(
        pending_source.parents[1],
        tmp_path / "registry/aeat",
        modelo="194",
        revision="2023",
        supporting_modelos=(),
        retain_source_chain=True,
    )
    require_source_chain_unchanged(
        load_modelo_directory(pending_source), load_modelo_directory(staged), revision="2023"
    )


@pytest.mark.parametrize("changed_revision", ["2019", "2023", "2024"])
def test_source_chain_refuses_changed_calculation_facts(changed_revision: str, pending_source: Path) -> None:
    source = load_modelo_directory(pending_source)
    before = source.revisions[changed_revision]
    changed = before.model_copy(update={"bindings": before.bindings[:-1]})
    candidate = source.model_copy(update={"revisions": {**source.revisions, changed_revision: changed}})
    with pytest.raises(RegistryValidationError, match="protected facts"):
        require_source_chain_unchanged(source, candidate, revision="2023")


def test_source_chain_refuses_removed_lineage_and_missing_siblings(pending_source: Path) -> None:
    source = load_modelo_directory(pending_source)
    changed = source.revisions["2023"].model_copy(update={"lineage_attestations": ()})
    candidate = source.model_copy(update={"revisions": {**source.revisions, "2023": changed}})
    with pytest.raises(RegistryValidationError, match="protected facts"):
        require_source_chain_unchanged(source, candidate, revision="2023")
    missing = source.model_copy(update={"revisions": {"2023": source.revisions["2023"]}})
    with pytest.raises(RegistryValidationError, match="unpinned or missing"):
        require_source_chain_unchanged(source, missing, revision="2023")


def _render_2023(root: Path) -> None:
    mapping = load_semantic_map(Path("dev/registry/mappings/modelo_194/2023"))
    inputs = _revision_render_inputs(
        load_modelo_directory(root),
        load_shared_catalogues(_SOURCE.parents[1]),
        modelo="194",
        revision="2023",
        source_ref=mapping.source_ref,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id="generated-modelo-194-2023-fichero",
            line_ending="crlf",
            source_ref=mapping.source_ref,
            source_sha256=mapping.source_sha256,
        ),
        filing_year=2023,
        period="0A",
        source_root=Path("src/cadrumo/_data"),
    )
    render_complete_export_tree(
        root / "revisions/2023/export",
        revision_id="2023",
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )


def test_clearance_retirement_requires_real_export_and_preserves_every_other_fact(
    tmp_path: Path, pending_source: Path
) -> None:
    source = load_modelo_directory(pending_source)
    root = stage_source_chain(pending_source, tmp_path / "194", revision="2023", include_target_export=False)
    retirement = prepare_export_clearance_retirement(root, "2023")
    assert retirement is not None
    with pytest.raises(RegistryValidationError, match="requires the installed export"):
        retirement.install(root)
    _render_2023(root)
    retirement.install(root)
    after = load_modelo_directory(root)
    assert after.revisions["2023"].cleared_families == ()
    require_source_chain_unchanged(source, after, revision="2023")
    assert prepare_export_clearance_retirement(root, "2023") is None


def test_clearance_retirement_refuses_concurrent_manifest_edit(tmp_path: Path, pending_source: Path) -> None:
    root = stage_source_chain(pending_source, tmp_path / "194", revision="2023", include_target_export=False)
    retirement = prepare_export_clearance_retirement(root, "2023")
    assert retirement is not None
    path = root / "revisions/2023/revision.toml"
    changed = path.read_bytes() + b"\n# Concurrent edit\n"
    path.write_bytes(changed)
    with pytest.raises(RegistryValidationError, match="changed before retirement"):
        retirement.install(root)
    assert path.read_bytes() == changed


def test_clearance_retirement_refuses_legal_withdrawal(tmp_path: Path, pending_source: Path) -> None:
    root = stage_source_chain(pending_source, tmp_path / "194", revision="2023", include_target_export=False)
    path = root / "revisions/2023/revision.toml"
    path.write_bytes(path.read_bytes().replace(b"not_authored_for_this_edition", b"official_structure_withdraws"))
    with pytest.raises(RegistryValidationError, match="official export withdrawal"):
        prepare_export_clearance_retirement(root, "2023")
