"""Tests for the committed Modelo 210 (IRNR non-resident taxation) registry foundation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_210() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if m.id == "210")
    return modelo, catalogues


def _trlirnr_corpus_paragraph(anchor: str) -> str:
    text = bundled_path("corpus", "normatives", "html", "trlirnr-rdleg-5-2004.html").read_text(
        encoding="utf-8",
    )
    start_marker = f'<p id="{anchor}">'
    assert start_marker in text
    return text.split(start_marker, 1)[1].split("</p>", 1)[0]


def test_modelo_210_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_210()
    assert modelo.id == "210"
    assert modelo.revisions, "210 must declare at least one revision"
    assert any(rev.formulas for rev in modelo.revisions.values()), "210 must declare formulas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_210_revision_2025_declares_constructs() -> None:
    modelo, _ = _load_modelo_210()
    revision = modelo.revisions["2025"]
    assert revision.constructs, "210 2025 revision must declare constructs"
    construct_ids = {c.id for c in revision.constructs}
    assert "m210-irnr-calculation" in construct_ids


def test_modelo_210_revision_2025_formula_targets_resolve() -> None:
    modelo, _catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]
    irnr_calc = next(c for c in revision.constructs if c.id == "m210-irnr-calculation")
    assert irnr_calc.formulas, "m210-irnr-calculation must declare formulas"
    # Verify all formula references in construct exist in the revision
    formula_ids = {f.id for f in revision.formulas}
    for formula_id in irnr_calc.formulas:
        assert formula_id in formula_ids, f"formula {formula_id} not found in revision formulas"


def test_modelo_210_snapshot_builds_for_2025_event_period() -> None:
    modelo, catalogues = _load_modelo_210()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="evento",
    )
    assert snapshot.revision.id == "2025"


def test_modelo_210_interest_rate_is_grounded_in_unconditional_art_25_1_f() -> None:
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]
    parameter = next(param for param in revision.parameters if param.id == "m210-tipo-gravamen-2025")
    rates = {row.key: row.value for row in parameter.keyed_brackets}

    assert rates["interest"] == Decimal("0.19")

    art_25_1_f = catalogues.legal["trlirnr-rdleg-5-2004:art-25.1.f"]
    assert any(
        "Intereses y otros rendimientos obtenidos por la cesion a terceros" in text
        for text in art_25_1_f.required_text
    )
    assert "condicion de residencia UE/EEE" in (art_25_1_f.notes or "")

    corpus_paragraph = _trlirnr_corpus_paragraph("a25-1-f")
    assert "Intereses y otros rendimientos obtenidos por la cesion a terceros" in corpus_paragraph
    assert "Ganancias patrimoniales" in corpus_paragraph
    assert "Union Europea" not in corpus_paragraph
    assert "Espacio Economico Europeo" not in corpus_paragraph


def test_modelo_210_imputed_real_estate_art_13_1_h_is_catalogued_for_deferred_branch() -> None:
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]

    art_13_1_h = catalogues.legal["trlirnr-rdleg-5-2004:art-13.1.h"]
    assert art_13_1_h.corpus_ref.endswith("#a13-1-h")
    assert "live M210 imputed-real-estate base branch" in (art_13_1_h.notes or "")

    corpus_paragraph = _trlirnr_corpus_paragraph("a13-1-h")
    assert "rentas imputadas a los contribuyentes personas fisicas" in corpus_paragraph
    assert "bienes inmuebles urbanos situados en territorio espanol" in corpus_paragraph
    assert "no afectos a actividades economicas" in corpus_paragraph
    assert "2 por ciento" not in corpus_paragraph
    assert "1,1 por ciento" not in corpus_paragraph

    parameter = next(param for param in revision.parameters if param.id == "m210-tipo-gravamen-2025")
    rates = {row.key: row.value for row in parameter.keyed_brackets}
    assert rates["inmobiliaria"] == Decimal("0.24")
    assert "trlirnr-rdleg-5-2004:art-25.1.a" in parameter.legal_refs
    assert "trlirnr-rdleg-5-2004:art-13.1.h" not in parameter.legal_refs

    imputation_params = {param.id: param for param in revision.parameters}
    assert imputation_params["m210-imputacion-rate-recent-revision-2025"].values[0].value == Decimal("0.011")
    assert imputation_params["m210-imputacion-rate-old-or-no-revision-2025"].values[0].value == Decimal("0.02")
    assert imputation_params["m210-imputacion-no-catastral-base-fraction-2025"].values[0].value == Decimal("0.50")


def test_modelo_210_imputed_real_estate_aeat_guidance_source_is_available() -> None:
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]

    source = catalogues.sources["aeat-irnr-renta-imputada-inmueble-urbano"]
    assert source.authority == "aeat"
    assert source.kind == "instructions"
    assert source.sha256 == "9631d3b915c2bcc8223e72861d66cace55a16cdbb32ac175308807a88cce25ca"

    source_text = (bundled_path() / source.corpus_path).read_text(encoding="utf-8")
    assert "base imponible" in source_text
    assert "valor catastral" in source_text
    assert "1,1%" in source_text
    assert "sin deducir ning&uacute;n tipo de gasto" in source_text
    assert "El <strong>tipo de gravamen</strong> es el general vigente" in source_text

    parameter = next(param for param in revision.parameters if param.id == "m210-tipo-gravamen-2025")
    assert "aeat-irnr-renta-imputada-inmueble-urbano" not in parameter.source_refs


def test_modelo_210_pension_tariff_and_convenio_row_are_grounded() -> None:
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]
    convenio_param = next(param for param in revision.parameters if param.id == "m210-convenio-rates")
    rows = {(row.country_code, row.tipo_renta): row for row in convenio_param.convenio_rates}
    ar_pension = rows[("AR", "pension")]

    assert ar_pension.rate == "DOMESTIC_TARIFF"
    assert ar_pension.legal_ref_anchor == "convenio-es-ar-1992:art-19"
    assert ar_pension.legal_refs == (
        "convenio-es-ar-1992:art-19",
        "trlirnr-rdleg-5-2004:art-25.1.b",
    )
    assert "BOE-CONVENIO-AR-NOT-FOUND" not in ar_pension.legal_ref_anchor

    tariff = next(param for param in revision.parameters if param.id == "m210-pension-tarifa-2025")
    assert tariff.data_type == "bracket_table"
    assert tariff.legal_refs == ("trlirnr-rdleg-5-2004:art-25.1.b",)
    assert [
        (bracket.lower_bound, bracket.upper_bound, bracket.fixed_addition, bracket.marginal_rate)
        for bracket in tariff.brackets
    ] == [
        (Decimal("0"), Decimal("12000"), Decimal("0"), Decimal("0.08")),
        (Decimal("12000"), Decimal("18700"), Decimal("960"), Decimal("0.30")),
        (Decimal("18700"), None, Decimal("2970"), Decimal("0.40")),
    ]

    pension_scale = catalogues.legal["trlirnr-rdleg-5-2004:art-25.1.b"]
    assert "live M210 pension tariff branch" in (pension_scale.notes or "")
    corpus_paragraph = _trlirnr_corpus_paragraph("a25-1-b")
    assert "Importe anual pension hasta 12.000 euros" in corpus_paragraph
    assert "tipo aplicable 30 por ciento" in corpus_paragraph
    assert "tipo aplicable 40 por ciento" in corpus_paragraph

    ar_treaty = catalogues.legal["convenio-es-ar-1992:art-19"]
    treaty_text = bundled_path(
        "corpus",
        "normatives",
        "html",
        "convenio-es-ar-1992-art-19.html",
    ).read_text(encoding="utf-8")
    assert "Las pensiones pagadas por un Estado Contratante" in treaty_text
    assert "solo pueden someterse a imposicion en este Estado" in treaty_text
    assert ar_treaty.document_id == "BOE-A-1994-20084"
