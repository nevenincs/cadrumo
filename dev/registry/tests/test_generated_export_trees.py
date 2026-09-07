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
from ..pipeline._provenance_manifest import (
    ExportFragmentTarget,
    export_fragment_provenance_path,
    load_export_fragment_provenance_manifest,
)
from ..pipeline._record_design_ir import load_record_design_intermediate
from ..pipeline._render_profile import (
    RenderProfileSourceEvidence,
    load_render_profile,
    load_render_profile_source_evidence,
)
from ..pipeline._semantic_map_join import join_record_design_semantics
from ..pipeline._semantic_map_loader import load_semantic_map
from ..pipeline._tree_check import GeneratedExportTreeCheckContext, check_generated_export_tree
from ..pipeline._tree_validation import GeneratedExportTreeValidationContext, validate_generated_export_tree
from ..pipeline.candidate_staging import (
    generated_export_bootstrap_target,
    stage_continuity_metadata,
    stage_generated_export_candidate,
)
from ..pipeline.render_check import parsed_tree_file
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
    return frozenset(
        match.group("modelo")
        for path in modelo_root.rglob("*.toml")
        for match in _SOURCE_MODELO_RE.finditer(path.read_text(encoding="utf-8"))
    )


def _authorities(tree: _GeneratedTree):
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
    # A width-17 membership rule REQUIRES official-source evidence by schema, so
    # a profile carrying one only validates against text actually read back out
    # of the hash-verified design binary. A profile whose every rule is a
    # reviewed policy claims no cell, and reading the workbook for it would be
    # both pointless and a refusal, since the resolver rejects an empty claim set.
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


#: Why check mode cannot yet pass for a committed tree, per tree. Check mode runs
#: the FULL candidate validation, so it demands a filing-complete revision, not
#: merely a correctly generated layout. Each entry names the outstanding
#: precondition; an entry that stops being true fails, which is what forces this
#: gate to be upgraded rather than left permanently soft.
_CHECK_MODE_PENDING: dict[str, str] = {
    # Both 232 revisions validate on every family now -- the reserved-byte
    # defect is fixed and the DR23200 auxiliary header is emitted through the
    # typed prefix contract -- so what check mode still refuses is the
    # unreviewed revision itself, the same wall m210 sits behind.
    # 353 and 322 both validate on every revision now, including 322's 2008-2025
    # export layout, which was the last authoring gap either of them had. What
    # check mode still refuses is `review_status = "pending_review"` on the
    # revision itself: a filing-grade snapshot requires a REVIEWED revision, and
    # that stamp is a human tax reviewer's to make against official sources, not
    # an authoring step. It is the same wall m210 sits behind.
    # 202 is the one tree blocked by a NEIGHBOUR rather than by itself. Its
    # candidate registry has to carry modelo 200 -- 202's pagos fraccionados are
    # the Sociedades annual return's instalments, so 200 is a supporting modelo
    # the isolation must admit -- and 200 declares no export layout at all while
    # claiming filing grade. Pinning 200's own refusal rather than the generic
    # envelope keeps the entry honest: the day 200's layout lands, this fails and
    # 202's remaining blocker (its per-revision singleton semantic roles, present
    # at HEAD and untouched by the layout work) has to be looked at on its own.
    #
    # 200's layout HAS now landed, and the entry above did its job: these three
    # rows failed the moment it did. What they were shadowing turns out to be one
    # thing, and it is NOT a modelo 202 data defect -- both reasons below are
    # produced by this test's own isolation.
    #
    # The candidate registry keeps EXACTLY the target revision and prunes every
    # sibling, because a sibling makes the revision selection ambiguous. Modelo
    # 202 has three revisions, and both facts these rows trip on span them:
    #
    #   - the singleton semantic roles are singletons only after pruning.
    #     `is_pf_mod_40_2_base_pago_fraccionado` is declared once in EACH of
    #     202's three revisions, so the full registry sees three observations and
    #     the typo check never fires.
    #   - 200's relation to 202's pagos fraccionados folds source year 2024 at
    #     filing_year_delta 0, which needs 202's `2023-2024` revision -- the one
    #     the isolation just deleted.
    #
    # The control is the full authority, which loads CLEAN with all three
    # revisions present. So these pins record a harness limitation: a
    # cross-revision fact cannot be validated under an isolation that keeps one
    # revision. Do not go looking for the defect in 202's casillas; it is not
    # there.
    # This pins `pending_review`, and a SECOND defect is known to sit behind
    # it and is recorded here so clearing the stamp does not lose it. Each cites a
    # source whose applicability window does not overlap its own life, which was
    # observed directly by stamping the revision, watching check mode refuse on
    # the window instead, and then removing the stamp again:
    #
    #   353/2008-2025  cites 2026 contribuyente calendars; revision ends 2025-12-31
    #   322/2008-2025  cites a 2026 calendar; same shape
    #   151/2015-2022  RESOLVED, and the note is kept only so the next reader
    #                  does not go looking. It formerly cited the 2023 diseno on
    #                  six casillas its own 2015-rendered tree does not address.
    #                  Re-measured at HEAD: every source_ref reachable from the
    #                  revision -- casillas, layout, and every record field -- is
    #                  `aeat-dr-151-2015`, and the string "151-2023" appears
    #                  nowhere in the revision tree. Only the two window rows
    #                  above remain live.
    #
    # Whoever stamps one of these must expect the window refusal next, and fix it
    # rather than re-pin it.
    # 185 and 222 are STALE grades, not wrong ones. Each revision carries a
    # human applicability review stamped 2026-08-21 recording "no export layout
    # of either kind is declared" and reaching "scheduling and applicability
    # only". The generated export-tree installs (5bff9d5332e for 185,
    # 8fdb80c99f6 for 222) then landed a fixed_width layout and the casillas
    # WITHOUT touching revision.toml, so measured at HEAD both statements are
    # false: 185 declares 21 casillas and one layout, 222 declares 76 and one.
    #
    # The enrolment is not the wrong half: all 21 enrolled rows declare exactly
    # one export layout, and the grade enum itself states that "an informative
    # modelo carrying export layouts and no formulas can legitimately reach
    # FILING". Promotion is an attestation no program may make, so these stay
    # red until a human tax reviewer raises them. The entries retire themselves
    # on that attestation.
    "m185-2025-y-siguientes": "cannot satisfy the requested 'filing' snapshot authority",
    "m222-2025-y-siguientes": "cannot satisfy the requested 'filing' snapshot authority",
    # 232 is not a grade or data defect -- it validates cleanly at BOTH
    "m202-2019-2022": "appears on exactly one casilla",
    "m202-2023-2024": "appears on exactly one casilla",
    "m202-2025-y-siguientes": "lacks exact source revision coverage",
    # Both 151 revisions resolve every enrolled family and validate through the
    # real authority, so what is left is the reviewer stamp -- the same wall
    # m210, m322 and m353 sit behind. Worth noting for whoever reviews them: the
    # 2015-2022 layout was a hand transcription before the generated tree became
    # authoritative, and it was
    # two positions SHORT of AEAT's own envelope, omitting the AUX block's
    # programa and NIF-desarrollo fields. The generated tree carries both.
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
    assert differing == [], f"{tree}: committed export fragment(s) differ from a fresh render: {differing}"

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
