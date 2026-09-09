"""Real-behaviour tests for the rule-grounding coverage join.

The join's whole claim is that a field's grounding is found through its AEAT
type. Two failure modes would make it useless while still producing rows: it
could report every field as grounded, or it could match a field against a
convention for a different type. Both are asserted against, on the live corpus,
because the corpus is what supplies the mixture of grounded and ungrounded
fields the join exists to separate.
"""

from __future__ import annotations

import dataclasses

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ...quality.unread_inputs import report_unread
from ..analysis.corpus import bundled_modelo_ids
from ..analysis.rule_grounding_coverage import KINDS, GroundingFinding, revision_findings, screen_authority
from ..analysis.type_convention_notes import revision_findings as type_conventions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@dataclasses.dataclass(frozen=True, slots=True)
class _Field:
    """The attributes the classifier reads from a field needing a rule.

    ``notes`` and ``kind`` carry what the field's own content cell cites and
    whether that citation resolved, which is the strongest grounding a field can
    have and was missing from the first version of this classifier.
    """

    aeat_type: str
    cell: str
    length: int = 17
    notes: tuple[str, ...] = ()
    kind: str = "pointer_unresolved"


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


@pytest.fixture(scope="module")
def corpus(authority: ValidatedRegistryAuthority) -> tuple[GroundingFinding, ...]:
    return screen_authority(authority, bundled_modelo_ids())


def test_the_join_separates_grounded_from_ungrounded_fields(corpus: tuple[GroundingFinding, ...]) -> None:
    """The join discriminates rather than reporting every field the same way.

    A join reporting every field the same way would still produce rows and a
    census, and would tell the authoring task nothing.

    The discrimination is asserted on input written here rather than on the
    live corpus, because the corpus no longer supplies the mixture. Every
    outstanding field now cites a note its own sheet defines, so every live row
    is ``grounded_by_own_note``. That is not the join losing a condition: the
    three fields that used to fall through to the weaker conditions did so
    because their designs print a note's label alone on its row and the
    definition grammar refused that shape, so the citations resolve now and the
    strongest grounding applies. A population assertion could not tell those two
    stories apart, which is why the property moved onto explicit input.
    """
    from ..analysis.rule_grounding_coverage import classify_grounding

    assert corpus, "the join lost its live population"
    assert {item.kind for item in corpus} <= set(KINDS)

    mixed = classify_grounding(
        (
            _Field(aeat_type="Num", cell="S1!B1", notes=("nota 1",), kind="pointer_resolves_vocabulary_miss"),
            _Field(aeat_type="Num", cell="S1!B2"),
            _Field(aeat_type="An", cell="S1!B3"),
        ),
        by_type={"Num": ["S1:nota 4"]},
        design_notes=("S1",),
        modelo="200",
        revision="r",
    )
    assert [item.kind for item in mixed] == [
        "grounded_by_own_note",
        "grounded_by_type_convention",
        "grounded_by_design_note",
    ]


def test_every_live_grounded_row_names_a_note_its_own_sheet_really_defines(
    corpus: tuple[GroundingFinding, ...],
) -> None:
    """The live floor the two emptied ones were re-pointed at.

    Two conditions lost their entire live population to a corrected reading -
    ``grounded_by_type_convention`` held two rows and ``grounded_by_design_note``
    one, and all three were fields whose own citation the definition grammar
    could not read. Their floors were doing real work: they are what stops an
    absence claim passing because the screen quietly stopped examining anything.
    So the work moves here rather than being dropped, onto the population that
    absorbed those rows.

    ``grounded_by_own_note`` is the strongest condition the join reports and the
    hardest to fake: the credit is only valid if the note the field's own cell
    cites is really defined on the field's own sheet. That is checked here
    against the design transcription itself, so a join crediting a field with a
    note nobody could open fails, and a join that reported nothing at all fails
    on the floor below it.
    """
    from ..analysis.footnote_pointer_notes import sheet_note_definitions
    from ..analysis.note_label_scope import transcription_paths

    grounded = [item for item in corpus if item.kind == "grounded_by_own_note"]
    assert grounded, "the join's strongest condition lost its live population"

    by_design = {path.name: path for path in transcription_paths()}
    for item in grounded:
        design = by_design.get(item.design)
        assert design is not None, f"{item.cell} names a transcription the corpus does not carry: {item.design!r}"
        defined = sheet_note_definitions(design.read_text(encoding="utf-8"))
        sheet = item.cell.split("!", 1)[0]
        assert item.notes, f"{item.cell} is credited with its own note and names none"
        for note in item.notes:
            note_sheet, label = note.split(":", 1)
            # Scoped to the field's OWN sheet, both in the credit and in the
            # lookup: a note label names a note only together with its sheet.
            assert note_sheet == sheet, f"{item.cell} is credited with {note!r} from another sheet"
            assert defined.get(sheet, {}).get(label), f"{item.cell} cites {note!r}, which {item.design} never defines"


def test_a_grounded_field_names_notes_that_really_cover_its_type(
    authority: ValidatedRegistryAuthority, corpus: tuple[GroundingFinding, ...]
) -> None:
    """Every note credited to a field states a convention for that field's type.

    This is the assertion that stops the join drifting into matching a field
    against any convention its design happens to carry.

    Asserted on written input, and then over whatever live rows carry this
    condition. The live half is announced rather than required: the condition
    has no member in the corpus today, for the reason the join test above
    records, and demanding one would make this gate fail for a corpus that got
    BETTER. It still runs the cross-check against the convention screen's own
    output the moment a member reappears.
    """
    from ..analysis.rule_grounding_coverage import classify_grounding

    # The type join, on input where the wrong answer is available: the design
    # states a convention for `An` as well, and the `Num` field must not receive
    # it.
    written = classify_grounding(
        (_Field(aeat_type="Num", cell="S1!B1"),),
        by_type={"Num": ["S1:nota 4"], "An": ["S1:nota 3"]},
        design_notes=(),
        modelo="200",
        revision="r",
    )
    assert [item.kind for item in written] == ["grounded_by_type_convention"]
    assert written[0].notes == ("S1:nota 4",)

    grounded = [item for item in corpus if item.kind == "grounded_by_type_convention"]
    report_unread(
        "rule-grounding type-convention cross-check",
        "no live field is grounded by a type convention, so the corpus half of this gate asserted nothing",
        () if grounded else ("grounded_by_type_convention",),
    )
    for item in grounded:
        assert item.notes
        covering = {
            f"{convention.sheet}:{convention.label}"
            for convention in type_conventions(authority, modelo=item.modelo, revision=item.revision)
            if item.aeat_type in convention.types
        }
        assert set(item.notes) <= covering
        assert set(item.notes) == covering


def test_a_field_grounded_only_by_a_design_note_names_that_note(
    corpus: tuple[GroundingFinding, ...],
) -> None:
    """Weaker grounding is reported as itself, never as a type convention.

    A design note names no type, so a field falling back to one has evidence
    that may or may not settle it. Reporting that as the stronger condition
    would put a field's rule on wording that says nothing about it - modelo
    200's design note does settle its amounts, and another design's says only
    that the NIF is mandatory, and the row cannot tell them apart.

    The corpus half is announced rather than required, for the same reason as
    the gate above: this condition's live members were fields whose own citation
    the definition grammar could not read, and they are grounded by that
    citation now.
    """
    fallback = [item for item in corpus if item.kind == "grounded_by_design_note"]
    report_unread(
        "rule-grounding design-note fallback",
        "no live field falls back to a design note, so the corpus half of this gate asserted nothing",
        () if fallback else ("grounded_by_design_note",),
    )
    for item in fallback:
        assert item.notes
        assert all(note.endswith(":unnumbered") for note in item.notes)


def test_the_ungrounded_condition_still_reports_when_nothing_is_available() -> None:
    """No field in the corpus is ungrounded, so the condition is proven built.

    Admitting design-level notes emptied this population. The condition is kept
    rather than deleted, because a design carrying neither a type convention nor
    a design note is exactly the case an author must not discover halfway
    through, and a condition with no instance and no proof stops reporting
    without anyone noticing.

    Proven through the screen's own classifier on explicit input, rather than by
    replacing what this module imports: a test that reached inside the screen to
    silence its sources would be testing a screen nobody runs.
    """
    from ..analysis.rule_grounding_coverage import classify_grounding

    field = _Field(aeat_type="Num", cell="A!B1")
    findings = classify_grounding((field,), by_type={}, design_notes=(), modelo="200", revision="r")
    assert [item.kind for item in findings] == ["ungrounded"]
    assert findings[0].notes == ()


def test_a_note_the_field_itself_cites_outranks_every_other_grounding() -> None:
    """A note the design pointed at FOR THIS FIELD needs no argument at all.

    The other two conditions each require a claim that the field falls under
    wording addressed to something larger - its type, or its design. A note the
    field's own cell cites is addressed to the field, so it wins. Asserted
    against both weaker sources being present, or the precedence would hold
    only where nothing else did.
    """
    from ..analysis.rule_grounding_coverage import classify_grounding

    field = _Field(
        aeat_type="Num",
        cell="DP200014!A36",
        notes=("nota 1",),
        kind="pointer_resolves_vocabulary_miss",
    )
    findings = classify_grounding(
        (field,), by_type={"Num": ["S1:nota 4"]}, design_notes=("DP200001",), modelo="200", revision="r"
    )
    assert [item.kind for item in findings] == ["grounded_by_own_note"]
    assert findings[0].notes == ("DP200014:nota 1",)


def test_an_unresolved_citation_is_not_grounding() -> None:
    """A pointer naming a note its sheet never defines grounds nothing.

    The field cites something, so a classifier reading the citation alone would
    call it grounded. What makes it grounding is that the citation RESOLVED, and
    three fields in the corpus cite a note their own sheet does not carry.
    """
    from ..analysis.rule_grounding_coverage import classify_grounding

    field = _Field(aeat_type="Num", cell="A!B1", notes=("nota 1",), kind="pointer_unresolved")
    findings = classify_grounding((field,), by_type={}, design_notes=("DP200001",), modelo="200", revision="r")
    assert [item.kind for item in findings] == ["grounded_by_design_note"]


def test_a_type_convention_outranks_a_design_note() -> None:
    """Where both exist the stronger evidence is the one reported.

    A design note is available to every field of the design, so without this the
    weaker condition would swallow every field that also had a convention naming
    its type, and the census would understate the grounding it actually has.
    """
    from ..analysis.rule_grounding_coverage import classify_grounding

    field = _Field(aeat_type="Num", cell="A!B1")
    findings = classify_grounding(
        (field,), by_type={"Num": ["S1:nota 4"]}, design_notes=("S1",), modelo="202", revision="r"
    )
    assert [item.kind for item in findings] == ["grounded_by_type_convention"]
    assert findings[0].notes == ("S1:nota 4",)


def test_a_design_note_grounds_a_field_whose_type_no_convention_names() -> None:
    """The fallback fires only when the stronger evidence is absent."""
    from ..analysis.rule_grounding_coverage import classify_grounding

    field = _Field(aeat_type="Num", cell="A!B1")
    findings = classify_grounding(
        (field,), by_type={"An": ["S1:nota 3"]}, design_notes=("DP200001",), modelo="200", revision="r"
    )
    assert [item.kind for item in findings] == ["grounded_by_design_note"]
    assert findings[0].notes == ("DP200001:unnumbered",)


def test_a_revision_stating_conventions_but_needing_no_rule_yields_nothing(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The join reports fields, never conventions.

    A design can state conventions while no field of it needs a rule, and
    reporting those would count wording as work. The subject is derived rather
    than named: an earlier draft named a modelo and revision by hand and picked
    a revision id the registry does not declare, which failed for a reason that
    had nothing to do with the property.
    """
    from ..analysis.footnote_only_wire_facts import revision_findings as fields_needing_rules

    checked = 0
    total = 0
    unreadable: list[str] = []
    for modelo in bundled_modelo_ids():
        for revision_id in authority.modelo(modelo).revisions:
            total += 1
            revision = str(revision_id)
            try:
                needed = fields_needing_rules(authority, modelo=modelo, revision=revision)
                conventions = type_conventions(authority, modelo=modelo, revision=revision)
            except (ValueError, KeyError, FileNotFoundError, OSError) as refusal:
                # These screens refuse a revision that declares nothing they can
                # read, which is honest -- but the refusals were dropped here
                # without a count, so a bare "checked > 0" passed on eleven
                # revisions while saying nothing about the ninety-seven it never
                # reached. Announced, not refused: the refusal is the screens'
                # own correct answer, not a broken input.
                unreadable.append(f"{modelo}/{revision} ({type(refusal).__name__})")
                continue
            if needed or not conventions:
                continue
            assert revision_findings(authority, modelo=modelo, revision=revision) == ()
            checked += 1

    report_unread(
        "convention-without-rule join",
        "these revisions declare nothing the two screens can read, so the property below was never asserted over them",
        unreadable,
    )
    assert checked, (
        f"no revision states a convention without needing a rule, so this proves nothing "
        f"({checked} asserted of {total} revisions, {len(unreadable)} unreadable by the screens)"
    )


def test_the_worklist_groups_fields_by_the_note_that_grounds_them() -> None:
    """The authoring cost is notes to read, not fields to visit.

    One note read covers every field citing it, so the worklist groups by note
    and orders by how many fields each covers. Asserted on constructed findings
    so the grouping is shown rather than agreed with.
    """
    from ..analysis.rule_grounding_coverage import GroundingFinding, grounding_worklist

    def _found(cell: str, note: str, length: int) -> GroundingFinding:
        return GroundingFinding(
            modelo="200",
            revision="r",
            cell=cell,
            design="d.extracted.md",
            aeat_type="Num",
            length=length,
            kind="grounded_by_own_note",
            notes=(note,),
            detail="",
        )

    work = grounding_worklist(
        (_found("S!A1", "S:nota 1", 17), _found("S!A2", "S:nota 1", 17), _found("S!A3", "S:nota 2", 4))
    )
    assert [(item.note, len(item.fields)) for item in work] == [("S:nota 1", 2), ("S:nota 2", 1)]
    assert work[0].fields == ("S!A1", "S!A2")


def test_a_note_cited_at_two_widths_shows_both() -> None:
    """A single rule cannot serve two widths, and the work item says so.

    Modelo 200's amounts note is the case: it states a seventeen-character value
    and three fields credited to it declare one and four characters. Collapsing
    the widths to one figure would hide exactly the thing an author has to
    notice before writing one rule for the group.
    """
    from ..analysis.rule_grounding_coverage import GroundingFinding, grounding_worklist

    def _found(cell: str, length: int) -> GroundingFinding:
        return GroundingFinding(
            modelo="200",
            revision="r",
            cell=cell,
            design="d.extracted.md",
            aeat_type="Num",
            length=length,
            kind="grounded_by_design_note",
            notes=("DP200001:unnumbered",),
            detail="",
        )

    work = grounding_worklist((_found("S!A1", 17), _found("S!A2", 1)))
    assert len(work) == 1
    assert work[0].widths == (1, 17)


def test_two_revisions_sharing_one_design_are_one_reading() -> None:
    """A note read once serves every revision whose design carries it."""
    from ..analysis.rule_grounding_coverage import GroundingFinding, grounding_worklist

    def _found(revision: str) -> GroundingFinding:
        return GroundingFinding(
            modelo="200",
            revision=revision,
            cell="S!A1",
            design="one.extracted.md",
            aeat_type="Num",
            length=17,
            kind="grounded_by_own_note",
            notes=("S:nota 1",),
            detail="",
        )

    assert len(grounding_worklist((_found("2024"), _found("2025")))) == 1


def test_one_label_in_two_designs_is_two_readings() -> None:
    """The same sheet and label in two designs is not one note.

    Grouping by modelo and label alone reported eleven work items where the
    corpus has thirteen, and the merge was not harmless: modelo 303's
    `DP30302:nota 5` carries three hundred and thirty characters in one design
    and two hundred and nine in another. A reader handed one row would have read
    one of the two texts and applied it to fields governed by the other.

    This is the sheet-merge defect one level up. A label identifies a note only
    together with the sheet that prints it AND the design that sheet belongs to.
    """
    from ..analysis.rule_grounding_coverage import GroundingFinding, grounding_worklist

    def _found(design: str) -> GroundingFinding:
        return GroundingFinding(
            modelo="303",
            revision="r",
            cell="DP30302!A1",
            design=design,
            aeat_type="Num",
            length=1,
            kind="grounded_by_own_note",
            notes=("DP30302:nota 5",),
            detail="",
        )

    work = grounding_worklist((_found("2023.extracted.md"), _found("2024.extracted.md")))
    assert len(work) == 2
    assert {item.design for item in work} == {"2023.extracted.md", "2024.extracted.md"}


def test_a_work_item_is_flagged_when_its_note_drifts() -> None:
    """The flag comes from the drift set the caller passes, not from a guess."""
    from ..analysis.rule_grounding_coverage import GroundingFinding, grounding_worklist

    finding = GroundingFinding(
        modelo="303",
        revision="2023",
        cell="DP30302!A1",
        design="d.extracted.md",
        aeat_type="Num",
        length=1,
        kind="grounded_by_own_note",
        notes=("DP30302:nota 5",),
        detail="",
    )
    drifting = frozenset({("303", "DP30302", "nota 5")})
    assert grounding_worklist((finding,), drifting=drifting)[0].grounding_drifts is True
    other = frozenset({("303", "DP30302", "nota 9")})
    assert grounding_worklist((finding,), drifting=other)[0].grounding_drifts is False


def test_an_unmeasured_caller_gets_no_claim_about_drift() -> None:
    """The default is no claim, not a claim of stability.

    A caller that has not measured drift must not be told a note is stable, so
    the flag defaults false and means "not reported as drifting" rather than
    "checked and found stable". The distinction matters because the two read the
    same in output and only one is evidence.
    """
    from ..analysis.rule_grounding_coverage import GroundingFinding, grounding_worklist

    finding = GroundingFinding(
        modelo="303",
        revision="2023",
        cell="DP30302!A1",
        design="d.extracted.md",
        aeat_type="Num",
        length=1,
        kind="grounded_by_own_note",
        notes=("DP30302:nota 5",),
        detail="",
    )
    assert grounding_worklist((finding,))[0].grounding_drifts is False


def _grounding_finding(*, modelo: str, revision: str, cell: str) -> GroundingFinding:
    """One census row, written here so the contradiction below is the only variable."""
    from ..analysis.rule_grounding_coverage import GroundingFinding

    return GroundingFinding(
        modelo=modelo,
        revision=revision,
        cell=cell,
        design="design.xlsx.extracted.md",
        aeat_type="Num",
        length=17,
        kind="ungrounded",
        notes=(),
        detail="written in this test",
    )


def test_a_field_that_anchors_a_reviewed_rule_and_needs_one_is_reported() -> None:
    """The teeth for the standing contradiction gate.

    Both rows are census rows in the same shape and differ in one thing: whether
    a reviewed rule anchors that exact cell. The anchored one is a contradiction
    - the rule exists, so the row is work already done - and the unanchored one
    is ordinary outstanding work that must not be swept up with it.

    The keys are written here rather than taken from the shipped profiles. A
    detector proven only against a clean corpus proves that the corpus is clean,
    not that the detector fires; and the corpus is clean, so nothing in it could
    have shown this.
    """
    from ..analysis.rule_grounding_coverage import reviewed_rule_contradictions

    already_ruled = _grounding_finding(modelo="200", revision="2025", cell="Pag. 1!A10")
    still_owed = _grounding_finding(modelo="200", revision="2025", cell="Pag. 1!A11")
    anchored = frozenset({("200", "2025", "Pag. 1!A10")})

    contradictions = reviewed_rule_contradictions((already_ruled, still_owed), anchored=anchored)

    assert [item.cell for item in contradictions] == ["Pag. 1!A10"]
    assert reviewed_rule_contradictions((still_owed,), anchored=anchored) == ()
    # The key is whole: a matching cell on another revision or another modelo is
    # a different field, and crediting it would silence a real row.
    assert (
        reviewed_rule_contradictions(
            (_grounding_finding(modelo="200", revision="2024", cell="Pag. 1!A10"),), anchored=anchored
        )
        == ()
    )
    assert (
        reviewed_rule_contradictions(
            (_grounding_finding(modelo="202", revision="2025", cell="Pag. 1!A10"),), anchored=anchored
        )
        == ()
    )
