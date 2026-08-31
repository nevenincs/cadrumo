"""Modelo 210 annual grouped-renta boundary and verification contract.

The registry formula continues to calculate M210 from its declared casillas.
This module owns only the legal evidence gate for the annual grouped-renta
period (``0A``): it accepts the persisted typed rows, never sums them into an
input or computed casilla, and converts any persisted-data drift into an
ordinary verification finding.

See Also:
    :func:`cadrumo.domain.modelos.validate_m210_agrupacion_renta_rows`:
        Domain-owned Article 2 compatibility validation for the row set.
    :func:`cadrumo.application.modelo.calculate_modelo_revision`:
        Calculation boundary that refuses an invalid row set before formula
        execution and revision persistence.
"""

from __future__ import annotations

from ...core.modelo import Modelo
from ...core.period import StandardPeriodCode
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.row_models import (
    Modelo210AgrupacionRentaRow,
    Modelo210AgrupacionRentaRowsError,
    ModeloDetailRow,
    validate_m210_agrupacion_renta_rows,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit

_M210_AGRUPACION_LEGAL_REF = "orden-eha-3316-2010:art-2"
_M210_AGRUPACION_SOURCE_REF = "boe-modelo-210-2024-form-layout"


def validate_m210_agrupacion_renta_rows_for_calculation(
    *,
    work_unit: WorkUnit,
    detail_rows: tuple[ModeloDetailRow, ...],
    m210_official_tipo_renta_code: str | None,
) -> None:
    """Require a complete, homogeneous row set for M210's annual ``0A`` mode.

    No other modelo can carry an M210 grouped-renta row, and non-annual M210
    work remains on the established scalar manual path. The 0A path is strict:
    an empty or mixed row set is refused before formula evaluation, while the
    domain validator checks the statutory component compatibility.
    """
    m210_rows = tuple(row for row in detail_rows if isinstance(row, Modelo210AgrupacionRentaRow))
    is_m210_annual_group = (
        str(work_unit.modelo) == str(Modelo.M210) and work_unit.period.standard_code is StandardPeriodCode.ANNUAL
    )

    if not is_m210_annual_group:
        if m210_rows:
            raise ModeloError(
                translated_message="errors.error.error_modelos",
                context={
                    "modelo": str(work_unit.modelo),
                    "period": work_unit.period.registry_token,
                    "m210_row_count": str(len(m210_rows)),
                },
            )
        return

    if len(m210_rows) != len(detail_rows):
        raise ModeloError(
            translated_message="errors.error.error_modelos",
            context={
                "detail_row_count": str(len(detail_rows)),
                "m210_row_count": str(len(m210_rows)),
            },
        )
    try:
        validate_m210_agrupacion_renta_rows(m210_rows)
    except Modelo210AgrupacionRentaRowsError as exc:
        raise ModeloError(
            str(exc),
            context={"reason": exc.reason, "detail": exc.detail},
        ) from exc

    if m210_official_tipo_renta_code is None:
        raise ModeloError(
            translated_message="errors.error.error_modelos",
            context={"m210_row_count": str(len(m210_rows))},
        )
    row_code = m210_rows[0].tipo_renta_code
    if row_code != m210_official_tipo_renta_code:
        raise ModeloError(
            translated_message="errors.error.error_modelos",
            context={
                "selected_tipo_renta_code": m210_official_tipo_renta_code,
                "row_tipo_renta_code": row_code,
            },
        )


def m210_agrupacion_renta_verification_findings(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return a blocking finding when persisted annual-group evidence is invalid.

    ``revision`` is the :class:`CalculationRevision` under verification.

    Normal calculation cannot persist this state because the calculate boundary
    above rejects it. Verify repeats the domain rule as an integrity check over
    stored revisions, preventing an old or malformed persisted record from
    becoming ``VERIFICADO_COMPLETO`` through a future import or storage path.
    """
    if str(work_unit.modelo) != str(Modelo.M210) or work_unit.period.standard_code is not StandardPeriodCode.ANNUAL:
        return ()
    try:
        validate_m210_agrupacion_renta_rows_for_calculation(
            work_unit=work_unit,
            detail_rows=revision.detail_rows,
            m210_official_tipo_renta_code=revision.m210_official_tipo_renta_code,
        )
    except ModeloError as exc:
        return (
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                message_locale_key="application.modelo.findings.m210_agrupacion_renta_invalid",
                message_facts={
                    "error_type": type(exc).__name__,
                    "modelo_id": str(work_unit.modelo),
                    "period_code": work_unit.period.registry_token,
                },
                legal_refs=(_M210_AGRUPACION_LEGAL_REF,),
                source_refs=(_M210_AGRUPACION_SOURCE_REF,),
            ),
        )
    return ()


__all__ = [
    "m210_agrupacion_renta_verification_findings",
    "validate_m210_agrupacion_renta_rows_for_calculation",
]
