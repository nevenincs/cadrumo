"""Real-behaviour tests for the pointer-only wire fact screen.

The screen's job is to hand a rule author the fields whose wire fact sits behind
a cross-reference, together with the wording behind it. Two things therefore
have to hold: the population must be the one the eligibility predicate would
newly admit, and the reading aid must not be mistaken for a verdict. The second
carries a live counterexample, because it was very nearly reported as one.

A third followed: a reference somebody HAS followed must stop being counted as
one nobody has. Two declaration families record those readings - what the note
says the representation is, and that the note states none - and each is pinned
to one design by digest, one sheet by name, and one exact published pointer, so
the tests below prove both directions for both: a covered cell drops out of the
outstanding population, and a declaration pinned to another digest, another
sheet, or another pointer covers nothing. Without the second half the screen
would credit work never done.

A fourth is the one the others could not see. The screen must return the SAME
eligibility verdict as the renderer for a field of a pinned design, and it did
not: it reached past the routed predicate and passed none of the design's
declarations, so a cell somebody had read was reported as outstanding while the
renderer treated it as read. Every test here passed throughout, because each
asserted the shape of a row and none asserted agreement with the thing being
screened.
"""

from __future__ import annotations

from typing import Final

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..analysis.footnote_only_wire_facts import (
    ADJUDICATED_KINDS,
    KINDS,
    OUTSTANDING_KINDS,
    cell_adjudication,
    cell_applicability_reading,
    field_is_render_profile_eligible,
    pinned_adjudications,
    pinned_applicability_readings,
    revision_findings,
    screen_authority,
    would_become_eligible,
)
from ..analysis.footnote_pointer_notes import note_definitions
from ..pipeline._render_profile import project_render_profile_eligibility
from ..pipeline.render_check import revision_render_inputs
from ..pipeline.render_profile_eligibility import resolve_render_profile_eligibility
from ..pipeline.source_defects import NoteGovernedAmountDeclaration, NoteStatedApplicabilityDeclaration

#: Named once per module rather than repeated at each read site, where a typo
#: would be a silent decode change rather than an error.
_UTF_8: Final[str] = "utf-8"

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A digest belonging to no shipped design, so a fixture pinned to it can only
#: ever be admitted by a matcher that stopped checking the pin.
_FOREIGN_SHA256: Final[str] = "0" * 64


def _declaration(
    *,
    source_ref: str = "fixture-design-ref",
    source_sha256: str = _FOREIGN_SHA256,
    sheet: str = "Pag. 1",
    published_content: str = "Nota 2",
) -> NoteGovernedAmountDeclaration:
    """One adjudication written here, so no test depends on a shipped table's contents."""
    return NoteGovernedAmountDeclaration(
        source_ref=source_ref,
        source_sha256=source_sha256,
        sheet=sheet,
        published_content=published_content,
        note_cell="A99",
        note_statement="Nota 2: estas casillas deben estar rellenas a 0",
        integer_digits=15,
        decimal_digits=2,
        sign_policy="unsigned",
        mandated_values=("0",),
        evidence="Written in this test to exercise the screen's matcher; adjudicates nothing.",
    )


def _applicability_reading(
    *,
    source_ref: str = "fixture-design-ref",
    source_sha256: str = _FOREIGN_SHA256,
    sheet: str = "Pag. 1",
    published_content: str = "Nota 2",
) -> NoteStatedApplicabilityDeclaration:
    """One applicability reading written here, carrying no digit counts by construction."""
    return NoteStatedApplicabilityDeclaration(
        source_ref=source_ref,
        source_sha256=source_sha256,
        sheet=sheet,
        published_content=published_content,
        note_cell="A98",
        note_statement="Nota 2: solo para periodos 02 y siguientes",
        evidence="Written in this test to exercise the screen's matcher; adjudicates nothing.",
    )


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


@pytest.fixture(scope="module")
def modelo_200(authority: ValidatedRegistryAuthority) -> tuple[object, ...]:
    return revision_findings(authority, modelo="200", revision="2025-y-siguientes")


def test_the_screen_reports_the_footnoted_corporate_tax_amounts(modelo_200: tuple[object, ...]) -> None:
    """Modelo 200's pointer-only cells are found, and every row is identifiable.

    Held by the shape of a row rather than by the count, which moves whenever a
    design is re-transcribed. A row that cannot name its cell is useless to the
    author it exists for, so identity is asserted rather than presence.
    """
    assert modelo_200, "the screen lost its live population"
    for finding in modelo_200:
        assert finding.record
        assert "!" in finding.cell
        assert finding.offset > 0
        assert finding.length > 0
        assert finding.description
        assert finding.kind in KINDS
        assert finding.notes


def test_every_reported_field_is_one_the_predicate_would_newly_admit(
    authority: ValidatedRegistryAuthority, modelo_200: tuple[object, ...]
) -> None:
    """The population is exactly the fields the correction would add.

    Asked through the shipped predicate, so a change to eligibility moves this
    screen with it rather than leaving a second copy of the rule behind.
    """
    del modelo_200
    from ..pipeline.render_check import revision_render_inputs

    inputs = revision_render_inputs(authority, modelo="200", revision="2025-y-siguientes")
    source = inputs.joined.source
    reported = {
        (field.parser_field.sheet, field.parser_field.source_row)
        for field in inputs.joined.fields
        if would_become_eligible(field.parser_field, source)
    }
    assert reported, "no field would become eligible, so the screen measures nothing"
    for field in inputs.joined.fields:
        parser_field = field.parser_field
        if (parser_field.sheet, parser_field.source_row) not in reported:
            continue
        # Rejected as it stands, admitted once the pointer stops counting as the
        # design's own statement. Both halves matter: a field already eligible
        # needs no pointer argument at all.
        assert not field_is_render_profile_eligible(parser_field, source)
        assert field_is_render_profile_eligible(parser_field.model_copy(update={"content": None}), source)


def test_the_screen_and_the_renderer_return_one_eligibility_verdict_per_field(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The screen's eligibility answer must EQUAL the one the renderer validates against.

    This is the property the screen lost. The renderer resolves a design's
    applicability readings from the source the parser read and partitions the
    whole design against them; the screen asked the bare projection about one
    field at a time and passed no readings at all. The two then disagreed about
    modelo 353's ``Nota 4.`` cells - read, recorded and acted on for the
    renderer, outstanding work for the screen - and no test could see it,
    because every existing assertion was about the shape of a row.

    Asserted as an agreement and not as a population, so it pins no count and
    ratchets nothing: for every field of the design, the screen's verdict equals
    that field's membership in the design-wide partition. A screen that goes back
    to assembling the predicate's arguments itself fails here on the first field
    whose cell a declaration covers.
    """
    from ..pipeline.render_check import revision_render_inputs

    inputs = revision_render_inputs(authority, modelo="353", revision="2026-desde-02")
    source = inputs.joined.source
    fields = tuple(joined_field.parser_field for joined_field in inputs.joined.fields)

    # The renderer's side: the whole design at once, exactly as
    # ``validate_render_profile`` asks it.
    renderer = resolve_render_profile_eligibility(fields, source)
    eligible = {(field.sheet, field.source_row) for field in renderer.all_fields}
    assert eligible, "no field of this design is eligible, so the agreement below is vacuous"

    for field in fields:
        assert field_is_render_profile_eligible(field, source) == ((field.sheet, field.source_row) in eligible), (
            f"the screen and the renderer disagree about {field.sheet}!{field.source_cell}"
        )

    # And the teeth: the drifted call - the bare projection with the argument
    # omitted - genuinely returns a DIFFERENT verdict for a covered cell, so the
    # agreement above is not asserting that two spellings of one call agree.
    readings = pinned_applicability_readings(source)
    assert readings, "this design declares no applicability reading, so the drift cannot be reproduced"
    covered = [
        field
        for field in fields
        if field.content is not None
        and cell_applicability_reading(readings, sheet=field.sheet, content=field.content) is not None
    ]
    assert covered, "no field carries a covered cell, so the drift cannot be reproduced"
    for field in covered:
        assert field_is_render_profile_eligible(field, source)
        assert not project_render_profile_eligibility([field]).all_fields


def test_a_vocabulary_miss_does_not_mean_the_note_states_no_wire_fact(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The reading aid under-reads, and this pins the case that proves it.

    Modelo 200's nota 1 states a filling rule outright - the first two digits
    carry the rate and the last two carry 00, so 25% is written 2500 - and the
    vocabulary list misses it because the note says 'digitos' and 'rellenaran'
    rather than 'decimal' or 'ceros'. Reporting the miss count as a count of
    notes that say nothing about representation would therefore have been
    wrong, and this test exists so that reading cannot be reintroduced.

    Pinned to the note's own wording. If the design is re-transcribed and this
    wording moves, the test fails and the replacement counterexample must be
    named, because the property is not the sentence but the fact that a miss
    settles nothing.
    """
    from cadrumo.core.resources.bundled_data import bundled_path

    from ..analysis.footnote_pointer_notes import design_transcription_path
    from ..pipeline.render_check import revision_render_inputs

    inputs = revision_render_inputs(authority, modelo="200", revision="2025-y-siguientes")
    corpus_path = bundled_path() / authority.catalogues.sources[inputs.joined.source.source_ref].corpus_path
    extracted = design_transcription_path(corpus_path).read_text(encoding=_UTF_8)
    # The counterexample belongs to the sheet that prints it. This design
    # defines "Nota 1" on six sheets and only DP200014's carries the rate
    # filling rule, which is exactly why a design-wide lookup was wrong.
    definitions = note_definitions(extracted, sheet="DP200014")

    text = definitions["nota 1"]
    assert "2500" in text, "the counterexample's wording is no longer in nota 1"
    assert "dos primeros" in text
    # The wording states a representation rule while carrying none of the words
    # the reading aid looks for. That gap is the whole point.
    assert not any(word in text.casefold() for word in ("decimal", "signo", "coma", "alinead", "ceros"))


def test_every_pointer_condition_is_reachable_from_constructed_evidence() -> None:
    """All four conditions, including the one the corpus never produces.

    ``pointer_resolves_vocabulary_hit`` has no instance anywhere in the bundled
    registry. While the decision lived inline in the walk it had neither a live
    member nor a proof, which is precisely the state this package calls a
    condition that has stopped reporting without anyone noticing - and it was in
    a screen written during this campaign.
    """
    from ..analysis.footnote_only_wire_facts import KINDS, classify_pointer
    from ..analysis.footnote_pointer_notes import FootnotePointerNote, PointerEvidence

    def evidence(*notes: FootnotePointerNote) -> PointerEvidence:
        return PointerEvidence(cell="(1)", pointer="(1)", notes=notes)

    hit = evidence(FootnotePointerNote(pointer="(1)", note="1", text="Se consigna con dos decimales."))
    miss = evidence(FootnotePointerNote(pointer="(1)", note="1", text="Solo para residentes."))
    unresolved = evidence(FootnotePointerNote(pointer="(1)", note="1", text=""))

    def kind_of(
        item: PointerEvidence,
        *,
        adjudication: NoteGovernedAmountDeclaration | None = None,
        applicability: NoteStatedApplicabilityDeclaration | None = None,
    ) -> str:
        return classify_pointer(
            item,
            resolved=0 if item is unresolved else 1,
            adjudication=adjudication,
            applicability=applicability,
        )[0]

    assert kind_of(hit) == "pointer_resolves_vocabulary_hit"
    assert kind_of(miss) == "pointer_resolves_vocabulary_miss"
    assert kind_of(unresolved) == "pointer_unresolved"
    assert kind_of(miss, adjudication=_declaration()) == "pointer_adjudicated"
    assert kind_of(miss, applicability=_applicability_reading()) == "pointer_applicability_adjudicated"

    reached = {
        kind_of(hit),
        kind_of(miss),
        kind_of(unresolved),
        kind_of(miss, adjudication=_declaration()),
        kind_of(miss, applicability=_applicability_reading()),
    }
    assert reached == set(KINDS), "a declared condition is unreachable from any input"


def test_an_unresolved_pointer_outranks_the_vocabulary_reading() -> None:
    """A design that never defines the note is a different problem.

    The precedence is asserted rather than left to the branch order: an
    unresolved pointer accompanied by a resolved note using wire vocabulary must
    still report as unresolved, because the missing definition is the finding.
    """
    from ..analysis.footnote_only_wire_facts import classify_pointer
    from ..analysis.footnote_pointer_notes import FootnotePointerNote, PointerEvidence

    mixed = PointerEvidence(
        cell="(1)(2)",
        pointer="(1)(2)",
        notes=(
            FootnotePointerNote(pointer="(1)", note="1", text="Se consigna con dos decimales."),
            FootnotePointerNote(pointer="(2)", note="2", text=""),
        ),
    )
    kind, detail = classify_pointer(mixed, resolved=1, adjudication=None, applicability=None)
    assert kind == "pointer_unresolved"
    assert "2" in detail


def test_the_detail_line_carries_the_resolved_count_it_was_given() -> None:
    """The count orders a reading queue, so it must be the caller's own figure."""
    from ..analysis.footnote_only_wire_facts import classify_pointer
    from ..analysis.footnote_pointer_notes import FootnotePointerNote, PointerEvidence

    miss = PointerEvidence(
        cell="(1)", pointer="(1)", notes=(FootnotePointerNote(pointer="(1)", note="1", text="Solo residentes."),)
    )
    assert "3 note(s)" in classify_pointer(miss, resolved=3, adjudication=None, applicability=None)[1]


def test_a_cell_covered_by_an_adjudication_is_no_longer_outstanding_work(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The reference somebody followed stops being reported as unfollowed.

    Modelo 390's 2025 design is the live case: its expired-rate amount slots
    publish the bare pointer ``Nota 2``, and a declaration pinned to that design
    and to each sheet that prints the note records the reading of it. Before
    this condition existed those cells were reported as references nobody had
    opened, which is the reading the declaration disproves.

    The rows are asserted to still be PRESENT and merely reclassified. Dropping
    them would hide the covered population, and a screen whose census cannot be
    reconciled against its rows is one nobody can check.
    """
    findings = revision_findings(authority, modelo="390", revision="2025")
    assert findings, "modelo 390's pointer-only cells vanished, so this proves nothing"
    outstanding = [item for item in findings if item.kind in OUTSTANDING_KINDS]
    assert not outstanding, f"adjudicated cells still reported as work: {[item.cell for item in outstanding]}"
    for item in findings:
        assert item.kind == "pointer_adjudicated"
        # The detail quotes where the note was read and what it said, so the row
        # carries the evidence a re-reader needs rather than a bare verdict.
        assert "rellenas a 0" in item.detail


def test_an_adjudication_pinned_to_another_digest_covers_nothing(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A reissued design drops out of the table rather than inheriting its reading.

    Exercised against the SHIPPED declarations twice: once through the design's
    real parser-read source, which must select them, and once through a source
    carrying the same reference and a foreign digest, which must select none.
    Without the second half a matcher that had stopped checking the pin would
    pass the first half unchanged.
    """
    from ..pipeline.render_check import revision_render_inputs

    source = revision_render_inputs(authority, modelo="390", revision="2025").joined.source
    live = pinned_adjudications(source)
    assert live, "the shipped adjudications no longer reach modelo 390's 2025 design"

    reissued = source.model_copy(update={"source_sha256": _FOREIGN_SHA256})
    assert pinned_adjudications(reissued) == (), "a stale pin was admitted"
    assert cell_adjudication(pinned_adjudications(reissued), sheet=live[0].sheet, content="Nota 2") is None


def test_an_adjudication_does_not_reach_another_sheet_or_another_pointer() -> None:
    """A note label names a note only together with its sheet.

    Written from a declaration authored here, so the assertion is about the
    matcher and not about which sheets a shipped table happens to list.
    """
    declarations = (_declaration(sheet="Pag. 1", published_content="Nota 2"),)

    assert cell_adjudication(declarations, sheet="Pag. 1", content="Nota 2") is not None
    # Whitespace is normalised the way the renderer normalises it before matching.
    assert cell_adjudication(declarations, sheet="Pag. 1", content="  Nota   2 ") is not None
    # The same label on the next page is a different note.
    assert cell_adjudication(declarations, sheet="Pag. 2", content="Nota 2") is None
    # A different pointer on the covered sheet is a different reference.
    assert cell_adjudication(declarations, sheet="Pag. 1", content="Nota 3") is None
    # A trailing stop is part of what the design published; the renderer matches
    # the published form exactly, and so must this.
    assert cell_adjudication(declarations, sheet="Pag. 1", content="Nota 2.") is None


def test_an_unresolved_pointer_stays_unresolved_however_it_was_adjudicated(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The transcription is still missing, and that is a different remedy.

    Asserted over constructed evidence, and over BOTH declaration families: an
    adjudicated representation and a recorded applicability reading are each
    offered alongside a note the design never defines, and neither may displace
    the condition.

    The corpus half of this test was removed rather than repaired. It asserted
    that the live screen still reported unresolved rows, and every one of the
    three it stood on was FALSE: modelos 200, 202 and 222 each define the note
    their pointer names, printing the label alone on its row with the wording
    beneath, and the definition grammar refused that shape. A condition whose
    only live members were reading defects cannot be held by asserting they
    stay. The condition is real and is proved here on input written for it.
    """
    from ..analysis.footnote_only_wire_facts import classify_pointer
    from ..analysis.footnote_pointer_notes import FootnotePointerNote, PointerEvidence

    # ``note`` carries the label the resolver builds - "nota 2" - so the detail
    # line names the definition the design owes rather than a bare digit.
    missing = PointerEvidence(
        cell="Nota 2", pointer="Nota 2", notes=(FootnotePointerNote(pointer="Nota 2", note="nota 2", text=""),)
    )
    outcomes = (
        classify_pointer(missing, resolved=0, adjudication=_declaration(), applicability=None),
        classify_pointer(missing, resolved=0, adjudication=None, applicability=_applicability_reading()),
        classify_pointer(missing, resolved=0, adjudication=_declaration(), applicability=_applicability_reading()),
    )
    for kind, detail in outcomes:
        assert kind == "pointer_unresolved"
        assert "nota 2" in detail
        assert kind in OUTSTANDING_KINDS


def test_an_applicability_reading_stops_a_cell_being_counted_as_unopened(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Modelo 353's read pointer is a covered row, not a pending one.

    The live case for the second adjudicated condition. The cell publishes
    ``Nota 4.``, the note it names says only which periods the slot applies to,
    and a declaration records that reading; the renderer therefore sends the
    field where every blank-``Contenido`` numeric field of its design goes. The
    screen used to report it as a reference nobody had opened.

    The row is asserted to still be PRESENT and merely reclassified, for the same
    reason its sibling condition is: a covered row that vanishes cannot be
    reconciled against the census, and a reader would not be able to see the
    mechanism working.
    """
    findings = revision_findings(authority, modelo="353", revision="2026-desde-02")
    covered = [item for item in findings if item.kind == "pointer_applicability_adjudicated"]
    assert covered, "modelo 353's read pointer stopped being reported at all"
    for item in covered:
        assert item.kind not in OUTSTANDING_KINDS
        # The detail quotes the note that was read and says what was concluded
        # from it, so the row carries what a re-reader needs.
        assert "Solo para periodos 02 y siguientes" in item.detail
        assert "applicability only" in item.detail


def test_the_declared_conditions_split_into_outstanding_and_covered() -> None:
    """The census cannot lose a condition to either side of the split."""
    assert set(OUTSTANDING_KINDS) < set(KINDS)
    assert set(KINDS) - set(OUTSTANDING_KINDS) == set(ADJUDICATED_KINDS)
    assert set(ADJUDICATED_KINDS) < set(KINDS)


def test_an_applicability_reading_pinned_elsewhere_covers_nothing(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The second declaration family is pinned exactly as the first is.

    Exercised against the SHIPPED readings twice - through the design's real
    parser-read source, which must select them, and through a source carrying a
    foreign digest, which must select none - and then against a reading authored
    here, to prove the sheet and the exact published pointer are both part of the
    match. Without this half a matcher that had stopped checking the pin would
    credit a reading of a file nobody read.
    """
    from ..pipeline.render_check import revision_render_inputs

    source = revision_render_inputs(authority, modelo="353", revision="2026-desde-02").joined.source
    live = pinned_applicability_readings(source)
    assert live, "the shipped applicability readings no longer reach modelo 353's design"

    reissued = source.model_copy(update={"source_sha256": _FOREIGN_SHA256})
    assert pinned_applicability_readings(reissued) == (), "a stale pin was admitted"
    assert (
        cell_applicability_reading(pinned_applicability_readings(reissued), sheet=live[0].sheet, content="Nota 4.")
        is None
    )

    authored = (_applicability_reading(sheet="Pag. 1", published_content="Nota 2"),)
    assert cell_applicability_reading(authored, sheet="Pag. 1", content="Nota 2") is not None
    assert cell_applicability_reading(authored, sheet="Pag. 1", content="  Nota   2 ") is not None
    assert cell_applicability_reading(authored, sheet="Pag. 2", content="Nota 2") is None
    assert cell_applicability_reading(authored, sheet="Pag. 1", content="Nota 3") is None
    assert cell_applicability_reading(authored, sheet="Pag. 1", content="Nota 2.") is None


def test_a_stale_pin_refuses_through_the_screens_own_predicate(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The refusal this screen must not mistake for silence, produced for real.

    The declarations are the SHIPPED ones for modelo 353's design, and the
    source is that design's own parser-read source reissued under a digest it
    does not carry - the exact shape of a pin that has gone stale because the
    design was replaced. Nothing is patched: the routed predicate validates the
    declaration set against the source it is handed and refuses.

    The second assertion is the whole reason this refusal was invisible. A
    ``RegistryValidationError`` IS a ``ValueError``, so a handler catching
    ``ValueError`` to skip revisions it cannot read claims this one too.
    """
    from ..pipeline.render_check import revision_render_inputs

    inputs = revision_render_inputs(authority, modelo="353", revision="2026-desde-02")
    field = inputs.joined.fields[0].parser_field
    reissued = inputs.joined.source.model_copy(update={"source_sha256": _FOREIGN_SHA256})

    with pytest.raises(RegistryValidationError, match="not pinned to the parser intermediate") as refusal:
        field_is_render_profile_eligible(field, reissued)

    assert isinstance(refusal.value, ValueError), (
        "a refusal that is not a ValueError would never have been swallowed by the skip handler, "
        "so this test would prove nothing about the classification below"
    )


class _RevisionDefinition:
    """One modelo definition carrying one revision id, and nothing else.

    Written here rather than taken from the authority because the subject under
    test is the SCREEN'S CLASSIFICATION of an error raised while walking a
    revision, not the walk itself. The error objects below are real - one is the
    refusal the routed predicate actually raises, the other the ``ValueError``
    ninety-four bundled revisions actually raise - and this pair only decides
    where they are delivered from.
    """

    def __init__(self) -> None:
        self.revisions = {"2026-desde-02": None}


class _AuthorityRaising:
    """An authority whose revision walk ends in one given error."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def modelo(self, modelo_id: str) -> _RevisionDefinition:
        return _RevisionDefinition()

    @property
    def catalogues(self) -> object:
        raise self._error


def test_screen_authority_refuses_a_stale_pin_instead_of_counting_it_as_nothing_to_read(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The two states must not collapse, and only the delivered error differs.

    Both runs below take the same path through the same screen and differ in one
    thing: which error the revision walk ends in. A revision that declares no
    export layout is inapplicable and is skipped, and the screen returns its
    (empty) findings. A revision whose pinned declarations refuse is a stale
    declaration in this repository's own tables, and the screen fails closed
    naming it. Before this, one handler caught both and the second was reported
    as the first - a revision that had silently stopped being screened,
    indistinguishable from one with nothing to read.
    """
    inputs = revision_render_inputs(authority, modelo="353", revision="2026-desde-02")
    reissued = inputs.joined.source.model_copy(update={"source_sha256": _FOREIGN_SHA256})
    with pytest.raises(RegistryValidationError) as captured:
        field_is_render_profile_eligible(inputs.joined.fields[0].parser_field, reissued)

    inapplicable = ValueError("353/2026-desde-02 declares no export layout to render")
    assert screen_authority(_AuthorityRaising(inapplicable), ("353",)) == ()

    with pytest.raises(RegistryValidationError, match="refused their own pinned declarations") as refused:
        screen_authority(_AuthorityRaising(captured.value), ("353",))
    assert "353/2026-desde-02" in str(refused.value)


def test_the_live_corpus_carries_no_refusal_today(authority: ValidatedRegistryAuthority) -> None:
    """The fix above is latent, not live, and this is what says so.

    Without it the gate above would be satisfied by a screen that refuses
    everything, and a reader could not tell whether the corpus was clean or the
    screen had stopped running. This screens the whole bundled authority and
    requires it to complete: every revision it skips today raises a plain
    ``ValueError``, and none of them is a refusal.
    """
    from ..analysis.corpus import bundled_modelo_ids

    assert screen_authority(authority, bundled_modelo_ids()) is not None
