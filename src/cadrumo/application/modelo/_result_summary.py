"""Headline result summary for a persisted calculation revision.

``work calculate`` and ``work revision`` render every casilla a modelo
declares — 2235 rows for Modelo 100. The figures an operator actually
looks for (the result to pay or refund, the key computed totals) are
buried in that flat table. This module distills a persisted
:class:`CalculationRevision` into a short, registry-grounded summary of
the headline casillas, so the CLI can lead with it before the full
table.

The headline casillas are taken from the modelo's own registry
metadata, never hand-picked. The revision's parent :class:`WorkUnit`
selects the registry snapshot, whose :class:`VerificationExpectationDefinition`
entries use ``reconciliation_total_casilla_ids`` for result-to-pay /
result-to-refund casillas and ``computed_casilla_ids`` for the modelo's
key computed outputs.

This is a presentation summary only. It does not derive the fichero
``Tipo de declaración`` result disposition, apply Modelo 303 refund elections,
or decide cross-period carry-forward; that single determined fact belongs to
:func:`application.modelo._result_disposition_resolution.resolve_modelo_result_disposition`.

See Also:
    :func:`application.modelo._result_disposition_resolution.resolve_modelo_result_disposition`
        Determines the filed result disposition that export and carry-forward
        persistence read.
    :func:`cadrumo.application.filing.summarise_calculation`
        Draft-calculation summary surface for filing workflows; this module
        handles persisted modelo revisions instead.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import CadrumoError
from ...core.i18n import output_language
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.calculations.registry.schema_verification import fold_reconciliation_total_casilla_ids
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit
from ._calculation_helpers import resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit
from .work_lifecycle import get_work_unit

_log = get_logger(__name__)


class ResultSummaryRole(StrEnum):
    """Closed vocabulary of why a casilla is a headline figure.

    ``RESULT_INGRESAR`` / ``RESULT_DEVOLVER`` mark the registry-declared
    result-to-pay / result-to-refund total. ``KEY_FIGURE`` marks a
    computed casilla the modelo's verification expectation tracks.
    """

    RESULT_INGRESAR = "result_ingresar"
    RESULT_DEVOLVER = "result_devolver"
    KEY_FIGURE = "key_figure"


class ResultSummaryRow(BaseModel):
    """One application row for a headline casilla in a calculation summary.

    Rows are emitted only for casillas present in the source
    :class:`CalculationRevision` values. ``result_ingresar`` and
    ``result_devolver`` identify registry-declared reconciliation totals;
    ``key_figure`` identifies a computed output retained for the CLI summary.
    ``label`` is resolved once for the active output language. CLI JSON
    rendering serializes this model into ``ResultSummaryRowPayload`` rows with
    string decimal values.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    label: str
    value: Decimal
    role: ResultSummaryRole
    """Why the casilla is a headline figure. See :class:`ResultSummaryRole`."""


class CalculationResultSummary(BaseModel):
    """Distilled headline figures for a persisted calculation revision.

    The modelo, filing year, and typed :class:`Period` come from the parent
    :class:`WorkUnit`; rows are :class:`ResultSummaryRow` values selected from
    that work unit's registry snapshot. Text rendering uses the period's bare
    registry token so the summary header does not duplicate the filing year.
    """

    model_config = _STRICT_FROZEN

    modelo: str
    filing_year: int
    period: Period
    rows: tuple[ResultSummaryRow, ...] = Field(default_factory=tuple)


def calculation_result_summary(
    revision: CalculationRevision,
    *,
    work_unit_resolver: Callable[[str], WorkUnit] = get_work_unit,
) -> CalculationResultSummary | None:
    """Return the :class:`CalculationResultSummary` for ``revision``, if available.

    ``revision`` is the persisted :class:`CalculationRevision` attempt and
    provides ``casilla_values``. The function resolves its parent
    :class:`WorkUnit`, then reads the registry snapshot's verification
    expectations for that work unit's revision. Missing work-unit or snapshot
    lookup errors return ``None`` so callers can render only the full casilla
    table; unexpected errors are allowed to propagate.

    For each :class:`VerificationExpectationDefinition`,
    ``reconciliation_total_casilla_ids`` are considered first and produce
    ``result_ingresar`` or ``result_devolver`` rows. Remaining unique
    ``computed_casilla_ids`` produce ``key_figure`` rows. A result casilla is
    emitted once and skipped later if it also appears as a computed key figure.

    Rows are emitted only when their casilla id exists in
    ``revision.casilla_values``. Returns ``None`` when no candidate row
    survives.
    """
    casilla_values = revision.casilla_values
    try:
        work_unit = work_unit_resolver(str(revision.work_unit_id))
    except (LookupError, KeyError, AttributeError, CadrumoError) as exc:
        _log.warning(
            "modelo result summary: unable to resolve work unit for revision=%s",
            revision.calculation_revision_id,
            exc_info=exc,
        )
        return None
    try:
        snapshot = _resolve_registry_snapshot_for_work_unit(work_unit)
    except (LookupError, KeyError, AttributeError, CadrumoError) as exc:
        _log.warning(
            "modelo result summary: unable to resolve registry snapshot for work_unit=%s",
            work_unit.work_unit_id,
            exc_info=exc,
        )
        return None

    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    result_roles, key_figures = _summary_candidate_ids(snapshot)

    if not result_roles and not key_figures:
        return None

    rows = _summary_rows(
        casilla_values,
        casillas_by_id=casillas_by_id,
        result_roles=result_roles,
        key_figures=key_figures,
    )

    if not rows:
        return None
    return CalculationResultSummary(
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        rows=tuple(rows),
    )


def _summary_candidate_ids(
    snapshot: RegistrySnapshot,
) -> tuple[dict[CasillaId, ResultSummaryRole], list[CasillaId]]:
    result_roles: dict[CasillaId, ResultSummaryRole] = {}
    key_figures: list[CasillaId] = []
    for kind, casilla_id in fold_reconciliation_total_casilla_ids(snapshot.revision.verification_expectations).items():
        role = ResultSummaryRole.RESULT_INGRESAR if kind == "ingresar" else ResultSummaryRole.RESULT_DEVOLVER
        result_roles.setdefault(casilla_id, role)
    for expectation in snapshot.revision.verification_expectations:
        for casilla_id in expectation.computed_casilla_ids:
            if casilla_id not in key_figures:
                key_figures.append(casilla_id)
    return result_roles, key_figures


def _summary_rows(
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
    result_roles: Mapping[CasillaId, ResultSummaryRole],
    key_figures: list[CasillaId],
) -> list[ResultSummaryRow]:
    rows: list[ResultSummaryRow] = []
    seen: set[CasillaId] = set()
    for casilla_id, role in result_roles.items():
        _append_summary_row(
            rows,
            seen,
            casilla_id=casilla_id,
            value=casilla_values.get(casilla_id),
            role=role,
            casillas_by_id=casillas_by_id,
        )
    for casilla_id in key_figures:
        _append_summary_row(
            rows,
            seen,
            casilla_id=casilla_id,
            value=casilla_values.get(casilla_id),
            role=ResultSummaryRole.KEY_FIGURE,
            casillas_by_id=casillas_by_id,
        )
    return rows


def _append_summary_row(
    rows: list[ResultSummaryRow],
    seen: set[CasillaId],
    *,
    casilla_id: CasillaId,
    value: Decimal | None,
    role: ResultSummaryRole,
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> None:
    if value is None or casilla_id in seen:
        return
    casilla = casillas_by_id.get(casilla_id)
    rows.append(
        ResultSummaryRow(
            casilla_id=casilla_id,
            label=casilla.get_label(output_language()) if casilla is not None else casilla_id,
            value=value,
            role=role,
        ),
    )
    seen.add(casilla_id)


__all__ = [
    "CalculationResultSummary",
    "ResultSummaryRole",
    "ResultSummaryRow",
    "calculation_result_summary",
]
