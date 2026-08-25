"""Cadence re-run CLI for the query-vocabulary RAG sweep.

A dev / maintenance CLI, ``python -m dev.docs.terminology.sweep``, mirroring the
``apidocs`` / ``preprocess`` precedents. It regenerates the term-to-target
relevance mapping by running the sweep against the resident RAG service; its
output is reviewed like any generated-but-committed surface (the registry
authoring-compiler pattern). The sweep re-runs on cadence -- a registry or docs
structure change -- and its diff is read on every refresh.

Scope: this verb RUNS the sweep and prints / writes the laundered mapping. A
separate committed step lands the relevance data file and adds the drift /
laundering / licence gates; this verb's ``--out`` writes the JSON that step
consumes, so the seam is clean.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final

import typer

from ..._paths import UTF_8
from ._query_aliases import load_query_alias_authority
from ._sweep import (
    DEFAULT_MAX_RESULTS,
    ServiceRagSearchClient,
    SweepResult,
    run_sweep,
)
from ._wrangle import STRONG_SIGNAL_SCORE_FLOOR

_UTF_8: Final[str] = UTF_8

app = typer.Typer(
    name="sweep",
    help="Query-vocabulary RAG sweep: regenerate the term-to-target relevance mapping.",
    no_args_is_help=True,
)


@app.command("run")
def run(
    concept: Annotated[
        list[str] | None,
        typer.Option("--concept", help="Limit the sweep to these concept ids (repeatable)."),
    ] = None,
    alias_authority: Annotated[
        Path | None,
        typer.Option(
            "--alias-authority",
            help="Use this independently ratified query-alias authority JSON.",
        ),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write the laundered relevance mapping JSON to this path."),
    ] = None,
    max_results: Annotated[
        int,
        typer.Option("--max-results", help="Per-query RAG result ceiling."),
    ] = DEFAULT_MAX_RESULTS,
    score_floor: Annotated[
        float,
        typer.Option("--score-floor", help="Strong-signal relevance floor for wrangling."),
    ] = STRONG_SIGNAL_SCORE_FLOOR,
    port: Annotated[int, typer.Option("--port", help="Resident RAG service port.")] = 8766,
    timeout_s: Annotated[float, typer.Option("--timeout", help="Per-query RAG timeout (seconds).")] = 60.0,
    reindex: Annotated[
        bool,
        typer.Option("--reindex/--no-reindex", help="Run the mandated reindex-before-sweep first."),
    ] = True,
) -> None:
    """Run the sweep and print a summary (and optionally write the mapping JSON)."""
    client = ServiceRagSearchClient(port=port, timeout_s=timeout_s)
    result = run_sweep(
        client=client,
        concept_ids=concept,
        query_alias_authority=(load_query_alias_authority(alias_authority) if alias_authority is not None else None),
        max_results=max_results,
        score_floor=score_floor,
        port=port,
        reindex=reindex,
    )
    _report(result)
    if out is not None:
        out.write_text(result.model_dump_json(indent=2) + "\n", encoding=_UTF_8, newline="")
        typer.echo(f"wrote relevance mapping -> {out}")


def _report(result: SweepResult) -> None:
    mapped = sum(1 for mapping in result.mappings if mapping.targets)
    typer.echo(
        f"sweep: {result.query_count} queries over {result.concept_count} concept(s); "
        f"{mapped} with targets, {result.query_count - mapped} empty (below floor).",
    )
    typer.echo(f"  {result.reindex_note}")


__all__ = ["app"]
