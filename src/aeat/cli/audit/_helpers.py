"""Helpers for the ``aeat audit`` subcommand surface (#339).

Exposes a strict pydantic :class:`CitationCoverageReport` and the pure
function :func:`validate_citation_coverage` that builds one from a
:class:`Ruleset`. Public from :mod:`aeat.cli.audit` for forward
compatibility with the future ``#394`` 13-root Kent-first tree (where
the ``audit`` root is first-class) and the ``#399`` ``--json`` output
schema work.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from ...formulas._ruleset import Ruleset
from ...models import ModeloCode

# TODO post-#399: register an OutputSchema for the audit-rulesets-citations
# command using CitationCoverageReport.model_json_schema() once the
# JSON-output contract lands.


class CitationCoverageReport(BaseModel):
    """Per-ruleset citation coverage on ``computed=True`` casillas.

    ``coverage_percent`` is a fraction in the closed interval [0.0, 1.0].
    ``missing_casillas`` is non-empty iff ``coverage_percent < 1.0``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ruleset_id: str = Field(min_length=1)
    modelo: ModeloCode
    effective_from: date
    effective_to: date | None
    total_computed: int = Field(ge=0)
    with_citation: int = Field(ge=0)
    coverage_percent: float = Field(ge=0.0, le=1.0)
    missing_casillas: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        """``True`` iff every computed casilla carries at least one citation."""
        return self.coverage_percent == 1.0


def validate_citation_coverage(ruleset: Ruleset) -> CitationCoverageReport:
    """Return a :class:`CitationCoverageReport` for ``ruleset``.

    Walks every casilla on the ruleset; a casilla counts toward
    ``total_computed`` only when ``computed=True``. ``with_citation``
    counts the subset whose ``legal_basis`` is non-empty. The
    :class:`CasillaDefinition` validator (#339) guarantees these are
    equal for every ruleset that imports successfully — the gap path
    can only be observed via fixtures built through pydantic's
    documented ``model_construct`` escape hatch.
    """
    computed = tuple(c for c in ruleset.casillas if c.computed)
    total = len(computed)
    with_citation = sum(1 for c in computed if c.legal_basis)
    missing = tuple(c.casilla_id for c in computed if not c.legal_basis)
    coverage = 1.0 if total == 0 else with_citation / total
    return CitationCoverageReport(
        ruleset_id=ruleset.ruleset_id,
        modelo=ruleset.modelo,
        effective_from=ruleset.effective_from,
        effective_to=ruleset.effective_to,
        total_computed=total,
        with_citation=with_citation,
        coverage_percent=coverage,
        missing_casillas=missing,
    )


def aggregate_reports(reports: Iterable[CitationCoverageReport]) -> CitationCoverageReport:
    """Return an aggregate :class:`CitationCoverageReport` over ``reports``.

    The aggregate uses ``ruleset_id="aggregate"``, the earliest
    ``effective_from``, and the latest ``effective_to`` (or ``None``
    when any input has an open span). Missing casillas are flattened
    across rulesets and prefixed with the contributing ``ruleset_id``
    so the reported ids stay unique.
    """
    bag = tuple(reports)
    if not bag:
        raise ValueError("aggregate_reports requires at least one report")
    total = sum(r.total_computed for r in bag)
    with_citation = sum(r.with_citation for r in bag)
    coverage = 1.0 if total == 0 else with_citation / total
    missing: tuple[str, ...] = tuple(f"{r.ruleset_id}:{cid}" for r in bag for cid in r.missing_casillas)
    earliest_from = min(r.effective_from for r in bag)
    open_span = any(r.effective_to is None for r in bag)
    latest_to: date | None = None if open_span else max(r.effective_to for r in bag if r.effective_to)
    representative_modelo = bag[0].modelo
    return CitationCoverageReport(
        ruleset_id="aggregate",
        modelo=representative_modelo,
        effective_from=earliest_from,
        effective_to=latest_to,
        total_computed=total,
        with_citation=with_citation,
        coverage_percent=coverage,
        missing_casillas=missing,
    )


__all__ = [
    "CitationCoverageReport",
    "aggregate_reports",
    "validate_citation_coverage",
]
