"""Developer CLI for Terminology Handbook scaffolding, curation, and audits.

A dev / maintenance module CLI invoked as ``python -m aeat.terminology``,
mirroring the ``aeat.locales`` and ``dev.docs.apidocs`` precedents. It is
NOT part of the operator ``aeat config`` / ``aeat app`` surface, so it
does not bear on the two-CLI-roots architecture rule; like ``apidocs`` it
emits plain English maintenance output rather than localised strings.

Verbs:

* ``scaffold`` -- reconcile the Handbook against live enrolment sources
  under the msgmerge three-outcome contract; ``--check`` is the
  non-mutating drift gate (dry-run over the same plan).
* ``set`` -- set a curated language field or term on a concept.
* ``relate`` -- add / remove a ``broader`` / ``related`` edge.
* ``retire`` -- tombstone a concept with a required successor.
* ``audit`` -- print the structured curation-health report.

Every curation verb writes through the strict schema and re-validates the
whole tree before committing; an invalid mutation is refused, never
written.
"""

from __future__ import annotations

from typing import Annotated

import typer

from ..core.external_constants import OutputLanguage
from ._curation import (
    CurationError,
    audit_handbook,
    relate_concepts,
    retire_concept,
    set_language_field,
    set_term,
)
from ._enums import TermStatus
from ._scaffold import ScaffoldAction, ScaffoldPlan, scaffold_handbook

app = typer.Typer(name="terminology", help="Terminology Handbook maintenance.", no_args_is_help=True)


@app.command("scaffold")
def scaffold(
    check: Annotated[
        bool,
        typer.Option("--check", help="Report drift without writing; exit non-zero on drift."),
    ] = False,
) -> None:
    """Reconcile the Handbook against live enrolment sources (msgmerge contract)."""
    plan = scaffold_handbook(apply=not check)
    _report_plan(plan)
    if check and not plan.is_empty:
        raise typer.Exit(code=1)


@app.command("set")
def set_field(
    concept_id: Annotated[str, typer.Argument(help="Concept id to curate.")],
    language: Annotated[OutputLanguage, typer.Argument(help="Language section code.")],
    field_name: Annotated[
        str,
        typer.Argument(help="short_description | definition | scope_note | source | term."),
    ],
    value: Annotated[str, typer.Argument(help="Field value (citation for 'source'; label for 'term').")],
    term_status: Annotated[
        TermStatus | None,
        typer.Option("--term-status", help="Term status when field is 'term'."),
    ] = None,
    authority: Annotated[
        str | None,
        typer.Option("--authority", help="Source authority when field is 'source'."),
    ] = None,
) -> None:
    """Set a curated language field or term on a concept."""
    try:
        if field_name == "term":
            status = term_status if term_status is not None else TermStatus.ADMITTED
            path = set_term(concept_id, language, value, status)
        else:
            path = set_language_field(concept_id, language, field_name, value, source_authority=authority)
    except CurationError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"set {field_name} on {concept_id} [{language.value}] -> {path.name}")


@app.command("relate")
def relate(
    concept_id: Annotated[str, typer.Argument(help="Concept id to relate from.")],
    relation: Annotated[str, typer.Argument(help="broader | related.")],
    target_id: Annotated[str, typer.Argument(help="Target concept id.")],
    remove: Annotated[bool, typer.Option("--remove", help="Remove the edge instead of adding it.")] = False,
) -> None:
    """Add or remove a broader / related edge between two concepts."""
    try:
        path = relate_concepts(concept_id, relation, target_id, remove=remove)
    except CurationError as exc:
        raise typer.BadParameter(str(exc)) from exc
    verb = "unrelated" if remove else "related"
    typer.echo(f"{verb} {concept_id} {relation} {target_id} -> {path.name}")


@app.command("retire")
def retire(
    concept_id: Annotated[str, typer.Argument(help="Concept id to retire.")],
    replaced_by: Annotated[str, typer.Argument(help="Successor concept id (required).")],
) -> None:
    """Tombstone a concept with a required successor (never deletes)."""
    try:
        path = retire_concept(concept_id, replaced_by)
    except CurationError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"retired {concept_id} -> replaced_by {replaced_by} ({path.name})")


@app.command("audit")
def audit() -> None:
    """Print the structured curation-health report."""
    report = audit_handbook()
    typer.echo(
        "audit: "
        f"{report.total_concepts} concepts "
        f"({report.draft_count} draft, {report.approved_count} approved, "
        f"{report.deprecated_count} deprecated, {report.retired_count} retired)"
    )
    typer.echo(f"  seed provenance: {report.seeded_count} seeded, {report.hand_authored_count} hand-authored")
    if report.empty_short_description:
        typer.echo(f"  empty short_description: {len(report.empty_short_description)} concept(s)")
        for concept_id, langs in sorted(report.empty_short_description.items()):
            typer.echo(f"    - {concept_id}: {', '.join(langs)}")
    if report.dangling_relations:
        typer.echo(f"  dangling relations: {len(report.dangling_relations)} concept(s)")
        for concept_id, targets in sorted(report.dangling_relations.items()):
            typer.echo(f"    - {concept_id} -> {', '.join(targets)}")
    if report.retired_without_replaced_by:
        typer.echo(f"  retired without replaced_by: {', '.join(report.retired_without_replaced_by)}")
    if not report.is_clean:
        raise typer.Exit(code=1)


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
