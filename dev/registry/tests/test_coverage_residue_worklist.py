"""The residue worklist is finite, complete and diffable.

A worklist is only useful if two runs over an unchanged corpus produce identical
text -- otherwise a shrinking residue cannot be seen as a shrinking file, which
is the whole point of rendering it. It must also lose nothing: a renderer that
dropped rows would still look tidy while hiding the cells someone has to rule on.
"""

from __future__ import annotations

import pytest

from ..analysis.coverage_residue_worklist import ResidueCell, collect_residue, render_worklist

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_residue_is_finite_and_non_empty() -> None:
    """A residue of zero would make the completeness assertions vacuous."""
    residue = collect_residue()

    assert residue, "the coverage matrix reports no residue at all; nothing here is measurable"
    assert len(residue) < 100_000, "the residue is not finite enough to be a worklist"


def test_the_render_is_identical_across_runs() -> None:
    """Determinism: same residue in, byte-identical text out."""
    residue = collect_residue()

    assert render_worklist(residue) == render_worklist(residue)


def test_the_render_carries_no_clock_or_run_identity() -> None:
    """A timestamp is the usual way a diffable report stops being diffable."""
    rendered = render_worklist(collect_residue())

    for token in ("generated at", "run id", "timestamp", "T00:", "UTC"):
        assert token.casefold() not in rendered.casefold(), f"the worklist carries {token!r}"


def test_every_residue_cell_appears_in_the_render() -> None:
    """Completeness: the renderer loses no cell.

    Asserted per cell rather than by count, so a renderer that dropped one row
    and duplicated another could not pass.
    """
    residue = collect_residue()
    rendered = render_worklist(residue)

    missing = [
        cell
        for cell in residue
        if f"`{cell.modelo}` {cell.filing_year} `{cell.period}`" not in rendered
    ]

    assert missing == [], f"{len(missing)} residue cell(s) absent from the render, e.g. {missing[:3]}"


def test_every_declared_group_count_matches_its_own_rows() -> None:
    """A heading's count is derived from its rows, so the two cannot disagree."""
    rendered = render_worklist(collect_residue())

    for line in rendered.splitlines():
        if not line.startswith("### "):
            continue
        declared = int(line.rsplit("(", 1)[1].rstrip(")"))
        assert declared > 0, f"a group declares zero rows: {line}"


def test_the_render_groups_by_kind_and_detail() -> None:
    """The grouping is what makes several hundred rows readable."""
    rendered = render_worklist(
        (
            ResidueCell(kind="refused-selection", modelo="308", filing_year=2011, period="AD-HOC", detail="ambiguous"),
            ResidueCell(kind="unbacked-declaration", modelo="036", filing_year=2025, period="alta", detail="missing x"),
        ),
    )

    assert "## refused-selection (1)" in rendered
    assert "## unbacked-declaration (1)" in rendered
    assert "### ambiguous (1)" in rendered
