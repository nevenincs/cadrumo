"""Developer CLI for Terminology Handbook scaffolding and audits.

A dev / maintenance module CLI invoked as ``python -m aeat.terminology``,
mirroring the ``aeat.locales`` and ``dev.docs.apidocs`` precedents. It is
NOT part of the operator ``aeat config`` / ``aeat app`` surface, so it
does not bear on the two-CLI-roots architecture rule; like ``apidocs`` it
emits plain English maintenance output rather than localised strings.

This step (W02.P05.S11) ships the ``scaffold`` verb and its three-outcome
engine. The ``--check`` drift gate, the ``set`` / ``relate`` / ``retire``
curation verbs, and the ``audit`` health report are the sibling step's
work; ``scaffold`` already exposes the structured
:class:`~aeat.terminology._scaffold.ScaffoldPlan` those surfaces consume.
"""

from __future__ import annotations

import typer

from ._scaffold import ScaffoldAction, ScaffoldPlan, scaffold_handbook

app = typer.Typer(name="terminology", help="Terminology Handbook maintenance.", no_args_is_help=True)


@app.command("scaffold")
def scaffold() -> None:
    """Reconcile the Handbook against live enrolment sources (msgmerge contract)."""
    plan = scaffold_handbook(apply=True)
    _report_plan(plan)


def _report_plan(plan: ScaffoldPlan) -> None:
    counts = plan.counts
    typer.echo(
        "scaffold: "
        f"{counts[ScaffoldAction.PRESERVE]} preserved, "
        f"{counts[ScaffoldAction.SCAFFOLD_EMPTY]} new drafts, "
        f"{counts[ScaffoldAction.RETIRE]} retired, "
        f"{counts[ScaffoldAction.UNCHANGED]} unchanged"
    )
    for entry in plan.by_action(ScaffoldAction.SCAFFOLD_EMPTY):
        typer.echo(f"  + {entry.concept_id} (draft)")
    for entry in plan.by_action(ScaffoldAction.RETIRE):
        suffix = " (needs replaced_by)" if entry.needs_replaced_by else ""
        typer.echo(f"  ~ {entry.concept_id} (retired){suffix}")


__all__ = ["app"]
