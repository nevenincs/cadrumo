"""Developer CLI: write the canonical held-out miss-rate report.

Mirrors the ``sweep`` / ``coverage`` developer-CLI pattern. The close-review
of the docs-terminology-search next wave (2026-07-13 audit, NIT-2) found the
committed miss-rate report artifacts were produced ad hoc; this module is the
committed, reproducible writer, so a report regenerates byte-comparably from
the committed mapping and held-out corpus alone.

Usage::

    python -m dev.docs.terminology.miss_rate report --output PATH --note TEXT

The threshold is the ratified ADR D3 default; overriding it is a deliberate
act that must cite a superseding decision.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Final

import typer

from ._miss_rate import (
    DEFAULT_RUNG2_MISS_RATE_THRESHOLD,
    adjudicate_rung2,
    evaluate_held_out_miss_rate,
)

_UTF_8: Final[str] = "utf-8"

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def _root() -> None:
    """Held-out miss-rate reporting for the compiled relevance mapping."""


def write_miss_rate_report(
    output: Path,
    *,
    note: str,
    threshold: float = DEFAULT_RUNG2_MISS_RATE_THRESHOLD,
) -> None:
    """Evaluate, adjudicate, and write the canonical report JSON."""
    evaluation = evaluate_held_out_miss_rate()
    adjudication = adjudicate_rung2(evaluation, miss_rate_threshold=threshold)
    payload = {
        "note": note,
        "evaluation": json.loads(evaluation.model_dump_json()),
        "rung2": json.loads(adjudication.model_dump_json()),
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
    threshold: Annotated[
        float,
        typer.Option("--threshold", help="Rung-2 materiality threshold (ADR D3 default)."),
    ] = DEFAULT_RUNG2_MISS_RATE_THRESHOLD,
) -> None:
    """Write the miss-rate report and print the adjudicated decision."""
    write_miss_rate_report(output, note=note, threshold=threshold)
    evaluation = evaluate_held_out_miss_rate()
    adjudication = adjudicate_rung2(evaluation, miss_rate_threshold=threshold)
    typer.echo(
        f"cases {evaluation.case_count}  hits {evaluation.hit_count}  "
        f"miss-rate {evaluation.miss_rate:.4f}  threshold {threshold}  "
        f"decision {adjudication.decision.value}"
    )
    typer.echo(f"wrote miss-rate report -> {output}")


if __name__ == "__main__":
    app()
