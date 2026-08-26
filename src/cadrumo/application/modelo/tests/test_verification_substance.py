"""Verification predicate substance tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.schema_verification import (
    ParsedVerificationPredicate,
    VerificationPredicateDefinition,
    VerificationPredicateOperator,
    parse_verification_predicate_expression,
)

from ....core import CasillaId, Modelo, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import ModeloError, ModeloVerificationFindingKind
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


def test_nonzero_collection_predicates() -> None:
    """all_nonzero and any_nonzero evaluate present, zero, and absent casillas explicitly."""
    cases = (
        (
            "all-present-nonzero",
            'all_nonzero(["01", "02"])',
            _casilla_values((_CASILLA_01, "1000"), (_CASILLA_02, "500")),
            True,
        ),
        (
            "all-one-zero",
            'all_nonzero(["01", "02"])',
            _casilla_values((_CASILLA_01, "1000"), (_CASILLA_02, "0")),
            False,
        ),
        (
            "all-one-absent",
            'all_nonzero(["01", "02"])',
            _casilla_values((_CASILLA_01, "1000")),
            False,
        ),
        (
            "any-one-nonzero",
            'any_nonzero(["01", "02"])',
            _casilla_values((_CASILLA_01, "0"), (_CASILLA_02, "500")),
            True,
        ),
        (
            "any-all-zero",
            'any_nonzero(["01", "02"])',
            _casilla_values((_CASILLA_01, "0"), (_CASILLA_02, "0")),
            False,
        ),
        ("any-all-absent", 'any_nonzero(["01", "02"])', {}, False),
    )

    for case_id, expression, values, expected in cases:
        assert evaluate_predicate_expression(expression, values, _workflow_profile()) is expected, case_id


def test_predicate_expression_rejects_noncanonical_casilla_id_token() -> None:
    """Predicate casilla references fail instead of reading malformed ids as absent zeroes."""
    values: dict[CasillaId, Decimal] = {_CASILLA_01: Decimal("1000")}

    with pytest.raises(ModeloError) as raised:
        evaluate_predicate_expression('all_nonzero(["01", "bad key"])', values, _workflow_profile())

    # The refusal carries the offending token as a machine fact; the text is
    # catalogue-rendered, so there is no sentence to match on.
    assert raised.value.context is not None
    assert raised.value.context["casilla_id_canonical"] is False


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
    assert findings[0].message_locale_key == "application.modelo.findings.cross_casilla_invariant_violated"
    assert dict(findings[0].message_facts) == {"predicate_id": "modelo-130-c15-cap-by-c14"}


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


def test_at_most_one_positive_blocks_only_multiple_positive_casillas() -> None:
    """at_most_one_positive treats absent, zero, and negative values as non-positive."""

    expression = 'at_most_one_positive(["01", "02", "07"])'
    allowed = _casilla_values((_CASILLA_01, "1200"), (_CASILLA_02, "0"), (_CASILLA_07, "-50"))
    violating = _casilla_values((_CASILLA_01, "1200"), (_CASILLA_02, "1"), (_CASILLA_07, "0"))

    assert evaluate_predicate_expression(expression, allowed, _workflow_profile()) is True
    assert evaluate_predicate_expression(expression, violating, _workflow_profile()) is False


def test_at_most_one_positive_emits_blocking_rule_finding() -> None:
    """A violated at_most_one_positive predicate produces a BLOCKING_RULE finding."""

    predicate = VerificationPredicateDefinition(
        predicate_id="test-at-most-one-positive",
        legal_refs=("ley-27-2014:art-40-3",),
        expression='at_most_one_positive(["01", "02"])',
        finding_kind="BLOCKING_RULE",
    )
    values = _casilla_values((_CASILLA_01, "1200"), (_CASILLA_02, "800"))

    findings = evaluate_verification_predicates((predicate,), values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert findings[0].message_locale_key == "application.modelo.findings.cross_casilla_invariant_violated"
    assert dict(findings[0].message_facts) == {"predicate_id": "test-at-most-one-positive"}


# ---------------------------------------------------------------------------
# contract: roll_forward_balances carry-forward continuity predicate (IS-2)
#
# The Modelo 200 BIN closing-stock roll-forward:
#   00671 (closing total pendiente) == 00670 (opening, bound)
#                                       − DP200014:00547 (applied)
#                                       + max(0, −DP200014:00552) (BIN generated)
# Expected values are derived from that AEAT roll-forward rule, NOT from the
# predicate formula under test.
# ---------------------------------------------------------------------------

_BIN_ROLL_FORWARD = 'roll_forward_balances(["00671", "00670", "DP200014:00547", "DP200014:00552"])'


def test_roll_forward_balances_core_cases() -> None:
    """The BIN roll-forward predicate distinguishes continuous filings from dropped stock."""
    cases = (
        (
            "reconciles",
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
            "dropped-closing",
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
            "legitimate-zero-closing",
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
            "generated-loss-added",
            _casilla_values(
                (_M200_BIN_OPEN_CASILLA, "5000"),
                (_M200_BIN_APPLIED_CASILLA, "2000"),
                (_M200_BIN_GENERATED_CASILLA, "-4000"),
                (_M200_BIN_CLOSING_CASILLA, "7000"),
            ),
            True,
            False,
        ),
    )

    for case_id, values, predicate_holds, advisory_fires in cases:
        assert evaluate_predicate_expression(_BIN_ROLL_FORWARD, values, _workflow_profile()) is predicate_holds, case_id
        assert evaluate_advisory_predicate_fires(_BIN_ROLL_FORWARD, values) is advisory_fires, case_id


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


def test_predicate_implies_nonzero_cases() -> None:
    """implies_nonzero engages only for strictly-positive antecedents and treats absent consequents as zero."""
    cases = (
        ("antecedent-zero", _casilla_values((_CASILLA_01, "0"), (_CASILLA_07, "0")), True),
        ("antecedent-negative", _casilla_values((_CASILLA_01, "-100"), (_CASILLA_07, "0")), True),
        ("both-positive", _casilla_values((_CASILLA_01, "500"), (_CASILLA_07, "200")), True),
        ("positive-antecedent-zero-consequent", _casilla_values((_CASILLA_01, "500"), (_CASILLA_07, "0")), False),
        ("positive-antecedent-absent-consequent", _casilla_values((_CASILLA_01, "500")), False),
    )

    for case_id, values, expected in cases:
        assert evaluate_predicate_expression(_IMPLIES_NONZERO_C01_C07, values, _workflow_profile()) is expected, case_id


# ---------------------------------------------------------------------------
# casilla_equals_implies_nonzero — categorical-conditional material
# implication; the antecedent is a TEXT casilla's operator-entered raw
# value (read from a separate text_values mapping), not the Decimal
# casilla_values projection. ADVISORY-only (the m210 categorical-conditional
# predicate decision); authored for the M210 IRNR
# inmobiliaria branch (tipo_renta == "inmobiliaria" implies a non-zero
# base_imponible), the no-silent-under-declaration shape implies_nonzero
# cannot express because its trigger is a categorical equality.
# ---------------------------------------------------------------------------

_CASILLA_EQUALS_IMPLIES_NONZERO = 'casilla_equals_implies_nonzero(["01", "literal-value", "07"])'


def test_casilla_equals_implies_nonzero_fires_cases() -> None:
    """The advisory fires only when the antecedent text value equals the literal AND the consequent is zero."""
    cases = (
        (
            "antecedent-matches-consequent-zero-fires",
            _casilla_values((_CASILLA_07, "0")),
            {_CASILLA_01: "literal-value"},
            True,
        ),
        (
            "antecedent-matches-consequent-nonzero-holds",
            _casilla_values((_CASILLA_07, "500")),
            {_CASILLA_01: "literal-value"},
            False,
        ),
        (
            "antecedent-differs-holds",
            _casilla_values((_CASILLA_07, "0")),
            {_CASILLA_01: "other-value"},
            False,
        ),
        (
            "antecedent-absent-holds",
            _casilla_values((_CASILLA_07, "0")),
            {},
            False,
        ),
    )

    for case_id, casilla_values, text_values, expected in cases:
        assert (
            evaluate_advisory_predicate_fires(_CASILLA_EQUALS_IMPLIES_NONZERO, casilla_values, text_values) is expected
        ), case_id


def test_casilla_equals_implies_nonzero_defaults_text_values_to_empty() -> None:
    """Callers that omit text_values (every pre-existing call site) never fire this operator."""
    values: dict[CasillaId, Decimal] = {_CASILLA_07: Decimal("0")}
    assert evaluate_advisory_predicate_fires(_CASILLA_EQUALS_IMPLIES_NONZERO, values) is False


def test_casilla_equals_implies_nonzero_bad_arity_does_not_fire() -> None:
    """A malformed arity reads as holding and never fires (ADVISORY-only, defensive default)."""
    expr = 'casilla_equals_implies_nonzero(["01", "07"])'  # two tokens; needs three
    values: dict[CasillaId, Decimal] = {_CASILLA_07: Decimal("0")}
    text_values = {_CASILLA_01: "literal-value"}
    assert evaluate_advisory_predicate_fires(expr, values, text_values) is False


def test_casilla_equals_implies_nonzero_is_advisory_only_no_blocking_branch() -> None:
    """The operator has no BLOCKING_RULE branch; it trivially holds via the unmatched-expression default."""
    values: dict[CasillaId, Decimal] = {_CASILLA_07: Decimal("0")}
    assert evaluate_predicate_expression(_CASILLA_EQUALS_IMPLIES_NONZERO, values, _workflow_profile()) is True


def test_casilla_equals_implies_nonzero_emits_advisory_finding_via_evaluate_verification_predicates() -> None:
    """The full evaluate_verification_predicates entry point threads text_values into the ADVISORY branch."""
    predicate = VerificationPredicateDefinition(
        predicate_id="test-categorical-conditional-invariant",
        legal_refs=("ley-35-2006:art-99",),
        expression=_CASILLA_EQUALS_IMPLIES_NONZERO,
        finding_kind="ADVISORY",
    )
    values: dict[CasillaId, Decimal] = {_CASILLA_07: Decimal("0")}
    text_values = {_CASILLA_01: "literal-value"}

    findings = evaluate_verification_predicates((predicate,), values, _workflow_profile(), text_values)
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert "ley-35-2006:art-99" in findings[0].legal_refs

    # When the antecedent text value does not match, no finding is produced.
    assert evaluate_verification_predicates((predicate,), values, _workflow_profile(), {}) == []


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
    assert findings[0].message_locale_key == "application.modelo.findings.cross_casilla_invariant_violated"
    assert dict(findings[0].message_facts) == {"predicate_id": "test-invariant"}


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


def _shipped_m100_m200_predicates(
    *,
    operator: VerificationPredicateOperator,
    finding_kind: str,
) -> tuple[tuple[VerificationPredicateDefinition, ParsedVerificationPredicate], ...]:
    matches: list[tuple[VerificationPredicateDefinition, ParsedVerificationPredicate]] = []
    for modelo in (Modelo.M100, Modelo.M200):
        validated = bundled_authority().validate_modelo(modelo.value)
        for revision in validated.revisions.values():
            for predicate in revision.verification_predicates:
                parsed = parse_verification_predicate_expression(predicate.expression)
                if parsed is not None and parsed.operator is operator and predicate.finding_kind == finding_kind:
                    matches.append((predicate, parsed))
    return tuple(matches)


def test_shipped_m100_m200_cap_predicates_allow_the_ceiling_and_refuse_an_overage() -> None:
    """Every loaded M100/M200 cap keeps its equality boundary and blocking finding."""
    predicates = _shipped_m100_m200_predicates(
        operator=VerificationPredicateOperator.CAP_LE_WHEN_POSITIVE,
        finding_kind="BLOCKING_RULE",
    )
    assert predicates
    unit = Decimal("1")

    for predicate, parsed in predicates:
        limited, ceiling = (
            validated_casilla_id(token, surface="verification predicate substance test") for token in parsed.casilla_ids
        )
        assert evaluate_verification_predicates((predicate,), {limited: unit, ceiling: unit}, _workflow_profile()) == []
        findings = evaluate_verification_predicates(
            (predicate,),
            {limited: unit + unit, ceiling: unit},
            _workflow_profile(),
        )
        assert tuple(dict(finding.message_facts)["predicate_id"] for finding in findings) == (predicate.predicate_id,)


def test_shipped_m100_m200_advisory_implications_fire_only_for_a_positive_missing_consequent() -> None:
    """Every loaded M100/M200 implication stays an advisory in its active direction."""
    predicates = _shipped_m100_m200_predicates(
        operator=VerificationPredicateOperator.IMPLIES_NONZERO,
        finding_kind="ADVISORY",
    )
    assert predicates
    unit = Decimal("1")

    for predicate, parsed in predicates:
        antecedent, consequent = (
            validated_casilla_id(token, surface="verification predicate substance test") for token in parsed.casilla_ids
        )
        findings = evaluate_verification_predicates(
            (predicate,),
            {antecedent: unit, consequent: Decimal("0")},
            _workflow_profile(),
        )
        assert tuple(dict(finding.message_facts)["predicate_id"] for finding in findings) == (predicate.predicate_id,)
        assert (
            evaluate_verification_predicates(
                (predicate,),
                {antecedent: unit, consequent: unit},
                _workflow_profile(),
            )
            == []
        )
        assert (
            evaluate_verification_predicates(
                (predicate,),
                {antecedent: Decimal("0"), consequent: Decimal("0")},
                _workflow_profile(),
            )
            == []
        )
