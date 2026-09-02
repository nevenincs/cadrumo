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

Each generated modelo is enrolled as a row in :data:`_GENERATED_TREES`, and a
row whose published design contradicts itself carries an adjudication in
:data:`_SOURCE_DEFECTS` keyed by the source file it describes.
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

from ..pipeline._export_tree import ExportTreeTransportProfile, render_complete_export_tree
from ..pipeline._provenance_manifest import ExportFragmentTarget
from ..pipeline._record_design_ir import load_record_design_intermediate
from ..pipeline._render_profile import (
    RenderProfileSourceEvidence,
    load_render_profile,
    load_render_profile_source_evidence,
)
from ..pipeline._semantic_map_join import join_record_design_semantics
from ..pipeline._semantic_map_loader import load_semantic_map
from ..pipeline._source_defects import SourceDefectDeclaration
from ..pipeline._tree_check import GeneratedExportTreeCheckContext, check_generated_export_tree
from ..pipeline._tree_validation import GeneratedExportTreeValidationContext, validate_generated_export_tree
from ..pipeline.render_check import parsed_tree_file

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


_GENERATED_TREES: tuple[_GeneratedTree, ...] = (
    _GeneratedTree("210", "2025", "aeat-dr-210-2022", "2022", 2025, "0A"),
    _GeneratedTree("232", "2018-y-siguientes", "aeat-dr-232-2018", "2018", 2018, "0A"),
    _GeneratedTree("232", "2016-2017", "aeat-dr-232-2016", "2016", 2016, "0A"),
    _GeneratedTree("353", "2026-desde-02", "aeat-dr-353-2026", "2026", 2026, "02"),
    _GeneratedTree("353", "2021-2025", "aeat-dr-353-2021-2025", "2021", 2021, "01"),
    # Split at the 2023/2024 re-layout, where the 2024 design adds nine
    # fields and revives DR32201 offset 1311 out of reserved space. The
    # earlier 2022/2023 boundary is NOT split: no key pairs those two
    # designs totally, so 2008-2022 still emits the 2023 layout.
    _GeneratedTree("322", "2008-2022", "aeat-dr-322-2022", "2022", 2022, "01"),
    _GeneratedTree("322", "2023", "aeat-dr-322-2023", "2023", 2023, "01"),
    _GeneratedTree("322", "2024-2025", "aeat-dr-322-2024-2025", "2024", 2024, "01"),
    _GeneratedTree("202", "2019-2022", "aeat-dr-202-2019", "2019", 2019, "1P"),
    _GeneratedTree("202", "2023-2024", "aeat-dr-202-2023", "2023", 2023, "1P"),
    _GeneratedTree("202", "2025-y-siguientes", "aeat-dr-202-2025", "2025", 2025, "1P"),
    _GeneratedTree("151", "2015-2022", "aeat-dr-151-2015", "2015", 2015, "0A"),
    _GeneratedTree("151", "2025-y-siguientes", "aeat-dr-151-2023", "2023", 2023, "0A"),
    # Split at Orden HAC/1430/2025 art. cuarto, which introduces NUMERO TOTAL DE
    # REGISTROS DE ENTIDAD at 221-229 of tipo 1 and is applicable for the first
    # time to ejercicio 2025. One revision carries one layout, so the years
    # before that boundary emit the 2023 design and the years after it the 2025.
    _GeneratedTree("184", "2023-2024", "aeat-dr-184-2023-2024", "2023", 2024, "0A"),
    _GeneratedTree("184", "2025-y-siguientes", "aeat-dr-184-2025", "2025", 2025, "0A"),
    # Enrolled late, and its absence is why its map went stale unnoticed: 347 was
    # published without a row here, so nothing compared its committed tree against a
    # fresh render, and two anchors kept naming parent rows the parser had already
    # descended past.
    # Split at the 2024/2025 boundary. The 2011 epoch was derivable because
    # 347's printed ordinal IS a box identity (unlike modelo 322, where it is
    # a contiguous position); the 2008 and 2010 designs pair with nothing, so
    # 2008-2010 still emits the 2011 layout and keeps reporting.
    _GeneratedTree("347", "2011-2024", "aeat-dr-347-2011", "2011", 2011, "0A"),
    _GeneratedTree("347", "2025-y-siguientes", "aeat-dr-347-2025", "2025", 2025, "0A"),
    # Enrolled with the layout, not after it, which is the whole lesson of the 347
    # entry above: a published tree that nothing compares against a fresh render
    # is free to drift, and 347's map did exactly that unnoticed.
    # The revision reads 2025-y-siguientes, not 2024: aeat-dr-200-2025 carries
    # record_design_epoch "2025" and applies_from 2025-01-01, and 2025-y-siguientes is
    # the only revision declaring it among its revision-level source_refs. Pairing that
    # design with the ejercicio-2024 revision asserted the 2025 layout for 2024 -- the
    # wrong-year pairing this row exists to catch. Revision 2024 has its own reviewed
    # design (aeat-dr-200-2024, epoch 2024, applies_to 2024-12-31) and a full parsed
    # mapping set, and owes an enrolment row of its own once its tree is rendered.
    _GeneratedTree("200", "2025-y-siguientes", "aeat-dr-200-2025", "2025", 2025, "0A"),
    _GeneratedTree("296", "2024-y-siguientes", "aeat-dr-296-2024", "2024", 2024, "0A"),
    # Enrolled in the same change that authored the layout, per the m347 entry
    # above. Modelo 185 is monthly, so its period is a month code rather than
    # the annual "0A" every other row here carries.
    _GeneratedTree("185", "2025-y-siguientes", "aeat-dr-185-2026", "2026", 2026, "01"),
    # Enrolled with the layout. Modelo 222 is the consolidacion twin of 202 and
    # shares its orden and its DR222_00 envelope grammar, so it carries 202's
    # supporting-modelo needs too: the isolation must admit modelo 200, whose
    # annual IS return these pagos fraccionados are instalments of.
    _GeneratedTree("222", "2025-y-siguientes", "aeat-dr-222-2025", "2025", 2025, "1P"),
    # The selected five source-bound M303 epochs.  The 2022 layout is out of
    # scope here; the superseded 2023-y-siguientes revision is not a
    # generated-tree fallback and must never re-enter this set.
    _GeneratedTree("303", "2023", "aeat-dr-303-2023", "2023", 2023, "4T"),
    _GeneratedTree("303", "2024-hasta-08-y-2t", "aeat-dr-303-2024-early", "2024-early", 2024, "2T"),
    _GeneratedTree("303", "2024-desde-09-y-3t", "aeat-dr-303-2024-late", "2024-late", 2024, "3T"),
    _GeneratedTree("303", "2025", "aeat-dr-303-2025", "2025", 2025, "4T"),
    _GeneratedTree("303", "2026-y-siguientes", "aeat-dr-303-2026", "2026", 2026, "4T"),
    # The 2022 annual IVA summary, whose eight numbered pages carry the only
    # adjudicated source defect in the estate -- see `_SOURCE_DEFECTS` below.
    _GeneratedTree("390", "2022", "aeat-dr-390-2022", "2022", 2022, "0A"),
)


#: Adjudicated contradictions in a published record design, keyed by the source
#: ref of the file each one describes rather than by the tree row that reads it:
#: a defect is a property of the document, so every row bound to the same design
#: inherits the same reading. Each declaration is additionally pinned to that
#: file's SHA-256 and refused by `validate_source_defect_declarations` if the
#: parsed source does not carry it, so a reissued design retires its entry by
#: going dormant rather than by being silently reapplied.
_SOURCE_DEFECTS: dict[str, tuple[SourceDefectDeclaration, ...]] = {
    "aeat-dr-390-2022": (
        SourceDefectDeclaration(
            source_ref="aeat-dr-390-2022",
            source_sha256="7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe",
            sheet="Pág. 7",
            source_cell="A53",
            published_content='Constante "</T3900700>"',
            adjudicated_literal="</T39007000>",
            evidence=(
                "Cell A53 states two facts that cannot both hold: the close constant it prints is eleven "
                "characters, and the slot the same cell declares for it is twelve bytes. Read straight out "
                "of xl/sharedStrings.xml, bypassing project code, the workbook carries </T39001000> through "
                "</T39006000> and </T39008000> at twelve characters each and </T3900700> at eleven, so the "
                "short form is in the AEAT file and no parser is implicated. Three independent signals "
                "converge on </T39007000>: the seven sibling pages all follow </T3900N000> for page N, that "
                "value is the only one filling the twelve-byte slot A53 itself declares, and it is the value "
                "the reviewed committed layout already carries. The published reading is unusable rather than "
                "merely disfavoured, since an eleven-byte literal is refused by the slot-width guard that "
                "follows this substitution regardless of how the byte comparison is settled."
            ),
        ),
    ),
}


def _source_defects(tree: _GeneratedTree) -> tuple[SourceDefectDeclaration, ...]:
    return _SOURCE_DEFECTS.get(tree.source_ref, ())


def _isolated_authority(tree: _GeneratedTree, root: Path) -> Path:
    """Copy the target's authored NON-export authority into an isolated root.

    The export directory is deliberately never copied: check mode renders the
    candidate afresh, so copying one would let a stale tree validate itself.
    """
    registry_root = root / "registry" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat", "legal"), registry_root / "legal")
    if tree.modelo == "303":
        # M303's selected snapshot compiles the canonical annual Orden support
        # authority.  It is registry authority, not an export input, so stage
        # the same complete bundled directory rather than reconstituting it.
        shutil.copytree(
            bundled_path("registry", "aeat", "m303_orden_anual"),
            registry_root / "m303_orden_anual",
        )
    modelo_root = registry_root / "modelos" / tree.modelo
    shutil.copytree(
        bundled_path("registry", "aeat", "modelos", tree.modelo),
        modelo_root,
        ignore=shutil.ignore_patterns("export"),
    )
    # Check mode requires the isolated candidate to hold EXACTLY the target
    # revision: it validates one generated tree against one selected revision,
    # and a sibling left in place makes the selection ambiguous. Modelo 232
    # carries two revisions, so the siblings are pruned rather than the whole
    # tree being hand-assembled.
    revisions_root = modelo_root / "revisions"
    for sibling in revisions_root.iterdir():
        if sibling.name != tree.revision:
            shutil.rmtree(sibling)
    assert not (modelo_root / "revisions" / tree.revision / "export").exists(), (
        f"{tree}: the isolated candidate must not carry a copied export tree"
    )
    # Every modelo the target REFERENCES comes along too. A cross-modelo binding
    # or dependency classification resolves against the loaded registry, so a
    # candidate holding only the target refuses with "references unknown source
    # modelo" -- a refusal the isolation created, indistinguishable in the
    # pending table from a real authoring gap. Modelo 353's per-member fan-in
    # over Modelo 322 is the worked case.
    for referenced in _supporting_modelos(tree):
        shutil.copytree(
            bundled_path("registry", "aeat", "modelos", referenced),
            registry_root / "modelos" / referenced,
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


def _stage_continuity_metadata(tree: _GeneratedTree, root: Path) -> Path | None:
    """Copy only the sibling facts the strict continuity validator reads.

    The generated candidate stays a one-revision authority.  A landing
    revision's continuity declarations nevertheless name real predecessor
    revisions, so the generic validator receives a separate directory-mode
    witness containing those predecessors' scalar metadata, continuity
    surfaces, and evolution declarations -- never their bindings, formulas,
    layouts, or generated exports.
    """
    source_modelo_root = bundled_path("registry", "aeat", "modelos", tree.modelo)
    definition = load_modelo_directory(source_modelo_root)
    target = definition.revisions[tree.revision]
    predecessors = sorted({str(evolution.from_revision) for evolution in target.casilla_continuidad_evolutions})
    if not predecessors:
        return None

    metadata_modelo_root = root / "continuity-metadata" / tree.modelo
    metadata_modelo_root.mkdir(parents=True)
    shutil.copy2(source_modelo_root / "manifest.toml", metadata_modelo_root / "manifest.toml")
    for predecessor in predecessors:
        source_revision_root = source_modelo_root / "revisions" / predecessor
        target_revision_root = metadata_modelo_root / "revisions" / predecessor
        target_revision_root.mkdir(parents=True)
        shutil.copy2(source_revision_root / "revision.toml", target_revision_root / "revision.toml")
        for member in ("casillas", "casilla_continuidad_evolutions"):
            source_member = source_revision_root / member
            if source_member.is_dir():
                shutil.copytree(source_member, target_revision_root / member)
    return metadata_modelo_root


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
    # 200 is behind a DELIBERATE downgrade, not a reviewer stamp. Its
    # authority_grade was lowered to "calculation" to hold the filing boundary
    # shut while one revision spanned the incompatible 2024 and 2025 AEAT
    # layouts. Check mode validates the candidate through the real authority and
    # therefore asks for filing grade, so it cannot run for 200 while that stands.
    #
    # The split HAS since landed -- 200 now carries revisions 2024 and
    # 2025-y-siguientes, each bound to its own design epoch -- but both still
    # declare authority_grade = "calculation", so the split alone did not retire
    # this entry. It retires when the grade is restored to filing, which is a
    # separate decision from splitting the revision, and the assertion below
    # fails the day check mode passes so the entry cannot outlive its reason.
    #
    # Recorded so the byte-equality half of this gate keeps working: without an
    # entry the row fails blind, and an unguarded published tree is free to
    # drift -- which is exactly what 347's map did unnoticed, per the note
    # above.
    "m200-2025-y-siguientes": "cannot satisfy the requested 'filing' snapshot authority",
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
    source_defects = _source_defects(tree)
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
    continuity_metadata_modelo_root = _stage_continuity_metadata(tree, candidate_root)
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
    metadata_modelo_root = _stage_continuity_metadata(tree, candidate_root)
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
