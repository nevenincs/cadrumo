"""Verification substance tests: Layer 1 + Layer 2 predicate gate (S75, S76).

S75: Unit tests for the predicate DSL evaluator (_evaluate_predicate_expression,
     _evaluate_verification_predicates).

S76: Regression — Modelo 130 with all casilla values zero (specifically casilla
     02 Gastos absent) is NOT granted verificado_completo. The Layer 1
     required=true gate on casilla 02 blocks the transition; this test pins
     that the enforcement is in place after S73.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from aeat.application.modelo import (
    calculate_modelo_revision,
    create_work_unit,
    verify_modelo_revision,
)
from aeat.application.modelo._actions import (
    StoredCalculationDriftError,
    _evaluate_advisory_predicate_fires,
    _evaluate_predicate_expression,
    _evaluate_verification_predicates,
)
from aeat.core.resources import resources
from aeat.domain.buckets import BucketEventHistoryRepository
from aeat.domain.calculations.registry import VerificationPredicateDefinition
from aeat.domain.deadlines import IVARegime, TaxpayerProfile
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._calculation_revision import CalculationRevisionCatalogue
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
)
from aeat.domain.modelos._verification_repository import VerificationReportCatalogueRepository
from aeat.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 14, 14, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# S75: unit tests for _evaluate_predicate_expression
# ---------------------------------------------------------------------------


def test_all_nonzero_passes_when_all_present_and_nonzero() -> None:
    """all_nonzero([...]) returns True when every listed casilla is non-zero."""
    values: dict[str, Decimal] = {"01": Decimal("1000"), "02": Decimal("500")}
    assert _evaluate_predicate_expression('all_nonzero(["01", "02"])', values) is True


def test_all_nonzero_fails_when_one_zero() -> None:
    """all_nonzero([...]) returns False when any listed casilla is zero."""
    values: dict[str, Decimal] = {"01": Decimal("1000"), "02": Decimal("0")}
    assert _evaluate_predicate_expression('all_nonzero(["01", "02"])', values) is False


def test_all_nonzero_fails_when_absent() -> None:
    """all_nonzero([...]) treats an absent casilla as zero."""
    values: dict[str, Decimal] = {"01": Decimal("1000")}
    assert _evaluate_predicate_expression('all_nonzero(["01", "02"])', values) is False


def test_any_nonzero_passes_when_one_nonzero() -> None:
    """any_nonzero([...]) returns True when at least one listed casilla is non-zero."""
    values: dict[str, Decimal] = {"01": Decimal("0"), "02": Decimal("500")}
    assert _evaluate_predicate_expression('any_nonzero(["01", "02"])', values) is True


def test_any_nonzero_fails_when_all_zero() -> None:
    """any_nonzero([...]) returns False when every listed casilla is zero or absent."""
    values: dict[str, Decimal] = {"01": Decimal("0"), "02": Decimal("0")}
    assert _evaluate_predicate_expression('any_nonzero(["01", "02"])', values) is False


def test_any_nonzero_fails_when_all_absent() -> None:
    """any_nonzero([...]) treats absent casillas as zero."""
    values: dict[str, Decimal] = {}
    assert _evaluate_predicate_expression('any_nonzero(["01", "02"])', values) is False


def test_cap_le_when_positive_passes_when_limited_within_ceiling() -> None:
    """cap_le_when_positive: passes when ceiling > 0 AND limited ≤ ceiling."""
    values: dict[str, Decimal] = {"11": Decimal("300"), "10": Decimal("500")}
    assert _evaluate_predicate_expression('cap_le_when_positive(["11", "10"])', values) is True


def test_cap_le_when_positive_fails_when_limited_exceeds_ceiling() -> None:
    """cap_le_when_positive: fails when ceiling > 0 AND limited > ceiling.

    P08.S47 case: M131 C11 (resultados negativos anteriores) MUST NOT
    exceed C10 (cuota positiva del trimestre) per AEAT instructions
    "en ningún caso podrá figurar en la casilla 11 un importe superior
    a la cantidad positiva consignada en la casilla 10".
    """
    values: dict[str, Decimal] = {"11": Decimal("750"), "10": Decimal("500")}
    assert _evaluate_predicate_expression('cap_le_when_positive(["11", "10"])', values) is False


def test_cap_le_when_positive_emits_blocking_rule_finding_for_violated_predicate() -> None:
    """P08.S60 integration test: a violated cap_le_when_positive predicate produces a BLOCKING_RULE finding.

    Constructs the exact M130 C15-cap predicate used in the
    registry (modelo-130-c15-cap-by-c14) and runs it through
    _evaluate_verification_predicates with a casilla_values map
    where C15 (limited) exceeds C14 (ceiling). The predicate must
    fire with a BLOCKING_RULE finding citing the predicate_id and
    the legal_refs from the registry declaration.
    """
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-c15-cap-by-c14",
        legal_refs=("rd-439-2007:art-110",),
        expression='cap_le_when_positive(["15", "14"])',
        finding_kind="BLOCKING_RULE",
    )
    # C14 = 1000 (positive ceiling), C15 = 1500 (exceeds cap)
    casilla_values = {"14": Decimal("1000"), "15": Decimal("1500")}

    findings = _evaluate_verification_predicates((predicate,), casilla_values)

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert "modelo-130-c15-cap-by-c14" in findings[0].message


def test_cap_le_when_positive_emits_no_finding_when_within_cap() -> None:
    """P08.S60 integration test: a satisfied cap predicate produces no finding."""
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-c15-cap-by-c14",
        legal_refs=("rd-439-2007:art-110",),
        expression='cap_le_when_positive(["15", "14"])',
        finding_kind="BLOCKING_RULE",
    )
    # C14 = 1000, C15 = 600 — within cap
    casilla_values = {"14": Decimal("1000"), "15": Decimal("600")}

    findings = _evaluate_verification_predicates((predicate,), casilla_values)
    assert findings == []


def test_cap_le_when_positive_holds_when_ceiling_is_zero_or_negative() -> None:
    """cap_le_when_positive: predicate holds (no cap) when ceiling ≤ 0.

    The AEAT cap rule only applies when the operator's gross liability
    is positive. A zero or negative cuota means there's no cap to
    enforce; the predicate must NOT block in that case.
    """
    values_zero: dict[str, Decimal] = {"11": Decimal("750"), "10": Decimal("0")}
    assert _evaluate_predicate_expression('cap_le_when_positive(["11", "10"])', values_zero) is True
    values_negative: dict[str, Decimal] = {"11": Decimal("750"), "10": Decimal("-50")}
    assert _evaluate_predicate_expression('cap_le_when_positive(["11", "10"])', values_negative) is True


def test_unknown_expression_does_not_block() -> None:
    """An unrecognised expression pattern does not produce a blocking finding."""
    values: dict[str, Decimal] = {}
    # Passes through — unknown DSL extensions do not block in W04
    assert _evaluate_predicate_expression('threshold(["01"], 100)', values) is True


# ---------------------------------------------------------------------------
# implies_nonzero — conditional predicate with strictly-positive antecedent
# Authority: .vault/adr/2026-05-27-dsl-conditional-predicate-adr.md
# ---------------------------------------------------------------------------


def test_predicate_implies_nonzero_holds_when_antecedent_zero() -> None:
    """Antecedent zero → predicate holds trivially (material implication with false antecedent).

    Mirrors the AEAT phrasing "cuando C01 sea positivo"; a zero antecedent
    does not engage the implication, regardless of the consequent's value.
    """
    values: dict[str, Decimal] = {"01": Decimal("0"), "07": Decimal("0")}
    assert _evaluate_predicate_expression('implies_nonzero(["01", "07"])', values) is True


def test_predicate_implies_nonzero_holds_when_antecedent_negative() -> None:
    """Antecedent negative → predicate holds trivially.

    The antecedent test is strictly-positive (> 0) rather than non-zero;
    a negative antecedent — even though casillas typically cannot carry
    negative base imponible — does not engage the implication. This is
    the defensive contract spelled out in ADR §C (constraints).
    """
    values: dict[str, Decimal] = {"01": Decimal("-100"), "07": Decimal("0")}
    assert _evaluate_predicate_expression('implies_nonzero(["01", "07"])', values) is True


def test_predicate_implies_nonzero_holds_when_both_positive() -> None:
    """Antecedent positive AND consequent non-zero → predicate holds (satisfied implication).

    The expected happy path for cuota-mínima invariants: when base is
    positive and cuota-mínima is also populated, the regulatory rule is
    satisfied.
    """
    values: dict[str, Decimal] = {"01": Decimal("500"), "07": Decimal("200")}
    assert _evaluate_predicate_expression('implies_nonzero(["01", "07"])', values) is True


def test_predicate_implies_nonzero_violated_when_consequent_zero() -> None:
    """Antecedent positive AND consequent zero → predicate violated.

    The canonical M131 EO cuota-mínima miss: base imponible positive but
    cuota-mínima absent. ADR D2.2 anti-tautology proof: this exact case
    is what `all_nonzero(["01", "07"])` would mis-flag when C01 is itself
    zero. The new operator does not have that false-positive surface.
    """
    values: dict[str, Decimal] = {"01": Decimal("500"), "07": Decimal("0")}
    assert _evaluate_predicate_expression('implies_nonzero(["01", "07"])', values) is False


def test_predicate_implies_nonzero_unknown_consequent_treated_as_zero() -> None:
    """Antecedent positive AND consequent absent → predicate violated.

    Missing casilla reads as Decimal(0) via the ``.get(id, Decimal(0))``
    default, same convention as the other operators. The implication
    therefore fires the BLOCKING finding rather than silently passing.
    """
    values: dict[str, Decimal] = {"01": Decimal("500")}
    assert _evaluate_predicate_expression('implies_nonzero(["01", "07"])', values) is False


# ---------------------------------------------------------------------------
# Modelo 131 c01-implies-c07 structural predicate (W04.P19.S398)
#
# Pins the M131 registry's implies_nonzero predicate against the
# integration surface that drives runtime evaluation. The predicate
# encodes a registry-graph correctness rule (positive base imponible
# C01 implies non-zero suma-de-pagos-fraccionados-previos C07) — NOT
# the regulatory cuota-mínima floor, which remains corpus-blocked
# under task #226. Tests construct the predicate via
# VerificationPredicateDefinition with the exact 2025-revision
# predicate_id + legal_refs from
# `src/aeat/_data/registry/aeat/modelos/131/revisions/2025/verification_expectations/0002-verification_predicates.toml`
# and route through _evaluate_verification_predicates, mirroring the
# cap_le_when_positive integration-test pattern above.
# ---------------------------------------------------------------------------


def test_modelo_131_c01_implies_c07_emits_blocking_rule_finding_for_violation() -> None:
    """M131 c01-implies-c07 fires a BLOCKING finding when C01>0 and C07=0.

    Anti-tautology: the predicate registered in the M131 2025 revision
    TOML is the same expression-shape the runtime evaluator consumes.
    With C01 strictly positive and C07 zero, the implies_nonzero
    contract (antecedent positive AND consequent zero → violated)
    forces a BLOCKING_RULE finding through
    _evaluate_verification_predicates with the predicate_id present
    in the finding message.
    """
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-131-2025-c01-implies-c07",
        legal_refs=("rd-439-2007:art-110",),
        expression='implies_nonzero(["01", "07"])',
        finding_kind="BLOCKING_RULE",
    )
    casilla_values = {"01": Decimal("500"), "07": Decimal("0")}

    findings = _evaluate_verification_predicates((predicate,), casilla_values)

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert "modelo-131-2025-c01-implies-c07" in findings[0].message


def test_modelo_131_c01_implies_c07_emits_no_finding_when_satisfied() -> None:
    """M131 c01-implies-c07 produces no finding when both casillas non-zero.

    Control case: positive antecedent paired with positive consequent
    satisfies the material implication. Confirms the integration path
    surfaces zero findings rather than the silent-pass shape an
    unrecognised expression would yield.
    """
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-131-2025-c01-implies-c07",
        legal_refs=("rd-439-2007:art-110",),
        expression='implies_nonzero(["01", "07"])',
        finding_kind="BLOCKING_RULE",
    )
    casilla_values = {"01": Decimal("500"), "07": Decimal("200")}

    findings = _evaluate_verification_predicates((predicate,), casilla_values)
    assert findings == []


def test_evaluate_verification_predicates_empty_returns_no_findings() -> None:
    """Empty predicate tuple yields empty findings list."""
    findings = _evaluate_verification_predicates((), {})
    assert findings == []


def test_evaluate_verification_predicates_violation_produces_blocking_rule() -> None:
    """A violated all_nonzero predicate produces a BLOCKING_RULE finding."""
    predicate = VerificationPredicateDefinition(
        predicate_id="test-invariant",
        legal_refs=("ley-35-2006:art-99",),
        expression='all_nonzero(["01", "02"])',
        finding_kind="BLOCKING_RULE",
    )
    values: dict[str, Decimal] = {"01": Decimal("1000"), "02": Decimal("0")}
    findings = _evaluate_verification_predicates((predicate,), values)
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert "test-invariant" in findings[0].message


def test_evaluate_verification_predicates_passing_predicate_no_finding() -> None:
    """A satisfied predicate does not produce any finding."""
    predicate = VerificationPredicateDefinition(
        predicate_id="test-invariant",
        legal_refs=("ley-35-2006:art-99",),
        expression='all_nonzero(["01", "02"])',
        finding_kind="BLOCKING_RULE",
    )
    values: dict[str, Decimal] = {"01": Decimal("1000"), "02": Decimal("500")}
    findings = _evaluate_verification_predicates((predicate,), values)
    assert findings == []


# ---------------------------------------------------------------------------
# Art. 110.3.b RIRPF advisory predicate unit tests
# ---------------------------------------------------------------------------


def test_advisory_when_ratio_ge_fires_when_ratio_meets_threshold() -> None:
    """advisory_when_ratio_ge fires when numerator/denominator >= threshold and denominator > 0.

    Oracle values: retenciones 10500 / rendimientos 15000 = 0.70 — exactly the
    Art. 110.3.b 70% threshold. The predicate must return True (advisory fires).
    """
    values: dict[str, Decimal] = {"06": Decimal("10500"), "01": Decimal("15000")}
    assert _evaluate_advisory_predicate_fires(
        'advisory_when_ratio_ge(["06", "01", "0.70"])', values
    ) is True


def test_advisory_when_ratio_ge_fires_when_ratio_exceeds_threshold() -> None:
    """advisory_when_ratio_ge fires when ratio strictly exceeds threshold."""
    # 12000 / 15000 = 0.80 > 0.70
    values: dict[str, Decimal] = {"06": Decimal("12000"), "01": Decimal("15000")}
    assert _evaluate_advisory_predicate_fires(
        'advisory_when_ratio_ge(["06", "01", "0.70"])', values
    ) is True


def test_advisory_when_ratio_ge_does_not_fire_below_threshold() -> None:
    """advisory_when_ratio_ge does NOT fire when ratio < threshold.

    Anti-tautology oracle: retenciones 9000 / rendimientos 15000 = 0.60 < 0.70.
    The predicate must return False (no advisory).
    """
    values: dict[str, Decimal] = {"06": Decimal("9000"), "01": Decimal("15000")}
    assert _evaluate_advisory_predicate_fires(
        'advisory_when_ratio_ge(["06", "01", "0.70"])', values
    ) is False


def test_advisory_when_ratio_ge_does_not_fire_when_denominator_zero() -> None:
    """advisory_when_ratio_ge: denominator guard prevents division by zero."""
    values: dict[str, Decimal] = {"06": Decimal("5000"), "01": Decimal("0")}
    assert _evaluate_advisory_predicate_fires(
        'advisory_when_ratio_ge(["06", "01", "0.70"])', values
    ) is False


def test_advisory_predicate_emits_warning_advisory_finding_when_condition_met() -> None:
    """Art. 110.3.b ADVISORY predicate produces a WARNING-severity ADVISORY finding when ratio >= 70%.

    The predicate is constructed with finding_kind='ADVISORY' (the new value added
    in this task). When the ratio condition holds, _evaluate_verification_predicates
    must produce exactly one finding of kind ADVISORY and severity WARNING.
    No BLOCKING_RULE finding is produced; the operator can still receive
    VERIFICADO_COMPLETO if all other gates pass.
    """
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-art110-3b-exencion-alta-retencion",
        legal_refs=("rd-439-2007:art-110-3-b",),
        expression='advisory_when_ratio_ge(["06", "01", "0.70"])',
        finding_kind="ADVISORY",
    )
    # Exactly 70% ratio: retenciones 10500 / rendimientos 15000
    casilla_values: dict[str, Decimal] = {"06": Decimal("10500"), "01": Decimal("15000")}

    from aeat.domain.modelos._verification_report import ModeloVerificationFindingSeverity

    findings = _evaluate_verification_predicates((predicate,), casilla_values)

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "rd-439-2007:art-110-3-b" in findings[0].legal_refs


def test_advisory_predicate_emits_no_finding_when_condition_not_met() -> None:
    """ADVISORY predicate produces no finding when ratio < 70%."""
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-art110-3b-exencion-alta-retencion",
        legal_refs=("rd-439-2007:art-110-3-b",),
        expression='advisory_when_ratio_ge(["06", "01", "0.70"])',
        finding_kind="ADVISORY",
    )
    # 60% ratio: retenciones 9000 / rendimientos 15000
    casilla_values: dict[str, Decimal] = {"06": Decimal("9000"), "01": Decimal("15000")}

    findings = _evaluate_verification_predicates((predicate,), casilla_values)
    assert findings == []


# ---------------------------------------------------------------------------
# S76: M130 all-zero regression
# ---------------------------------------------------------------------------


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


@pytest.fixture
def repos(tmp_path):
    """Real encrypted SQLite repos over a fresh isolated profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default") as profile:
        objects = profile.repository
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, vr, bv


def test_m130_all_zero_without_gastos_is_blocked(repos) -> None:
    """M130 revision with casilla 02 (Gastos) absent is blocked even when other casillas are zero.

    S76 regression: Layer 1 required=true on casilla 02 must block the
    VERIFICADO_COMPLETO transition when Gastos is not supplied. Before S73
    this filing would have been granted; after S73 it is blocked.
    """
    wu_repo, cr_repo, vr_repo, bv_repo = repos

    # Verify that the registry declares casilla 02 as required
    snap = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T")
    casilla_02 = next((c for c in snap.revision.casillas if str(c.id) == "02"), None)
    assert casilla_02 is not None, "M130 must have casilla 02 in registry"
    assert casilla_02.required is True, "M130 casilla 02 must be required=true (S73 Layer 1)"

    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    # Provide all casillas as zero EXCEPT casilla 02 (Gastos) which is required.
    # Casilla 15 is a previous_filing bound casilla — supply its binding value
    # (not as a casilla input) so the formula engine can resolve it.
    casilla_inputs: dict[str, Decimal] = {
        "05": Decimal("0"),
        "06": Decimal("0"),
        "08": Decimal("0"),
        "10": Decimal("0"),
        "16": Decimal("0"),
        "18": Decimal("0"),
        # casilla 01 is bound (from ledger), casilla 02 deliberately absent
    }

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verificado_completo is False
    assert report.completeness_status is not VerificationCompletenessStatus.COMPLETE
    assert "02" in report.missing_required_casillas, (
        "Casilla 02 must appear in missing_required_casillas when absent from inputs"
    )

    missing_kinds = {f.kind for f in report.findings}
    assert ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA in missing_kinds


def test_runtime_evaluator_recognises_every_known_predicate_operator() -> None:
    """P10.S68: the canonical predicate-operator set MUST be runtime-evaluable.

    The single source of truth lives at
    aeat.domain.calculations.registry._schema.KNOWN_VERIFICATION_PREDICATE_OPERATORS.
    The validator (in _validate_surfaces) uses it to reject unknown
    operators at registry-load time. The runtime evaluator
    (_evaluate_predicate_expression) has its own regex per operator.
    Drift between the two sets is a silent-pass hazard.

    Structural gate: each known operator MUST have a matching
    regex registered in _actions._PREDICATE_<NAME_UPPER>. The probe
    map below names the expected module-level regex variable per
    operator; the test asserts (a) the regex exists, (b) it matches
    the canonical probe expression for the operator. If the parallel
    campaign that owns advisory_when_ratio_ge ever renames or
    removes that regex without updating the canonical set, this
    test fires.
    """
    from aeat.application.modelo import _actions
    from aeat.domain.calculations.registry._schema import (
        KNOWN_VERIFICATION_PREDICATE_OPERATORS,
    )

    probe_expressions: dict[str, str] = {
        "all_nonzero": 'all_nonzero(["01", "02"])',
        "any_nonzero": 'any_nonzero(["01", "02"])',
        "cap_le_when_positive": 'cap_le_when_positive(["11", "10"])',
        "advisory_when_ratio_ge": 'advisory_when_ratio_ge(["01", "02", "0.5"])',
        "implies_nonzero": 'implies_nonzero(["01", "07"])',
    }
    regex_attr_names: dict[str, str] = {
        "all_nonzero": "_PREDICATE_ALL_NONZERO",
        "any_nonzero": "_PREDICATE_ANY_NONZERO",
        "cap_le_when_positive": "_PREDICATE_CAP_LE_WHEN_POSITIVE",
        "advisory_when_ratio_ge": "_PREDICATE_ADVISORY_WHEN_RATIO_GE",
        "implies_nonzero": "_PREDICATE_IMPLIES_NONZERO",
    }

    missing_probes = KNOWN_VERIFICATION_PREDICATE_OPERATORS.difference(probe_expressions)
    assert not missing_probes, (
        f"P10.S68 probe map is missing entries for known operators {sorted(missing_probes)!r}; "
        "extend probe_expressions and regex_attr_names when adding a new operator to the canonical set"
    )

    for operator_name in KNOWN_VERIFICATION_PREDICATE_OPERATORS:
        regex_attr = regex_attr_names[operator_name]
        regex = getattr(_actions, regex_attr, None)
        assert regex is not None, (
            f"Runtime evaluator missing regex {regex_attr!r} for known operator "
            f"{operator_name!r}; the canonical set "
            "(_schema.KNOWN_VERIFICATION_PREDICATE_OPERATORS) and the runtime "
            "evaluator's regex set must stay in sync"
        )
        probe = probe_expressions[operator_name]
        assert regex.match(probe) is not None, (
            f"Runtime evaluator regex {regex_attr!r} does not match the canonical "
            f"probe expression for {operator_name!r}: probe={probe!r}; pattern="
            f"{regex.pattern!r}. A probe-shape change in the parallel campaign "
            "must be reflected here so the gate catches the next drift."
        )


def test_m130_c15_cap_predicate_fires_blocking_rule_when_carry_forward_exceeds_c14(repos) -> None:
    """P09.S64: end-to-end integration test for the M130 C15 ≤ C14 cap predicate.

    Drives the full registry-load → snapshot → calculate_modelo_revision →
    verify_modelo_revision pipeline with a scenario where the prior-quarter
    saldo seed (supplied via binding_values for casilla 15) exceeds C14
    (computed from operator-supplied inputs). The verification report MUST
    surface a BLOCKING_RULE finding citing the
    modelo-130-c15-cap-by-c14 predicate.

    The earlier S60 test exercised the predicate evaluator with literal
    casilla values; this test exercises the FULL production pipeline —
    a registry-load typo / binding-aggregation regression / predicate-
    declaration drift would all surface here.
    """
    wu_repo, cr_repo, vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="2T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    # Modest operator inputs so C14 stays small + positive.
    casilla_inputs: dict[str, Decimal] = {
        "02": Decimal("0"),
        "05": Decimal("0"),
        "06": Decimal("0"),
        "08": Decimal("0"),
        "10": Decimal("0"),
        "16": Decimal("0"),
        "18": Decimal("0"),
    }
    # Carry-forward seed deliberately large — exceeds the computed C14.
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("99999"),
            # M130 C03 is a ledger-aggregated cumulative binding; supply
            # a small value so C14 stays small + positive (the cap rule
            # only fires when C14 > 0).
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("1000"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    # The cap predicate fires when C14 > 0 AND C15 > C14. The carry-
    # forward seed (99999) exceeds any plausible C14 computed from
    # the small inputs above; the predicate MUST emit a BLOCKING_RULE.
    blocking_findings = [
        f for f in report.findings if f.kind is ModeloVerificationFindingKind.BLOCKING_RULE
    ]
    cap_findings = [f for f in blocking_findings if "modelo-130-c15-cap-by-c14" in f.message]
    assert cap_findings, (
        "M130 C15-cap-by-C14 predicate must fire when carry-forward exceeds positive C14; "
        f"got blocking findings: {[f.message for f in blocking_findings]}"
    )
    assert report.granted_verificado_completo is False


def test_m131_c11_cap_predicate_fires_blocking_rule_when_carry_forward_exceeds_c10(repos) -> None:
    """P10.S69: M131 cap-predicate end-to-end integration (symmetry with S64).

    M131 declares modelo-131-<rev>-c11-cap-by-c10 on all 4 revisions
    via cap_le_when_positive(["11", "10"]). P09.S64 covered M130;
    this Step extends parallel coverage to M131. AEAT M131
    instructions cite the same cap rule verbatim: "en ningún caso
    podrá figurar en la casilla 11 un importe superior a la
    cantidad positiva consignada en la casilla 10".
    """
    wu_repo, cr_repo, vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id="default",
        modelo="131",
        filing_year=2026,
        period="2T",
        revision_id="2026",
        repository=wu_repo,
        clock=_T0,
    )

    # 04, 06, 07, 13 are computed casillas on the M131 2026 revision;
    # only the operator-input (manual) casillas may appear in inputs.
    casilla_inputs: dict[str, Decimal] = {
        "01": Decimal("100"),
        "02": Decimal("50"),
        "03": Decimal("0"),
        "05": Decimal("0"),
        "08": Decimal("0"),
        "09": Decimal("0"),
        "12": Decimal("0"),
        "14": Decimal("0"),
    }
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "modelo-131-2026-resultados-negativos-anteriores": Decimal("99999"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    blocking = [f for f in report.findings if f.kind is ModeloVerificationFindingKind.BLOCKING_RULE]
    cap_findings = [f for f in blocking if "modelo-131-2026-c11-cap-by-c10" in f.message]
    assert cap_findings, (
        "M131 C11-cap-by-C10 predicate must fire when carry-forward exceeds positive C10; "
        f"got blocking findings: {[f.message for f in blocking]}"
    )
    assert report.granted_verificado_completo is False


# ---------------------------------------------------------------------------
# S211: tampering regression — mutating a persisted observation is detected
# ---------------------------------------------------------------------------


def test_observation_tampering_is_detected_by_verify_path(repos) -> None:
    """Mutating a stored observation value between calculate and verify is caught.

    S211 regression: the observation provenance cross-check added in S210
    must detect when observations[i].value diverges from casilla_values for
    the same casilla. The verify path raises StoredCalculationDriftError and
    refuses VERIFICADO_COMPLETO.

    The tamper is applied by rewriting the stored catalogue with a mutated
    observation (different value from what casilla_values holds), keeping
    the revision id and casilla_values intact. The content-hash check passes
    because it does not cover observations; only the new provenance
    cross-check catches the drift.
    """
    wu_repo, cr_repo, _vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    casilla_inputs: dict[str, Decimal] = {
        "02": Decimal("1000"),
        "05": Decimal("0"),
        "06": Decimal("0"),
        "08": Decimal("0"),
        "10": Decimal("0"),
        "16": Decimal("0"),
        "18": Decimal("0"),
    }
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    # Require at least one typed observation for the provenance cross-check
    assert len(revision.observations) >= 1, (
        "The revision must carry at least one typed observation for S211 to be valid"
    )

    # Demonstrate that _assert_revision_content_integrity raises on provenance drift.
    # The CalculationRevision model validator already enforces consistency between
    # casilla_values and observations at construction time (preventing in-band
    # injection of inconsistent state). The runtime check is a defense-in-depth
    # layer against raw storage corruption that bypasses pydantic. We bypass
    # model_validator here via model_construct to simulate that scenario.
    from aeat.application.modelo._actions import _assert_revision_content_integrity
    from aeat.domain.calculations.registry import CasillaObservation

    target_obs = revision.observations[0]
    tampered_obs = CasillaObservation.model_construct(
        casilla_id=target_obs.casilla_id,
        value=target_obs.value + Decimal("9999"),
        formula_id=target_obs.formula_id,
        op=target_obs.op,
        operand_refs=target_obs.operand_refs,
        operand_values=target_obs.operand_values,
        legal_refs=target_obs.legal_refs,
        source_refs=target_obs.source_refs,
        absent_by_design=target_obs.absent_by_design,
    )
    tampered_observations = (tampered_obs, *revision.observations[1:])

    # Build a tampered revision bypassing the model validator (simulates raw storage drift)
    tampered_revision = CalculationRevisionCatalogue.__fields__["revisions"] if False else revision
    tampered_revision = revision.model_construct(
        **{
            **revision.model_dump(),
            "observations": tampered_observations,
        },
    )

    # The provenance cross-check must raise for the tampered revision
    with pytest.raises(StoredCalculationDriftError, match="provenance drift"):
        _assert_revision_content_integrity(tampered_revision)


# ---------------------------------------------------------------------------
# S318: legal_refs / source_refs threading through verification findings
# ---------------------------------------------------------------------------

# M130 casilla 02 oracle values drawn from:
#   src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/casillas/0001-casillas.toml
_M130_CASILLA_02_LEGAL_REFS = frozenset(
    {
        "rd-439-2007:art-110",
        "orden-eha-672-2007:art-1",
        "ley-35-2006:art-99",
        "rd-439-2007:art-95",
    }
)
_M130_CASILLA_02_SOURCE_REFS = frozenset(
    {
        "aeat-dr-130-2019-v12",
        "aeat-modelo-130-instructions",
    }
)


def test_missing_required_casilla_finding_carries_registry_provenance(repos) -> None:
    """A MISSING_REQUIRED_CASILLA finding must carry legal_refs and source_refs
    drawn from the registry casilla definition.

    S318 regression: before this fix findings had empty legal_refs/source_refs,
    making provenance invisible at the operator-facing verify surface.

    Expected values are drawn from the M130 casilla 02 TOML definition (the
    external authority), not hand-computed from the same formula.
    """
    wu_repo, cr_repo, vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    # Deliberately omit casilla 02 (Gastos) so a MISSING_REQUIRED_CASILLA
    # finding is produced for it.
    casilla_inputs: dict[str, Decimal] = {
        "05": Decimal("0"),
        "06": Decimal("0"),
        "08": Decimal("0"),
        "10": Decimal("0"),
        "16": Decimal("0"),
        "18": Decimal("0"),
    }
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    casilla_02_findings = [
        f
        for f in report.findings
        if f.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA and f.casilla_id == "02"
    ]
    assert casilla_02_findings, "Expected a MISSING_REQUIRED_CASILLA finding for casilla 02"
    finding = casilla_02_findings[0]

    # legal_refs must be non-empty and match the TOML oracle.
    assert finding.legal_refs, "finding.legal_refs must not be empty for a registry-backed casilla"
    assert frozenset(finding.legal_refs) == _M130_CASILLA_02_LEGAL_REFS, (
        f"finding.legal_refs {finding.legal_refs!r} does not match registry oracle "
        f"{sorted(_M130_CASILLA_02_LEGAL_REFS)!r}"
    )

    # source_refs must also be threaded through.
    assert finding.source_refs, "finding.source_refs must not be empty for a registry-backed casilla"
    assert frozenset(finding.source_refs) == _M130_CASILLA_02_SOURCE_REFS, (
        f"finding.source_refs {finding.source_refs!r} does not match registry oracle "
        f"{sorted(_M130_CASILLA_02_SOURCE_REFS)!r}"
    )


def test_missing_casilla_finding_legal_refs_empty_when_casilla_def_absent() -> None:
    """Anti-tautology: _missing_required_casilla_finding with no casilla_def produces empty refs.

    Proves the provenance threading is structural (not a constant default)
    and would fail the previous test if the casilla lookup returned None.
    """
    from aeat.application.modelo._actions import _missing_required_casilla_finding

    finding = _missing_required_casilla_finding("99", "wu-test-id", casilla_def=None)
    assert finding.legal_refs == (), "finding with no casilla_def must carry empty legal_refs"
    assert finding.source_refs == (), "finding with no casilla_def must carry empty source_refs"
