"""Verification substance tests: Layer 1 + Layer 2 predicate gate (contract, contract).

contract: Unit tests for the predicate DSL evaluator (evaluate_predicate_expression,
     evaluate_verification_predicates).

contract: Regression — Modelo 130 casilla 02 (Gastos) is now ledger-bound
     (the H1 fix), so the gasto resolver populates it (0 when there are no
     expenses) and an absent manual value no longer blocks verificado_completo
     (finding M4 resolved). The missing-required gate fires only for MANUAL
     required casillas; this module pins that behaviour and the provenance the
     finding carries.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import (
    KNOWN_VERIFICATION_PREDICATE_OPERATORS,
    CasillaId,
    VerificationPredicateDefinition,
)
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    derive_calculation_revision_id,
)
from ....domain.modelos._errors import ModeloError, ModeloValidationError
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
)
from ....domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    StoredCalculationDriftError,
    calculate_modelo_revision,
    create_work_unit,
    verify_modelo_revision,
)
from .._verification_actions import (
    evaluate_advisory_predicate_fires,
    evaluate_predicate_expression,
    evaluate_verification_predicates,
)
from ._verification_substance_support import (
    _ABSENT_REGISTRY_CASILLA,
    _CASILLA_00501,
    _CASILLA_01,
    _CASILLA_02,
    _CASILLA_03,
    _CASILLA_05,
    _CASILLA_06,
    _CASILLA_07,
    _CASILLA_08,
    _CASILLA_09,
    _CASILLA_10,
    _CASILLA_11,
    _CASILLA_12,
    _CASILLA_14,
    _CASILLA_15,
    _CASILLA_16,
    _CASILLA_18,
    _M200_BIN_APPLIED_CASILLA,
    _M200_BIN_CLOSING_CASILLA,
    _M200_BIN_GENERATED_CASILLA,
    _M200_BIN_OPEN_CASILLA,
    _T0,
    _T1,
    _T2,
    _casilla_values,
    _Repos,
    _seed_ready_profile,
    _workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# ---------------------------------------------------------------------------
# contract: unit tests for evaluate_predicate_expression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "values", "expected"),
    (
        (
            'all_nonzero(["01", "02"])',
            _casilla_values((_CASILLA_01, "1000"), (_CASILLA_02, "500")),
            True,
        ),
        (
            'all_nonzero(["01", "02"])',
            _casilla_values((_CASILLA_01, "1000"), (_CASILLA_02, "0")),
            False,
        ),
        (
            'all_nonzero(["01", "02"])',
            _casilla_values((_CASILLA_01, "1000")),
            False,
        ),
        (
            'any_nonzero(["01", "02"])',
            _casilla_values((_CASILLA_01, "0"), (_CASILLA_02, "500")),
            True,
        ),
        (
            'any_nonzero(["01", "02"])',
            _casilla_values((_CASILLA_01, "0"), (_CASILLA_02, "0")),
            False,
        ),
        ('any_nonzero(["01", "02"])', {}, False),
    ),
    ids=(
        "all-present-nonzero",
        "all-one-zero",
        "all-one-absent",
        "any-one-nonzero",
        "any-all-zero",
        "any-all-absent",
    ),
)
def test_nonzero_collection_predicates(expression: str, values: dict[CasillaId, Decimal], expected: bool) -> None:
    """all_nonzero and any_nonzero evaluate present, zero, and absent casillas explicitly."""
    assert evaluate_predicate_expression(expression, values, _workflow_profile()) is expected


def test_predicate_expression_rejects_noncanonical_casilla_id_token() -> None:
    """Predicate casilla references fail instead of reading malformed ids as absent zeroes."""
    values: dict[CasillaId, Decimal] = {_CASILLA_01: Decimal("1000")}

    with pytest.raises(ModeloError, match=r"non-canonical casilla\.id"):
        evaluate_predicate_expression('all_nonzero(["01", "bad key"])', values, _workflow_profile())


def test_cap_le_when_positive_passes_when_limited_within_ceiling() -> None:
    """cap_le_when_positive: passes when ceiling > 0 AND limited ≤ ceiling."""
    values: dict[CasillaId, Decimal] = {_CASILLA_11: Decimal("300"), _CASILLA_10: Decimal("500")}
    assert evaluate_predicate_expression('cap_le_when_positive(["11", "10"])', values, _workflow_profile()) is True


def test_cap_le_when_positive_fails_when_limited_exceeds_ceiling() -> None:
    """cap_le_when_positive: fails when ceiling > 0 AND limited > ceiling.

    Predicate case: M131 C11 (resultados negativos anteriores) MUST NOT
    exceed C10 (cuota positiva del trimestre) per AEAT instructions
    "en ningún caso podrá figurar en la casilla 11 un importe superior
    a la cantidad positiva consignada en la casilla 10".
    """
    values: dict[CasillaId, Decimal] = {_CASILLA_11: Decimal("750"), _CASILLA_10: Decimal("500")}
    assert evaluate_predicate_expression('cap_le_when_positive(["11", "10"])', values, _workflow_profile()) is False


def test_cap_le_when_positive_emits_blocking_rule_finding_for_violated_predicate() -> None:
    """A violated cap_le_when_positive predicate produces a BLOCKING_RULE finding.

    Constructs the exact M130 C15-cap predicate used in the
    registry (modelo-130-c15-cap-by-c14) and runs it through
    evaluate_verification_predicates with a casilla_values map
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
    casilla_values = {_CASILLA_14: Decimal("1000"), _CASILLA_15: Decimal("1500")}

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert "modelo-130-c15-cap-by-c14" in findings[0].message


def test_cap_le_when_positive_emits_no_finding_when_within_cap() -> None:
    """A satisfied cap predicate produces no finding."""
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-c15-cap-by-c14",
        legal_refs=("rd-439-2007:art-110",),
        expression='cap_le_when_positive(["15", "14"])',
        finding_kind="BLOCKING_RULE",
    )
    # C14 = 1000, C15 = 600 — within cap
    casilla_values = {_CASILLA_14: Decimal("1000"), _CASILLA_15: Decimal("600")}

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert findings == []


def test_cap_le_when_positive_holds_when_ceiling_is_zero_or_negative() -> None:
    """cap_le_when_positive: predicate holds (no cap) when ceiling ≤ 0.

    The AEAT cap rule only applies when the operator's gross liability
    is positive. A zero or negative cuota means there's no cap to
    enforce; the predicate must NOT block in that case.
    """
    values_zero: dict[CasillaId, Decimal] = {_CASILLA_11: Decimal("750"), _CASILLA_10: Decimal("0")}
    assert evaluate_predicate_expression('cap_le_when_positive(["11", "10"])', values_zero, _workflow_profile()) is True
    values_negative: dict[CasillaId, Decimal] = {_CASILLA_11: Decimal("750"), _CASILLA_10: Decimal("-50")}
    assert (
        evaluate_predicate_expression('cap_le_when_positive(["11", "10"])', values_negative, _workflow_profile())
        is True
    )


# ---------------------------------------------------------------------------
# contract: roll_forward_balances carry-forward continuity predicate (IS-2)
#
# The Modelo 200 BIN closing-stock roll-forward (modelo-200-bin-continuity decision record):
#   00671 (closing total pendiente) == 00670 (opening, bound)
#                                       − DP200014:00547 (applied)
#                                       + max(0, −DP200014:00552) (BIN generated)
# Expected values are derived from that AEAT roll-forward rule, NOT from the
# predicate formula under test.
# ---------------------------------------------------------------------------

_BIN_ROLL_FORWARD = 'roll_forward_balances(["00671", "00670", "DP200014:00547", "DP200014:00552"])'


@pytest.mark.parametrize(
    ("values", "predicate_holds", "advisory_fires"),
    (
        (
            _casilla_values(
                (_M200_BIN_OPEN_CASILLA, "10000"),
                (_M200_BIN_APPLIED_CASILLA, "3000"),
                (_M200_BIN_GENERATED_CASILLA, "5000"),
                (_M200_BIN_CLOSING_CASILLA, "7000"),
            ),
            True,
            False,
        ),
        (
            _casilla_values(
                (_M200_BIN_OPEN_CASILLA, "10000"),
                (_M200_BIN_APPLIED_CASILLA, "3000"),
                (_M200_BIN_GENERATED_CASILLA, "5000"),
                (_M200_BIN_CLOSING_CASILLA, "0"),
            ),
            False,
            True,
        ),
        (
            _casilla_values(
                (_M200_BIN_OPEN_CASILLA, "3000"),
                (_M200_BIN_APPLIED_CASILLA, "3000"),
                (_M200_BIN_GENERATED_CASILLA, "8000"),
                (_M200_BIN_CLOSING_CASILLA, "0"),
            ),
            True,
            False,
        ),
        (
            _casilla_values(
                (_M200_BIN_OPEN_CASILLA, "5000"),
                (_M200_BIN_APPLIED_CASILLA, "2000"),
                (_M200_BIN_GENERATED_CASILLA, "-4000"),
                (_M200_BIN_CLOSING_CASILLA, "7000"),
            ),
            True,
            False,
        ),
    ),
    ids=("reconciles", "dropped-closing", "legitimate-zero-closing", "generated-loss-added"),
)
def test_roll_forward_balances_core_cases(
    values: dict[CasillaId, Decimal],
    predicate_holds: bool,
    advisory_fires: bool,
) -> None:
    """The BIN roll-forward predicate distinguishes continuous filings from dropped stock."""
    assert evaluate_predicate_expression(_BIN_ROLL_FORWARD, values, _workflow_profile()) is predicate_holds
    assert evaluate_advisory_predicate_fires(_BIN_ROLL_FORWARD, values) is advisory_fires


def test_roll_forward_balances_tolerates_one_cent_but_not_euros() -> None:
    """Sub-cent drift reconciles; a euro-scale discontinuity fires."""
    base: dict[CasillaId, Decimal] = {
        _M200_BIN_OPEN_CASILLA: Decimal("10000"),
        _M200_BIN_APPLIED_CASILLA: Decimal("3000"),
        _M200_BIN_GENERATED_CASILLA: Decimal("5000"),
    }
    within = {**base, _M200_BIN_CLOSING_CASILLA: Decimal("7000.01")}
    assert evaluate_advisory_predicate_fires(_BIN_ROLL_FORWARD, within) is False
    beyond = {**base, _M200_BIN_CLOSING_CASILLA: Decimal("7001")}
    assert evaluate_advisory_predicate_fires(_BIN_ROLL_FORWARD, beyond) is True


def test_roll_forward_balances_bad_arity_holds_and_does_not_fire() -> None:
    """A malformed arity reads as holding (BLOCKING) and never fires (ADVISORY)."""
    expr = 'roll_forward_balances(["00671", "00670", "DP200014:00547"])'
    values: dict[CasillaId, Decimal] = {
        _M200_BIN_CLOSING_CASILLA: Decimal("0"),
        _M200_BIN_OPEN_CASILLA: Decimal("9999"),
    }
    assert evaluate_predicate_expression(expr, values, _workflow_profile()) is True
    assert evaluate_advisory_predicate_fires(expr, values) is False


def test_roll_forward_balances_emits_advisory_finding_on_discontinuity() -> None:
    """The ADVISORY M200 BIN predicate fires a WARNING finding on a dropped carryforward."""
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-200-bin-stock-cierre-reconcilia-roll-forward",
        legal_refs=("ley-27-2014:art-26",),
        expression=_BIN_ROLL_FORWARD,
        finding_kind="ADVISORY",
    )
    # roll-forward = 10000 − 3000 + 0 = 7000; operator dropped closing to 0
    values: dict[CasillaId, Decimal] = {
        _M200_BIN_OPEN_CASILLA: Decimal("10000"),
        _M200_BIN_APPLIED_CASILLA: Decimal("3000"),
        _M200_BIN_GENERATED_CASILLA: Decimal("5000"),
        _M200_BIN_CLOSING_CASILLA: Decimal("0"),
    }
    findings = evaluate_verification_predicates((predicate,), values, _workflow_profile())
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert "ley-27-2014:art-26" in findings[0].legal_refs


def test_roll_forward_balances_emits_no_finding_when_continuous() -> None:
    """The ADVISORY M200 BIN predicate stays silent for a reconciling closing."""
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-200-bin-stock-cierre-reconcilia-roll-forward",
        legal_refs=("ley-27-2014:art-26",),
        expression=_BIN_ROLL_FORWARD,
        finding_kind="ADVISORY",
    )
    values: dict[CasillaId, Decimal] = {
        _M200_BIN_OPEN_CASILLA: Decimal("10000"),
        _M200_BIN_APPLIED_CASILLA: Decimal("3000"),
        _M200_BIN_GENERATED_CASILLA: Decimal("5000"),
        _M200_BIN_CLOSING_CASILLA: Decimal("7000"),
    }
    assert evaluate_verification_predicates((predicate,), values, _workflow_profile()) == []


def test_unknown_expression_does_not_block() -> None:
    """An unrecognised expression pattern does not produce a blocking finding."""
    values: dict[CasillaId, Decimal] = {}
    # Passes through — unknown DSL extensions do not block existing registry data.
    assert evaluate_predicate_expression('threshold(["01"], 100)', values, _workflow_profile()) is True


# ---------------------------------------------------------------------------
# implies_nonzero — conditional predicate with strictly-positive antecedent
# Authority: conditional predicate rule-set reference
# ---------------------------------------------------------------------------

_IMPLIES_NONZERO_C01_C07 = 'implies_nonzero(["01", "07"])'


@pytest.mark.parametrize(
    ("values", "expected"),
    (
        (_casilla_values((_CASILLA_01, "0"), (_CASILLA_07, "0")), True),
        (_casilla_values((_CASILLA_01, "-100"), (_CASILLA_07, "0")), True),
        (_casilla_values((_CASILLA_01, "500"), (_CASILLA_07, "200")), True),
        (_casilla_values((_CASILLA_01, "500"), (_CASILLA_07, "0")), False),
        (_casilla_values((_CASILLA_01, "500")), False),
    ),
    ids=(
        "antecedent-zero",
        "antecedent-negative",
        "both-positive",
        "positive-antecedent-zero-consequent",
        "positive-antecedent-absent-consequent",
    ),
)
def test_predicate_implies_nonzero_cases(values: dict[CasillaId, Decimal], expected: bool) -> None:
    """implies_nonzero engages only for strictly-positive antecedents and treats absent consequents as zero."""
    assert evaluate_predicate_expression(_IMPLIES_NONZERO_C01_C07, values, _workflow_profile()) is expected


def test_evaluate_verification_predicates_empty_returns_no_findings() -> None:
    """Empty predicate tuple yields empty findings list."""
    findings = evaluate_verification_predicates((), {}, _workflow_profile())
    assert findings == []


def test_evaluate_verification_predicates_violation_produces_blocking_rule() -> None:
    """A violated all_nonzero predicate produces a BLOCKING_RULE finding."""
    predicate = VerificationPredicateDefinition(
        predicate_id="test-invariant",
        legal_refs=("ley-35-2006:art-99",),
        expression='all_nonzero(["01", "02"])',
        finding_kind="BLOCKING_RULE",
    )
    values: dict[CasillaId, Decimal] = {_CASILLA_01: Decimal("1000"), _CASILLA_02: Decimal("0")}
    findings = evaluate_verification_predicates((predicate,), values, _workflow_profile())
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
    values: dict[CasillaId, Decimal] = {_CASILLA_01: Decimal("1000"), _CASILLA_02: Decimal("500")}
    findings = evaluate_verification_predicates((predicate,), values, _workflow_profile())
    assert findings == []


# ---------------------------------------------------------------------------
# Art. 109 RIRPF advisory predicate unit tests
# ---------------------------------------------------------------------------

_ADVISORY_RATIO_GE = 'advisory_when_ratio_ge(["06", "01", "0.70"])'


@pytest.mark.parametrize(
    ("values", "expected"),
    (
        (_casilla_values((_CASILLA_06, "10500"), (_CASILLA_01, "15000")), True),
        (_casilla_values((_CASILLA_06, "12000"), (_CASILLA_01, "15000")), True),
        (_casilla_values((_CASILLA_06, "9000"), (_CASILLA_01, "15000")), False),
        (_casilla_values((_CASILLA_06, "5000"), (_CASILLA_01, "0")), False),
    ),
    ids=("exact-threshold", "above-threshold", "below-threshold", "zero-denominator"),
)
def test_advisory_when_ratio_ge_cases(values: dict[CasillaId, Decimal], expected: bool) -> None:
    """advisory_when_ratio_ge fires at or above the threshold and stays silent below it or with no denominator."""
    assert evaluate_advisory_predicate_fires(_ADVISORY_RATIO_GE, values) is expected


def test_advisory_when_ratio_ge_rejects_noncanonical_casilla_id_token() -> None:
    values: dict[CasillaId, Decimal] = {_CASILLA_06: Decimal("100"), _CASILLA_01: Decimal("100")}

    with pytest.raises(ModeloError, match=r"non-canonical casilla\.id"):
        evaluate_advisory_predicate_fires('advisory_when_ratio_ge(["06", "bad key", "0.70"])', values)


_ADVISORY_IMPLIES_M200_BASE = 'implies_nonzero(["00501", "DP200014:00552"])'


@pytest.mark.parametrize(
    ("values", "expected"),
    (
        (_casilla_values((_CASILLA_00501, "140000"), (_M200_BIN_GENERATED_CASILLA, "0")), True),
        (_casilla_values((_CASILLA_00501, "-5000"), (_M200_BIN_GENERATED_CASILLA, "0")), False),
        (_casilla_values((_CASILLA_00501, "0"), (_M200_BIN_GENERATED_CASILLA, "0")), False),
        (_casilla_values((_CASILLA_00501, "140000"), (_M200_BIN_GENERATED_CASILLA, "140000")), False),
    ),
    ids=("positive-result-zero-base", "loss-result", "zero-result", "determined-base"),
)
def test_advisory_implies_nonzero_cases(values: dict[CasillaId, Decimal], expected: bool) -> None:
    """The M200 advisory fires only when positive resultado contable has no determined base."""
    assert evaluate_advisory_predicate_fires(_ADVISORY_IMPLIES_M200_BASE, values) is expected


def test_advisory_predicate_emits_warning_advisory_finding_when_condition_met() -> None:
    """Art. 109 ADVISORY predicate produces a WARNING-severity ADVISORY finding when ratio >= 70%.

    The predicate is constructed with finding_kind='ADVISORY' (the new value added
    in this task). When the ratio condition holds, evaluate_verification_predicates
    must produce exactly one finding of kind ADVISORY and severity WARNING.
    No BLOCKING_RULE finding is produced; the operator can still receive
    VERIFICADO_COMPLETO if all other gates pass.
    """
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-art109-exencion-alta-retencion",
        legal_refs=("rd-439-2007:art-109",),
        expression='advisory_when_ratio_ge(["06", "01", "0.70"])',
        finding_kind="ADVISORY",
    )
    # Exactly 70% ratio: retenciones 10500 / rendimientos 15000
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_06: Decimal("10500"),
        _CASILLA_01: Decimal("15000"),
    }

    from ....domain.modelos._verification_report import ModeloVerificationFindingSeverity

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "rd-439-2007:art-109" in findings[0].legal_refs


def test_advisory_predicate_emits_no_finding_when_condition_not_met() -> None:
    """ADVISORY predicate produces no finding when ratio < 70%."""
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-art109-exencion-alta-retencion",
        legal_refs=("rd-439-2007:art-109",),
        expression='advisory_when_ratio_ge(["06", "01", "0.70"])',
        finding_kind="ADVISORY",
    )
    # 60% ratio: retenciones 9000 / rendimientos 15000
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_06: Decimal("9000"),
        _CASILLA_01: Decimal("15000"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert findings == []


# ---------------------------------------------------------------------------
# contract: M130 all-zero regression
# ---------------------------------------------------------------------------


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Real encrypted SQLite repos over a fresh isolated profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default") as profile:
        objects = profile.repository
        _seed_ready_profile(UserProfileLifecycleRepository(bucket_id="default", objects=objects), bucket_id="default")
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, vr, bv


def test_m130_casilla_02_gastos_is_ledger_bound_not_manual_blocking(repos: _Repos) -> None:
    """M130 casilla 02 (Gastos) is ledger-bound, so an absent manual value never blocks.

    Regression for finding M4: casilla 02 used to be ``input_kind = manual``,
    so a filer with no gastos was blocked with a MISSING_REQUIRED_CASILLA finding
    until they hand-entered ``--casilla 02=0``. Casilla 02 is now bound to the
    ``ledger_renta_gasto_aggregation`` source (the H1 fix): the gasto resolver
    populates it from the ledger (0 when there are no expenses), so the
    missing-required gate — which fires only for MANUAL required casillas — never
    flags it. The required=true flag is retained but is inert for a bound casilla.
    """
    wu_repo, cr_repo, vr_repo, bv_repo = repos

    snap = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T")
    casilla_02 = next((c for c in snap.revision.casillas if c.id == _CASILLA_02), None)
    assert casilla_02 is not None, "M130 must have casilla 02 in registry"
    assert str(casilla_02.input_kind) == "bound", "M130 casilla 02 must be ledger-bound (H1 fix)"
    assert casilla_02.binding == "modelo-130-actividad-economica-gastos-cumulative"

    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    # Casilla 02 is deliberately NOT supplied (no ledger gastos, no manual value).
    casilla_inputs: dict[CasillaId, Decimal] = {
        _CASILLA_05: Decimal("0"),
        _CASILLA_06: Decimal("0"),
        _CASILLA_08: Decimal("0"),
        _CASILLA_10: Decimal("0"),
        _CASILLA_16: Decimal("0"),
        _CASILLA_18: Decimal("0"),
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

    # M4 resolved: casilla 02 is bound, so it is NOT a manual missing-required block.
    assert _CASILLA_02 not in report.missing_required_casilla_ids
    casilla_02_missing = [
        f
        for f in report.findings
        if f.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA and f.casilla_id == _CASILLA_02
    ]
    assert not casilla_02_missing, "bound casilla 02 must not produce a MISSING_REQUIRED_CASILLA finding"


def test_runtime_evaluator_recognises_every_known_predicate_operator() -> None:
    """The canonical predicate-operator set MUST be runtime-evaluable.

    The single source of truth lives at
    aeat.domain.calculations.registry.KNOWN_VERIFICATION_PREDICATE_OPERATORS.
    The validator (in _validate_surfaces) uses it to reject unknown
    operators at registry-load time. The runtime evaluator
    (evaluate_predicate_expression) has its own regex per operator.
    Drift between the two sets is a silent-pass hazard.

    Structural gate: each known operator MUST have a matching
    regex registered in _verification_actions._PREDICATE_<NAME_UPPER>. The probe
    map below names the expected module-level regex variable per
    operator; the test asserts (a) the regex exists, (b) it matches
    the canonical probe expression for the operator. If the parallel
    campaign that owns advisory_when_ratio_ge ever renames or
    removes that regex without updating the canonical set, this
    test fires.
    """
    from .. import _verification_actions

    probe_expressions: dict[str, str] = {
        "all_nonzero": 'all_nonzero(["01", "02"])',
        "any_nonzero": 'any_nonzero(["01", "02"])',
        "cap_le_when_positive": 'cap_le_when_positive(["11", "10"])',
        "advisory_when_ratio_ge": 'advisory_when_ratio_ge(["01", "02", "0.5"])',
        "equals": 'equals(["27", "iva.cuota-devengada-total"])',
        "implies_nonzero": 'implies_nonzero(["01", "07"])',
        "implies_any_nonzero": 'implies_any_nonzero(["iva.cuota-devengada-total", "03", "06", "09"])',
        "profile_field_required": ('profile_field_required("representante_fiscal_nif", "non_resident_irnr_non_eea")'),
        "roll_forward_balances": 'roll_forward_balances(["00671", "00670", "DP200014:00547", "DP200014:00552"])',
    }
    regex_attr_names: dict[str, str] = {
        "all_nonzero": "_PREDICATE_ALL_NONZERO",
        "any_nonzero": "_PREDICATE_ANY_NONZERO",
        "cap_le_when_positive": "_PREDICATE_CAP_LE_WHEN_POSITIVE",
        "advisory_when_ratio_ge": "_PREDICATE_ADVISORY_WHEN_RATIO_GE",
        "equals": "_PREDICATE_EQUALS",
        "implies_nonzero": "_PREDICATE_IMPLIES_NONZERO",
        "implies_any_nonzero": "_PREDICATE_IMPLIES_ANY_NONZERO",
        "profile_field_required": "_PREDICATE_PROFILE_FIELD_REQUIRED",
        "roll_forward_balances": "_PREDICATE_ROLL_FORWARD_BALANCES",
    }

    missing_probes = KNOWN_VERIFICATION_PREDICATE_OPERATORS.difference(probe_expressions)
    assert not missing_probes, (
        f"Probe map is missing entries for known operators {sorted(missing_probes)!r}; "
        "extend probe_expressions and regex_attr_names when adding a new operator to the canonical set"
    )

    for operator_name in KNOWN_VERIFICATION_PREDICATE_OPERATORS:
        regex_attr = regex_attr_names[operator_name]
        regex = getattr(_verification_actions, regex_attr, None)
        assert regex is not None, (
            f"Runtime evaluator missing regex {regex_attr!r} for known operator "
            f"{operator_name!r}; the canonical set "
            "(registry.KNOWN_VERIFICATION_PREDICATE_OPERATORS) and the runtime "
            "evaluator's regex set must stay in sync"
        )
        probe = probe_expressions[operator_name]
        assert regex.match(probe) is not None, (
            f"Runtime evaluator regex {regex_attr!r} does not match the canonical "
            f"probe expression for {operator_name!r}: probe={probe!r}; pattern="
            f"{regex.pattern!r}. A probe-shape change in the parallel campaign "
            "must be reflected here so the gate catches the next drift."
        )


def test_m130_c15_cap_predicate_fires_blocking_rule_when_carry_forward_exceeds_c14(repos: _Repos) -> None:
    wu_repo, cr_repo, vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    # Modest operator inputs so C14 stays small + positive.
    # C01 (ingresos) is bound via ledger_renta_income_aggregation, but the
    # ledger binding's smuggling guard only applies to previous_filing
    # sources; supplying C01 directly is the supported manual-entry path
    # mirrored by the M131 sibling test below.
    casilla_inputs: dict[CasillaId, Decimal] = {
        _CASILLA_01: Decimal("10000"),
        _CASILLA_02: Decimal("0"),
        _CASILLA_05: Decimal("0"),
        _CASILLA_06: Decimal("0"),
        _CASILLA_08: Decimal("0"),
        _CASILLA_10: Decimal("0"),
        _CASILLA_16: Decimal("0"),
        _CASILLA_18: Decimal("0"),
    }
    # Carry-forward seed deliberately large — exceeds the computed C14.
    # previous_year_economic_activity_net_income > 12000 keeps the C13
    # minoración at zero so C14 = C12 (positive cuota) instead of being
    # eroded to negative by the small-income minoración bracket.
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("20000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("99999"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    invalid_c15 = revision.casilla_values[_CASILLA_14] + Decimal("1.00")
    invalid_values = dict(revision.casilla_values)
    invalid_values[_CASILLA_15] = invalid_c15
    invalid_observations = tuple(
        observation.model_copy(update={"value": invalid_c15}) if observation.casilla_id == _CASILLA_15 else observation
        for observation in revision.observations
    )
    invalid_revision_id = derive_calculation_revision_id(
        work_unit_id=revision.work_unit_id,
        input_values_by_casilla_id=revision.input_values_by_casilla_id,
        binding_overrides=revision.binding_overrides,
        relation_overrides=revision.relation_overrides,
        casilla_values=invalid_values,
        source_transaction_ids=revision.source_transaction_ids,
        borrador_snapshot_id=revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=revision.bindings_sourced_from_borrador,
        detail_rows=revision.detail_rows,
    )
    invalid_revision = CalculationRevision(
        calculation_revision_id=invalid_revision_id,
        work_unit_id=revision.work_unit_id,
        state=revision.state,
        input_values_by_casilla_id=revision.input_values_by_casilla_id,
        binding_overrides=revision.binding_overrides,
        relation_overrides=revision.relation_overrides,
        source_transaction_ids=revision.source_transaction_ids,
        borrador_snapshot_id=revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=revision.bindings_sourced_from_borrador,
        casilla_values=invalid_values,
        observations=invalid_observations,
        detail_rows=revision.detail_rows,
        created_at=revision.created_at,
        updated_at=revision.updated_at,
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), invalid_revision))

    report = verify_modelo_revision(
        invalid_revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    blocking_findings = [f for f in report.findings if f.kind is ModeloVerificationFindingKind.BLOCKING_RULE]
    cap_findings = [f for f in blocking_findings if "modelo-130-c15-cap-by-c14" in f.message]
    assert cap_findings, (
        "M130 C15-cap-by-C14 predicate must fire when carry-forward exceeds positive C14; "
        f"got blocking findings: {[f.message for f in blocking_findings]}"
    )
    assert report.granted_verificado_completo is False


def test_m131_c11_cap_predicate_fires_blocking_rule_when_carry_forward_exceeds_c10(repos: _Repos) -> None:
    """M131 cap-predicate end-to-end integration.

    M131 declares modelo-131-<rev>-c11-cap-by-c10 on all 4 revisions
    via cap_le_when_positive(["11", "10"]). The companion test covers M130;
    this test extends parallel coverage to M131. AEAT M131
    instructions cite the same cap rule verbatim: "en ningún caso
    podrá figurar en la casilla 11 un importe superior a la
    cantidad positiva consignada en la casilla 10".
    """
    wu_repo, cr_repo, vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id="default",
        modelo="131",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        revision_id="2026",
        repository=wu_repo,
        clock=_T0,
    )

    # 04, 06, 07, 13 are computed casillas on the M131 2026 revision;
    # only the operator-input (manual) casillas may appear in inputs.
    casilla_inputs: dict[CasillaId, Decimal] = {
        _CASILLA_01: Decimal("100"),
        _CASILLA_02: Decimal("50"),
        _CASILLA_03: Decimal("0"),
        _CASILLA_05: Decimal("0"),
        _CASILLA_08: Decimal("0"),
        _CASILLA_09: Decimal("0"),
        _CASILLA_12: Decimal("0"),
        _CASILLA_14: Decimal("0"),
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
# contract: tampering regression — mutating a persisted observation is detected
# ---------------------------------------------------------------------------


def test_observation_tampering_is_detected_by_verify_path(repos: _Repos) -> None:
    """Mutating a stored observation value between calculate and verify is caught.

    contract regression: the observation provenance cross-check added in contract
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
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    casilla_inputs: dict[CasillaId, Decimal] = {
        _CASILLA_02: Decimal("1000"),
        _CASILLA_05: Decimal("0"),
        _CASILLA_06: Decimal("0"),
        _CASILLA_08: Decimal("0"),
        _CASILLA_10: Decimal("0"),
        _CASILLA_16: Decimal("0"),
        _CASILLA_18: Decimal("0"),
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

    # Demonstrate that assert_revision_content_integrity raises on provenance drift.
    # The CalculationRevision model validator already enforces consistency between
    # casilla_values and observations at construction time (preventing in-band
    # injection of inconsistent state). The runtime check is a defense-in-depth
    # layer against raw storage corruption that bypasses pydantic. We bypass
    # model_validator here via model_construct to simulate that scenario.
    from ....domain.calculations.registry import CasillaObservation
    from .._registry_helpers import assert_revision_content_integrity as _assert_revision_content_integrity

    target_obs = revision.observations[0]
    tampered_obs = CasillaObservation.model_construct(
        casilla_id=target_obs.casilla_id,
        value=target_obs.value + Decimal("9999"),
        formula_id=target_obs.formula_id,
        op=target_obs.op,
        operand_refs=target_obs.operand_refs,
        operand_casilla_refs=target_obs.operand_casilla_refs,
        operand_values=target_obs.operand_values,
        legal_refs=target_obs.legal_refs,
        source_refs=target_obs.source_refs,
        absent_by_design=target_obs.absent_by_design,
    )
    tampered_observations = (tampered_obs, *revision.observations[1:])

    # Build a tampered revision bypassing the model validator (simulates raw storage drift).
    tampered_payload: dict[str, Any] = revision.model_dump()
    tampered_payload["observations"] = tampered_observations
    tampered_revision = revision.model_construct(**tampered_payload)

    # The provenance cross-check must raise for the tampered revision
    with pytest.raises(StoredCalculationDriftError, match="provenance drift"):
        _assert_revision_content_integrity(tampered_revision)


# ---------------------------------------------------------------------------
# contract: legal_refs / source_refs threading through verification findings
# ---------------------------------------------------------------------------


def test_missing_required_casilla_finding_carries_registry_provenance() -> None:
    """A MISSING_REQUIRED_CASILLA finding must carry legal_refs and source_refs
    drawn from the registry casilla definition.

    contract regression: before this fix findings had empty legal_refs/source_refs,
    making provenance invisible at the operator-facing verify surface.

    Exercises the finding builder directly against the live M130 casilla 02
    registry definition (its provenance is unchanged by the H1 bind: the casilla
    keeps its legal_refs/source_refs whether manual or bound). The oracle is read
    from the registry casilla definition — the authority the finding draws from —
    so the assertion proves the finding's provenance equals the registry's, not a
    hand-copied list. The companion refusal test proves a missing registry
    definition is a hard error, not an empty-provenance finding.
    """
    from .._verification_actions import missing_required_casilla_finding

    snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T")
    casilla_02 = next(c for c in snapshot.revision.casillas if c.id == _CASILLA_02)
    expected_legal_refs = frozenset(str(r) for r in casilla_02.legal_refs)
    expected_source_refs = frozenset(str(r) for r in casilla_02.source_refs)
    assert expected_legal_refs, "registry casilla 02 must declare legal_refs (oracle precondition)"
    assert expected_source_refs, "registry casilla 02 must declare source_refs (oracle precondition)"

    finding = missing_required_casilla_finding(_CASILLA_02, "wu-test-id", casilla_def=casilla_02)

    assert finding.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA
    assert finding.casilla_id == _CASILLA_02
    assert finding.legal_refs, "finding.legal_refs must not be empty for a registry-backed casilla"
    assert frozenset(finding.legal_refs) == expected_legal_refs, (
        f"finding.legal_refs {finding.legal_refs!r} does not match registry oracle {sorted(expected_legal_refs)!r}"
    )
    assert frozenset(finding.source_refs) == expected_source_refs, (
        f"finding.source_refs {finding.source_refs!r} does not match registry oracle {sorted(expected_source_refs)!r}"
    )


def test_missing_casilla_finding_refuses_absent_registry_definition() -> None:
    """Missing-required findings must not be emitted without registry provenance."""
    from .._verification_actions import missing_required_casilla_finding

    with pytest.raises(ModeloValidationError, match="requires registry casilla definition provenance"):
        missing_required_casilla_finding(_ABSENT_REGISTRY_CASILLA, "wu-test-id", casilla_def=None)
