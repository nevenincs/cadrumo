"""A generated child may store an empty keyed delta only with exact baseline proof."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import SourceRefId
from cadrumo.domain.calculations.registry.static_inspection import GeneratedArtifactSource

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_modelo_directory
from ...edition_delta_chain_materialisation import chain_materialisation, member_identities
from ...edition_delta_proof_source import read_staged_edition
from .._export_tree import render_complete_export_tree
from .._tree_validation import _require_isolated_target_context, validate_generated_export_tree
from ..candidate_staging import stage_attested_inherited_modelo
from ..cli import (
    GeneratedTreeInvocation,
    _render_candidate,
    _require_storage_equivalent_republication,
    prepare_generated_tree_invocation,
)
from ..export_fragment_provenance import verify_export_fragment_provenance_manifest
from ..generated_export_inheritance import (
    require_generated_export_inheritance,
    select_generated_export_inheritance,
    verify_generated_export_inheritance_storage,
)
from ..render_check import compare_export_tree_roots, revision_render_inputs
from ..source_defects import source_defects_for
from ..tree_publication_contracts import GeneratedExportTreeTargetStateReceipt

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
