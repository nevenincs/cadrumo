"""Real-behaviour tests for the pointer-only wire fact screen.

The screen's job is to hand a rule author the fields whose wire fact sits behind
a cross-reference, together with the wording behind it. Two things therefore
have to hold: the population must be the one the eligibility predicate would
newly admit, and the reading aid must not be mistaken for a verdict. The second
carries a live counterexample, because it was very nearly reported as one.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..analysis.footnote_only_wire_facts import KINDS, revision_findings, would_become_eligible
from ..analysis.footnote_pointer_notes import note_definitions
from ..pipeline._render_profile import project_render_profile_eligibility

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
    reported = {
        (field.parser_field.sheet, field.parser_field.source_row)
        for field in inputs.joined.fields
        if would_become_eligible(field.parser_field)
    }
    assert reported, "no field would become eligible, so the screen measures nothing"
    for field in inputs.joined.fields:
        parser_field = field.parser_field
        if (parser_field.sheet, parser_field.source_row) not in reported:
            continue
        # Rejected as it stands, admitted once the pointer stops counting as the
        # design's own statement. Both halves matter: a field already eligible
        # needs no pointer argument at all.
        assert not project_render_profile_eligibility([parser_field]).all_fields
        assert project_render_profile_eligibility(
            [parser_field.model_copy(update={"content": None})]
        ).all_fields


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
    extracted = design_transcription_path(corpus_path).read_text(encoding="utf-8")
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
