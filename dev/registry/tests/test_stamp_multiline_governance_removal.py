"""A governance stamp must be replaceable when the previous one spans several lines.

``reviewed_by`` carries a reviewer's scope statement, which grows long enough that it
is routinely authored as a TOML multi-line basic string. The manifest writer edits
whole ``key = value`` lines so a hand-authored file stays reviewable, and it once
assumed a scalar assignment is always ONE physical line. A triple-quoted value breaks
that assumption: removing only the line carrying the key orphans the prose and the
closing delimiter, and a reviewer note opening ``agent: ...`` then parses as a key
with a colon where an equals belongs.
"""

from __future__ import annotations

import tomllib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_HEADER = '[revisions."2019-y-siguientes"]'


def _manifest(reviewed_by_block: str) -> str:
    return (
        f"{_HEADER}\n"
        'authority_grade = "applicability"\n'
        "valid_from = 2019-01-01\n"
        'review_status = "agent_reviewed"\n'
        f"{reviewed_by_block}"
        "reviewed_at = 2026-08-20\n"
    )


def test_a_multiline_reviewer_note_is_replaced_whole() -> None:
    from ..conformance._stamp import _apply_governance

    text = _manifest('reviewed_by = """\nagent: first line; second clause\nand a third\n"""\n')

    rewritten = _apply_governance(
        text,
        "2019-y-siguientes",
        {"review_status": '"agent_reviewed"', "reviewed_by": '"agent: replacement"'},
    )

    parsed = tomllib.loads(rewritten)["revisions"]["2019-y-siguientes"]
    assert parsed["reviewed_by"] == "agent: replacement"
    # The orphan is what broke it: prose surviving with no key to belong to.
    assert "first line" not in rewritten
    assert "and a third" not in rewritten


def test_a_single_line_reviewer_note_is_still_replaced() -> None:
    """The control. A fix that only handled the multi-line form would pass the test above."""
    from ..conformance._stamp import _apply_governance

    text = _manifest('reviewed_by = "agent: one line"\n')

    rewritten = _apply_governance(
        text,
        "2019-y-siguientes",
        {"review_status": '"agent_reviewed"', "reviewed_by": '"agent: replacement"'},
    )

    parsed = tomllib.loads(rewritten)["revisions"]["2019-y-siguientes"]
    assert parsed["reviewed_by"] == "agent: replacement"
    assert "one line" not in rewritten


def test_neighbouring_declarations_survive_the_removal() -> None:
    """The span must stop at the closing delimiter, not run on into the rest of the table."""
    from ..conformance._stamp import _apply_governance

    text = (
        f"{_HEADER}\n"
        'reviewed_by = """\nagent: note\n"""\n'
        'authority_grade = "applicability"\n'
        'legal_refs = ["orden-1999-11-17:apartado-quinto"]\n'
    )

    rewritten = _apply_governance(text, "2019-y-siguientes", {"reviewed_by": '"agent: replacement"'})

    parsed = tomllib.loads(rewritten)["revisions"]["2019-y-siguientes"]
    assert parsed["authority_grade"] == "applicability"
    assert parsed["legal_refs"] == ["orden-1999-11-17:apartado-quinto"]


def test_a_bracket_initial_prose_line_does_not_end_the_revision_table() -> None:
    """A wrapped reviewer line starting with "[" is prose, not a table header.

    Modelo 840's reviewed_by cites AEAT box numbers, and the writer's wrap put
    ``[13]. VERIFIED -- ...`` at the start of a physical line. The table-end scan
    looked for the next line beginning with a bracket, took that prose line for a
    new TOML table, and truncated the revision table thirty lines early; the
    rebuild then emitted the remaining prose and the trailing declarations
    outside any table, so the manifest stopped parsing and the revision was
    unstampable while its neighbours stamped cleanly.
    """
    from ..conformance._stamp import _apply_governance

    block = (
        'reviewed_by = """\n'
        "agent: coverage 0 -> 15 of 108. AEAT prints them as [14] at @270+4 and\n"
        "[13]. VERIFIED -- the wrap put a bracket at the start of this line\n"
        "and the scan must not read it as a table header.\n"
        '"""\n'
    )
    neighbour = '\n[revisions."2019-y-siguientes".family_dispositions.formulas]\nreason = "unchanged neighbour"\n'

    rewritten = _apply_governance(
        _manifest(block) + neighbour,
        "2019-y-siguientes",
        {"review_status": '"agent_reviewed"', "reviewed_by": '"agent: replacement"'},
    )

    parsed = tomllib.loads(rewritten)["revisions"]["2019-y-siguientes"]
    assert parsed["reviewed_by"] == "agent: replacement"
    # The whole prose span goes, including the bracket-initial line.
    assert "VERIFIED" not in rewritten
    assert "@270+4" not in rewritten
    # The real table that follows is untouched.
    assert parsed["family_dispositions"]["formulas"]["reason"] == "unchanged neighbour"
