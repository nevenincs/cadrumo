"""Modelo 193 perceptor PENDIENTE and EJERCICIO DEVENGO reach the fichero as the 2025 design prints them.

Synthetic rows go through ``build_draft`` and ``export_draft`` and the written
bytes are read back as records of 500 positions (the design's record length;
the layout declares no line ending). The expectations come from the printed
design (aeat-dr-193-2025, position 1-based, here sliced 0-based):

- Position 92 is the CLAVE DE PERCEPCION and 5-8 the EJERCICIO.
- Position 117 is PENDIENTE, "Solo para claves de percepción A, B o D": an "X"
  marks accrued income left unpaid because the holders did not come forward, and
  then the record carries NIF 999999999, the name VALORES PENDIENTE DE ABONO and
  an EJERCICIO DEVENGO "sin contenido".
- Positions 118-121 are the EJERCICIO DEVENGO, also only for keys A, B or D: the
  four digits of the accrual year of income paid this year for an earlier year,
  and "En ningún otro caso que no sea el descrito anteriormente se cumplimentará
  este campo". Numeric fields without content are filled with zeros.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.filing.errors import FilingExportValidationError
from ....domain.filing.protocols import ModeloInputScalar, ModeloInputValue
from ....domain.submission.models import ModeloDraftStatus
from ..draft_construction import build_draft
from ..export import export_draft
from ..runtime import ModeloOperatorProfile, build_runtime_schema_provider
from .export_support import m151_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2025
_RECORD_LENGTH = 500
_PREFIX = "modelo-193-perceptor-row-"
_PENDING_NIF = "999999999"
_PENDING_NAME = "VALORES PENDIENTE DE ABONO"


def _row(nif: str, name: str, **fields: str) -> dict[str, ModeloInputScalar]:
    """One perceptor row: a key B coupon of 1000.00 with 190.00 withheld unless overridden."""
    values: dict[str, ModeloInputScalar] = {
        "nif": nif,
        "name": name,
        "clave": "B",
        "percibido": Decimal("1000.00"),
        "base": Decimal("1000.00"),
        "retencion": Decimal("190.00"),
        **fields,
    }
    return values


def _export(operation: PinnedAuthorityOperation, tmp_path: Path, rows: list[dict[str, ModeloInputScalar]]) -> list[str]:
    """Export the rows and return the perceptor records of the written fichero."""
    period = Period.from_year_and_code(_YEAR, "0A")
    provider = build_runtime_schema_provider(filing_year=_YEAR, period=period, modelos=("193",), operation=operation)
    inputs: dict[str, ModeloInputValue] = {
        "decl.gastos-total": Decimal("0"),
        "modelo-193-perceptores-anual": Decimal(len(rows)),
        "modelo-193-perceptor-rows-base-total": sum((Decimal(str(row["base"])) for row in rows), Decimal(0)),
        "modelo-193-perceptor-rows-retenciones-total": sum(
            (Decimal(str(row["retencion"])) for row in rows), Decimal(0)
        ),
        "modelo-193-retenciones-ingresadas": Decimal("0"),
    }
    row_sets: dict[str, dict[str, ModeloInputScalar]] = {}
    for index, row in enumerate(rows, start=1):
        for field, value in row.items():
            row_sets.setdefault(f"{_PREFIX}{field.replace('_', '-')}", {})[str(index)] = value
    inputs.update(row_sets)
    draft = build_draft(
        modelo="193",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs=inputs,
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    output_path = tmp_path / "modelo-193-2025.txt"
    export_draft(
        draft,
        output_path=output_path,
        producer_snapshot=m151_producer_snapshot().model_copy(update={"modelo": Modelo("193")}),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
        schema_provider=provider,
    )
    text = output_path.read_bytes().decode("iso-8859-1")
    assert len(text) == _RECORD_LENGTH * (len(rows) + 1)
    return [text[start : start + _RECORD_LENGTH] for start in range(_RECORD_LENGTH, len(text), _RECORD_LENGTH)]


def test_pending_ordinary_and_atraso_rows_carry_their_pendiente_and_devengo_bytes(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    pending, ordinary, atraso = _export(
        operation,
        tmp_path,
        [
            _row(_PENDING_NIF, _PENDING_NAME, pendiente="X"),
            _row("12345678Z", "PERCEPTOR ORDINARIO"),
            _row("X0001502F", "PERCEPTOR ATRASO", ejercicio_devengo="2024"),
        ],
    )
    assert pending[116:117] == "X"
    assert pending[117:121] == "0000"
    assert pending[17:26] == _PENDING_NIF
    assert pending[35:75] == _PENDING_NAME.ljust(40)
    assert ordinary[116:117] == " "
    assert ordinary[117:121] == "0000"
    assert atraso[116:117] == " "
    assert atraso[117:121] == "2024"
    for record in (pending, ordinary, atraso):
        assert record[0:1] == "2"
        assert record[4:8] == "2025"
        assert record[91:92] == "B"


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        pytest.param({"pendiente": "Y"}, "pending mark must be blank or X", id="pendiente-not-x"),
        pytest.param({"pendiente": "X", "clave": "C"}, "keys A, B and D", id="pendiente-on-other-key"),
        pytest.param({"ejercicio_devengo": "2024", "clave": "C"}, "keys A, B and D", id="devengo-on-other-key"),
        pytest.param({"pendiente": "X", "ejercicio_devengo": "2024"}, "pending row has no devengo", id="x-with-year"),
        pytest.param({"ejercicio_devengo": "2025"}, "earlier than the declaration year", id="same-year"),
        pytest.param({"ejercicio_devengo": "2026"}, "earlier than the declaration year", id="later-year"),
    ],
)
def test_contradictory_pendiente_or_devengo_refuses_the_fichero(
    operation: PinnedAuthorityOperation, tmp_path: Path, fields: dict[str, str], reason: str
) -> None:
    with pytest.raises(FilingExportValidationError, match=reason):
        _export(operation, tmp_path, [_row("12345678Z", "PERCEPTOR", **fields)])
    assert not (tmp_path / "modelo-193-2025.txt").exists()
