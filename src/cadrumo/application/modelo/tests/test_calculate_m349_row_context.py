"""Registered calculation validates Modelo 349 row context before publication."""

from __future__ import annotations

from calendar import isleap
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.row_models import (
    Modelo184MemberRow,
    Modelo349CountryPrefixContextError,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..calculate_input_validation import ModeloCalculateDetailRowsError, validate_detail_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon


def _unit() -> WorkUnit:
    period = Period.from_year_and_code(_YEAR, "1T")
    revision = published_snapshot("349", filing_year=_YEAR, period="1T").revision
    bucket_id = "9c4acfdc-abb7-4206-8755-1d8c027b6114"
    now = datetime(1980, 6, 29, 12, 0, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id, modelo="349", filing_year=_YEAR, period=period, revision_id=revision.id
        ),
        bucket_id=bucket_id,
        modelo=Modelo("349"),
        filing_year=_YEAR,
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
        validate_detail_rows((row,), work_unit=_unit(), operation=operation)


def test_application_rejects_country_specific_nif_format() -> None:
    row = Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="DE123",
        razon_social="EU trader",
        clave_operacion="E",
        importe=Decimal("25.00"),
    )
    with bundled_indexed_authority().operation() as operation, pytest.raises(ModeloCalculateDetailRowsError) as raised:
        validate_detail_rows((row,), work_unit=_unit(), operation=operation)
    assert raised.value.context == {"nif": "DE123", "pais": "DE"}


def test_application_accepts_supported_rectification_context() -> None:
    with bundled_indexed_authority().operation() as operation:
        row = Modelo349RectificacionRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="EU trader",
            clave_operacion="E",
            ejercicio=str(_YEAR - 1),
            periodo="4T",
            base_rectificada=Decimal("25.00"),
            base_anterior=Decimal("30.00"),
        )
        validate_detail_rows((row,), work_unit=_unit(), operation=operation)


@pytest.mark.parametrize(
    ("filing_year", "refused"), [(year, not isleap(year)) for year in filing_year_envelope().years]
)
def test_a_member_day_count_is_held_to_the_days_of_its_own_year(filing_year: int, refused: bool) -> None:
    row = Modelo184MemberRow(
        nif="33333333C", porcentaje=Decimal("100"), importe=Decimal("0"), clave="D", dias_miembro=366
    )
    unit = _unit().model_copy(update={"filing_year": filing_year})
    with bundled_indexed_authority().operation() as operation:
        if refused:
            with pytest.raises(ModeloCalculateDetailRowsError) as raised:
                validate_detail_rows((row,), work_unit=unit, operation=operation)
            assert raised.value.context == {"days": "366", "filing_year": str(filing_year)}
        else:
            validate_detail_rows((row,), work_unit=unit, operation=operation)
