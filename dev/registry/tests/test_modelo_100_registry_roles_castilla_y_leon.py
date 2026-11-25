"""Modelo 100 Castilla y Leon semantic-role registry tests."""

from __future__ import annotations

import pytest

from .authored_edition_support import authored_revisions
from .modelo_100_registry_support import (
    AUTONOMIC_DEDUCTION_ART_77_REF,
    modelo_100_revision,
    modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CASTILLA_Y_LEON_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "castilla_y_leon_res")
_CASTILLA_Y_LEON_PENDING_APPLICATION_ROLE = "irpf_deduccion_castilla_y_leon_importe_pendiente_aplicacion"
_LEGACY_CASTILLA_Y_LEON_YEAR_PENDING_ROLE = "irpf_deduccion_castilla_y_leon_generado_2022_pendiente"
_M100_EDITIONS = tuple(revision.valid_from.year for revision in authored_revisions("100"))
# Printed labels in authoring order; pairing by position makes a newly authored edition fail
# here until its official label is recorded.
_CL11EA14_LABELS = (
    "Importe generado en 2019 pendiente de aplicación",
    "Importe generado en 2020 pendiente de aplicación",
    "Importe generado en 2021 pendiente de aplicación",
    "Importe generado en 2022 pendiente de aplicación",
    "Importe generado en 2022 pendiente de aplicación",
    "Importe generado en 2022 pendiente de aplicación",
)
_EXPECTED_CL11EA14_LABELS = dict(zip(_M100_EDITIONS, _CL11EA14_LABELS, strict=True))
# The edition whose official CL11 schedule lists the 2020, 2021 and 2022 generated amounts.
_CL11_SCHEDULE_EDITION = _M100_EDITIONS[3]


@pytest.mark.parametrize("filing_year", sorted(_EXPECTED_CL11EA14_LABELS))
def test_modelo_100_castilla_y_leon_cl11ea14_is_pending_application_slot(filing_year: int) -> None:
    revision = modelo_100_revision(filing_year)
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "0983")

    assert casilla.label == _EXPECTED_CL11EA14_LABELS[filing_year]
    assert tuple(casilla.section) == _CASTILLA_Y_LEON_DEDUCTION_SECTION
    assert casilla.semantic_role == _CASTILLA_Y_LEON_PENDING_APPLICATION_ROLE
    assert casilla.semantic_role != _LEGACY_CASTILLA_Y_LEON_YEAR_PENDING_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_castilla_y_leon_pending_application_role_covers_official_cl11_schedule() -> None:
    revision = modelo_100_snapshot(_CL11_SCHEDULE_EDITION).revision
    expected_ids = {"0981", "0982", "0983", "0998", "0999"}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_ids}

    assert set(casillas_by_id) == expected_ids
    assert {casilla.semantic_role for casilla in casillas_by_id.values()} == {_CASTILLA_Y_LEON_PENDING_APPLICATION_ROLE}
    assert [casillas_by_id[casilla_id].label for casilla_id in sorted(expected_ids)] == [
        "Importe generado en 2020 pendiente de aplicación",
        "Importe generado en 2021 pendiente de aplicación",
        "Importe generado en 2022 pendiente de aplicación",
        "Importe generado en 2021 pendiente de aplicación",
        "Importe generado en 2022 pendiente de aplicación",
    ]
