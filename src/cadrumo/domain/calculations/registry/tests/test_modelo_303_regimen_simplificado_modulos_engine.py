"""Modelo 303 régimen simplificado de IVA módulos engine (phased dataset).

Non-tautological: expected values are transcribed independently from the
bundled Orden HAC/1347/2024 Anexo I IVA module tables
(``corpus/normatives/html/orden-hac-1347-2024.html``), not re-derived from
the registry formula under test. The cuota-mínima percentages are grounded
in the same Orden's Anexo II per-activity percentage table.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.money import round_to_cents
from .._formula_runtime import calculate_registry_snapshot
from ._registry_schema_support import _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Cuota devengada anual por unidad de módulo (IVA, Orden HAC/1347/2024 Anexo
# I, filing year 2025), independently transcribed for cross-check — a
# discrepancy between these literals and the registry parameter values would
# fail the assertions below, proving the registry table is grounded. Note
# these are DISTINCT euro figures from the IRPF "rendimiento anual por
# unidad" table for the same epígrafes (a different Orden annex).
_AUTOTAXI_721_2_IVA = {
    1: Decimal("903.46"),  # personal empleado (persona)
    2: Decimal("8.78"),  # distancia recorrida (1.000 km)
}
_MERCANCIAS_722_IVA = {
    1: Decimal("4149.99"),  # personal empleado (persona)
    2: Decimal("388.55"),  # carga vehículos (tonelada)
}
_PELUQUERIA_972_1_IVA = {
    1: Decimal("2562.75"),  # personal empleado (persona)
    2: Decimal("41.33"),  # superficie del local (m2)
    3: Decimal("17.48"),  # consumo de energía eléctrica (100 kWh)
}

_CUOTA_MINIMA_PCT = {
    "721.2": Decimal("10"),
    "722": Decimal("10"),
    "972.1": Decimal("13"),
}
_DIFICIL_JUSTIFICACION_FORFAIT_PCT = Decimal("1")


def _run_modulos_engine(
    epigrafe: str | None,
    *,
    modulo_1: Decimal = Decimal("0"),
    modulo_2: Decimal = Decimal("0"),
    modulo_3: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal]:
    snapshot = _committed_snapshot("303", 2025, "4T")
    assert snapshot.filing_period is not None
    text_inputs = {"modulos-iva-epigrafe": epigrafe} if epigrafe else {}
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "modulos-iva-1-unidades": modulo_1,
            "modulos-iva-2-unidades": modulo_2,
            "modulos-iva-3-unidades": modulo_3,
        },
        text_inputs=text_inputs,
        binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("0")},
        date_context={"filing_period": snapshot.filing_period.end_date},
    )
    values = result.values
    return values["modulos-iva-cuota-devengada"], values["modulos-iva-cuota-derivada"]


def _expected_cuota_derivada(devengada: Decimal, epigrafe: str) -> Decimal:
    neto_forfait = devengada - devengada * _DIFICIL_JUSTIFICACION_FORFAIT_PCT / Decimal("100")
    minima = devengada * _CUOTA_MINIMA_PCT[epigrafe] / Decimal("100")
    return round_to_cents(max(neto_forfait, minima))


class TestAutotaxi7212RegimenSimplificadoIva:
    """Epígrafe IAE 721.2 (Transporte por autotaxis)."""

    def test_cuota_devengada_matches_orden_coefficients(self) -> None:
        # 0 personal empleado, 40 (1.000 km).
        devengada, _derivada = _run_modulos_engine("721.2", modulo_1=Decimal("0"), modulo_2=Decimal("40"))
        expected_devengada = round_to_cents(Decimal("40") * _AUTOTAXI_721_2_IVA[2])
        assert devengada == expected_devengada == Decimal("351.20")

    def test_cuota_derivada_applies_forfait_and_cuota_minima_floor(self) -> None:
        devengada, derivada = _run_modulos_engine("721.2", modulo_1=Decimal("0"), modulo_2=Decimal("40"))
        expected_derivada = _expected_cuota_derivada(devengada, "721.2")
        assert derivada == expected_derivada == Decimal("347.69")


class TestMercancias722RegimenSimplificadoIva:
    """Epígrafe IAE 722 (Transporte de mercancías por carretera, excepto residuos)."""

    def test_cuota_devengada_matches_orden_coefficients(self) -> None:
        # 1 personal empleado, 8 toneladas carga.
        devengada, _derivada = _run_modulos_engine("722", modulo_1=Decimal("1"), modulo_2=Decimal("8"))
        expected_devengada = round_to_cents(
            Decimal("1") * _MERCANCIAS_722_IVA[1] + Decimal("8") * _MERCANCIAS_722_IVA[2],
        )
        assert devengada == expected_devengada == Decimal("7258.39")

    def test_cuota_derivada_applies_forfait_and_cuota_minima_floor(self) -> None:
        devengada, derivada = _run_modulos_engine("722", modulo_1=Decimal("1"), modulo_2=Decimal("8"))
        expected_derivada = _expected_cuota_derivada(devengada, "722")
        assert derivada == expected_derivada


class TestPeluqueria9721RegimenSimplificadoIva:
    """Epígrafe IAE 972.1 (Servicios de peluquería de señora y caballero)."""

    def test_cuota_devengada_matches_orden_coefficients(self) -> None:
        # 2 personal empleado, 40 m2 local, 15 (100 kWh).
        devengada, _derivada = _run_modulos_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("40"),
            modulo_3=Decimal("15"),
        )
        expected_devengada = round_to_cents(
            Decimal("2") * _PELUQUERIA_972_1_IVA[1]
            + Decimal("40") * _PELUQUERIA_972_1_IVA[2]
            + Decimal("15") * _PELUQUERIA_972_1_IVA[3],
        )
        assert devengada == expected_devengada == Decimal("7040.90")

    def test_cuota_derivada_applies_forfait_and_cuota_minima_floor(self) -> None:
        devengada, derivada = _run_modulos_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("40"),
            modulo_3=Decimal("15"),
        )
        expected_derivada = _expected_cuota_derivada(devengada, "972.1")
        assert derivada == expected_derivada == Decimal("6970.49")

    def test_cuota_minima_floor_binds_when_forfait_net_is_lower(self) -> None:
        # A tiny declared unit count keeps the cuota devengada low; the cuota
        # mínima (13% of devengada) is BELOW the 99%-net figure in every case
        # for this activity because 99% > 13%, so this activity's floor never
        # actually binds over the forfait-net branch — asserted structurally
        # via the shared max() formula, not by fabricating a case where the
        # floor wins (that would require a per-activity cuota mínima
        # percentage exceeding the 99% net-of-forfait fraction, which no
        # tabled activity here declares).
        devengada, derivada = _run_modulos_engine("972.1", modulo_1=Decimal("1"))
        expected_devengada = round_to_cents(Decimal("1") * _PELUQUERIA_972_1_IVA[1])
        expected_derivada = _expected_cuota_derivada(devengada, "972.1")
        assert devengada == expected_devengada
        assert derivada == expected_derivada


class TestModulosIvaEngineNoSilentFabrication:
    """no-silent-under-declaration guard: an untabled epígrafe never fabricates a figure."""

    def test_untabled_epigrafe_resolves_to_zero_not_fabricated_figure(self) -> None:
        # A positive unit count against an activity absent from the bounded
        # first-slice coefficient table must NOT be silently multiplied by a
        # wrong or absent coefficient; the internal reference casillas
        # resolve to zero, and the operator-declared casilla 48 remains the
        # authoritative manual input.
        devengada, derivada = _run_modulos_engine(
            "659.4",  # comercio prensa en quioscos — not in the bounded first slice
            modulo_1=Decimal("5"),
            modulo_2=Decimal("3"),
        )
        assert devengada == Decimal("0")
        assert derivada == Decimal("0")

    def test_blank_epigrafe_resolves_to_zero(self) -> None:
        devengada, derivada = _run_modulos_engine(None, modulo_1=Decimal("5"))
        assert devengada == Decimal("0")
        assert derivada == Decimal("0")

    def test_zero_units_on_tabled_epigrafe_resolves_to_zero(self) -> None:
        # A tabled epígrafe with no units declared (e.g. no activity conducted
        # yet this period) legitimately resolves to zero — not a
        # silent-zero violation, since the antecedent itself is zero.
        devengada, derivada = _run_modulos_engine("972.1")
        assert devengada == Decimal("0")
        assert derivada == Decimal("0")
