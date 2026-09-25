"""Every committed generated export tree is checked by the generator's own authority.

ONE gate for all of them, and it does NOT re-implement the comparison: it drives
``check_generated_export_tree``, which regenerates the tree into an isolated
candidate registry, validates that candidate through the real loader and registry
authority, and only then requires the published target to attest to the same
authorities with identical normalized loader semantics and identical bytes.

An earlier version of this module compared directories with ``filecmp`` instead.
That is a strictly weaker question -- it can say two directories differ, but it
cannot say the tree is a VALID registry authority -- and it let trees be written
without the pre-cutover proof that the generator already owned.

Enrollment is projected from the validated registry and each published tree's
canonical provenance manifest. A generated tree therefore enters this gate in
the same change that publishes it; no second hand-maintained revision list can
silently omit it. A tree whose published design contradicts itself consumes the
pipeline-owned adjudication keyed by the source file it describes.
"""

from __future__ import annotations

import filecmp
import shutil
from collections.abc import Iterable
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import (
    RegistryLoadError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import (
    load_modelo_directory,
)
from .._export_tree import render_complete_export_tree
from .._tree_check import GeneratedExportTreeCheckContext, check_generated_export_tree
from .._tree_validation import GeneratedExportTreeValidationContext, validate_generated_export_tree
from ..candidate_staging import (
    stage_continuity_metadata,
)
from ..cli import stage_published_modelo
from ..export_fragment_provenance import (
    ExportFragmentTarget,
    export_fragment_provenance_manifest_json_bytes,
    export_fragment_provenance_path,
    load_export_fragment_provenance_manifest,
    loader_semantic_digest,
)
from ..generated_tree_dispositions import record_drift_dispositions, render_refusal_dispositions
from ..generated_tree_inventory import GeneratedExportTree, generated_export_trees
from ..joined_record_design import design_view
from ..render_check import compare_revision_against_committed, parsed_tree_file
from ..source_defects import source_defects_for
from ._generated_tree_test_support import isolated_authorities, isolated_authority, supporting_modelos

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.usefixtures("governed_fact_scope")]


_GENERATED_TREES = generated_export_trees()
_RECORD_DRIFT_DISPOSITIONS = {item.subject: item for item in record_drift_dispositions()}
_RENDER_REFUSAL_DISPOSITIONS = {item.subject: item for item in render_refusal_dispositions()}
#: Check mode's exact current refusal. A changed refusal makes the owning row red.
_CHECK_MODE_PENDING: dict[str, str] = {
    # The tree is published at calculation grade and reproduces exactly, but check
    # mode validates the candidate as a filing snapshot, and the revision's
    # relationship families are not yet resolved to filing grade. Retires, by
    # failing the pass assertion below, the day the revision earns filing grade.
    "m222-2025-y-siguientes": (
        "declares 'calculation' authority grade, which cannot satisfy the requested 'filing' snapshot authority"
    ),
    # The 2023 and 2024 editions are the same case as their in-force sibling
    # above, from the same design family: each publishes a reproducing tree at
    # calculation grade, and each still owes the relationship families the
    # filing rung asserts. Both retire by the same pass assertion the day the
    # revision earns filing grade.
    "m222-2023": (
        "declares 'calculation' authority grade, which cannot satisfy the requested 'filing' snapshot authority"
    ),
    "m222-2024": (
        "declares 'calculation' authority grade, which cannot satisfy the requested 'filing' snapshot authority"
    ),
}


def test_every_pending_check_mode_entry_names_an_enrolled_tree() -> None:
    """A pending reason keyed to no row is unreachable, and unreachable is invisible.

    ``_CHECK_MODE_PENDING`` is keyed by ``str(GeneratedExportTree)``, which embeds the
    revision id, so renaming a row silently orphans its entry: the lookup returns
    ``None``, check mode is then expected to PASS, and the recorded reason stops
    being asserted without anything going red. That is the one failure this dict
    cannot self-report, because every other drift in it surfaces as a refusal
    that does not match its recorded text.
    """
    enrolled = {str(tree) for tree in _GENERATED_TREES}
    orphaned = sorted(set(_CHECK_MODE_PENDING) - enrolled)
    assert orphaned == [], (
        f"pending check-mode entries name no enrolled tree: {orphaned}. A row rename must carry "
        "its entry with it; deleting the entry instead silently drops the reason this gate is "
        "allowed to be pending."
    )


def _published_layout(tree: GeneratedExportTree, root: Path) -> ExportLayoutDefinition:
    """Load the committed tree's layout exactly as check mode loads its published witness."""
    staged = stage_published_modelo(root, modelo=tree.modelo, revision=tree.revision)
    definition = load_modelo_directory(staged or bundled_path("registry", "aeat", "modelos", tree.modelo))
    (layout,) = definition.revisions[tree.revision].export_layouts
    return layout


def _stale_loader_attestations(entries: Iterable[tuple[str, Path, ExportLayoutDefinition]]) -> list[str]:
    """Name every export root whose manifest attests a loader digest its layout no longer has."""
    stale: list[str] = []
    for subject, export_root, layout in entries:
        manifest = load_export_fragment_provenance_manifest(export_fragment_provenance_path(export_root).read_bytes())
        current = loader_semantic_digest(layout)
        if manifest.loader_semantic_sha256 != current:
            stale.append(f"{subject} (attests {manifest.loader_semantic_sha256}, current {current})")
    return stale


def test_every_committed_manifest_attests_the_current_loader_semantics(tmp_path: Path) -> None:
    """Each committed manifest's loader digest equals the digest of the layout it ships.

    The reproduction gate reaches this question only after a full render and
    reports one tree at a time. This asks it directly and names every stale tree
    at once, so a projection or loader change that re-attests the corpus reads
    as one list of trees to republish.
    """
    stale = _stale_loader_attestations(
        (str(tree), tree.committed, _published_layout(tree, tmp_path / str(tree)))
        for tree in _GENERATED_TREES
    )

    assert stale == [], (
        f"{len(stale)} committed export manifest(s) attest loader semantics their layout no longer has: "
        f"{stale}. Republish each through `python -m dev.registry.pipeline republish-target`; "
        "test_loader_semantic_projection_shape_is_bound_to_its_schema_version names a projection change"
    )


def test_a_manifest_attesting_other_loader_semantics_is_named(tmp_path: Path) -> None:
    """Detector: a tree whose manifest attests a different loader digest is reported by name."""
    tree = next(item for item in _GENERATED_TREES if str(item) == "m347-2025-y-siguientes")
    layout = _published_layout(tree, tmp_path / "published")
    stale_root = tmp_path / "stale" / "export"
    shutil.copytree(tree.committed, stale_root)
    manifest_path = export_fragment_provenance_path(stale_root)
    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    manifest_path.write_bytes(
        export_fragment_provenance_manifest_json_bytes(
            manifest.model_copy(update={"loader_semantic_sha256": "0" * 64})
        ),
    )

    stale = _stale_loader_attestations(
        (("committed", tree.committed, layout), ("stale-copy", stale_root, layout)),
    )

    assert stale == [f"stale-copy (attests {'0' * 64}, current {loader_semantic_digest(layout)})"]


def test_m390_isolation_excludes_both_export_authorities_and_keeps_required_support(tmp_path: Path) -> None:
    """The enrolled-tree harness renders without copying either export authority."""
    tree = next(item for item in _GENERATED_TREES if item.modelo == "390" and item.revision == "2022")

    registry_root = isolated_authority(tree, tmp_path)
    revision_root = registry_root / "modelos" / "390" / "revisions" / "2022"
    continuity_metadata_modelo_root = stage_continuity_metadata(
        bundled_path("registry", "aeat", "modelos", tree.modelo),
        tmp_path,
        revision=tree.revision,
    )

    assert not (revision_root / "export").exists()
    assert not (revision_root / "export_layouts").exists()
    assert (registry_root / "m303_orden_anual" / "manifest.toml").is_file()
    construct_text = "".join(
        path.read_text(encoding="utf-8") for path in sorted((revision_root / "constructs").glob("*.toml"))
    )
    assert "modelo-390-2022-fichero-boe" not in construct_text
    assert "generated-modelo-390-2022-fichero" in construct_text

    joined, semantic_map, transport, render_profile, evidence = isolated_authorities(tree)
    rendered = render_complete_export_tree(
        revision_root / "export",
        revision_id=tree.revision,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
        source_defects=source_defects_for(tree.source_ref),
    )
    validate_generated_export_tree(
        context=GeneratedExportTreeValidationContext(
            registry_root=registry_root,
            source_root=bundled_path(),
            target=ExportFragmentTarget(
                modelo=tree.modelo,
                revision_id=tree.revision,
                design_epoch=tree.epoch,
            ),
            filing_year=tree.filing_year,
            period=tree.period,
            supporting_modelos=supporting_modelos(tree),
            continuity_metadata_modelo_root=continuity_metadata_modelo_root,
        ),
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
    )


@pytest.mark.parametrize("tree", _GENERATED_TREES, ids=str)
def test_committed_tree_is_reproducible_and_check_mode_refuses_only_for_its_named_reason(
    tree: GeneratedExportTree,
    tmp_path: Path,
) -> None:
    """The committed tree equals a fresh render, and check mode's verdict is pinned.

    Two questions, deliberately separated. Byte equality against a fresh render is
    answerable today and is the drift gate: an edited map, profile or design that
    is not accompanied by a regenerated tree reds here, and so does a hand-edited
    fragment.

    Whether the generator's own `check_generated_export_tree` PASSES is a stronger
    question, because it validates the candidate through the real registry
    authority and so demands a filing-complete, operator-reviewed revision. None of
    the committed trees has reached that yet. Rather than skip the call or soften
    it, the refusal is pinned to a named reason per tree, so the day a revision
    becomes reviewable this test fails and the pin has to be removed.
    """
    joined, semantic_map, transport, render_profile, evidence = isolated_authorities(tree)
    source_defects = source_defects_for(tree.source_ref)
    fresh_root = tmp_path / "fresh" / "export"

    # The refusal ledger is consulted BEFORE the render, not after it. A tree the
    # generator declines to render raises here, so a check placed after the call
    # could never run: the row would be unreachable and the gate would error
    # rather than report. The row must also name its cause, so a refusal that
    # changes reason is not silently absorbed by a pin written for another one.
    refusal = _RENDER_REFUSAL_DISPOSITIONS.get(f"{tree.modelo}/{tree.revision}")
    if refusal is not None:
        assert refusal.source_ref == tree.source_ref
        with pytest.raises(RegistryValidationError) as refused:
            render_complete_export_tree(
                fresh_root,
                revision_id=tree.revision,
                joined=joined,
                semantic_map=semantic_map,
                transport_profile=transport,
                render_profile=render_profile,
                render_profile_source_evidence=evidence,
                source_defects=source_defects,
            )
        assert refusal.refusal_marker in str(refused.value), (
            f"{tree}: render-refusal pin is dormant or its cause changed"
        )
        return

    render_complete_export_tree(
        fresh_root,
        revision_id=tree.revision,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
        source_defects=source_defects,
    )

    fresh_members = {path.name for path in fresh_root.iterdir()}
    # The fresh render above already succeeded, so reaching here with no committed tree
    # means the row is enrolled ahead of its publication rather than broken. Say that,
    # instead of letting iterdir raise FileNotFoundError: the row is the only staleness
    # detector the committed tree has, so the red must read as a tree owed and never
    # invite retiring the row to clear it.
    assert tree.committed.is_dir(), (
        f"{tree}: enrolled with no committed export tree at {tree.committed}, though the fresh "
        "render succeeded. Publish it through the generator's own publication authority; do not "
        "retire the row."
    )
    committed_members = {path.name for path in tree.committed.iterdir()}
    assert committed_members == fresh_members, (
        f"{tree}: committed export tree membership differs from a fresh render; "
        f"committed-only: {sorted(committed_members - fresh_members)}; "
        f"fresh-only: {sorted(fresh_members - committed_members)}"
    )
    byte_differing = sorted(
        name for name in fresh_members if not filecmp.cmp(fresh_root / name, tree.committed / name, shallow=False)
    )
    # A differing file whose parsed content is identical is a serializer change, not a
    # change to what the tree declares. The distinction is drawn by the one helper the
    # render comparison uses, so both surfaces agree on what "the same record" means.
    differing = [
        name
        for name in byte_differing
        if (parsed := parsed_tree_file(name, (tree.committed / name).read_bytes())) is None
        or parsed != parsed_tree_file(name, (fresh_root / name).read_bytes())
    ]
    subject = f"{tree.modelo}/{tree.revision}"
    if not differing and subject in _RECORD_DRIFT_DISPOSITIONS:
        # The row's whole worth is that it retires when its cause does, and the
        # dormancy check lived inside the drift branch - so it could never fire
        # on the case that matters: a repair SUCCEEDING. Twelve rows went dormant
        # unnoticed the moment their revisions were republished, and the gate
        # stayed green.
        raise AssertionError(
            f"{tree}: a record-drift disposition stands but the tree now reproduces from its "
            "inputs. The row is dormant and must be removed; an explanation cannot outlive its "
            "cause without becoming a permanent exemption nobody reads.",
        )

    if differing:
        disposition = _RECORD_DRIFT_DISPOSITIONS.get(subject)
        comparison = compare_revision_against_committed(
            compiled_bundled_authority(),
            modelo=tree.modelo,
            revision=tree.revision,
        )
        if disposition is not None:
            assert disposition.source_ref == tree.source_ref
            assert comparison.disposition_class == "record_drift", (
                f"{tree}: record-drift pin is dormant and must be removed"
            )
            # The row states HOW MUCH it explains, and that is checked here.
            # Asserting only that a difference exists let a row written for one
            # cause silently cover a second: modelo 390's rows were explaining
            # eighty type-column contradictions nobody had declared, and the
            # only reason it surfaced is that the rows were removed. A scope
            # that can grow without its wording changing is an exemption, not
            # an explanation.
            assert len(comparison.record_differing) == disposition.differing_records, (
                f"{tree}: row explains {disposition.differing_records} record(s), "
                f"the comparison reports {len(comparison.record_differing)}: "
                f"{sorted(comparison.record_differing)}. Re-derive the row rather than "
                "widening it; a second cause needs its own declaration."
            )
            return
        raise AssertionError(
            f"{tree}: committed export fragment(s) differ from a fresh render: {differing}; "
            f"differing manifest members: {list(comparison.provenance_fields)}"
        )

    candidate_root = tmp_path / "candidate"
    registry_root = isolated_authority(tree, candidate_root)
    continuity_metadata_modelo_root = stage_continuity_metadata(
        bundled_path("registry", "aeat", "modelos", tree.modelo),
        candidate_root,
        revision=tree.revision,
    )
    # The published layout load must see exactly the target revision, so a
    # multi-revision modelo is staged through the same isolation the CLI uses.
    published_modelo_root = stage_published_modelo(candidate_root, modelo=tree.modelo, revision=tree.revision)
    context = GeneratedExportTreeCheckContext(
        validation=GeneratedExportTreeValidationContext(
            registry_root=registry_root,
            source_root=bundled_path(),
            target=ExportFragmentTarget(
                modelo=tree.modelo,
                revision_id=tree.revision,
                design_epoch=tree.epoch,
            ),
            filing_year=tree.filing_year,
            period=tree.period,
            supporting_modelos=supporting_modelos(tree),
            continuity_metadata_modelo_root=continuity_metadata_modelo_root,
        ),
        temporary_root=candidate_root,
        target_registry_root=bundled_path("registry", "aeat"),
        target_export_root=tree.committed,
        published_modelo_root=published_modelo_root,
    )
    expected = _CHECK_MODE_PENDING.get(str(tree))
    try:
        checked = check_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=transport,
            render_profile=render_profile,
            render_profile_source_evidence=evidence,
            source_defects=source_defects,
        )
    except RegistryValidationError as refusal:
        assert expected is not None, f"{tree}: check mode refused with no pending reason recorded: {refusal}"
        assert expected in str(refusal), (
            f"{tree}: check mode refused for a reason other than the recorded {expected!r}: {refusal}"
        )
        return
    assert expected is None, (
        f"{tree}: check mode now PASSES, so the pending entry {expected!r} is stale -- remove it "
        "from _CHECK_MODE_PENDING and let this gate assert the pass"
    )
    assert str(checked.candidate.layout.id) == tree.layout_id


@pytest.mark.parametrize(
    ("tree", "expected_literals"),
    (
        (
            next(item for item in _GENERATED_TREES if str(item) == "m184-2023-2024"),
            ("m184-2023.entidad.f008", "E", "m184-2023.socio.f008", "S"),
        ),
        (
            next(item for item in _GENERATED_TREES if str(item) == "m184-2025-y-siguientes"),
            ("m184-2025.entidad.f008", "E", "m184-2025.socio.f008", "S"),
        ),
    ),
    ids=str,
)
def test_m184_sheet_type_literals_replace_the_blank_capable_casilla_path(
    tree: GeneratedExportTree,
    expected_literals: tuple[str, str, str, str],
    tmp_path: Path,
) -> None:
    """Both Tipo-2 record markers emit official bytes without a manual casilla path."""
    joined, semantic_map, transport, render_profile, evidence = isolated_authorities(tree)
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=tree.revision,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
    )
    fields = {field.id: field for record in rendered.layout.records for field in record.fields}
    entidad_id, entidad_literal, socio_id, socio_literal = expected_literals

    assert (
        fields[entidad_id].kind.value,
        fields[entidad_id].literal,
        fields[entidad_id].casilla_id,
        fields[entidad_id].required,
    ) == ("literal", entidad_literal, None, True)
    assert (
        fields[socio_id].kind.value,
        fields[socio_id].literal,
        fields[socio_id].casilla_id,
        fields[socio_id].required,
    ) == ("literal", socio_literal, None, True)

    revision = load_modelo_directory(bundled_path("registry", "aeat", "modelos", tree.modelo)).revisions[tree.revision]
    casillas = {str(casilla.id): casilla for casilla in revision.casillas}
    entidad_casilla = casillas["tipo2.tipo-hoja"]
    assert (entidad_casilla.input_kind.value, entidad_casilla.required, entidad_casilla.export_refs) == (
        "manual",
        False,
        (),
    )
    socio_casilla = casillas["tipo3.tipo-hoja"]
    assert (socio_casilla.input_kind.value, socio_casilla.required, socio_casilla.export_refs) == (
        "manual",
        False,
        (),
    )


def test_target_only_continuity_metadata_requires_real_declared_m303_siblings(tmp_path: Path) -> None:
    """A strict 2026 landing revision cannot validate against invented predecessors.

    The 2026 M303 target declares transitions from five real revisions.  It is
    the generic target-only isolation regression: the fresh candidate succeeds
    only when those source-copied predecessor metadata fragments are supplied;
    absent, missing, or structurally mismatched predecessor declarations still
    refuse through the ordinary strict-continuity validator.
    """
    tree = next(item for item in _GENERATED_TREES if item.modelo == "303" and item.revision == "2026-y-siguientes")
    joined, semantic_map, transport, render_profile, evidence = isolated_authorities(tree)
    candidate_root = tmp_path / "candidate"
    registry_root = isolated_authority(tree, candidate_root)
    metadata_modelo_root = stage_continuity_metadata(
        bundled_path("registry", "aeat", "modelos", tree.modelo),
        candidate_root,
        revision=tree.revision,
    )
    assert metadata_modelo_root is not None
    assert set(child.name for child in (metadata_modelo_root / "revisions").iterdir()) == {
        "2022",
        "2023",
        "2024-hasta-08-y-2t",
        "2024-desde-09-y-3t",
        "2025",
    }

    rendered = render_complete_export_tree(
        registry_root / "modelos" / tree.modelo / "revisions" / tree.revision / "export",
        revision_id=tree.revision,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
    )

    def validate(metadata_root: Path | None) -> None:
        validate_generated_export_tree(
            context=GeneratedExportTreeValidationContext(
                registry_root=registry_root,
                source_root=bundled_path(),
                target=ExportFragmentTarget(
                    modelo=tree.modelo,
                    revision_id=tree.revision,
                    design_epoch=tree.epoch,
                ),
                filing_year=tree.filing_year,
                period=tree.period,
                continuity_metadata_modelo_root=metadata_root,
            ),
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=evidence,
        )

    validate(metadata_modelo_root)

    with pytest.raises(RegistryValidationError, match="has no predecessor edition to continue"):
        validate(None)

    missing_metadata_root = tmp_path / "missing-metadata" / tree.modelo
    shutil.copytree(metadata_modelo_root, missing_metadata_root)
    shutil.rmtree(missing_metadata_root / "revisions" / "2022")
    with pytest.raises(RegistryValidationError, match="edition '2023' has no predecessor edition to continue"):
        validate(missing_metadata_root)

    mismatched_metadata_root = tmp_path / "mismatched-metadata" / tree.modelo
    shutil.copytree(metadata_modelo_root, mismatched_metadata_root)
    (mismatched_metadata_root / "revisions" / "2022").rename(
        mismatched_metadata_root / "revisions" / "mismatched-2022",
    )
    with pytest.raises(RegistryLoadError, match="declares '2022', expected 'mismatched-2022'"):
        validate(mismatched_metadata_root)


@pytest.mark.parametrize("tree", _GENERATED_TREES, ids=str)
def test_every_official_anchor_reaches_exactly_one_generated_field(tree: GeneratedExportTree) -> None:
    """The joined design bijects the official design, measured from the binary.

    Counts come from the parsed design, never from a constant: a blank slot in a
    fixed-width return is indistinguishable from a legitimately empty one once
    the bytes are written, so anchor coverage is proven against the source.
    """
    joined, _semantic_map, _transport, _profile, _evidence = isolated_authorities(tree)

    official_anchors = [
        (field.record_identity, field.offset) for record in joined.records for field in record.parser_sheet.fields
    ]
    assert len(official_anchors) == len(set(official_anchors)), f"{tree}: official anchors are not unique"
    covered_anchors = {
        (field.parser_field.record_identity, field.parser_field.offset)
        for record in joined.records
        for field in record.fields
    }
    assert covered_anchors == set(official_anchors), (
        f"{tree}: semantic entries do not cover exactly the official design anchors"
    )
    # A cell whose own text divides it reaches one field per declared part; every
    # slot, whole cell or part, reaches exactly one field.
    slots = [
        (field.parser_field.record_identity, design_view(field).offset)
        for record in joined.records
        for field in record.fields
    ]
    assert len(slots) == len(set(slots)), f"{tree}: a design slot reaches more than one generated field"
