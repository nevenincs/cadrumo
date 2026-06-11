"""Headline result summary for a persisted calculation revision.

``work calculate`` and ``work revision`` render every casilla a modelo
declares — 2235 rows for Modelo 100. The figures an operator actually
looks for (the result to pay or refund, the key computed totals) are
buried in that flat table. This module distills a persisted
:class:`CalculationRevision` into a short, registry-grounded summary of
the headline casillas, so the CLI can lead with it before the full
table.

The headline casillas are taken from the modelo's own registry
metadata, never hand-picked: the ``reconciliation_totals`` of the
revision's verification expectations name the result-to-pay /
result-to-refund casillas, and the verification expectation's
``computed_casillas`` enumerate the modelo's key computed outputs.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import AeatError
from ...core.logging import get_logger
from ...domain.calculations.registry import CasillaId
from ...domain.modelos._calculation_revision import CalculationRevision
from ._calculation_helpers import resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit
from ._work_lifecycle import get_work_unit

_log = get_logger(__name__)


class ResultSummaryRow(BaseModel):
    """One headline casilla in a calculation result summary."""

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    label: str
    value: Decimal
    role: str
    """Why the casilla is a headline figure.

    ``result_ingresar`` / ``result_devolver`` mark the registry-declared
    result-to-pay / result-to-refund total. ``key_figure`` marks a
    computed casilla the modelo's verification expectation tracks.
    """


class CalculationResultSummary(BaseModel):
    """Distilled headline figures for a persisted calculation revision."""

    model_config = _STRICT_FROZEN

    modelo: str
    filing_year: int
    period: str
    rows: tuple[ResultSummaryRow, ...] = Field(default_factory=tuple)


def calculation_result_summary(revision: CalculationRevision) -> CalculationResultSummary | None:
    """Return the headline :class:`CalculationResultSummary` for a persisted :class:`CalculationRevision`.

    Resolves the revision's work unit and registry snapshot, then picks
    the headline casillas from the snapshot's verification expectations.
    Returns ``None`` when the work unit or registry snapshot cannot be
    resolved, or when the modelo declares no verification expectation —
    the caller then renders only the full casilla table.
    """
    casilla_values = revision.casilla_values
    try:
        work_unit = get_work_unit(str(revision.work_unit_id))
    except (LookupError, KeyError, AttributeError, AeatError) as exc:
        _log.warning(
            "modelo result summary: unable to resolve work unit for revision=%s",
            revision.calculation_revision_id,
            exc_info=exc,
        )
        return None
    try:
        snapshot = _resolve_registry_snapshot_for_work_unit(work_unit)
    except (LookupError, KeyError, AttributeError, AeatError) as exc:
        _log.warning(
            "modelo result summary: unable to resolve registry snapshot for work_unit=%s",
            work_unit.work_unit_id,
            exc_info=exc,
        )
        return None

    casilla_labels = {str(casilla.id): casilla.label for casilla in snapshot.revision.casillas}
    result_roles: dict[str, str] = {}
    key_figures: list[str] = []
    for expectation in snapshot.revision.verification_expectations:
        for kind, casilla_id in expectation.reconciliation_totals.items():
            role = "result_ingresar" if kind == "ingresar" else "result_devolver"
            result_roles.setdefault(str(casilla_id), role)
        for casilla_id in expectation.computed_casillas:
            if str(casilla_id) not in key_figures:
                key_figures.append(str(casilla_id))

    if not result_roles and not key_figures:
        return None

    rows: list[ResultSummaryRow] = []
    seen: set[str] = set()
    # Result-to-pay / result-to-refund totals lead the summary.
    for casilla_id, role in result_roles.items():
        value = casilla_values.get(casilla_id)
        if value is None or casilla_id in seen:
            continue
        rows.append(
            ResultSummaryRow(
                casilla_id=casilla_id,
                label=casilla_labels.get(casilla_id, casilla_id),
                value=value,
                role=role,
            ),
        )
        seen.add(casilla_id)
    # The verification expectation's computed casillas follow as key figures.
    for casilla_id in key_figures:
        value = casilla_values.get(casilla_id)
        if value is None or casilla_id in seen:
            continue
        rows.append(
            ResultSummaryRow(
                casilla_id=casilla_id,
                label=casilla_labels.get(casilla_id, casilla_id),
                value=value,
                role="key_figure",
            ),
        )
        seen.add(casilla_id)

    if not rows:
        return None
    return CalculationResultSummary(
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        rows=tuple(rows),
    )


__all__ = [
    "CalculationResultSummary",
    "ResultSummaryRow",
    "calculation_result_summary",
]
