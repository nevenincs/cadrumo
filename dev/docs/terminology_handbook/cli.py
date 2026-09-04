"""Developer CLI for Terminology Handbook scaffolding, curation, and audits.

A dev / maintenance module CLI invoked as ``python -m dev.docs.terminology_handbook``,
mirroring the ``dev.locales`` and ``dev.docs.apidocs`` precedents. It is
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

import json
from pathlib import Path
from typing import Annotated

import typer

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n import tr

from ._curation import (
    CurationError,
    audit_handbook,
    relate_concepts,
    remove_term,
    retire_concept,
    set_language_field,
    set_term,
)
from ._scaffold import ScaffoldAction, ScaffoldPlan, scaffold_handbook
from ._seed_import import (
    SeedEntry,
    SeedSource,
    apply_seed_entries,
    parse_iate_tbx,
    parse_ubterm_csv,
)
from .enums import TermStatus
from .errors import TerminologyError

#: The curation baseline recorded beside this package. Named here because
#: nothing referenced the file at all, which is how it stayed inert.
_CURATION_BASELINE_NAME = "curation-ratchet.json"
_BASELINE_ENCODING = "utf-8"

app = typer.Typer(name="terminology", help=tr("Terminology Handbook maintenance."), no_args_is_help=True)


@app.command("scaffold")
def scaffold(
    check: Annotated[
        bool,
        typer.Option("--check", help=tr("Report drift without writing; exit non-zero on drift.")),
    ] = False,
) -> None:
    """Reconcile the Handbook against live enrolment sources (msgmerge contract)."""
    plan = scaffold_handbook(apply=not check)
    _report_plan(plan)
    if check and not plan.is_empty:
        raise typer.Exit(code=1)


@app.command("set")
def set_field(
    concept_id: Annotated[str, typer.Argument(help=tr("Concept id to curate."))],
    language: Annotated[OutputLanguage, typer.Argument(help=tr("Language section code."))],
    field_name: Annotated[
        str,
        typer.Argument(help=tr("short_description | definition | scope_note | source | term.")),
    ],
    value: Annotated[str, typer.Argument(help=tr("Field value (citation for 'source'; label for 'term')."))],
    term_status: Annotated[
        TermStatus | None,
        typer.Option("--term-status", help=tr("Term status when field is 'term'.")),
    ] = None,
    authority: Annotated[
        str | None,
        typer.Option("--authority", help=tr("Source authority when field is 'source'.")),
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
    concept_id: Annotated[str, typer.Argument(help=tr("Concept id to relate from."))],
    relation: Annotated[str, typer.Argument(help=tr("broader | related."))],
    target_id: Annotated[str, typer.Argument(help=tr("Target concept id."))],
    remove: Annotated[bool, typer.Option("--remove", help=tr("Remove the edge instead of adding it."))] = False,
) -> None:
    """Add or remove a broader / related edge between two concepts."""
    try:
        path = relate_concepts(concept_id, relation, target_id, remove=remove)
    except CurationError as exc:
        raise typer.BadParameter(str(exc)) from exc
    verb = "unrelated" if remove else "related"
    typer.echo(f"{verb} {concept_id} {relation} {target_id} -> {path.name}")


@app.command("remove-term")
def remove_term_cmd(
    concept_id: Annotated[str, typer.Argument(help=tr("Concept id to curate."))],
    language: Annotated[OutputLanguage, typer.Argument(help=tr("Language section code."))],
    label: Annotated[str, typer.Argument(help=tr("Exact term label to remove."))],
) -> None:
    """Remove a term by its exact label from a concept's language section."""
    try:
        path = remove_term(concept_id, language, label)
    except CurationError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"removed term {label!r} from {concept_id} [{language.value}] -> {path.name}")


@app.command("retire")
def retire(
    concept_id: Annotated[str, typer.Argument(help=tr("Concept id to retire."))],
    replaced_by: Annotated[str, typer.Argument(help=tr("Successor concept id (required)."))],
) -> None:
    """Tombstone a concept with a required successor (never deletes)."""
    try:
        path = retire_concept(concept_id, replaced_by)
    except CurationError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"retired {concept_id} -> replaced_by {replaced_by} ({path.name})")


def _recorded_curation_baseline() -> dict[str, object]:
    """Return the recorded curation baseline, or an empty mapping when absent.

    The file records a draft count, an empty-short-description count, a date
    and a review cadence, and NOTHING loaded it: no module, no recipe, no
    other declaration named it. It read as governance while being inert, and
    it had already been passed - 99 and 100 recorded, 101 and 102 live - with
    nothing to notice.

    It is reported rather than enforced. The recorded numbers are a frozen
    corpus count, which this project's quality rule disfavours as proof of
    anything; what they can honestly do is show a reader how far the tree has
    moved since someone last reviewed it.
    """
    path = Path(__file__).with_name(_CURATION_BASELINE_NAME)
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding=_BASELINE_ENCODING))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        typer.echo(f"  recorded baseline at {path.name} could not be read: {error}")
        return {}
    return loaded if isinstance(loaded, dict) else {}


@app.command("audit")
def audit() -> None:
    """Print the structured curation-health report."""
    report = audit_handbook()
    typer.echo(
        "audit: "
        f"{report.total_concepts} concepts "
        f"({report.draft_count} draft, {report.approved_count} approved, "
        f"{report.deprecated_count} deprecated, {report.retired_count} retired)",
    )
    typer.echo(f"  seed provenance: {report.seeded_count} seeded, {report.hand_authored_count} hand-authored")
    baseline = _recorded_curation_baseline()
    if baseline:
        typer.echo(
            f"  recorded {baseline.get('recorded_at', 'an unknown date')}: "
            f"{baseline.get('draft_count', '?')} draft, "
            f"{baseline.get('empty_short_description_count', '?')} empty short_description "
            f"(live: {report.draft_count} and {len(report.empty_short_description)})"
        )
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


@app.command("seed")
def seed(
    source: Annotated[SeedSource, typer.Argument(help=tr("Tier-A source: iate | ubterm (eurovoc once verified)."))],
    export_path: Annotated[Path, typer.Argument(help=tr("Path to the downloaded source export file."))],
    min_reliability: Annotated[
        int,
        typer.Option("--min-reliability", help=tr("IATE: minimum reliability code to keep (>= 3).")),
    ] = 3,
    domain: Annotated[
        list[str] | None,
        typer.Option("--domain", help=tr("IATE: subject-field allow-set (repeatable).")),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=tr("Report what would be seeded without writing.")),
    ] = False,
) -> None:
    """Import a Tier-A external seed export, stamping provenance on every value.

    Parses the downloaded source file into typed seed entries, maps each onto
    an existing concept by its Spanish preferred label, and adds the
    missing-language translations / aliases while stamping the licence-required
    attribution. An excluded (ND / NC / unlicensed) source is refused; a seed
    never overwrites curated prose and never auto-approves a draft.
    """
    try:
        if source is SeedSource.IATE:
            domains = frozenset(domain) if domain else None
            entries: tuple[SeedEntry, ...] = parse_iate_tbx(
                export_path,
                min_reliability=min_reliability,
                domains=domains,
            )
        elif source is SeedSource.UBTERM:
            entries = parse_ubterm_csv(export_path)
        else:
            # EuroVoc and the excluded sources are refused by the licence gate
            # the moment apply attempts an attribution lookup; surface it early
            # with the gate's reason rather than a half-parse.
            from ._seed_import import assert_source_ingestible

            assert_source_ingestible(source)
            raise typer.BadParameter(f"no parser wired for source {source.value!r}")
        result = apply_seed_entries(entries, today=None, write=not dry_run)
    except TerminologyError as exc:
        raise typer.BadParameter(str(exc)) from exc

    mode = "would seed" if dry_run else "seeded"
    typer.echo(
        f"{mode} from {source.value}: {result.applied_count} concept(s) matched, "
        f"{len(result.unmatched_keys)} unmatched key(s), "
        f"{result.languages_added} language(s) + {result.aliases_added} alias(es) added",
    )
    for key in result.unmatched_keys:
        typer.echo(f"  ? unmatched: {key}")


def _report_plan(plan: ScaffoldPlan) -> None:
    counts = plan.counts
    typer.echo(
        "scaffold: "
        f"{counts[ScaffoldAction.PRESERVE]} preserved, "
        f"{counts[ScaffoldAction.SCAFFOLD_EMPTY]} new drafts, "
        f"{counts[ScaffoldAction.RETIRE]} retired, "
        f"{counts[ScaffoldAction.UNCHANGED]} unchanged",
    )
    for entry in plan.by_action(ScaffoldAction.SCAFFOLD_EMPTY):
        typer.echo(f"  + {entry.concept_id} (draft)")
    for entry in plan.by_action(ScaffoldAction.RETIRE):
        suffix = " (needs replaced_by)" if entry.needs_replaced_by else ""
        typer.echo(f"  ~ {entry.concept_id} (retired){suffix}")


__all__ = ["app"]
