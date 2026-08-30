"""Verification advisory predicate substance tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import CasillaId
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.modelos.verification_report import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ....domain.modelos.errors import ModeloError
from .._verification_actions import (
    evaluate_advisory_predicate_fires,
    evaluate_verification_predicates,
)
from ._verification_substance_support import (
    _CASILLA_00501,
    _CASILLA_01,
    _CASILLA_06,
    _M200_BIN_GENERATED_CASILLA,
    _casilla_values,
    _workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# ---------------------------------------------------------------------------
# Advisory predicate unit tests
# ---------------------------------------------------------------------------

_ADVISORY_RATIO_GE = 'advisory_when_ratio_ge(["00501", "DP200014:00552", "0.70"])'
_M130_ART109_PROFILE_ADVISORY = 'profile_flag_enabled("art109_activity_income_withholding_ge_70pct")'
_AdvisoryPredicateCase = tuple[str, dict[CasillaId, Decimal], bool]

_ADVISORY_RATIO_GE_CASES: tuple[_AdvisoryPredicateCase, ...] = (
    ("exact-threshold", _casilla_values((_CASILLA_00501, "10500"), (_M200_BIN_GENERATED_CASILLA, "15000")), True),
    ("above-threshold", _casilla_values((_CASILLA_00501, "12000"), (_M200_BIN_GENERATED_CASILLA, "15000")), True),
    ("below-threshold", _casilla_values((_CASILLA_00501, "9000"), (_M200_BIN_GENERATED_CASILLA, "15000")), False),
    ("zero-denominator", _casilla_values((_CASILLA_00501, "5000"), (_M200_BIN_GENERATED_CASILLA, "0")), False),
)

_ADVISORY_IMPLIES_M200_BASE = 'implies_nonzero(["00501", "DP200014:00552"])'
_ADVISORY_IMPLIES_M200_BASE_CASES: tuple[_AdvisoryPredicateCase, ...] = (
    (
        "positive-result-zero-base",
        _casilla_values((_CASILLA_00501, "140000"), (_M200_BIN_GENERATED_CASILLA, "0")),
        True,
    ),
    ("loss-result", _casilla_values((_CASILLA_00501, "-5000"), (_M200_BIN_GENERATED_CASILLA, "0")), False),
    ("zero-result", _casilla_values((_CASILLA_00501, "0"), (_M200_BIN_GENERATED_CASILLA, "0")), False),
    (
        "determined-base",
        _casilla_values((_CASILLA_00501, "140000"), (_M200_BIN_GENERATED_CASILLA, "140000")),
        False,
    ),
)


def test_advisory_when_ratio_ge_cases() -> None:
    """advisory_when_ratio_ge fires at or above the threshold and stays silent below it or with no denominator."""
    for case_label, values, expected in _ADVISORY_RATIO_GE_CASES:
        assert evaluate_advisory_predicate_fires(_ADVISORY_RATIO_GE, values) is expected, case_label


def test_advisory_when_ratio_ge_rejects_noncanonical_casilla_id_token() -> None:
    values: dict[CasillaId, Decimal] = {
        _CASILLA_00501: Decimal("100"),
        _M200_BIN_GENERATED_CASILLA: Decimal("100"),
    }

    with pytest.raises(ModeloError):
        evaluate_advisory_predicate_fires('advisory_when_ratio_ge(["00501", "bad key", "0.70"])', values)


def test_advisory_implies_nonzero_cases() -> None:
    """The M200 advisory fires only when positive resultado contable has no determined base."""
    for case_label, values, expected in _ADVISORY_IMPLIES_M200_BASE_CASES:
        assert evaluate_advisory_predicate_fires(_ADVISORY_IMPLIES_M200_BASE, values) is expected, case_label


def test_art109_profile_advisory_emits_warning_when_profile_flag_is_enabled() -> None:
    """Art. 109 ADVISORY reads the profile coverage flag, not a casilla ratio."""
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-art109-exencion-alta-retencion",
        legal_refs=("rd-439-2007:art-109",),
        expression=_M130_ART109_PROFILE_ADVISORY,
        finding_kind="ADVISORY",
    )
    profile = _workflow_profile().model_copy(update={"art109_activity_income_withholding_ge_70pct": True})
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_06: Decimal("0"),
        _CASILLA_01: Decimal("15000"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, profile)

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "rd-439-2007:art-109" in findings[0].legal_refs


def test_art109_profile_advisory_ignores_professional_only_profile_flag() -> None:
    """The professional-only compatibility field is not the full Art. 109 fact."""
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-art109-exencion-alta-retencion",
        legal_refs=("rd-439-2007:art-109",),
        expression=_M130_ART109_PROFILE_ADVISORY,
        finding_kind="ADVISORY",
    )
    profile = _workflow_profile().model_copy(update={"professional_income_withholding_ge_70pct": True})
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_06: Decimal("0"),
        _CASILLA_01: Decimal("15000"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, profile)

    assert findings == []


def test_art109_profile_advisory_ignores_high_retention_amount_ratio_when_profile_flag_is_disabled() -> None:
    """A high casilla 06 amount alone is not the Art. 109 income-coverage fact."""
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-art109-exencion-alta-retencion",
        legal_refs=("rd-439-2007:art-109",),
        expression=_M130_ART109_PROFILE_ADVISORY,
        finding_kind="ADVISORY",
    )
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_06: Decimal("10500"),
        _CASILLA_01: Decimal("15000"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert findings == []


# ---------------------------------------------------------------------------
# contract: M130 all-zero regression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("threshold", "hazard"),
    (
        pytest.param("NaN", "builds without raising, then raises InvalidOperation at the comparison", id="nan"),
        pytest.param("Infinity", "compares False to every ratio, silencing the advisory", id="infinity"),
        pytest.param("-Infinity", "compares True to every ratio, firing the advisory always", id="negative-infinity"),
    ),
)
def test_advisory_when_ratio_ge_refuses_a_non_finite_threshold(threshold: str, hazard: str) -> None:
    """A non-finite threshold must not fire and must not escape as an exception.

    Registry build refuses these, so a validated registry cannot reach here with
    one; this is the defence in depth for anything that bypasses that gate. The
    ``NaN`` case is the one that used to escape: the evaluator's ``try`` wrapped
    only the ``Decimal`` construction, which does NOT raise for ``NaN``, while
    the comparison that does raise sat outside it. Not firing is the honest
    reading of a threshold that cannot be evaluated.
    """
    values = _casilla_values((_CASILLA_00501, "10500"), (_M200_BIN_GENERATED_CASILLA, "15000"))
    expression = f'advisory_when_ratio_ge(["00501", "DP200014:00552", "{threshold}"])'

    assert evaluate_advisory_predicate_fires(expression, values) is False, hazard
