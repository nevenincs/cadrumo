"""Developer CLI for synonym-candidate mining and ratification validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Final

import typer

from ..._paths import UTF_8
from ..terminology_handbook.errors import TerminologyLoadError
from ._synonym_mining import (
    RatificationStatus,
    SynonymCandidateObservation,
    carry_forward_review_state,
    load_synonym_ratification_queue,
    mine_synonym_candidates,
    reviewed_decisions_dropped,
    synonym_ratification_queue_path,
    validate_ratification_queue,
)

_DEFAULT_QUEUE_PATH = synonym_ratification_queue_path()
_UTF_8: Final[str] = UTF_8

app = typer.Typer(
    name="synonyms",
    help="Mine and validate Terminology Handbook synonym ratification queues.",
    no_args_is_help=True,
)


@app.command("validate")
def validate(
    queue: Annotated[
        Path | None,
        typer.Option("--queue", help="Queue JSON to validate; defaults to the bundled ratification queue."),
    ] = None,
) -> None:
    """Validate that ratified candidates landed and unratified ones do not ship."""
    try:
        loaded = load_synonym_ratification_queue(queue)
    except TerminologyLoadError as exc:
        raise typer.BadParameter(str(exc)) from exc
    result = validate_ratification_queue(loaded)
    if result.passed:
        typer.echo(f"synonyms: clean ({len(loaded.entries)} candidate(s))")
        return
    typer.echo(f"synonyms: {len(result.violations)} violation(s)")
    for violation in result.violations:
        typer.echo(f"  - {violation.concept_id}:{violation.candidate}: {violation.reason}")
    raise typer.Exit(code=1)


@app.command("mine")
def mine(
    observations: Annotated[
        Path,
        typer.Argument(help="JSON file containing a list of raw synonym candidate observations."),
    ],
    out: Annotated[
        Path,
        typer.Option("--out", help="Output queue JSON path."),
    ] = _DEFAULT_QUEUE_PATH,
    drop_reviewed: Annotated[
        bool,
        typer.Option(
            "--drop-reviewed",
            help="Retire the reviewed decisions this mine would discard. Destructive; refused by default.",
        ),
    ] = False,
) -> None:
    """Filter raw embedding observations into a proposed ratification queue.

    ``--out`` defaults to the committed queue, whose ``status``, ``review_reason``
    and ``reviewed_at`` fields are hand-authored and which no mine reproduces: the
    miner stamps every row proposed and skips candidates already in the shipped
    query vocabulary, which is every ratified one. Surviving decisions are carried
    forward; a mine that would still discard one is refused whole, before any byte
    is written.
    """
    try:
        payload = json.loads(observations.read_text(encoding=_UTF_8))
        rows = tuple(SynonymCandidateObservation.model_validate(row) for row in payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise typer.BadParameter(f"{observations}: cannot load observations: {exc}") from exc
    queue = mine_synonym_candidates(rows)
    carried = 0
    if out.is_file():
        try:
            prior = load_synonym_ratification_queue(out)
        except TerminologyLoadError as exc:
            raise typer.BadParameter(
                f"{out}: the existing queue cannot be read, so its decisions cannot be protected: {exc}",
            ) from exc
        queue = carry_forward_review_state(queue, prior)
        carried = sum(1 for entry in queue.entries if entry.status is not RatificationStatus.PROPOSED)
        dropped = reviewed_decisions_dropped(queue, prior)
        if dropped and not drop_reviewed:
            typer.echo(f"synonyms: refusing to write {out}")
            typer.echo(f"  {len(dropped)} reviewed decision(s) would be written off, and no mine restores them:")
            for entry in dropped:
                typer.echo(
                    f"    - {entry.concept_id}:{entry.candidate} ({entry.action.value}, {entry.language.value}) "
                    f"{entry.status.value} on {entry.reviewed_at}: {entry.review_reason}",
                )
            typer.echo("  Write to a different --out, or pass --drop-reviewed to retire them deliberately.")
            raise typer.Exit(code=1)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(queue.model_dump_json(indent=2) + "\n", encoding=_UTF_8, newline="")
    typer.echo(f"synonyms: wrote {len(queue.entries)} candidate(s), {carried} reviewed carried forward -> {out}")


__all__ = ["app"]
