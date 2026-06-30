"""Tests for registry source and legal catalogue verification."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from .....core.paths import PROJECT_ROOT
from .....core.resources import bundled_path
from .._corpus_catalogue import verify_source_catalogue, verify_source_file
from .._coverage import audit_registry_model_law_coverage
from .._legal import verify_legal_catalogue
from .._validate import RegistryValidator
from ._catalogue_verification_support import _catalogues, _registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_committed_registry_tree_has_coherent_shared_catalogues() -> None:
    modelos, catalogues = _registry_tree()

    assert len(modelos) >= 5, "committed registry must declare several modelos"
    assert len(catalogues.legal) > 0, "shared legal catalogue must be non-empty"
    assert len(catalogues.sources) > 0, "shared sources catalogue must be non-empty"
    verify_legal_catalogue(catalogues.legal, source_root=bundled_path())
    verify_source_catalogue(PROJECT_ROOT, catalogues.sources)
    validator = RegistryValidator(catalogues, source_root=bundled_path())
    validator.validate_registry(modelos)


def test_committed_registry_tree_has_required_model_law_coverage() -> None:
    modelos, catalogues = _registry_tree()

    audit = audit_registry_model_law_coverage(modelos, catalogues, source_root=bundled_path())

    assert audit.ok
    assert audit.required_gate_failures == ()
    assert len(audit.ledgers) == sum(len(modelo.revisions) for modelo in modelos)
    for ledger in audit.ledgers:
        gates = {gate.tier: gate for gate in ledger.gates}
        assert gates["legal_authority"].status == "satisfied", ledger
        assert gates["official_source_guidance"].status == "satisfied", ledger
        assert gates["layout_authority"].status == "satisfied", ledger


def test_committed_aeat_record_design_sources_match_corpus_manifests() -> None:
    catalogues = _catalogues()
    checked: list[str] = []

    for source in catalogues.sources.values():
        path = Path(source.corpus_path)
        parts = path.parts
        if len(parts) < 5 or parts[:3] != ("corpus", "aeat_official", "disenos_registro"):
            continue
        # corpus_path is stored relative to the bundled corpus root
        # (src/aeat/_data/), so resolve via bundled_path rather than
        # PROJECT_ROOT to find the on-disk manifest.
        modelo_dir = bundled_path(*parts[:4])
        manifest_path = modelo_dir / "manifest.json"
        assert manifest_path.is_file(), f"{source.id} missing corpus manifest {manifest_path}"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        stored_path = Path(*parts[4:]).as_posix()
        artefact = next(
            (item for item in manifest["artefacts"] if item["stored_path"] == stored_path),
            None,
        )

        assert artefact is not None, f"{source.id} missing manifest artefact for {stored_path}"
        assert source.sha256 == artefact["sha256"], source.id
        assert source.bytes == artefact["bytes"], source.id
        assert source.source_url == artefact["url"], source.id
        checked.append(source.id)

    assert checked


def test_modelo_100_record_design_sources_match_manifest() -> None:
    catalogues = _catalogues()
    manifest_path = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources_by_path = {source.corpus_path: source for source in catalogues.sources.values()}
    checked: list[str] = []

    for artefact in manifest["artefacts"]:
        title = artefact["title"]
        if not (
            "Diccionario declaración individual" in title
            or "Diccionario declaración individual (toma de datos)" in title
            or "Esquema XSD Ejercicio" in title
        ):
            continue
        corpus_path = f"corpus/aeat_official/disenos_registro/modelo_100/{artefact['stored_path']}"
        source = sources_by_path.get(corpus_path)

        assert source is not None, f"Modelo 100 corpus artefact has no registry source: {corpus_path}"
        assert source.sha256 == artefact["sha256"]
        assert source.bytes == artefact["bytes"]
        assert source.source_url == artefact["url"]
        assert source.evidence_tier == "layout_authority"
        assert source.kind in {"dictionary", "xsd"}
        verify_source_file(PROJECT_ROOT, source)
        checked.append(source.id)

    assert len(checked) == 18


def _source_path(corpus_path: str) -> Path:
    return bundled_path(*corpus_path.split("/"))


def _record_design_label(corpus_path: str, casilla_id: str) -> str:
    marker = f"[{casilla_id}]"
    for line in _source_path(corpus_path).read_text(encoding="cp1252").splitlines():
        if marker not in line:
            continue
        label = line.split(marker, 1)[1].strip()
        assert label.startswith("[") and label.endswith("]"), line
        return label[1:-1]
    raise AssertionError(f"source {corpus_path} has no label for casilla {casilla_id}")


def _manual_extracted_text(corpus_path: str) -> str:
    extracted_path = Path(f"{_source_path(corpus_path)}.extracted.json")
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    return "\n".join(unit["text"] for unit in payload["units"])


def test_modelo_100_2021_deportistas_0489_is_grounded_in_dictionary_and_manual() -> None:
    modelos, catalogues = _registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "100")
    revision = modelo.revisions["2021"]
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "0489")
    dictionary = catalogues.sources["aeat-dr-100-2021-dictionary"]
    manual = catalogues.sources["aeat-renta-2021-manual-parte1"]

    assert dictionary.evidence_tier == "layout_authority"
    assert manual.evidence_tier == "official_source_guidance"
    assert casilla.label == _record_design_label(dictionary.corpus_path, "0489")
    assert "aeat-renta-2021-manual-parte1" in casilla.source_refs
    assert casilla.semantic_role == "irpf_red_deportistas_aportaciones_contribuciones"

    manual_text = " ".join(_manual_extracted_text(manual.corpus_path).split())
    assert "casillas [0488] y [0489]" in manual_text
    assert "aportaciones y contribuciones realizadas en 2021" in manual_text


def test_modelo_100_2021_forestal_0302_prefers_manual_year_over_dictionary_drift() -> None:
    modelos, catalogues = _registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "100")
    revision = modelo.revisions["2021"]
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "0302")
    dictionary = catalogues.sources["aeat-dr-100-2021-dictionary"]
    manual = catalogues.sources["aeat-renta-2021-manual-parte1"]

    expected_label = (
        "Ganancias patrimoniales obtenidas por los vecinos en 2021 como consecuencia de "
        "aprovechamientos forestales en montes públicos"
    )

    assert _record_design_label(dictionary.corpus_path, "0302") == expected_label.replace("2021", "2020")
    assert casilla.label == expected_label
    assert "aeat-renta-2021-manual-parte1" in casilla.source_refs

    manual_text = " ".join(_manual_extracted_text(manual.corpus_path).split())
    assert expected_label in manual_text
    assert "Esta ganancia patrimonial ha estado sujeta en 2021 a la retención del 19 por 100" in manual_text


def test_renta_manual_sources_match_manifest() -> None:
    catalogues = _catalogues()
    sources_by_path = {source.corpus_path: source for source in catalogues.sources.values()}
    renta_root = bundled_path("corpus", "manuals", "renta")
    manifest_paths = sorted(
        renta_root.glob("*/*/manifest.json"),
        key=lambda path: path.relative_to(renta_root).as_posix(),
    )
    checked: list[str] = []

    assert manifest_paths
    for manifest_path in manifest_paths:
        root = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pdf_path = root / manifest["relative_pdf_path"]
        # corpus_path on registry sources is bundled-corpus-relative
        # (i.e. begins with ``corpus/...``), so relativise against the
        # bundle root rather than PROJECT_ROOT.
        corpus_path = pdf_path.relative_to(bundled_path()).as_posix()
        source = sources_by_path.get(corpus_path)

        assert manifest["synthetic"] is False, f"Renta manual manifest must cite a real PDF: {manifest_path}"
        assert pdf_path.is_file(), f"Renta manual manifest points at a missing PDF: {pdf_path}"
        assert source is not None, f"Renta manual corpus artefact has no registry source: {corpus_path}"
        assert source.sha256 == manifest["sha256"]
        assert source.bytes == manifest["content_length"]
        assert source.source_url == manifest["source_pdf_url"]
        assert source.evidence_tier == "official_source_guidance"
        assert source.kind == "manual_pdf"
        verify_source_file(PROJECT_ROOT, source)
        checked.append(source.id)

    assert checked == [
        "aeat-renta-2020-manual-parte1",
        "aeat-renta-2021-manual-parte1",
        "aeat-renta-2022-manual-parte1",
        "aeat-renta-2023-manual-parte1",
        "aeat-renta-2024-manual-parte1",
        "aeat-renta-2024-manual-deducciones-autonomicas",
        "aeat-renta-2025-manual-parte1",
        "aeat-renta-2025-manual-deducciones-autonomicas",
    ]


def test_renta_economic_activity_legal_basis_links_to_corpus() -> None:
    catalogues = _catalogues()

    assert {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }.issubset(catalogues.legal)
    verify_legal_catalogue(catalogues.legal, source_root=bundled_path())


@pytest.mark.parametrize(
    ("ref_id", "effective_from", "required_text"),
    (
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
    ),
)
def test_lirpf_work_and_capital_income_foundations_link_to_full_boe_corpus(
    ref_id: str,
    effective_from: date,
    required_text: tuple[str, ...],
) -> None:
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]
    article = ref_id.rsplit("-", 1)[-1]

    assert reference.corpus_ref == f"corpus/normatives/html/ley-35-2006.html#a{article}"
    assert reference.effective_from == effective_from
    assert reference.required_text == required_text
    if ref_id == "ley-35-2006:art-20":
        assert reference.notes is not None
        assert "effects from 2024-01-01" in reference.notes
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


@pytest.mark.parametrize(
    ("ref_id", "effective_from", "required_text"),
    (
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
            ),
        ),
    ),
)
def test_lirpf_economic_activity_chapter_links_to_full_boe_corpus(
    ref_id: str,
    effective_from: date,
    required_text: tuple[str, ...],
) -> None:
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]
    article = ref_id.rsplit("-", 1)[-1]

    assert reference.corpus_ref == f"corpus/normatives/html/ley-35-2006.html#a{article}"
    assert reference.effective_from == effective_from
    assert reference.required_text == required_text
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


@pytest.mark.parametrize(
    ("ref_id", "effective_from", "required_text"),
    (
        (
            "ley-35-2006:art-33",
            date(2015, 1, 1),
            (
                "Concepto.",
                "Son ganancias y pérdidas patrimoniales",
                "variaciones en el valor del patrimonio",
                "alteración en la composición",
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
                "acciones admitidas a negociación",
                "valores no admitidos a negociación",
                "instituciones de inversión colectiva",
            ),
        ),
    ),
)
def test_lirpf_capital_gains_foundation_links_to_full_boe_corpus(
    ref_id: str,
    effective_from: date,
    required_text: tuple[str, ...],
) -> None:
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]
    article = ref_id.rsplit("-", 1)[-1]

    assert reference.corpus_ref == f"corpus/normatives/html/ley-35-2006.html#a{article}"
    assert reference.effective_from == effective_from
    assert reference.required_text == required_text
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


@pytest.mark.parametrize(
    ("ref_id", "effective_from", "required_text"),
    (
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
    ),
)
def test_lirpf_state_quota_chain_links_to_full_boe_corpus(
    ref_id: str,
    effective_from: date,
    required_text: tuple[str, ...],
) -> None:
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]
    article = ref_id.rsplit("-", 1)[-1]

    assert reference.corpus_ref == f"corpus/normatives/html/ley-35-2006.html#a{article}"
    assert reference.effective_from == effective_from
    assert reference.required_text == required_text
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


@pytest.mark.parametrize(
    ("ref_id", "effective_from", "required_text"),
    (
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
    ),
)
def test_lirpf_autonomic_quota_chain_links_to_full_boe_corpus(
    ref_id: str,
    effective_from: date,
    required_text: tuple[str, ...],
) -> None:
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]
    article = ref_id.rsplit("-", 1)[-1]

    assert reference.corpus_ref == f"corpus/normatives/html/ley-35-2006.html#a{article}"
    assert reference.effective_from == effective_from
    assert reference.required_text == required_text
    if ref_id == "ley-35-2006:art-75":
        assert reference.notes is not None
        assert "not the generic autonomic quota article" in reference.notes
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


@pytest.mark.parametrize(
    ("ref_id", "effective_from", "required_text"),
    (
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
    ),
)
def test_lirpf_minimum_and_broad_deduction_foundations_link_to_full_boe_corpus(
    ref_id: str,
    effective_from: date,
    required_text: tuple[str, ...],
) -> None:
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]
    article = ref_id.rsplit("-", 1)[-1]

    assert reference.corpus_ref == f"corpus/normatives/html/ley-35-2006.html#a{article}"
    assert reference.effective_from == effective_from
    assert reference.required_text == required_text
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


@pytest.mark.parametrize(
    ("ref_id", "effective_from", "required_text"),
    (
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
    ),
)
def test_lirpf_family_joint_and_attribution_foundations_link_to_full_boe_corpus(
    ref_id: str,
    effective_from: date,
    required_text: tuple[str, ...],
) -> None:
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]
    article = ref_id.rsplit("-", 1)[-1]

    assert reference.corpus_ref == f"corpus/normatives/html/ley-35-2006.html#a{article}"
    assert reference.effective_from == effective_from
    assert reference.required_text == required_text
    if ref_id == "ley-35-2006:art-84":
        assert reference.notes is not None
        assert "in force from 2010-01-01" in reference.notes
    if ref_id == "ley-35-2006:art-87":
        assert reference.notes is not None
        assert "in force from 2022-10-20" in reference.notes
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())
