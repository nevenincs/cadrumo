"""Emit the coverage residue as a finite, diffable worklist.

The temporal coverage matrix resolves nearly every declared cell on its own. What
it cannot resolve is a residue: cells whose disposition needs a human ruling, not
another pass of the deriver. Left in someone's head, that residue is invisible;
left as source annotations, it rots against the tree it describes.

This emitter renders it as ordered text so two runs diff cleanly and a shrinking
residue is visible as a shrinking file. Nothing here is stamped with a clock or a
run id: a report that changes when nothing changed cannot be diffed, and a
timestamp is the usual way that happens.

Two residues are reported, because they need different rulings.

**Refused cells** are coordinates the law-selection could not settle -- typically
two revisions both claiming a boundary period. Only a reading of the governing
orden settles which applies, and until it does the cell resolves to nothing.

**Unbacked cells** are coordinates the declaration claims support for while the
corpus does not fully back them: no evidence-backed source artefact, no
filing-grade revision, or no law-resolvable revision at all. Each is a decision
about whether to ground the year, lower the claim, or withdraw the cell.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class ResidueCell:
    """One cell the coverage matrix cannot settle without a ruling."""

    kind: str
    modelo: str
    filing_year: int
    period: str
    detail: str


def collect_residue() -> tuple[ResidueCell, ...]:
    """Collect every residue cell from the live coverage matrix and gap projection.

    Returns:
        The residue, sorted so two runs over an unchanged corpus are identical.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..temporal_coverage import compose_temporal_coverage

    authority = bundled_authority()
    authority.validate_registry()
    report = compose_temporal_coverage(authority=authority)

    cells: list[ResidueCell] = [
        ResidueCell(
            kind="refused-selection",
            modelo=str(row.modelo),
            filing_year=int(row.filing_year),
            period=str(row.period),
            detail=str(row.failure_detail or row.failure_code or "law selection refused"),
        )
        for row in report.refused_rows
    ]
    cells.extend(
        ResidueCell(
            kind="unbacked-declaration",
            modelo=str(gap.modelo),
            filing_year=int(gap.filing_year),
            period=str(gap.period),
            detail=f"missing {gap.missing_prerequisite}",
        )
        for gap in authority.supported_filing_year_gaps
    )
    return tuple(sorted(set(cells)))


def render_worklist(cells: tuple[ResidueCell, ...]) -> str:
    """Render ``cells`` as deterministic, diffable text.

    Grouped by residue kind, then by the missing prerequisite or failure, then by
    modelo. Grouping is what makes the file readable at 800-odd rows; the counts
    are derived from the rows beneath them rather than asserted, so a count and
    its rows cannot disagree.
    """
    by_kind: dict[str, dict[str, list[ResidueCell]]] = defaultdict(lambda: defaultdict(list))
    for cell in cells:
        by_kind[cell.kind][cell.detail].append(cell)

    lines: list[str] = [
        "# Registry coverage residue worklist",
        "",
        "Every cell below needs a ruling, not another derivation pass. Regenerate",
        "with `python -m dev.registry.analysis.coverage_residue_worklist`.",
        "",
        f"Total residue cells: {len(cells)}",
        "",
    ]
    for kind in sorted(by_kind):
        kind_cells = sum(len(rows) for rows in by_kind[kind].values())
        lines.append(f"## {kind} ({kind_cells})")
        lines.append("")
        for detail in sorted(by_kind[kind]):
            rows = sorted(by_kind[kind][detail])
            lines.append(f"### {detail} ({len(rows)})")
            lines.append("")
            for row in rows:
                lines.append(f"- `{row.modelo}` {row.filing_year} `{row.period}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    """Print the rendered worklist."""
    print(render_worklist(collect_residue()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ResidueCell",
    "collect_residue",
    "render_worklist",
]
