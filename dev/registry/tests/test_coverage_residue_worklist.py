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


def _heading_row_counts(rendered: str) -> list[tuple[str, int, int]]:
    """Return ``(heading, declared count, rows printed beneath it)`` for every heading.

    Both levels are read. The renderer derives a ``##`` count by summing across
    its details and a ``###`` count by taking a plain length, so the two are two
    different expressions and each needs its own comparison.
    """
    headings: list[str] = []
    declared: list[int] = []
    actual: list[int] = []
    open_indexes: dict[int, int] = {}
    for line in rendered.splitlines():
        level = 3 if line.startswith("### ") else 2 if line.startswith("## ") else 0
        if level:
            if level == 2:
                open_indexes.pop(3, None)
            open_indexes[level] = len(headings)
            headings.append(line)
            declared.append(int(line.rsplit("(", 1)[1].rstrip(")")))
            actual.append(0)
        elif line.startswith("- "):
            for index in open_indexes.values():
                actual[index] += 1
    return list(zip(headings, declared, actual, strict=True))


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

    missing = [cell for cell in residue if f"`{cell.modelo}` {cell.filing_year} `{cell.period}`" not in rendered]

    assert missing == [], f"{len(missing)} residue cell(s) absent from the render, e.g. {missing[:3]}"


def test_every_declared_group_count_matches_its_own_rows() -> None:
    """Each heading's count must equal the rows printed beneath it.

    The name promises a comparison this case did not make. It asserted only
    that a declared count was positive, which every heading the renderer can
    emit satisfies by construction, and it never read the ``##`` counts at
    all -- the ones derived by a different expression, a sum across details.
    A kind heading could disagree with its own rows with nothing here to say
    so.
    """
    rendered = render_worklist(collect_residue())

    groups = _heading_row_counts(rendered)
    kinds = [heading for heading, _, _ in groups if not heading.startswith("### ")]
    details = [heading for heading, _, _ in groups if heading.startswith("### ")]

    # Both levels must be present or the comparison below reads nothing: an
    # empty residue renders a header block carrying no heading at all, and
    # the loop this replaces then ran zero times and reported clean.
    assert kinds, "the render carries no kind heading, so the comparison below reads nothing"
    assert details, "the render carries no detail heading, so the comparison below reads nothing"

    disagreeing = [(heading, count, rows) for heading, count, rows in groups if count != rows]

    assert disagreeing == [], f"heading(s) declaring a count their rows do not support: {disagreeing}"


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
