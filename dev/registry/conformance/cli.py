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

Both ALWAYS exit 0, deliberately. The picture they render is currently a bad
one — ninety unreviewed revisions, five dead schema axes, an
independent-check coverage under five per cent — and a screen that refused to
render would leave that backlog unread while teaching every peer to route
around the tool. A fact earns a gating exit when its worklist empties, which is
what the ``audit`` verb is for.

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

from typing import Annotated

import typer

from .manager import (
    ConformanceReport,
    build_coverage_report,
    load_conformance_report,
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
