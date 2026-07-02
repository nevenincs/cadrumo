"""Modelo 131 estimación-objetiva módulos engine (Fase 1ª + Fase 4ª, first slice).

Non-tautological: expected values are transcribed independently from the
bundled Orden HAC/1347/2024 Anexo II coefficient tables
(``corpus/normatives/html/orden-hac-1347-2024.html``), not re-derived from the
registry formula under test. The 5 por ciento reducción general is grounded
in the same Orden's disposición adicional primera. See
``2026-07-01-modelo-131-eo-modulos-engine-adr``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._formula_runtime import calculate_registry_snapshot
from ._registry_schema_support import _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Rendimiento anual por unidad antes de amortización (Orden HAC/1347/2024
# Anexo II, filing year 2025), independently transcribed for cross-check —
# a discrepancy between these literals and the registry parameter values
# would fail the assertions below, proving the registry table is grounded.
_PELUQUERIA_972_1 = {
    1: Decimal("3161.90"),  # personal asalariado (persona)
    2: Decimal("9649.47"),  # personal no asalariado (persona)
    3: Decimal("94.48"),  # superficie del local (m2)
    4: Decimal("81.88"),  # consumo de energía eléctrica (100 kWh)
}
_AUTOTAXI_721_2 = {
    1: Decimal("1346.27"),  # personal asalariado (persona)
    2: Decimal("7656.89"),  # personal no asalariado (persona)
    3: Decimal("45.08"),  # distancia recorrida (1.000 km)
}
_MERCANCIAS_722 = {
    1: Decimal("2728.59"),  # personal asalariado (persona)
    2: Decimal("10090.99"),  # personal no asalariado (persona)
    3: Decimal("126.21"),  # carga vehículos (tonelada)
}
_REDUCCION_GENERAL_2025 = Decimal("0.05")


def _run_modulos_engine(
    epigrafe: str | None,
    *,
    modulo_1: Decimal = Decimal("0"),
    modulo_2: Decimal = Decimal("0"),
    modulo_3: Decimal = Decimal("0"),
    modulo_4: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal]:
    snapshot = _committed_snapshot("131", 2025, "1T")
    text_inputs = {"modulos-epigrafe": epigrafe} if epigrafe else {}
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "modulos-1-unidades": modulo_1,
            "modulos-2-unidades": modulo_2,
            "modulos-3-unidades": modulo_3,
            "modulos-4-unidades": modulo_4,
        },
        text_inputs=text_inputs,
        date_context={"filing_period": snapshot.filing_period.end_date},
    )
    values = result.values
    return values["modulos-rendimiento-neto-previo"], values["modulos-rendimiento-neto-actividad"]


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


class TestPeluqueria9721EstimacionObjetiva:
    """Epígrafe IAE 972.1 (Servicios de peluquería de señora y caballero)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 50 m2 local, 30 (100 kWh).
        previo, _actividad = _run_modulos_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("2") * _PELUQUERIA_972_1[1]
            + Decimal("1") * _PELUQUERIA_972_1[2]
            + Decimal("50") * _PELUQUERIA_972_1[3]
            + Decimal("30") * _PELUQUERIA_972_1[4],
        )
        assert previo == expected_previo == Decimal("23153.67")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("21995.99")


class TestAutotaxi7212EstimacionObjetiva:
    """Epígrafe IAE 721.2 (Transporte por autotaxis)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 0 personal asalariado, 1 personal no asalariado (titular), 40 (1.000 km).
        previo, _actividad = _run_modulos_engine(
            "721.2",
            modulo_1=Decimal("0"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = _quantize(Decimal("1") * _AUTOTAXI_721_2[2] + Decimal("40") * _AUTOTAXI_721_2[3])
        assert previo == expected_previo == Decimal("9460.09")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "721.2",
            modulo_1=Decimal("0"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("8987.09")


class TestTransporteMercancias722EstimacionObjetiva:
    """Epígrafe IAE 722 (Transporte de mercancías por carretera)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 0 personal no asalariado, 8 toneladas carga.
        previo, _actividad = _run_modulos_engine(
            "722",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("0"),
            modulo_3=Decimal("8"),
        )
        expected_previo = _quantize(Decimal("1") * _MERCANCIAS_722[1] + Decimal("8") * _MERCANCIAS_722[3])
        assert previo == expected_previo == Decimal("3738.27")


class TestModulosEngineNoSilentFabrication:
    """no-silent-under-declaration guard: an untabled epígrafe never fabricates a figure."""

    def test_untabled_epigrafe_resolves_to_zero_not_fabricated_figure(self) -> None:
        # A large positive unit count against an activity absent from the
        # bounded first-slice coefficient table must NOT be silently
        # multiplied by a wrong or absent coefficient; the internal
        # reference casilla resolves to zero, and the operator-declared
        # casilla 01 remains the authoritative manual input (Phase 1).
        previo, actividad = _run_modulos_engine(
            "659.4",  # comercio prensa en quioscos — not in the bounded first slice
            modulo_1=Decimal("5"),
            modulo_2=Decimal("3"),
        )
        assert previo == Decimal("0")
        assert actividad == Decimal("0")

    def test_blank_epigrafe_resolves_to_zero(self) -> None:
        previo, actividad = _run_modulos_engine(None, modulo_1=Decimal("5"))
        assert previo == Decimal("0")
        assert actividad == Decimal("0")

    def test_zero_units_on_tabled_epigrafe_resolves_to_zero(self) -> None:
        # A tabled epígrafe with no units declared (e.g. no activity conducted
        # yet this period) legitimately resolves to zero — not a silent-zero
        # violation, since the antecedent itself is zero.
        previo, actividad = _run_modulos_engine("972.1")
        assert previo == Decimal("0")
        assert actividad == Decimal("0")
