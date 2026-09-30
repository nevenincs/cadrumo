"""Modelo 130 negative result: the exported Tipo de declaracion follows the quarter.

The official Modelo 130 instructions give a negative casilla 19 two different
declaration types: "A deducir" (B) in the first three quarters, where the
negative amount carries into the next quarter of the same ejercicio, and
"Negativa" (N) in the fourth quarter, where nothing is left to carry. The
export must resolve that disposition and write it into the fichero's Tipo de
declaracion position, which is read back here from the official record layout.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.modelo_export_support import (
    _M130_RESULT_CASILLA,
    export_taxpayer_profile,
    isolated_backend,
    seed_profile,
    seed_revision,
)
from cadrumo.application.filing.runtime import build_runtime_schema_provider
from cadrumo.application.modelo.export import ModeloExportCommand, export_modelo_revision
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.period import Period
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState

__all__ = ["isolated_backend"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FILING_YEAR = 2026
_INGRESOS_CASILLA = validated_casilla_id("01", surface="m130 negative result test")
_GASTOS_CASILLA = validated_casilla_id("02", surface="m130 negative result test")
# Synthetic quarter: 250.00 of income gives a 50.00 pago fraccionado (casilla
# 04 = 20% of casilla 03), and a prior-year net income of zero gives the full
# 100.00 minoracion of casilla 13, so casilla 19 = 50.00 - 100.00 = -50.00.
_INPUTS = {_INGRESOS_CASILLA: "250.00", _GASTOS_CASILLA: "0.00"}
_ZERO_PRIOR_BINDINGS: dict[BindingId, str] = {
    "modelo-130-pagos-fraccionados-anteriores": "0",
    "modelo-130-resultados-negativos-anteriores": "0",
    "irpf.previous_year_economic_activity_net_income": "0",
}
_NEGATIVE_RESULT = Decimal("-50.00")
_LINE_ENDING_WIDTH = {"crlf": 2, "lf": 1}


def _m130_layout(period: str) -> ExportLayoutDefinition:
    provider = build_runtime_schema_provider(
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, period),
        modelos=("130",),
    )
    [layout] = provider.get_subview("130").export_layouts
    return layout


def _record_wire_length(record: ExportRecordDefinition) -> int:
    return max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields)


def _field_slice(layout: ExportLayoutDefinition, field: ExportFieldDefinition) -> slice:
    """Locate one field in the emitted bytes by walking the layout's records in order."""
    cursor = 0
    for record in sorted(layout.records, key=lambda item: item.order):
        if field in record.fields:
            assert field.offset is not None
            assert field.length is not None
            start = cursor + field.offset - 1
            return slice(start, start + field.length)
        cursor += _record_wire_length(record) + _LINE_ENDING_WIDTH.get(str(record.line_ending), 0)
    raise AssertionError(f"export field {field.id!r} is not in layout {layout.id!r}")


def _producer_field(layout: ExportLayoutDefinition, producer_key: FilingProducerKey) -> ExportFieldDefinition:
    matches = [field for record in layout.records for field in record.fields if field.producer_key is producer_key]
    assert len(matches) == 1, [field.id for field in matches]
    return matches[0]


def _casilla_field(layout: ExportLayoutDefinition, casilla_id: str) -> ExportFieldDefinition:
    matches = [field for record in layout.records for field in record.fields if field.casilla_id == casilla_id]
    assert len(matches) == 1, [field.id for field in matches]
    return matches[0]


def _export_negative_m130(tmp_path: Path, *, period: str, activity_start: date) -> tuple[ResultDisposition, bytes]:
    with bundled_indexed_authority().operation() as operation:
        bucket_id = seed_profile()
        _, revision_id = seed_revision(
            bucket_id=bucket_id,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
            modelo="130",
            filing_year=_FILING_YEAR,
            period=period,
            input_values_by_casilla_id=dict(_INPUTS),
            binding_overrides=dict(_ZERO_PRIOR_BINDINGS),
            casilla_values={_M130_RESULT_CASILLA: _NEGATIVE_RESULT},
        )
        output_path = tmp_path / f"modelo-130-{_FILING_YEAR}-{period}.txt"
        result = export_modelo_revision(
            ModeloExportCommand(calculation_revision_id=revision_id, output_path=output_path, actor="operator"),
            workflow_profile=export_taxpayer_profile().model_copy(update={"activity_start_date": activity_start}),
            export_ports=modelo_export_ports_for_test(bucket_id=bucket_id),
            clock=datetime(_FILING_YEAR + 1, 1, 20, 12, 0, tzinfo=UTC),
            operation=operation,
        )
    assert result.modelo == "130"
    assert result.period == Period.from_year_and_code(_FILING_YEAR, period)
    written = output_path.read_bytes()
    assert result.byte_size == len(written)
    return result.resolved_result_disposition, written


@pytest.mark.parametrize(
    ("period", "activity_start", "expected"),
    [
        pytest.param("4T", date(_FILING_YEAR, 10, 1), ResultDisposition.NEGATIVA, id="fourth-quarter-negativa"),
        pytest.param(
            "3T", date(_FILING_YEAR, 7, 1), ResultDisposition.RESULTADO_A_DEDUCIR, id="third-quarter-a-deducir"
        ),
    ],
)
def test_negative_m130_result_exports_the_quarter_disposition_in_tipo_de_declaracion(
    isolated_backend: None,
    tmp_path: Path,
    period: str,
    activity_start: date,
    expected: ResultDisposition,
) -> None:
    disposition, written = _export_negative_m130(tmp_path, period=period, activity_start=activity_start)
    layout = _m130_layout(period)
    tipo_declaracion = _field_slice(layout, _producer_field(layout, FilingProducerKey.FILING_RESULT_DISPOSITION))
    resultado = _field_slice(layout, _casilla_field(layout, _M130_RESULT_CASILLA))

    assert disposition is expected
    # The result casilla, located by the same layout walk, proves the slice is
    # aligned with the emitted record and that the exported result is negative.
    assert written[resultado].decode("ascii") == "N0000000000005000"
    assert written[tipo_declaracion].decode("ascii") == expected.value
