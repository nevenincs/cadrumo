"""A return outside estimacion directa exports no direct-estimation activity block.

The Modelo 100 design places casilla 0224 (rendimiento neto, ``E1RN``) and the
rest of the direct-estimation block inside ``ActividadEstDirecta``, one
occurrence per activity determined under estimacion directa. A taxpayer with no
such activity has no occurrence, so the block's casillas are not stated at all.
The calculation still carries 0224 as a structural zero, so its dependents add
up over no activity; these tests prove that zero never reaches the exported
bytes as a stated value.

Real encrypted store, real registered operations, real calculate, verify and export.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision import CalculationRevision

from .m130_m100_annual_support import BUCKET_ID, import_official_quarter_observation, seed_prior_year_m100
from .renta_persona_support import (
    PAYER_A,
    Persona,
    calculate_annual,
    record_certificate,
    register_refund_account,
    seed_profile,
    verify_and_export,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

__all__ = ["secure_objects"]

_DIRECT_BLOCK_TAG = "ActividadEstDirecta"
_RENDIMIENTO_NETO_TAG = "E1RN"
_RENDIMIENTO_NETO_CASILLA = validated_casilla_id("0224")

_SALARIED = Persona(categories="trabajo")
_OBJETIVA = Persona(categories="trabajo,actividad_economica", regime="objetiva")

# The objetiva taxpayer files its four Modelo 131 quarters: an original return each (no earlier
# result, casilla 14), restating the annual módulos estimate (casilla 01) and paying casilla 15.
_M131_QUARTERS = ("1T", "2T", "3T", "4T")
_M131_FILED_QUARTER = {
    validated_casilla_id("01"): Decimal("5400.00"),
    validated_casilla_id("14"): Decimal("0"),
    validated_casilla_id("15"): Decimal("27.00"),
}


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


def _local_names(payload: bytes) -> set[str]:
    root = DefusedElementTree.fromstring(payload)
    return {element.tag.rsplit("}", 1)[-1] for element in root.iter()}


def _export(
    persona: Persona, objects: SecureObjectRepository, directory: Path, operation: PinnedAuthorityOperation
) -> tuple[CalculationRevision, bytes]:
    seed_profile(persona)
    seed_prior_year_m100(objects)
    record_certificate(
        operation,
        directory=directory,
        payer=PAYER_A,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion="3000.00",
        importe_integro="24000.00",
    )
    if persona.regime == "objetiva":
        for period in _M131_QUARTERS:
            import_official_quarter_observation(
                objects, modelo="131", period=period, casilla_values=_M131_FILED_QUARTER
            )
    register_refund_account(objects)
    annual = calculate_annual(objects)
    return annual, verify_and_export(annual, objects, directory / "modelo-100.xml", persona)


@pytest.mark.parametrize("persona", [_SALARIED, _OBJETIVA], ids=["salaried", "objetiva"])
def test_a_return_outside_estimacion_directa_states_no_direct_estimation_block(
    persona: Persona,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    annual, payload = _export(persona, secure_objects, tmp_path, operation)

    # The calculation's structural zero is what the exported bytes must not state.
    assert Decimal(annual.casilla_values[_RENDIMIENTO_NETO_CASILLA]) == Decimal("0")
    names = _local_names(payload)
    assert "DatosEconomicos" in names
    assert _DIRECT_BLOCK_TAG not in names
    assert _RENDIMIENTO_NETO_TAG not in names
