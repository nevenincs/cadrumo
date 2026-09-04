"""Developer CLI for the Modelo 100 anexo-A AEIP continuity family."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..._paths import REPO_ROOT
from .adjudications import DEFAULT_ADJUDICATIONS_FILENAME, load_adjudications
from .manager import (
    AeipInventory,
    ChainPlan,
    build_inventory,
    extract_occurrences,
    plan_chains,
    render_evolution_record,
)

app = typer.Typer(
    name="aeip",
    help="Inventory and plan the Modelo 100 anexo-A AEIP event-keyed continuity chains.",
    no_args_is_help=True,
)


def _repo_root() -> Path:
    return REPO_ROOT


def _modelos_root() -> Path:
    return _repo_root() / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"


def _load(modelo_id: str, adjudications_path: Path | None) -> tuple[AeipInventory, ChainPlan]:
    path = adjudications_path or Path(__file__).resolve().parent / DEFAULT_ADJUDICATIONS_FILENAME
    adjudications = load_adjudications(path)
    occurrences, category_counts = extract_occurrences(_modelos_root(), modelo_id=modelo_id)
    inventory = build_inventory(
        occurrences,
        adjudications=adjudications,
        category_row_counts=category_counts,
    )
    return inventory, plan_chains(inventory, adjudications=adjudications)


_MODELO_OPTION = typer.Option("--modelo", help="AEAT modelo identifier carrying the anexo-A family.")
_ADJUDICATIONS_OPTION = typer.Option(
    "--adjudications",
    help="Path to the adjudications file; defaults to the one shipped beside this CLI.",
)


def casilla_claims(
    inventory: AeipInventory,
) -> tuple[dict[tuple[str, str], set[str]], dict[str, set[str]]]:
    """Return which programmes claim each casilla, per revision and pooled.

    Two different questions were being answered by one number. Pooling every
    revision under a bare casilla id counts a programme that INHERITED an id
    in a later year as colliding with the programme that held it earlier,
    which is ordinary AEAT reassignment and not an identity defect.

    The finding that matters is two programmes claiming one casilla WITHIN a
    single revision, because only there is the id ambiguous. Measured on the
    live modelo 100 family, the pooled number reported thirty and the
    same-revision number was zero - so every reported collision was expected
    behaviour, and a real one appearing would have moved thirty to thirty-one
    with nothing to distinguish it.
    """
    within_revision: dict[tuple[str, str], set[str]] = {}
    pooled: dict[str, set[str]] = {}
    for event in inventory.events:
        for occurrence in event.occurrences:
            within_revision.setdefault((occurrence.revision_id, occurrence.casilla_id), set()).add(event.slug)
            pooled.setdefault(occurrence.casilla_id, set()).add(event.slug)
    return within_revision, pooled


@app.command("inventory")
def inventory_command(
    modelo: Annotated[str, _MODELO_OPTION] = "100",
    adjudications: Annotated[Path | None, _ADJUDICATIONS_OPTION] = None,
) -> None:
    """Report the event matrix: programmes, spans, and id-reuse collisions."""
    inventory, _ = _load(modelo, adjudications)
    multi = [event for event in inventory.events if event.spans_multiple_revisions]

    typer.echo(f"Modelo {modelo} anexo-A AEIP family across revisions {', '.join(inventory.revisions)}")
    typer.echo(f"  event-row occurrences : {len(inventory.occurrences)}")
    typer.echo(f"  distinct programmes   : {len(inventory.events)}")
    typer.echo(f"    spanning >1 revision: {len(multi)}")
    typer.echo(f"    single-revision     : {len(inventory.events) - len(multi)}")
    for revision in inventory.revisions:
        events = sum(1 for event in inventory.events for occ in event.occurrences if occ.revision_id == revision)
        categories = inventory.category_row_counts.get(revision, 0)
        typer.echo(f"  {revision}: {events:>3} event rows, {categories:>3} category rows")

    within_revision, pooled = casilla_claims(inventory)
    collisions = sorted(key for key, slugs in within_revision.items() if len(slugs) > 1)
    reassigned = sorted(casilla for casilla, slugs in pooled.items() if len(slugs) > 1)
    typer.echo(f"  distinct casilla ids  : {len(pooled)}")
    typer.echo(f"    same-revision collisions   : {len(collisions)}")
    for revision, casilla in collisions:
        claimants = ", ".join(sorted(within_revision[(revision, casilla)]))
        typer.echo(f"      {revision}:{casilla} claimed by {claimants}")
    typer.echo(f"    reassigned across revisions: {len(reassigned)} (expected; not a collision)")


@app.command("check")
def check_command(
    modelo: Annotated[str, _MODELO_OPTION] = "100",
    adjudications: Annotated[Path | None, _ADJUDICATIONS_OPTION] = None,
) -> None:
    """Report every unadjudicated ambiguity; exit non-zero while any remain."""
    _, plan = _load(modelo, adjudications)
    if plan.complete:
        typer.echo(f"AEIP family fully adjudicated: {len(plan.entries)} chains planned.")
        return
    typer.echo(f"{len(plan.ambiguities)} unadjudicated ambiguit(y/ies):")
    for ambiguity in plan.ambiguities:
        typer.echo(f"  [{ambiguity.kind}] {', '.join(ambiguity.slugs)}")
        typer.echo(f"      {ambiguity.detail}")
    raise typer.Exit(code=1)


@app.command("plan")
def plan_command(
    modelo: Annotated[str, _MODELO_OPTION] = "100",
    adjudications: Annotated[Path | None, _ADJUDICATIONS_OPTION] = None,
    show_records: Annotated[
        bool,
        typer.Option("--show-records", help="Print the evolution-record fragments for review."),
    ] = False,
) -> None:
    """Plan the chain stamps and evolution records. Writes nothing."""
    _, plan = _load(modelo, adjudications)
    typer.echo(f"planned chains        : {len(plan.entries)}")
    typer.echo(f"occurrences to stamp  : {plan.stamp_count}")
    typer.echo(f"evolution records     : {plan.record_count}")
    typer.echo(f"single-revision events: {len(plan.single_revision_events)} (no chain)")
    typer.echo(f"blocked by ambiguity  : {len(plan.ambiguities)}")
    for entry in plan.entries:
        stamps = ", ".join(f"{occ.revision_id}:{occ.casilla_id}" for occ in entry.occurrences)
        typer.echo(f"\n  {entry.chain_id}")
        typer.echo(f"    {entry.title}")
        typer.echo(f"    stamp: {stamps}")
        for pair in entry.pairs:
            typer.echo(f"    pair : {pair.from_revision} -> {pair.to_revision} [{pair.evolution_kind}]")
            if show_records:
                record = render_evolution_record(pair, casilla_id=entry.occurrences[-1].casilla_id)
                typer.echo("".join(f"\n      {line}" for line in record.splitlines()))
