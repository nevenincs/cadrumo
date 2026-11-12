"""A disclosed limitation is a warning marker that leaves an ordinary finding's identity untouched."""

from __future__ import annotations

import pytest

from ..verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_KEY = "application.modelo.findings.trabajo_deduction_not_computed"


def _finding(*, severity: ModeloVerificationFindingSeverity, disclosed: bool = False) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=severity,
        message_locale_key=_KEY,
        legal_refs=("ley-35-2006:art-19",),
        disclosed_limitation=disclosed,
    )


def test_an_ordinary_finding_is_unmarked_and_serializes_without_the_field() -> None:
    ordinary = _finding(severity=ModeloVerificationFindingSeverity.WARNING)
    assert ordinary.disclosed_limitation is False
    assert "disclosed_limitation" not in ordinary.model_dump(mode="json")


def test_a_marked_finding_serializes_the_marker_and_round_trips() -> None:
    marked = _finding(severity=ModeloVerificationFindingSeverity.WARNING, disclosed=True)
    assert marked.model_dump(mode="json")["disclosed_limitation"] is True
    assert ModeloVerificationFinding.model_validate(marked.model_dump(mode="python")) == marked


def test_a_blocking_finding_cannot_be_a_disclosed_limitation() -> None:
    with pytest.raises(ValueError, match="never a blocking"):
        _finding(severity=ModeloVerificationFindingSeverity.BLOCKING, disclosed=True)
