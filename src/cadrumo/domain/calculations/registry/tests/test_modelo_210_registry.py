"""Tests for the committed Modelo 210 (IRNR non-resident taxation) registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import ConvenioOverrideKind, ResultDisposition, TipoRentaIrnr
from .....core.resources import bundled_path
from .. import load_catalogue_file, load_convenio_authority, load_modelo_directory, select_revision
from .._errors import NoRevisionForPeriodError
from .._legal import verify_legal_catalogue
from .._schema import ModeloDefinition, RegistryCatalogues
from .._snapshot import build_snapshot
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M210_FORM_ORDER_REF = "orden-eha-3316-2010:art-1"
_M210_AGRUPACION_ORDER_REF = "orden-eha-3316-2010:art-2"
_ANNUAL_PERIOD = "0A"


def _load_modelo_210() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("210")


def _trlirnr_corpus_paragraph(anchor: str) -> str:
    text = bundled_path("corpus", "normatives", "html", "trlirnr-rdleg-5-2004.html").read_text(
        encoding="utf-8",
    )
    start_marker = f'<p id="{anchor}">'
    assert start_marker in text
    return text.split(start_marker, 1)[1].split("</p>", 1)[0]


def _trlirnr_extracted_markdown() -> str:
    return bundled_path("corpus", "normatives", "html", "trlirnr-rdleg-5-2004.html.extracted.md").read_text(
        encoding="utf-8",
    )


def _orden_hac_623_2026_extracted_markdown() -> str:
    text = bundled_path("corpus", "normatives", "html", "orden-hac-623-2026.html.extracted.md").read_text(
        encoding="utf-8",
    )
    return text.replace("\xa0", " ")


def test_modelo_210_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_210()
    assert modelo.id == "210"
    assert modelo.revisions, "210 must declare at least one revision"
    assert any(rev.formulas for rev in modelo.revisions.values()), "210 must declare formulas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_convenio_authority_loads_migrated_treaties_with_typed_override_kinds() -> None:
    convenio = load_convenio_authority(bundled_path("registry", "aeat", "treaties"))

    assert {"GB", "MA", "AR", "DE"} <= set(convenio.treaties)

    gb = convenio.resolve("GB", TipoRentaIrnr.GENERAL, 2025)
    assert gb is not None
    assert gb.kind is ConvenioOverrideKind.FLAT
    assert gb.rate == Decimal("0.24")

    ma = convenio.resolve("MA", TipoRentaIrnr.INTEREST, 2025)
    assert ma is not None
    assert ma.kind is ConvenioOverrideKind.CEILING
    assert ma.rate == Decimal("0.10")

    ar = convenio.resolve("AR", TipoRentaIrnr.PENSION, 2025)
    assert ar is not None
    assert ar.kind is ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF
    assert ar.rate is None

    de = convenio.resolve("DE", TipoRentaIrnr.INTEREST, 2025)
    assert de is not None
    assert de.kind is ConvenioOverrideKind.EXEMPT
    assert de.rate is None

    # A treaty country with no override row for the filed income type is a
    # non-match; the runtime raises the missing-row BLOCKING sentinel.
    assert convenio.resolve("GB", TipoRentaIrnr.INTEREST, 2025) is None


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


def test_modelo_210_snapshot_builds_for_2025_event_and_annual_group_periods() -> None:
    modelo, catalogues = _load_modelo_210()
    assert modelo.revisions["2025"].period_selector.periods == ("EVENT-N", "0A")
    event_snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="EVENT-1",
    )
    annual_snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )
    assert event_snapshot.revision.id == "2025"
    assert event_snapshot.filing_period is not None
    assert str(event_snapshot.filing_period.code) == "EVENT-1"
    assert annual_snapshot.revision.id == "2025"
    assert annual_snapshot.filing_period is not None
    assert str(annual_snapshot.filing_period.code) == "0A"


def test_modelo_210_deadlines_use_canonical_annual_identity_and_exact_revision_owner() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "210"))

    expected = {
        2025: {
            "modelo-210-2025-0a-arrendamiento-ingreso": (
                ResultDisposition.INGRESO,
                ("01", "35"),
                date(2026, 4, 1),
                date(2026, 4, 20),
            ),
            "modelo-210-2025-0a-cuota-cero": (
                ResultDisposition.NEGATIVA,
                ("01", "35"),
                date(2026, 1, 1),
                date(2026, 1, 20),
            ),
            "modelo-210-2025-0a-devolucion": (
                ResultDisposition.DEVOLUCION,
                ("01", "35"),
                date(2026, 2, 1),
                date(2030, 2, 1),
            ),
            "modelo-210-2025-0a-renta-imputada": (
                None,
                ("02",),
                date(2026, 1, 1),
                date(2026, 12, 31),
            ),
        },
        2026: {
            "modelo-210-2026-0a-arrendamiento-ingreso": (
                ResultDisposition.INGRESO,
                ("01", "35"),
                date(2027, 4, 1),
                date(2027, 4, 20),
            ),
            "modelo-210-2026-0a-cuota-cero": (
                ResultDisposition.NEGATIVA,
                ("01", "35"),
                date(2027, 1, 1),
                date(2027, 1, 20),
            ),
            "modelo-210-2026-0a-devolucion": (
                ResultDisposition.DEVOLUCION,
                ("01", "35"),
                date(2027, 2, 1),
                date(2031, 2, 1),
            ),
            "modelo-210-2026-0a-renta-imputada": (
                None,
                ("02",),
                date(2027, 4, 1),
                date(2027, 12, 31),
            ),
        },
    }

    for filing_year, expected_windows in expected.items():
        owner = select_revision(modelo, filing_year=filing_year, period=_ANNUAL_PERIOD)
        assert {window.id for window in owner.deadline_windows} == set(expected_windows)
        assert all(window.period.registry_token == _ANNUAL_PERIOD for window in owner.deadline_windows)
        assert all(window.filing_year == filing_year for window in owner.deadline_windows)
        assert all("-1t" not in window.id and "-2t" not in window.id for window in owner.deadline_windows)
        for window in owner.deadline_windows:
            assert (
                window.resultado_scope,
                window.tipo_renta_scope,
                window.opens_on,
                window.closes_on,
            ) == expected_windows[window.id]

    assert select_revision(modelo, filing_year=2025, period=_ANNUAL_PERIOD).id == "2025"
    assert select_revision(modelo, filing_year=2026, period=_ANNUAL_PERIOD).id == "2026-y-siguientes"


def test_modelo_210_tipo_28_stays_event_shaped_until_its_offset_authority_is_bundled() -> None:
    """Tipo 28 must not turn a remembered event offset into registry law."""
    registry_root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(registry_root / "modelos" / "210")
    irnr_catalogue = load_catalogue_file(registry_root / "legal" / "irnr.toml")

    assert all("EVENT-N" in revision.period_selector.periods for revision in modelo.revisions.values())
    assert "rd-1776-2004:art-14" not in irnr_catalogue.legal
    assert all(
        "28" not in (window.tipo_renta_scope or ())
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
    )


def test_modelo_210_legacy_evento_period_is_not_supported() -> None:
    modelo, catalogues = _load_modelo_210()

    with pytest.raises(NoRevisionForPeriodError):
        build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period="evento",
        )


def test_modelo_210_form_order_is_boe_corpus_backed() -> None:
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]
    legal = {_M210_FORM_ORDER_REF: catalogues.legal[_M210_FORM_ORDER_REF]}
    source = catalogues.sources["boe-modelo-210-base-order"]

    verify_legal_catalogue(legal, source_root=bundled_path())

    assert _M210_FORM_ORDER_REF in modelo.legal_refs
    assert _M210_FORM_ORDER_REF in revision.legal_refs
    assert revision.orden_aplicabilidad == (_M210_FORM_ORDER_REF,)
    assert "boe-modelo-210-base-order" in modelo.source_refs
    assert "boe-modelo-210-base-order" in revision.source_refs

    reference = legal[_M210_FORM_ORDER_REF]
    assert reference.document_id == "BOE-A-2010-19707"
    assert reference.kind == "orden"
    assert reference.article == "1"
    assert reference.consolidated_as_of == date(2026, 6, 23)
    assert "Se aprueba el modelo 210" in reference.required_text

    assert source.evidence_tier == "layout_authority"
    assert source.corpus_path == "corpus/normatives/html/orden-eha-3316-2010.html"
    assert source.sha256 == "c40939b99cd2091b924a78e0690977a0f7c1f82c734fb0275f1085234c91a21d"
    assert source.bytes == 249282
    assert source.applies_from == date(2011, 1, 3)
    source_text = (bundled_path() / source.corpus_path).read_text(encoding="utf-8")
    assert "Última actualización publicada el 23/06/2026" in source_text
    assert "Se aprueba el modelo 210" in source_text


def test_modelo_210_annual_agrupacion_rule_is_boe_corpus_backed() -> None:
    """The 0A selector and grouped-row contract cite the consolidated Article 2 text."""
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]
    legal = {_M210_AGRUPACION_ORDER_REF: catalogues.legal[_M210_AGRUPACION_ORDER_REF]}

    verify_legal_catalogue(legal, source_root=bundled_path())

    assert _M210_AGRUPACION_ORDER_REF in modelo.legal_refs
    assert _M210_AGRUPACION_ORDER_REF in revision.legal_refs
    reference = legal[_M210_AGRUPACION_ORDER_REF]
    assert reference.document_id == "BOE-A-2010-19707"
    assert reference.article == "2"
    assert reference.corpus_ref == "corpus/normatives/html/orden-eha-3316-2010.html#a2"
    assert "mismo código de tipo de renta" in reference.required_text
    assert "código específico de tipo de renta, el 35" in reference.required_text
    assert "En ningún caso las rentas agrupadas pueden compensarse entre sí." in reference.required_text


def test_modelo_210_irnr_sources_separate_aeat_guidance_from_boe_layout() -> None:
    modelo, catalogues = _load_modelo_210()

    procedure = catalogues.sources["aeat-modelo-210-procedure"]
    assert "aeat-modelo-210-procedure" in modelo.source_refs
    assert procedure.evidence_tier == "official_source_guidance"
    assert procedure.authority == "aeat"
    assert procedure.kind == "instructions"
    assert procedure.corpus_path == "corpus/aeat_official/instructions/modelo_210/files/modelo-210-instrucciones.html"
    assert (bundled_path() / procedure.corpus_path).is_file()

    m216_procedure = catalogues.sources["aeat-modelo-216-procedure"]
    assert m216_procedure.evidence_tier == "official_source_guidance"
    assert m216_procedure.authority == "aeat"
    assert m216_procedure.kind == "instructions"
    assert (bundled_path() / m216_procedure.corpus_path).is_file()

    assert catalogues.sources["boe-modelo-210-2024-form-layout"].evidence_tier == "layout_authority"
    assert catalogues.sources["boe-modelo-216-form-layout"].evidence_tier == "layout_authority"


def test_modelo_210_2026_order_is_bundled_and_referenced_by_current_surfaces() -> None:
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]

    deadline_source = catalogues.sources["boe-modelo-210-2026-deadline-update"]
    layout_2026_source = catalogues.sources["boe-modelo-210-2026-form-layout"]
    layout_2024_source = catalogues.sources["boe-modelo-210-2024-form-layout"]

    assert deadline_source.corpus_path == "corpus/normatives/html/orden-hac-623-2026.html"
    assert deadline_source.sha256 == "b901936072eb6bd8213dd84e9bd493a65d10b652b3b62dbe42228e1094f38074"
    assert deadline_source.bytes == 64566
    assert deadline_source.source_url == "https://www.boe.es/buscar/doc.php?id=BOE-A-2026-13573"
    assert deadline_source.published_at == date(2026, 6, 23)
    assert deadline_source.applies_from == date(2026, 1, 1)
    assert deadline_source.kind == "instructions"

    assert layout_2024_source.applies_to == date(2026, 12, 31)
    assert layout_2026_source.corpus_path == deadline_source.corpus_path
    assert layout_2026_source.applies_from == date(2027, 1, 1)

    assert "boe-modelo-210-2026-deadline-update" in revision.source_refs
    assert "boe-modelo-210-2026-form-layout" in revision.source_refs
    filing_link = next(link for link in revision.application_links if link.surface == "filing")
    assert "boe-modelo-210-2026-deadline-update" in filing_link.source_refs
    assert any(ref.workbook_source == "boe-modelo-210-2026-form-layout" for ref in revision.workbook_parity_refs)

    extracted_order = _orden_hac_623_2026_extracted_markdown()
    assert "anexo de “desglose de dividendos”" in extracted_order
    assert "desglose de gastos deducibles de inmuebles arrendados o subarrendados" in extracted_order
    assert "desde el día 1 de abril hasta el 23 de diciembre" in extracted_order
    assert "autoliquidaciones que se presenten desde el 1 de enero de 2027" in extracted_order
    assert "devengos correspondientes a 2026" in extracted_order


def test_modelo_210_interest_rate_is_grounded_in_unconditional_art_25_1_f() -> None:
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]
    parameter = next(param for param in revision.parameters if param.id == "m210-tipo-gravamen-2025")
    rates = {row.key: row.value for row in parameter.keyed_brackets}

    assert rates["interest"] == Decimal("0.19")

    art_25_1_f = catalogues.legal["trlirnr-rdleg-5-2004:art-25.1.f"]
    assert any(
        "Intereses y otros rendimientos obtenidos por la cesion a terceros" in text for text in art_25_1_f.required_text
    )
    assert "condicion de residencia UE/EEE" in (art_25_1_f.notes or "")

    corpus_paragraph = _trlirnr_corpus_paragraph("a25-1-f")
    assert "Intereses y otros rendimientos obtenidos por la cesion a terceros" in corpus_paragraph
    assert "Ganancias patrimoniales" in corpus_paragraph
    assert "Union Europea" not in corpus_paragraph
    assert "Espacio Economico Europeo" not in corpus_paragraph


def test_modelo_210_dividend_rate_is_grounded_in_unconditional_art_25_1_f() -> None:
    """Art. 25.1.f.1º dividends: the same unconditional 19% as interest / ganancia_patrimonial.

    TRLIRNR art. 25.1.f enumerates three income classes at 19 percent: 1º
    dividendos, 2º intereses, 3º ganancias patrimoniales. Before this test the
    registry's baseline rate table wired the 2º and 3º rows but had no
    ``tipo_renta="dividend"`` row at all, so a non-resident with Spanish-source
    dividend income (a routine M210 category with its own EUR 1,500 exemption
    per the AEAT instructions) had no correct-rate path and fell to the
    fail-closed baseline-deferred BLOCKING refusal.
    """
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]
    parameter = next(param for param in revision.parameters if param.id == "m210-tipo-gravamen-2025")
    rates = {row.key: row.value for row in parameter.keyed_brackets}

    assert rates["dividend"] == Decimal("0.19")
    assert TipoRentaIrnr("dividend") is TipoRentaIrnr.DIVIDEND

    art_25_1_f = catalogues.legal["trlirnr-rdleg-5-2004:art-25.1.f"]
    assert any(
        "Dividendos y otros rendimientos derivados de la participacion en los fondos propios de una entidad" in text
        for text in art_25_1_f.required_text
    )
    assert "condicion de residencia UE/EEE" in (art_25_1_f.notes or "")

    corpus_paragraph = _trlirnr_corpus_paragraph("a25-1-f")
    assert "Dividendos y otros rendimientos derivados de la participacion en los fondos propios" in corpus_paragraph
    assert "Union Europea" not in corpus_paragraph
    assert "Espacio Economico Europeo" not in corpus_paragraph


def test_modelo_210_searchable_extract_preserves_unconditional_art_25_1_f() -> None:
    corpus_paragraph = _trlirnr_corpus_paragraph("a25-1-f")
    extracted_lines = _trlirnr_extracted_markdown().splitlines()
    extracted_art_25_1_f = next(line for line in extracted_lines if line.startswith("f) "))

    assert extracted_art_25_1_f == corpus_paragraph
    assert "Intereses y otros rendimientos obtenidos por la cesion a terceros" in extracted_art_25_1_f
    assert "Ganancias patrimoniales" in extracted_art_25_1_f
    assert "residentes en otro Estado miembro" not in extracted_art_25_1_f


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
    assert source.sha256 == "a954f18028c83634641e2197b7ca67fc540686f0117bcae69fc96c51bc15ed83"

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
    convenio = load_convenio_authority(bundled_path("registry", "aeat", "treaties"))
    ar_treaty_def = convenio.treaties["AR"]
    ar_pension = next(row for row in ar_treaty_def.overrides if row.tipo_renta is TipoRentaIrnr.PENSION)

    assert ar_pension.kind is ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF
    assert ar_pension.rate is None
    assert ar_pension.legal_ref_anchor == "convenio-es-ar-1992:art-19"
    assert ar_pension.legal_refs == (
        "convenio-es-ar-1992:art-19",
        "trlirnr-rdleg-5-2004:art-25.1.b",
    )

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

    casillas = {casilla.id: casilla for casilla in revision.casillas}
    assert "trlirnr-rdleg-5-2004:art-25.1.b" in modelo.legal_refs
    assert "trlirnr-rdleg-5-2004:art-25.1.b" in revision.legal_refs
    assert "trlirnr-rdleg-5-2004:art-25.1.b" in casillas["tipo_renta"].legal_refs
    assert "trlirnr-rdleg-5-2004:art-25.1.b" in casillas["tipo_gravamen"].legal_refs
    assert "trlirnr-rdleg-5-2004:art-25.1.b" in casillas["cuota_integra"].legal_refs


def test_modelo_210_2025_verification_predicates_guard_representante_fiscal_and_base_imponible() -> None:
    """The 2025 revision carries both the representante-fiscal gate and the no-silent-

    under-declaration base-imponible advisory in the same verification_predicates
    array (per aeat-registry-authority-flow, the array is
    declared inline in revision.toml fragments, not in a bindings/ subdirectory).
    """
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]
    predicates = {p.predicate_id: p for p in revision.verification_predicates}

    representante_fiscal = predicates["m210-representante-fiscal-required"]
    assert representante_fiscal.expression == (
        'profile_field_required("representante_fiscal_nif", "non_resident_irnr_non_eea")'
    )
    assert representante_fiscal.finding_kind == "BLOCKING_RULE"
    assert "trlirnr-rdleg-5-2004:art-10" in tuple(str(r) for r in representante_fiscal.legal_refs)

    base_imponible_guard = predicates["modelo-210-2025-rendimientos-integros-implica-base-imponible"]
    assert base_imponible_guard.expression == 'implies_nonzero(["rendimientos_integros", "base_imponible"])'
    assert base_imponible_guard.finding_kind == "ADVISORY"
    assert "trlirnr-rdleg-5-2004:art-24" in tuple(str(r) for r in base_imponible_guard.legal_refs)

    casillas = {casilla.id for casilla in revision.casillas}
    assert "rendimientos_integros" in casillas
    assert "base_imponible" in casillas

    art_24 = catalogues.legal["trlirnr-rdleg-5-2004:art-24"]
    assert art_24.corpus_ref.endswith("#a24")
    # art-24's anchor sits on the <h1> heading, not a per-paragraph <p id=...>
    # (unlike the 25.1.* sub-letter anchors), so cross-check it the same way
    # the registry-build legal-catalogue validator does rather than via the
    # per-paragraph slicing helper used for the lettered sub-anchors above.
    verify_legal_catalogue({"trlirnr-rdleg-5-2004:art-24": art_24}, source_root=bundled_path())
    corpus_text = bundled_path("corpus", "normatives", "html", "trlirnr-rdleg-5-2004.html").read_text(
        encoding="utf-8",
    )
    for required_text in art_24.required_text:
        assert required_text in corpus_text


def test_modelo_210_2025_inmobiliaria_branch_carries_categorical_conditional_advisory() -> None:
    """The 2025 revision carries the inmobiliaria-branch categorical-conditional advisory.

    Per the m210 categorical-conditional predicate decision: the inmobiliaria
    branch's silent-zero risk (tipo_renta == "inmobiliaria" implies a
    non-zero base_imponible) is gated on a categorical casilla condition the
    implies_nonzero operator cannot express, so it uses the
    casilla_equals_implies_nonzero operator instead. Co-exists with the
    pre-existing representante-fiscal and rendimientos-integros-implica-
    base-imponible predicates in the same array, neither of which is
    modified by this addition.
    """
    modelo, catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]
    predicates = {p.predicate_id: p for p in revision.verification_predicates}

    assert set(predicates) == {
        "m210-representante-fiscal-required",
        "modelo-210-2025-rendimientos-integros-implica-base-imponible",
        "modelo-210-2025-inmobiliaria-implica-base-imponible",
        "modelo-210-2025-ue-residente-requiere-residencia-ue-eee",
    }

    inmobiliaria_guard = predicates["modelo-210-2025-inmobiliaria-implica-base-imponible"]
    assert inmobiliaria_guard.expression == (
        'casilla_equals_implies_nonzero(["tipo_renta", "inmobiliaria", "base_imponible"])'
    )
    assert inmobiliaria_guard.finding_kind == "ADVISORY"
    legal_refs = tuple(str(r) for r in inmobiliaria_guard.legal_refs)
    assert "trlirnr-rdleg-5-2004:art-13.1.h" in legal_refs
    assert "trlirnr-rdleg-5-2004:art-24" in legal_refs

    casillas = {casilla.id for casilla in revision.casillas}
    assert "tipo_renta" in casillas
    assert "base_imponible" in casillas

    art_13_1_h = catalogues.legal["trlirnr-rdleg-5-2004:art-13.1.h"]
    assert art_13_1_h.corpus_ref.endswith("#a13-1-h")
    verify_legal_catalogue({"trlirnr-rdleg-5-2004:art-13.1.h": art_13_1_h}, source_root=bundled_path())
