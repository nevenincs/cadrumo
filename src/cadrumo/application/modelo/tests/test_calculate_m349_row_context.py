"""Registered calculation validates Modelo 349 row context before publication."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.row_models import (
    Modelo349CountryPrefixContextError,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..calculate_input import ModeloCalculateDetailRowsError, _validate_detail_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    revision = published_snapshot("349", filing_year=2026, period="1T").revision
    bucket_id = "9c4acfdc-abb7-4206-8755-1d8c027b6114"
    now = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id, modelo="349", filing_year=2026, period=period, revision_id=revision.id
        ),
        bucket_id=bucket_id,
        modelo=Modelo("349"),
        filing_year=2026,
        period=period,
        revision_id=revision.id,
        name="M349 contextual rows",
        created_at=now,
        updated_at=now,
    )


def test_application_rejects_post_transition_gb_ordinary_row() -> None:
    row = Modelo349OperadorRow(
        codigo_pais="GB",
        nif_comunitario="GB123456789",
        razon_social="UK trader",
        clave_operacion="E",
        importe=Decimal("25.00"),
    )
    with bundled_indexed_authority().operation() as operation, pytest.raises(Modelo349CountryPrefixContextError):
        _validate_detail_rows((row,), work_unit=_unit(), operation=operation)


def test_application_rejects_country_specific_nif_format() -> None:
    row = Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="DE123",
        razon_social="EU trader",
        clave_operacion="E",
        importe=Decimal("25.00"),
    )
    with bundled_indexed_authority().operation() as operation, pytest.raises(ModeloCalculateDetailRowsError) as raised:
        _validate_detail_rows((row,), work_unit=_unit(), operation=operation)
    assert raised.value.context == {"nif": "DE123", "pais": "DE"}


def test_application_accepts_supported_rectification_context() -> None:
    with bundled_indexed_authority().operation() as operation:
        row = Modelo349RectificacionRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="EU trader",
            clave_operacion="E",
            ejercicio="2025",
            periodo="4T",
            base_rectificada=Decimal("25.00"),
            base_anterior=Decimal("30.00"),
        )
        _validate_detail_rows((row,), work_unit=_unit(), operation=operation)
