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
        )
        typer.echo(f"recorded baseline recorded_at={written.recorded_at} rows={composed.revision_count}")
        return

    result = check_conformance_ratchet(composed, load_baseline(baseline))
    typer.echo(render_audit(result))
    if check and not result.passed:
        raise typer.Exit(code=1)


def _warn_if_vacuous(composed: ConformanceReport) -> None:
    """Emit a greppable warning when the screen rendered nothing at all.

    The screen keeps its zero exit — refusal belongs to the ``audit`` verb — but
    an empty render that said nothing would be indistinguishable from a clean
    registry, which is the exact false-green shape this whole surface exists to
    remove. The warning is a record line so a caller greps it rather than
    reading prose.
    """
    if composed.rows:
        return
    typer.echo(
        'warning rows=0 detail="composed no revision rows at all; every count above is vacuous '
        'and describes the read, not the registry"',
    )


__all__ = ["app"]
