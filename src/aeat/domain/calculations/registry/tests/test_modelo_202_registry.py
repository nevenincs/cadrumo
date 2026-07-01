"""Tests for committed Modelo 202 registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .._legal import verify_legal_catalogue
from .._schema import ModeloDefinition, RegistryCatalogues
from .._snapshot import build_snapshot
from .._validate import RegistryValidator
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


_M202_BASE_IMPONIBLE_PREVIA_ADVISORY_PREDICATE_ID = (
    "modelo-202-base-imponible-previa-determinada-cuando-resultado-positivo"
)


@pytest.mark.parametrize("revision_id", ["2019-2022", "2023-2024", "2025-y-siguientes"])
def test_committed_modelo_202_guards_base_imponible_previa_under_declaration(revision_id: str) -> None:
    """Every M202 revision carries the clave 04 -> clave 13 silent-under-declaration advisory.

    The base imponible previa (clave 13) is formula-derived from the resultado
    contable (clave 04, manual, required=false): clave 13 = clave 04 + clave 38
    - clave 39. Without an explicit guard a future registry edit that decoupled
    clave 13 from clave 04 could silently re-open a M200-class silent
    under-declaration with no test failing it (`no-silent-under-declaration`).
    """
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions[revision_id]

    predicate = next(
        p
        for p in revision.verification_predicates
        if p.predicate_id == _M202_BASE_IMPONIBLE_PREVIA_ADVISORY_PREDICATE_ID
    )

    assert predicate.expression == 'implies_nonzero(["04", "13"])'
    assert predicate.finding_kind == "ADVISORY"
    assert "ley-27-2014:art-40-3" in tuple(str(r) for r in predicate.legal_refs)
    assert "ley-27-2014:art-40" in tuple(str(r) for r in predicate.legal_refs)


_M202_B2_TIPO_3_ADVISORY_PREDICATE_ID = "modelo-202-2025-b2-base-tipo-3-implica-importe-pago-fraccionado-tipo-3"
_M202_B2_TIPO_4_ADVISORY_PREDICATE_ID = "modelo-202-2025-b2-base-tipo-4-implica-importe-pago-fraccionado-tipo-4"
_M202_B2_RESULTADO_PREVIO_ADVISORY_PREDICATE_ID = "modelo-202-b2-resultado-previo-implica-modalidad-40-3-resultado"


def test_committed_modelo_202_2025_guards_b2_tipo_3_and_tipo_4_under_declaration() -> None:
    """The 2025-only B2 casos especificos tipo-3/tipo-4 tramos guard their own base-to-importe formula.

    Claves 63 and 66 are formula-derived (``percent``) from claves 61/62 and
    64/65 respectively; both tramos exist only in the 2025-y-siguientes
    revision (`test_committed_modelo_202_marks_2025_only_b2_rate_bands_as_intentional_singletons`).
    See the `modelo-verify-nonzero-guards` m202-deferred-items audit
    (2026-07-01) for the full B2-lane investigation.
    """
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions["2025-y-siguientes"]
    predicates = {p.predicate_id: p for p in revision.verification_predicates}

    tipo_3 = predicates[_M202_B2_TIPO_3_ADVISORY_PREDICATE_ID]
    assert tipo_3.expression == 'implies_nonzero(["61", "63"])'
    assert tipo_3.finding_kind == "ADVISORY"
    assert "ley-27-2014:art-40-3" in tuple(str(r) for r in tipo_3.legal_refs)
    assert "ley-27-2014:art-29" in tuple(str(r) for r in tipo_3.legal_refs)

    tipo_4 = predicates[_M202_B2_TIPO_4_ADVISORY_PREDICATE_ID]
    assert tipo_4.expression == 'implies_nonzero(["64", "66"])'
    assert tipo_4.finding_kind == "ADVISORY"
    assert "ley-27-2014:art-40-3" in tuple(str(r) for r in tipo_4.legal_refs)
    assert "ley-27-2014:art-29" in tuple(str(r) for r in tipo_4.legal_refs)


def _casilla_refs_in_expression(expression: object) -> set[str]:
    """Recursively collect every ``casilla_id`` referenced by a formula expression tree."""
    refs: set[str] = set()
    casilla_id = getattr(expression, "casilla_id", None)
    if casilla_id is not None:
        refs.add(str(casilla_id))
    for arg in getattr(expression, "args", ()):
        refs |= _casilla_refs_in_expression(arg)
    return refs


@pytest.mark.parametrize("revision_id", ["2019-2022", "2023-2024", "2025-y-siguientes"])
def test_committed_modelo_202_b2_resultado_previo_remains_unwired_from_modalidad_40_3_resultado(
    revision_id: str,
) -> None:
    """Clave 26 (B2 resultado previo) is a confirmed, undecided registry defect -- not a guard candidate.

    Every M202 revision's ``modalidad-40-3-resultado`` formula (target clave
    32) reads only clave 18 (the B1 caso general resultado previo); clave 26
    (the B2 casos especificos resultado previo, itself formula-derived from
    claves 22 + 25 + 63 + 66 + 50 + 42 + 51 + 52) is never referenced by any
    formula in this revision. A taxpayer whose modalidad 40.3 case is B2-only
    would have their entire B2 computation silently dropped from the final
    ``cantidad a ingresar`` (clave 34) -- a suspected formula-correctness
    defect, not a false-positive-risk case. No ``implies_nonzero`` predicate is
    authored over this relationship because the correct combination semantics
    (whether clave 32 should sum 18+26, select whichever is populated, or some
    other treatment) cannot be safely inferred from the bundled corpus or the
    registry's own vague formula source citation ("es un importe calculado")
    without further legal/workbook verification
    (`aeat-safety-legal-gates`, `no-tautological-calculation-tests`). See the
    `modelo-verify-nonzero-guards` m202-deferred-items audit (2026-07-01) for
    the full investigation and the recommended follow-up. This test locks the
    deliberate absence: closing the prerequisite (verifying and wiring clave 26
    into clave 32) must update or remove this assertion.
    """
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions[revision_id]

    modalidad_40_3_resultado_formula = next(f for f in revision.formulas if f.target_casilla_id == "32")
    referenced_casillas = _casilla_refs_in_expression(modalidad_40_3_resultado_formula.expression)
    assert "26" not in referenced_casillas, (
        "clave 26 (B2 resultado previo) now feeds clave 32 (modalidad-40-3-resultado); "
        "the modelo-verify-nonzero-guards m202-deferred-items audit's wiring-gap finding is "
        "resolved -- update this test and consider authoring the deferred implies_nonzero(26, 32) "
        "advisory now that the correct combination semantics are confirmed"
    )

    predicate_ids = {p.predicate_id for p in revision.verification_predicates}
    assert _M202_B2_RESULTADO_PREVIO_ADVISORY_PREDICATE_ID not in predicate_ids


_M202_MINIMO_A_INGRESAR_CN_10M_ADVISORY_PREDICATE_ID = "modelo-202-04-implica-minimo-a-ingresar-cn-10m"


@pytest.mark.parametrize("revision_id", ["2019-2022", "2023-2024", "2025-y-siguientes"])
def test_committed_modelo_202_minimo_a_ingresar_cn_10m_remains_unguarded(revision_id: str) -> None:
    """Clave 33 (minimo a ingresar, CN >= 10 millones euros) is a grounded, documented non-guard.

    Clave 33 is fully manual with no formula linkage in every revision; the
    LIS minimum-payment-on-account floor for INCN >= EUR 10.000.000 groups is
    not established by any legal-catalogue entry or bundled corpus text this
    codebase carries (the closest grounded provisions, ley-27-2014:art-40 and
    art-29, cover only the ordinary modalidad 40.2/40.3 mechanics, not the
    minimum-tax floor), and the floor applies only to a CN-gated subset of
    filers -- a categorical fact no casilla in this chain carries. No clean
    antecedent casilla exists (the same shape as the M714 riskier-edge
    non-guards and the M210 inmobiliaria-branch deferral): authoring
    ``implies_nonzero(["04", "33"])`` would fire on every filer below the
    CN >= 10.000.000 threshold who correctly leaves clave 33 blank -- the
    overwhelming majority of filers -- a structurally guaranteed
    false-positive rate. See the `modelo-verify-nonzero-guards`
    m202-deferred-items audit (2026-07-01) for the full investigation.
    """
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions[revision_id]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    casilla_33 = casillas_by_id["33"]
    assert casilla_33.formula is None
    assert casilla_33.binding is None

    predicate_ids = {p.predicate_id for p in revision.verification_predicates}
    assert _M202_MINIMO_A_INGRESAR_CN_10M_ADVISORY_PREDICATE_ID not in predicate_ids
