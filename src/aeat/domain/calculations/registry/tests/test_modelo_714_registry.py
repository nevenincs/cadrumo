"""Tests for the committed Modelo 714 (patrimonio) registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .._formula_runtime import calculate_registry_snapshot
from .._ids import CasillaId, validated_casilla_id
from .._legal import verify_legal_catalogue
from .._schema import ModeloDefinition, RegistryCatalogues
from .._schema_input_kind import InputKind
from .._snapshot import build_snapshot
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PATRIMONIO_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.base-imponible",
    surface="_PATRIMONIO_BASE_IMPONIBLE_CASILLA",
)
_PATRIMONIO_BASE_LIQUIDABLE_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.base-liquidable",
    surface="_PATRIMONIO_BASE_LIQUIDABLE_CASILLA",
)
_PATRIMONIO_CUOTA_INTEGRA_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.cuota-integra",
    surface="_PATRIMONIO_CUOTA_INTEGRA_CASILLA",
)
_PATRIMONIO_REDUCCION_LIMITE_80_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.reduccion-limite-80",
    surface="_PATRIMONIO_REDUCCION_LIMITE_80_CASILLA",
)
_PATRIMONIO_LIMITE_CONJUNTO_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.limite-conjunto",
    surface="_PATRIMONIO_LIMITE_CONJUNTO_CASILLA",
)
_PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.total-cuota-integra",
    surface="_PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA",
)
_PATRIMONIO_CUOTA_MINORADA_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.cuota-minorada",
    surface="_PATRIMONIO_CUOTA_MINORADA_CASILLA",
)
_PATRIMONIO_CUOTA_A_INGRESAR_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.cuota-a-ingresar",
    surface="_PATRIMONIO_CUOTA_A_INGRESAR_CASILLA",
)
_PATRIMONIO_ART31_UNGROUNDED_TAIL = (
    _PATRIMONIO_LIMITE_CONJUNTO_CASILLA,
    _PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA,
    _PATRIMONIO_CUOTA_MINORADA_CASILLA,
    _PATRIMONIO_CUOTA_A_INGRESAR_CASILLA,
)
_PATRIMONIO_COMPUTED_SAFE_TARGETS = (
    _PATRIMONIO_CUOTA_INTEGRA_CASILLA,
    _PATRIMONIO_REDUCCION_LIMITE_80_CASILLA,
)
_PATRIMONIO_LEGAL_REFS = (
    "ley-19-1991:art-4-9",
    "ley-19-1991:art-28",
    "ley-19-1991:art-30",
    "ley-19-1991:art-31",
)
_PATRIMONIO_FORM_ORDER_REF = "orden-hac-1023-2021:modelo-714"


def _load_modelo_714() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("714")


@pytest.mark.parametrize(
    ("base_liquidable", "expected_cuota"),
    [
        # Oracle from the BOE Ley 19/1991 art. 30 published escala table
        # (bundled corpus ley-19-1991-art-30.html). Boundary values are the
        # table's published "Cuota" column; mid-bracket values are computed as
        # published_fixed + (base - lower_bound) * marginal_rate, derived from
        # the table — NOT from the formula under test (non-tautological).
        ("0", "0.00"),
        ("167129.45", "334.26"),  # bracket-2 lower bound: published cuota
        ("668499.75", "2506.86"),  # bracket-4 lower bound: published cuota
        ("1336999.51", "8523.36"),  # bracket-5 lower bound: published cuota
        ("10695996.06", "183670.29"),  # top bracket lower bound: published cuota
        ("700000", "2790.36"),  # mid bracket-4: 2506.86 + (700000-668499.75)*0.009
        ("1000000", "5490.36"),  # mid bracket-4: 2506.86 + (1000000-668499.75)*0.009
        ("20000000", "509310.43"),  # top bracket: 183670.29 + (20000000-10695996.06)*0.035
    ],
)
def test_modelo_714_cuota_integra_escala_matches_boe_table(base_liquidable: str, expected_cuota: str) -> None:
    """The art. 30 escala formula computes casilla 29 exactly per the BOE table."""
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={_PATRIMONIO_BASE_LIQUIDABLE_CASILLA: Decimal(base_liquidable)},
        date_context={"filing_period": date(2024, 12, 31)},
    )
    assert result.values[_PATRIMONIO_CUOTA_INTEGRA_CASILLA] == Decimal(expected_cuota)


def test_modelo_714_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_714()
    assert modelo.id == "714"
    assert modelo.revisions, "714 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_714_legal_refs_are_boe_corpus_backed() -> None:
    """All Ley 19/1991 references used by 714 verify against bundled BOE corpus."""
    modelo, catalogues = _load_modelo_714()
    legal = {legal_ref: catalogues.legal[legal_ref] for legal_ref in _PATRIMONIO_LEGAL_REFS}

    verify_legal_catalogue(legal, source_root=bundled_path())

    assert set(_PATRIMONIO_LEGAL_REFS) <= set(modelo.legal_refs)
    assert {entry.document_id for entry in legal.values()} == {"BOE-A-1991-14392"}
    assert legal["ley-19-1991:art-4-9"].article == "4.Nueve"
    assert "vivienda habitual" in legal["ley-19-1991:art-4-9"].required_text
    assert "300.000 euros" in legal["ley-19-1991:art-4-9"].required_text
    assert legal["ley-19-1991:art-30"].article == "30"
    assert "0,2" in legal["ley-19-1991:art-30"].required_text
    assert "3,5" in legal["ley-19-1991:art-30"].required_text
    assert legal["ley-19-1991:art-31"].article == "31"
    art31_required_text = legal["ley-19-1991:art-31"].required_text
    assert "60 por 100" in art31_required_text
    assert "bases imponibles" in art31_required_text
    assert "más de un año" in art31_required_text
    assert "no sean susceptibles de producir los rendimientos" in art31_required_text
    assert "80 por 100" in art31_required_text


def test_modelo_714_form_order_is_boe_corpus_backed() -> None:
    modelo, catalogues = _load_modelo_714()
    revision = modelo.revisions["2021-y-siguientes"]
    legal = {_PATRIMONIO_FORM_ORDER_REF: catalogues.legal[_PATRIMONIO_FORM_ORDER_REF]}

    verify_legal_catalogue(legal, source_root=bundled_path())

    assert _PATRIMONIO_FORM_ORDER_REF in modelo.legal_refs
    assert _PATRIMONIO_FORM_ORDER_REF in revision.legal_refs
    assert revision.orden_aplicabilidad == (_PATRIMONIO_FORM_ORDER_REF,)
    reference = legal[_PATRIMONIO_FORM_ORDER_REF]
    assert reference.document_id == "BOE-A-2021-7593"
    assert reference.kind == "orden"
    assert reference.article == "modelo 714"
    assert "ejercicio 2021 y siguientes" in reference.required_text


def test_modelo_714_boe_form_source_is_layout_only() -> None:
    modelo, catalogues = _load_modelo_714()
    revision = modelo.revisions["2021-y-siguientes"]

    assert "boe-modelo-714-form" not in catalogues.sources
    assert catalogues.sources["aeat-modelo-714-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-714-layout"].evidence_tier == "layout_authority"
    assert "boe-modelo-714-layout" in modelo.source_refs
    assert "boe-modelo-714-layout" in revision.source_refs


def test_modelo_714_revision_2021_declares_constructs() -> None:
    modelo, _ = _load_modelo_714()
    revision = modelo.revisions["2021-y-siguientes"]
    assert revision.constructs, "714 2021-y-siguientes revision must declare constructs"
    construct_ids = {c.id for c in revision.constructs}
    assert "m714-patrimonio-calculation" in construct_ids


def test_modelo_714_revision_2021_cuota_integra_computed_via_grounded_escala() -> None:
    """Cuota íntegra (29) is computed from the Ley 19/1991 art. 30 escala.

    The downstream chain (base imponible, base liquidable, and the post-cuota
    casillas) stays a manual foundation pending its own official formula
    evidence; only the escala step — grounded verbatim in the bundled
    authoritative corpus — is computed. No ungrounded placeholder formula is declared.
    """
    modelo, _ = _load_modelo_714()
    revision = modelo.revisions["2021-y-siguientes"]
    # The sole cuota-íntegra formula is the real, art.30-grounded escala — not a placeholder.
    escala_formula = next(f for f in revision.formulas if f.target_casilla_id == _PATRIMONIO_CUOTA_INTEGRA_CASILLA)
    assert escala_formula.id == "patrimonio-cuota-integra-escala-estatal"
    assert "ley-19-1991:art-30" in escala_formula.legal_refs
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    # The escala output casilla is computed via that formula.
    assert casillas[_PATRIMONIO_CUOTA_INTEGRA_CASILLA].input_kind is InputKind.COMPUTED
    assert casillas[_PATRIMONIO_CUOTA_INTEGRA_CASILLA].formula == "patrimonio-cuota-integra-escala-estatal"
    # The manual foundation (inputs + not-yet-modelled downstream) is unchanged.
    for casilla_id in (
        _PATRIMONIO_BASE_IMPONIBLE_CASILLA,
        _PATRIMONIO_BASE_LIQUIDABLE_CASILLA,
        _PATRIMONIO_CUOTA_A_INGRESAR_CASILLA,
    ):
        assert casillas[casilla_id].input_kind is InputKind.MANUAL


def test_modelo_714_art31_tail_has_no_partial_m100_formula_or_relation() -> None:
    modelo, _ = _load_modelo_714()
    revision = modelo.revisions["2021-y-siguientes"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}

    assert {formula.target_casilla_id for formula in revision.formulas} == set(_PATRIMONIO_COMPUTED_SAFE_TARGETS)
    assert not revision.relations
    for casilla_id in _PATRIMONIO_ART31_UNGROUNDED_TAIL:
        casilla = casillas[casilla_id]
        assert casilla.input_kind is InputKind.MANUAL
        assert casilla.formula is None
        assert casilla.binding is None


def test_modelo_714_snapshot_builds_for_2021_event_period() -> None:
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2021,
        period="0A",
    )
    assert snapshot.revision.id == "2021-y-siguientes"
    assert _PATRIMONIO_FORM_ORDER_REF in snapshot.legal


@pytest.mark.parametrize(
    ("base_liquidable", "expected_cuota", "expected_suelo_80"),
    [
        # Casilla 39 (art. 31 suelo) = 80% of the cuota integra (casilla 29).
        ("0", "0.00", "0.00"),
        ("1336999.51", "8523.36", "6818.69"),  # 8523.36 * 0.80
        ("1000000", "5490.36", "4392.29"),  # 5490.36 * 0.80
        ("20000000", "509310.43", "407448.34"),  # 509310.43 * 0.80
    ],
)
def test_modelo_714_reduccion_limite_80_is_80pct_of_cuota_integra(
    base_liquidable: str, expected_cuota: str, expected_suelo_80: str
) -> None:
    """Casilla 39 (Ley 19/1991 art. 31 suelo) computes as 80% of the cuota integra."""
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={_PATRIMONIO_BASE_LIQUIDABLE_CASILLA: Decimal(base_liquidable)},
        date_context={"filing_period": date(2024, 12, 31)},
    )
    assert result.values[_PATRIMONIO_CUOTA_INTEGRA_CASILLA] == Decimal(expected_cuota)
    assert result.values[_PATRIMONIO_REDUCCION_LIMITE_80_CASILLA] == Decimal(expected_suelo_80)


_M714_CUOTA_INTEGRA_ADVISORY_PREDICATE_ID = "modelo-714-cuota-integra-implica-total-cuota-integra"
_M714_CUOTA_INTEGRA_ADVISORY_EXPRESSION = (
    'implies_nonzero(["patrimonio.cuota-integra", "patrimonio.total-cuota-integra"])'
)


def test_modelo_714_carries_cuota_integra_under_declaration_advisory() -> None:
    """The 2021-y-siguientes revision guards the casilla-29-to-casilla-40 manual handoff.

    Casilla 29 (``patrimonio.cuota-integra``) is formula-computed from the base
    liquidable via the art. 30 escala; casilla 40
    (``patrimonio.total-cuota-integra``) is a manual transcription of the
    official Diseno de Registro total with no formula linkage from 29. A
    positive cuota integra with a silently-zero total is the
    operator-skippable shape ``no-silent-under-declaration`` requires a guard
    for; this predicate must stay ADVISORY (non-blocking) -- the other two
    M714 candidate edges (base-imponible to base-liquidable,
    total-cuota-integra to cuota-a-ingresar) are deliberately NOT guarded here,
    per the sibling tests below.
    """
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    predicates = {p.predicate_id: p for p in snapshot.revision.verification_predicates}
    guard = predicates.get(_M714_CUOTA_INTEGRA_ADVISORY_PREDICATE_ID)
    assert guard is not None, (
        f"M714 2021-y-siguientes must guard the casilla-29-to-casilla-40 handoff via "
        f"{_M714_CUOTA_INTEGRA_ADVISORY_PREDICATE_ID!r} (no-silent-under-declaration)"
    )
    assert guard.expression == _M714_CUOTA_INTEGRA_ADVISORY_EXPRESSION
    assert guard.finding_kind == "ADVISORY", (
        "a legitimately zero total cuota integra transcription must not refuse the draft"
    )
    assert "ley-19-1991:art-30" in {str(ref) for ref in guard.legal_refs}


def _load_714_snapshot_and_casillas() -> tuple[frozenset[str], dict[CasillaId, object]]:
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )
    predicate_ids = frozenset(p.predicate_id for p in snapshot.revision.verification_predicates)
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    return predicate_ids, casillas_by_id


def test_modelo_714_base_liquidable_edge_remains_unguarded() -> None:
    """``base-imponible -> base-liquidable`` is a grounded, documented non-guard.

    ``patrimonio.base-liquidable`` = ``patrimonio.base-imponible`` - minimo
    exento (Ley 19/1991 art. 28: EUR 700.000 general, autonomically variable).
    A filer with base imponible > 0 but <= the minimo exento legitimately has
    base liquidable = 0 -- and is NOT a rare edge, because the M714 filing
    obligation (art. 37) is triggered independently by patrimonio bruto >
    EUR 2.000.000, so such a filer must file with a legitimately zero base
    liquidable. ``implies_nonzero(["patrimonio.base-imponible",
    "patrimonio.base-liquidable"])`` would false-fire on every such filer, and
    the CCAA-variable minimo exento means no fixed constant lets a guard even
    estimate the boundary; both casillas are manual with no formula linkage.
    The prerequisite to make it guardable is to compute base-liquidable =
    max(base-imponible - minimo_exento_CCAA, 0) from a CCAA minimo-exento table
    (the same computed shape M200 later adopted), after which the zero is a
    computed consequence needing no advisory. Keep deferred until then.
    """
    predicate_ids, casillas_by_id = _load_714_snapshot_and_casillas()

    assert "modelo-714-base-imponible-implica-base-liquidable" not in predicate_ids

    for casilla_id in (_PATRIMONIO_BASE_IMPONIBLE_CASILLA, _PATRIMONIO_BASE_LIQUIDABLE_CASILLA):
        casilla = casillas_by_id[casilla_id]
        assert casilla.input_kind is InputKind.MANUAL
        assert casilla.formula is None


def test_modelo_714_cuota_a_ingresar_edge_remains_unguarded() -> None:
    """``total-cuota-integra -> cuota-a-ingresar`` is a grounded, documented non-guard.

    Between ``patrimonio.total-cuota-integra`` (casilla 40) and
    ``patrimonio.cuota-a-ingresar`` (casilla 55) sit three legitimate zeroing
    mechanisms: the art. 31 limite conjunto reduction, the art. 32 foreign-tax
    deduction / art. 33 Ceuta-Melilla bonificacion, and -- decisively --
    autonomic bonificaciones up to 100% (Madrid and Andalucia have applied a
    ~100% IP bonificacion). A resident of those CCAAs with a positive total
    cuota integra legitimately has cuota a ingresar = 0; this is the NORM there,
    not an edge, so ``implies_nonzero(["patrimonio.total-cuota-integra",
    "patrimonio.cuota-a-ingresar"])`` would fire on the most common case and be
    actively miseducating (the `ledger-iva-advisory-only-on-cuota-bearing-
    categories` antipattern). This is the lowest-value of the three residual
    edges to ever guard: both casillas are manual, and even a full
    deduccion/bonificacion derivation would only make the zero a legitimate
    computed consequence. Keep deferred until then.
    """
    predicate_ids, casillas_by_id = _load_714_snapshot_and_casillas()

    assert "modelo-714-total-cuota-integra-implica-cuota-a-ingresar" not in predicate_ids

    for casilla_id in (_PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA, _PATRIMONIO_CUOTA_A_INGRESAR_CASILLA):
        casilla = casillas_by_id[casilla_id]
        assert casilla.input_kind is InputKind.MANUAL
        assert casilla.formula is None
