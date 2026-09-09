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
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final, override

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.errors import (
    RegistryLoadError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.loader import (
    load_modelo_directory,
    load_registry_tree,
)
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection
from cadrumo.domain.calculations.registry.temporal import (
    coverage_assessment_horizon,
    revision_selection_coordinates,
)

from ..pipeline._export_tree import ExportTreeTransportProfile, render_complete_export_tree
from ..pipeline._tree_check import GeneratedExportTreeCheckContext, check_generated_export_tree
from ..pipeline._tree_validation import GeneratedExportTreeValidationContext, validate_generated_export_tree
from ..pipeline.candidate_staging import (
    generated_export_bootstrap_target,
    stage_continuity_metadata,
    stage_generated_export_candidate,
)
from ..pipeline.export_fragment_provenance import (
    ExportFragmentTarget,
    export_fragment_provenance_path,
    load_export_fragment_provenance_manifest,
)
from ..pipeline.joined_record_design import JoinedRecordDesign, join_record_design_semantics
from ..pipeline.record_design_intermediate import load_record_design_intermediate
from ..pipeline.render_check import (
    compare_revision_against_committed,
    parsed_tree_file,
    record_drift_dispositions,
    render_refusal_dispositions,
)
from ..pipeline.render_profile import (
    RenderProfile,
    RenderProfileSourceEvidence,
    load_render_profile,
    load_render_profile_source_evidence,
)
from ..pipeline.semantic_map import SemanticMap, load_semantic_map
from ..pipeline.source_defects import source_defects_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@dataclass(frozen=True)
class _GeneratedTree:
    """One committed generated export tree and the authorities that produce it."""

    modelo: str
    revision: str
    source_ref: str
    epoch: str
    filing_year: int
    period: str

    @property
    def layout_id(self) -> str:
        return f"generated-modelo-{self.modelo}-{self.revision}-fichero"

    @property
    def committed(self) -> Path:
        return bundled_path("registry", "aeat", "modelos", self.modelo, "revisions", self.revision, "export")

    @override
    def __str__(self) -> str:
        return f"m{self.modelo}-{self.revision}"


@dataclass(frozen=True)
class _ReproductionPendingPin:
    """One source-bound reason a semantically reproducible tree cannot yet be republished."""

    source_ref: str
    source_sha256: str
    reason: str
    reconsideration_condition: str
    check_mode_refusal: str


def _generated_trees() -> tuple[_GeneratedTree, ...]:
    """Project every provenance-attested tree from validated registry authority."""
    authority = bundled_authority()
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    trees: list[_GeneratedTree] = []
    for modelo in sorted(authority.modelos, key=lambda item: item.id):
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            export_root = bundled_path(
                "registry",
                "aeat",
                "modelos",
                str(modelo.id),
                "revisions",
                str(revision.id),
                "export",
            )
            manifest_path = export_fragment_provenance_path(export_root)
            if not manifest_path.is_file():
                continue
            manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
            if manifest.modelo != modelo.id or manifest.revision_id != revision.id:
                raise AssertionError(
                    "generated export provenance identity conflicts with its declared registry revision: "
                    f"{manifest_path}",
                )
            coordinates = revision_selection_coordinates(
                revision,
                assessment_horizon=assessment_horizon,
            )
            if not coordinates:
                raise AssertionError(f"generated tree {modelo.id}/{revision.id} has no law-selectable coordinate")
            filing_year, period = coordinates[0]
            trees.append(
                _GeneratedTree(
                    modelo=str(modelo.id),
                    revision=str(revision.id),
                    source_ref=str(manifest.source_ref),
                    epoch=manifest.design_epoch,
                    filing_year=filing_year,
                    period=period,
                )
            )
    if not trees:
        raise AssertionError("validated registry declares no provenance-attested generated export tree")
    return tuple(trees)


_GENERATED_TREES = _generated_trees()
_RECORD_DRIFT_DISPOSITIONS = {item.subject: item for item in record_drift_dispositions()}
_RENDER_REFUSAL_DISPOSITIONS = {item.subject: item for item in render_refusal_dispositions()}
_REPRODUCTION_PENDING = {
    "m185-2025-y-siguientes": _ReproductionPendingPin(
        source_ref="aeat-dr-185-2026",
        source_sha256="102dc91b4e9484b830c81e790cf08569be95e2854fee1138f63f363d35d2bcae",
        reason="revision earns applicability authority, below the publisher's calculation-grade floor",
        reconsideration_condition=(
            "Reconsider when the revision earns calculation authority or the generated tree is withdrawn."
        ),
        check_mode_refusal="cannot satisfy the requested 'filing' snapshot authority",
    ),
    "m222-2025-y-siguientes": _ReproductionPendingPin(
        source_ref="aeat-dr-222-2025",
        source_sha256="0a44cd6bcae3b6ecbdb7bba1e54ddfad519506b91545b655c8da8454a3a63f51",
        reason="revision earns applicability authority, below the publisher's calculation-grade floor",
        reconsideration_condition=(
            "Reconsider when the revision earns calculation authority or the generated tree is withdrawn."
        ),
        check_mode_refusal="cannot satisfy the requested 'filing' snapshot authority",
    ),
    "m202-2019-2022": _ReproductionPendingPin(
        source_ref="aeat-dr-202-2019",
        source_sha256="96160cf2a82a4e6f2c9c9848c6061b2cfe5c4877de7a455126704af86f3ac7db",
        reason="isolated validation makes cross-revision singleton semantic roles appear on exactly one casilla",
        reconsideration_condition="Reconsider when generated validation preserves Modelo 202 cross-revision facts.",
        check_mode_refusal="appears on exactly one casilla",
    ),
    "m202-2023-2024": _ReproductionPendingPin(
        source_ref="aeat-dr-202-2023",
        source_sha256="1e4881439e25417df5a8584bffd7149ca0952e2df53963b19c0346572259bec7",
        reason="isolated validation makes cross-revision singleton semantic roles appear on exactly one casilla",
        reconsideration_condition="Reconsider when generated validation preserves Modelo 202 cross-revision facts.",
        check_mode_refusal="appears on exactly one casilla",
    ),
    "m202-2025-y-siguientes": _ReproductionPendingPin(
        source_ref="aeat-dr-202-2025",
        source_sha256="04e7b349b24b982d985195d4ae38b68e72e75d606cf66c7ef30b62b281c7f82c",
        reason="isolated validation loses exact source-revision coverage needed by the cross-modelo relation",
        reconsideration_condition="Reconsider when generated validation preserves Modelo 202 cross-revision facts.",
        check_mode_refusal="lacks exact source revision coverage",
    ),
    "m303-2022": _ReproductionPendingPin(
        source_ref="aeat-dr-303-2022",
        source_sha256="6648f6b319579e49cd5bfdaae69e7451db75767e7f19da0b90383b25b79b3f60",
        reason=(
            "the committed attestation predates current record serialization, while attempted republication is "
            "refused because generated DP30305 fields lack matching casilla export_refs in isolated validation"
        ),
        reconsideration_condition=(
            "Reconsider when every generated field is declared by its owning casilla and the tree can be republished."
        ),
        check_mode_refusal="export provenance output-file digests do not match generated tree",
    ),
    "m303-2023": _ReproductionPendingPin(
        source_ref="aeat-dr-303-2023",
        source_sha256="72e463cb29984f535c9f56917d788ff0641965f116aeab47da5f76a59eecfbe4",
        reason=(
            "the committed attestation predates current record serialization, while attempted republication is "
            "refused because generated DP30305 fields lack matching casilla export_refs in isolated validation"
        ),
        reconsideration_condition=(
            "Reconsider when every generated field is declared by its owning casilla and the tree can be republished."
        ),
        check_mode_refusal="export provenance output-file digests do not match generated tree",
    ),
    "m303-2024-desde-09-y-3t": _ReproductionPendingPin(
        source_ref="aeat-dr-303-2024-late",
        source_sha256="2095dd633413f4aed28053bc88402461d80865f454156c01ebc4a2ab68cb76a8",
        reason=(
            "the committed attestation predates current record serialization, while attempted republication is "
            "refused because generated DP30305 fields lack matching casilla export_refs in isolated validation"
        ),
        reconsideration_condition=(
            "Reconsider when every generated field is declared by its owning casilla and the tree can be republished."
        ),
        check_mode_refusal="export provenance output-file digests do not match generated tree",
    ),
    "m303-2024-hasta-08-y-2t": _ReproductionPendingPin(
        source_ref="aeat-dr-303-2024-early",
        source_sha256="8b1f74b58b9293e60f9ea6fa3cc352a35ca3fe7d09a6705f122585e7f7da65b9",
        reason=(
            "the committed attestation predates current record serialization, while attempted republication is "
            "refused because generated DP30305 fields lack matching casilla export_refs in isolated validation"
        ),
        reconsideration_condition=(
            "Reconsider when every generated field is declared by its owning casilla and the tree can be republished."
        ),
        check_mode_refusal="export provenance output-file digests do not match generated tree",
    ),
    "m303-2025": _ReproductionPendingPin(
        source_ref="aeat-dr-303-2025",
        source_sha256="6c3d7eeb714e0deb52f91d7e8dbadeb83f16c1d32d25f9e871756f3ddf0117e6",
        reason=(
            "the committed attestation predates current record serialization, while attempted republication is "
            "refused because generated DP30305 fields lack matching casilla export_refs in isolated validation"
        ),
        reconsideration_condition=(
            "Reconsider when every generated field is declared by its owning casilla and the tree can be republished."
        ),
        check_mode_refusal="export provenance output-file digests do not match generated tree",
    ),
    "m303-2026-y-siguientes": _ReproductionPendingPin(
        source_ref="aeat-dr-303-2026",
        source_sha256="0be8b156da2250c6b11f6253e0165221ed2e549ec4c65a562021bec6b9b8489b",
        reason=(
            "the committed attestation predates current record serialization, while attempted republication is "
            "refused because generated DP30305 fields lack matching casilla export_refs in isolated validation"
        ),
        reconsideration_condition=(
            "Reconsider when every generated field is declared by its owning casilla and the tree can be republished."
        ),
        check_mode_refusal="export provenance output-file digests do not match generated tree",
    ),
}


def _isolated_authority(tree: _GeneratedTree, root: Path) -> Path:
    """Copy the target's authored NON-export authority into an isolated root.

    The export directory is deliberately never copied: check mode renders the
    candidate afresh, so copying one would let a stale tree validate itself.
    """
    registry_root = root / "registry" / "aeat"
    supporting_modelos = _supporting_modelos(tree)
    source = next(
        (item for ref, item in bundled_authority().catalogues.sources.items() if str(ref) == tree.source_ref),
        None,
    )
    assert source is not None, f"{tree}: declared render source {tree.source_ref!r} is absent"
    bootstrap_target = generated_export_bootstrap_target(
        modelo=tree.modelo,
        revision=tree.revision,
        source_ref=tree.source_ref,
        source_sha256=source.sha256,
    )
    modelo_root = stage_generated_export_candidate(
        bundled_path("registry", "aeat"),
        registry_root,
        modelo=tree.modelo,
        revision=tree.revision,
        supporting_modelos=supporting_modelos,
        bootstrap_target=bootstrap_target,
    )
    assert not (modelo_root / "revisions" / tree.revision / "export").exists(), (
        f"{tree}: the isolated candidate must not carry a copied export tree"
    )
    assert not (modelo_root / "revisions" / tree.revision / "export_layouts").exists(), (
        f"{tree}: the isolated candidate must not carry a copied superseded manual export tree"
    )
    return registry_root


#: How a revision names another modelo it folds a value in from.
_SOURCE_MODELO_RE: Final[re.Pattern[str]] = re.compile(r'^\s*source_modelo\s*=\s*"(?P<modelo>[^"]+)"', re.MULTILINE)


def _supporting_modelos(tree: _GeneratedTree) -> frozenset[str]:
    """The modelos staged beside the target because the target folds them in."""
    referenced = _referenced_modelos(bundled_path("registry", "aeat", "modelos", tree.modelo))
    return frozenset(
        modelo for modelo in referenced - {tree.modelo} if bundled_path("registry", "aeat", "modelos", modelo).is_dir()
    )


def _referenced_modelos(modelo_root: Path) -> frozenset[str]:
    found: set[str] = set()
    for path in modelo_root.rglob("*.toml"):
        for match in _SOURCE_MODELO_RE.finditer(path.read_text(encoding="utf-8")):
            modelo = match.group("modelo")
            assert isinstance(modelo, str), "the named group always participates in this pattern"
            found.add(modelo)
    return frozenset(found)


def _authorities(
    tree: _GeneratedTree,
) -> tuple[SemanticMap, RenderProfile, JoinedRecordDesign, RenderProfileSourceEvidence, ExportTreeTransportProfile]:
    semantic_map = load_semantic_map(Path(f"dev/registry/mappings/modelo_{tree.modelo}") / tree.epoch)
    render_profile = load_render_profile(Path(f"dev/registry/render_profiles/modelo_{tree.modelo}") / tree.epoch)
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if str(m.id) == tree.modelo)
    inspection = RegistryRevisionInspection.from_revision(
        modelo=modelo,
        revision=modelo.revisions[tree.revision],
        source_root=bundled_path(),
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )
    intermediate = load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=tree.source_ref,
        filing_year=tree.filing_year,
        design_epoch=tree.epoch,
    )
    joined = join_record_design_semantics(semantic_map, intermediate, inspection)
    transport = ExportTreeTransportProfile(
        modelo=tree.modelo,
        design_epoch=tree.epoch,
        source_ref=tree.source_ref,
        source_sha256=intermediate.source.source_sha256,
        layout_id=tree.layout_id,
        format="fixed_width",
        encoding=ExportEncoding.ISO_8859_1,
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )
    # A rule of either kind may claim an official cell, and such a claim only
    # validates against text actually read back out of the hash-verified design
    # binary. A profile whose every rule is a reviewed policy claims no cell, and
    # reading the workbook for it would be both pointless and a refusal for a
    # design that is not a workbook at all.
    claims_official = any(
        rule.evidence.authority_kind != "reviewed_policy"
        for rule in (*render_profile.singleton_rules, *render_profile.width_17_rules)
    )
    evidence = (
        load_render_profile_source_evidence(
            bundled_path() / catalogues.sources[tree.source_ref].corpus_path, render_profile
        )
        if claims_official
        else RenderProfileSourceEvidence(design_identity=render_profile.design_identity, entries=())
    )
    return semantic_map, render_profile, joined, evidence, transport


#: Check mode's exact current refusal, projected from the same source-bound pins
#: that govern pending republication. A changed refusal makes the owning row red.
_CHECK_MODE_PENDING: dict[str, str] = {
    subject: pin.check_mode_refusal for subject, pin in _REPRODUCTION_PENDING.items()
}


def test_every_pending_check_mode_entry_names_an_enrolled_tree() -> None:
    """A pending reason keyed to no row is unreachable, and unreachable is invisible.

    ``_CHECK_MODE_PENDING`` is keyed by ``str(_GeneratedTree)``, which embeds the
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


def test_every_reproduction_pending_pin_is_live_and_source_bound() -> None:
    """A publication exclusion names current evidence and retires when its cause does."""
    enrolled = {str(tree): tree for tree in _GENERATED_TREES}
    assert set(_REPRODUCTION_PENDING) <= set(enrolled), (
        f"reproduction pins name no enrolled tree: {sorted(set(_REPRODUCTION_PENDING) - set(enrolled))}"
    )
    authority = bundled_authority()
    for subject, pin in _REPRODUCTION_PENDING.items():
        tree = enrolled[subject]
        assert tree.source_ref == pin.source_ref
        source = authority.catalogues.sources.get(pin.source_ref)
        assert source is not None
        assert source.sha256 == pin.source_sha256, f"{subject}: source was reissued; reconsider the pin"
        assert pin.reason.strip() and pin.reconsideration_condition.strip()
        # A tree the generator REFUSES has no disposition class to be live or
        # dormant against: comparing it would re-render and raise. The refusal
        # supersedes the reproduction pin while it stands, so the pin is checked
        # for source-binding above and its class check resumes the day the
        # refusal retires. The refusal row is asserted source-bound in its place,
        # so the pin is superseded by a declaration and never merely unchecked.
        refusal = _RENDER_REFUSAL_DISPOSITIONS.get(subject)
        if refusal is not None:
            assert refusal.source_ref == pin.source_ref
            assert refusal.source_sha256 == pin.source_sha256
            continue
        comparison = compare_revision_against_committed(
            authority,
            modelo=tree.modelo,
            revision=tree.revision,
        )
        assert comparison.disposition_class == "provenance_only", (
            f"{subject}: reproduction pin is dormant or its failure class changed"
        )


def test_m390_isolation_excludes_both_export_authorities_and_keeps_required_support(tmp_path: Path) -> None:
    """The enrolled-tree harness renders without copying either export authority."""
    tree = next(item for item in _GENERATED_TREES if item.modelo == "390" and item.revision == "2022")

    registry_root = _isolated_authority(tree, tmp_path)
    revision_root = registry_root / "modelos" / "390" / "revisions" / "2022"

    assert not (revision_root / "export").exists()
    assert not (revision_root / "export_layouts").exists()
    assert (registry_root / "m303_orden_anual" / "manifest.toml").is_file()
    construct_text = (revision_root / "constructs" / "0001-constructs.toml").read_text(encoding="utf-8")
    assert "modelo-390-2022-fichero-boe" not in construct_text
    assert "generated-modelo-390-2022-fichero" in construct_text

    semantic_map, render_profile, joined, evidence, transport = _authorities(tree)

    # This revision carries a render-refusal disposition: its official type column
    # declares signed amounts whose representation is not grounded. The isolation
    # property this test owns -- that the harness supplies everything a render
    # needs WITHOUT copying either export authority -- is asserted above and is
    # unaffected. The render is asserted to refuse for THAT declared cause, so
    # this still fails if the harness breaks or if the refusal changes reason.
    #
    # GIVEN UP while the disposition stands: that the rendered tree then passes
    # `validate_generated_export_tree` under the isolated root. That assertion
    # needs a tree that renders, and every revision of this modelo now refuses.
    # It is re-established on a rendering tree rather than left unowned.
    refusal = _RENDER_REFUSAL_DISPOSITIONS[f"{tree.modelo}/{tree.revision}"]
    with pytest.raises(RegistryValidationError) as refused:
        render_complete_export_tree(
            revision_root / "export",
            revision_id=tree.revision,
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=transport,
            render_profile=render_profile,
            render_profile_source_evidence=evidence,
            source_defects=source_defects_for(tree.source_ref),
        )
    assert refusal.refusal_marker in str(refused.value)


def test_target_only_continuity_metadata_requires_real_declared_m303_siblings(tmp_path: Path) -> None:
    """A strict landing revision cannot validate against invented predecessors.

    The generic target-only isolation regression: the fresh candidate succeeds
    only when the source-copied predecessor metadata fragments are supplied;
    absent, missing, or structurally mismatched predecessor declarations still
    refuse through the ordinary strict-continuity validator.

    Carried by the periodic-instalment modelo because it renders. The quarterly
    IVA modelo, whose 2026 target declares transitions from five real revisions
    and which this regression used to ride on, now carries a render-refusal
    disposition on every revision, so it cannot supply a rendered tree. GIVEN UP
    while that disposition stands: the five-predecessor breadth of that instance.
    The property itself is unchanged and is asserted here.
    """
    tree = next(item for item in _GENERATED_TREES if item.modelo == "353" and item.revision.startswith("2026"))
    semantic_map, render_profile, joined, evidence, transport = _authorities(tree)
    candidate_root = tmp_path / "candidate"
    registry_root = _isolated_authority(tree, candidate_root)
    metadata_modelo_root = stage_continuity_metadata(
        bundled_path("registry", "aeat", "modelos", tree.modelo),
        candidate_root,
        revision=tree.revision,
    )
    assert metadata_modelo_root is not None
    staged = set(child.name for child in (metadata_modelo_root / "revisions").iterdir())
    assert staged, "target-only staging supplied no predecessor metadata"
    assert tree.revision not in staged, "the target must not stage itself as its own predecessor"

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

    with pytest.raises(
        RegistryValidationError, match="evolution references a revision that the modelo does not declare"
    ):
        validate(None)

    missing_metadata_root = tmp_path / "missing-metadata" / tree.modelo
    shutil.copytree(metadata_modelo_root, missing_metadata_root)
    shutil.rmtree(missing_metadata_root / "revisions" / "2022")
    with pytest.raises(
        RegistryValidationError, match="evolution references a revision that the modelo does not declare"
    ):
        validate(missing_metadata_root)

    mismatched_metadata_root = tmp_path / "mismatched-metadata" / tree.modelo
    shutil.copytree(metadata_modelo_root, mismatched_metadata_root)
    (mismatched_metadata_root / "revisions" / "2022").rename(
        mismatched_metadata_root / "revisions" / "mismatched-2022",
    )
    with pytest.raises(RegistryLoadError, match="declares '2022', expected 'mismatched-2022'"):
        validate(mismatched_metadata_root)


@pytest.mark.parametrize("tree", _GENERATED_TREES, ids=str)
def test_every_official_anchor_reaches_exactly_one_generated_field(tree: _GeneratedTree) -> None:
    """The joined design bijects the official design, measured from the binary.

    Counts come from the parsed design, never from a constant: a blank slot in a
    fixed-width return is indistinguishable from a legitimately empty one once
    the bytes are written, so anchor coverage is proven against the source.
    """
    _semantic_map, _profile, joined, _evidence, _transport = _authorities(tree)

    official_anchors = [
        (field.parser_field.record_identity, field.parser_field.offset)
        for record in joined.records
        for field in record.fields
    ]
    assert len(official_anchors) == len(set(official_anchors)), f"{tree}: official anchors are not unique"
    mapped_anchors = [
        (entry.anchor.record_identity, field.parser_field.offset)
        for record in joined.records
        for field in record.fields
        for entry in (field.semantic_entry,)
    ]
    assert sorted(mapped_anchors) == sorted(official_anchors), (
        f"{tree}: semantic entries do not biject the official design anchors"
    )
