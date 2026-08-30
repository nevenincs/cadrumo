"""Every ModeloDetailRow kind refuses when declared against the wrong modelo.

Before this gate existed, a detail row declared against a mismatched work
unit was silently persisted into that revision's ``detail_rows`` while
contributing to no figure -- a taxpayer-declared row that appeared to exist
yet affected nothing, with no advisory anywhere. Each kind is proven
separately because the whole finding is that they previously diverged: M210
already refused, M349 silently dropped the aggregation, and M184/M232/M347
had no check at all.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.row_models import Modelo184MemberRow, Modelo210AgrupacionRentaRow, Modelo232VinculadaRow, Modelo347ContraparteRow, Modelo349OperadorRow, Modelo349RectificacionRow, ModeloDetailRow
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.errors import ModeloError
from .._calculation_modelo_adjustments import require_detail_rows_declared_for_their_owning_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "detail-row-membership-bucket"
_CLOCK = datetime(2026, 1, 10, tzinfo=UTC)
_REVISION_ID = "a" * 64


def _work_unit(*, modelo: str) -> WorkUnit:
    period = Period.from_year_and_code(2025, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=modelo, filing_year=2025, period=period, revision_id=_REVISION_ID
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=2025,
        period=period,
        revision_id=_REVISION_ID,
        name=f"{modelo}-2025-1T",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _m184_row() -> Modelo184MemberRow:
    return Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("100"), importe=Decimal("10000"), clave="D")


def _m232_row() -> Modelo232VinculadaRow:
    return Modelo232VinculadaRow(
        nif="A12345671",
        nombre="Vinculada SA",
        pais="ES",
        tipo_vinculacion="A",
        tipo_operacion="01",
        metodo="1A",
        importe=Decimal("125000"),
    )


def _m349_operador_row() -> Modelo349OperadorRow:
    return Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="DE123456789",
        razon_social="ALEMAN GMBH",
        clave_operacion="E",
        importe=Decimal("1500.00"),
    )


def _m349_rectificacion_row() -> Modelo349RectificacionRow:
    return Modelo349RectificacionRow(
        codigo_pais="DE",
        nif_comunitario="DE123456789",
        razon_social="ALEMAN GMBH",
        clave_operacion="E",
        ejercicio="2025",
        periodo="2T",
        base_rectificada=Decimal("1100.00"),
        base_anterior=Decimal("1000.00"),
    )


def _m347_row() -> Modelo347ContraparteRow:
    return Modelo347ContraparteRow(nif="12345678A", importe_Q1=Decimal("3005.07"))


def _m210_row() -> Modelo210AgrupacionRentaRow:
    from ....core import M210PayerMode

    return Modelo210AgrupacionRentaRow(
        source_id="manual-renta-jan",
        tipo_renta_code="01",
        importe=Decimal("100.00"),
        tipo_gravamen=Decimal("0.24"),
        pagador_mode=M210PayerMode.SINGLE_PAYER,
        pagador_id="ES-PAGADOR-1",
        deriva_de_bien_derecho=True,
        bien_derecho_id="ES-INMUEBLE-1",
    )


@pytest.mark.parametrize(
    ("row_factory", "owning_modelo"),
    [
        (_m184_row, "184"),
        (_m232_row, "232"),
        (_m349_operador_row, "349"),
        (_m349_rectificacion_row, "349"),
        (_m347_row, "347"),
        (_m210_row, "210"),
    ],
)
def test_each_detail_row_kind_refuses_against_the_wrong_modelo(
    row_factory: Callable[[], ModeloDetailRow], owning_modelo: str
) -> None:
    """A detail row declared against a mismatched work unit refuses, not persists silently."""
    row = row_factory()
    work_unit = _work_unit(modelo="100")

    with pytest.raises(ModeloError) as exc_info:
        require_detail_rows_declared_for_their_owning_modelo(work_unit=work_unit, detail_rows=(row,))

    assert exc_info.value.context is not None
    assert exc_info.value.context["row_type"] == type(row).__name__
    assert exc_info.value.context["owning_modelo"] == owning_modelo
    assert exc_info.value.context["work_unit_modelo"] == "100"


@pytest.mark.parametrize(
    ("row_factory", "owning_modelo"),
    [
        (_m184_row, "184"),
        (_m232_row, "232"),
        (_m349_operador_row, "349"),
        (_m349_rectificacion_row, "349"),
        (_m347_row, "347"),
        (_m210_row, "210"),
    ],
)
def test_each_detail_row_kind_is_admitted_for_its_own_modelo(
    row_factory: Callable[[], ModeloDetailRow], owning_modelo: str
) -> None:
    """A detail row declared against its own owning modelo raises nothing."""
    row = row_factory()
    work_unit = _work_unit(modelo=owning_modelo)

    require_detail_rows_declared_for_their_owning_modelo(work_unit=work_unit, detail_rows=(row,))
