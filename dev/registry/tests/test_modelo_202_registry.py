"""Tests for committed Modelo 202 registry foundation."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from functools import lru_cache
from html import unescape

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.binding_temporal import FilingYearOffsetByTargetPeriod, TargetPeriods
from cadrumo.domain.calculations.registry.formula_expression import evaluate_expression
from cadrumo.domain.calculations.registry.relations import (
    relation_prefill_bindings_for_period,
    relation_source_requirements,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    open_ended_revision,
)
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot

from ..compiler.legal_grounding import verify_legal_catalogue
from ..conformance.registry_schema_support import committed_modelo
from .profile_schema_support import committed_registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

# The only revision that carries the B2 casos especificos tipo-3/tipo-4 tramos.
_B2_BANDS_REVISION = str(open_ended_revision("202").id)

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
        "497ce0a6cdbf7deb19c3bee0839861325c14a2fbfe7714eb47722c2084b9cef7",
        130975,
    ),
    "boe-modelo-202-2018-amendment": (
        "corpus/normatives/html/orden-hac-941-2018.html",
        "05180686f258df500d76f300801b8896e8b086e15870d8ca7bf40ad61b104778",
        58193,
    ),
    "boe-modelo-202-2023-amendment": (
        "corpus/normatives/html/orden-hfp-312-2023.html",
        "261ac0000942e4ea0fb428fc9a4ab94ee5f0b8d9a21a77317c7f5cea4ddda2b0",
        42907,
    ),
    "boe-modelo-202-2025-amendment": (
        "corpus/normatives/html/orden-hac-262-2025.html",
        "aba2815c04843d892cceea488b81643f614fddaa0f524e4c7fbdf1e7784b9b41",
        39598,
    ),
}
_M202_REVISION_IDS = tuple(str(revision.id) for revision in authored_revisions("202"))
_M202_CLOSED_REVISION_IDS = tuple(
    str(revision.id) for revision in authored_revisions("202") if revision.valid_to is not None
)
# The instruction source each closed revision is filed on, in revision order.
_M202_CLOSED_REVISION_INSTRUCTION_SOURCES = (
    "aeat-modelo-202-instructions-2018-2022",
    "aeat-modelo-202-instructions-2023-2024",
)


def _boe_dates(source_text: str, pattern: str) -> list[date]:
    return [date(int(year), int(month), int(day)) for day, month, year in re.findall(pattern, unescape(source_text))]


def _entry_into_force(source_text: str) -> date:
    """Return the date the order's own BOE page states it entered into force."""
    dates = _boe_dates(source_text, r"Fecha de entrada en vigor: (\d{2})/(\d{2})/(\d{4})") or _boe_dates(
        source_text, r"Texto original, publicado el \d{2}/\d{2}/\d{4}, en vigor a partir del (\d{2})/(\d{2})/(\d{4})"
    )
    assert len(set(dates)) == 1, dates
    return dates[0]


def _last_consolidated_update(source_text: str) -> date:
    """Return the latest consolidation date the order's BOE page states."""
    return max(_boe_dates(source_text, r"ltima actualización,? publicada el (\d{2})/(\d{2})/(\d{4})"))


def _corpus_text(source_id: str) -> str:
    _modelo, catalogues = _load_modelo_202()
    return (bundled_path() / catalogues.sources[source_id].corpus_path).read_text(encoding="utf-8")


def _instruction_window(source_id: str) -> tuple[date, date]:
    """Return the first and last day of the exercises an instruction source's id names."""
    match = re.search(r"-(\d{4})-(\d{4})$", source_id)
    assert match is not None, source_id
    return date(int(match.group(1)), 1, 1), date(int(match.group(2)), 12, 31)


@lru_cache
def _load_modelo_202() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("202")


def test_committed_modelo_202_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_202()

    committed_registry_validator(catalogues).validate_modelo(modelo)

    assert set(modelo.revisions) == set(_M202_REVISION_IDS)


def test_committed_modelo_202_order_chain_is_boe_corpus_backed() -> None:
    modelo, catalogues = _load_modelo_202()
    legal = {ref_id: catalogues.legal[ref_id] for ref_id in _M202_ORDER_REFS}

    verify_legal_catalogue(legal, source_root=bundled_path())

    assert set(_M202_ORDER_REFS).issubset(modelo.legal_refs)
    assert set(_M202_SOURCE_EXPECTATIONS).issubset(modelo.source_refs)

    # The orders and sources each authored revision is filed on, in revision order.
    expected_by_revision = dict(
        zip(
            _M202_REVISION_IDS,
            (
                (
                    (_M202_BASE_ORDER_REF, _M202_2018_ORDER_REF),
                    ("boe-modelo-202-base-order", "boe-modelo-202-2018-amendment"),
                ),
                (
                    (_M202_BASE_ORDER_REF, _M202_2023_ORDER_REF),
                    ("boe-modelo-202-base-order", "boe-modelo-202-2023-amendment"),
                ),
                (
                    (_M202_BASE_ORDER_REF, _M202_2025_ORDER_REF),
                    ("boe-modelo-202-base-order", "boe-modelo-202-2025-amendment"),
                ),
            ),
            strict=True,
        )
    )
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
    assert base.consolidated_as_of == _last_consolidated_update(_corpus_text("boe-modelo-202-base-order"))
    assert "Se aprueba el modelo 202" in base.required_text

    # The first-application clause ("aplicable por primera vez... octubre de
    # 2018" etc.) lives in each order's disposición final, outside the
    # articulo-primero/unico anchor these references are deliberately scoped
    # to (commit d07696cc73), so it is no longer part of required_text here.
    # Each order's entry into force is the one its own BOE page states.
    amendment_expectations = {
        _M202_2018_ORDER_REF: ("BOE-A-2018-12515", "boe-modelo-202-2018-amendment"),
        _M202_2023_ORDER_REF: ("BOE-A-2023-8120", "boe-modelo-202-2023-amendment"),
        _M202_2025_ORDER_REF: ("BOE-A-2025-5407", "boe-modelo-202-2025-amendment"),
    }
    for ref_id, (document_id, source_id) in amendment_expectations.items():
        reference = legal[ref_id]
        assert reference.document_id == document_id
        assert reference.article in {"primero.5", "unico.1"}
        assert reference.effective_from == _entry_into_force(_corpus_text(source_id))

    for source_id, (corpus_path, sha256, byte_count) in _M202_SOURCE_EXPECTATIONS.items():
        source = catalogues.sources[source_id]
        assert source.evidence_tier == "layout_authority"
        assert source.corpus_path == corpus_path
        assert source.sha256 == sha256
        assert source.bytes == byte_count
        source_text = (bundled_path() / source.corpus_path).read_text(encoding="utf-8")
        assert source.applies_from == _entry_into_force(source_text)
        assert source.source_url.startswith("https://www.boe.es/")
        assert "modelo 202" in source_text or "Modelo 202" in source_text


def test_committed_modelo_202_closed_revisions_use_period_matching_instruction_sources() -> None:
    modelo, catalogues = _load_modelo_202()
    for revision_id, expected_source_ref in zip(
        _M202_CLOSED_REVISION_IDS, _M202_CLOSED_REVISION_INSTRUCTION_SOURCES, strict=True
    ):
        applies_from, applies_to = _instruction_window(expected_source_ref)
        forbidden_source_refs = (
            "aeat-modelo-202-instructions",
            *(other for other in _M202_CLOSED_REVISION_INSTRUCTION_SOURCES if other != expected_source_ref),
        )
        revision = modelo.revisions[revision_id]
        instruction_source = catalogues.sources[expected_source_ref]

        assert instruction_source.evidence_tier == "official_source_guidance"
        assert instruction_source.applies_from == applies_from
        assert instruction_source.applies_to == applies_to
        assert expected_source_ref in revision.source_refs

        revision_payload = revision.model_dump_json()
        for source_ref in forbidden_source_refs:
            assert f'"{source_ref}"' not in revision_payload, revision_id


def test_committed_modelo_202_marks_single_revision_b2_rate_bands_as_intentional_singletons() -> None:
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions[_B2_BANDS_REVISION]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    for casilla_id in ("61", "62", "64", "65"):
        casilla = casillas_by_id[casilla_id]
        assert casilla.semantic_role_cardinality == "intentional_singleton"
        assert casilla.semantic_role_cardinality_reason is not None
        assert f"{revision.valid_from.year}-only" in casilla.semantic_role_cardinality_reason


def test_committed_modelo_202_static_cross_reference_and_construct_are_declared() -> None:
    modelo, catalogues = _load_modelo_202()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year_envelope().horizon,
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
    assert set(construct.workbook_parity_refs) == {"modelo-202-dr-xlsx"}
    assert "modelo-202-cuota-base-ejercicio-anterior" in construct.bindings
    assert "modelo-202-dep-200-cuota-base" in construct.dependency_classifications
    assert "modelo-202-cuota-base-ejercicio-anterior" in construct.bindings


def test_committed_modelo_202_cuota_base_relation_periods_and_year_offsets_are_declared() -> None:
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions[_B2_BANDS_REVISION]
    binding, provider = next(
        item
        for item in relation_prefill_bindings_for_period(revision)
        if item[0].id == "modelo-202-cuota-base-ejercicio-anterior"
    )
    assert provider.source_modelo == "200"
    assert provider.declared_source_casilla_ids == ("DP200014B:00599",)
    assert provider.relation_kind == "cross_model_output"
    assert provider.dependency_role == "direct_calculation"
    assert isinstance(provider.temporal, FilingYearOffsetByTargetPeriod)
    assert provider.temporal.source_periods == ("0A",)
    assert provider.temporal.offsets == {"1P": -2, "2P": -1, "3P": -1}
    assert isinstance(binding.applicability, TargetPeriods)
    assert binding.applicability.periods == ("1P", "2P", "3P")

    # The offsets asserted above, applied to the filing year the requirements are resolved for.
    filing_year = filing_year_envelope().horizon
    expected_source_years = {"1P": filing_year - 2, "2P": filing_year - 1, "3P": filing_year - 1}
    for target_period, expected_source_year in expected_source_years.items():
        requirements = relation_source_requirements(revision, filing_year=filing_year, period=target_period)
        # 2P and 3P also require this year's earlier pagos fraccionados, so the
        # requirement under test is selected by its binding rather than by being
        # the only one.
        (requirement,) = [item for item in requirements if item.target_bindings == (binding.id,)]
        assert requirement.filing_year == expected_source_year
        assert requirement.periods == ("0A",)


def _expression_casilla_ids(expression: FormulaExpression) -> frozenset[str]:
    found: set[str] = set() if expression.casilla_id is None else {expression.casilla_id}
    for argument in expression.args:
        found |= _expression_casilla_ids(argument)
    return frozenset(found)


def test_committed_modelo_202_art_40_2_base_reads_the_modelo_200_box_net_of_retenciones() -> None:
    """Every instrucciones era defines the art. 40.2 base as the cuota minus deducciones and retenciones.

    The Modelo 200 cuota liquida is net of deducciones and bonificaciones only; the
    box the relation reads must also subtract the retenciones e ingresos a cuenta,
    in each authored Modelo 200 edition that calculates it. An applicability-grade
    edition computes nothing, so a relation reading it takes the filed value.
    """
    modelo, _catalogues = _load_modelo_202()
    modelo_200, _ = committed_modelo("200")
    relation_sources: set[str] = set()
    for revision in modelo.revisions.values():
        for binding, provider in relation_prefill_bindings_for_period(revision):
            if binding.id != "modelo-202-cuota-base-ejercicio-anterior":
                continue
            relation_sources.update(provider.declared_source_casilla_ids)
            cited = {text for citation in binding.source_citations for text in citation.required_text}
            assert "retenciones e ingresos a cuenta" in cited, revision.id
    assert relation_sources == {"DP200014B:00599"}
    calculating = [
        revision_200
        for revision_200 in modelo_200.revisions.values()
        if revision_200.effective_authority_grade is not RegistryAuthorityGrade.APPLICABILITY
    ]
    assert calculating, "no Modelo 200 edition calculates, so this check proves nothing"
    for revision_200 in calculating:
        retenciones = {
            casilla.id
            for casilla in revision_200.casillas
            if casilla.semantic_role == "is_retenciones_ingresos_a_cuenta"
        }
        assert retenciones, revision_200.id
        formulas = {formula.target_casilla_id: formula for formula in revision_200.formulas}
        operands = _expression_casilla_ids(formulas["DP200014B:00599"].expression)
        assert "DP200014B:00592" in operands, revision_200.id
        assert retenciones & operands, revision_200.id
        # The cuota liquida alone is not net of the retenciones the base subtracts.
        assert not retenciones & _expression_casilla_ids(formulas["DP200014B:00592"].expression), revision_200.id


_M202_BASE_IMPONIBLE_PREVIA_ADVISORY_PREDICATE_ID = (
    "modelo-202-base-imponible-previa-determinada-cuando-resultado-positivo"
)


def test_committed_modelo_202_guards_base_imponible_previa_under_declaration() -> None:
    """Every M202 revision carries the clave 04 -> clave 13 silent-under-declaration advisory.

    The base imponible previa (clave 13) is formula-derived from the resultado
    contable (clave 04, manual, required=false): clave 13 = clave 04 + clave 38
    - clave 39. Without an explicit guard a future registry edit that decoupled
    clave 13 from clave 04 could silently re-open a M200-class silent
    under-declaration with no test failing it (`no-silent-under-declaration`).
    """
    modelo, _catalogues = _load_modelo_202()
    for revision_id in _M202_REVISION_IDS:
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
_M202_B1_B2_RESULTADO_PREVIO_XOR_PREDICATE_ID = "modelo-202-b1-b2-resultado-previo-at-most-one-positive"


def test_committed_modelo_202_guards_b2_tipo_3_and_tipo_4_under_declaration() -> None:
    """The single-revision B2 casos especificos tipo-3/tipo-4 tramos guard their own base-to-importe formula.

    Claves 63 and 66 are formula-derived (``percent``) from claves 61/62 and
    64/65 respectively; both tramos exist only in the 2025-y-siguientes
    revision (`test_committed_modelo_202_marks_single_revision_b2_rate_bands_as_intentional_singletons`).
    See the `modelo-verify-nonzero-guards` m202-deferred-items audit
    (2026-07-01) for the full B2-lane investigation.
    """
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions[_B2_BANDS_REVISION]
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


def _casilla_refs_in_expression(expression: FormulaExpression) -> set[str]:
    """Recursively collect every ``casilla_id`` referenced by a formula expression tree."""
    refs: set[str] = set()
    if expression.casilla_id is not None:
        refs.add(str(expression.casilla_id))
    for arg in expression.args:
        refs |= _casilla_refs_in_expression(arg)
    return refs


def test_committed_modelo_202_b2_resultado_previo_feeds_modalidad_40_3_resultado() -> None:
    """Clave 26 (B2 resultado previo) now feeds clave 32 (modalidad-40-3-resultado).

    The bundled AEAT corpus (``modelo-202-instrucciones.html`` /
    ``modelo-202-instrucciones-2023-2024.html``) states the clave 32 formula
    verbatim: "Clave [32] = ( [clave [18] (o clave [26]) - clave [27] -
    clave [28] ] x clave [29]/100 ) - clave [30] - clave [31]" -- clave 18
    (B1 caso general, unico tipo) and clave 26 (B2 casos especificos, varios
    tipos) are alternative, mutually exclusive computations of the same
    "resultado previo" figure. Every M202 revision previously read only
    clave 18, silently dropping a B2-only filer's entire computation from
    the final ``cantidad a ingresar`` (clave 34). See the
    `modelo-verify-nonzero-guards` m202-deferred-items audit (2026-07-01) for
    the investigation that confirmed the defect against the bundled corpus
    and resolved it by combining both lanes additively with a blocking
    lane-exclusivity predicate: the registry models no discrete B1-vs-B2
    discriminator binding, and both lanes' manual inputs default to zero when
    unused, so addition reproduces "18 (o 26)" without inventing new registry
    data only while verification refuses the both-positive overstatement case.
    """
    modelo, _catalogues = _load_modelo_202()
    for revision_id in _M202_REVISION_IDS:
        revision = modelo.revisions[revision_id]

        modalidad_40_3_resultado_formula = next(f for f in revision.formulas if f.target_casilla_id == "32")
        expression = modalidad_40_3_resultado_formula.expression
        referenced_casillas = _casilla_refs_in_expression(expression)
        assert "18" in referenced_casillas
        assert "26" in referenced_casillas

        # Lock the exact combination shape: an "add" node whose two args are
        # precisely the clave 18 and clave 26 leaves (not, say, a "subtract" or
        # "max" that would zero or misstate one lane).
        combination_nodes = [node for node in _iter_expression_nodes(expression) if node.op == "add"]
        assert any({arg.casilla_id for arg in node.args} == {"18", "26"} for node in combination_nodes), (
            "expected an add(clave 18, clave 26) node combining the B1 and B2 resultado previo lanes"
        )

        predicate_ids = {p.predicate_id for p in revision.verification_predicates}
        assert _M202_B2_RESULTADO_PREVIO_ADVISORY_PREDICATE_ID not in predicate_ids
        predicate = next(
            p
            for p in revision.verification_predicates
            if p.predicate_id == _M202_B1_B2_RESULTADO_PREVIO_XOR_PREDICATE_ID
        )
        assert predicate.expression == 'at_most_one_positive(["18", "26"])'
        assert predicate.finding_kind == "BLOCKING_RULE"
        assert "ley-27-2014:art-40-3" in tuple(str(r) for r in predicate.legal_refs)


def _iter_expression_nodes(expression: FormulaExpression) -> list[FormulaExpression]:
    """Recursively collect every node (operator or leaf) in a formula expression tree."""
    nodes = [expression]
    for arg in expression.args:
        nodes.extend(_iter_expression_nodes(arg))
    return nodes


def test_committed_modelo_202_modalidad_40_3_resultado_reflects_b2_only_filer() -> None:
    """A B2-only filer's resultado previo (clave 26) now reaches clave 32, not zero.

    This is a graph-wiring / runtime-execution proof, not a re-derivation of
    LIS tax law (`aeat-quality-gates`): claves 27-31 are held
    at their neutral values (0 bonificaciones/retenciones/pagos previos, 100%
    volumen territorio comun) so the only quantity under test is whether the
    clave 26 leaf is live in the clave 32 dependency graph. Before the fix,
    a B2-only filer (clave 18 == 0) always produced clave 32 == 0 regardless
    of clave 26; after the fix clave 32 == clave 26 under these neutral
    adjustment values.
    """
    modelo, _catalogues = _load_modelo_202()
    for revision_id in _M202_REVISION_IDS:
        revision = modelo.revisions[revision_id]
        modalidad_40_3_resultado_formula = next(f for f in revision.formulas if f.target_casilla_id == "32")

        operand_refs: list[str] = []
        operand_casilla_refs: list[CasillaId] = []
        operand_values: list[Decimal] = []
        result = evaluate_expression(
            modalidad_40_3_resultado_formula.expression,
            values={
                "18": Decimal("0"),
                "26": Decimal("1000"),
                "27": Decimal("0"),
                "28": Decimal("0"),
                "29": Decimal("100"),
                "30": Decimal("0"),
                "31": Decimal("0"),
            },
            binding_values={},
            parameters={},
            date_context={},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=set(),
            operand_refs=operand_refs,
            operand_casilla_refs=operand_casilla_refs,
            operand_values=operand_values,
        )
        assert result == Decimal("1000"), revision_id


_M202_MINIMO_A_INGRESAR_CN_10M_ADVISORY_PREDICATE_ID = "modelo-202-04-implica-minimo-a-ingresar-cn-10m"


def test_committed_modelo_202_minimo_a_ingresar_cn_10m_remains_unguarded() -> None:
    """Clave 33 (minimo a ingresar, CN >= 10 millones euros) is a grounded, documented non-guard.

    The LIS pago-fraccionado minimo floor for INCN >= EUR 10.000.000 groups is
    now GROUNDED on clave 33 via ``ley-27-2014:da-14`` (disposicion adicional
    decimocuarta, redaccion vigente del art. 71 de la Ley 6/2018), closing the
    ``aeat-calculation-grounding`` gap previously
    identified; the value now cites the provision that establishes it, not only
    the framework art-40/40-3/29/30/105 mechanics.

    The verify GUARD nonetheless stays DEFERRED (documented non-guard) because
    no false-positive-free antecedent is expressible today: the
    semantically-correct guard is
    (INCN >= 10.000.000) AND (resultado positivo ajustado > 0) => clave 33 > 0,
    and all three signals are structurally unreachable -- the INCN is a
    ``profile`` binding fact the predicate evaluator never receives (it sees
    only casilla/text values), ``casilla_equals_implies_nonzero`` gates a
    text-equality not a numeric >= threshold, and clave 04 is not the DA-14a
    adjusted resultado-positivo base. The naive ``implies_nonzero(["04", "33"])``
    would therefore fire on every sub-EUR-10M filer who correctly leaves clave
    33 blank -- the overwhelming majority -- a structurally guaranteed
    false-positive rate (the M714-class antipattern). Clave 33 is fully manual
    with no formula or binding linkage in every revision.
    """
    modelo, _catalogues = _load_modelo_202()
    for revision_id in _M202_REVISION_IDS:
        revision = modelo.revisions[revision_id]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

        casilla_33 = casillas_by_id["33"]
        assert casilla_33.formula is None
        assert casilla_33.binding is None
        # The DA-14a binding provision is grounded on the value (Item A / residuals
        # Finding 1b) even though the value stays unguarded.
        assert "ley-27-2014:da-14" in {str(ref) for ref in casilla_33.legal_refs}

        predicate_ids = {p.predicate_id for p in revision.verification_predicates}
        assert _M202_MINIMO_A_INGRESAR_CN_10M_ADVISORY_PREDICATE_ID not in predicate_ids
