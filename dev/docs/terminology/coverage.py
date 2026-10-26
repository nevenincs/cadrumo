"""Corpus coverage report CLI: ``python -m dev.docs.terminology.coverage``.

A dev / maintenance CLI mirroring the sibling ``sweep`` verb: a thin Typer app
that derives the corpus coverage of the committed relevance mapping and writes
the report as run output. ``report`` measures the widening backlog: every
derivable target (concept card, casilla, CLI surface, legal provision) with no
inbound entry in the committed mapping.

The MEASUREMENT is deterministic -- no timestamp, no machine path in the
payload -- so two runs over one tree produce byte-identical JSON and the sweep
cadence compares them directly. Its DESTINATION is not: the report is run
output, so it lands in a fresh ``.logs/audit-runs/`` run directory that the
next ``just clean-apply`` reclaims, and the command prints where it wrote.
Pass ``--output`` to place it somewhere a reviewer has chosen instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final

import typer

from dev._paths import UTF_8

from .coverage_report import TerminologyCoverageReport, compute_coverage_report, coverage_report_path

_UTF_8: Final[str] = UTF_8

app = typer.Typer(
    name="coverage",
    help="Corpus coverage report: measure the committed relevance mapping against the derivable target surface.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Corpus coverage report CLI."""


@app.command("report")
def report(
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write the coverage report JSON to this path."),
    ] = None,
) -> None:
    """Compute the coverage report, write it, and print a per-kind summary."""
    destination = output if output is not None else coverage_report_path()
    result = compute_coverage_report()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result.model_dump_json(indent=2) + "\n", encoding=_UTF_8, newline="")
    _print_summary(result)
    typer.echo(f"wrote coverage report -> {destination}")


def _print_summary(result: TerminologyCoverageReport) -> None:
    for entry in result.kinds:
        percentage = entry.coverage_fraction * 100.0
        typer.echo(
            f"  {entry.kind.value:<8} {entry.covered:>5}/{entry.total:<6} covered "
            f"({percentage:6.2f}%); {len(entry.uncovered_ids)} uncovered",
        )
    typer.echo(
        f"  referenced targets: {result.referenced_target_count}; "
        f"orphan mapping targets: {len(result.orphan_mapping_target_ids)}",
    )


if __name__ == "__main__":
    app()
