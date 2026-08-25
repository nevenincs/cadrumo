"""Modelo 131 estimación-objetiva módulos engine — 2026 roll-forward parity.

The 2026 revision replicates the 2025 revision's four-fase módulos engine
(coefficient table, casillas, formulas, verification predicates) because the
bundled Orden HAC/1425/2025 Anexo II reproduces the same euro figures as Orden
HAC/1347/2024 for every currently-tabled activity
(confirmed by a full numeric diff of the corpus text at authoring time: every
signos/módulos rendimiento figure, every índice-corrector-de-exceso cuantía,
the reducción general, and the incentivos-al-empleo tramos/incremento
coefficients are byte-identical between the two Ordenes).

Non-tautological: the expected figures below are transcribed independently
from the bundled ``corpus/normatives/html/orden-hac-1425-2025.html`` — the
2026 filing year's own applicable Orden — and the fase 2ª/3ª/4ª arithmetic is
reproduced by an independent helper (not the registry formula under test)
before being compared against the engine's output.

See Also:
    :mod:`~domain.calculations.registry._formula_runtime_m131`
        Runtime evaluators for the M131 table-driven módulos operations.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Public registry calculation entry point exercised by the parity cases.
    :mod:`~domain.calculations.registry.tests.test_modelo_131_modulos_engine`
        Baseline 2025 módulos-engine behavior this roll-forward must preserve.
    ``src/cadrumo/_data/registry/aeat/modelos/131/revisions/2026/formulas/0003-cmodulos-epigrafe__cmodulos-rendimiento-neto-actividad.toml``
        Registry-authored 2026 formula chain under test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core import RegistryAuthorityGrade
from .....core.money import round_to_cents
from ..formula_runtime import calculate_registry_snapshot
from ._registry_schema_support import _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Rendimiento anual por unidad antes de amortización (Orden HAC/1425/2025
# Anexo II, filing year 2026), independently transcribed from the 2026 Orden
# corpus text for cross-check — a discrepancy between these literals and the
# registry parameter values would fail the assertions below, proving the 2026
# coefficient table is grounded (not merely copy-pasted from 2025 without
# re-verification).
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

_REDUCCION_GENERAL_2026 = Decimal("0.05")

# Fase 2ª — coeficiente por tramos del número de unidades del módulo
# "personal asalariado" (Orden HAC/1425/2025 Anexo II, instrucción 2.2.a),
# independently transcribed for cross-check against the registry's
# m131-modulos-coeficiente-tramos-asalariados-2026 bracket_table parameter.
_COEFICIENTE_INCREMENTO_ASALARIADOS = Decimal("0.40")
_TRAMOS_ASALARIADOS = (
    (Decimal("0"), Decimal("1.00"), Decimal("0.10")),
    (Decimal("1.00"), Decimal("3.00"), Decimal("0.15")),
    (Decimal("3.00"), Decimal("5.00"), Decimal("0.20")),
    (Decimal("5.00"), Decimal("8.00"), Decimal("0.25")),
    (Decimal("8.00"), None, Decimal("0.30")),
)

# Fase 3ª — índice corrector de exceso (Orden HAC/1425/2025 Anexo II,
# instrucción 2.3.b.3): índice 1,30 applied to the excess over the tabled
# cuantía. Independently transcribed from the 2026 Orden Anexo II table,
# matching the registry's m131-modulos-cuantia-exceso-2026 parameter.
_INDICE_EXCESO = Decimal("1.30")
_CUANTIA_EXCESO_972_1 = Decimal("18051.81")


def _coeficiente_tramos(base: Decimal) -> Decimal:
    """Reproduce the coeficiente-por-tramos progressive-bracket lookup.

    Mirrors the registry's ``m131-modulos-coeficiente-tramos-asalariados-2026``
    bracket_table (cumulative fixed_addition + marginal_rate x remainder),
    independently transcribed here rather than re-derived from the formula
    under test.
    """
    if base <= Decimal("0"):
        return Decimal("0")
    for lower, upper, rate in _TRAMOS_ASALARIADOS:
        if upper is None or base <= upper:
            cumulative = Decimal("0")
            for prior_lower, prior_upper, prior_rate in _TRAMOS_ASALARIADOS:
                if prior_upper is not None and prior_upper <= lower:
                    cumulative += prior_rate * (prior_upper - prior_lower)
            return cumulative + rate * (base - lower)
    raise AssertionError("unreachable: open-ended top tramo always matches")


def _expected_minorado_no_inversion(previo: Decimal, *, modulo_1: Decimal, modulo_1_coefficient: Decimal) -> Decimal:
    """Reproduce Fase 2ª (minoración por incentivos al empleo only; no anterior/inversión)."""
    coeficiente_tramos = _coeficiente_tramos(modulo_1)
    minoracion_empleo = coeficiente_tramos * modulo_1_coefficient
    return round_to_cents(previo - minoracion_empleo)


def _expected_modulos(minorado: Decimal, *, cuantia: Decimal | None) -> Decimal:
    """Reproduce Fase 3ª (índice corrector de exceso only)."""
    if cuantia is None or minorado <= cuantia:
        return minorado
    return round_to_cents(cuantia + _INDICE_EXCESO * (minorado - cuantia))


def _run_modulos_engine_2026(
    epigrafe: str | None,
    *,
    modulo_1: Decimal = Decimal("0"),
    modulo_2: Decimal = Decimal("0"),
    modulo_3: Decimal = Decimal("0"),
    modulo_4: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    snapshot = _committed_snapshot("131", 2026, "1T", grade=RegistryAuthorityGrade.CALCULATION)
    assert snapshot.filing_period is not None
    text_inputs = {"modulos-epigrafe": epigrafe} if epigrafe else {}
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "modulos-1-unidades": modulo_1,
            "modulos-2-unidades": modulo_2,
            "modulos-3-unidades": modulo_3,
            "modulos-4-unidades": modulo_4,
            "modulos-5-unidades": Decimal("0"),
            "modulos-6-unidades": Decimal("0"),
            "modulos-7-unidades": Decimal("0"),
            "modulos-1-unidades-anterior": Decimal("0"),
            "modulos-minoracion-inversion": Decimal("0"),
        },
        text_inputs=text_inputs,
        date_context={"filing_period": snapshot.filing_period.end_date},
    )
    values = result.values
    return (
        values["modulos-rendimiento-neto-previo"],
        values["modulos-rendimiento-neto-minorado"],
        values["modulos-rendimiento-neto-modulos"],
        values["modulos-rendimiento-neto-actividad"],
    )


class TestPeluqueria9721EstimacionObjetiva2026:
    """Epígrafe IAE 972.1 (Servicios de peluquería) on the 2026 revision."""

    def test_fase_1_rendimiento_neto_previo_matches_2026_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 50 m2 local, 30 (100 kWh).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine_2026(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_previo = round_to_cents(
            Decimal("2") * _PELUQUERIA_972_1[1]
            + Decimal("1") * _PELUQUERIA_972_1[2]
            + Decimal("50") * _PELUQUERIA_972_1[3]
            + Decimal("30") * _PELUQUERIA_972_1[4],
        )
        assert previo == expected_previo == Decimal("23153.67")

    def test_fases_2_3_4_reproduce_independent_computation_on_2026_orden(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine_2026(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_minorado = _expected_minorado_no_inversion(
            previo,
            modulo_1=Decimal("2"),
            modulo_1_coefficient=_PELUQUERIA_972_1[1],
        )
        expected_modulos = _expected_modulos(expected_minorado, cuantia=_CUANTIA_EXCESO_972_1)
        expected_actividad = round_to_cents(expected_modulos - expected_modulos * _REDUCCION_GENERAL_2026)
        assert minorado == expected_minorado == Decimal("22363.20")
        assert modulos == expected_modulos == Decimal("23656.62")
        assert actividad == expected_actividad == Decimal("22473.79")


class TestAutotaxi7212EstimacionObjetiva2026:
    """Epígrafe IAE 721.2 (Transporte por autotaxis) on the 2026 revision."""

    def test_fase_1_rendimiento_neto_previo_matches_2026_orden_coefficients(self) -> None:
        # 0 personal asalariado, 1 personal no asalariado (titular), 40 (1.000 km).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine_2026(
            "721.2",
            modulo_1=Decimal("0"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = round_to_cents(Decimal("1") * _AUTOTAXI_721_2[2] + Decimal("40") * _AUTOTAXI_721_2[3])
        assert previo == expected_previo == Decimal("9460.09")


class TestModulos2026PartialTableCoverageDoesNotSilentlyMisattribute:
    """A 2026 activity absent from the phased dataset resolves to zero, not a fabricated figure."""

    def test_untabled_epigrafe_resolves_to_zero_on_2026_revision(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine_2026(
            "699.9",  # not an Orden Anexo II épigrafe — remains untabled
            modulo_1=Decimal("5"),
            modulo_2=Decimal("3"),
        )
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")

    def test_2025_and_2026_engines_agree_for_the_same_tabled_activity(self) -> None:
        """Cross-revision parity proof.

        The 2025 and 2026 engines must produce the same rendimiento-neto-de-la-
        actividad figure for the same declared units on an épigrafe whose Orden
        coefficients are byte-identical across both years — an independent check
        that the 2026 replication did not silently drift from its 2025 source
        (aeat-calculation-aggregation).
        """
        snapshot_2025 = _committed_snapshot("131", 2025, "1T", grade=RegistryAuthorityGrade.CALCULATION)
        assert snapshot_2025.filing_period is not None
        result_2025 = calculate_registry_snapshot(
            snapshot_2025,
            inputs={
                "modulos-1-unidades": Decimal("2"),
                "modulos-2-unidades": Decimal("1"),
                "modulos-3-unidades": Decimal("50"),
                "modulos-4-unidades": Decimal("30"),
                "modulos-5-unidades": Decimal("0"),
                "modulos-6-unidades": Decimal("0"),
                "modulos-7-unidades": Decimal("0"),
                "modulos-1-unidades-anterior": Decimal("0"),
                "modulos-minoracion-inversion": Decimal("0"),
            },
            text_inputs={"modulos-epigrafe": "972.1"},
            date_context={"filing_period": snapshot_2025.filing_period.end_date},
        )
        _previo_2026, _minorado_2026, _modulos_2026, actividad_2026 = _run_modulos_engine_2026(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        actividad_2025 = result_2025.values["modulos-rendimiento-neto-actividad"]
        assert actividad_2025 == actividad_2026 == Decimal("22473.79")
