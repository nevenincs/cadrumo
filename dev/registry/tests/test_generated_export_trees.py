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

Each generated modelo is enrolled as a row in :data:`_GENERATED_TREES`. Modelo 303
and 390 are deliberately absent: they are held by an in-flight campaign that owns
their maps and profiles.
"""

from __future__ import annotations

import filecmp
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    ExportEncoding,
    RegistryRevisionInspection,
    RegistryValidationError,
    load_registry_tree,
)

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
from ..pipeline._tree_check import GeneratedExportTreeCheckContext, check_generated_export_tree
from ..pipeline._tree_validation import GeneratedExportTreeValidationContext

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

    def __str__(self) -> str:
        return f"m{self.modelo}-{self.revision}"


_GENERATED_TREES: tuple[_GeneratedTree, ...] = (
    _GeneratedTree("210", "2025", "aeat-dr-210-2022", "2022", 2025, "0A"),
    _GeneratedTree("232", "2018-y-siguientes", "aeat-dr-232-2018", "2018", 2018, "0A"),
    _GeneratedTree("232", "2016-2017", "aeat-dr-232-2016", "2016", 2016, "0A"),
    _GeneratedTree("353", "2026-y-siguientes", "aeat-dr-353-2026", "2026", 2026, "01"),
    _GeneratedTree("353", "2008-2025", "aeat-dr-353-2021-2025", "2021", 2021, "01"),
    # Split at the 2023/2024 re-layout, where the 2024 design adds nine
    # fields and revives DR32201 offset 1311 out of reserved space. The
    # earlier 2022/2023 boundary is NOT split: no key pairs those two
    # designs totally, so 2008-2022 still emits the 2023 layout.
    _GeneratedTree("322", "2008-2023", "aeat-dr-322-2023", "2023", 2023, "01"),
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
    _GeneratedTree("184", "2015-2024", "aeat-dr-184-2023-2024", "2023", 2024, "0A"),
    _GeneratedTree("184", "2025-y-siguientes", "aeat-dr-184-2025", "2025", 2025, "0A"),
    # Enrolled late, and its absence is why its map went stale unnoticed: 347 was
    # published without a row here, so nothing compared its committed tree against a
    # fresh render, and two anchors kept naming parent rows the parser had already
    # descended past.
    _GeneratedTree("347", "2008-y-siguientes", "aeat-dr-347-2025", "2025", 2025, "0A"),
    # Enrolled with the layout, not after it, which is the whole lesson of the 347
    # entry above: a published tree that nothing compares against a fresh render
    # is free to drift, and 347's map did exactly that unnoticed.
    _GeneratedTree("200", "2024-y-siguientes", "aeat-dr-200-2025", "2025", 2025, "0A"),
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
)


def _isolated_authority(tree: _GeneratedTree, root: Path) -> Path:
    """Copy the target's authored NON-export authority into an isolated root.

    The export directory is deliberately never copied: check mode renders the
    candidate afresh, so copying one would let a stale tree validate itself.
    """
    registry_root = root / "registry" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat", "legal"), registry_root / "legal")
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
        encoding=ExportEncoding.LATIN_1,
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
    "m202-2019-2022": "appears on exactly one casilla",
    "m202-2023-2024": "appears on exactly one casilla",
    "m202-2025-y-siguientes": "lacks exact source revision coverage",
    # Both 151 revisions resolve every enrolled family and validate through the
    # real authority, so what is left is the reviewer stamp -- the same wall
    # m210, m322 and m353 sit behind. Worth noting for whoever reviews them: the
    # 2015-2022 layout was a hand transcription until this campaign, and it was
    # two positions SHORT of AEAT's own envelope, omitting the AUX block's
    # programa and NIF-desarrollo fields. The generated tree carries both.
}


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
    fresh_root = tmp_path / "fresh" / "export"
    render_complete_export_tree(
        fresh_root,
        revision_id=tree.revision,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
    )

    fresh_members = {path.name for path in fresh_root.iterdir()}
    committed_members = {path.name for path in tree.committed.iterdir()}
    assert committed_members == fresh_members, (
        f"{tree}: committed export tree membership differs from a fresh render; "
        f"committed-only: {sorted(committed_members - fresh_members)}; "
        f"fresh-only: {sorted(fresh_members - committed_members)}"
    )
    differing = sorted(
        name for name in fresh_members if not filecmp.cmp(fresh_root / name, tree.committed / name, shallow=False)
    )
    assert differing == [], f"{tree}: committed export fragment(s) differ from a fresh render: {differing}"

    candidate_root = tmp_path / "candidate"
    registry_root = _isolated_authority(tree, candidate_root)
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
