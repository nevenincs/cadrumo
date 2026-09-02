"""Real-behaviour tests for the casilla identifier grammar screen.

The classifier is exercised directly on its rules, and the census is driven
through the bundled registry via the validated authority.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..analysis.casilla_id_grammar import GRAMMARS, classify_casilla_id, screen_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


@pytest.mark.parametrize(
    ("casilla_id", "grammar"),
    [
        ("109", "numeric"),
        ("0001", "numeric"),
        ("iva.cuota-deducible-total", "dotted"),
        ("declarante-nif", "kebab"),
        ("490-01-tipo-declaracion-13", "kebab"),
        ("TIPOTRIBUTACION", "token"),
        ("A", "token"),
        ("DP200013:00417", "page_qualified"),
        ("DP200014:bin-aplicada-maxima", "page_qualified"),
    ],
)
def test_each_grammar_classifies_its_own_shape(casilla_id: str, grammar: str) -> None:
    """Every named grammar recognises a real identifier of its own shape."""
    assert classify_casilla_id(casilla_id) == grammar


@pytest.mark.parametrize("casilla_id", ["", "with space", "DP200013:", ":00417", "DP200013:with space"])
def test_unrecognised_shapes_are_not_forced_into_a_grammar(casilla_id: str) -> None:
    """An unrecognised shape is reported, never absorbed by the nearest grammar."""
    assert classify_casilla_id(casilla_id) == "unclassified"


def test_a_page_qualifier_cannot_absorb_an_unclassifiable_tail() -> None:
    """The colon form is only page-qualified when its tail classifies on its own.

    This is the detector case for the widening hazard: a head-only rule would
    accept any tail whatever, so an unrecognised identifier could be hidden
    behind a valid page prefix.
    """
    assert classify_casilla_id("DP200013:00417") == "page_qualified"
    assert classify_casilla_id("DP200013:not a tail") == "unclassified"


def test_every_bundled_identifier_falls_in_a_named_grammar(authority: ValidatedRegistryAuthority) -> None:
    """No identifier in the shipped registry is unclassified.

    A non-zero count here is not a test failure to suppress: it means the
    corpus carries a shape the declared grammar set does not name, and the set
    is what an identifier contract would be written from.
    """
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    modelo_ids = tuple(sorted(str(code) for code in registry_modelo_codes()))
    uses = screen_authority(authority, modelo_ids)
    unclassified = {use.modelo: dict(use.counts).get("unclassified", 0) for use in uses}
    assert not {modelo: count for modelo, count in unclassified.items() if count}


def test_the_corpus_uses_more_than_one_grammar_and_modelos_mix_them(authority: ValidatedRegistryAuthority) -> None:
    """The condition the screen exists to surface is present and measurable."""
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    modelo_ids = tuple(sorted(str(code) for code in registry_modelo_codes()))
    uses = screen_authority(authority, modelo_ids)
    grammars_seen = {name for use in uses for name in use.grammars_used}
    assert grammars_seen <= set(GRAMMARS)
    assert len(grammars_seen) > 1
    assert [use.modelo for use in uses if use.mixes], "at least one modelo mixes grammars"
