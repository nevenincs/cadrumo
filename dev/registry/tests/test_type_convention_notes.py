"""Real-behaviour tests for the type-convention note screen.

The screen's value rests entirely on which notes it selects, so the selector is
proven on constructed input: it must fire on a type the design uses, stay quiet
on one it does not, and not confuse two type codes where one is a prefix of the
other. The corpus is then asserted by shape, because the counts move whenever a
design is added or re-transcribed.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..analysis.type_convention_notes import KINDS, revision_findings, screen_authority, types_named_in

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NUMERIC_RULE = "Los campos numéricos (Num) deberán estar alineados a la derecha rellenando con ceros."


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_a_note_naming_a_type_the_design_uses_is_selected() -> None:
    """The plainest case: a convention for a type present in the design."""
    assert types_named_in(_NUMERIC_RULE, frozenset({"Num", "An"})) == ("Num",)


def test_a_note_naming_a_type_the_design_does_not_use_is_ignored() -> None:
    """The candidate set is the design's own, so an absent code cannot match.

    Without this the selector could match any parenthesised token and still pass
    the case above, which would make the population meaningless.
    """
    assert types_named_in(_NUMERIC_RULE, frozenset({"An"})) == ()


def test_a_shorter_type_code_does_not_match_a_longer_one() -> None:
    """``(N)`` and ``(Num)`` are different types and must not be conflated.

    The signed-numeric code is a prefix of the numeric one, so an unanchored
    match would report every numeric convention as also settling signed fields -
    and sign is exactly the property those two notes differ on.
    """
    assert types_named_in(_NUMERIC_RULE, frozenset({"N"})) == ()
    assert types_named_in("Los campos con signo (N) admiten el carácter N.", frozenset({"N", "Num"})) == ("N",)


def test_a_bare_code_outside_parentheses_is_not_a_type_reference() -> None:
    """An AEAT type code is a short token that occurs in ordinary Spanish.

    ``N`` appears inside words and as an initial throughout these designs, so
    matching one bare would fire on prose that names no type at all.
    """
    assert types_named_in("Numerar los campos y alinear a la derecha.", frozenset({"N", "Num"})) == ()


def test_the_screen_finds_the_conventions_modelo_202_states(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The design that motivated this screen still carries its conventions.

    Modelo 202 settles alphanumeric, numeric and signed-numeric representation
    in general notes. Held by the types named rather than by note labels or
    counts, because the labels are the design's numbering and would change on a
    re-transcription without the property changing.
    """
    findings = revision_findings(authority, modelo="202", revision="2025-y-siguientes")
    assert findings, "the design that motivated this screen reports nothing"
    named = {code for item in findings for code in item.types}
    assert {"An", "Num"} <= named
    for item in findings:
        assert item.kind in KINDS
        assert item.text
        assert item.fields_governed == sum(count for _, count in item.field_counts)


def test_each_design_is_reported_once_however_many_revisions_share_it(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A transcription reused across revisions contributes one set of rows.

    Several revisions of a modelo share one design. Counting per revision would
    scale the population by how often a design was reused rather than by how
    much wording it carries, which is the shape that makes a census look like
    progress.
    """
    from ..analysis.corpus import bundled_modelo_ids

    findings = screen_authority(authority, bundled_modelo_ids())
    assert findings, "the screen lost its live population"
    seen: dict[tuple[str, str, str], int] = {}
    for item in findings:
        key = (item.design, item.sheet, item.label)
        seen[key] = seen.get(key, 0) + 1
    assert max(seen.values()) == 1, "a design's note was reported more than once"
