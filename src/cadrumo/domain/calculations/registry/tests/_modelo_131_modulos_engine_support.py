"""Shared fixtures and oracle helpers for Modelo 131 módulos engine tests.

See Also:
    :mod:`~domain.calculations.registry._formula_runtime_m131`
        Extracted M131 módulos formula evaluators under test.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Registry runtime entry point exercised by the helper.
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_snapshot`
        Bundled-registry fixture that supplies the Modelo 131 2025 snapshot.
    :class:`~domain.calculations.registry.ParameterDefinition`
        Registry table rows mirrored by these independently transcribed
        expected-value helpers.
    :mod:`~domain.calculations.registry.tests.test_modelo_131_modulos_engine`
        Core phased dataset using these helpers.
"""

from __future__ import annotations

from decimal import Decimal

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.money.rounding import round_to_cents
from ..formula_runtime import calculate_registry_snapshot
from ._registry_schema_support import _committed_snapshot

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

# Activities not previously covered by a dedicated test, independently
# transcribed from the same bundled Orden Anexo II and cross-checked
# against the AEAT manual.
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

# Remaining next-priority activities: reparaciones,
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
# keyed_bracket_table parameter for the epígrafes tabled so far.
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
    return round_to_cents(previo - minoracion_empleo - minoracion_inversion)


def _expected_modulos(minorado: Decimal, *, epigrafe: str) -> Decimal:
    """Reproduce Fase 3ª (índice corrector de exceso only)."""
    cuantia = _CUANTIA_EXCESO.get(epigrafe)
    if cuantia is None or minorado <= cuantia:
        return minorado
    return round_to_cents(cuantia + _INDICE_EXCESO * (minorado - cuantia))


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
    """Reproduce the full Fase 3ª índices correctores generales cascade.

    Independently transcribed from Orden HAC/1347/2024 Anexo II, instrucción
    2.3's own literal enumeration order — "Los índices correctores se
    aplicarán según el orden que aparecen enumerados a continuación" — b.1
    (empresas de pequeña dimensión), THEN b.2 (temporada), THEN b.3 (exceso),
    THEN b.4 (inicio de nuevas actividades), each applied on the rendimiento
    LEFT BY THE PREVIOUS STEP. This helper is transcribed from the law's own
    textual sequence, not re-derived from (or mirroring the intermediate
    steps of) the ``m131_resolve_modulos_indices_generales`` op under test:
    b.3's exceso threshold is a non-linear piecewise function of its input,
    so applying b.4 before b.3 (as a prior defect in the op under test did)
    yields a materially different, non-commutative result — this oracle
    must reproduce the LAW's order exactly, not any convenient regrouping.
    """
    if minorado <= Decimal("0"):
        return minorado
    aplica_pequena_dimension = pequena_dimension > Decimal("0") and epigrafe not in _EPIGRAFES_INDICE_ESPECIAL
    rendimiento = minorado
    # b.1) empresas de pequeña dimensión.
    if aplica_pequena_dimension:
        rendimiento = rendimiento * pequena_dimension
        # b.1 excludes b.3 outright, and the Orden never reaches b.2/b.4 once
        # b.1 applies.
        return round_to_cents(rendimiento)
    # b.2) temporada — applied BEFORE b.3.
    if temporada > Decimal("0"):
        rendimiento = rendimiento * temporada
    # b.3) exceso — applied on the b.2-rectificado rendimiento.
    cuantia = _CUANTIA_EXCESO.get(epigrafe)
    if cuantia is not None and rendimiento > cuantia:
        rendimiento = cuantia + _INDICE_EXCESO * (rendimiento - cuantia)
    # b.4) inicio de nuevas actividades — applied on the b.3-rectificado
    # rendimiento, and only when b.2 (temporada) is absent (mutual exclusion).
    if temporada <= Decimal("0") and inicio_actividad > Decimal("0"):
        rendimiento = rendimiento * inicio_actividad
    return round_to_cents(rendimiento)


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
    snapshot = _committed_snapshot("131", 2025, "1T", grade=RegistryAuthorityGrade.CALCULATION)
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


def _assert_fase4_reduccion_general(epigrafe: str, **modulos: Decimal) -> None:
    """Assert Fase 4ª (reducción general del 5%, disposición adicional primera).

    Shared body for the per-activity-class ``test_fase_4_...`` method repeated
    verbatim across the M131 módulos-engine suites (base + food +
    retail_services): only Fase 4 is mechanically identical across activity
    classes — Fases 1-3 differ substantively per epígrafe and stay their own
    per-class tests. ``modulos`` forwards the epígrafe's declared módulo unit
    counts (``modulo_1``..``modulo_7``, whichever the epígrafe uses) straight
    through to the real engine and to the Fase 2ª oracle's ``modulo_1``.
    """
    previo, minorado, modulos_value, actividad = _run_modulos_engine(epigrafe, **modulos)
    expected_minorado = _expected_minorado(
        previo,
        epigrafe=epigrafe,
        modulo_1=modulos.get("modulo_1", Decimal("0")),
        modulo_1_anterior=modulos.get("modulo_1_anterior", Decimal("0")),
        modulo_1_coefficient=_module_1_coefficient(epigrafe),
    )
    expected_modulos = _expected_modulos(minorado, epigrafe=epigrafe)
    expected_actividad = round_to_cents(modulos_value - modulos_value * _REDUCCION_GENERAL_2025)
    assert minorado == expected_minorado
    assert modulos_value == expected_modulos
    assert actividad == expected_actividad
