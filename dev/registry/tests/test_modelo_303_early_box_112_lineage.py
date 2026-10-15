"""The early 2026 transport row 112 is not a printed-form continuation."""

from __future__ import annotations

from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_cross_revision_lineage_origin import role_exempt_occurrences

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EARLY_REVISION = "2026-hasta-01-y-1t"
_LATER_REVISION = "2026-y-siguientes"
_CASILLA_ID = "112"


@cache
def _modelo() -> ModeloDefinition:
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", "303"))


def _row(revision_id: str) -> CasillaDefinition:
    revision = _modelo().revisions[revision_id]
    return next(casilla for casilla in revision.casillas if str(casilla.id) == _CASILLA_ID)


def test_early_transport_row_is_absent_while_later_box_112_is_active() -> None:
    modelo = _modelo()
    early = _row(_EARLY_REVISION)
    later = _row(_LATER_REVISION)

    assert str(early.continuidad_id) == "dr303-112"
    assert early.semantic_role == "m303_pago_a_cuenta_deposito_distinto_del_aduanero_no_aplicable"
    assert early.continuidad_origin is CasillaLineageOrigin.NOT_ON_FORM
    assert early.continuidad_evidence is not None
    assert early.continuidad_evidence.strip() != ""
    assert early.constraints is not None
    assert early.constraints.min_value == Decimal("0")
    assert early.constraints.max_value == Decimal("0")
    assert (_EARLY_REVISION, _CASILLA_ID) not in role_exempt_occurrences(modelo)

    assert str(later.continuidad_id) == "dr303-112"
    assert later.semantic_role == "m303_pago_a_cuenta_deposito_distinto_del_aduanero"
    assert later.continuidad_origin is CasillaLineageOrigin.NEW_ON_FORM
    assert later.continuidad_evidence is not None
    assert later.continuidad_evidence.strip() != ""
