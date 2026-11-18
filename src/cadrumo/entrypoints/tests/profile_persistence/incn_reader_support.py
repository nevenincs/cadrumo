"""Read the prior INCN through the resolver against an isolated operator work unit."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ....application.modelo.incn_periodo_anterior import (
    IncnPeriodoAnterior,
    IncnPeriodoAnteriorStores,
    resolve_incn_periodo_anterior,
)
from ..modelo_operator_work_storage import SeededOperatorWork


def read_seeded_incn(
    work: SeededOperatorWork,
    *,
    activity_start: datetime | None = None,
    twelve_month_statement: Decimal | None = None,
) -> IncnPeriodoAnterior:
    """Use the same pinned authority and repositories as the seeded calculation."""
    ports = work.ports
    return resolve_incn_periodo_anterior(
        work.work_unit.bucket_id,
        work.work_unit.filing_year,
        stores=IncnPeriodoAnteriorStores(
            operation=ports.operation,
            observation_repository=ports.observation_repository,
            iva_compensation_history_repository=ports.iva_compensation_history_repository,
            calculation_repository=ports.calculation_repository,
            work_unit_repository=ports.work_unit_repository,
            filing_repository=ports.filing_repository,
        ),
        activity_start_date=None if activity_start is None else activity_start.date(),
        twelve_month_statement=twelve_month_statement,
    )
