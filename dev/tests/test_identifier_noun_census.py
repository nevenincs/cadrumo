"""Real-source contract tests for the identifier noun-vocabulary census.

The census exists to prove that the original suffix-heuristic count
is a FLOOR, so the load-bearing test is not "it returns records" but "it finds
the specific field whose invisibility to the suffix sweep is what proved the
floor". That case is ``Deuda.clave_liquidacion``: an AEAT-issued identifier
this codebase enrols by name, carrying no identifier suffix, documented in
prose as an *identifier*.

The negative controls matter as much. An instrument that returns the expected
answer proves nothing until it has been watched returning a different one, so
each control below is a case the census MUST be silent about — a field with no
identifier prose, and a vocabulary word that appears nowhere.
"""

from __future__ import annotations

import pytest

from dev.identity.identifier_noun_census import (
    NOUN_VOCABULARY,
    SUFFIX_HEURISTIC,
    NounCandidate,
    attribute_prose,
    census_sources,
    fold_accents,
    matched_nouns,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_MOTIVATING_SOURCE = '''
from pydantic import BaseModel, Field


class Deuda(BaseModel):
    """One row from AEAT's debt listing.

    Attributes:
        clave_liquidacion: AEAT's identifier for the liquidación the debt
            arises from, as printed on the listing row.
        importe_pendiente: The outstanding amount, a non-negative magnitude.
        situacion: AEAT's procedural-state label, carried as free text.
    """

    clave_liquidacion: str = Field(min_length=1, max_length=64)
    importe_pendiente: str
    situacion: str = Field(min_length=1, max_length=64)
'''


def _by_field(records: tuple[NounCandidate, ...]) -> dict[str, NounCandidate]:
    return {record.field: record for record in records}


def test_finds_the_field_whose_invisibility_proved_the_floor() -> None:
    """``clave_liquidacion`` is found, and found as NOUN-ONLY.

    This is the whole justification for the census. The field is an AEAT-issued
    identifier with no identifier suffix, so the original sweep could not see
    it; reading the prose finds it. If this ever fails, the census has stopped
    doing the one thing it was built for.
    """
    records = _by_field(census_sources((("src/cadrumo/x.py", _MOTIVATING_SOURCE),)))

    assert "clave_liquidacion" in records
    found = records["clave_liquidacion"]
    assert found.matches_suffix_heuristic is False, "the suffix sweep must not be credited with this find"
    assert "identifier" in found.nouns
    assert found.bare_str is True


def test_is_silent_about_fields_with_no_identifier_prose() -> None:
    """Negative control: documented non-identifiers must not be reported.

    ``importe_pendiente`` is an amount and ``situacion`` is an adjudicated
    non-identifier excluded from the taxonomy by name. Both are documented in the
    same ``Attributes:`` block as the field above, so a census that reported
    them would be matching the block rather than the prose.
    """
    records = _by_field(census_sources((("src/cadrumo/x.py", _MOTIVATING_SOURCE),)))

    assert "importe_pendiente" not in records
    assert "situacion" not in records


def test_reports_nothing_for_a_module_with_no_documented_identifiers() -> None:
    """Negative control: the instrument can return empty."""
    source = '''
from pydantic import BaseModel


class Amounts(BaseModel):
    """Money only.

    Attributes:
        total: The sum of the lines.
    """

    total: str
'''
    assert census_sources((("src/cadrumo/y.py", source),)) == ()


def test_accent_folding_makes_numero_one_word() -> None:
    """``número`` and ``numero`` are the same word for this sweep."""
    assert fold_accents("Número") == "numero"
    assert matched_nouns("el número de justificante") == ("numero",)


def test_matching_is_whole_word_not_substring() -> None:
    """A vocabulary noun inside a longer unrelated word is not a match.

    The census is read as evidence about a field's documented meaning, so a
    substring hit would inflate the candidate set with words that merely
    contain a stem.
    """
    assert matched_nouns("claveteado") == ()
    assert matched_nouns("this clave is real") == ("clave",)


def test_attribute_prose_folds_continuation_lines() -> None:
    """The identifying noun is frequently on the second line of a description."""
    docstring = "Doc.\n\nAttributes:\n    thing: A value that is\n        really an identificador.\n"
    prose = attribute_prose(docstring)

    assert "identificador" in prose["thing"]
    assert matched_nouns(prose["thing"]) == ("identificador",)


def test_field_description_is_read_as_a_second_documentation_channel() -> None:
    """A field documented only through ``Field(description=...)`` is still found.

    This tree documents fields two ways. Reading one channel would under-report,
    which is the same failure at a smaller scale as the suffix sweep this census
    corrects.
    """
    source = '''
from pydantic import BaseModel, Field


class Thing(BaseModel):
    """No attributes block at all."""

    marker: str = Field(description="The AEAT identificador for this row.")
'''
    records = _by_field(census_sources((("src/cadrumo/z.py", source),)))

    assert "marker" in records
    assert records["marker"].source == "field_description"


def test_suffix_heuristic_restatement_matches_the_original_vocabulary() -> None:
    """The restated suffix list is the original one, and is used only for the delta.

    If this drifts, ``matches_suffix_heuristic`` stops meaning "the first census
    already had this" and the floor-versus-ceiling measurement becomes
    uninterpretable.
    """
    assert set(SUFFIX_HEURISTIC) == {"_id", "_ref", "_code", "_key", "_number", "_csv"}


def test_vocabulary_is_accent_free_so_folding_is_the_only_normaliser() -> None:
    """Every vocabulary entry is already folded, so comparison is unambiguous."""
    for noun in NOUN_VOCABULARY:
        assert fold_accents(noun) == noun, noun
