"""A generated child may store an empty keyed delta only with exact baseline proof."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import replace
from functools import partial
from pathlib import Path

import pytest

from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import SourceRefId
from cadrumo.domain.calculations.registry.static_inspection import GeneratedArtifactSource

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_modelo_directory
from ...edition_delta_assessment import assess_migration_state
from ...edition_delta_chain_materialisation import chain_materialisation, member_identities
from ...edition_delta_migration import migrate_modelo
from ...edition_delta_proof_source import read_staged_edition
from .. import _tree_publication as tree_publication
from .. import cli as pipeline_cli
from .._export_tree import render_complete_export_tree
from .._tree_publication import publish_validated_generated_export_tree
from .._tree_validation import _require_isolated_target_context, validate_generated_export_tree
from ..bootstrap_supersession import bootstrap_layout_supersession_fingerprint
from ..candidate_source_chain import require_source_chain_unchanged
from ..candidate_staging import stage_attested_inherited_modelo
from ..cli import (
    GeneratedTreeInvocation,
    _render_candidate,
    _require_storage_equivalent_republication,
    check_prepared_invocation,
    prepare_generated_tree_invocation,
    publish_prepared_invocation,
)
from ..export_fragment_provenance import (
    ExportFragmentProvenanceManifest,
    ExportFragmentTarget,
    verify_export_fragment_provenance_manifest,
)
from ..export_tree_serialization import render_toml_bytes
from ..generated_export_inheritance import (
    generated_export_source_chain_fingerprint,
    require_generated_export_inheritance,
    select_generated_export_inheritance,
    verify_generated_export_inheritance_storage,
)
from ..render_check import compare_export_tree_roots, compare_revision_against_committed, revision_render_inputs
from ..source_defects import source_defects_for
from ..tree_publication_artifacts import stage_verified_candidate_package, verify_generated_export_package
from ..tree_publication_contracts import (
    GeneratedExportPublicationJournal,
    GeneratedExportSupersession,
    GeneratedExportTransactionPaths,
    GeneratedExportTreePublicationContext,
    GeneratedExportTreeTargetStateReceipt,
    PublishedGeneratedExportTree,
    export_provenance_file_sha256,
)
from ..tree_publication_journal import write_generated_export_publication_journal

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_static_storage_verification_refuses_a_changed_earlier_ancestor(tmp_path: Path) -> None:
    """Degraded provenance retains intact chains and refuses a changed physical parent."""
    authority = compiled_bundled_authority()
    registry_root = bundled_path("registry", "aeat")
    context = select_generated_export_inheritance(authority, registry_root, modelo="189", revision="2025")
    assert context is not None and context.baseline_context is not None
    selected = authority.modelo("189").revisions["2025"]
    sources: Mapping[SourceRefId, GeneratedArtifactSource] = dict(authority.catalogues.sources)
    candidate_root = tmp_path / "registry"
    shutil.copytree(registry_root / "modelos/189", candidate_root / "modelos/189")
    verify_generated_export_inheritance_storage(
        context.attestation, candidate_root, modelo="189", effective_layout=selected.export_layouts[0], sources=sources
    )
    ancestor_id = context.baseline_context.attestation.baseline_revision_id
    ancestor = candidate_root / "modelos/189/revisions" / str(ancestor_id) / "revision.toml"
    ancestor.write_bytes(ancestor.read_bytes() + b"\n# modified storage ancestor\n")
    with pytest.raises(RegistryValidationError, match="baseline pins"):
        verify_generated_export_inheritance_storage(
            context.attestation,
            candidate_root,
            modelo="189",
            effective_layout=selected.export_layouts[0],
            sources=sources,
        )


def _prepared(tmp_path: Path, *, revision: str = "2025"):
    authority = compiled_bundled_authority()
    prepared = prepare_generated_tree_invocation(
        GeneratedTreeInvocation("189", revision, "aeat-dr-189-2023", int(revision), "0A"),
        tmp_path,
        authority=authority,
    )
    assert prepared.inheritance is not None
    return prepared, authority


def _full_witness(prepared, root: Path) -> Path:
    """Independently reproduce the old complete source tree in isolation."""
    render_complete_export_tree(
        root,
        revision_id=prepared.inputs.revision_id,
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        transport_profile=prepared.inputs.transport_profile,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        source_defects=source_defects_for(prepared.invocation.source_ref),
    )
    return root


def test_ordinary_full_revision_with_continuity_evolutions_does_not_select_compaction() -> None:
    """An unrelated evolution must not block a distinct complete export layout."""
    authority = compiled_bundled_authority()
    registry_root = bundled_path("registry", "aeat")
    modelo_root = registry_root / "modelos/390"
    revision = authority.modelo("390").revisions["2023"]
    baseline = authority.modelo("390").revisions[str(revision.family_storage_baseline)]
    assert revision.export_layouts != baseline.export_layouts
    assert (modelo_root / "revisions/2023/casilla_continuidad_evolutions").exists()
    assert select_generated_export_inheritance(authority, registry_root, modelo="390", revision="2023") is None


@pytest.mark.parametrize("evolution_revision", ["2024", "2025"])
def test_equal_layout_with_continuity_evolutions_declines_optional_compaction(
    tmp_path: Path, evolution_revision: str
) -> None:
    """Either side is ineligible, while an already required attestation still refuses."""
    authority = compiled_bundled_authority()
    registry_root = tmp_path / "registry"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", "189"), registry_root / "modelos/189")
    expected = select_generated_export_inheritance(authority, registry_root, modelo="189", revision="2025")
    assert expected is not None
    definition = authority.modelo("189")
    assert definition.revisions["2025"].export_layouts == definition.revisions["2024"].export_layouts
    evolution_root = registry_root / "modelos/189/revisions" / evolution_revision / "casilla_continuidad_evolutions"
    assert not evolution_root.exists()
    evolution_root.mkdir()

    assert select_generated_export_inheritance(authority, registry_root, modelo="189", revision="2025") is None
    with pytest.raises(
        RegistryValidationError, match=f"cannot detach a revision with continuity evolutions: 189/{evolution_revision}"
    ):
        require_generated_export_inheritance(expected, authority, registry_root, modelo="189", revision="2025")


def test_early_2026_m303_renders_a_complete_tree_without_detaching_baseline_evolutions(tmp_path: Path) -> None:
    """The real January/Q1 edition keeps its 2026 record and the baseline's legal history."""
    authority = compiled_bundled_authority()
    registry_root = tmp_path / "registry"

    def omit_target_export(directory: str, names: list[str]) -> set[str]:
        """Recreate only the child's first-publication state in a separate scratch copy."""
        return {"export"}.intersection(names) if Path(directory).name == "2026-hasta-01-y-1t" else set()

    shutil.copytree(
        bundled_path("registry", "aeat", "modelos", "303"),
        registry_root / "modelos/303",
        ignore=omit_target_export,
    )
    definition = authority.modelo("303")
    selected = definition.revisions["2026-hasta-01-y-1t"]
    baseline = definition.revisions[str(selected.family_storage_baseline)]
    evolutions = baseline.casilla_continuidad_evolutions
    assert evolutions
    assert selected.export_layouts == baseline.export_layouts
    assert (registry_root / "modelos/303/revisions" / str(baseline.id) / "casilla_continuidad_evolutions").is_dir()
    assert (
        select_generated_export_inheritance(authority, registry_root, modelo="303", revision=str(selected.id)) is None
    )

    inputs = revision_render_inputs(
        authority, modelo="303", revision=str(selected.id), source_ref="aeat-dr-303-2026", filing_year=2026, period="1T"
    )
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
        source_defects=source_defects_for("aeat-dr-303-2026"),
    )
    assert rendered.layout == selected.export_layouts[0]
    assert len(rendered.output_files) > 1
    assert rendered.provenance_manifest.generated_export_inheritance is None
    assert authority.modelo("303").revisions[str(baseline.id)].casilla_continuidad_evolutions == evolutions

    comparison = compare_revision_against_committed(
        authority,
        modelo="303",
        revision=str(selected.id),
        source_ref="aeat-dr-303-2026",
        filing_year=2026,
        period="1T",
        registry_root=registry_root,
    )
    assert comparison.layout_id == str(rendered.layout.id)
    assert comparison.only_rendered
    assert not comparison.reproduced


def test_real_2024_child_candidate_can_replace_its_full_tree(tmp_path: Path) -> None:
    prepared, authority = _prepared(tmp_path, revision="2024")
    assert prepared.inheritance is not None
    assert prepared.inheritance.pinned_ancestors[0][0] == "2023"
    rendered = _render_candidate(prepared)
    validated = validate_generated_export_tree(
        context=prepared.validation,
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        rendered=rendered,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
    )
    assert validated.layout == authority.modelo("189").revisions["2024"].export_layouts[0]
    full_root = _full_witness(prepared, tmp_path / "full-2024-witness" / "export")
    state = GeneratedExportTreeTargetStateReceipt.observe(full_root)
    assert state.manifest_sha256 is not None
    bound = replace(
        prepared,
        target_export_root=full_root,
        invocation=replace(prepared.invocation, expected_manifest_sha256=state.manifest_sha256),
    )
    comparison = compare_export_tree_roots(
        modelo="189",
        revision="2024",
        layout_id=prepared.inputs.layout_id,
        committed_root=full_root,
        rendered_root=prepared.candidate_root / "modelos/189/revisions/2024/export",
    )
    assert comparison.disposition_class == "record_drift"
    _require_storage_equivalent_republication(bound, rendered, state, comparison)


def test_recursive_child_chain_requires_every_pinned_ancestor(tmp_path: Path) -> None:
    authority = compiled_bundled_authority()
    source_root = tmp_path / "compact-source" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", "189"), source_root / "modelos/189")
    prior = select_generated_export_inheritance(
        authority,
        source_root,
        modelo="189",
        revision="2024",
    )
    assert prior is not None and tuple(item[0] for item in prior.pinned_ancestors) == ("2023",)
    source_2024_export = source_root / "modelos/189/revisions/2024/export"
    source_2024_export.rename(tmp_path / "old-2024-export")
    inputs_2024 = revision_render_inputs(
        authority,
        modelo="189",
        revision="2024",
        source_ref="aeat-dr-189-2023",
        filing_year=2024,
        period="0A",
    )
    render_complete_export_tree(
        source_2024_export,
        revision_id=inputs_2024.revision_id,
        joined=inputs_2024.joined,
        semantic_map=inputs_2024.semantic_map,
        transport_profile=inputs_2024.transport_profile,
        render_profile=inputs_2024.render_profile,
        render_profile_source_evidence=inputs_2024.render_profile_source_evidence,
        source_defects=source_defects_for("aeat-dr-189-2023"),
        inheritance=prior,
    )
    chain = select_generated_export_inheritance(
        authority,
        source_root,
        modelo="189",
        revision="2025",
    )
    assert chain is not None and tuple(item[0] for item in chain.pinned_ancestors) == ("2023", "2024")
    candidate_root = tmp_path / "chain-candidate" / "aeat"
    staged_root = stage_attested_inherited_modelo(
        source_root / "modelos/189",
        candidate_root / "modelos/189",
        revision="2025",
        inheritance=chain,
        include_target_export=False,
    )
    inputs_2025 = revision_render_inputs(
        authority,
        modelo="189",
        revision="2025",
        source_ref="aeat-dr-189-2023",
        filing_year=2025,
        period="0A",
    )
    rendered = render_complete_export_tree(
        staged_root / "revisions/2025/export",
        revision_id=inputs_2025.revision_id,
        joined=inputs_2025.joined,
        semantic_map=inputs_2025.semantic_map,
        transport_profile=inputs_2025.transport_profile,
        render_profile=inputs_2025.render_profile,
        render_profile_source_evidence=inputs_2025.render_profile_source_evidence,
        source_defects=source_defects_for("aeat-dr-189-2023"),
        inheritance=chain,
    )
    assert rendered.output_files == ("0000-export-layout.toml",)
    assert tuple(load_modelo_directory(staged_root).revisions) == ("2023", "2024", "2025")
    for revision in ("2023", "2024", "2025"):
        original = read_staged_edition(source_root / "modelos/189", revision, side="source")
        staged = read_staged_edition(staged_root, revision, side="staged")
        assert member_identities(staged) == member_identities(original)
        assert chain_materialisation(staged) == chain_materialisation(original)
    _require_isolated_target_context(
        candidate_root,
        modelo_id="189",
        revision_id="2025",
        baseline_revisions=("2023", "2024"),
    )

    repeated = replace(chain, baseline_context=chain)
    with pytest.raises(ValueError, match="repeated ancestor revision"):
        stage_attested_inherited_modelo(
            source_root / "modelos/189",
            tmp_path / "cycle-candidate" / "modelos/189",
            revision="2025",
            inheritance=repeated,
            include_target_export=False,
        )
    with pytest.raises(RegistryValidationError, match="ancestor cycle"):
        select_generated_export_inheritance(
            authority,
            source_root,
            modelo="189",
            revision="2025",
            _visited=frozenset({"2025"}),
        )
    (staged_root / "revisions/unrelated").mkdir()
    with pytest.raises(RegistryValidationError, match="generated modelo revisions directory"):
        _require_isolated_target_context(
            candidate_root,
            modelo_id="189",
            revision_id="2025",
            baseline_revisions=("2023", "2024"),
        )
    (staged_root / "revisions/unrelated").rmdir()
    (staged_root / "revisions/2023").rename(tmp_path / "removed-2023")
    with pytest.raises(RegistryValidationError, match="generated modelo revisions directory"):
        _require_isolated_target_context(
            candidate_root,
            modelo_id="189",
            revision_id="2025",
            baseline_revisions=("2023", "2024"),
        )
    source_2023_revision = source_root / "modelos/189/revisions/2023/revision.toml"
    source_2023_revision.write_bytes(source_2023_revision.read_bytes() + b"\n# changed ancestor witness\n")
    with pytest.raises(RegistryValidationError, match="baseline chain attestation changed"):
        require_generated_export_inheritance(
            chain,
            authority,
            source_root,
            modelo="189",
            revision="2025",
        )


def test_real_child_delta_hydrates_to_full_render_and_old_tree_is_exact(tmp_path: Path) -> None:
    prepared, authority = _prepared(tmp_path)
    rendered = _render_candidate(prepared)
    assert rendered.output_files == ("0000-export-layout.toml",)
    assert rendered.provenance_manifest.generated_export_inheritance == prepared.inheritance.attestation
    assert "export_layouts = []" in (
        prepared.candidate_root / "modelos/189/revisions/2025/export/0000-export-layout.toml"
    ).read_text(encoding="utf-8")
    validated = validate_generated_export_tree(
        context=prepared.validation,
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        rendered=rendered,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
    )
    assert validated.layout == authority.modelo("189").revisions["2025"].export_layouts[0]
    hydrated = load_modelo_directory(prepared.candidate_root / "modelos/189")
    assert hydrated.revisions["2025"].export_layouts == (rendered.layout,)
    expected = (*tuple(item[0] for item in prepared.inheritance.pinned_ancestors), "2025")
    assert tuple(hydrated.revisions) == expected
    for revision in expected:
        original = read_staged_edition(bundled_path("registry", "aeat", "modelos", "189"), revision, side="source")
        staged = read_staged_edition(prepared.candidate_root / "modelos/189", revision, side="staged")
        assert member_identities(staged) == member_identities(original)
        assert chain_materialisation(staged) == chain_materialisation(original)
    with pytest.raises(RegistryValidationError, match="field derivations do not match the rendered tree"):
        verify_export_fragment_provenance_manifest(
            export_root=prepared.candidate_root / "modelos/189/revisions/2025/export",
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            target=prepared.validation.target,
            loaded_layout=rendered.layout,
            field_derivations=rendered.field_derivations[:-1],
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
            generated_export_inheritance=prepared.inheritance.attestation,
        )

    comparison = compare_export_tree_roots(
        modelo="189",
        revision="2025",
        layout_id=prepared.inputs.layout_id,
        committed_root=prepared.target_export_root,
        rendered_root=prepared.candidate_root / "modelos/189/revisions/2025/export",
    )
    assert comparison.disposition_class in (None, "provenance_only")
    assert not comparison.record_differing and not comparison.only_committed and not comparison.only_rendered

    child_source = prepared.candidate_root / "modelos/189/revisions/2025/revision.toml"
    raw_source = child_source.read_bytes()
    changed_source = raw_source.replace(b'authority_grade = "filing"', b'authority_grade = "applicability"', 1)
    assert changed_source != raw_source
    child_source.write_bytes(changed_source)
    with pytest.raises(RegistryValidationError, match="changed hydrated 189/2025 source facts"):
        validate_generated_export_tree(
            context=prepared.validation,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            rendered=rendered,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        )


def test_changed_source_pins_baseline_or_layout_refuse_compaction(tmp_path: Path) -> None:
    prepared, authority = _prepared(tmp_path)
    inheritance = prepared.inheritance
    assert inheritance is not None
    wrong_pin = replace(
        inheritance,
        attestation=inheritance.attestation.model_copy(update={"baseline_source_sha256": "0" * 64}),
    )
    with pytest.raises(RegistryValidationError, match="baseline or effective layout changed"):
        require_generated_export_inheritance(
            wrong_pin,
            authority,
            bundled_path("registry", "aeat"),
            modelo="189",
            revision="2025",
        )
    wrong_layout = replace(
        inheritance,
        baseline_layout=inheritance.baseline_layout.model_copy(update={"id": "different-layout"}),
    )
    with pytest.raises(RegistryValidationError, match="changed ordered layout"):
        render_complete_export_tree(
            tmp_path / "wrong-layout" / "export",
            revision_id=prepared.inputs.revision_id,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            transport_profile=prepared.inputs.transport_profile,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
            source_defects=source_defects_for(prepared.invocation.source_ref),
            inheritance=wrong_layout,
        )
    assert not (tmp_path / "wrong-layout" / "export").exists()

    wrong_map = prepared.inputs.semantic_map.model_copy(update={"source_sha256": "0" * 64})
    with pytest.raises((RegistryValidationError, ValueError), match="source"):
        render_complete_export_tree(
            tmp_path / "wrong-child-source" / "export",
            revision_id=prepared.inputs.revision_id,
            joined=prepared.inputs.joined,
            semantic_map=wrong_map,
            transport_profile=prepared.inputs.transport_profile,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
            source_defects=source_defects_for(prepared.invocation.source_ref),
            inheritance=inheritance,
        )
    wrong_profile = prepared.inputs.render_profile.model_copy(
        update={
            "design_identity": prepared.inputs.render_profile.design_identity.model_copy(
                update={"source_sha256": "0" * 64},
            ),
        },
    )
    with pytest.raises((RegistryValidationError, ValueError), match="source"):
        render_complete_export_tree(
            tmp_path / "wrong-child-profile" / "export",
            revision_id=prepared.inputs.revision_id,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            transport_profile=prepared.inputs.transport_profile,
            render_profile=wrong_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
            source_defects=source_defects_for(prepared.invocation.source_ref),
            inheritance=inheritance,
        )

    isolated_root = tmp_path / "changed-baseline" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", "189"), isolated_root / "modelos/189")
    baseline_revision = isolated_root / "modelos/189/revisions/2024/revision.toml"
    baseline_revision.write_bytes(baseline_revision.read_bytes() + b"\n# changed baseline witness\n")
    with pytest.raises(RegistryValidationError, match="baseline or effective layout changed"):
        require_generated_export_inheritance(
            inheritance,
            authority,
            isolated_root,
            modelo="189",
            revision="2025",
        )

    missing_root = tmp_path / "missing-baseline" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", "189"), missing_root / "modelos/189")
    (missing_root / "modelos/189/revisions/2024/export").rename(
        missing_root / "modelos/189/revisions/2024/absent-export",
    )
    with pytest.raises(RegistryValidationError, match="generated export package must be a non-linked directory"):
        require_generated_export_inheritance(
            inheritance,
            authority,
            missing_root,
            modelo="189",
            revision="2025",
        )

    evolution_root = tmp_path / "claimed-evolution" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", "189"), evolution_root / "modelos/189")
    (evolution_root / "modelos/189/revisions/2025/casilla_continuidad_evolutions").mkdir()
    with pytest.raises(RegistryValidationError, match="cannot detach a revision with continuity evolutions"):
        require_generated_export_inheritance(
            inheritance,
            authority,
            evolution_root,
            modelo="189",
            revision="2025",
        )

    for member in ("semantic_map_sha256", "render_profile_sha256"):
        stale_root = tmp_path / f"stale-{member}" / "aeat"
        shutil.copytree(bundled_path("registry", "aeat", "modelos", "189"), stale_root / "modelos/189")
        manifest_path = stale_root / "modelos/189/revisions/2024/export/_generation.provenance.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest[member] = "0" * 64
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with pytest.raises(RegistryValidationError, match="baseline source render is no longer current"):
            require_generated_export_inheritance(
                inheritance,
                authority,
                stale_root,
                modelo="189",
                revision="2025",
            )


def test_extra_revision_and_same_size_old_field_mutation_refuse(tmp_path: Path) -> None:
    prepared, _ = _prepared(tmp_path, revision="2024")
    rendered = _render_candidate(prepared)
    (prepared.candidate_root / "modelos/189/revisions/unrelated").mkdir()
    with pytest.raises(RegistryValidationError, match="generated modelo revisions directory"):
        validate_generated_export_tree(
            context=prepared.validation,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            rendered=rendered,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        )

    mutated = tmp_path / "mutated-full" / "export"
    _full_witness(prepared, mutated)
    record = mutated / "0001-record-modelo-189-declarante.toml"
    original = record.read_bytes()
    changed = original.replace(b"literal = '1'", b"literal = '2'", 1)
    assert len(changed) == len(original) and changed != original
    record.write_bytes(changed)
    state = GeneratedExportTreeTargetStateReceipt.observe(mutated)
    expected_manifest = hashlib.sha256((mutated / "_generation.provenance.json").read_bytes()).hexdigest()
    bound = replace(
        prepared,
        target_export_root=mutated,
        invocation=replace(prepared.invocation, expected_manifest_sha256=expected_manifest),
    )
    comparison = compare_export_tree_roots(
        modelo="189",
        revision="2024",
        layout_id=prepared.inputs.layout_id,
        committed_root=mutated,
        rendered_root=prepared.candidate_root / "modelos/189/revisions/2025/export",
    )
    with pytest.raises(ValueError, match="does not reproduce the current full source render"):
        _require_storage_equivalent_republication(bound, rendered, state, comparison)


def _m303_source_copy(root: Path, *, complete_registry: bool = False) -> Path:
    """Keep real declarations while recreating the child's first-publication state."""
    registry_root = root / "registry" / "aeat"

    def omit_child_export(directory: str, names: list[str]) -> set[str]:
        return {"export"}.intersection(names) if Path(directory).name == "2026-hasta-01-y-1t" else set()

    if complete_registry:
        shutil.copytree(bundled_path("registry", "aeat"), registry_root, ignore=omit_child_export)
    else:
        for catalogue in bundled_path("registry", "aeat").iterdir():
            if catalogue.is_dir() and catalogue.name != "modelos":
                shutil.copytree(catalogue, registry_root / catalogue.name)
        shutil.copytree(
            bundled_path("registry", "aeat", "modelos", "303"),
            registry_root / "modelos/303",
            ignore=omit_child_export,
        )
    return registry_root


def _prepare_retained_m303(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Bind the canonical developer owner to one explicitly authorized scratch target."""
    registry_root = _m303_source_copy(tmp_path / "live", complete_registry=True)
    authority = compiled_bundled_authority()

    def scratch_bundled_path(*parts: str) -> Path:
        if parts[:2] == ("registry", "aeat"):
            return registry_root.joinpath(*parts[2:])
        return bundled_path(*parts)

    monkeypatch.setattr(pipeline_cli, "bundled_path", scratch_bundled_path)
    prepared = prepare_generated_tree_invocation(
        GeneratedTreeInvocation("303", "2026-hasta-01-y-1t", "aeat-dr-303-2026", 2026, "1T"),
        tmp_path / "generation",
        authority=authority,
    )
    return prepared, authority, registry_root


def test_real_early_m303_compact_publication_retains_the_complete_legal_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Publish real source-derived empty storage without duplicating or detaching facts."""
    prepared, authority, registry_root = _prepare_retained_m303(tmp_path, monkeypatch)
    modelo_root = registry_root / "modelos/303"
    original = authority.modelo("303")
    original_non_export = generated_export_source_chain_fingerprint(
        registry_root, modelo="303", revision="2026-hasta-01-y-1t", omit_target_export=True
    )
    assert prepared.inheritance is not None
    assert prepared.validation.source_chain_revisions == tuple(original.revisions)
    assert str(prepared.inheritance.attestation.baseline_revision_id) == "2026-y-siguientes"
    assert original.revisions["2026-y-siguientes"].casilla_continuidad_evolutions
    status, rendered, state = check_prepared_invocation(prepared)
    assert status == "publishable_absence" and state.manifest_sha256 is None
    assert rendered.output_files == ("0000-export-layout.toml",)
    assert rendered.layout == original.revisions["2026-hasta-01-y-1t"].export_layouts[0]
    assert rendered.provenance_manifest.generated_export_inheritance == prepared.inheritance.attestation
    publish_prepared_invocation(prepared, rendered, state)
    assert prepared.target_export_root.is_dir()
    assert (
        generated_export_source_chain_fingerprint(
            registry_root, modelo="303", revision="2026-hasta-01-y-1t", omit_target_export=True
        )
        == original_non_export
    )
    loaded = load_modelo_directory(modelo_root)
    require_source_chain_unchanged(original, loaded, revision="2026-hasta-01-y-1t")
    assert loaded.revisions["2026-hasta-01-y-1t"].form_layouts == original.revisions["2026-hasta-01-y-1t"].form_layouts
    assert loaded.revisions["2026-y-siguientes"].casilla_continuidad_evolutions == (
        original.revisions["2026-y-siguientes"].casilla_continuidad_evolutions
    )
    payload = parse_toml((prepared.target_export_root / "0000-export-layout.toml").read_text("utf-8"))
    assert payload["revisions"]["2026-hasta-01-y-1t"]["export_layouts"] == []
    assert compare_revision_against_committed(
        authority,
        modelo="303",
        revision="2026-hasta-01-y-1t",
        source_ref="aeat-dr-303-2026",
        filing_year=2026,
        period="1T",
        registry_root=registry_root,
    ).reproduced
    assessment = assess_migration_state(modelo_root)
    assert assessment.minimal and assessment.inputs_stable
    outcome = migrate_modelo(
        registry_root=registry_root, modelo_id="303", work_dir=tmp_path / "non-applying-noop", apply=False
    )
    assert not outcome.changed and not outcome.applied and outcome.staged_registry is None
    assert outcome.after_assessment is not None and outcome.after_assessment.minimal
    manifest = modelo_root / "manifest.toml"
    before = manifest.read_bytes()
    try:
        manifest.write_bytes(before + b"\n# unrelated post-cutover source mutation\n")
        with pytest.raises(RegistryValidationError, match="source-chain facts changed during export cutover"):
            pipeline_cli._validate_final_live_target(prepared)
    finally:
        manifest.write_bytes(before)


@pytest.mark.parametrize("evolution_revision", ["2024", "2025"])
def test_explicit_retained_mode_still_refuses_unvalidated_empty_evolution_directories(
    tmp_path: Path, evolution_revision: str
) -> None:
    """A staging obligation cannot authorize new declarations absent from validated facts."""
    authority = compiled_bundled_authority()
    registry_root = tmp_path / "registry"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", "189"), registry_root / "modelos/189")
    expected = select_generated_export_inheritance(authority, registry_root, modelo="189", revision="2025")
    assert expected is not None
    (registry_root / "modelos/189/revisions" / evolution_revision / "casilla_continuidad_evolutions").mkdir()
    assert (
        select_generated_export_inheritance(
            authority, registry_root, modelo="189", revision="2025", retain_source_chain=True
        )
        is None
    )
    with pytest.raises(
        RegistryValidationError, match=f"cannot detach a revision with continuity evolutions: 189/{evolution_revision}"
    ):
        require_generated_export_inheritance(
            expected, authority, registry_root, modelo="189", revision="2025", retain_source_chain=True
        )


@pytest.mark.parametrize(
    "mutation", ["evolution", "endpoint", "source", "manifest", "manual", "missing_origin", "layout"]
)
def test_retained_mode_refuses_changed_real_continuity_or_generated_origin(tmp_path: Path, mutation: str) -> None:
    """Real continuity never converts missing or stale generated authority into a fallback."""
    authority = compiled_bundled_authority()
    registry_root = _m303_source_copy(tmp_path)
    definition = authority.modelo("303")
    expected = select_generated_export_inheritance(
        authority, registry_root, modelo="303", revision="2026-hasta-01-y-1t", retain_source_chain=True
    )
    assert expected is not None
    baseline_root = registry_root / "modelos/303/revisions/2026-y-siguientes"
    if mutation == "evolution":
        fragment = baseline_root / "casilla_continuidad_evolutions/0001-declarations.toml"
        original = fragment.read_bytes()
        changed = original.replace(b'from_revision = "2025"', b'from_revision = "absent-endpoint"', 1)
        assert changed != original
        fragment.write_bytes(changed)
    elif mutation == "endpoint":
        (registry_root / "modelos/303/revisions/2025").rename(tmp_path / "removed-endpoint")
    elif mutation == "source":
        manifest_path = baseline_root / "export/_generation.provenance.json"
        payload = json.loads(manifest_path.read_bytes())
        payload["source_sha256"] = "0" * 64
        manifest_path.write_bytes(canonical_json_bytes(payload))
    elif mutation == "manifest":
        fragment = baseline_root / "export/_generation.provenance.json"
        payload = json.loads(fragment.read_bytes())
        payload["semantic_map_sha256"] = "0" * 64
        fragment.write_bytes(canonical_json_bytes(payload))
    elif mutation == "missing_origin":
        (baseline_root / "export").rename(tmp_path / "missing-generated-origin")
    elif mutation == "manual":
        (baseline_root / "export").rename(tmp_path / "removed-generated-origin")
        manual = baseline_root / "export_layouts"
        manual.mkdir()
        layout = definition.revisions["2026-y-siguientes"].export_layouts[0]
        (manual / "0001-layout.toml").write_bytes(
            render_toml_bytes(
                "0001-layout.toml",
                {
                    "revisions": {
                        "2026-y-siguientes": {"export_layouts": [layout.model_dump(mode="json", exclude_none=True)]}
                    }
                },
            )
        )
    else:
        expected = replace(expected, baseline_layout=expected.baseline_layout.model_copy(update={"id": "other-layout"}))
    with pytest.raises(RegistryValidationError):
        require_generated_export_inheritance(
            expected,
            authority,
            registry_root,
            modelo="303",
            revision="2026-hasta-01-y-1t",
            retain_source_chain=True,
        )
    assert not (registry_root / "modelos/303/revisions/2026-hasta-01-y-1t/export").exists()


def test_retained_source_bytes_and_publication_root_are_checked_before_any_cutover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A held proof refuses ancestor and unrelated fact mutations, including byte-only changes."""
    prepared, _, registry_root = _prepare_retained_m303(tmp_path, monkeypatch)
    status, rendered, state = check_prepared_invocation(prepared)
    assert status == "publishable_absence"
    modelo_root = registry_root / "modelos/303"
    guarded = (
        modelo_root / "manifest.toml",
        modelo_root / "revisions/2025/revision.toml",
        modelo_root / "revisions/2026-hasta-01-y-1t/revision.toml",
        modelo_root / "revisions/2026-y-siguientes/casilla_continuidad_evolutions/0001-declarations.toml",
        modelo_root / "revisions/2026-y-siguientes/export/_generation.provenance.json",
    )
    for path in guarded:
        before = path.read_bytes()
        try:
            path.write_bytes(before + b"\n")
            with pytest.raises(RegistryValidationError, match="source-chain facts changed during export cutover"):
                publish_prepared_invocation(prepared, rendered, state)
            assert not prepared.target_export_root.exists()
        finally:
            path.write_bytes(before)

    candidate_endpoint = prepared.candidate_root / "modelos/303/revisions/2025"
    displaced_endpoint = tmp_path / "dropped-candidate-endpoint"
    candidate_endpoint.rename(displaced_endpoint)
    try:
        with pytest.raises(RegistryValidationError, match="generated modelo revisions directory"):
            publish_prepared_invocation(prepared, rendered, state)
        assert not prepared.target_export_root.exists()
    finally:
        displaced_endpoint.rename(candidate_endpoint)

    other_root = tmp_path / "other-registry"
    other_target = other_root / "modelos/303/revisions/2026-hasta-01-y-1t/export"
    other_target.parent.mkdir(parents=True)
    context = GeneratedExportTreePublicationContext(
        validation=prepared.validation,
        temporary_root=prepared.candidate_root.parents[2],
        target_root=other_root,
        target_export_root=other_target,
        expected_target_state=state,
    )
    with pytest.raises(RegistryValidationError, match="origin differs from the publication root"):
        publish_validated_generated_export_tree(
            context=context,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            rendered=rendered,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        )
    assert not other_target.exists() and not prepared.target_export_root.exists()
    with pytest.raises(RegistryValidationError, match=r"complete validated modelo|lost an attested ancestor"):
        replace(prepared.validation, source_chain_revisions=prepared.validation.source_chain_revisions[1:])
    with pytest.raises(RegistryValidationError, match="complete validated modelo"):
        replace(
            prepared.validation,
            target=ExportFragmentTarget(modelo="189", revision_id="2026-hasta-01-y-1t", design_epoch="2026"),
        )
    assert (
        generated_export_source_chain_fingerprint(registry_root, modelo="303", revision="2026-hasta-01-y-1t")
        == prepared.validation.source_chain_sha256
    )


def test_direct_retained_publisher_settles_swap_and_callback_mutations_by_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The canonical publisher owns post-cutover integrity even without a CLI callback."""
    prepared, _, registry_root = _prepare_retained_m303(tmp_path, monkeypatch)
    status, rendered, state = check_prepared_invocation(prepared)
    assert status == "publishable_absence"
    manifest = registry_root / "modelos/303/manifest.toml"
    source_before = manifest.read_bytes()

    def replace_export_directory(source: Path, destination: Path, *, mutation: str) -> None:
        source.replace(destination)
        if mutation != "callback" and destination == prepared.target_export_root:
            manifest.write_bytes(source_before + b"\n# source changed during cutover\n")

    def final_validator(*, mutation: str, callbacks: list[str]) -> None:
        callbacks.append("called")
        if mutation == "callback":
            manifest.write_bytes(source_before + b"\n# source changed during final validation\n")

    for mutation in ("swap_without_callback", "swap_with_callback", "callback"):
        callbacks: list[str] = []

        context = GeneratedExportTreePublicationContext(
            validation=prepared.validation,
            temporary_root=prepared.candidate_root.parents[2],
            target_root=registry_root,
            target_export_root=prepared.target_export_root,
            expected_target_state=state,
            final_live_validator=(
                None
                if mutation == "swap_without_callback"
                else partial(final_validator, mutation=mutation, callbacks=callbacks)
            ),
            replace_export_directory=partial(replace_export_directory, mutation=mutation),
        )
        try:
            with pytest.raises(RegistryValidationError, match="source-chain facts changed during export cutover"):
                publish_validated_generated_export_tree(
                    context=context,
                    joined=prepared.inputs.joined,
                    semantic_map=prepared.inputs.semantic_map,
                    rendered=rendered,
                    render_profile=prepared.inputs.render_profile,
                    render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
                )
            assert not prepared.target_export_root.exists()
            assert callbacks == (["called"] if mutation == "callback" else [])
            assert manifest.read_bytes() != source_before
        finally:
            # The publisher rolls back only its own export; it never rewrites peer source facts.
            manifest.write_bytes(source_before)
        assert (
            generated_export_source_chain_fingerprint(registry_root, modelo="303", revision="2026-hasta-01-y-1t")
            == prepared.validation.source_chain_sha256
        )


def test_retained_compact_recovery_checks_source_before_and_after_real_journal_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real staged/live recovery preserves stale journals and never returns false integrity success."""
    prepared, authority, registry_root = _prepare_retained_m303(tmp_path, monkeypatch)
    status, rendered, _ = check_prepared_invocation(prepared)
    assert status == "publishable_absence"
    context = GeneratedExportTreePublicationContext(
        validation=prepared.validation,
        temporary_root=prepared.candidate_root.parents[2],
        target_root=registry_root,
        target_export_root=prepared.target_export_root,
    )
    paths = GeneratedExportTransactionPaths.for_context(context)
    candidate = prepared.candidate_root / "modelos/303/revisions/2026-hasta-01-y-1t/export"
    candidate_manifest = verify_generated_export_package(candidate)
    manifest_sha = export_provenance_file_sha256(candidate / "_generation.provenance.json")
    staged = stage_verified_candidate_package(
        candidate_export_root=candidate,
        target_root=registry_root,
        modelo="303",
        revision_id="2026-hasta-01-y-1t",
        expected_manifest_sha256=manifest_sha,
        expected_manifest=candidate_manifest,
    )
    journal = GeneratedExportPublicationJournal(
        schema_version=1,
        state="intent",
        modelo="303",
        revision_id="2026-hasta-01-y-1t",
        candidate_export=str(staged),
        backup_export=str(paths.new_backup_sibling()),
        candidate_manifest_sha256=manifest_sha,
    )
    write_generated_export_publication_journal(paths.journal, journal)
    journal_before = paths.journal.read_bytes()
    package_before = {path.name: path.read_bytes() for path in staged.iterdir()}
    source_manifest = registry_root / "modelos/303/manifest.toml"
    source_before = source_manifest.read_bytes()

    def publish(bound: GeneratedExportTreePublicationContext) -> PublishedGeneratedExportTree:
        return publish_validated_generated_export_tree(
            context=bound,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            rendered=rendered,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        )

    try:
        source_manifest.write_bytes(source_before + b"\n# stale retained source before recovery\n")
        with pytest.raises(RegistryValidationError, match="source-chain facts changed during export cutover"):
            publish(context)
        assert paths.journal.read_bytes() == journal_before
        assert {path.name: path.read_bytes() for path in staged.iterdir()} == package_before
        assert not prepared.target_export_root.exists()
    finally:
        source_manifest.write_bytes(source_before)

    recovered = publish(context)
    assert recovered.validated is None and recovered.export_root == prepared.target_export_root
    assert verify_generated_export_package(recovered.export_root) == candidate_manifest
    assert not paths.journal.exists() and not staged.exists()
    require_source_chain_unchanged(
        authority.modelo("303"),
        load_modelo_directory(registry_root / "modelos/303"),
        revision="2026-hasta-01-y-1t",
    )

    # Recreate the actual pre-install interruption using the verified package and owning journal.
    prepared.target_export_root.replace(staged)
    write_generated_export_publication_journal(paths.journal, journal)

    def install_with_source_mutation(source: Path, destination: Path) -> None:
        source.replace(destination)
        if destination == prepared.target_export_root:
            source_manifest.write_bytes(source_before + b"\n# source changed during real recovery\n")

    try:
        with pytest.raises(RegistryValidationError, match="source-chain facts changed during export cutover"):
            publish(replace(context, replace_export_directory=install_with_source_mutation))
        assert verify_generated_export_package(prepared.target_export_root) == candidate_manifest
        assert not paths.journal.exists() and not staged.exists()
        assert source_manifest.read_bytes() != source_before
        # The outer completion refusal does not claim rollback after recovery finalized its journal.
    finally:
        source_manifest.write_bytes(source_before)

    # The live-candidate branch must remain recoverable with the same restored source context.
    write_generated_export_publication_journal(paths.journal, journal.model_copy(update={"state": "candidate_live"}))
    recovered_live = publish(context)
    assert recovered_live.validated is None
    assert {path.name: path.read_bytes() for path in recovered_live.export_root.iterdir()} == package_before
    assert not paths.journal.exists()
    assert (
        generated_export_source_chain_fingerprint(
            registry_root, modelo="303", revision="2026-hasta-01-y-1t", omit_target_export=True
        )
        == prepared.validation.source_chain_non_export_sha256
    )


def test_retained_compact_refuses_incompatible_modes_before_transaction_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual clearance and canonical bundle journals cannot bypass export-only retained admission."""
    prepared, _, registry_root = _prepare_retained_m303(tmp_path, monkeypatch)
    status, rendered, state = check_prepared_invocation(prepared)
    assert status == "publishable_absence"
    context = GeneratedExportTreePublicationContext(
        validation=prepared.validation,
        temporary_root=prepared.candidate_root.parents[2],
        target_root=registry_root,
        target_export_root=prepared.target_export_root,
        expected_target_state=state,
    )
    paths = GeneratedExportTransactionPaths.for_context(context)

    def publish(bound: GeneratedExportTreePublicationContext) -> PublishedGeneratedExportTree:
        return publish_validated_generated_export_tree(
            context=bound,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            rendered=rendered,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        )

    revision_root = prepared.target_export_root.parent
    source_sha = bootstrap_layout_supersession_fingerprint(revision_root)
    # This is an intentionally incompatible typed context, not an invented manual-source authorization.
    supersession = GeneratedExportSupersession(
        superseded_layout_id="injected-manual-layout",
        generated_layout_id=prepared.inputs.layout_id,
        expected_construct_references=0,
        source_state_sha256=source_sha,
    )
    with pytest.raises(RegistryValidationError, match="does not support supersession or export clearance"):
        publish(replace(context, supersession=supersession))
    assert not paths.journal.exists() and not prepared.target_export_root.exists()

    metadata = revision_root / "revision.toml"
    before = metadata.read_bytes()
    header = b'[revisions."2026-hasta-01-y-1t"]'
    assert before.count(header) == 1
    clearance = (
        b'\ncleared_families = [{ family = "export_layouts", cause = "not_authored_for_this_edition", '
        b'reason = "Injected incompatible publication mode for admission proof." }]'
    )
    try:
        metadata.write_bytes(before.replace(header, header + clearance, 1))
        with pytest.raises(RegistryValidationError, match="does not support supersession or export clearance"):
            publish(context)
        assert not paths.journal.exists() and not prepared.target_export_root.exists()
    finally:
        metadata.write_bytes(before)

    bundle = paths.new_bundle_staging_sibling()
    shutil.copytree(prepared.candidate_root / "modelos/303/revisions/2026-hasta-01-y-1t", bundle)
    bundle_before = {path.relative_to(bundle): path.read_bytes() for path in bundle.rglob("*") if path.is_file()}
    candidate_sha = bootstrap_layout_supersession_fingerprint(bundle)
    manifest_sha = export_provenance_file_sha256(bundle / "export/_generation.provenance.json")
    supersession_journal = GeneratedExportPublicationJournal(
        schema_version=1,
        state="intent",
        modelo="303",
        revision_id="2026-hasta-01-y-1t",
        candidate_export=str(bundle),
        backup_export=str(paths.new_bundle_backup_sibling()),
        candidate_manifest_sha256=manifest_sha,
        candidate_revision_sha256=candidate_sha,
        superseded_layout_id="injected-manual-layout",
        generated_layout_id=prepared.inputs.layout_id,
        superseded_construct_references=0,
        supersession_source_sha256=source_sha,
    )
    clearance_journal = GeneratedExportPublicationJournal(
        schema_version=1,
        state="intent",
        modelo="303",
        revision_id="2026-hasta-01-y-1t",
        candidate_export=str(bundle),
        backup_export=str(paths.new_bundle_backup_sibling()),
        candidate_manifest_sha256=manifest_sha,
        candidate_revision_sha256=candidate_sha,
        supersession_source_sha256=source_sha,
        retires_export_clearance=True,
    )
    for journal in (supersession_journal, clearance_journal):
        write_generated_export_publication_journal(paths.journal, journal)
        journal_before = paths.journal.read_bytes()
        with pytest.raises(RegistryValidationError, match="cannot recover a revision-bundle transaction"):
            publish(context)
        assert paths.journal.read_bytes() == journal_before
        assert {
            path.relative_to(bundle): path.read_bytes() for path in bundle.rglob("*") if path.is_file()
        } == bundle_before
        assert metadata.read_bytes() == before and not prepared.target_export_root.exists()
        assert not Path(journal.backup_export).exists()
        paths.journal.unlink()
    assert (
        generated_export_source_chain_fingerprint(registry_root, modelo="303", revision="2026-hasta-01-y-1t")
        == prepared.validation.source_chain_sha256
    )


def test_retained_compact_refuses_clearance_added_during_actual_candidate_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh mode fence prevents post-validation staging from redirecting the transaction."""
    prepared, _, registry_root = _prepare_retained_m303(tmp_path, monkeypatch)
    status, rendered, state = check_prepared_invocation(prepared)
    assert status == "publishable_absence"
    context = GeneratedExportTreePublicationContext(
        validation=prepared.validation,
        temporary_root=prepared.candidate_root.parents[2],
        target_root=registry_root,
        target_export_root=prepared.target_export_root,
        expected_target_state=state,
    )
    paths = GeneratedExportTransactionPaths.for_context(context)
    metadata = prepared.target_export_root.parent / "revision.toml"
    before = metadata.read_bytes()
    header = b'[revisions."2026-hasta-01-y-1t"]'
    assert before.count(header) == 1
    clearance = (
        b'\ncleared_families = [{ family = "export_layouts", cause = "not_authored_for_this_edition", '
        b'reason = "Injected post-validation transaction mode for admission proof." }]'
    )
    staged_packages: list[Path] = []
    original_stage = tree_publication.stage_verified_candidate_package

    def stage_then_change_mode(
        *,
        candidate_export_root: Path,
        target_root: Path,
        modelo: str,
        revision_id: str,
        expected_manifest_sha256: str,
        expected_manifest: ExportFragmentProvenanceManifest,
    ) -> Path:
        staged = original_stage(
            candidate_export_root=candidate_export_root,
            target_root=target_root,
            modelo=modelo,
            revision_id=revision_id,
            expected_manifest_sha256=expected_manifest_sha256,
            expected_manifest=expected_manifest,
        )
        staged_packages.append(staged)
        metadata.write_bytes(before.replace(header, header + clearance, 1))
        return staged

    monkeypatch.setattr(tree_publication, "stage_verified_candidate_package", stage_then_change_mode)
    try:
        with pytest.raises(RegistryValidationError, match="does not support supersession or export clearance"):
            publish_validated_generated_export_tree(
                context=context,
                joined=prepared.inputs.joined,
                semantic_map=prepared.inputs.semantic_map,
                rendered=rendered,
                render_profile=prepared.inputs.render_profile,
                render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
            )
        assert len(staged_packages) == 1
        assert verify_generated_export_package(staged_packages[0]) == rendered.provenance_manifest
        assert not paths.journal.exists() and not prepared.target_export_root.exists()
        assert metadata.read_bytes() == before.replace(header, header + clearance, 1)
        assert not tuple(registry_root.glob(paths.backup_prefix + "*"))
        # This pre-transaction refusal leaves only the already verified staged package for its owner.
    finally:
        metadata.write_bytes(before)
