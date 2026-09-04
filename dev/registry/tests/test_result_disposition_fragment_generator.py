"""Tests for the result-disposition fragment generator.

The module writes registry declarations and takes an ``--apply`` flag, and had
no tests: `dev.quality.module_test_reach` ranks it first alongside two import
codemods for exactly that pair of properties. The property most worth holding is
therefore not what it renders but what it does NOT do without ``--apply``.

The renderer's two branches carry the module's actual judgement. A modelo whose
diseño never declares a "Tipo de declaracion" field is declared not applicable
with the scanned file count as its evidence, and one that does gets the letters
the diseño states. Those are different declarations about the registry, and the
difference is one ``None``.
"""

from __future__ import annotations

import pathlib

import pytest

from ..result_disposition_fragment_generator import (
    CAMPAIGN_OWNED_MODELOS,
    _render,
    plan_fragments,
    write_fragments,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_dry_run_writes_nothing(tmp_path: pathlib.Path) -> None:
    """The safety property of a generator that takes ``--apply``.

    An untested module that writes source files behind a flag is the highest-cost
    kind a repository holds, and the flag is only a safeguard if the unflagged
    path is proven inert. Asserted against a real planning run over the live
    registry, writing into an empty directory that must stay empty.
    """
    planned = write_fragments(tmp_path, apply=False)

    assert planned, "nothing was planned, so this proves nothing"
    assert list(tmp_path.rglob("*")) == [], "a dry run created files"


def test_every_planned_path_sits_under_the_root_it_was_given(tmp_path: pathlib.Path) -> None:
    """A generator that escapes its root writes into the real tree from a test."""
    for fragment in plan_fragments(tmp_path):
        assert tmp_path in fragment.path.parents


def test_the_not_applicable_branch_carries_its_measured_absence() -> None:
    """A modelo with no such field is declared informative, with the count as evidence.

    The absence is the declaration's whole justification, so the number of files
    scanned to establish it belongs in the text rather than in the author's
    memory.
    """
    body = _render("347", "2025", negative=None, zero=None, note="", scanned=14)

    assert "applicable = false" in body
    assert "not_applicable_reason" in body
    assert "14 corpus files" in body
    assert "negative_disposition" not in body


def test_the_applicable_branch_carries_the_letters_the_diseno_states() -> None:
    """The letters are the disposition, so they are rendered verbatim."""
    body = _render("303", "2025", negative="C", zero="N", note="Admite B, C, D, N", scanned=9)

    assert "applicable = true" in body
    assert 'negative_disposition = "C"' in body
    assert 'zero_disposition = "N"' in body
    assert "Admite B, C, D, N" in body


def test_a_note_carrying_a_quote_cannot_break_the_declaration() -> None:
    """The rendered fragment is TOML, and a raw double quote would end the string.

    The note comes from a diseño this project does not control, so this is a
    property of the input rather than a hypothetical.
    """
    body = _render("100", "2025", negative="C", zero="N", note='He said "B" here', scanned=1)

    assert 'diseno_note = "' in body
    assert '"B"' not in body.split("diseno_note = ")[1]


def test_a_long_note_is_truncated_rather_than_carried_whole() -> None:
    """The fragment is a declaration, not a transcription of the design."""
    body = _render("100", "2025", negative="C", zero="N", note="x" * 500, scanned=1)

    assert "x" * 180 in body
    assert "x" * 181 not in body


def test_the_plan_covers_only_filing_grade_revisions_outside_owned_trees() -> None:
    """Two exclusions, both deliberate, and neither visible in the output rows.

    A revision below filing grade has no result to dispose of, and two modelos
    are owned by another campaign whose fragments this generator must not write.
    Asserted against the live registry because that is where both facts live.
    """
    from cadrumo.core.authority_grade import RegistryAuthorityGrade
    from cadrumo.core.resources.bundled_data import bundled_path
    from cadrumo.domain.calculations.registry.loader import load_registry_tree

    planned = plan_fragments()
    assert planned, "nothing was planned, so this proves nothing"

    assert CAMPAIGN_OWNED_MODELOS, "no modelo is owned, so the exclusion proves nothing"
    assert not ({fragment.modelo for fragment in planned} & CAMPAIGN_OWNED_MODELOS)

    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    filing = {
        (definition.id, str(revision.id))
        for definition in modelos
        for revision in definition.revisions.values()
        if revision.authority_grade is RegistryAuthorityGrade.FILING
    }
    assert {(fragment.modelo, fragment.revision) for fragment in planned} <= filing


def test_every_fragment_declares_one_of_the_two_dispositions() -> None:
    """Applicable and not-applicable are the whole vocabulary, and both occur.

    A run where every fragment took one branch would leave the other unexercised
    against the live corpus while still passing every constructed test above.
    """
    planned = plan_fragments()
    applicable = [fragment for fragment in planned if fragment.applicable]
    informative = [fragment for fragment in planned if not fragment.applicable]

    assert applicable and informative, "the live corpus exercises only one branch"
    for fragment in planned:
        marker = "applicable = true" if fragment.applicable else "applicable = false"
        assert marker in fragment.body
