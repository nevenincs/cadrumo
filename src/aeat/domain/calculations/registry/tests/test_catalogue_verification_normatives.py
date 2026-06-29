"""Article-level normative corpus verification tests."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.paths import PROJECT_ROOT
from .....core.resources import bundled_path
from .._corpus_catalogue import verify_source_file
from .._errors import RegistryValidationError
from .._legal import verify_legal_catalogue
from ._catalogue_verification_support import (
    _FORMAL_WITHHOLDING_ARTICLE_REF,
    _FORMAL_WITHHOLDING_MODELOS,
    _FRACTIONAL_PAYMENT_ARTICLE_REF,
    _M100_WITHHOLDING_IMPORT_SECTIONS,
    _catalogues,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_lirpf_art_91_transparencia_fiscal_links_to_full_boe_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["ley-35-2006:art-91"]

    assert reference.corpus_ref == "corpus/normatives/html/ley-35-2006.html#a91"
    assert reference.effective_from == date(2021, 7, 11)
    assert reference.required_text == (
        "Imputación de rentas en el régimen de transparencia fiscal internacional.",
        "Los contribuyentes imputarán las rentas positivas obtenidas",
        "entidad no residente en territorio español",
        "participación igual o superior al 50 por ciento",
        "inferior al 75 por ciento del que hubiera correspondido",
        "organización de medios materiales y personales",
        "Titularidad de bienes inmuebles rústicos y urbanos",
        "Participación en fondos propios de cualquier tipo de entidad",
        "Operaciones de capitalización y seguro",
        "se imputarán en la base imponible general",
        "Será deducible de la cuota líquida",
        "deberán presentar conjuntamente con la declaración por este Impuesto los siguientes datos",
    )
    assert reference.notes is not None
    assert "Ley 11/2021 art 3.4" in reference.notes
    assert "paragraph 6 fixes the imputation period" in reference.notes
    assert "paragraph 11 lists accompanying entity data" in reference.notes
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_ley_31_2022_da_70_rib_reference_links_to_bundled_boe_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["ley-31-2022:da-70"]

    assert reference.corpus_ref == "corpus/normatives/html/ley-31-2022-da-70.html#da-70"
    assert reference.permalink.endswith("#da-70")
    assert reference.required_text == (
        "Reserva para inversiones en las Illes Balears",
        "El importe de la reserva pendiente de materialización",
        "Los contribuyentes del Impuesto sobre la Renta de las Personas Físicas",
        "tendrán derecho a una deducción en la cuota íntegra",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_lirpf_da_45_regularizacion_clausulas_suelo_links_to_bundled_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["ley-35-2006:da-45"]

    assert reference.corpus_ref == "corpus/normatives/html/ley-35-2006.html#dacuadragesimaquinta"
    assert reference.permalink.endswith("#dacuadragesimaquinta")
    assert reference.required_text == (
        "Tratamiento fiscal de las cantidades percibidas por la devolución de las cláusulas de limitación "
        "de tipos de interés",
        "se perderá el derecho a practicar la deducción",
        "debiendo sumar a la cuota líquida estatal y autonómica",
        "sin inclusión de intereses de demora",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_lirpf_art_99_payments_on_account_links_to_full_boe_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["ley-35-2006:art-99"]

    assert reference.corpus_ref == "corpus/normatives/html/ley-35-2006.html#a99"
    assert reference.effective_from == date(2016, 1, 1)
    assert reference.required_text == (
        "Obligación de practicar pagos a cuenta",
        "tendrán la consideración de deuda tributaria",
        "Retenciones.",
        "Ingresos a cuenta.",
        "Pagos fraccionados.",
        "estarán obligadas a practicar retención e ingreso a cuenta",
        "estarán obligados a efectuar pagos fraccionados a cuenta",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_lirpf_art_80_double_taxation_links_to_full_boe_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["ley-35-2006:art-80"]

    assert reference.corpus_ref == "corpus/normatives/html/ley-35-2006.html#a80"
    assert reference.effective_from == date(2015, 1, 1)
    assert reference.required_text == (
        "Deducción por doble imposición internacional",
        "rendimientos o ganancias patrimoniales obtenidos y gravados en el extranjero",
        "impuesto de naturaleza idéntica o análoga",
        "resultado de aplicar el tipo medio efectivo de gravamen",
        "cuota líquida total por la base liquidable",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_lirpf_art_49_savings_base_compensation_links_to_full_boe_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["ley-35-2006:art-49"]

    assert reference.corpus_ref == "corpus/normatives/html/ley-35-2006-art-49.html#a49"
    assert reference.effective_from == date(2015, 1, 1)
    assert reference.required_text == (
        "La base imponible del ahorro estará constituida",
        "con el límite del 25 por ciento",
        "se compensará en los cuatro años siguientes",
        "Las compensaciones previstas en el apartado anterior deberán efectuarse",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


@pytest.mark.parametrize(
    ("ref_id", "effective_from", "required_text"),
    (
        (
            "ley-35-2006:art-50",
            date(2015, 1, 1),
            (
                "Base liquidable general y del ahorro.",
                "La base liquidable general estará constituida",
                "exclusivamente y por este orden",
                "artículos 51, 53, 54, 55 y disposición adicional undécima",
                "sin que pueda resultar negativa",
                "La base liquidable del ahorro será el resultado de disminuir",
                "Si la base liquidable general resultase negativa",
                "cuatro años siguientes",
            ),
        ),
        (
            "ley-35-2006:art-52",
            date(2023, 1, 1),
            (
                "Límite de reducción.",
                "límite máximo conjunto",
                "apartados 1, 2, 3, 4 y 5 del artículo 51",
                "El 30 por 100 de la suma",
                "1.500 euros anuales",
                "En 8.500 euros anuales",
                "rendimientos íntegros del trabajo superiores a 60.000 euros",
                "En 4.250 euros anuales",
                "cuantía máxima de reducción por aplicación de los incrementos",
                "5.000 euros anuales para las primas a seguros colectivos de dependencia",
                "podrán reducir en los cinco ejercicios siguientes",
            ),
        ),
    ),
)
def test_lirpf_base_liquidable_and_reduction_limit_links_to_full_boe_corpus(
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
    if ref_id == "ley-35-2006:art-50":
        assert reference.notes is not None
        assert "in force from 2015-01-01" in reference.notes
    if ref_id == "ley-35-2006:art-52":
        assert reference.notes is not None
        assert "Ley 31/2022 art 62.1" in reference.notes
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_rirpf_art_59_regularizacion_perdida_derecho_links_to_bundled_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["rd-439-2007:art-59"]

    assert reference.corpus_ref == "corpus/normatives/html/rd-439-2007-art-59.html#a59"
    assert reference.permalink.endswith("#a59")
    assert reference.required_text == (
        "Pérdida del derecho a deducir",
        "sumar a la cuota líquida estatal y a la cuota líquida autonómica",
        "las cantidades indebidamente deducidas",
        "más los intereses de demora",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_lgt_art_26_interes_demora_links_to_bundled_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["ley-58-2003:art-26"]

    assert reference.corpus_ref == "corpus/normatives/html/ley-58-2003-art-26.html#a26"
    assert reference.permalink.endswith("#a26")
    assert reference.required_text == (
        "Interés de demora",
        "prestación accesoria",
        "se calculará sobre el importe no ingresado en plazo",
        "interés legal del dinero vigente",
        "incrementado en un 25 por ciento",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_orden_hac_242_2025_art_8_deadline_links_to_full_boe_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["orden-hac-242-2025:art-8"]
    source = catalogues.sources["boe-modelo-100-2024-form"]

    assert reference.corpus_ref == "corpus/normatives/html/orden-hac-242-2025.html#a8"
    assert reference.permalink.endswith("#a8")
    assert reference.required_text == (
        "Plazo de presentación del borrador de declaración",
        "2 de abril y 30 de junio de 2025",
        "desde el día 2 de abril hasta el 25 de junio de 2025",
    )
    assert source.corpus_path == "corpus/normatives/html/orden-hac-242-2025.html"
    assert source.sha256 == "6c6e3656116c3efd95c6ae5ee249f2629addd2e8f87874ee9efc4097b99f5c22"
    assert source.bytes == 139603
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())
    verify_source_file(PROJECT_ROOT, source)


@pytest.mark.parametrize(
    ("ref_id", "article", "corpus_ref"),
    (
        ("orden-hac-248-2021:art-10", "10", "corpus/normatives/html/orden-hac-248-2021.html#a1-2"),
        ("orden-hfp-207-2022:art-10", "10", "corpus/normatives/html/orden-hfp-207-2022.html#a1-2"),
        ("orden-hfp-310-2023:art-11", "11", "corpus/normatives/html/orden-hfp-310-2023.html#a1-3"),
        ("orden-hac-265-2024:art-11", "11", "corpus/normatives/html/orden-hac-265-2024.html#a1-3"),
        ("orden-hac-242-2025:art-11", "11", "corpus/normatives/html/orden-hac-242-2025.html#a11"),
        ("orden-hac-277-2026:art-10", "10", "corpus/normatives/html/orden-hac-277-2026.html#a10"),
    ),
)
def test_modelo_100_tfi_additional_documentation_order_refs_link_to_boe_corpus(
    ref_id: str,
    article: str,
    corpus_ref: str,
) -> None:
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]

    assert reference.article == article
    assert reference.corpus_ref == corpus_ref
    assert reference.required_text == (
        "Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta "
        "de las Personas Físicas",
        "imputación de rentas en el régimen de transparencia fiscal internacional",
        "datos relativos a la entidad no residente en territorio español",
        "Nombre o razón social y lugar del domicilio social",
        "Importe de las rentas positivas que deban ser imputadas",
        "Justificación de los impuestos satisfechos respecto de la renta positiva",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_rd_439_art_100_legal_basis_links_to_full_rental_withholding_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["rd-439-2007:art-100"]

    assert reference.corpus_ref == "corpus/normatives/html/rd-439-2007-art-100.html#a100"
    assert reference.effective_from == date(2018, 12, 23)
    assert "summary" not in reference.corpus_ref
    assert "19 por ciento" in reference.required_text
    assert "se reducirá en el 60 por ciento" in reference.required_text
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_rd_439_art_30_legal_basis_links_to_simplified_direct_estimation_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["rd-439-2007:art-30"]

    assert reference.corpus_ref == "corpus/normatives/html/rd-439-2007-art-30.html#a30"
    assert reference.required_text == (
        "Determinación del rendimiento neto en el método de estimación directa simplificada",
        "gastos de difícil justificación",
        "5 por ciento",
        "2.000 euros anuales",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_rd_439_art_109_legal_basis_links_to_pago_fraccionado_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["rd-439-2007:art-109"]
    corpus_text = bundled_path("corpus", "normatives", "html", "rd-439-2007-art-109.html").read_text(
        encoding="utf-8",
    )

    assert "rd-439-2007:art-110-3-b" not in catalogues.legal
    assert reference.corpus_ref == "corpus/normatives/html/rd-439-2007-art-109.html#a109"
    assert reference.notes is not None
    assert "obligados al pago fraccionado" in reference.notes.lower()
    assert "obligaciones formales del retenedor" not in reference.notes.lower()
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())

    assert "Artículo 109. Obligados al pago fraccionado." in corpus_text
    assert "autoliquidar e ingresar en el Tesoro" in corpus_text
    assert "obligaciones formales" not in corpus_text.lower()


def test_rd_439_art_110_legal_basis_links_to_full_payment_amount_corpus() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["rd-439-2007:art-110"]

    assert reference.corpus_ref == "corpus/normatives/html/rd-439-2007-art-110.html#a110"
    assert "apartado 110.5 vigente" in (reference.notes or "")
    assert "el 4 por ciento de los rendimientos netos" in reference.required_text
    assert "el porcentaje anterior será el 3 por ciento" in reference.required_text
    assert "no disponga de personal asalariado dicho porcentaje será el 2 por ciento" in reference.required_text
    assert any("volumen de ventas o ingresos del trimestre" in text for text in reference.required_text)
    assert any(
        "retenciones practicadas y los ingresos a cuenta efectuados conforme" in text
        for text in reference.required_text
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


@pytest.mark.parametrize(
    ("ref_id", "article", "corpus_ref", "required_text"),
    (
        (
            "ley-19-1994:art-27",
            "27",
            "corpus/normatives/html/ley-19-1994-art-27.html#a27",
            (
                "Reserva para inversiones en Canarias",
                "plazo máximo de tres años",
                "cinco años como mínimo",
                "rendimientos netos mediante el método de estimación directa",
                "rendimientos netos de explotación",
                "ochenta por ciento",
            ),
        ),
        (
            "ley-19-1994:art-43",
            "43",
            "corpus/normatives/html/ley-19-1994-art-43.html#a43",
            (
                "Tipo de gravamen especial",
                "4%",
            ),
        ),
    ),
)
def test_ley_19_1994_canary_tax_regime_refs_link_to_current_boe_corpus(
    ref_id: str,
    article: str,
    corpus_ref: str,
    required_text: tuple[str, ...],
) -> None:
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]

    assert reference.article == article
    assert reference.corpus_ref == corpus_ref
    assert reference.required_text == required_text
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_retired_normative_summary_corpus_files_are_not_bundled() -> None:
    retired_summary_json = (
        "ley-19-1994.json",
        "ley-35-2006.json",
        "ley-37-1992.json",
        "ley-58-2003.json",
        "orden-hac-242-2025.json",
        "orden-hac-623-2026.json",
        "rd-1065-2007.json",
        "rd-1624-1992.json",
        "rd-439-2007.json",
    )

    assert [name for name in retired_summary_json if bundled_path("corpus", "normatives", name).exists()] == []
    assert not bundled_path("corpus", "normatives", "html", "ley-19-1994-art-50.html").exists()


def test_rd_1007_verifactu_refs_are_article_level_and_current() -> None:
    catalogues = _catalogues()
    art3 = catalogues.legal["rd-1007-2023:art-3"]
    df4 = catalogues.legal["rd-1007-2023:df-4"]

    assert art3.article == "3"
    assert art3.corpus_ref == "corpus/normatives/html/rd-1007-2023.html#a3"
    assert {
        "Los contribuyentes del Impuesto sobre Sociedades",
        "Los contribuyentes del Impuesto sobre la Renta de las Personas Físicas que desarrollen actividades económicas",
        "Las entidades en régimen de atribución de rentas que desarrollen actividades económicas",
        (
            "no se aplicará a los contribuyentes que lleven los libros registros en los términos establecidos "
            "en el apartado 6"
        ),
    }.issubset(set(art3.required_text))

    assert df4.article == "disposicion final cuarta"
    assert df4.corpus_ref == "corpus/normatives/html/rd-1007-2023.html#df-4"
    assert "antes del 1 de enero de 2027" in df4.required_text
    assert "antes del 1 de julio de 2027" in df4.required_text
    assert "2026" not in " ".join(df4.required_text)
    verify_legal_catalogue({art3.id: art3, df4.id: df4}, source_root=bundled_path())


def test_trlirnr_rows_use_current_real_decreto_legislativo_kind() -> None:
    catalogues = _catalogues()
    trlirnr_refs = tuple(
        reference for ref_id, reference in catalogues.legal.items() if ref_id.startswith("trlirnr-rdleg-5-2004:")
    )

    assert trlirnr_refs
    assert {reference.kind for reference in trlirnr_refs} == {"real_decreto_legislativo"}


def test_real_decreto_legislativo_kind_still_runs_strict_required_text_check() -> None:
    catalogues = _catalogues()
    reference = catalogues.legal["trlirnr-rdleg-5-2004:art-25.1.a"].model_copy(
        update={"required_text": ("this text is intentionally absent from the bundled TRLIRNR corpus",)},
    )

    with pytest.raises(RegistryValidationError, match="corpus text missing required text"):
        verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_formal_withholding_modelos_do_not_cite_fractional_payment_article() -> None:
    modelos_root = bundled_path("registry", "aeat", "modelos")
    offenders: list[str] = []
    missing_formal_article: list[str] = []

    for modelo_id in sorted(_FORMAL_WITHHOLDING_MODELOS):
        modelo_root = modelos_root / modelo_id
        assert modelo_root.is_dir(), modelo_id
        has_formal_article = False

        for path in sorted(modelo_root.rglob("*.toml")):
            text = path.read_text(encoding="utf-8")
            if _FRACTIONAL_PAYMENT_ARTICLE_REF in text:
                offenders.append(path.relative_to(modelos_root).as_posix())
            if _FORMAL_WITHHOLDING_ARTICLE_REF in text:
                has_formal_article = True

        if not has_formal_article:
            missing_formal_article.append(modelo_id)

    assert offenders == []
    assert missing_formal_article == []


def test_modelo_100_withholding_imports_use_formal_withholding_article() -> None:
    modelo_root = bundled_path("registry", "aeat", "modelos", "100")
    offenders: list[str] = []
    missing_formal_article: list[str] = []
    checked: list[str] = []

    for path in sorted(modelo_root.rglob("*.toml")):
        if not (set(path.parts) & _M100_WITHHOLDING_IMPORT_SECTIONS):
            continue

        text = path.read_text(encoding="utf-8")
        if "retenciones" not in text.lower():
            continue
        if not any(f'source_modelo = "{modelo_id}"' in text for modelo_id in _FORMAL_WITHHOLDING_MODELOS):
            continue

        rel_path = path.relative_to(modelo_root).as_posix()
        checked.append(rel_path)
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in text:
            offenders.append(rel_path)
        if _FORMAL_WITHHOLDING_ARTICLE_REF not in text:
            missing_formal_article.append(rel_path)

    assert len(checked) == 72
    assert offenders == []
    assert missing_formal_article == []


def test_modelo_100_retention_credit_formulas_do_not_cite_fractional_payment_article() -> None:
    modelo_root = bundled_path("registry", "aeat", "modelos", "100")
    offenders: list[str] = []
    checked: list[str] = []

    for path in sorted(modelo_root.rglob("formulas/*.toml")):
        text = path.read_text(encoding="utf-8")
        formula_id = next((line for line in text.splitlines() if line.startswith("id = ")), "")
        if "retenciones" not in formula_id.lower():
            continue

        rel_path = path.relative_to(modelo_root).as_posix()
        checked.append(rel_path)
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in text:
            offenders.append(rel_path)

    assert "revisions/2025/formulas/0068-renta-2025-retenciones-arrendamientos-urbanos.toml" in checked
    assert offenders == []
