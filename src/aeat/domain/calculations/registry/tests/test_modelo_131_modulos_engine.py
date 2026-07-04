"""Modelo 131 estimación-objetiva módulos engine (Fases 1ª-4ª, phased dataset).

Non-tautological: expected values are transcribed independently from the
bundled Orden HAC/1347/2024 Anexo II coefficient tables
(``corpus/normatives/html/orden-hac-1347-2024.html``), not re-derived from the
registry formula under test. Fase 2ª's minoración por incentivos al empleo
(the coeficiente por incremento + coeficiente por tramos mechanism) is
cross-checked byte-identical against the AEAT Manual práctico de Renta 2025
full worked example (epígrafe 673.1, Capítulo 8) — see
``TestCafesEspecial6731EstimacionObjetiva.test_full_manual_worked_example_fases_1_a_4``.
Fase 2ª's minoración por incentivos a la inversión is an operator-declared
euro amount (this engine does not model a per-element libro registro de
bienes de inversión); its subtraction is cross-checked against the same
manual worked example's printed 6.050,00 euros figure — see
``test_full_manual_worked_example_incluye_minoracion_inversion``. Fase 3ª's
índice corrector de exceso is grounded in the same Orden's tabled
cuantía/índice constants via the shared ``_expected_modulos`` helper (an
independent reproduction, not a re-derivation of the formula under test's own
intermediate output). The 5 por ciento reducción general (Fase 4ª) is grounded
in the same Orden's disposición adicional primera.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

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

# Next-priority activities (café-bar / restaurante), independently
# transcribed from the bundled Orden HAC/1347/2024 Anexo II
# (corpus/normatives/html/orden-hac-1347-2024.html, lines ~1772-1943) and
# cross-checked byte-identical against the AEAT Manual práctico de Renta 2025,
# Parte 1, Capítulo 8 apéndice (source.pdf.extracted.md lines ~22921-22984).
_RESTAURANTE_DOS_TENEDORES_671_4 = {
    1: Decimal("3709.88"),  # personal asalariado (persona)
    2: Decimal("17434.55"),  # personal no asalariado (persona)
    3: Decimal("201.55"),  # potencia eléctrica (kW contratado)
    4: Decimal("585.77"),  # mesas (mesa)
    5: Decimal("1077.06"),  # máquinas tipo «A»
    6: Decimal("3810.65"),  # máquinas tipo «B»
}
_RESTAURANTE_UN_TENEDOR_671_5 = {
    1: Decimal("3602.80"),  # personal asalariado (persona)
    2: Decimal("16174.82"),  # personal no asalariado (persona)
    3: Decimal("125.97"),  # potencia eléctrica (kW contratado)
    4: Decimal("220.45"),  # mesas (mesa)
    5: Decimal("1077.06"),  # máquinas tipo «A»
    6: Decimal("3810.65"),  # máquinas tipo «B»
}
_CAFETERIAS_672_1 = {
    1: Decimal("1448.68"),  # personal asalariado (persona)
    2: Decimal("13743.56"),  # personal no asalariado (persona)
    3: Decimal("478.69"),  # potencia eléctrica (kW contratado)
    4: Decimal("377.92"),  # mesas (mesa)
    5: Decimal("957.39"),  # máquinas tipo «A»
    6: Decimal("3747.67"),  # máquinas tipo «B»
}

# Next-priority activities (comercio al por menor de alimentación),
# independently transcribed from the same bundled Orden Anexo II (lines
# ~837-1148) and cross-checked byte-identical against the AEAT manual
# (source.pdf.extracted.md lines ~22413-22607).
_CARNE_642_1 = {
    1: Decimal("2355.68"),  # personal asalariado (persona)
    2: Decimal("10991.07"),  # personal no asalariado (persona)
    3: Decimal("35.90"),  # superficie local independiente (m2)
    4: Decimal("81.88"),  # superficie local no independiente (m2)
    5: Decimal("39.05"),  # consumo de energía eléctrica (100 kWh)
}
_PAN_PASTELERIA_644_1 = {
    1: Decimal("6248.22"),  # personal asalariado de fabricación (persona)
    2: Decimal("1058.17"),  # resto personal asalariado (persona)
    3: Decimal("14530.89"),  # personal no asalariado (persona)
    4: Decimal("49.13"),  # superficie del local de fabricación (m2)
    5: Decimal("34.01"),  # resto superficie local independiente (m2)
    6: Decimal("125.97"),  # resto superficie local no independiente (m2)
    7: Decimal("629.86"),  # superficie del horno (100 dm2)
}
_ALIMENTACION_647_1 = {
    1: Decimal("1026.67"),  # personal asalariado (persona)
    2: Decimal("10839.90"),  # personal no asalariado (persona)
    3: Decimal("20.15"),  # superficie del local independiente (m2)
    4: Decimal("68.65"),  # superficie del local no independiente (m2)
    5: Decimal("8.81"),  # consumo de energía eléctrica (100 kWh)
}

# Activities not previously covered by a dedicated test (backfilled
# per a review's low-severity finding), independently transcribed from the
# same bundled Orden Anexo II and cross-checked against the AEAT manual.
_CAFES_ESPECIAL_673_1 = {
    1: Decimal("4056.30"),  # personal asalariado (persona)
    2: Decimal("15538.66"),  # personal no asalariado (persona)
    3: Decimal("321.23"),  # potencia eléctrica (kW contratado)
    4: Decimal("233.04"),  # mesas (mesa)
    5: Decimal("371.62"),  # longitud de barra (metro)
    6: Decimal("957.39"),  # máquinas tipo «A»
    7: Decimal("2903.66"),  # máquinas tipo «B»
}
_OTROS_CAFES_673_2 = {
    1: Decimal("1643.93"),  # personal asalariado (persona)
    2: Decimal("11413.08"),  # personal no asalariado (persona)
    3: Decimal("94.48"),  # potencia eléctrica (kW contratado)
    4: Decimal("119.67"),  # mesas (mesa)
    5: Decimal("163.76"),  # longitud de barra (metro)
    6: Decimal("806.23"),  # máquinas tipo «A»
    7: Decimal("2947.75"),  # máquinas tipo «B»
}
_HUEVOS_AVES_642_5 = {
    1: Decimal("3382.36"),  # personal asalariado (persona)
    2: Decimal("11337.49"),  # personal no asalariado (persona)
    3: Decimal("25.19"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("27.08"),  # superficie local independiente (m2)
    5: Decimal("58.57"),  # superficie local no independiente (m2)
}
_CASQUERIAS_642_6 = {
    1: Decimal("2254.90"),  # personal asalariado (persona)
    2: Decimal("11098.14"),  # personal no asalariado (persona)
    3: Decimal("27.71"),  # superficie local independiente (m2)
    4: Decimal("69.28"),  # superficie local no independiente (m2)
    5: Decimal("35.90"),  # consumo de energía eléctrica (100 kWh)
}
_PESCADOS_643_1 = {
    1: Decimal("3823.25"),  # personal asalariado (persona)
    2: Decimal("13296.36"),  # personal no asalariado (persona)
    3: Decimal("36.53"),  # superficie local independiente (m2)
    4: Decimal("113.37"),  # superficie local no independiente (m2)
    5: Decimal("28.98"),  # consumo de energía eléctrica (100 kWh)
}
_DESPACHOS_PAN_644_2 = {
    1: Decimal("6134.85"),  # personal asalariado de fabricación (persona)
    2: Decimal("1039.27"),  # resto personal asalariado (persona)
    3: Decimal("14266.34"),  # personal no asalariado (persona)
    4: Decimal("48.50"),  # superficie del local de fabricación (m2)
    5: Decimal("33.38"),  # resto superficie local independiente (m2)
    6: Decimal("125.97"),  # resto superficie local no independiente (m2)
    7: Decimal("629.86"),  # superficie del horno (100 dm2)
}
_PASTELERIA_644_3 = {
    1: Decimal("6367.89"),  # personal asalariado de fabricación (persona)
    2: Decimal("1014.08"),  # resto personal asalariado (persona)
    3: Decimal("12912.15"),  # personal no asalariado (persona)
    4: Decimal("43.46"),  # superficie del local de fabricación (m2)
    5: Decimal("34.01"),  # resto superficie local independiente (m2)
    6: Decimal("113.37"),  # resto superficie local no independiente (m2)
    7: Decimal("522.78"),  # superficie del horno (100 dm2)
}
_MASAS_FRITAS_644_6 = {
    1: Decimal("6852.88"),  # personal asalariado de fabricación (persona)
    2: Decimal("2254.90"),  # resto personal asalariado (persona)
    3: Decimal("13214.47"),  # personal no asalariado (persona)
    4: Decimal("27.71"),  # superficie del local de fabricación (m2)
    5: Decimal("21.41"),  # resto superficie local independiente (m2)
    6: Decimal("36.53"),  # resto superficie local no independiente (m2)
}
_AUTOSERVICIO_647_2 = {
    1: Decimal("1788.80"),  # personal asalariado (persona)
    2: Decimal("10827.31"),  # personal no asalariado (persona)
    3: Decimal("23.31"),  # superficie del local (m2)
    4: Decimal("32.75"),  # consumo de energía eléctrica (100 kWh)
}

# Next-priority activities (comercio al por menor de textil/calzado/
# mueble/electrodoméstico, hospedaje, reparaciones, transporte urbano),
# independently transcribed from the bundled Orden HAC/1347/2024 Anexo II and
# cross-checked byte-identical against the AEAT Manual práctico de Renta 2025.
_LENCERIA_651_3 = {
    1: Decimal("2198.21"),  # personal asalariado (persona)
    2: Decimal("11998.85"),  # personal no asalariado (persona) — corpus-typo
    # correction: the bundled Orden HTML reads "11.998.85" (period instead of
    # comma); the AEAT Manual Renta 2025 states "11.998,85" unambiguously.
    3: Decimal("47.87"),  # superficie del local (m2)
    4: Decimal("75.58"),  # consumo de energía eléctrica (100 kWh)
}
_TEXTIL_651_1 = {
    1: Decimal("3010.74"),  # personal asalariado (persona)
    2: Decimal("13812.85"),  # personal no asalariado (persona)
    3: Decimal("38.42"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("35.28"),  # superficie del local independiente (m2)
    5: Decimal("107.07"),  # superficie del local no independiente (m2)
}
_MUEBLES_653_1 = {
    1: Decimal("4075.20"),  # personal asalariado (persona)
    2: Decimal("16200.02"),  # personal no asalariado (persona)
    3: Decimal("50.39"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("16.38"),  # superficie del local (m2)
}
_RECAMBIOS_654_2 = {
    1: Decimal("3098.92"),  # personal asalariado (persona)
    2: Decimal("17018.84"),  # personal no asalariado (persona)
    3: Decimal("201.55"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("617.26"),  # potencia fiscal vehículo (CVF)
}
_OPTICA_659_3 = {
    1: Decimal("7174.12"),  # personal asalariado (persona)
    2: Decimal("19273.74"),  # personal no asalariado (persona)
    3: Decimal("119.67"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("1070.76"),  # potencia fiscal vehículo (CVF)
}
_AMBULANTE_ALIMENTACION_663_1 = {
    1: Decimal("1398.29"),  # personal asalariado (persona)
    2: Decimal("13989.21"),  # personal no asalariado (persona)
    3: Decimal("113.37"),  # potencia fiscal vehículo (CVF)
}
_HOSPEDAJE_HOTEL_681 = {
    1: Decimal("6223.02"),  # personal asalariado (persona)
    2: Decimal("20438.98"),  # personal no asalariado (persona)
    3: Decimal("371.62"),  # número de plazas (plaza)
}
_REPARACION_VEHICULOS_691_2 = {
    1: Decimal("4157.08"),  # personal asalariado (persona)
    2: Decimal("17094.42"),  # personal no asalariado (persona)
    3: Decimal("27.08"),  # superficie del local (m2)
}
_TRANSPORTE_URBANO_721_1 = {
    1: Decimal("2981.02"),  # personal asalariado (persona)
    2: Decimal("16016.97"),  # personal no asalariado (persona)
    3: Decimal("121.40"),  # número de asientos (asiento)
}

# Remaining next-priority activities (#516): reparaciones,
# engrase/lavado, mudanzas, mensajería, enseñanza, servicios personales, and
# the 659.4/691.9 epígrafe-collision pairs (resolved via the "a"/"b"
# key-namespace suffix convention — see the registry parameter file's note),
# independently transcribed from the bundled Orden HAC/1347/2024
# Anexo II and cross-checked byte-identical against the AEAT Manual práctico
# de Renta 2025, Parte 1, Capítulo 8 apéndice.
_PAPELERIA_659_4A = {
    1: Decimal("4648.37"),  # personal asalariado (persona)
    2: Decimal("17176.30"),  # personal no asalariado (persona)
    3: Decimal("57.94"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("30.86"),  # superficie del local (m2)
    5: Decimal("535.38"),  # potencia fiscal vehículo (CVF)
}
_QUIOSCOS_PRENSA_659_4B = {
    1: Decimal("3476.83"),  # personal asalariado (persona)
    2: Decimal("17220.39"),  # personal no asalariado (persona)
    3: Decimal("403.11"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("844.02"),  # superficie del local (m2)
}
_REPARACION_CALZADO_691_9A = {
    1: Decimal("1845.50"),  # personal asalariado (persona)
    2: Decimal("10014.78"),  # personal no asalariado (persona)
    3: Decimal("125.97"),  # consumo de energía eléctrica (100 kWh)
}
_REPARACION_OTROS_BIENES_691_9B = {
    1: Decimal("4094.10"),  # personal asalariado (persona)
    2: Decimal("16187.42"),  # personal no asalariado (persona)
    3: Decimal("45.35"),  # superficie del local (m2)
}
_ENGRASE_LAVADO_751_5 = {
    1: Decimal("4667.27"),  # personal asalariado (persona)
    2: Decimal("19191.86"),  # personal no asalariado (persona)
    3: Decimal("30.23"),  # superficie del local (m2)
}
_MUDANZAS_757 = {
    1: Decimal("2566.32"),  # personal asalariado (persona)
    2: Decimal("10175.13"),  # personal no asalariado (persona)
    3: Decimal("48.08"),  # carga vehículos (tonelada)
}
_MENSAJERIA_849_5 = {
    1: Decimal("2728.59"),  # personal asalariado (persona)
    2: Decimal("10090.99"),  # personal no asalariado (persona)
    3: Decimal("126.21"),  # carga vehículos (tonelada)
}
_AUTOESCUELA_933_1 = {
    1: Decimal("3067.42"),  # personal asalariado (persona)
    2: Decimal("20596.45"),  # personal no asalariado (persona)
    3: Decimal("774.72"),  # número de vehículos (vehículo)
    4: Decimal("258.24"),  # potencia fiscal vehículo (CVF)
}
_OTRAS_ENSENANZAS_933_9 = {
    1: Decimal("1253.49"),  # personal asalariado (persona)
    2: Decimal("15727.62"),  # personal no asalariado (persona)
    3: Decimal("62.36"),  # superficie del local (m2)
}
_ESCUELAS_DEPORTE_967_2 = {
    1: Decimal("7035.55"),  # personal asalariado (persona)
    2: Decimal("14215.95"),  # personal no asalariado (persona)
    3: Decimal("34.01"),  # superficie del local (m2)
}
_TINTORERIA_971_1 = {
    1: Decimal("4553.90"),  # personal asalariado (persona)
    2: Decimal("16773.19"),  # personal no asalariado (persona)
    3: Decimal("45.98"),  # consumo de energía eléctrica (100 kWh)
}
_INSTITUTOS_BELLEZA_972_2 = {
    1: Decimal("1788.80"),  # personal asalariado (persona)
    2: Decimal("14896.21"),  # personal no asalariado (persona)
    3: Decimal("88.18"),  # superficie del local (m2)
    4: Decimal("55.43"),  # consumo de energía eléctrica (100 kWh)
}
_COPISTERIA_973_3 = {
    1: Decimal("4125.59"),  # personal asalariado (persona)
    2: Decimal("17044.03"),  # personal no asalariado (persona)
    3: Decimal("541.68"),  # potencia eléctrica (KW contratado)
}
_FRUTAS_VERDURAS_641 = {
    1: Decimal("2387.18"),  # personal asalariado (persona)
    2: Decimal("10581.66"),  # personal no asalariado (persona)
    3: Decimal("57.94"),  # superficie local independiente (m2)
    4: Decimal("88.18"),  # superficie local no independiente (m2)
    5: Decimal("1.01"),  # carga elementos de transporte (kilogramo)
}
_QUIOSCOS_SERVICIOS_675 = {
    1: Decimal("2802.88"),  # personal asalariado (persona)
    2: Decimal("14461.60"),  # personal no asalariado (persona)
    3: Decimal("107.07"),  # potencia eléctrica (KW contratado)
    4: Decimal("26.45"),  # superficie del local (m2)
}
_CHOCOLATERIAS_676 = {
    1: Decimal("2418.67"),  # personal asalariado (persona)
    2: Decimal("20016.97"),  # personal no asalariado (persona)
    3: Decimal("541.68"),  # potencia eléctrica (KW contratado)
    4: Decimal("220.45"),  # mesas (mesa)
    5: Decimal("806.23"),  # máquinas tipo «A»
}

_REDUCCION_GENERAL_2025 = Decimal("0.05")

# Fase 2ª — coeficiente por tramos del número de unidades del módulo
# "personal asalariado" (Orden HAC/1347/2024 Anexo II, instrucción 2.2.a),
# independently transcribed for cross-check against the registry's
# m131-modulos-coeficiente-tramos-asalariados-2025 bracket_table parameter.
_COEFICIENTE_INCREMENTO_ASALARIADOS = Decimal("0.40")
_TRAMOS_ASALARIADOS = (
    (Decimal("0"), Decimal("1.00"), Decimal("0.10")),
    (Decimal("1.00"), Decimal("3.00"), Decimal("0.15")),
    (Decimal("3.00"), Decimal("5.00"), Decimal("0.20")),
    (Decimal("5.00"), Decimal("8.00"), Decimal("0.25")),
    (Decimal("8.00"), None, Decimal("0.30")),
)

# Fase 3ª — índice corrector de exceso (Orden HAC/1347/2024 Anexo II,
# instrucción 2.3.b.3): índice 1,30 aplied to the excess over the tabled
# cuantía. Cuantías independently transcribed from the same bundled Orden
# Anexo II table, matching the registry's m131-modulos-cuantia-exceso-2025
# keyed_bracket_table parameter for the epígrafes tabled in this first
# slice (2026-07-01-modelo-131-eo-modulos-engine-adr Phase 2).
_INDICE_EXCESO = Decimal("1.30")
_CUANTIA_EXCESO = {
    "972.1": Decimal("18051.81"),
    "721.2": Decimal("33640.86"),
    "722": Decimal("33640.86"),
    "671.4": Decimal("51617.08"),
    "671.5": Decimal("38081.38"),
    "672.1": Decimal("39070.26"),
    "673.1": Decimal("30586.03"),
    "673.2": Decimal("19084.78"),
}

# Módulo 1 ("personal asalariado") rendimiento-anual-por-unidad coefficient
# per epígrafe, keyed to the same activity dicts the Fase 1ª tests already
# cross-check against the bundled Orden Anexo II — reused here (not
# re-derived from the registry formula under test) so the Fase 2ª test
# helper can compute the minoración's "coefficient x módulo-1 coefficient"
# product independently.
_MODULO_1_COEFICIENTE_BY_EPIGRAFE = {
    "972.1": _PELUQUERIA_972_1[1],
    "721.2": _AUTOTAXI_721_2[1],
    "722": _MERCANCIAS_722[1],
    "671.4": _RESTAURANTE_DOS_TENEDORES_671_4[1],
    "671.5": _RESTAURANTE_UN_TENEDOR_671_5[1],
    "672.1": _CAFETERIAS_672_1[1],
    "673.1": _CAFES_ESPECIAL_673_1[1],
    "673.2": _OTROS_CAFES_673_2[1],
    "644.1": _PAN_PASTELERIA_644_1[1],
    "647.2": _AUTOSERVICIO_647_2[1],
    "642.5": _HUEVOS_AVES_642_5[1],
    "643.1": _PESCADOS_643_1[1],
    "644.2": _DESPACHOS_PAN_644_2[1],
    "644.3": _PASTELERIA_644_3[1],
    "644.6": _MASAS_FRITAS_644_6[1],
    "651.1": _TEXTIL_651_1[1],
    "681": _HOSPEDAJE_HOTEL_681[1],
    "721.1": _TRANSPORTE_URBANO_721_1[1],
    "659.4a": _PAPELERIA_659_4A[1],
    "691.9b": _REPARACION_OTROS_BIENES_691_9B[1],
    "751.5": _ENGRASE_LAVADO_751_5[1],
    "849.5": _MENSAJERIA_849_5[1],
    "933.1": _AUTOESCUELA_933_1[1],
    "967.2": _ESCUELAS_DEPORTE_967_2[1],
    "971.1": _TINTORERIA_971_1[1],
    "972.2": _INSTITUTOS_BELLEZA_972_2[1],
    "973.3": _COPISTERIA_973_3[1],
    "641": _FRUTAS_VERDURAS_641[1],
    "675": _QUIOSCOS_SERVICIOS_675[1],
    "676": _CHOCOLATERIAS_676[1],
    "642.6": _CASQUERIAS_642_6[1],
    "659.4b": _QUIOSCOS_PRENSA_659_4B[1],
    "691.9a": _REPARACION_CALZADO_691_9A[1],
    "757": _MUDANZAS_757[1],
    "933.9": _OTRAS_ENSENANZAS_933_9[1],
}


def _module_1_coefficient(epigrafe: str) -> Decimal:
    return _MODULO_1_COEFICIENTE_BY_EPIGRAFE[epigrafe]


def _coeficiente_tramos(base: Decimal) -> Decimal:
    """Reproduce the coeficiente-por-tramos progressive-bracket lookup.

    Mirrors the registry's ``m131-modulos-coeficiente-tramos-asalariados-2025``
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


def _money_round(value: Decimal) -> Decimal:
    """Round to euro-cent precision with half-up semantics (mirrors ``apply_rounding('money-2')``)."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _expected_minorado(
    previo: Decimal,
    *,
    epigrafe: str,
    modulo_1: Decimal,
    modulo_1_anterior: Decimal,
    modulo_1_coefficient: Decimal,
    minoracion_inversion: Decimal = Decimal("0"),
) -> Decimal:
    """Reproduce Fase 2ª (minoración por incentivos al empleo + a la inversión)."""
    incremento = (
        modulo_1 - modulo_1_anterior
        if modulo_1_anterior > Decimal("0") and modulo_1 > modulo_1_anterior
        else Decimal("0")
    )
    coeficiente_incremento = incremento * _COEFICIENTE_INCREMENTO_ASALARIADOS
    base_tramos = modulo_1 - incremento
    coeficiente_tramos = _coeficiente_tramos(base_tramos)
    minoracion_empleo = (coeficiente_incremento + coeficiente_tramos) * modulo_1_coefficient
    return _money_round(previo - minoracion_empleo - minoracion_inversion)


def _expected_modulos(minorado: Decimal, *, epigrafe: str) -> Decimal:
    """Reproduce Fase 3ª (índice corrector de exceso only)."""
    cuantia = _CUANTIA_EXCESO.get(epigrafe)
    if cuantia is None or minorado <= cuantia:
        return minorado
    return _money_round(cuantia + _INDICE_EXCESO * (minorado - cuantia))


#: Epígrafes carrying a documented índice corrector especial (Orden
#: HAC/1347/2024 Anexo II, instrucción 2.3, letra a) that exclude the índice
#: corrector para empresas de pequeña dimensión (b.1) — mirrors the
#: registry's ``_M131_EPIGRAFES_INDICE_ESPECIAL`` frozenset (transcribed
#: independently for cross-check, not imported from the module under test).
_EPIGRAFES_INDICE_ESPECIAL = frozenset({"721.2", "722"})


def _expected_modulos_generales(
    minorado: Decimal,
    *,
    epigrafe: str,
    pequena_dimension: Decimal = Decimal("0"),
    temporada: Decimal = Decimal("0"),
    inicio_actividad: Decimal = Decimal("0"),
) -> Decimal:
    """Reproduce the full Fase 3ª índices correctores generales cascade (b.1, b.2/b.4, b.3).

    Independently transcribed from Orden HAC/1347/2024 Anexo II, instrucción
    2.3's own enumeration order and incompatibilidades, not re-derived from
    the ``m131_resolve_modulos_indices_generales`` op under test.
    """
    if minorado <= Decimal("0"):
        return minorado
    aplica_pequena_dimension = pequena_dimension > Decimal("0") and epigrafe not in _EPIGRAFES_INDICE_ESPECIAL
    rendimiento = minorado
    if aplica_pequena_dimension:
        rendimiento = rendimiento * pequena_dimension
    if temporada > Decimal("0"):
        rendimiento = rendimiento * temporada
    elif inicio_actividad > Decimal("0"):
        rendimiento = rendimiento * inicio_actividad
    if aplica_pequena_dimension:
        return _money_round(rendimiento)
    cuantia = _CUANTIA_EXCESO.get(epigrafe)
    if cuantia is None or rendimiento <= cuantia:
        return _money_round(rendimiento)
    return _money_round(cuantia + _INDICE_EXCESO * (rendimiento - cuantia))


def _run_modulos_engine(
    epigrafe: str | None,
    *,
    modulo_1: Decimal = Decimal("0"),
    modulo_2: Decimal = Decimal("0"),
    modulo_3: Decimal = Decimal("0"),
    modulo_4: Decimal = Decimal("0"),
    modulo_5: Decimal = Decimal("0"),
    modulo_6: Decimal = Decimal("0"),
    modulo_7: Decimal = Decimal("0"),
    modulo_1_anterior: Decimal = Decimal("0"),
    minoracion_inversion: Decimal = Decimal("0"),
    indice_pequena_dimension: Decimal = Decimal("0"),
    indice_temporada: Decimal = Decimal("0"),
    indice_inicio_actividad: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    snapshot = _committed_snapshot("131", 2025, "1T")
    assert snapshot.filing_period is not None
    text_inputs = {"modulos-epigrafe": epigrafe} if epigrafe else {}
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "modulos-1-unidades": modulo_1,
            "modulos-2-unidades": modulo_2,
            "modulos-3-unidades": modulo_3,
            "modulos-4-unidades": modulo_4,
            "modulos-5-unidades": modulo_5,
            "modulos-6-unidades": modulo_6,
            "modulos-7-unidades": modulo_7,
            "modulos-1-unidades-anterior": modulo_1_anterior,
            "modulos-minoracion-inversion": minoracion_inversion,
            "modulos-indice-pequena-dimension": indice_pequena_dimension,
            "modulos-indice-temporada": indice_temporada,
            "modulos-indice-inicio-actividad": indice_inicio_actividad,
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


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


class TestPeluqueria9721EstimacionObjetiva:
    """Epígrafe IAE 972.1 (Servicios de peluquería de señora y caballero)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 50 m2 local, 30 (100 kWh).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
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
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="972.1",
            modulo_1=Decimal("2"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("972.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="972.1")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestAutotaxi7212EstimacionObjetiva:
    """Epígrafe IAE 721.2 (Transporte por autotaxis)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 0 personal asalariado, 1 personal no asalariado (titular), 40 (1.000 km).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "721.2",
            modulo_1=Decimal("0"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = _quantize(Decimal("1") * _AUTOTAXI_721_2[2] + Decimal("40") * _AUTOTAXI_721_2[3])
        assert previo == expected_previo == Decimal("9460.09")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "721.2",
            modulo_1=Decimal("0"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="721.2",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("721.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="721.2")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestTransporteMercancias722EstimacionObjetiva:
    """Epígrafe IAE 722 (Transporte de mercancías por carretera)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 0 personal no asalariado, 8 toneladas carga.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "722",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("0"),
            modulo_3=Decimal("8"),
        )
        expected_previo = _quantize(Decimal("1") * _MERCANCIAS_722[1] + Decimal("8") * _MERCANCIAS_722[3])
        assert previo == expected_previo == Decimal("3738.27")


class TestRestauranteDosTenedores6714EstimacionObjetiva:
    """Epígrafe IAE 671.4 (Restaurantes de dos tenedores)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 8 kW potencia
        # eléctrica, 3 mesas, 1 máquina tipo «A».
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "671.4",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("8"),
            modulo_4=Decimal("3"),
            modulo_5=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("2") * _RESTAURANTE_DOS_TENEDORES_671_4[1]
            + Decimal("1") * _RESTAURANTE_DOS_TENEDORES_671_4[2]
            + Decimal("8") * _RESTAURANTE_DOS_TENEDORES_671_4[3]
            + Decimal("3") * _RESTAURANTE_DOS_TENEDORES_671_4[4]
            + Decimal("1") * _RESTAURANTE_DOS_TENEDORES_671_4[5],
        )
        assert previo == expected_previo == Decimal("29301.08")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "671.4",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("8"),
            modulo_4=Decimal("3"),
            modulo_5=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="671.4",
            modulo_1=Decimal("2"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("671.4"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="671.4")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestRestauranteUnTenedor6715EstimacionObjetiva:
    """Epígrafe IAE 671.5 (Restaurantes de un tenedor)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 0 personal no asalariado, 6 kW potencia
        # eléctrica, 4 mesas, 2 máquinas tipo «B».
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "671.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("0"),
            modulo_3=Decimal("6"),
            modulo_4=Decimal("4"),
            modulo_6=Decimal("2"),
        )
        expected_previo = _quantize(
            Decimal("1") * _RESTAURANTE_UN_TENEDOR_671_5[1]
            + Decimal("6") * _RESTAURANTE_UN_TENEDOR_671_5[3]
            + Decimal("4") * _RESTAURANTE_UN_TENEDOR_671_5[4]
            + Decimal("2") * _RESTAURANTE_UN_TENEDOR_671_5[6],
        )
        assert previo == expected_previo == Decimal("12861.72")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "671.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("0"),
            modulo_3=Decimal("6"),
            modulo_4=Decimal("4"),
            modulo_6=Decimal("2"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="671.5",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("671.5"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="671.5")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestCafeterias6721EstimacionObjetiva:
    """Epígrafe IAE 672.1, 2 y 3 (Cafeterías)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 3 personal asalariado, 1 personal no asalariado, 10 kW potencia
        # eléctrica.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "672.1",
            modulo_1=Decimal("3"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
        )
        expected_previo = _quantize(
            Decimal("3") * _CAFETERIAS_672_1[1]
            + Decimal("1") * _CAFETERIAS_672_1[2]
            + Decimal("10") * _CAFETERIAS_672_1[3],
        )
        assert previo == expected_previo == Decimal("22876.50")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "672.1",
            modulo_1=Decimal("3"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="672.1",
            modulo_1=Decimal("3"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("672.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="672.1")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestComercioCarne6421EstimacionObjetiva:
    """Epígrafe IAE 642.1, 2, 3 y 4 (Comercio al por menor de carne y despojos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 40 m2 superficie
        # local no independiente.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "642.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("40"),
        )
        expected_previo = _quantize(
            Decimal("1") * _CARNE_642_1[1] + Decimal("1") * _CARNE_642_1[2] + Decimal("40") * _CARNE_642_1[4],
        )
        assert previo == expected_previo == Decimal("16621.95")


class TestPanPasteleria6441EstimacionObjetiva:
    """Epígrafe IAE 644.1 (Comercio al por menor de pan, pastelería...) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_uses_all_seven_modulo_slots(self) -> None:
        # 1 personal asalariado de fabricación, 1 resto personal asalariado,
        # 1 personal no asalariado, 30 m2 superficie del local de
        # fabricación, 2 (100 dm2) superficie del horno. This activity has 7
        # signos; a 4-slot engine would silently drop módulo 7 (superficie
        # del horno, 629,86 €/unit) — the exact over-truncation risk the
        # modelo-131-eo-modulos-engine decision record rejected (the option
        # that capped the engine at 4 slots).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "644.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("1"),
            modulo_4=Decimal("30"),
            modulo_7=Decimal("2"),
        )
        expected_previo = _quantize(
            Decimal("1") * _PAN_PASTELERIA_644_1[1]
            + Decimal("1") * _PAN_PASTELERIA_644_1[2]
            + Decimal("1") * _PAN_PASTELERIA_644_1[3]
            + Decimal("30") * _PAN_PASTELERIA_644_1[4]
            + Decimal("2") * _PAN_PASTELERIA_644_1[7],
        )
        assert previo == expected_previo == Decimal("24570.90")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "644.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("1"),
            modulo_4=Decimal("30"),
            modulo_7=Decimal("2"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="644.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("644.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="644.1")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestComercioAlimenticios6471EstimacionObjetiva:
    """Epígrafe IAE 647.1 (Comercio al por menor de alimentación en establecimientos con vendedor)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 40 m2 superficie del local independiente.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "647.1",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = _quantize(Decimal("1") * _ALIMENTACION_647_1[1] + Decimal("40") * _ALIMENTACION_647_1[3])
        assert previo == expected_previo == Decimal("1832.67")


class TestCafesEspecial6731EstimacionObjetiva:
    """Epígrafe IAE 673.1 (Cafés y bares de categoría especial) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 5 metros longitud de barra.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("1"),
            modulo_5=Decimal("5"),
        )
        expected_previo = _quantize(
            Decimal("1") * _CAFES_ESPECIAL_673_1[1] + Decimal("5") * _CAFES_ESPECIAL_673_1[5],
        )
        assert previo == expected_previo == Decimal("5914.40")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("1"),
            modulo_5=Decimal("5"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="673.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("673.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="673.1")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad

    def test_full_manual_worked_example_fases_1_a_4(self) -> None:
        """AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 8, caso práctico.

        Bar de categoría especial (epígrafe 673.1): 3,66 personal asalariado,
        1,00 personal no asalariado, 35,00 kW potencia eléctrica, 8,00 mesas,
        10,00 metros de barra, 0,00 máquinas tipo «A», 1,00 máquina tipo «B»;
        3,00 personas del módulo "personal asalariado" en el ejercicio
        anterior (2024). The Fase 1ª and Fase 2ª figures below are
        transcribed byte-identical from the manual's printed solution — Fase
        1ª rendimiento neto previo 50.111,95; Fase 2ª minoración por
        incentivos al empleo 2.693,38 (coeficiente de minoración 0,664, del
        cual 0,264 por incremento y 0,40 por tramos, sobre el módulo
        "personal asalariado" 4.056,30 euros/unidad). The minoración por
        incentivos a la inversión (6.050,00 euros, an asset-register figure
        this first slice does not model) is NOT applied here, so this test's
        own ``minorado`` (47.418,57) diverges from the manual's printed
        rendimiento neto minorado (41.368,57 = 50.111,95 - 2.693,38 - 6.050);
        the divergence is the documented, legitimate consequence of the
        not-yet-modelled inversión reduction, never a computation error. The
        manual's own Fase 3ª (índice corrector de exceso applied to
        41.368,57, giving rendimiento neto de módulos 44.603,33) does not
        apply against this test's employ-only minorado and is intentionally
        NOT asserted here to avoid re-deriving a "manual" figure the manual
        never printed for this base; Fase 3ª's índice-de-exceso mechanism
        against the tabled cuantía is instead covered structurally by
        ``test_fase_4_rendimiento_neto_actividad_applies_reduccion_general``
        (shared ``_expected_modulos`` helper, cross-checked against the
        Orden's own tabled cuantía/índice constants).
        """
        previo, minorado, _modulos, _actividad = _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("3.66"),
            modulo_2=Decimal("1.00"),
            modulo_3=Decimal("35.00"),
            modulo_4=Decimal("8.00"),
            modulo_5=Decimal("10.00"),
            modulo_6=Decimal("0.00"),
            modulo_7=Decimal("1.00"),
            modulo_1_anterior=Decimal("3.00"),
        )
        assert previo == Decimal("50111.95")
        # Fase 2ª: coeficiente por incremento 0,40 x 0,66 = 0,264; coeficiente
        # por tramos sobre 3,00 unidades restantes = 0,10 + 0,30 = 0,40;
        # coeficiente de minoración 0,264 + 0,40 = 0,664; minoración empleo =
        # 0,664 x 4.056,30 = 2.693,38 (manual, redondeado).
        minoracion_empleo = _money_round(previo - minorado)
        assert minoracion_empleo == Decimal("2693.38")
        assert minorado == Decimal("47418.57")

    def test_full_manual_worked_example_incluye_minoracion_inversion(self) -> None:
        """AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 8, caso práctico.

        Same activity and inputs as
        ``test_full_manual_worked_example_fases_1_a_4``, now supplying the
        operator-declared minoración por incentivos a la inversión the
        manual's own libro registro de bienes de inversión yields: mobiliario
        viejo ya amortizado (0), cafetera 9.400 euros amortización pendiente
        1.000 (25% coeficiente máximo topado por el saldo pendiente),
        vitrina térmica 4.000 euros x 25% = 1.000, instalación de aire
        acondicionado 6.600 euros x 25% = 1.650, mesas y sillas nuevas 2.400
        euros amortizadas libremente (elementos nuevos ≤ 601,01 euros/unidad
        y ≤ 3.005,06 euros en conjunto) = 2.400; total minoración por
        incentivos a la inversión = 1.000 + 1.000 + 1.650 + 2.400 = 6.050,00
        euros, transcribed byte-identical from the manual's printed table.
        With this declared amount, this test's rendimiento neto minorado
        (50.111,95 − 2.693,38 − 6.050,00 = 41.368,57) and rendimiento neto de
        módulos (30.586,03 + 1,30 x (41.368,57 − 30.586,03) = 44.603,33) both
        reproduce the manual's own printed Fase 2ª and Fase 3ª figures
        exactly — an independent, non-tautological proof that the engine's
        minoración-por-inversión subtraction and the índice-corrector-de-
        exceso chain compose correctly once the operator supplies the
        amortization figure.
        """
        previo, minorado, modulos, _actividad = _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("3.66"),
            modulo_2=Decimal("1.00"),
            modulo_3=Decimal("35.00"),
            modulo_4=Decimal("8.00"),
            modulo_5=Decimal("10.00"),
            modulo_6=Decimal("0.00"),
            modulo_7=Decimal("1.00"),
            modulo_1_anterior=Decimal("3.00"),
            minoracion_inversion=Decimal("6050.00"),
        )
        assert previo == Decimal("50111.95")
        assert minorado == Decimal("41368.57")
        # Fase 3ª: rendimiento neto minorado 41.368,57 supera la cuantía
        # tabulada 30.586,03; exceso 10.782,54 x índice 1,30 = 14.017,30;
        # rendimiento neto de módulos = 30.586,03 + 14.017,30 = 44.603,33
        # (manual, redondeado).
        assert modulos == Decimal("44603.33")


class TestOtrosCafes6732EstimacionObjetiva:
    """Epígrafe IAE 673.2 (Otros cafés y bares)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 3 mesas.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "673.2",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("3"),
        )
        expected_previo = _quantize(
            Decimal("1") * _OTROS_CAFES_673_2[1]
            + Decimal("1") * _OTROS_CAFES_673_2[2]
            + Decimal("3") * _OTROS_CAFES_673_2[4],
        )
        assert previo == expected_previo == Decimal("13416.02")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "673.2",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("3"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="673.2",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("673.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="673.2")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestHuevosAves6425EstimacionObjetiva:
    """Epígrafe IAE 642.5 (Comercio al por menor de huevos, aves, conejos de granja, caza)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 20 m2 superficie local independiente.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "642.5",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _HUEVOS_AVES_642_5[1] + Decimal("20") * _HUEVOS_AVES_642_5[4],
        )
        assert previo == expected_previo == Decimal("3923.96")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "642.5",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="642.5",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("642.5"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="642.5")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestCasquerias6426EstimacionObjetiva:
    """Epígrafe IAE 642.6 (Comercio al por menor en casquerías)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 30 m2 superficie local no independiente.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "642.6",
            modulo_2=Decimal("1"),
            modulo_4=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("1") * _CASQUERIAS_642_6[2] + Decimal("30") * _CASQUERIAS_642_6[4],
        )
        assert previo == expected_previo == Decimal("13176.54")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "642.6",
            modulo_2=Decimal("1"),
            modulo_4=Decimal("30"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="642.6",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("642.6"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="642.6")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestPescados6431EstimacionObjetiva:
    """Epígrafe IAE 643.1 y 2 (Comercio al por menor de pescados)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "643.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _PESCADOS_643_1[1] + Decimal("1") * _PESCADOS_643_1[2],
        )
        assert previo == expected_previo == Decimal("17119.61")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "643.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="643.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("643.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="643.1")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestDespachosPan6442EstimacionObjetiva:
    """Epígrafe IAE 644.2 (Despachos de pan, panes especiales y bollería) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado de fabricación, 1 personal no asalariado.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "644.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _DESPACHOS_PAN_644_2[1] + Decimal("1") * _DESPACHOS_PAN_644_2[3],
        )
        assert previo == expected_previo == Decimal("20401.19")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "644.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="644.2",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("644.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="644.2")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestPasteleria6443EstimacionObjetiva:
    """Epígrafe IAE 644.3 (Comercio al por menor de pastelería, bollería y confitería) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado de fabricación, 20 m2 superficie del local de fabricación.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "644.3",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _PASTELERIA_644_3[1] + Decimal("20") * _PASTELERIA_644_3[4],
        )
        assert previo == expected_previo == Decimal("7237.09")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "644.3",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="644.3",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("644.3"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="644.3")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestMasasFritas6446EstimacionObjetiva:
    """Epígrafe IAE 644.6 (Comercio al por menor de masas fritas, patatas fritas y similares)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado de fabricación, 1 resto personal asalariado.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "644.6",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _MASAS_FRITAS_644_6[1] + Decimal("1") * _MASAS_FRITAS_644_6[2],
        )
        assert previo == expected_previo == Decimal("9107.78")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "644.6",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="644.6",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("644.6"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="644.6")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestAutoservicio6472EstimacionObjetiva:
    """Epígrafe IAE 647.2 y 3 (Comercio al por menor de alimentación en autoservicio < 400 m2)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 30 m2 superficie del local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "647.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("1") * _AUTOSERVICIO_647_2[1] + Decimal("30") * _AUTOSERVICIO_647_2[3],
        )
        assert previo == expected_previo == Decimal("2488.10")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "647.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="647.2",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("647.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="647.2")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestLenceria6513EstimacionObjetiva:
    """Epígrafe IAE 651.3 y 5 (Comercio al por menor de lencería, corsetería) — corpus-typo correction."""

    def test_fase_1_rendimiento_neto_previo_matches_manual_correction_not_orden_typo(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado. Proves the registry
        # holds the AEAT Manual's "11.998,85" figure, not the bundled Orden
        # HTML's literal typo "11.998.85".
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "651.3",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _LENCERIA_651_3[1] + Decimal("1") * _LENCERIA_651_3[2],
        )
        assert previo == expected_previo == Decimal("14197.06")


class TestTextil6511EstimacionObjetiva:
    """Epígrafe IAE 651.1 (Comercio al por menor de productos textiles)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 20 m2 local independiente.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "651.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _TEXTIL_651_1[1] + Decimal("1") * _TEXTIL_651_1[2] + Decimal("20") * _TEXTIL_651_1[4],
        )
        assert previo == expected_previo == Decimal("17529.19")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "651.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="651.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("651.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="651.1")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestMuebles6531EstimacionObjetiva:
    """Epígrafe IAE 653.1 (Comercio al por menor de muebles)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 30 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "653.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("1") * _MUEBLES_653_1[1] + Decimal("1") * _MUEBLES_653_1[2] + Decimal("30") * _MUEBLES_653_1[4],
        )
        assert previo == expected_previo == Decimal("20766.62")


class TestRecambios6542EstimacionObjetiva:
    """Epígrafe IAE 654.2 (Comercio al por menor de accesorios y piezas de recambio para vehículos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 10 CVF potencia fiscal vehículo.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "654.2",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("10"),
        )
        expected_previo = _quantize(
            Decimal("1") * _RECAMBIOS_654_2[1] + Decimal("10") * _RECAMBIOS_654_2[4],
        )
        assert previo == expected_previo == Decimal("9271.52")


class TestOptica6593EstimacionObjetiva:
    """Epígrafe IAE 659.3 (Comercio al por menor de aparatos e instrumentos ópticos y fotográficos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "659.3",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _OPTICA_659_3[1] + Decimal("1") * _OPTICA_659_3[2],
        )
        assert previo == expected_previo == Decimal("26447.86")


class TestAmbulanteAlimentacion6631EstimacionObjetiva:
    """Epígrafe IAE 663.1 (Comercio ambulante de productos alimenticios)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 2 CVF potencia fiscal vehículo.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "663.1",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("2"),
        )
        expected_previo = _quantize(
            Decimal("1") * _AMBULANTE_ALIMENTACION_663_1[1] + Decimal("2") * _AMBULANTE_ALIMENTACION_663_1[3],
        )
        assert previo == expected_previo == Decimal("1625.03")


class TestHospedajeHotel681EstimacionObjetiva:
    """Epígrafe IAE 681 (Servicio de hospedaje en hoteles y moteles de una o dos estrellas)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 20 plazas.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "681",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _HOSPEDAJE_HOTEL_681[1]
            + Decimal("1") * _HOSPEDAJE_HOTEL_681[2]
            + Decimal("20") * _HOSPEDAJE_HOTEL_681[3],
        )
        assert previo == expected_previo == Decimal("34094.40")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "681",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="681",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("681"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="681")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestReparacionVehiculos6912EstimacionObjetiva:
    """Epígrafe IAE 691.2 (Reparación de vehículos automóviles, bicicletas y otros)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 30 m2 superficie del local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "691.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("1") * _REPARACION_VEHICULOS_691_2[1] + Decimal("30") * _REPARACION_VEHICULOS_691_2[3],
        )
        assert previo == expected_previo == Decimal("4969.48")


class TestTransporteUrbano7211EstimacionObjetiva:
    """Epígrafe IAE 721.1 y 3 (Transporte urbano colectivo y de viajeros por carretera)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 30 asientos.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "721.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("2") * _TRANSPORTE_URBANO_721_1[1]
            + Decimal("1") * _TRANSPORTE_URBANO_721_1[2]
            + Decimal("30") * _TRANSPORTE_URBANO_721_1[3],
        )
        assert previo == expected_previo == Decimal("25621.01")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "721.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="721.1",
            modulo_1=Decimal("2"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("721.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="721.1")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestPapeleria6594AEstimacionObjetiva:
    """Epígrafe IAE 659.4a (Comercio al por menor de libros, periódicos, papelería...)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 20 (100 kWh),
        # 15 m2 local, 1 vehículo (CVF).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "659.4a",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
            modulo_4=Decimal("15"),
            modulo_5=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _PAPELERIA_659_4A[1]
            + Decimal("1") * _PAPELERIA_659_4A[2]
            + Decimal("20") * _PAPELERIA_659_4A[3]
            + Decimal("15") * _PAPELERIA_659_4A[4]
            + Decimal("1") * _PAPELERIA_659_4A[5],
        )
        assert previo == expected_previo == Decimal("23981.75")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "659.4a",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
            modulo_4=Decimal("15"),
            modulo_5=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="659.4a",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("659.4a"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="659.4a")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestQuioscosPrensa6594BEstimacionObjetiva:
    """Epígrafe IAE 659.4b (Comercio al por menor de prensa, revistas y libros en quioscos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 10 (100 kWh), 4 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "659.4b",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
            modulo_4=Decimal("4"),
        )
        expected_previo = _quantize(
            Decimal("1") * _QUIOSCOS_PRENSA_659_4B[2]
            + Decimal("10") * _QUIOSCOS_PRENSA_659_4B[3]
            + Decimal("4") * _QUIOSCOS_PRENSA_659_4B[4],
        )
        assert previo == expected_previo == Decimal("24627.57")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "659.4b",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
            modulo_4=Decimal("4"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="659.4b",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("659.4b"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="659.4b")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad

    def test_bare_unsuffixed_epigrafe_collision_code_stays_untabled(self) -> None:
        # The bare "659.4" (no "a"/"b" disambiguating suffix) must NOT resolve
        # to either collision activity's coefficients — a lookup on the
        # unsuffixed code would silently misattribute one activity's figures
        # to the other. It stays untabled behind the advisory guard.
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "659.4", modulo_1=Decimal("1"), modulo_2=Decimal("1")
        )
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")


class TestReparacionCalzado6919AEstimacionObjetiva:
    """Epígrafe IAE 691.9a (Reparación de calzado)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 20 (100 kWh).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "691.9a",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _REPARACION_CALZADO_691_9A[2] + Decimal("20") * _REPARACION_CALZADO_691_9A[3],
        )
        assert previo == expected_previo == Decimal("12534.18")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "691.9a",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="691.9a",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("691.9a"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="691.9a")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestReparacionOtrosBienes6919BEstimacionObjetiva:
    """Epígrafe IAE 691.9b (Reparación de otros bienes de consumo n.c.o.p.)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 25 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "691.9b",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("25"),
        )
        expected_previo = _quantize(
            Decimal("1") * _REPARACION_OTROS_BIENES_691_9B[1] + Decimal("25") * _REPARACION_OTROS_BIENES_691_9B[3],
        )
        assert previo == expected_previo == Decimal("5227.85")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "691.9b",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("25"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="691.9b",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("691.9b"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="691.9b")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad

    def test_bare_unsuffixed_epigrafe_collision_code_stays_untabled(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "691.9", modulo_1=Decimal("1"), modulo_2=Decimal("1")
        )
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")


class TestEngraseLavado7515EstimacionObjetiva:
    """Epígrafe IAE 751.5 (Engrase y lavado de vehículos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 40 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "751.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = _quantize(
            Decimal("1") * _ENGRASE_LAVADO_751_5[1]
            + Decimal("1") * _ENGRASE_LAVADO_751_5[2]
            + Decimal("40") * _ENGRASE_LAVADO_751_5[3],
        )
        assert previo == expected_previo == Decimal("25068.33")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "751.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="751.5",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("751.5"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="751.5")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestMudanzas757EstimacionObjetiva:
    """Epígrafe IAE 757 (Servicios de mudanzas)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 15 toneladas carga vehículos.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "757",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("15"),
        )
        expected_previo = _quantize(Decimal("1") * _MUDANZAS_757[2] + Decimal("15") * _MUDANZAS_757[3])
        assert previo == expected_previo == Decimal("10896.33")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "757",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("15"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="757",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("757"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="757")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestMensajeria8495EstimacionObjetiva:
    """Epígrafe IAE 849.5 (Transporte de mensajería y recadería con medios propios)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 3 toneladas carga vehículos.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "849.5",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_previo = _quantize(Decimal("1") * _MENSAJERIA_849_5[1] + Decimal("3") * _MENSAJERIA_849_5[3])
        assert previo == expected_previo == Decimal("3107.22")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "849.5",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="849.5",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("849.5"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="849.5")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestAutoescuela9331EstimacionObjetiva:
    """Epígrafe IAE 933.1 (Enseñanza de conducción de vehículos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 2 vehículos, 4 CVF.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "933.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("2"),
            modulo_4=Decimal("4"),
        )
        expected_previo = _quantize(
            Decimal("1") * _AUTOESCUELA_933_1[1]
            + Decimal("1") * _AUTOESCUELA_933_1[2]
            + Decimal("2") * _AUTOESCUELA_933_1[3]
            + Decimal("4") * _AUTOESCUELA_933_1[4],
        )
        assert previo == expected_previo == Decimal("26246.27")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "933.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("2"),
            modulo_4=Decimal("4"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="933.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("933.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="933.1")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestOtrasEnsenanzas9339EstimacionObjetiva:
    """Epígrafe IAE 933.9 (Otras actividades de enseñanza: idiomas, corte y confección, etc.)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 40 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "933.9",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = _quantize(
            Decimal("1") * _OTRAS_ENSENANZAS_933_9[2] + Decimal("40") * _OTRAS_ENSENANZAS_933_9[3],
        )
        assert previo == expected_previo == Decimal("18222.02")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "933.9",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="933.9",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("933.9"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="933.9")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestEscuelasDeporte9672EstimacionObjetiva:
    """Epígrafe IAE 967.2 (Escuelas y servicios de perfeccionamiento del deporte)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 60 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "967.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("60"),
        )
        expected_previo = _quantize(
            Decimal("1") * _ESCUELAS_DEPORTE_967_2[1] + Decimal("60") * _ESCUELAS_DEPORTE_967_2[3],
        )
        assert previo == expected_previo == Decimal("9076.15")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "967.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("60"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="967.2",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("967.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="967.2")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestTintoreria9711EstimacionObjetiva:
    """Epígrafe IAE 971.1 (Tinte, limpieza en seco, lavado y planchado)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 30 (100 kWh).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "971.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("1") * _TINTORERIA_971_1[1]
            + Decimal("1") * _TINTORERIA_971_1[2]
            + Decimal("30") * _TINTORERIA_971_1[3],
        )
        assert previo == expected_previo == Decimal("22706.49")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "971.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="971.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("971.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="971.1")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestInstitutosBelleza9722EstimacionObjetiva:
    """Epígrafe IAE 972.2 (Salones e institutos de belleza)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 40 m2 local, 20 (100 kWh).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "972.2",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
            modulo_4=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _INSTITUTOS_BELLEZA_972_2[2]
            + Decimal("40") * _INSTITUTOS_BELLEZA_972_2[3]
            + Decimal("20") * _INSTITUTOS_BELLEZA_972_2[4],
        )
        assert previo == expected_previo == Decimal("19532.01")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "972.2",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
            modulo_4=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="972.2",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("972.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="972.2")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestCopisteria9733EstimacionObjetiva:
    """Epígrafe IAE 973.3 (Servicios de copias de documentos con máquinas fotocopiadoras)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 3 KW contratado.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "973.3",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_previo = _quantize(Decimal("1") * _COPISTERIA_973_3[2] + Decimal("3") * _COPISTERIA_973_3[3])
        assert previo == expected_previo == Decimal("18669.07")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "973.3",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="973.3",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("973.3"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="973.3")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestFrutasVerduras641EstimacionObjetiva:
    """Epígrafe IAE 641 (Comercio al por menor de frutas, verduras, hortalizas y tubérculos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 30 m2 local
        # independiente, 500 kg carga elementos de transporte.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "641",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
            modulo_5=Decimal("500"),
        )
        expected_previo = _quantize(
            Decimal("1") * _FRUTAS_VERDURAS_641[1]
            + Decimal("1") * _FRUTAS_VERDURAS_641[2]
            + Decimal("30") * _FRUTAS_VERDURAS_641[3]
            + Decimal("500") * _FRUTAS_VERDURAS_641[5],
        )
        assert previo == expected_previo == Decimal("15212.04")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "641",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
            modulo_5=Decimal("500"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="641",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("641"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="641")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestQuioscosServicios675EstimacionObjetiva:
    """Epígrafe IAE 675 (Servicios en quioscos, cajones, barracas u otros locales análogos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 5 KW contratado, 10 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "675",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("5"),
            modulo_4=Decimal("10"),
        )
        expected_previo = _quantize(
            Decimal("1") * _QUIOSCOS_SERVICIOS_675[2]
            + Decimal("5") * _QUIOSCOS_SERVICIOS_675[3]
            + Decimal("10") * _QUIOSCOS_SERVICIOS_675[4],
        )
        assert previo == expected_previo == Decimal("15261.45")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "675",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("5"),
            modulo_4=Decimal("10"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="675",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("675"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="675")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestChocolaterias676EstimacionObjetiva:
    """Epígrafe IAE 676 (Servicios en chocolaterías, heladerías y horchaterías)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 3 KW contratado, 5 mesas, 1 máquina tipo A.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "676",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
            modulo_4=Decimal("5"),
            modulo_5=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _CHOCOLATERIAS_676[1]
            + Decimal("3") * _CHOCOLATERIAS_676[3]
            + Decimal("5") * _CHOCOLATERIAS_676[4]
            + Decimal("1") * _CHOCOLATERIAS_676[5],
        )
        assert previo == expected_previo == Decimal("5952.19")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "676",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
            modulo_4=Decimal("5"),
            modulo_5=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="676",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("676"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="676")
        expected_actividad = _money_round(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestModulosEngineNoSilentFabrication:
    """no-silent-under-declaration guard: an untabled epígrafe never fabricates a figure."""

    def test_untabled_epigrafe_resolves_to_zero_not_fabricated_figure(self) -> None:
        # A large positive unit count against an activity absent from the
        # bounded first-slice coefficient table must NOT be silently
        # multiplied by a wrong or absent coefficient; the internal
        # reference casilla resolves to zero, and the operator-declared
        # casilla 01 remains the authoritative manual input.
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "699.9",  # not an Orden Anexo II epígrafe — remains untabled
            modulo_1=Decimal("5"),
            modulo_2=Decimal("3"),
        )
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")

    def test_blank_epigrafe_resolves_to_zero(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(None, modulo_1=Decimal("5"))
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")

    def test_zero_units_on_tabled_epigrafe_resolves_to_zero(self) -> None:
        # A tabled epígrafe with no units declared (e.g. no activity conducted
        # yet this period) legitimately resolves to zero — not a silent-zero
        # violation, since the antecedent itself is zero.
        previo, minorado, modulos, actividad = _run_modulos_engine("972.1")
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")


class TestModulosIndicesCorrectoresGenerales:
    """Fase 3ª índices correctores generales cascade (b.1, b.2, b.3, b.4).

    Grounded in Orden HAC/1347/2024 Anexo II, instrucción 2.3 (bundled
    ``orden-hac-1347-2024.html`` corpus) and cross-checked against the AEAT
    Manual práctico de Renta 2025, Parte 1, Capítulo 8 (same índice values
    and the same three incompatibilidades quoted verbatim). Uses the same
    673.1 base as ``TestCafesEspecial6731EstimacionObjetiva``'s full manual
    worked example so the b.1/b.2/b.4 additions can be verified against a
    figure (Fase 1ª/2ª) already independently proven correct.
    """

    def _run_673_1(self, **kwargs: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        return _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("3.66"),
            modulo_2=Decimal("1.00"),
            modulo_3=Decimal("35.00"),
            modulo_4=Decimal("8.00"),
            modulo_5=Decimal("10.00"),
            modulo_7=Decimal("1.00"),
            modulo_1_anterior=Decimal("3.00"),
            minoracion_inversion=Decimal("6050.00"),
            **kwargs,
        )

    def test_no_indices_generales_declared_matches_b3_only_baseline(self) -> None:
        """No b.1/b.2/b.4 declared reproduces the pre-existing b.3-only manual figure exactly."""
        _previo, minorado, modulos, _actividad = self._run_673_1()
        assert minorado == Decimal("41368.57")
        assert modulos == Decimal("44603.33")
        expected = _expected_modulos_generales(minorado, epigrafe="673.1")
        assert modulos == expected

    def test_pequena_dimension_applies_multiplicatively_and_excludes_indice_exceso(self) -> None:
        """b.1 (0,80) applies to minorado; b.3 (índice de exceso) is then excluded outright."""
        _previo, minorado, modulos, _actividad = self._run_673_1(
            indice_pequena_dimension=Decimal("0.80"),
        )
        expected = _expected_modulos_generales(minorado, epigrafe="673.1", pequena_dimension=Decimal("0.80"))
        assert modulos == expected == Decimal("33094.86")
        # Confirms b.3 was skipped: a naive product with the manual's own
        # índice-exceso figure would be far higher than the plain 0,80 product.
        assert modulos == _money_round(minorado * Decimal("0.80"))

    def test_pequena_dimension_ignored_for_autotaxi_especial_epigrafe(self) -> None:
        """b.1 is IGNORED (never applied) for an epígrafe carrying a documented índice especial (721.2)."""
        previo, minorado, modulos, _actividad = _run_modulos_engine(
            "721.2",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("900"),
            indice_pequena_dimension=Decimal("0.80"),
        )
        expected_previo = _quantize(Decimal("1") * _AUTOTAXI_721_2[2] + Decimal("900") * _AUTOTAXI_721_2[3])
        assert previo == expected_previo
        # b.1 ignored -> b.3 índice de exceso still applies to the plain minorado.
        expected = _expected_modulos_generales(minorado, epigrafe="721.2", pequena_dimension=Decimal("0.80"))
        assert modulos == expected == _expected_modulos(minorado, epigrafe="721.2")

    def test_pequena_dimension_ignored_for_mercancias_especial_epigrafe(self) -> None:
        """b.1 is IGNORED (never applied) for an epígrafe carrying a documented índice especial (722)."""
        _previo, minorado, modulos, _actividad = _run_modulos_engine(
            "722",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("800"),
            indice_pequena_dimension=Decimal("0.75"),
        )
        expected = _expected_modulos_generales(minorado, epigrafe="722", pequena_dimension=Decimal("0.75"))
        assert modulos == expected == _expected_modulos(minorado, epigrafe="722")

    def test_temporada_applies_multiplicatively_before_indice_exceso(self) -> None:
        """b.2 (temporada) applies to minorado before b.3 evaluates the (adjusted) excess."""
        _previo, minorado, modulos, _actividad = self._run_673_1(indice_temporada=Decimal("1.50"))
        expected = _expected_modulos_generales(minorado, epigrafe="673.1", temporada=Decimal("1.50"))
        assert modulos == expected

    def test_inicio_actividad_applies_when_temporada_absent(self) -> None:
        """b.4 (inicio de nuevas actividades) applies when temporada is not declared."""
        _previo, minorado, modulos, _actividad = self._run_673_1(indice_inicio_actividad=Decimal("0.80"))
        expected = _expected_modulos_generales(minorado, epigrafe="673.1", inicio_actividad=Decimal("0.80"))
        assert modulos == expected

    def test_temporada_and_inicio_actividad_declared_together_temporada_wins(self) -> None:
        """b.2 and b.4 are mutually exclusive; temporada (enumeration order) wins, inicio is ignored."""
        _previo, minorado, modulos_both, _actividad = self._run_673_1(
            indice_temporada=Decimal("1.50"),
            indice_inicio_actividad=Decimal("0.80"),
        )
        _previo2, minorado2, modulos_temporada_only, _actividad2 = self._run_673_1(
            indice_temporada=Decimal("1.50"),
        )
        assert minorado == minorado2
        assert modulos_both == modulos_temporada_only
        expected = _expected_modulos_generales(minorado, epigrafe="673.1", temporada=Decimal("1.50"))
        assert modulos_both == expected

    def test_blank_indices_generales_never_fabricate_a_factor(self) -> None:
        """A blank/zero b.1/b.2/b.4 input never fabricates a factor (baseline unchanged)."""
        _previo, minorado, modulos, _actividad = self._run_673_1(
            indice_pequena_dimension=Decimal("0"),
            indice_temporada=Decimal("0"),
            indice_inicio_actividad=Decimal("0"),
        )
        assert modulos == _expected_modulos(minorado, epigrafe="673.1") == Decimal("44603.33")

    def test_non_positive_minorado_never_receives_indices_generales(self) -> None:
        """A non-positive rendimiento neto minorado skips the whole cascade (mirrors the b.3-only guard)."""
        _previo, minorado, modulos, _actividad = _run_modulos_engine(
            "972.1",
            indice_pequena_dimension=Decimal("0.80"),
            indice_temporada=Decimal("1.50"),
        )
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")


class TestModulosIndicesGeneralesAdvisoryFlags:
    """The pequeña-dimensión-ignorado and temporada/inicio-conflicto advisory-support flags."""

    def test_pequena_dimension_ignorado_flag_fires_on_especial_epigrafe(self) -> None:
        snapshot = _committed_snapshot("131", 2025, "1T")
        assert snapshot.filing_period is not None
        result = calculate_registry_snapshot(
            snapshot,
            inputs={
                "modulos-2-unidades": Decimal("1"),
                "modulos-3-unidades": Decimal("900"),
                "modulos-indice-pequena-dimension": Decimal("0.80"),
            },
            text_inputs={"modulos-epigrafe": "721.2"},
            date_context={"filing_period": snapshot.filing_period.end_date},
        )
        assert result.values["modulos-pequena-dimension-ignorado-flag"] == Decimal("1")

    def test_pequena_dimension_ignorado_flag_stays_zero_on_ordinary_epigrafe(self) -> None:
        snapshot = _committed_snapshot("131", 2025, "1T")
        assert snapshot.filing_period is not None
        result = calculate_registry_snapshot(
            snapshot,
            inputs={
                "modulos-1-unidades": Decimal("2"),
                "modulos-indice-pequena-dimension": Decimal("0.80"),
            },
            text_inputs={"modulos-epigrafe": "972.1"},
            date_context={"filing_period": snapshot.filing_period.end_date},
        )
        assert result.values["modulos-pequena-dimension-ignorado-flag"] == Decimal("0")

    def test_pequena_dimension_ignorado_flag_stays_zero_when_not_declared(self) -> None:
        snapshot = _committed_snapshot("131", 2025, "1T")
        assert snapshot.filing_period is not None
        result = calculate_registry_snapshot(
            snapshot,
            inputs={"modulos-2-unidades": Decimal("1"), "modulos-3-unidades": Decimal("900")},
            text_inputs={"modulos-epigrafe": "721.2"},
            date_context={"filing_period": snapshot.filing_period.end_date},
        )
        assert result.values["modulos-pequena-dimension-ignorado-flag"] == Decimal("0")

    def test_temporada_inicio_conflicto_flag_fires_when_both_declared(self) -> None:
        snapshot = _committed_snapshot("131", 2025, "1T")
        assert snapshot.filing_period is not None
        result = calculate_registry_snapshot(
            snapshot,
            inputs={
                "modulos-1-unidades": Decimal("1"),
                "modulos-indice-temporada": Decimal("1.50"),
                "modulos-indice-inicio-actividad": Decimal("0.80"),
            },
            text_inputs={"modulos-epigrafe": "673.1"},
            date_context={"filing_period": snapshot.filing_period.end_date},
        )
        assert result.values["modulos-temporada-inicio-actividad-conflicto-flag"] == Decimal("1")

    def test_temporada_inicio_conflicto_flag_stays_zero_when_only_one_declared(self) -> None:
        snapshot = _committed_snapshot("131", 2025, "1T")
        assert snapshot.filing_period is not None
        result = calculate_registry_snapshot(
            snapshot,
            inputs={"modulos-1-unidades": Decimal("1"), "modulos-indice-temporada": Decimal("1.50")},
            text_inputs={"modulos-epigrafe": "673.1"},
            date_context={"filing_period": snapshot.filing_period.end_date},
        )
        assert result.values["modulos-temporada-inicio-actividad-conflicto-flag"] == Decimal("0")
