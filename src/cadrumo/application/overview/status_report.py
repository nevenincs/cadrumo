"""The overview status report and the advisories it carries.

These four builders were defined directly in the package namespace, which is
why that namespace could not be made inert by deleting an export map: there
was production code in it. They live in a module of their own now, and the
package root re-exports nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core.decimal.coercion import coerce_decimal_strict as _coerce_decimal_strict
from ...core.logging import get_logger as _get_logger
from ...core.modelo import Modelo as _Modelo
from ...domain.deadlines.models import evaluate_multiple_pagadores_obligation as _evaluate_multiple_pagadores_obligation
from .calendar_models import (
    OverviewStatusReport,
)

if TYPE_CHECKING:
    from ..state_projection import OperatorStateProjection
    from ..workflow.state_models import WorkflowState

_log = _get_logger(__name__)
_MULTIPLE_PAGADORES_OBLIGATION_LOCALE_KEY = "cli.overview.status.filing_obligation_multiple_pagadores"


def build_filing_obligation_advisories(
    raw_values: Mapping[str, object] | None,
    *,
    filing_year: int | None = None,
) -> tuple[str, ...]:
    """Derive overview-status advisory locale keys from raw profile values.

    The helper feeds :class:`OverviewStatusReport` and stays on the local
    read-model path. It implements the Art. 96.2.a)/96.3 LIRPF
    multiple-pagadores rule through
    :func:`domain.deadlines.evaluate_multiple_pagadores_obligation`:
    when the operator has declared ``irpf.pagadores_count >= 2`` and
    ``irpf.pagadores_secondary_income > 1500``, the work-income exemption
    limit drops from the general €22,000 to the per-year reduced limit, and
    Modelo 100 filing is mandatory when ``irpf.pagadores_total_work_income``
    exceeds that reduced limit. When the total work income is undeclared, the
    advisory surfaces conservatively rather than granting a false clear.

    Args:
        raw_values: Profile raw values mapping, or ``None``.
        filing_year: The income year selecting the dated reduced limit; when
            ``None`` the latest known reduced limit is used (the current
            figure for a year-agnostic operator surface).

    Returns a tuple of ``tr()``-resolvable locale keys, empty when no
    evidence of a mandatory obligation is present. Malformed raw values are
    logged only by profile-field name and exception type.
    """
    if raw_values is None:
        return ()

    def _to_int(field_name: str, v: object) -> int | None:
        if v is None or str(v).strip() == "":
            return None
        try:
            return int(str(v).strip())
        except ValueError as exc:
            _log.debug(
                "overview filing obligation advisory ignored invalid integer profile value",
                extra={"profile_field": field_name, "error_type": type(exc).__name__},
            )
            return None

    def _to_decimal(field_name: str, v: object) -> Decimal | None:
        if v is None or str(v).strip() == "":
            return None
        try:
            return _coerce_decimal_strict(v)
        except (InvalidOperation, ValueError) as exc:
            _log.debug(
                "overview filing obligation advisory ignored invalid decimal profile value",
                extra={"profile_field": field_name, "error_type": type(exc).__name__},
            )
            return None

    pagadores_count = _to_int("irpf.pagadores_count", raw_values.get("irpf.pagadores_count"))
    secondary_income = _to_decimal("irpf.pagadores_secondary_income", raw_values.get("irpf.pagadores_secondary_income"))
    total_work_income = _to_decimal(
        "irpf.pagadores_total_work_income",
        raw_values.get("irpf.pagadores_total_work_income"),
    )

    if _evaluate_multiple_pagadores_obligation(
        pagadores_count,
        secondary_income,
        total_work_income,
        filing_year,
    ):
        return (_MULTIPLE_PAGADORES_OBLIGATION_LOCALE_KEY,)
    return ()


def build_unsupported_work_create_modelos(
    raw_values: Mapping[str, object] | None,
) -> tuple[str, ...]:
    """Return modelos whose local work-create path is unsupported.

    The result feeds :class:`OverviewStatusReport` and uses canonical
    :class:`core.Modelo` identifiers. Non-resident IRNR profile state
    currently advertises Modelo 210 because the local work-create path is not
    available for that filing.
    """
    if raw_values is None:
        return ()
    fiscal_residency = (
        str(
            raw_values.get("taxpayer.fiscal_residency") or raw_values.get("taxpayer_type.fiscal_residency") or "",
        )
        .strip()
        .lower()
    )
    if fiscal_residency == "non_resident_irnr":
        return (_Modelo.M210.value,)
    return ()


def overview_status_report_from_projection(
    projection: OperatorStateProjection,
    *,
    raw_values: Mapping[str, object] | None = None,
) -> OverviewStatusReport:
    """Project the canonical state projection into the ``overview status`` emit shape.

    The :class:`OverviewStatusReport` is a CLI emit shape derived from
    the one :class:`application.state_projection.OperatorStateProjection`;
    it is not a second state-assembly path. Both the declaration-draft
    :class:`domain.filing.ModeloDraft` count and the
    :class:`~WorkUnitCatalogue` count are carried
    distinctly.

    Args:
        projection: The canonical state projection to project.
        raw_values: Optional profile raw values mapping. When supplied,
            used to evaluate filing-obligation advisories (e.g., the
            Art. 96.3 LIRPF multiple-pagadores rule).

    Returns:
        An :class:`OverviewStatusReport` derived from the projection.
    """
    return OverviewStatusReport(
        active_profile_name=projection.active_profile.label,
        transactions=projection.workspace.transactions,
        invoices=projection.workspace.invoices,
        drafts=projection.workspace.drafts,
        work_units=projection.workspace.work_units,
        discarded_work_units=projection.workspace.discarded_work_units,
        calculation_revisions=projection.workspace.calculation_revisions,
        unreadable_rows=projection.workspace.unreadable_rows,
        filing_obligation_advisories=build_filing_obligation_advisories(raw_values),
        unsupported_work_create_modelos=build_unsupported_work_create_modelos(raw_values),
    )


def build_overview_status_report(
    *,
    state: WorkflowState | None = None,
    raw_values: Mapping[str, object] | None = None,
) -> OverviewStatusReport:
    """Build and return the :class:`OverviewStatusReport` used by root and overview status.

    Consumes the canonical
    :func:`application.state_projection.build_operator_state_projection`
    and projects it through :func:`overview_status_report_from_projection`;
    the bespoke per-surface store assembly this function once carried is
    deleted. ``overview status`` therefore reports the same counters as
    every other operator surface — including the ``modelo work`` work units the
    old assembly never read.
    """
    from ..state_projection import build_operator_state_projection

    projection = build_operator_state_projection(state=state)
    return overview_status_report_from_projection(projection, raw_values=raw_values)
