"""Tests for the committed Modelo 714 (patrimonio) registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources.bundled_data import bundled_path
from .....tests.registry_snapshot import build_snapshot
from .._validate import RegistryValidator
from ..formula_runtime import calculate_registry_snapshot
from ..legal import verify_legal_catalogue
from ..relations import relation_source_requirements
from ..schema import ModeloDefinition, RegistryCatalogues
from ..schema_input_kind import InputKind
from ..schema_surfaces import CasillaDefinition
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
_PATRIMONIO_IRPF_BASES_IMPONIBLES_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.irpf-bases-imponibles",
    surface="_PATRIMONIO_IRPF_BASES_IMPONIBLES_CASILLA",
)
_PATRIMONIO_DIVIDENDOS_NO_IRPF_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.dividendos-no-irpf",
    surface="_PATRIMONIO_DIVIDENDOS_NO_IRPF_CASILLA",
)
_PATRIMONIO_BASE_AHORRO_EXCLUIDA_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.base-ahorro-excluida",
    surface="_PATRIMONIO_BASE_AHORRO_EXCLUIDA_CASILLA",
)
_PATRIMONIO_LIMITE_CONJUNTO_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.limite-conjunto",
    surface="_PATRIMONIO_LIMITE_CONJUNTO_CASILLA",
)
_PATRIMONIO_IRPF_CUOTAS_INTEGRAS_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.irpf-cuotas-integras",
    surface="_PATRIMONIO_IRPF_CUOTAS_INTEGRAS_CASILLA",
)
_PATRIMONIO_IRPF_CUOTAS_EXCLUIDAS_BASE_AHORRO_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.irpf-cuotas-excluidas-base-ahorro",
    surface="_PATRIMONIO_IRPF_CUOTAS_EXCLUIDAS_BASE_AHORRO_CASILLA",
)
_PATRIMONIO_CUOTA_INTEGRA_SUSCEPTIBLE_LIMITACION_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.cuota-integra-susceptible-limitacion",
    surface="_PATRIMONIO_CUOTA_INTEGRA_SUSCEPTIBLE_LIMITACION_CASILLA",
)
_PATRIMONIO_SUMA_CUOTAS_LIMITE_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.suma-cuotas-limite",
    surface="_PATRIMONIO_SUMA_CUOTAS_LIMITE_CASILLA",
)
_PATRIMONIO_EXCESO_LIMITE_CONJUNTO_CASILLA: CasillaId = validated_casilla_id(
    "patrimonio.exceso-limite-conjunto",
    surface="_PATRIMONIO_EXCESO_LIMITE_CONJUNTO_CASILLA",
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
_M714_REL_100_BASE_IMPONIBLE_GENERAL = "m714-rel-100-base-imponible-general"
_M714_REL_100_BASE_IMPONIBLE_AHORRO = "m714-rel-100-base-imponible-ahorro"
_M714_REL_100_CUOTA_INTEGRA_ESTATAL = "m714-rel-100-cuota-integra-estatal"
_M714_REL_100_CUOTA_INTEGRA_AUTONOMICA = "m714-rel-100-cuota-integra-autonomica"

_PATRIMONIO_ART31_MANUAL_INPUTS = (
    _PATRIMONIO_DIVIDENDOS_NO_IRPF_CASILLA,
    _PATRIMONIO_BASE_AHORRO_EXCLUIDA_CASILLA,
    _PATRIMONIO_IRPF_CUOTAS_EXCLUIDAS_BASE_AHORRO_CASILLA,
    _PATRIMONIO_CUOTA_INTEGRA_SUSCEPTIBLE_LIMITACION_CASILLA,
)
_PATRIMONIO_RESIDUAL_MANUAL_RESULT_INPUTS = (
    _PATRIMONIO_CUOTA_MINORADA_CASILLA,
    _PATRIMONIO_CUOTA_A_INGRESAR_CASILLA,
)
_PATRIMONIO_COMPUTED_TARGETS = (
    _PATRIMONIO_CUOTA_INTEGRA_CASILLA,
    _PATRIMONIO_IRPF_BASES_IMPONIBLES_CASILLA,
    _PATRIMONIO_LIMITE_CONJUNTO_CASILLA,
    _PATRIMONIO_IRPF_CUOTAS_INTEGRAS_CASILLA,
    _PATRIMONIO_SUMA_CUOTAS_LIMITE_CASILLA,
    _PATRIMONIO_EXCESO_LIMITE_CONJUNTO_CASILLA,
    _PATRIMONIO_REDUCCION_LIMITE_80_CASILLA,
    _PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA,
)
_PATRIMONIO_LEGAL_REFS = (
    "ley-19-1991:art-4-9",
    "ley-19-1991:art-28",
    "ley-19-1991:art-30",
    "ley-19-1991:art-31",
)
# orden-hac-1023-2021:modelo-714 (formerly cited here) resolved, on live BOE,
# to an unrelated municipal job-posting resolution -- fabricated, not a real
# citation. The real governing instrument for ejercicio 2021 is Orden
# HFP/207/2022 art. 4 (BOE-A-2022-4296), a numbered-article citation rather
# than the old whole-orden "modelo 714" anchor shape.
_PATRIMONIO_FORM_ORDER_REF = "orden-hfp-207-2022:art-4"


def _load_modelo_714() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("714")


def _zero_art31_inputs(base_liquidable: Decimal) -> dict[CasillaId, Decimal]:
    return {
        _PATRIMONIO_BASE_LIQUIDABLE_CASILLA: base_liquidable,
        _PATRIMONIO_DIVIDENDOS_NO_IRPF_CASILLA: Decimal("0"),
        _PATRIMONIO_BASE_AHORRO_EXCLUIDA_CASILLA: Decimal("0"),
        _PATRIMONIO_IRPF_CUOTAS_EXCLUIDAS_BASE_AHORRO_CASILLA: Decimal("0"),
        _PATRIMONIO_CUOTA_INTEGRA_SUSCEPTIBLE_LIMITACION_CASILLA: Decimal("0"),
    }


def _zero_m100_relation_values() -> dict[str, Decimal]:
    return {
        _M714_REL_100_BASE_IMPONIBLE_GENERAL: Decimal("0"),
        _M714_REL_100_BASE_IMPONIBLE_AHORRO: Decimal("0"),
        _M714_REL_100_CUOTA_INTEGRA_ESTATAL: Decimal("0"),
        _M714_REL_100_CUOTA_INTEGRA_AUTONOMICA: Decimal("0"),
    }


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
        inputs=_zero_art31_inputs(Decimal(base_liquidable)),
        date_context={"filing_period": date(2024, 12, 31)},
        relation_values=_zero_m100_relation_values(),
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
    revision = modelo.revisions["2021"]
    legal = {_PATRIMONIO_FORM_ORDER_REF: catalogues.legal[_PATRIMONIO_FORM_ORDER_REF]}

    verify_legal_catalogue(legal, source_root=bundled_path())

    assert _PATRIMONIO_FORM_ORDER_REF in modelo.legal_refs
    assert _PATRIMONIO_FORM_ORDER_REF in revision.legal_refs
    assert revision.orden_aplicabilidad == (_PATRIMONIO_FORM_ORDER_REF,)
    reference = legal[_PATRIMONIO_FORM_ORDER_REF]
    assert reference.document_id == "BOE-A-2022-4296"
    assert reference.kind == "orden"
    assert reference.article == "4"
    assert "Aprobación del modelo de declaración del Impuesto sobre el Patrimonio" in reference.required_text


def test_modelo_714_boe_form_source_is_layout_only() -> None:
    modelo, catalogues = _load_modelo_714()
    revision = modelo.revisions["2021"]

    assert "boe-modelo-714-form" not in catalogues.sources
    assert catalogues.sources["aeat-modelo-714-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-714-layout"].evidence_tier == "layout_authority"
    assert "boe-modelo-714-layout" in modelo.source_refs
    assert "boe-modelo-714-layout" in revision.source_refs


def test_modelo_714_revision_2021_declares_constructs() -> None:
    modelo, _ = _load_modelo_714()
    revision = modelo.revisions["2021"]
    assert revision.constructs, "714 2021 revision must declare constructs"
    construct_ids = {c.id for c in revision.constructs}
    assert "m714-patrimonio-calculation" in construct_ids


def test_modelo_714_revision_2021_cuota_integra_computed_via_grounded_escala() -> None:
    """Cuota íntegra (29) is computed from the Ley 19/1991 art. 30 escala.

    Base imponible and base liquidable stay manual. The downstream art.31 joint
    limit is computed only where it is backed by same-year M100 relation values
    plus explicit M714 exclusion inputs.
    """
    modelo, _ = _load_modelo_714()
    revision = modelo.revisions["2021"]
    # The sole cuota-íntegra formula is the real, art.30-grounded escala — not a placeholder.
    escala_formula = next(f for f in revision.formulas if f.target_casilla_id == _PATRIMONIO_CUOTA_INTEGRA_CASILLA)
    assert escala_formula.id == "patrimonio-cuota-integra-escala-estatal"
    assert "ley-19-1991:art-30" in escala_formula.legal_refs
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    # The escala output casilla is computed via that formula.
    assert casillas[_PATRIMONIO_CUOTA_INTEGRA_CASILLA].input_kind is InputKind.COMPUTED
    assert casillas[_PATRIMONIO_CUOTA_INTEGRA_CASILLA].formula == "patrimonio-cuota-integra-escala-estatal"
    # The base inputs and later deduction/bonification result remain manual.
    for casilla_id in (
        _PATRIMONIO_BASE_IMPONIBLE_CASILLA,
        _PATRIMONIO_BASE_LIQUIDABLE_CASILLA,
        _PATRIMONIO_CUOTA_MINORADA_CASILLA,
        _PATRIMONIO_CUOTA_A_INGRESAR_CASILLA,
    ):
        assert casillas[casilla_id].input_kind is InputKind.MANUAL


def test_modelo_714_art31_m100_same_year_relation_chain_is_declared() -> None:
    modelo, _ = _load_modelo_714()
    revision = modelo.revisions["2021"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}

    # Each ejercicio is its own revision, so the selector names exactly one year
    # rather than the 2021-2025 span the combined revision carried before the
    # split. The relations below still reach 2021-2025 on the M100 side, because
    # that window describes which SOURCE revisions they may read, not which
    # filings this revision governs.
    assert revision.period_selector.years == (2021,)
    assert revision.period_selector.periods == ("0A",)
    assert {formula.target_casilla_id for formula in revision.formulas} == set(_PATRIMONIO_COMPUTED_TARGETS)

    relations = {relation.id: relation for relation in revision.relations}
    assert set(relations) == {
        _M714_REL_100_BASE_IMPONIBLE_GENERAL,
        _M714_REL_100_BASE_IMPONIBLE_AHORRO,
        _M714_REL_100_CUOTA_INTEGRA_ESTATAL,
        _M714_REL_100_CUOTA_INTEGRA_AUTONOMICA,
    }
    expected_source_casillas = {
        _M714_REL_100_BASE_IMPONIBLE_GENERAL: "0435",
        _M714_REL_100_BASE_IMPONIBLE_AHORRO: "0460",
        _M714_REL_100_CUOTA_INTEGRA_ESTATAL: "0545",
        _M714_REL_100_CUOTA_INTEGRA_AUTONOMICA: "0546",
    }
    for relation_id, source_casilla_id in expected_source_casillas.items():
        relation = relations[relation_id]
        assert relation.kind == "cross_model_output"
        assert relation.dependency_role == "direct_calculation"
        assert relation.source_modelo == "100"
        assert relation.source_casilla_id == source_casilla_id
        assert relation.source_revision_selector.year_from == 2021
        assert relation.source_revision_selector.year_to == 2025
        assert relation.source_revision_selector.filing_year_delta is None
        assert relation.period_alignment.source_period == "0A"
        assert relation.period_alignment.target_period == "0A"
        assert relation.period_alignment.filing_year_delta == 0
        assert relation.source_periods == ("0A",)
        assert relation.target_periods == ("0A",)

    requirements = relation_source_requirements(revision, filing_year=2024, period="0A")
    assert {requirement.relation_ids[0]: requirement.filing_year for requirement in requirements} == {
        _M714_REL_100_BASE_IMPONIBLE_GENERAL: 2024,
        _M714_REL_100_BASE_IMPONIBLE_AHORRO: 2024,
        _M714_REL_100_CUOTA_INTEGRA_ESTATAL: 2024,
        _M714_REL_100_CUOTA_INTEGRA_AUTONOMICA: 2024,
    }

    for casilla_id in _PATRIMONIO_COMPUTED_TARGETS:
        assert casillas[casilla_id].input_kind is InputKind.COMPUTED
        assert casillas[casilla_id].formula is not None
    for casilla_id in _PATRIMONIO_ART31_MANUAL_INPUTS + _PATRIMONIO_RESIDUAL_MANUAL_RESULT_INPUTS:
        casilla = casillas[casilla_id]
        assert casilla.input_kind is InputKind.MANUAL
        assert casilla.formula is None
        assert casilla.binding is None


def test_modelo_714_art31_joint_limit_calculates_from_same_year_m100_relations() -> None:
    """The Ley 19/1991 art.31 chain computes casilla 40 from M100 and M714 inputs."""
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="0A")

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _PATRIMONIO_BASE_LIQUIDABLE_CASILLA: Decimal("1000000.00"),
            _PATRIMONIO_DIVIDENDOS_NO_IRPF_CASILLA: Decimal("0.00"),
            _PATRIMONIO_BASE_AHORRO_EXCLUIDA_CASILLA: Decimal("15000.00"),
            _PATRIMONIO_IRPF_CUOTAS_EXCLUIDAS_BASE_AHORRO_CASILLA: Decimal("2000.00"),
            _PATRIMONIO_CUOTA_INTEGRA_SUSCEPTIBLE_LIMITACION_CASILLA: Decimal("5490.36"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
        relation_values={
            _M714_REL_100_BASE_IMPONIBLE_GENERAL: Decimal("10000.00"),
            _M714_REL_100_BASE_IMPONIBLE_AHORRO: Decimal("20000.00"),
            _M714_REL_100_CUOTA_INTEGRA_ESTATAL: Decimal("3000.00"),
            _M714_REL_100_CUOTA_INTEGRA_AUTONOMICA: Decimal("4000.00"),
        },
    )

    assert result.values[_PATRIMONIO_CUOTA_INTEGRA_CASILLA] == Decimal("5490.36")
    assert result.values[_PATRIMONIO_IRPF_BASES_IMPONIBLES_CASILLA] == Decimal("30000.00")
    assert result.values[_PATRIMONIO_LIMITE_CONJUNTO_CASILLA] == Decimal("9000.00")
    assert result.values[_PATRIMONIO_IRPF_CUOTAS_INTEGRAS_CASILLA] == Decimal("7000.00")
    assert result.values[_PATRIMONIO_SUMA_CUOTAS_LIMITE_CASILLA] == Decimal("10490.36")
    assert result.values[_PATRIMONIO_EXCESO_LIMITE_CONJUNTO_CASILLA] == Decimal("1490.36")
    assert result.values[_PATRIMONIO_REDUCCION_LIMITE_80_CASILLA] == Decimal("4392.29")
    assert result.values[_PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA] == Decimal("4000.00")

    entries_by_target = {entry.target_casilla_id: entry for entry in result.entries}
    assert (
        _M714_REL_100_BASE_IMPONIBLE_GENERAL
        in entries_by_target[_PATRIMONIO_IRPF_BASES_IMPONIBLES_CASILLA].operand_refs
    )
    assert (
        _M714_REL_100_BASE_IMPONIBLE_AHORRO in entries_by_target[_PATRIMONIO_IRPF_BASES_IMPONIBLES_CASILLA].operand_refs
    )
    assert (
        _M714_REL_100_CUOTA_INTEGRA_ESTATAL in entries_by_target[_PATRIMONIO_IRPF_CUOTAS_INTEGRAS_CASILLA].operand_refs
    )
    assert (
        _M714_REL_100_CUOTA_INTEGRA_AUTONOMICA
        in entries_by_target[_PATRIMONIO_IRPF_CUOTAS_INTEGRAS_CASILLA].operand_refs
    )


def test_modelo_714_snapshot_builds_for_2021_event_period() -> None:
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2021,
        period="0A",
    )
    assert snapshot.revision.id == "2021"
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
        inputs=_zero_art31_inputs(Decimal(base_liquidable)),
        date_context={"filing_period": date(2024, 12, 31)},
        relation_values=_zero_m100_relation_values(),
    )
    assert result.values[_PATRIMONIO_CUOTA_INTEGRA_CASILLA] == Decimal(expected_cuota)
    assert result.values[_PATRIMONIO_REDUCCION_LIMITE_80_CASILLA] == Decimal(expected_suelo_80)


_M714_CUOTA_INTEGRA_ADVISORY_PREDICATE_ID = "modelo-714-cuota-integra-implica-total-cuota-integra"


def test_modelo_714_no_longer_carries_cuota_integra_manual_handoff_advisory() -> None:
    """Casilla 40 is formula-computed, so the old 29 -> 40 manual guard is gone."""
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    predicates = {p.predicate_id: p for p in snapshot.revision.verification_predicates}
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}

    assert _M714_CUOTA_INTEGRA_ADVISORY_PREDICATE_ID not in predicates
    assert casillas[_PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA].input_kind is InputKind.COMPUTED
    assert casillas[_PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA].formula == "patrimonio-total-cuota-integra-art31"


def _load_714_snapshot_and_casillas() -> tuple[frozenset[str], dict[CasillaId, CasillaDefinition]]:
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )
    predicate_ids = frozenset(p.predicate_id for p in snapshot.revision.verification_predicates)
    casillas_by_id: dict[CasillaId, CasillaDefinition] = {casilla.id: casilla for casilla in snapshot.revision.casillas}
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
    categories` antipattern). Casilla 40 is now computed, but casilla 45 and
    casilla 55 remain explicit manual result inputs until the deduction and
    bonification chain is grounded.
    """
    predicate_ids, casillas_by_id = _load_714_snapshot_and_casillas()

    assert "modelo-714-total-cuota-integra-implica-cuota-a-ingresar" not in predicate_ids

    total_cuota = casillas_by_id[_PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA]
    assert total_cuota.input_kind is InputKind.COMPUTED
    assert total_cuota.formula == "patrimonio-total-cuota-integra-art31"

    for casilla_id in _PATRIMONIO_RESIDUAL_MANUAL_RESULT_INPUTS:
        casilla = casillas_by_id[casilla_id]
        assert casilla.input_kind is InputKind.MANUAL
        assert casilla.formula is None
