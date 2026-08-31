"""LIRPF legal-corpus catalogue verification tests."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources.bundled_data import bundled_path
from ..legal import verify_legal_catalogue_grounding
from ._catalogue_verification_support import _catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_renta_economic_activity_legal_basis_links_to_corpus() -> None:
    catalogues = _catalogues()

    assert {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }.issubset(catalogues.legal)
    verify_legal_catalogue_grounding(catalogues.legal, source_root=bundled_path())


def _assert_lirpf_reference_links_to_full_boe_corpus(
    ref_id: str,
    effective_from: date,
    required_text: tuple[str, ...],
):
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]
    article = ref_id.rsplit("-", 1)[-1]

    assert reference.corpus_ref == f"corpus/normatives/html/ley-35-2006.html#a{article}", ref_id
    assert reference.effective_from == effective_from, ref_id
    assert reference.required_text == required_text, ref_id
    verify_legal_catalogue_grounding({reference.id: reference}, source_root=bundled_path())
    return reference


def test_lirpf_work_and_capital_income_foundations_link_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-17",
            date(2020, 2, 6),
            (
                "Rendimientos íntegros del trabajo.",
                "contraprestaciones o utilidades",
                "trabajo personal o de la relación laboral o estatutaria",
                "Las pensiones y haberes pasivos percibidos",
                "se calificarán como rendimientos de actividades económicas",
            ),
        ),
        (
            "ley-35-2006:art-18",
            date(2015, 1, 1),
            (
                "Porcentajes de reducción aplicables a determinados rendimientos del trabajo.",
                "El 30 por ciento de reducción",
                "período de generación superior a dos años",
                "300.000 euros anuales",
            ),
        ),
        (
            "ley-35-2006:art-19",
            date(2015, 1, 1),
            (
                "Rendimiento neto del trabajo.",
                "disminuir el rendimiento íntegro en el importe de los gastos deducibles",
                "cotizaciones a la Seguridad Social",
                "gastos de defensa jurídica",
                "2.000 euros anuales",
            ),
        ),
        (
            "ley-35-2006:art-20",
            date(2024, 1, 1),
            (
                "Reducción por obtención de rendimientos del trabajo.",
                "rendimientos netos del trabajo inferiores a 19.747,5 euros",
                "no tengan rentas, excluidas las exentas, distintas de las del trabajo superiores a 6.500 euros",
                "iguales o inferiores a 14.852 euros: 7.302 euros anuales",
                "multiplicar por 1,75 la diferencia",
                "multiplicar por 1,14 la diferencia",
                "el saldo resultante no podrá ser negativo",
            ),
        ),
        (
            "ley-35-2006:art-22",
            date(2007, 1, 1),
            (
                "Rendimientos íntegros del capital inmobiliario.",
                "bienes inmuebles rústicos y urbanos",
                "se deriven del arrendamiento",
                "importe que por todos los conceptos deba satisfacer",
            ),
        ),
        (
            "ley-35-2006:art-23",
            date(2024, 1, 1),
            (
                "Gastos deducibles y reducciones.",
                "gastos necesarios para la obtención de los rendimientos",
                "el 3 por ciento sobre el mayor",
                "el coste de adquisición satisfecho o el valor catastral",
                "En un 90 por ciento",
                "En un 70 por ciento",
                "En un 60 por ciento",
                "En un 50 por ciento",
            ),
        ),
        (
            "ley-35-2006:art-24",
            date(2007, 1, 1),
            (
                "Rendimiento en caso de parentesco.",
                "sea el cónyuge o un pariente",
                "hasta el tercer grado inclusive",
                "no podrá ser inferior al que resulte de las reglas del artículo 85",
            ),
        ),
        (
            "ley-35-2006:art-25",
            date(2015, 1, 1),
            (
                "Rendimientos íntegros del capital mobiliario.",
                "Rendimientos obtenidos por la participación en los fondos propios",
                "Los dividendos",
                "Rendimientos obtenidos por la cesión a terceros de capitales propios",
                "intereses y cualquier otra forma de retribución",
                "Otros rendimientos del capital mobiliario",
            ),
        ),
        (
            "ley-35-2006:art-26",
            date(2015, 1, 1),
            (
                "Gastos deducibles y reducciones.",
                "gastos de administración y depósito de valores negociables",
                "arrendamiento de bienes muebles, negocios o minas",
                "se reducirán en un 30 por ciento",
                "300.000 euros anuales",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        reference = _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)
        if ref_id == "ley-35-2006:art-20":
            assert reference.notes is not None
            assert "effects from 2024-01-01" in reference.notes


def test_lirpf_economic_activity_chapter_links_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-27",
            date(2015, 1, 1),
            (
                "Rendimientos íntegros de actividades económicas",
                "ordenación por cuenta propia de medios de producción",
                "arrendamiento de inmuebles se realiza como actividad económica",
            ),
        ),
        (
            "ley-35-2006:art-28",
            date(2007, 1, 1),
            (
                "Reglas generales de cálculo del rendimiento neto",
                "rendimiento neto de las actividades económicas",
                "según las normas del Impuesto sobre Sociedades",
                "ganancias o pérdidas patrimoniales derivadas de los elementos patrimoniales afectos",
            ),
        ),
        (
            "ley-35-2006:art-30",
            date(2018, 1, 1),
            (
                "Normas para la determinación del rendimiento neto en estimación directa",
                "método de estimación directa",
                "normal y la simplificada",
                "gastos de difícil justificación",
            ),
        ),
        (
            "ley-35-2006:art-31",
            date(2016, 1, 1),
            (
                "Normas para la determinación del rendimiento neto en estimación objetiva",
                "método de estimación objetiva",
                "salvo que renuncien a su aplicación",
                "signos, índices o módulos",
            ),
        ),
        (
            "ley-35-2006:art-32",
            date(2023, 1, 1),
            (
                "Reducciones.",
                "rendimientos netos con un período de generación superior a dos años",
                "el saldo resultante no podrá ser negativo",
                "inicien el ejercicio de una actividad económica",
                "no podrá superar el importe de 300.000 euros anuales",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)


def test_lirpf_capital_gains_foundation_links_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-33",
            date(2015, 1, 1),
            (
                "Concepto.",
                "Son ganancias y pérdidas patrimoniales",
                "variaciones en el valor del patrimonio",
                "alteración en la composición",
                # Art. 33.5.f: a loss is not computable where homogeneous
                # securities were acquired inside the two-month window. It is
                # part of the same article and belongs in its anchor proof, so
                # the pin tracks the entry rather than the entry being trimmed
                # back to match a stale pin.
                "hubiera adquirido valores homogéneos dentro de los dos meses anteriores o posteriores",
            ),
        ),
        (
            "ley-35-2006:art-34",
            date(2007, 1, 1),
            (
                "Importe de las ganancias o pérdidas patrimoniales. Norma general",
                "diferencia entre los valores de adquisición y transmisión",
                "valor de mercado de los elementos patrimoniales",
                "mejoras en los elementos patrimoniales transmitidos",
            ),
        ),
        (
            "ley-35-2006:art-37",
            date(2015, 1, 1),
            (
                "Normas específicas de valoración",
                # LIRPF art. 37.1.a is "valores admitidos a negociación". The
                # "acciones" phrasing belongs to the Manual Práctico's worked
                # examples, not to the statute this reference cites.
                "valores admitidos a negociación",
                "valores no admitidos a negociación",
                "instituciones de inversión colectiva",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)


def test_lirpf_state_quota_chain_links_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-62",
            date(2007, 1, 1),
            (
                "Cuota íntegra estatal.",
                "La cuota íntegra estatal será la suma",
                "artículos 63 y 66",
                "bases liquidables general y del ahorro",
            ),
        ),
        (
            "ley-35-2006:art-63",
            date(2021, 1, 1),
            (
                "Escala general del Impuesto.",
                "base liquidable general que exceda del importe del mínimo personal y familiar",
                "A la base liquidable general se le aplicarán los tipos",
                "se minorará en el importe derivado de aplicar",
                "tipo medio de gravamen general estatal",
            ),
        ),
        (
            "ley-35-2006:art-66",
            date(2024, 12, 22),
            (
                "Tipos de gravamen del ahorro.",
                "base liquidable del ahorro que exceda",
                "A la base liquidable del ahorro se le aplicarán los tipos",
                "se minorará en el importe derivado de aplicar",
                "contribuyentes que tuviesen su residencia habitual en el extranjero",
            ),
        ),
        (
            "ley-35-2006:art-67",
            date(2015, 1, 1),
            (
                "Cuota líquida estatal.",
                "La cuota líquida estatal del Impuesto será el resultado de disminuir la cuota íntegra estatal",
                "deducción por inversión en empresas de nueva o reciente creación",
                "50 por ciento del importe total de las deducciones",
                "no podrá ser negativo",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)


def test_lirpf_autonomic_quota_chain_links_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-73",
            date(2007, 1, 1),
            (
                "Cuota íntegra autonómica.",
                "La cuota íntegra autonómica del Impuesto será la suma",
                "artículos 74 y 76",
                "base liquidable general y del ahorro",
            ),
        ),
        (
            "ley-35-2006:art-74",
            date(2011, 1, 12),
            (
                "Escala autonómica del Impuesto.",
                "base liquidable general que exceda del importe del mínimo personal y familiar",
                "escala autonómica del Impuesto",
                "aprobadas por la Comunidad Autónoma",
                "tipo medio de gravamen general autonómico",
            ),
        ),
        (
            "ley-35-2006:art-75",
            date(2025, 4, 3),
            (
                "Especialidades aplicables en los supuestos de anualidades por alimentos a favor de los hijos.",
                "satisfagan las anualidades por alimentos a sus hijos",
                "aplicarán la escala prevista",
                "mínimo personal y familiar",
                "incrementado en 1.980 euros anuales",
                "sin que pueda resultar negativa",
            ),
        ),
        (
            "ley-35-2006:art-76",
            date(2024, 12, 22),
            (
                "Tipo de gravamen del ahorro.",
                "base liquidable del ahorro que exceda",
                "A la base liquidable del ahorro se le aplicarán los tipos",
                "se minorará en el importe derivado de aplicar",
            ),
        ),
        (
            "ley-35-2006:art-77",
            date(2015, 1, 1),
            (
                "Cuota líquida autonómica.",
                "La cuota líquida autonómica será el resultado de disminuir",
                "50 por ciento del importe total de las deducciones",
                "deducciones establecidas por la Comunidad Autónoma",
                "no podrá ser negativo",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        reference = _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)
        if ref_id == "ley-35-2006:art-75":
            assert reference.notes is not None
            assert "not the generic autonomic quota article" in reference.notes


def test_lirpf_minimum_and_broad_deduction_foundations_link_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-56",
            date(2010, 1, 1),
            (
                "Mínimo personal y familiar.",
                "constituye la parte de la base liquidable",
                "necesidades básicas personales y familiares",
                "Cuando no exista base liquidable general",
                "artículos 57, 58, 59 y 60",
                "gravamen autonómico",
            ),
        ),
        (
            "ley-35-2006:art-68",
            date(2023, 1, 1),
            (
                "Deducciones.",
                "Deducción por inversión en empresas de nueva o reciente creación",
                "50 por ciento de las cantidades satisfechas",
                "La base máxima de deducción será de 100.000 euros anuales",
                "Deducciones en actividades económicas",
                "Deducciones por donativos y otras aportaciones",
                "Deducción por rentas obtenidas en Ceuta o Melilla",
                "actuaciones para la protección y difusión del Patrimonio Histórico Español",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)


def test_lirpf_family_joint_and_attribution_foundations_link_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-82",
            date(2007, 1, 1),
            (
                "Tributación conjunta.",
                "modalidades de unidad familiar",
                "cónyuges no separados legalmente",
                "Los hijos menores",
                "Nadie podrá formar parte de dos unidades familiares",
                "31 de diciembre de cada año",
            ),
        ),
        (
            "ley-35-2006:art-83",
            date(2007, 1, 1),
            (
                "Opción por la tributación conjunta.",
                "podrán optar, en cualquier período impositivo",
                "no vinculará para períodos sucesivos",
                "deberá abarcar a la totalidad de los miembros",
                "Si uno de ellos presenta declaración individual",
            ),
        ),
        (
            "ley-35-2006:art-84",
            date(2010, 1, 1),
            (
                "Normas aplicables en la tributación conjunta.",
                "idéntica cuantía en la tributación conjunta",
                "se reducirá en 3.400 euros anuales",
                "se reducirá en 2.150 euros anuales",
                "No se aplicará esta reducción cuando el contribuyente conviva",
            ),
        ),
        (
            "ley-35-2006:art-86",
            date(2007, 1, 1),
            (
                "Régimen de atribución de rentas.",
                "se atribuirán a los socios, herederos, comuneros o partícipes",
                "sección 2.ª",
            ),
        ),
        (
            "ley-35-2006:art-87",
            date(2022, 10, 20),
            (
                "Entidades en régimen de atribución de rentas.",
                "artículo 8.3 de esta Ley",
                "entidades constituidas en el extranjero",
                "no estarán sujetas al Impuesto sobre Sociedades",
                "apartado 12 del artículo 15 bis",
            ),
        ),
        (
            "ley-35-2006:art-88",
            date(2007, 1, 1),
            (
                "Calificación de la renta atribuida.",
                "tendrán la naturaleza derivada de la actividad o fuente",
                "para cada uno de ellos",
            ),
        ),
        (
            "ley-35-2006:art-89",
            date(2007, 1, 1),
            (
                "Cálculo de la renta atribuible y pagos a cuenta.",
                "Para el cálculo de las rentas a atribuir",
                "se determinarán con arreglo a las normas de este Impuesto",
                "no serán aplicables las reducciones previstas en los artículos 23.2, 23.3, 26.2 y 32",
                "estarán sujetas a retención o ingreso a cuenta",
                "se atribuirán por partes iguales",
                "podrán practicar en su declaración las reducciones previstas",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        reference = _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)
        if ref_id == "ley-35-2006:art-84":
            assert reference.notes is not None
            assert "in force from 2010-01-01" in reference.notes
        if ref_id == "ley-35-2006:art-87":
            assert reference.notes is not None
            assert "in force from 2022-10-20" in reference.notes
