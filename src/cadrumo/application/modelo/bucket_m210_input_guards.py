"""Input conflicts the M210 gross-income source mode refuses before a bucket calculation."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.irnr import M210GrossIncomeSourceMode
from ...domain.calculations.registry.irnr_tipo_renta import m210_tipo_renta_code_projection
from ...domain.modelos.row_models import Modelo210AgrupacionRentaRow, ModeloDetailRow
from .action_errors import ModeloAggregationInputConflictError
from .preconditions import build_modelo_calculate_refusal_failure


def reject_manual_m210_gross_income_override_in_ledger_mode(
    *,
    mode: M210GrossIncomeSourceMode | None,
    casilla_inputs: Mapping[CasillaId, Decimal],
) -> None:
    """Keep explicit ledger and manual M210 [5] authority mutually exclusive."""
    if mode is not M210GrossIncomeSourceMode.LEDGER:
        return
    if "rendimientos_integros" in casilla_inputs:
        raise ModeloAggregationInputConflictError(
            translated_message="application.modelo.errors.caller_casilla_source_binding_conflict",
            context={"casillas": ["rendimientos_integros"]},
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="m210.gross_income_source.ledger_with_manual_gross_income",
                evidence_values={"rejected_casilla_ids": "rendimientos_integros", "ledger_source": True},
            ),
        )


def validate_m210_official_tipo_renta_selection(
    *,
    mode: M210GrossIncomeSourceMode | None,
    m210_official_tipo_renta_code: str | None,
    text_casilla_inputs: Mapping[CasillaId, str],
) -> None:
    """Keep raw M210 code and conceptual formula token coherent at the application boundary."""
    if m210_official_tipo_renta_code is None:
        if mode is M210GrossIncomeSourceMode.LEDGER:
            raise ModeloAggregationInputConflictError(
                translated_message="application.modelo.errors.m210_ledger_source_selection_required",
                precondition_failure=build_modelo_calculate_refusal_failure(
                    scenario="m210.tipo_renta.ledger_selection_missing",
                    evidence_values={"ledger_source": True, "official_tipo_renta_code_stated": False},
                ),
            )
        return
    expected_tipo_renta = m210_tipo_renta_code_projection().get(m210_official_tipo_renta_code)
    if expected_tipo_renta is None or text_casilla_inputs.get("tipo_renta") != expected_tipo_renta.value:
        raise ModeloAggregationInputConflictError(
            translated_message="application.modelo.errors.m210_official_tipo_renta_selection_mismatch",
            context={
                "official_tipo_renta_code": m210_official_tipo_renta_code,
                "expected_tipo_renta": expected_tipo_renta.value if expected_tipo_renta is not None else None,
                "tipo_renta": text_casilla_inputs.get("tipo_renta"),
            },
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="m210.tipo_renta.official_code_mismatch",
                evidence_values={
                    "official_tipo_renta_code": m210_official_tipo_renta_code,
                    "official_code_recognised": expected_tipo_renta is not None,
                },
            ),
        )


def reject_manual_m210_agrupacion_rows_in_ledger_mode(
    *,
    mode: M210GrossIncomeSourceMode | None,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> None:
    """Keep annual M210 ledger evidence on the same classified-row authority."""
    if mode is M210GrossIncomeSourceMode.LEDGER and any(
        isinstance(row, Modelo210AgrupacionRentaRow) for row in detail_rows
    ):
        raise ModeloAggregationInputConflictError(
            translated_message="application.modelo.errors.m210_ledger_manual_agrupacion_rows",
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="m210.gross_income_source.ledger_with_manual_agrupacion_rows",
                evidence_values={
                    "ledger_source": True,
                    "manual_agrupacion_row_count": sum(
                        isinstance(row, Modelo210AgrupacionRentaRow) for row in detail_rows
                    ),
                },
            ),
        )
