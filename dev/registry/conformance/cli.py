"""Developer CLI for modelo registry conformance governance.

A dev / maintenance module CLI invoked as ``python -m dev.registry.conformance``,
mirroring the ``dev.registry.matrix``, ``cadrumo.locales`` and
``dev.docs.terminology_handbook`` precedents. It is NOT part of the operator
``aeat config`` / ``aeat app`` surface, so it does not bear on the
two-CLI-roots architecture rule; like ``apidocs`` it emits plain English
maintenance output rather than localised strings.

Verbs:

* ``report`` -- every conformance axis, one row per modelo revision.
* ``coverage`` -- per-axis measured counts against their real populations.
* ``audit [--check]`` -- the shrink-only ratchet against the committed
  baseline. ``--check`` is the ONLY gating exit in this whole surface.
* ``stamp`` -- write a revision's DECLARED governance provenance. It cannot
  write ``operator_reviewed``: this CLI is agent-driven, and an agent recording
  an operator's signoff is the exact dishonesty the feature exists to detect.
  The schema still accepts the value, so the operator signs off by editing
  ``revision.toml`` directly.

``report`` and ``coverage`` ALWAYS exit 0, deliberately. The picture they render
is currently a bad one — ninety unreviewed revisions, five dead schema axes, an
independent-check coverage under five per cent — and a screen that refused to
render would leave that backlog unread while teaching every peer to route
around the tool. A fact earns a gating exit when its worklist empties, which is
what ``audit --check`` is for: it does not demand the backlog be clean, only
that it not GROW.

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
    :mod:`~dev.registry.matrix.cli`
        Sibling registry capability-matrix CLI.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from ._stamp import StampableReviewStatus, StampError, stamp_revision
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


@app.command("audit")
def audit(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Gate: exit 1 when a backlog counter grew past its ceiling or a population fell below its floor.",
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

    Two directions are checked and reported separately, because they fail for
    opposite reasons. A CEILING violation means a backlog or defect count GREW:
    somebody added an unreviewed revision, a grounding finding, a classification
    incoherence. A FLOOR violation means a measurement population FELL: the run
    examined fewer revisions, casillas, oracle payloads, or locale leaves than
    the baseline proves it must, so every clean ceiling above it is vacuous and
    cannot be trusted. Floors are reported first for that reason.

    Without ``--check`` this is a screen and exits 0 whatever it finds.

    ``--record`` is compared against the baseline already on disk in the same
    two directions, and refuses a capture that would raise a ceiling or lower a
    floor unless ``--accept-weakening`` says so. The floor direction is why: a
    raised ceiling shows up on the census and the next honest capture pulls it
    back, while a floor lowered by a capture taken over a half-landed tree is
    silent forever and disarms the anti-vacuity check permanently.
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
                "Registry tree root to stamp. Defaults to the bundled AEAT tree. Present so this verb "
                "can be exercised against a copy instead of the shipped registry."
            ),
        ),
    ] = None,
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

    ``--registry-root`` exists so this command can be run at all without writing
    to the shipped registry. The writer has always accepted a root and this verb
    never passed one, so every CLI-level behaviour here — the today-defaulting of
    the review date, the translation of a writer refusal into a parameter error —
    had no end-to-end coverage of any kind, and a finding about the writer could
    not be reproduced through the real app. The containment check is relative to
    whatever root it is given, so pointing it at a copy loses no safety.
    """
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
            registry_root=registry_root,
        )
    except StampError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(result.render())


def _warn_if_vacuous(composed: ConformanceReport) -> None:
    """Echo the vacuity warning when the screen rendered nothing at all."""
    warning = vacuity_warning(composed)
    if warning is not None:
        typer.echo(warning)


__all__ = ["app"]
