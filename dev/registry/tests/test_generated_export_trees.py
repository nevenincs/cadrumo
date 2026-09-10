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
from dev.registry.maintenance_support import coverage_assessment_horizon, revision_selection_coordinates

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
    """The modelos staged beside the target because the target depends on them.

    A revision folds a value in from another modelo, and the source declaration
    names it. Governed-fact projections are deliberately NOT included: their two
    target modelos pull a transitive closure of nineteen, which is very nearly
    the whole registry, so staging them would leave a candidate containing every
    modelo and the isolation this set exists to create would mean nothing. That
    dependency is answered where it arises, in fact compilation.
    """
    referenced = _referenced_modelos(bundled_path("registry", "aeat", "modelos", tree.modelo))
    depended_on = referenced - {tree.modelo}
    return frozenset(
        modelo for modelo in depended_on if bundled_path("registry", "aeat", "modelos", modelo).is_dir()
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
        # A pin states that a tree differs from a fresh render only in its
        # attestation. Once the tree also differs in its RECORDS it has a
        # disposition row saying so, and that row is the stronger statement:
        # source-pinned, self-retiring, and consulted by the reproduction gate
        # before the pin ever is. The pin is not deleted, because it still
        # carries the check-mode refusal this suite expects, but its class
        # assertion defers to the disposition and resumes the day the row
        # retires. The row is asserted source-bound in its place, so the pin is
        # superseded by a declaration rather than left merely unchecked.
        comparison = compare_revision_against_committed(
            authority,
            modelo=tree.modelo,
            revision=tree.revision,
        )
        # The pin table is keyed by the tree's own name; the ledger is keyed by
        # modelo/revision. Look the row up the way the ledger spells it.
        disposition = _RECORD_DRIFT_DISPOSITIONS.get(f"{tree.modelo}/{tree.revision}")
        if disposition is not None:
            assert disposition.source_ref == pin.source_ref
            assert disposition.source_sha256 == pin.source_sha256
            assert comparison.disposition_class == "record_drift", (
                f"{subject}: a disposition row stands but the tree no longer drifts in its records"
            )
            continue
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
            supporting_modelos=_supporting_modelos(tree),
        ),
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
    )


@pytest.mark.parametrize("tree", _GENERATED_TREES, ids=str)
def test_committed_tree_is_reproducible_and_check_mode_refuses_only_for_its_named_reason(
    tree: _GeneratedTree,
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
    semantic_map, render_profile, joined, evidence, transport = _authorities(tree)
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
            bundled_authority(),
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
        reproduction_pin = _REPRODUCTION_PENDING.get(str(tree))
        assert reproduction_pin is not None, (
            f"{tree}: committed export fragment(s) differ from a fresh render: {differing}"
        )
        assert reproduction_pin.source_ref == tree.source_ref
        assert comparison.disposition_class == "provenance_only", (
            f"{tree}: reproduction pin is dormant or its failure class changed"
        )

    candidate_root = tmp_path / "candidate"
    registry_root = _isolated_authority(tree, candidate_root)
    continuity_metadata_modelo_root = stage_continuity_metadata(
        bundled_path("registry", "aeat", "modelos", tree.modelo),
        candidate_root,
        revision=tree.revision,
    )
    published_modelo_root: Path | None = None
    revisions_root = bundled_path("registry", "aeat", "modelos", tree.modelo, "revisions")
    if len(tuple(revisions_root.iterdir())) > 1:
        # The published layout load must see exactly the target revision, and
        # a multi-revision modelo publishes several, so the test stages the
        # published copy with siblings pruned -- check mode copies nothing.
        published_modelo_root = candidate_root / "published-registry" / "aeat" / "modelos" / tree.modelo
        shutil.copytree(
            bundled_path("registry", "aeat", "modelos", tree.modelo),
            published_modelo_root,
            dirs_exist_ok=True,
        )
        for sibling in (published_modelo_root / "revisions").iterdir():
            if sibling.name != tree.revision:
                shutil.rmtree(sibling)
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
            supporting_modelos=_supporting_modelos(tree),
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
    tree: _GeneratedTree,
    expected_literals: tuple[str, str, str, str],
    tmp_path: Path,
) -> None:
    """Both Tipo-2 record markers emit official bytes without a manual casilla path."""
    semantic_map, render_profile, joined, evidence, transport = _authorities(tree)
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
    semantic_map, render_profile, joined, evidence, transport = _authorities(tree)
    candidate_root = tmp_path / "candidate"
    registry_root = _isolated_authority(tree, candidate_root)
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
