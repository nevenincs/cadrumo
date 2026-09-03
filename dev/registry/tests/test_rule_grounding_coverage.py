"""Real-behaviour tests for the rule-grounding coverage join.

The join's whole claim is that a field's grounding is found through its AEAT
type. Two failure modes would make it useless while still producing rows: it
could report every field as grounded, or it could match a field against a
convention for a different type. Both are asserted against, on the live corpus,
because the corpus is what supplies the mixture of grounded and ungrounded
fields the join exists to separate.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..analysis.corpus import bundled_modelo_ids
from ..analysis.rule_grounding_coverage import KINDS, revision_findings, screen_authority
from ..analysis.type_convention_notes import revision_findings as type_conventions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


@pytest.fixture(scope="module")
def corpus(authority: ValidatedRegistryAuthority) -> tuple[object, ...]:
    return screen_authority(authority, bundled_modelo_ids())


def test_the_join_separates_grounded_from_ungrounded_fields(corpus: tuple[object, ...]) -> None:
    """Both conditions occur, so the join is discriminating rather than uniform.

    A join reporting every field the same way would still produce rows and a
    census, and would tell the authoring task nothing. Held as presence of both
    populations, not as their sizes.
    """
    assert corpus, "the join lost its live population"
    kinds = {item.kind for item in corpus}
    assert kinds == set(KINDS), "the join no longer separates the two conditions"


def test_a_grounded_field_names_notes_that_really_cover_its_type(
    authority: ValidatedRegistryAuthority, corpus: tuple[object, ...]
) -> None:
    """Every note credited to a field states a convention for that field's type.

    This is the assertion that stops the join drifting into matching a field
    against any convention its design happens to carry. Checked against the
    convention screen's own output rather than against a copy of its rule.
    """
    grounded = [item for item in corpus if item.kind == "grounded_by_type_convention"]
    assert grounded, "no field is grounded, so this proves nothing"
    for item in grounded:
        assert item.notes
        covering = {
            f"{convention.sheet}:{convention.label}"
            for convention in type_conventions(authority, modelo=item.modelo, revision=item.revision)
            if item.aeat_type in convention.types
        }
        assert set(item.notes) <= covering
        assert set(item.notes) == covering


def test_an_ungrounded_field_has_no_convention_for_its_type(
    authority: ValidatedRegistryAuthority, corpus: tuple[object, ...]
) -> None:
    """A field is only called ungrounded when its design really is silent.

    The complement of the test above, and the one that catches the join
    under-reporting: a lookup miss caused by a key mismatch would report a
    grounded field as ungrounded and look exactly like a real gap.
    """
    ungrounded = [item for item in corpus if item.kind == "ungrounded"]
    assert ungrounded, "nothing is ungrounded, so this proves nothing"
    for item in ungrounded:
        assert item.notes == ()
        for convention in type_conventions(authority, modelo=item.modelo, revision=item.revision):
            assert item.aeat_type not in convention.types


def test_a_revision_with_no_field_needing_a_rule_yields_nothing(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The join reports fields, never conventions.

    A design can state conventions while no field of it needs a rule, and
    reporting those would count wording as work.
    """
    assert revision_findings(authority, modelo="390", revision="2025-y-siguientes") == ()
