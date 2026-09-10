"""Real-behaviour tests for the casilla identifier grammar screen.

The classifier is exercised directly on its rules, and the census is driven
through the bundled registry via the validated authority.
"""

from __future__ import annotations

import dataclasses

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from dev.registry.compiler.authority import compiled_bundled_authority

from ..analysis.casilla_id_grammar import GRAMMARS, classify_casilla_id, screen_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


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


def test_a_modelo_mixing_grammars_is_reported_and_one_that_does_not_is_not(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The condition the screen exists to surface is detected and measured.

    Constructed on copies of two single-grammar modelos, one numeric and one
    dotted: one casilla of the numeric modelo is re-declared in the kebab
    grammar, the shape an author reaching for a descriptive name leaves in a
    numbered design. The screen must count the planted identifier under its own
    grammar, report that modelo and only that modelo as mixing, and keep seeing
    the untouched modelo's grammar. Constructed rather than read from the corpus,
    so harmonising every live modelo onto one grammar leaves the proof standing.
    """
    numeric, dotted = authority.modelo("111"), authority.modelo("036")
    (only_numeric,) = screen_authority(authority, ("111",))
    assert [name for name, _ in only_numeric.counts] == ["numeric"], "the constructed mix must be the only one"
    numeric_total = only_numeric.counts[0][1]
    assert not screen_authority(authority, ("036",))[0].mixes

    revision_id = min(numeric.revisions)
    revision = numeric.revisions[revision_id]
    victim = revision.casillas[0]
    renamed = victim.model_copy(update={"id": f"{victim.id}-renombrada"})
    assert classify_casilla_id(str(renamed.id)) == "kebab"
    planted_revision = revision.model_copy(
        update={"casillas": tuple(renamed if item is victim else item for item in revision.casillas)}
    )
    planted_modelo = numeric.model_copy(update={"revisions": {**numeric.revisions, revision_id: planted_revision}})
    modelos = (planted_modelo, dotted)
    planted = dataclasses.replace(
        authority,
        modelos=modelos,
        _modelos_by_id={modelo.id: modelo for modelo in modelos},
        _registry_validated=False,
        _validated_modelos=set(),
        _snapshots={},
    )

    uses = screen_authority(planted, ("036", "111"))
    grammars_seen = {name for use in uses for name in use.grammars_used}
    assert grammars_seen <= set(GRAMMARS)
    assert grammars_seen == {"numeric", "kebab", "dotted"}
    assert [use.modelo for use in uses if use.mixes] == ["111"]
    mixing = next(use for use in uses if use.modelo == "111")
    assert mixing.counts == (("numeric", numeric_total - 1), ("kebab", 1))
