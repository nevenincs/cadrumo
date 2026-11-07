"""Actual lineage evidence survives isolated staging without mutating siblings."""

from pathlib import Path

import pytest
import tomlkit

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_editions, revision_covering

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from ...export_clearance import prepare_export_clearance_retirement
from ..candidate_source_chain import require_source_chain_unchanged, requires_source_chain, stage_source_chain
from ..candidate_staging import stage_generated_export_candidate
from ..export_tree import render_complete_export_tree
from ..render_check import GeneratedExportBootstrapTransport, build_revision_render_inputs
from ..semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE = Path("src/cadrumo/_data/registry/aeat/modelos/194")

# The three newest editions of modelo 194: the one before the target (which restates
# nothing the target needs a chain for), the target, and the one after it.
_PRIOR_EXERCISE, _TARGET_EXERCISE, _LATER_EXERCISE = newest_authored_editions("194", 3)
_PRIOR = str(revision_covering("194", _PRIOR_EXERCISE).id)
_TARGET = str(revision_covering("194", _TARGET_EXERCISE).id)
_LATER = str(revision_covering("194", _LATER_EXERCISE).id)


@pytest.fixture
def pending_source(tmp_path: Path) -> Path:
    """Keep the prepublication case stable after the shipped target is installed."""
    root = stage_generated_export_candidate(
        _SOURCE.parents[1],
        tmp_path / "pending/registry/aeat",
        modelo="194",
        revision=_TARGET,
        supporting_modelos=(),
        retain_source_chain=True,
    )
    path = root / "revisions" / _TARGET / "revision.toml"
    document = tomlkit.parse(path.read_text("utf-8"))
    document["revisions"][_TARGET]["cleared_families"] = [
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
    assert not requires_source_chain(source.revisions[_PRIOR])
    assert requires_source_chain(source.revisions[_TARGET])
    staged = stage_source_chain(pending_source, tmp_path / "194", revision=_TARGET, include_target_export=False)
    candidate = load_modelo_directory(staged)
    assert candidate == source
    assert (staged / "revisions" / _PRIOR / "export/_generation.provenance.json").is_file()
    assert not (staged / "revisions" / _TARGET / "export").exists()
    require_source_chain_unchanged(source, candidate, revision=_TARGET)
    assert candidate.revisions[_TARGET].lineage_attestations == source.revisions[_TARGET].lineage_attestations


def test_pipeline_staging_preserves_distinct_attestations(tmp_path: Path, pending_source: Path) -> None:
    staged = stage_generated_export_candidate(
        pending_source.parents[1],
        tmp_path / "registry/aeat",
        modelo="194",
        revision=_TARGET,
        supporting_modelos=(),
        retain_source_chain=True,
    )
    require_source_chain_unchanged(
        load_modelo_directory(pending_source), load_modelo_directory(staged), revision=_TARGET
    )


@pytest.mark.parametrize("changed_revision", [_PRIOR, _TARGET, _LATER])
def test_source_chain_refuses_changed_calculation_facts(changed_revision: str, pending_source: Path) -> None:
    source = load_modelo_directory(pending_source)
    before = source.revisions[changed_revision]
    changed = before.model_copy(update={"bindings": before.bindings[:-1]})
    candidate = source.model_copy(update={"revisions": {**source.revisions, changed_revision: changed}})
    with pytest.raises(RegistryValidationError, match="protected facts"):
        require_source_chain_unchanged(source, candidate, revision=_TARGET)


def test_source_chain_refuses_removed_lineage_and_missing_siblings(pending_source: Path) -> None:
    source = load_modelo_directory(pending_source)
    changed = source.revisions[_TARGET].model_copy(update={"lineage_attestations": ()})
    candidate = source.model_copy(update={"revisions": {**source.revisions, _TARGET: changed}})
    with pytest.raises(RegistryValidationError, match="protected facts"):
        require_source_chain_unchanged(source, candidate, revision=_TARGET)
    missing = source.model_copy(update={"revisions": {_TARGET: source.revisions[_TARGET]}})
    with pytest.raises(RegistryValidationError, match="unpinned or missing"):
        require_source_chain_unchanged(source, missing, revision=_TARGET)


def _render_target(root: Path) -> None:
    mapping = load_semantic_map(Path("dev/registry/mappings/modelo_194") / _TARGET)
    inputs = build_revision_render_inputs(
        load_modelo_directory(root),
        load_shared_catalogues(_SOURCE.parents[1]),
        modelo="194",
        revision=_TARGET,
        source_ref=mapping.source_ref,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id=f"generated-modelo-194-{_TARGET}-fichero",
            line_ending="crlf",
            source_ref=mapping.source_ref,
            source_sha256=mapping.source_sha256,
        ),
        filing_year=_TARGET_EXERCISE,
        period="0A",
        source_root=Path("src/cadrumo/_data"),
    )
    render_complete_export_tree(
        root / "revisions" / _TARGET / "export",
        revision_id=_TARGET,
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
    root = stage_source_chain(pending_source, tmp_path / "194", revision=_TARGET, include_target_export=False)
    retirement = prepare_export_clearance_retirement(root, _TARGET)
    assert retirement is not None
    with pytest.raises(RegistryValidationError, match="requires the installed export"):
        retirement.install(root)
    _render_target(root)
    retirement.install(root)
    after = load_modelo_directory(root)
    assert after.revisions[_TARGET].cleared_families == ()
    require_source_chain_unchanged(source, after, revision=_TARGET)
    assert prepare_export_clearance_retirement(root, _TARGET) is None


def test_clearance_retirement_refuses_concurrent_manifest_edit(tmp_path: Path, pending_source: Path) -> None:
    root = stage_source_chain(pending_source, tmp_path / "194", revision=_TARGET, include_target_export=False)
    retirement = prepare_export_clearance_retirement(root, _TARGET)
    assert retirement is not None
    path = root / "revisions" / _TARGET / "revision.toml"
    changed = path.read_bytes() + b"\n# Concurrent edit\n"
    path.write_bytes(changed)
    with pytest.raises(RegistryValidationError, match="changed before retirement"):
        retirement.install(root)
    assert path.read_bytes() == changed


def test_clearance_retirement_refuses_legal_withdrawal(tmp_path: Path, pending_source: Path) -> None:
    root = stage_source_chain(pending_source, tmp_path / "194", revision=_TARGET, include_target_export=False)
    path = root / "revisions" / _TARGET / "revision.toml"
    path.write_bytes(path.read_bytes().replace(b"not_authored_for_this_edition", b"official_structure_withdraws"))
    with pytest.raises(RegistryValidationError, match="official export withdrawal"):
        prepare_export_clearance_retirement(root, _TARGET)
