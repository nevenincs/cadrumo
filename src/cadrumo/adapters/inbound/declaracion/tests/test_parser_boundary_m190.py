"""Modelo 190 parser boundary corpus tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId
from .....domain.calculations.registry.tests.authored_editions import revision_covering
from ..parser import parse_declaracion
from .parser_boundary_support import (
    MODELO_190_SYNTHETIC_FIXTURE,
    expected_casilla_values,
    expected_period,
    specimen_period,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]

_SPECIMEN_PERIOD = specimen_period(MODELO_190_SYNTHETIC_FIXTURE)

# The three amounts the fixture prints. They are DISTINCT from one another
# because the specimen this replaced printed the sanitiser's single redaction
# constant into both money boxes, so a target that crossed
# ``percepciones-total`` with ``retenciones-total`` read the same number and
# this assertion held anyway.
_M190_EXPECTED_VALUES: dict[CasillaId, Decimal] = expected_casilla_values(
    {
        "decl.total-percepciones": Decimal("1"),
        "decl.percepciones-total": Decimal("12345.60"),
        "decl.retenciones-total": Decimal("1851.84"),
    },
)


def test_parser_extracts_modelo_190_targets_from_declaration_copy() -> None:
    filing = parse_declaracion(
        MODELO_190_SYNTHETIC_FIXTURE,
        modelo_override="190",
        año_override=_SPECIMEN_PERIOD.filing_year,
        period_override="0A",
    )

    assert filing.modelo == "190"
    assert filing.period == expected_period(_SPECIMEN_PERIOD.filing_year, "0A")
    assert filing.tax_id == "Y0001006P"
    assert {value.casilla_id: value.printed_value for value in filing.values} == _M190_EXPECTED_VALUES
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "190"
    assert filing.registry_snapshot_ref.revision_id == str(revision_covering("190", _SPECIMEN_PERIOD.filing_year).id)
    assert filing.registry_snapshot_ref.modelo_year == _SPECIMEN_PERIOD.filing_year
    assert filing.registry_snapshot_ref.period == "0A"
