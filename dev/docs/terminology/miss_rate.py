"""Developer CLI: write the canonical held-out miss-rate report.

Mirrors the ``sweep`` / ``coverage`` developer-CLI pattern. A close review of
the docs-terminology-search next wave found the committed miss-rate report
artifacts were produced ad hoc; this module is the committed, reproducible
writer, so a report regenerates byte-comparably from the committed mapping
and held-out corpus alone.

Usage::

    python -m dev.docs.terminology.miss_rate report --output PATH --note TEXT

The threshold is a fixed default and cannot be supplied by a caller; changing
it means changing this source contract, not passing a flag.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Final

import typer

from ..._paths import UTF_8
from ._miss_rate import evaluate_held_out_miss_rate

_UTF_8: Final[str] = UTF_8

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def _root() -> None:  # pyright: ignore[reportUnusedFunction]  # Typer registers the callback through its decorator.
    """Held-out miss-rate reporting for the compiled relevance mapping."""


def write_miss_rate_report(
    output: Path,
    *,
    note: str,
) -> None:
    """Evaluate the held-out miss rate and write the canonical report JSON."""
    evaluation = evaluate_held_out_miss_rate()
    payload = {
        "note": note,
        "evaluation": json.loads(evaluation.model_dump_json()),
    }
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )


@app.command()
def report(
    output: Annotated[Path, typer.Option("--output", help="Report JSON path.")],
    note: Annotated[str, typer.Option("--note", help="One-line report provenance note.")],
) -> None:
    """Write the miss-rate report and print the measured result."""
    write_miss_rate_report(output, note=note)
    evaluation = evaluate_held_out_miss_rate()
    typer.echo(f"cases {evaluation.case_count}  hits {evaluation.hit_count}  miss-rate {evaluation.miss_rate:.4f}")
    typer.echo(f"wrote miss-rate report -> {output}")


if __name__ == "__main__":
    app()
