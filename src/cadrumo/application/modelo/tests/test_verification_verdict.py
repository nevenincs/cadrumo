"""A check that finds the calculation out of date is blocked, not merely incomplete.

Missing required values alone leave a check incomplete: entering them releases
it. A calculation the filer's records changed under must be run again first,
so a stale calculation found beside missing values still makes the check
blocked.
"""

from __future__ import annotations

import pytest

from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ..verification_actions import _classify_verification_outcome

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MISSING_BOX = "01"


def _missing() -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=_MISSING_BOX,
        message_locale_key="application.modelo.findings.missing_required_casilla",
        message_facts={"casilla_id": _MISSING_BOX},
        legal_refs=("rd-439-2007:art-110",),
    )


def _stale() -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.ledger_snapshot_drift",
        legal_refs=("ley-58-2003:art-119",),
    )


def test_a_stale_calculation_beside_a_missing_required_box_is_blocked() -> None:
    verdict = _classify_verification_outcome(findings=[_missing(), _stale()], missing_required=[_MISSING_BOX])

    assert verdict == (VerificationCompletenessStatus.BLOCKED, False)


def test_a_stale_calculation_alone_is_blocked() -> None:
    assert _classify_verification_outcome(findings=[_stale()], missing_required=[]) == (
        VerificationCompletenessStatus.BLOCKED,
        False,
    )


def test_a_missing_required_box_alone_is_incomplete() -> None:
    """Teeth for the rule above: only what entering values cannot release makes the check blocked."""
    verdict = _classify_verification_outcome(findings=[_missing()], missing_required=[_MISSING_BOX])

    assert verdict == (VerificationCompletenessStatus.INCOMPLETE, False)
