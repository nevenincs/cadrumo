"""Modelo 131 módulos engine retail, repair, transport, and service activity cases.

See Also:
    :mod:`~domain.calculations.registry.tests._modelo_131_modulos_engine_support`
        Shared independent coefficient tables and oracle arithmetic.
    :mod:`~domain.calculations.registry._formula_runtime_m131`
        Extracted M131 módulos formula evaluators exercised here.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Registry runtime entry point reached through ``_run_modulos_engine``.
    :class:`~domain.calculations.registry.ParameterDefinition`
        Registry-authored coefficient and índice tables cross-checked by these
        cases.
    :mod:`~domain.calculations.registry.tests.test_modelo_131_modulos_engine_food`
        Sibling food and hospitality activity split using the same helper
        oracle.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.money.rounding import round_to_cents
from ._modelo_131_modulos_engine_support import (
    _AMBULANTE_ALIMENTACION_663_1,
    _AUTOESCUELA_933_1,
    _CHOCOLATERIAS_676,
    _COPISTERIA_973_3,
    _ENGRASE_LAVADO_751_5,
    _ESCUELAS_DEPORTE_967_2,
    _FRUTAS_VERDURAS_641,
    _HOSPEDAJE_HOTEL_681,
    _INSTITUTOS_BELLEZA_972_2,
    _LENCERIA_651_3,
    _MENSAJERIA_849_5,
    _MUDANZAS_757,
    _MUEBLES_653_1,
    _OPTICA_659_3,
    _OTRAS_ENSENANZAS_933_9,
    _PAPELERIA_659_4A,
    _QUIOSCOS_PRENSA_659_4B,
    _QUIOSCOS_SERVICIOS_675,
    _RECAMBIOS_654_2,
    _REPARACION_CALZADO_691_9A,
    _REPARACION_OTROS_BIENES_691_9B,
    _REPARACION_VEHICULOS_691_2,
    _TEXTIL_651_1,
    _TINTORERIA_971_1,
    _TRANSPORTE_URBANO_721_1,
    _assert_fase4_reduccion_general,
    _run_modulos_engine,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
        expected_previo = round_to_cents(
            Decimal("1") * _LENCERIA_651_3[1] + Decimal("1") * _LENCERIA_651_3[2],
        )
        assert previo == expected_previo == Decimal("14197.06")


#: Fase 1ª clone-collapsed dataset for the retail/repair/transport/service
#: split — each entry was a separate hand-forked
#: ``TestXxxEstimacionObjetiva.test_fase_1_...`` method (identical body,
#: differing only by epígrafe, coefficient table, módulo units and expected
#: figure) before the AST clone scan flagged them. ``id=`` carries the IAE
#: epígrafe citation the removed class docstring held.
_FASE_1_CASES = [
    pytest.param(
        "651.1",
        _TEXTIL_651_1,
        {1: Decimal("1"), 2: Decimal("1"), 4: Decimal("20")},
        Decimal("17529.19"),
        id="651.1-comercio-al-por-menor-de-productos-textiles",
    ),
    pytest.param(
        "653.1",
        _MUEBLES_653_1,
        {1: Decimal("1"), 2: Decimal("1"), 4: Decimal("30")},
        Decimal("20766.62"),
        id="653.1-comercio-al-por-menor-de-muebles",
    ),
    pytest.param(
        "654.2",
        _RECAMBIOS_654_2,
        {1: Decimal("1"), 4: Decimal("10")},
        Decimal("9271.52"),
        id="654.2-comercio-al-por-menor-de-recambios-vehiculos",
    ),
    pytest.param(
        "659.3",
        _OPTICA_659_3,
        {1: Decimal("1"), 2: Decimal("1")},
        Decimal("26447.86"),
        id="659.3-comercio-al-por-menor-de-aparatos-opticos-y-fotograficos",
    ),
    pytest.param(
        "663.1",
        _AMBULANTE_ALIMENTACION_663_1,
        {1: Decimal("1"), 3: Decimal("2")},
        Decimal("1625.03"),
        id="663.1-comercio-ambulante-de-productos-alimenticios",
    ),
    pytest.param(
        "681",
        _HOSPEDAJE_HOTEL_681,
        {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("20")},
        Decimal("34094.40"),
        id="681-hospedaje-en-hoteles-y-moteles-de-una-o-dos-estrellas",
    ),
    pytest.param(
        "691.2",
        _REPARACION_VEHICULOS_691_2,
        {1: Decimal("1"), 3: Decimal("30")},
        Decimal("4969.48"),
        id="691.2-reparacion-de-vehiculos-automoviles-bicicletas-y-otros",
    ),
    pytest.param(
        "721.1",
        _TRANSPORTE_URBANO_721_1,
        {1: Decimal("2"), 2: Decimal("1"), 3: Decimal("30")},
        Decimal("25621.01"),
        id="721.1-transporte-urbano-colectivo-y-de-viajeros-por-carretera",
    ),
    pytest.param(
        "659.4a",
        _PAPELERIA_659_4A,
        {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("20"), 4: Decimal("15"), 5: Decimal("1")},
        Decimal("23981.75"),
        id="659.4a-comercio-al-por-menor-de-libros-periodicos-papeleria",
    ),
    pytest.param(
        "659.4b",
        _QUIOSCOS_PRENSA_659_4B,
        {2: Decimal("1"), 3: Decimal("10"), 4: Decimal("4")},
        Decimal("24627.57"),
        id="659.4b-comercio-al-por-menor-de-prensa-revistas-y-libros-en-quioscos",
    ),
    pytest.param(
        "691.9a",
        _REPARACION_CALZADO_691_9A,
        {2: Decimal("1"), 3: Decimal("20")},
        Decimal("12534.18"),
        id="691.9a-reparacion-de-calzado",
    ),
    pytest.param(
        "691.9b",
        _REPARACION_OTROS_BIENES_691_9B,
        {1: Decimal("1"), 3: Decimal("25")},
        Decimal("5227.85"),
        id="691.9b-reparacion-de-otros-bienes-de-consumo-ncop",
    ),
    pytest.param(
        "751.5",
        _ENGRASE_LAVADO_751_5,
        {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("40")},
        Decimal("25068.33"),
        id="751.5-engrase-y-lavado-de-vehiculos",
    ),
    pytest.param(
        "757",
        _MUDANZAS_757,
        {2: Decimal("1"), 3: Decimal("15")},
        Decimal("10896.33"),
        id="757-servicios-de-mudanzas",
    ),
    pytest.param(
        "849.5",
        _MENSAJERIA_849_5,
        {1: Decimal("1"), 3: Decimal("3")},
        Decimal("3107.22"),
        id="849.5-transporte-de-mensajeria-y-recaderia-con-medios-propios",
    ),
    pytest.param(
        "933.1",
        _AUTOESCUELA_933_1,
        {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("2"), 4: Decimal("4")},
        Decimal("26246.27"),
        id="933.1-ensenanza-de-conduccion-de-vehiculos",
    ),
    pytest.param(
        "933.9",
        _OTRAS_ENSENANZAS_933_9,
        {2: Decimal("1"), 3: Decimal("40")},
        Decimal("18222.02"),
        id="933.9-otras-actividades-de-ensenanza",
    ),
    pytest.param(
        "967.2",
        _ESCUELAS_DEPORTE_967_2,
        {1: Decimal("1"), 3: Decimal("60")},
        Decimal("9076.15"),
        id="967.2-escuelas-y-servicios-de-perfeccionamiento-del-deporte",
    ),
    pytest.param(
        "971.1",
        _TINTORERIA_971_1,
        {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("30")},
        Decimal("22706.49"),
        id="971.1-tinte-limpieza-en-seco-lavado-y-planchado",
    ),
    pytest.param(
        "972.2",
        _INSTITUTOS_BELLEZA_972_2,
        {2: Decimal("1"), 3: Decimal("40"), 4: Decimal("20")},
        Decimal("19532.01"),
        id="972.2-salones-e-institutos-de-belleza",
    ),
    pytest.param(
        "973.3",
        _COPISTERIA_973_3,
        {2: Decimal("1"), 3: Decimal("3")},
        Decimal("18669.07"),
        id="973.3-servicios-de-copias-con-maquinas-fotocopiadoras",
    ),
    pytest.param(
        "675",
        _QUIOSCOS_SERVICIOS_675,
        {2: Decimal("1"), 3: Decimal("5"), 4: Decimal("10")},
        Decimal("15261.45"),
        id="675-servicios-en-quioscos-cajones-barracas",
    ),
]

#: Fase 4ª (5% reducción general) clone-collapsed dataset — same módulo units
#: as the matching Fase 1ª case above, for the subset of epígrafes that also
#: carried a hand-forked fase_4 clone.
_FASE_4_CASES = [
    pytest.param("651.1", {1: Decimal("1"), 2: Decimal("1"), 4: Decimal("20")}, id="651.1-textil"),
    pytest.param("681", {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("20")}, id="681-hospedaje-hotel"),
    pytest.param("721.1", {1: Decimal("2"), 2: Decimal("1"), 3: Decimal("30")}, id="721.1-transporte-urbano"),
    pytest.param(
        "659.4a",
        {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("20"), 4: Decimal("15"), 5: Decimal("1")},
        id="659.4a-papeleria",
    ),
    pytest.param("659.4b", {2: Decimal("1"), 3: Decimal("10"), 4: Decimal("4")}, id="659.4b-quioscos-prensa"),
    pytest.param("691.9a", {2: Decimal("1"), 3: Decimal("20")}, id="691.9a-reparacion-calzado"),
    pytest.param("691.9b", {1: Decimal("1"), 3: Decimal("25")}, id="691.9b-reparacion-otros-bienes"),
    pytest.param("751.5", {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("40")}, id="751.5-engrase-lavado"),
    pytest.param("757", {2: Decimal("1"), 3: Decimal("15")}, id="757-mudanzas"),
    pytest.param("849.5", {1: Decimal("1"), 3: Decimal("3")}, id="849.5-mensajeria"),
    pytest.param("933.1", {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("2"), 4: Decimal("4")}, id="933.1-autoescuela"),
    pytest.param("933.9", {2: Decimal("1"), 3: Decimal("40")}, id="933.9-otras-ensenanzas"),
    pytest.param("967.2", {1: Decimal("1"), 3: Decimal("60")}, id="967.2-escuelas-deporte"),
    pytest.param("971.1", {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("30")}, id="971.1-tintoreria"),
    pytest.param("972.2", {2: Decimal("1"), 3: Decimal("40"), 4: Decimal("20")}, id="972.2-institutos-belleza"),
    pytest.param("973.3", {2: Decimal("1"), 3: Decimal("3")}, id="973.3-copisteria"),
    pytest.param("675", {2: Decimal("1"), 3: Decimal("5"), 4: Decimal("10")}, id="675-quioscos-servicios"),
]


@pytest.mark.parametrize(("epigrafe", "table", "modulos", "expected_previo"), _FASE_1_CASES)
def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(
    epigrafe: str,
    table: dict[int, Decimal],
    modulos: dict[int, Decimal],
    expected_previo: Decimal,
) -> None:
    previo, _minorado, _modulos, _actividad = _run_modulos_engine(
        epigrafe,
        **{f"modulo_{idx}": units for idx, units in modulos.items()},
    )
    expected = round_to_cents(sum((units * table[idx] for idx, units in modulos.items()), start=Decimal("0")))
    assert previo == expected == expected_previo


@pytest.mark.parametrize(("epigrafe", "modulos"), _FASE_4_CASES)
def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(
    epigrafe: str,
    modulos: dict[int, Decimal],
) -> None:
    _assert_fase4_reduccion_general(epigrafe, **{f"modulo_{idx}": units for idx, units in modulos.items()})


@pytest.mark.parametrize(
    "epigrafe",
    [
        pytest.param("659.4", id="659.4-quioscos-prensa-vs-papeleria-ab-suffix-collision"),
        pytest.param("691.9", id="691.9-reparacion-calzado-vs-otros-bienes-ab-suffix-collision"),
    ],
)
def test_bare_unsuffixed_epigrafe_collision_code_stays_untabled(epigrafe: str) -> None:
    # The bare epígrafe (no "a"/"b" disambiguating suffix) must NOT resolve to
    # either collision activity's coefficients — a lookup on the unsuffixed
    # code would silently misattribute one activity's figures to the other.
    # It stays untabled behind the advisory guard.
    previo, minorado, modulos, actividad = _run_modulos_engine(epigrafe, modulo_1=Decimal("1"), modulo_2=Decimal("1"))
    assert previo == Decimal("0")
    assert minorado == Decimal("0")
    assert modulos == Decimal("0")
    assert actividad == Decimal("0")


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
        expected_previo = round_to_cents(
            Decimal("1") * _FRUTAS_VERDURAS_641[1]
            + Decimal("1") * _FRUTAS_VERDURAS_641[2]
            + Decimal("30") * _FRUTAS_VERDURAS_641[3]
            + Decimal("500") * _FRUTAS_VERDURAS_641[5],
        )
        assert previo == expected_previo == Decimal("15212.04")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        _assert_fase4_reduccion_general(
            "641",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
            modulo_5=Decimal("500"),
        )


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
        expected_previo = round_to_cents(
            Decimal("1") * _CHOCOLATERIAS_676[1]
            + Decimal("3") * _CHOCOLATERIAS_676[3]
            + Decimal("5") * _CHOCOLATERIAS_676[4]
            + Decimal("1") * _CHOCOLATERIAS_676[5],
        )
        assert previo == expected_previo == Decimal("5952.19")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        _assert_fase4_reduccion_general(
            "676",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
            modulo_4=Decimal("5"),
            modulo_5=Decimal("1"),
        )
