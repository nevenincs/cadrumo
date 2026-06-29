"""Verification predicate substance tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry import (
    CasillaId,
    VerificationPredicateDefinition,
)
from ....domain.modelos._errors import ModeloError
from ....domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
)
from .._verification_actions import (
    evaluate_advisory_predicate_fires,
    evaluate_predicate_expression,
    evaluate_verification_predicates,
)
from ._verification_substance_support import (
    _CASILLA_01,
    _CASILLA_02,
    _CASILLA_07,
    _CASILLA_10,
    _CASILLA_11,
    _CASILLA_14,
    _CASILLA_15,
    _M200_BIN_APPLIED_CASILLA,
    _M200_BIN_CLOSING_CASILLA,
    _M200_BIN_GENERATED_CASILLA,
    _M200_BIN_OPEN_CASILLA,
    _casilla_values,
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
