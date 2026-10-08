"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from collections.abc import Sequence

from ....application.aggregation.service import PerModeloAggregationResult
from ....domain.calculations.registry.withholding_bindings import WithholdingClaveBreakdown
from .._modelo_payloads import ModeloAggregateResult, WithholdingWindowReadbackPayload
from ..modelo_aux_payloads import WithholdingClaveBreakdownPayload


def from_aggregation_result(
    result: PerModeloAggregationResult,
    *,
    clave_breakdown: Sequence[WithholdingClaveBreakdown] = (),
    withholding_window: WithholdingWindowReadbackPayload | None = None,
) -> ModeloAggregateResult:
    """Project the canonical service result onto the CLI transport shape.

    The one construction path, so the envelope cannot carry a modelo,
    period, provider, source-kind set, or counter the service did not
    produce. Counters come from the result's own
    :class:`~application.aggregation.service.PerModeloAggregationLogFields`, which
    already bounds them.

    Args:
        result: The canonical per-modelo aggregation result.
        clave_breakdown: Per-clave rows of the per-perceptor-clave detail
            the calculation reads, empty when it reads none.
        withholding_window: Current baseline and generation metadata for an
            invoice-backed withholding scope, absent for other modelos.
    """
    return ModeloAggregateResult(
        modelo=result.modelo,
        period=result.period,
        provider=result.provider,
        observation_count=result.log_fields.observation_count,
        source_kinds=list(result.source_kinds),
        result_row_count=result.log_fields.result_row_count,
        withholding_window=withholding_window,
        clave_breakdown=[
            WithholdingClaveBreakdownPayload(
                clave=row.clave,
                percepcion_count=row.percepcion_count,
                percibido_total=str(row.percibido_total),
                retencion_total=str(row.retencion_total),
            )
            for row in clave_breakdown
        ],
    )
