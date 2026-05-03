"""Legacy audit report schemas retained for migration-only tests."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from ....domain.modelos import ModeloCode


class CitationCoverageReport(BaseModel):
    """Legacy citation coverage report shape retained for old fixtures.

    ``coverage_percent`` is a fraction in the closed interval ``[0.0, 1.0]``.
    ``missing_casillas`` is non-empty iff ``coverage_percent < 1.0``.
    ``modelo`` is :data:`None` only on aggregate reports that span more
    than one distinct :class:`aeat.domain.modelos.ModeloCode`; per-ruleset
    reports always carry the ruleset's modelo.

    Attributes:
        ruleset_id: Stable identifier of the source ruleset, or
            ``"aggregate"`` on aggregated reports.
        modelo: The modelo the report covers, or ``None`` for a
            multi-modelo aggregate.
        effective_from: First date on which the ruleset (or earliest
            ruleset in an aggregate) is in force.
        effective_to: Last date on which the ruleset is in force, or
            ``None`` for an open span.
        total_computed: Number of casillas marked ``computed=True``.
        with_citation: Subset of ``total_computed`` carrying at least one
            legal citation.
        coverage_percent: ``with_citation / total_computed``, or ``1.0``
            when ``total_computed`` is zero.
        missing_casillas: Casilla ids that are computed but have no
            legal basis attached.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ruleset_id: str = Field(min_length=1)
    modelo: ModeloCode | None
    effective_from: date
    effective_to: date | None
    total_computed: int = Field(ge=0)
    with_citation: int = Field(ge=0)
    coverage_percent: float = Field(ge=0.0, le=1.0)
    missing_casillas: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        """Return ``True`` iff every computed casilla carries at least one citation."""
        return self.coverage_percent == 1.0


def validate_citation_coverage(ruleset: object) -> CitationCoverageReport:
    """Reject legacy ruleset citation coverage calculation."""

    _ = ruleset
    raise ValueError("legacy ruleset citation audits are disabled; use the registry")


def aggregate_reports(reports: Iterable[CitationCoverageReport]) -> CitationCoverageReport:
    """Return an aggregate :class:`CitationCoverageReport` over ``reports``.

    The aggregate uses ``ruleset_id="aggregate"``, the earliest
    ``effective_from``, and the latest ``effective_to`` (or ``None``
    when any input has an open span). Missing casillas are flattened
    across rulesets and prefixed with the contributing ``ruleset_id``
    so the reported ids stay unique.

    ``modelo`` is set to the shared
    :class:`aeat.domain.modelos.ModeloCode` only when every input
    report carries the same modelo; otherwise it is ``None`` to signal
    a multi-modelo aggregate. Picking an arbitrary "representative"
    modelo from a mixed bag would mislead any downstream consumer that
    filters by modelo.

    Args:
        reports: One or more reports to fold together.

    Returns:
        A single aggregate :class:`CitationCoverageReport`.

    Raises:
        ValueError: When ``reports`` is empty.
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
    unique_modelos = {r.modelo for r in bag if r.modelo is not None}
    aggregate_modelo: ModeloCode | None = next(iter(unique_modelos)) if len(unique_modelos) == 1 else None
    return CitationCoverageReport(
        ruleset_id="aggregate",
        modelo=aggregate_modelo,
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
