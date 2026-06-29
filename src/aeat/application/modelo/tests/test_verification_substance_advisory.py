"""Verification advisory predicate substance tests."""

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
