"""Developer CLI for modelo registry conformance governance.

A dev / maintenance module CLI invoked as ``python -m dev.registry.conformance``,
mirroring the ``dev.registry.newmodelo``, ``dev.locales`` and
``dev.docs.terminology_handbook`` precedents. It is NOT part of the operator
``aeat config`` / ``aeat app`` surface, so it does not bear on the
two-CLI-roots architecture rule; like ``apidocs`` it emits plain English
maintenance output rather than localised strings.

Verbs:

* ``report`` -- every conformance axis, one row per modelo revision.
* ``coverage`` -- per-axis measured counts against their real populations.
* ``audit [--check]`` -- the shrink-only ratchet against the committed
  baseline.
* ``closure [--check]`` -- the derived temporal, source, and filing release
  predicate. ``--check`` blocks a shipped-completeness claim while any limb is
  refused or the three denominators disagree.
* ``stamp`` -- write a revision's DECLARED governance provenance. It cannot
  write ``operator_reviewed``: this CLI is agent-driven, and an agent recording
  an operator's signoff is the exact dishonesty the feature exists to detect.
  The schema still accepts the value, so the operator signs off by editing
  ``revision.toml`` directly.

``report`` and ``coverage`` ALWAYS exit 0, deliberately. The picture they render
is currently a bad one — ninety unreviewed revisions, five dead schema axes, an
independent-check coverage under five per cent — and a screen that refused to
render would leave that backlog unread while teaching every peer to route
around the tool. ``audit --check`` protects the monotonic conformance ratchet
without demanding that the current backlog be clean; ``closure --check``
instead gates the separate, explicit completeness claim and therefore blocks
while any release limb remains refused.

Reading the output
------------------

``n/a`` means NOT MEASURED or NO CLAIM MADE. It is never a zero, and the two
must not be conflated: a revision that reconciles nothing makes no
independent-check claim, while a revision that reconciles two hundred and
checks none of them makes one and fails it. ``-`` is a real empty list.

Every independent-check figure is COVERAGE OF INDEPENDENT CHECKING, never
correctness. ``0.0460`` does NOT mean 4.6% of the registry is right; it means
4.6% of what the registry reconciles is cross-checked against a figure AEAT
published rather than one this application computed. The remaining 95.4% is
the engine agreeing with itself, which is a statement about evidence, not about
arithmetic.

``--no-validate`` selects the degraded read, which survives a
concurrently-edited registry the validating authority would refuse outright.
Every row is then stamped ``registry_validated=false`` and the three axes
needing that authority — evidence-tier coverage, the support probe, and the
derived authorization — report ``n/a`` rather than a fabricated zero.

See Also:
    :mod:`~dev.registry.conformance.manager`
        Pure folds and renderers behind every verb here.
    :func:`~application.registry.audit_bundled_registry_conformance`
        Shipped composer the manager reads.
    :mod:`~entrypoints.cli._modelo_discovery_cli`
        Operator-facing support-matrix command over the same shipped capability
        authority ``report`` probes per revision.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer

from ._stamp import StampableReviewStatus, StampError, bundled_registry_root, stamp_revision
from .authorities import canonical_live_registry_closure_authorities
from .closure import (
    RegistryClosureReport,
    check_registry_closure_release,
    load_registry_closure_report,
    render_registry_closure_report,
)
from .manager import (
    ConformanceReport,
    build_coverage_report,
    check_conformance_ratchet,
    load_baseline,
    load_conformance_report,
    record_baseline,
    render_audit,
    render_coverage,
    render_report,
    vacuity_warning,
)

app = typer.Typer(
    name="conformance",
    help="Report modelo registry conformance: provenance, grounding, coherence, enforcement.",
    no_args_is_help=True,
)

_NoValidate = Annotated[
    bool,
    typer.Option(
        "--no-validate",
        help=(
            "Degraded read: use the non-validating tree loader, which survives a registry a peer "
            "is mid-edit. Every row is stamped registry_validated=false and the axes needing the "
            "validating authority report n/a, never zero."
        ),
    ),
]

_AsJson = Annotated[
    bool,
    typer.Option("--json", help="Emit the strict payload as JSON instead of greppable key=value rows."),
]


@app.command("report")
def report(as_json: _AsJson = False, no_validate: _NoValidate = False) -> None:
    """Print every conformance axis, one row per modelo revision.

    Composes the shipped conformance profile — declared governance provenance,
    this revision's own capabilities, evidence-tier coverage, the modelo-level
    support probe and authorization, external-oracle grounding, classification
    coherence, registry-scope diagnostics — and adds schema-local translation
    coverage. Always exits 0: this is a screen, not a gate.
    """
    composed = load_conformance_report(validate=not no_validate)
    if as_json:
        typer.echo(composed.model_dump_json(indent=2))
        _warn_if_vacuous(composed)
        return
    typer.echo(render_report(composed))
    _warn_if_vacuous(composed)


@app.command("coverage")
def coverage(as_json: _AsJson = False, no_validate: _NoValidate = False) -> None:
    """Print each conformance axis's measured count against its real population.

    Population matters as much as the count: ``0 of 43`` is a dead schema
    surface while ``0 of 0`` says only that nothing could have declared it
    either way. Axes whose plain name would mislead carry a ``caveat`` field,
    which rides in the JSON payload as well as the text so a programmatic
    consumer cannot read the number without it. Always exits 0.
    """
    composed = load_conformance_report(validate=not no_validate)
    projected = build_coverage_report(composed)
    if as_json:
        typer.echo(projected.model_dump_json(indent=2))
        _warn_if_vacuous(composed)
        return
    typer.echo(render_coverage(projected))
    _warn_if_vacuous(composed)


@app.command("closure")
def closure(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help=(
                "Gate: exit 1 unless every law-selectable revision satisfies temporal coverage, "
                "source connectivity, and filing export with no join disagreement."
            ),
        ),
    ] = False,
    as_of: Annotated[
        str | None,
        typer.Option(
            "--as-of",
            help="Date used to evaluate expiring source-connectivity evidence; defaults to today.",
        ),
    ] = None,
    as_json: _AsJson = False,
    offline: Annotated[
        bool,
        typer.Option(
            "--offline",
            help="Evaluate without live source-connectivity or filing-export proof authorities.",
        ),
    ] = False,
) -> None:
    """Render the derived cross-authority release report and optional blocking gate.

    The default report derives temporal, source, and filing facts through the
    canonical live authorities. ``--offline`` is the explicit no-proof mode.
    Command context cannot replace either authority with pre-authorized claims.
    Neither mode treats absent proof as a pass: the affected limb remains an
    owned refusal, and ``--check`` blocks the release claim.
    """
    try:
        as_of_date = None if as_of is None else date.fromisoformat(as_of)
    except ValueError as error:
        raise typer.BadParameter("must be an ISO calendar date (YYYY-MM-DD)") from error
    if offline:
        report = load_registry_closure_report(as_of=as_of_date)
    else:
        repository_root = Path(__file__).resolve().parents[3]
        with canonical_live_registry_closure_authorities(repository_root) as authorities:
            report = load_registry_closure_report(
                as_of=as_of_date,
                registry_authority=authorities.registry,
                source_proof_authority=authorities.source_connectivity,
                filing_proof_authority=authorities.filing_export,
            )
    emit_registry_closure_command(report, check=check, as_json=as_json)


def emit_registry_closure_command(
    report: RegistryClosureReport,
    *,
    check: bool,
    as_json: bool,
) -> None:
    """Emit one already-composed report through the closure command contract."""
    result = check_registry_closure_release(report)
    if as_json:
        typer.echo(report.model_dump_json(indent=2))
    else:
        typer.echo(render_registry_closure_report(report))
    if check and not result.passed:
        raise typer.Exit(code=1)


@app.command("audit")
def audit(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help=(
                "Gate: exit 1 when a defect counter grew past its ceiling, a measurement population "
                "fell below its floor, or recorded provenance fell below its progress floor."
            ),
        ),
    ] = False,
    record: Annotated[
        bool,
        typer.Option("--record", help="Capture the current counters as the committed baseline. Requires --note."),
    ] = False,
    note: Annotated[
        str | None,
        typer.Option("--note", help="Why this baseline capture happened and under what tree conditions."),
    ] = None,
    baseline: Annotated[
        Path | None,
        typer.Option("--baseline", help="Read or write this baseline file instead of the committed one."),
    ] = None,
    accept_weakening: Annotated[
        bool,
        typer.Option(
            "--accept-weakening",
            help=(
                "Take a capture that raises a ceiling or lowers a floor. Refused without this, "
                "because a lowered floor lets a half-read tree pass the anti-vacuity check forever."
            ),
        ),
    ] = False,
    no_validate: _NoValidate = False,
) -> None:
    """Compare the current conformance counters against the committed baseline.

    Three directions are checked and reported separately, because they fail for
    different reasons and want different responses.

    A CEILING violation means a DEFECT count grew: a grounding finding, a
    classification incoherence, an unattributed oracle payload. A VACUITY FLOOR
    violation means a measurement population FELL — fewer revisions, casillas,
    oracle payloads, or locale leaves than the baseline proves the run must
    reach — so every clean counter beside it is vacuous and cannot be trusted,
    which is why it is reported first. A PROGRESS FLOOR violation means declared
    provenance or translation was LOST: a signoff erased, an authorship claim
    dropped, a translated leaf deleted. For the review axis that work is
    underivable by construction, so nothing in the tree can reconstruct it.

    Population growth is deliberately NOT gated. The review and translation
    counters used to be shrink-only ceilings pinned at the full population, so
    the ninety-first revision reddened all three at once and the only sanctioned
    way past the refusal was the flag that says a capture is deliberately
    suspicious. Counting the work DONE instead of the work OUTSTANDING separates
    the two terms: a new revision moves the population and leaves progress alone.

    Without ``--check`` this is a screen and exits 0 whatever it finds.

    ``--record`` is compared against the baseline already on disk in the same
    three directions and refuses a capture that weakens any of them unless
    ``--accept-weakening`` says so. The floor directions are why the guard
    exists: a raised ceiling shows up on the census and the next honest capture
    pulls it back, while a floor lowered by a capture taken over a half-landed
    tree is silent forever.
    """
    if check and record:
        raise SystemExit(
            "--check and --record are opposite operations: one refuses a moved counter, the other "
            "accepts it as the new ceiling. Run them separately so the acceptance is a visible act",
        )
    if no_validate and (check or record):
        raise SystemExit(
            "--no-validate cannot back a gate or a baseline capture: under the degraded read the "
            "evidence-tier coverage, support-probe, and authorization axes are never measured, so "
            "their counters would read clean while nothing checked them",
        )

    composed = load_conformance_report(validate=not no_validate)
    if record:
        if not note or not note.strip():
            raise SystemExit(
                "--record requires --note stating why the baseline moved and under what tree "
                "conditions it was captured; an unexplained re-record is indistinguishable from "
                "silencing a real regression",
            )
        written = record_baseline(
            composed,
            note=note.strip(),
            recorded_at=datetime.now(tz=UTC).date().isoformat(),
            path=baseline,
            accept_weakening=accept_weakening,
        )
        typer.echo(f"recorded baseline recorded_at={written.recorded_at} rows={composed.revision_count}")
        return

    result = check_conformance_ratchet(composed, load_baseline(baseline))
    typer.echo(render_audit(result))
    if check and not result.passed:
        raise typer.Exit(code=1)


@app.command("stamp")
def stamp(
    modelo: Annotated[str, typer.Argument(help="Modelo id to stamp, e.g. 130.")],
    revision: Annotated[str, typer.Argument(help="Revision id to stamp, e.g. 2019-y-siguientes.")],
    engineered_by: Annotated[
        str | None,
        typer.Option("--engineered-by", help="Who built this revision."),
    ] = None,
    clear_engineered_by: Annotated[
        bool,
        typer.Option("--clear-engineered-by", help="Drop the authorship claim so a wrong name is correctable."),
    ] = False,
    review_status: Annotated[
        StampableReviewStatus | None,
        typer.Option(
            "--review-status",
            help=(
                "How far the review has progressed. operator_reviewed is deliberately absent: this "
                "CLI is agent-driven and cannot record a human's signoff. Author it in revision.toml."
            ),
        ),
    ] = None,
    reviewed_by: Annotated[
        str | None,
        typer.Option("--reviewed-by", help="Who reviewed it. Required when advancing the status."),
    ] = None,
    reviewed_at: Annotated[
        datetime | None,
        typer.Option("--reviewed-at", formats=["%Y-%m-%d"], help="Date of review. Defaults to today."),
    ] = None,
    registry_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-root",
            help=(
                "Registry tree root to stamp. Required unless --bundled-registry names the shipped "
                "tree instead; there is no default, because the only value a default could have is "
                "the shipped registry."
            ),
        ),
    ] = None,
    bundled_registry: Annotated[
        bool,
        typer.Option(
            "--bundled-registry",
            help=(
                "Stamp the SHIPPED AEAT registry that ships in the wheel. The only door to it, and "
                "unmistakable by design: a forgotten flag can no longer send a write there."
            ),
        ),
    ] = False,
) -> None:
    """Write one modelo revision's declared governance provenance.

    Writes ONLY the four governance scalars, and ONLY into the revision's own
    ``revision.toml`` manifest: a stamp declared inside a per-section fragment
    once merged silently and won, so a revision could read unstamped while the
    compiled snapshot claimed a completed review. Advancing the status to
    ``agent_reviewed`` records a reviewer and a date. Returning it to
    ``pending_review`` drops the declared reviewer, because the schema refuses a
    reviewer attached to a review the status denies; but naming a reviewer while
    the status stays ``pending_review`` is REFUSED rather than dropped, so a
    caller is never told the write succeeded while their claim was discarded.

    The stamp is validated by the real revision schema before anything is
    written, and the whole modelo is re-loaded through the real loader
    afterwards; a manifest the loader would reject is restored to its previous
    bytes rather than left on disk.

    The target tree must be NAMED. Exactly one of ``--registry-root`` and
    ``--bundled-registry`` is required and there is no default, because the only
    value a default could have is the shipped registry — and it did have it. A
    caller one layer up that dropped the root sent this verb at the bundled
    Modelo 130 manifest and left a fabricated agent review in shipped data, and a
    second reviewer reported an unattributable stamp appearing in the tree the
    same session. Stamping the shipped registry stays legal, because declaring
    authorship and agent review over it is what the verb is for; it is simply no
    longer something that can happen because a flag was forgotten.

    ``--registry-root`` pointed at the bundled tree is refused for the same
    reason: two doors to shipped data, one of them not saying so, is the state
    this closes. The refusal names the flag that does say so.
    """
    root = _resolve_registry_root(registry_root, bundled_registry=bundled_registry)
    resolved_date = reviewed_at.date() if reviewed_at is not None else None
    if review_status is StampableReviewStatus.AGENT_REVIEWED and resolved_date is None:
        # Defaulted rather than demanded: the review being recorded is happening
        # now, so today is the true date. It is echoed back so the written value
        # is never implicit.
        #
        # Deliberately NOT widened to a lone ``--reviewed-by``. That path used to
        # inherit the declared reviewer's date and record a person as having
        # reviewed on a day they did not, and the writer now REFUSES it rather
        # than defaulting: a reviewer change carries no warrant that the review
        # is happening now, and defaulting would silently move a real review's
        # date whenever a caller only meant to correct a misspelt name. Widening
        # this condition would re-open that trade. See the writer's own rule.
        resolved_date = datetime.now(tz=UTC).date()
    try:
        result = stamp_revision(
            modelo,
            revision,
            engineered_by=engineered_by,
            clear_engineered_by=clear_engineered_by,
            review_status=review_status,
            reviewed_by=reviewed_by,
            reviewed_at=resolved_date,
            registry_root=root,
        )
    except StampError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(result.render())


def _resolve_registry_root(registry_root: Path | None, *, bundled_registry: bool) -> Path:
    """Resolve the tree to stamp, refusing anything that leaves the target implicit.

    Three refusals, one rule: the tree a write lands in is stated by the caller,
    never inferred.

    Neither flag is a refusal rather than a bundled-tree default, which is the
    whole change — the default WAS the bundled tree, and a caller that forgot to
    pass a root wrote a fabricated review into shipped data. Both flags together
    is a refusal because the two answers cannot be reconciled and picking one
    would guess. And ``--registry-root`` resolved to the bundled tree is a
    refusal because it is a second, silent door to shipped data: the point of
    ``--bundled-registry`` is that reaching the shipped registry is visible in
    the command line and in shell history, and a path that happens to resolve
    there is not.

    Args:
        registry_root: The root the caller named, or :data:`None`.
        bundled_registry: Whether the caller asked for the shipped tree by name.

    Returns:
        The resolved registry root to stamp.

    Raises:
        click.exceptions.BadParameter: Neither door was named, both were, or the
            named path resolves to the shipped tree.
    """
    bundled = bundled_registry_root()
    if bundled_registry and registry_root is not None:
        raise typer.BadParameter(
            f"--registry-root {str(registry_root)!r} and --bundled-registry name two different trees; "
            "supply exactly one",
        )
    if bundled_registry:
        return bundled
    if registry_root is None:
        raise typer.BadParameter(
            "no registry tree named: pass --registry-root PATH for a copy, or --bundled-registry to "
            f"stamp the shipped AEAT registry at {bundled}. There is deliberately no default: the "
            "only value it could have is the shipped registry, and a caller that forgot the flag "
            "wrote a fabricated review into it.",
        )
    if registry_root.resolve() == bundled:
        raise typer.BadParameter(
            f"--registry-root {str(registry_root)!r} resolves to the shipped AEAT registry at "
            f"{bundled}. Writing there is legal and is what this verb is for, but it is stated with "
            "--bundled-registry so the act is visible in the command line rather than hidden in a "
            "path that happens to resolve there.",
        )
    return registry_root


def _warn_if_vacuous(composed: ConformanceReport) -> None:
    """Echo the vacuity warning when the screen rendered nothing at all."""
    warning = vacuity_warning(composed)
    if warning is not None:
        typer.echo(warning)


__all__ = ["app"]
