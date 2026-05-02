"""``aeat audit`` subcommand surface (dev-only).

This subpackage exposes the ``Typer`` apps that make up the ``aeat
audit`` namespace. They are importable from
:mod:`aeat.entrypoints.cli.audit` and fully testable via
:class:`typer.testing.CliRunner`, but registration on the root ``aeat``
``Typer`` app is intentionally deferred to a single follow-up commit
to avoid collisions with parallel work on the error-code registry and
the ``--json`` output contract.

The ``audit`` namespace is intentionally non-default. Today it ships
one dev-only command, ``aeat audit rulesets citations``, that walks
the registered rulesets and reports per-modelo coverage of the
mandatory-citation invariant. The namespace is forward-compatible with
the operator-first command tree and will gain non-dev surfaces over
time.
"""

from __future__ import annotations

import sys

import typer

from ....domain.formulas._rulesets import ALL_RULESETS
from .._i18n import t, tr
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
    """Reconfigure :data:`sys.stdout` and :data:`sys.stderr` to UTF-8 if possible.

    The audit reports render Spanish article fragments verbatim
    ("artículo 110.1.c", "agrícolas, ganaderas, forestales y
    pesqueras") and modelo names with diacritics. On Windows the
    default console encoding is cp1252, which crashes on non-ASCII
    output. Reconfiguring to UTF-8 at command entry is the documented
    Python 3.7+ workaround. Streams that don't support ``reconfigure``
    (for example when stdout has been replaced with a buffered I/O
    object during testing) are left alone —
    :class:`typer.testing.CliRunner` substitutes its own capturing
    stream that handles arbitrary text.
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
    """Render a single :class:`CitationCoverageReport` as one display line.

    A :data:`None` ``modelo`` renders as ``"all"`` to signal a
    multi-modelo aggregate (per the :func:`aggregate_reports` contract).
    Per-ruleset reports always carry a concrete modelo.
    """
    bar = "OK " if report.is_complete else "GAP"
    pct = f"{report.coverage_percent * 100:6.2f}%"
    span = f"{report.effective_from.isoformat()}…{report.effective_to.isoformat() if report.effective_to else 'open'}"
    modelo_label = report.modelo.value if report.modelo is not None else "all"
    body = (
        f"{bar} {report.ruleset_id:<32} "
        f"modelo {modelo_label} "
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
        "over every registered ruleset. Exits non-zero on any gap."
    ),
)
def citations_cmd() -> None:
    """Walk every registered ruleset and report mandatory-citation coverage.

    Emits one line per ruleset followed by an aggregate line. Exits
    with code ``1`` if any ruleset has a coverage gap on
    ``computed=True`` casillas; exits with code ``0`` otherwise.

    The mandatory-citation validator on
    :class:`aeat.domain.casillas.CasillaDefinition` guarantees that no
    real ruleset can ever ship a gap — a gap can only appear via a
    fixture built with pydantic's documented ``model_construct``
    escape hatch. This command therefore serves as a defence-in-depth
    audit surface and as the reporting tool used to prove a per-modelo
    verify-roundtrip baseline.

    Raises:
        :exc:`typer.Exit`: With code ``1`` when any ruleset has a
            citation gap, or when no rulesets are registered.
    """
    _reconfigure_utf8()
    if not ALL_RULESETS:
        typer.echo(
            tr(
                t(
                    "no hay rulesets registrados",
                    "no rulesets registered",
                    "no hi ha rulesets registrats",
                    "nincsenek regisztrált rulesetek",
                )
            ),
            err=True,
        )
        raise typer.Exit(code=1)
    reports = tuple(validate_citation_coverage(ruleset) for ruleset in ALL_RULESETS)
    for report in reports:
        typer.echo(_render_line(report))
    aggregate = aggregate_reports(reports)
    typer.echo("-" * 80)
    typer.echo(_render_line(aggregate))
    if not aggregate.is_complete:
        typer.echo(
            tr(
                t(
                    "FAIL: al menos un ruleset tiene legal_basis ausente en una casilla calculada. "
                    "Inspecciona las filas GAP arriba.",
                    "FAIL: at least one ruleset has missing legal_basis on a computed casilla. "
                    "Inspect the GAP rows above.",
                    "FAIL: almenys un ruleset té legal_basis absent en una casella calculada. "
                    "Inspecciona les files GAP a sobre.",
                    "FAIL: legalább egy ruleset legal_basis-a hiányzik egy számított rovaton. "
                    "Vizsgáld meg a fenti GAP sorokat.",
                )
            ),
            err=True,
        )
        raise typer.Exit(code=1)


__all__ = [
    "CitationCoverageReport",
    "aggregate_reports",
    "audit_app",
    "validate_citation_coverage",
]
