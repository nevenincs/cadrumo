"""Modelo 190 perceptor EJERCICIO DEVENGO reaches the fichero as the 2025 design prints it.

Synthetic rows go through ``build_draft`` and ``export_draft`` and the written
bytes are read back as records of 500 positions. The expectations come from the
printed design (aeat-dr-190-2025; positions 1-based, here sliced 0-based):

- Position 78 is the CLAVE DE PERCEPCION, 79-80 the SUBCLAVE and 5-8 the EJERCICIO.
- Positions 148-151 are the EJERCICIO DEVENGO: "Únicamente se cumplimentará este
  campo" for cantidades satisfechas "en concepto de atrasos cuyo devengo o
  exigibilidad corresponda a ejercicios anteriores", where "se reflejarán en este
  campo las cuatro cifras del ejercicio de devengo", and for reintegros. A numeric
  field without content is filled with zeros.
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
_PREFIX = "modelo-190-perceptor-row-"


def _row(nif: str, name: str, **fields: str) -> dict[str, ModeloInputScalar]:
    """One clave A subclave 01 salary row of 1000.00 with 150.00 withheld unless overridden."""
    values: dict[str, ModeloInputScalar] = {
        "nif": nif,
        "name": name,
        "clave": "A",
        "subclave": "01",
        "percibido-dinerario": Decimal("1000.00"),
        "retencion-practicada": Decimal("150.00"),
        **fields,
    }
    return values


def _export(operation: PinnedAuthorityOperation, tmp_path: Path, rows: list[dict[str, ModeloInputScalar]]) -> list[str]:
    """Export the rows and return the perceptor records of the written fichero."""
    period = Period.from_year_and_code(_YEAR, "0A")
    provider = build_runtime_schema_provider(filing_year=_YEAR, period=period, modelos=("190",), operation=operation)
    inputs: dict[str, ModeloInputValue] = {
        "decl.total-percepciones": Decimal(len(rows)),
    }
    row_sets: dict[str, dict[str, ModeloInputScalar]] = {}
    for index, row in enumerate(rows, start=1):
        for field, value in row.items():
            row_sets.setdefault(f"{_PREFIX}{field}", {})[str(index)] = value
    inputs.update(row_sets)
    draft = build_draft(
        modelo="190",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs=inputs,
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    output_path = tmp_path / "modelo-190-2025.txt"
    export_draft(
        draft,
        output_path=output_path,
        producer_snapshot=m151_producer_snapshot().model_copy(update={"modelo": Modelo("190")}),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
        schema_provider=provider,
    )
    text = output_path.read_bytes().decode("iso-8859-1")
    assert len(text) == _RECORD_LENGTH * (len(rows) + 1)
    return [text[start : start + _RECORD_LENGTH] for start in range(_RECORD_LENGTH, len(text), _RECORD_LENGTH)]


def test_an_ordinary_row_has_no_devengo_year_and_an_atraso_carries_the_earlier_year(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    ordinary, atraso = _export(
        operation,
        tmp_path,
        [
            _row("12345678Z", "PERCEPTOR ORDINARIO"),
            _row("X0001502F", "PERCEPTOR ATRASO", **{"ejercicio-devengo": "2024"}),
        ],
    )
    assert ordinary[147:151] == "0000"
    assert atraso[147:151] == "2024"
    for record in (ordinary, atraso):
        assert record[0:1] == "2"
        assert record[4:8] == "2025"
        assert record[77:78] == "A"
        assert record[78:80] == "01"


@pytest.mark.parametrize("year", ["2025", "2026"])
def test_a_positive_atraso_must_name_an_exercise_before_the_declaration(
    operation: PinnedAuthorityOperation, tmp_path: Path, year: str
) -> None:
    with pytest.raises(FilingExportValidationError, match="earlier than the declaration year"):
        _export(operation, tmp_path, [_row("12345678Z", "PERCEPTOR", **{"ejercicio-devengo": year})])
    assert not (tmp_path / "modelo-190-2025.txt").exists()
