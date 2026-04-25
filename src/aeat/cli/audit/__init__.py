"""``aeat audit`` subcommand surface (#339, dev-only).

Phase 1 of issue #339 ships this subpackage in isolation: the audit
``Typer`` apps are importable from :mod:`aeat.cli.audit` and fully
testable via :class:`typer.testing.CliRunner`, but the surface is **not
yet** registered on the root ``aeat`` ``Typer`` app. The root
registration is deferred to a single Phase 2 follow-up commit that
lands after either ``#398`` (error-code registry) or ``#399``
(``--json`` output contract) merges, to avoid a 3-way collision on
:mod:`aeat.cli.__init__`.

The ``audit`` namespace is intentionally non-default. Today it ships
one dev-only command — ``aeat audit rulesets citations`` — that walks
the registered rulesets and reports per-modelo coverage of the
mandatory-citation invariant introduced in this issue. Forward-
compatible with the future ``#394`` 13-root Kent-first tree, where
``audit`` is a Kent-first root extended over time with non-dev
surfaces.
"""

from __future__ import annotations

import sys

import typer

from ...formulas._rulesets import ALL_RULESETS
from ._helpers import (
    CitationCoverageReport,
    aggregate_reports,
    validate_citation_coverage,
)

audit_app = typer.Typer(
    name="audit",
    help="Audit helpers (dev-only).",
    no_args_is_help=True,
    add_completion=False,
)
rulesets_app = typer.Typer(
    name="rulesets",
    help="Ruleset audit subcommands.",
    no_args_is_help=True,
    add_completion=False,
)
audit_app.add_typer(rulesets_app, name="rulesets")


def _reconfigure_utf8() -> None:
    """Reconfigure ``sys.stdout`` / ``sys.stderr`` to UTF-8 if possible.

    The audit reports render Spanish article fragments verbatim
    ("artículo 110.1.c", "agrícolas, ganaderas, forestales y
    pesqueras") and modelo names with diacritics. On Windows the
    default console encoding is cp1252, which crashes on non-ASCII
    output (regression observed in #389). Reconfiguring to UTF-8 at
    command entry is the documented Python 3.7+ workaround. ``Stream``s
    that don't support ``reconfigure`` (e.g. when stdout has been
    replaced with a buffered I/O object during testing) are left
    alone — :class:`typer.testing.CliRunner` substitutes its own
    capturing stream that handles arbitrary text.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            continue


def _render_line(report: CitationCoverageReport) -> str:
    """Render a single :class:`CitationCoverageReport` as one line."""
    bar = "OK " if report.is_complete else "GAP"
    pct = f"{report.coverage_percent * 100:6.2f}%"
    span = f"{report.effective_from.isoformat()}…{report.effective_to.isoformat() if report.effective_to else 'open'}"
    body = (
        f"{bar} {report.ruleset_id:<32} "
        f"modelo {report.modelo.value} "
        f"{span}  "
        f"computed={report.total_computed:>3d}  "
        f"with_citation={report.with_citation:>3d}  "
        f"coverage={pct}"
    )
    if report.missing_casillas:
        body += f"  missing={list(report.missing_casillas)}"
    return body


@rulesets_app.command(
    "citations",
    help=(
        "Report per-modelo coverage of the mandatory-citation invariant "
        "(#339) over every registered ruleset. Exits non-zero on any gap."
    ),
)
def citations_cmd() -> None:
    """Walk every registered ruleset and report citation coverage.

    Emits one line per ruleset followed by an aggregate line. Exits
    with code ``1`` if any ruleset has a coverage gap on
    ``computed=True`` casillas; exits with code ``0`` otherwise.

    The mandatory-citation validator on :class:`CasillaDefinition`
    guarantees that no real ruleset can ever ship a gap — a gap can
    only appear via a fixture built with pydantic's documented
    ``model_construct`` escape hatch. This command therefore serves as
    a defence-in-depth audit surface and as the reporting tool the
    EPIC #316 child issues use to prove their per-modelo
    verify-roundtrip baseline.
    """
    _reconfigure_utf8()
    if not ALL_RULESETS:
        typer.echo("no rulesets registered", err=True)
        raise typer.Exit(code=1)
    reports = tuple(validate_citation_coverage(ruleset) for ruleset in ALL_RULESETS)
    for report in reports:
        typer.echo(_render_line(report))
    aggregate = aggregate_reports(reports)
    typer.echo("-" * 80)
    typer.echo(_render_line(aggregate))
    if not aggregate.is_complete:
        typer.echo(
            "FAIL: at least one ruleset has missing legal_basis on a computed casilla. Inspect the GAP rows above.",
            err=True,
        )
        raise typer.Exit(code=1)


__all__ = [
    "CitationCoverageReport",
    "aggregate_reports",
    "audit_app",
    "rulesets_app",
    "validate_citation_coverage",
]
