"""Tests for committed Modelo 202 registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator, build_snapshot
from .._legal import verify_legal_catalogue
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M202_BASE_ORDER_REF = "orden-hfp-227-2017:art-1"
_M202_2018_ORDER_REF = "orden-hac-941-2018:art-primero-5-anexo-i"
_M202_2023_ORDER_REF = "orden-hfp-312-2023:art-unico-1-anexo-i"
_M202_2025_ORDER_REF = "orden-hac-262-2025:art-unico-1-anexo-i"

_M202_ORDER_REFS = (
    _M202_BASE_ORDER_REF,
    _M202_2018_ORDER_REF,
    _M202_2023_ORDER_REF,
    _M202_2025_ORDER_REF,
)

_M202_SOURCE_EXPECTATIONS = {
    "boe-modelo-202-base-order": (
        "corpus/normatives/html/orden-hfp-227-2017.html",
        "6b6d43ce28a1117d93d97c20436004e7ac18adf80200d3636a5bbde65219b2ee",
        131156,
        date(2017, 3, 16),
    ),
    "boe-modelo-202-2018-amendment": (
        "corpus/normatives/html/orden-hac-941-2018.html",
        "2481fd9016b8216a8a2bbfae9ea23e8846850a9dfb0039edd7e078e075c84218",
        58327,
        date(2018, 9, 15),
    ),
    "boe-modelo-202-2023-amendment": (
        "corpus/normatives/html/orden-hfp-312-2023.html",
        "a318fa1d8afcac5ebf671f5e6b24a57f392004569b97ca5cfa337d69b23ee64c",
        43041,
        date(2023, 4, 1),
    ),
    "boe-modelo-202-2025-amendment": (
        "corpus/normatives/html/orden-hac-262-2025.html",
        "f0d43850934d3beca67e1c2ccd49bb484151d5580e5f4126e944097ce0399e12",
        39732,
        date(2025, 3, 20),
    ),
}


def _load_modelo_202() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("202")


def test_committed_modelo_202_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_202()

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    assert set(modelo.revisions) == {"2019-2022", "2023-2024", "2025-y-siguientes"}


def test_committed_modelo_202_order_chain_is_boe_corpus_backed() -> None:
    modelo, catalogues = _load_modelo_202()
    legal = {ref_id: catalogues.legal[ref_id] for ref_id in _M202_ORDER_REFS}

    verify_legal_catalogue(legal, source_root=bundled_path())

    assert set(_M202_ORDER_REFS).issubset(modelo.legal_refs)
    assert set(_M202_SOURCE_EXPECTATIONS).issubset(modelo.source_refs)

    expected_by_revision = {
        "2019-2022": (
            (_M202_BASE_ORDER_REF, _M202_2018_ORDER_REF),
            ("boe-modelo-202-base-order", "boe-modelo-202-2018-amendment"),
        ),
        "2023-2024": (
            (_M202_BASE_ORDER_REF, _M202_2023_ORDER_REF),
            ("boe-modelo-202-base-order", "boe-modelo-202-2023-amendment"),
        ),
        "2025-y-siguientes": (
            (_M202_BASE_ORDER_REF, _M202_2025_ORDER_REF),
            ("boe-modelo-202-base-order", "boe-modelo-202-2025-amendment"),
        ),
    }
    for revision_id, (order_refs, source_refs) in expected_by_revision.items():
        revision = modelo.revisions[revision_id]
        assert revision.orden_aplicabilidad == order_refs
        assert set(order_refs).issubset(revision.legal_refs)
        assert set(source_refs).issubset(revision.source_refs)
        assert len(revision.workbook_parity_refs) == 1
        workbook_ref = revision.workbook_parity_refs[0]
        assert workbook_ref.formula_coverage == "record_design_layout"
        assert set(order_refs).issubset(workbook_ref.legal_refs)
        assert set(source_refs).issubset(workbook_ref.source_refs)
        construct = revision.constructs[0]
        assert set(order_refs).issubset(construct.legal_refs)
        assert set(source_refs).issubset(construct.source_refs)

    base = legal[_M202_BASE_ORDER_REF]
    assert base.document_id == "BOE-A-2017-2778"
    assert base.article == "1"
    assert base.consolidated_as_of == date(2025, 3, 19)
    assert "Se aprueba el modelo 202" in base.required_text

    amendment_expectations = {
        _M202_2018_ORDER_REF: ("BOE-A-2018-12515", date(2018, 9, 15), "octubre de 2018"),
        _M202_2023_ORDER_REF: ("BOE-A-2023-8120", date(2023, 4, 1), "abril de 2023"),
        _M202_2025_ORDER_REF: ("BOE-A-2025-5407", date(2025, 3, 20), "abril de 2025"),
    }
    for ref_id, (document_id, effective_from, required_fragment) in amendment_expectations.items():
        reference = legal[ref_id]
        assert reference.document_id == document_id
        assert reference.article in {"primero.5", "unico.1"}
        assert reference.effective_from == effective_from
        assert any(required_fragment in text for text in reference.required_text)

    for source_id, (corpus_path, sha256, byte_count, applies_from) in _M202_SOURCE_EXPECTATIONS.items():
        source = catalogues.sources[source_id]
        assert source.corpus_path == corpus_path
        assert source.sha256 == sha256
        assert source.bytes == byte_count
        assert source.applies_from == applies_from
        source_text = (bundled_path() / source.corpus_path).read_text(encoding="utf-8")
        assert source.source_url.startswith("https://www.boe.es/")
        assert "modelo 202" in source_text or "Modelo 202" in source_text


def test_committed_modelo_202_marks_2025_only_b2_rate_bands_as_intentional_singletons() -> None:
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions["2025-y-siguientes"]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    for casilla_id in ("61", "62", "64", "65"):
        casilla = casillas_by_id[casilla_id]
        assert casilla.semantic_role_cardinality == "intentional_singleton"
        assert casilla.semantic_role_cardinality_reason is not None
        assert "2025-only" in casilla.semantic_role_cardinality_reason


def test_committed_modelo_202_static_cross_reference_and_construct_are_declared() -> None:
    modelo, catalogues = _load_modelo_202()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="2P",
    )
    decision = snapshot.live_cross_references["modelo-202-static-documentation"]
    construct = snapshot.constructs["modelo-202-foundation"]

    assert decision.surface == "static_official_documentation"
    assert decision.requires_authentication is False
    assert decision.synthetic_data_allowed is False
    assert "presentation" in decision.forbidden_actions
    assert "modelo-202-portal" in construct.application_links
    assert set(construct.live_cross_references) == {"modelo-202-static-documentation"}
    assert set(construct.workbook_parity_refs) == {"modelo-202-dr-xlsx-2025"}
    assert "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior" in construct.bindings
    assert "modelo-202-2025-y-siguientes-dep-200-cuota-base" in construct.dependency_classifications
    assert "modelo-202-2025-y-siguientes-rel-cuota-base-1p" in construct.relations
    assert "modelo-202-2025-y-siguientes-rel-cuota-base-2p-3p" in construct.relations


def test_committed_modelo_202_cuota_base_relation_periods_and_year_offsets_are_declared() -> None:
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions["2025-y-siguientes"]
    relations = {relation.id: relation for relation in revision.relations}

    one_p = relations["modelo-202-2025-y-siguientes-rel-cuota-base-1p"]
    assert one_p.source_modelo == "200"
    assert one_p.source_casilla_id == "DP200014B:00592"
    assert one_p.target_binding == "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
    assert one_p.source_revision_selector.filing_year_delta == -2
    assert one_p.period_alignment.filing_year_delta == -2
    assert one_p.source_periods == ("0A",)
    assert one_p.target_periods == ("1P",)

    two_p_three_p = relations["modelo-202-2025-y-siguientes-rel-cuota-base-2p-3p"]
    assert two_p_three_p.source_modelo == "200"
    assert two_p_three_p.source_casilla_id == "DP200014B:00592"
    assert two_p_three_p.target_binding == "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
    assert two_p_three_p.source_revision_selector.filing_year_delta == -1
    assert two_p_three_p.period_alignment.filing_year_delta == -1
    assert two_p_three_p.source_periods == ("0A",)
    assert two_p_three_p.target_periods == ("2P", "3P")
