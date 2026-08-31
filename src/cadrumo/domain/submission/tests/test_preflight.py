"""Preflight gate-2: the error-severity findings gate.

No dedicated test file existed for :class:`Preflight` before this one.
Exercises the four-gate validator with hand-rolled Protocol-conforming
classes, per this package's own documented testing philosophy (``_protocols.py``:
"no mocks, no patches"). Gates 3 and 4 are skipped in every test here since
gate-2 -- the subject of this file -- runs before either.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core.auth_provider import AuthProviderDescription
from ....core.errors.severity import BaseSeverity
from ....core.period import Period
from .._preflight import Preflight
from .._protocols import ModeloDraftStatus, ModeloFinding, ModeloFindingLike
from ..errors import SubmissionPreflightError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _UnusedDeadlineChecker:
    """A ``DeadlineWindowChecker`` conformer that must never be called (gate-3 is skipped)."""

    def is_window_open(self, modelo: str, period: Period, today: date) -> bool:
        raise AssertionError("gate-3 must not run when skip_deadline_window=True")


class _UnusedAuthProvider:
    """An ``AuthProviderProbe`` conformer that must never be called (gate-4 is skipped)."""

    @property
    def kind(self) -> str:
        return "unused"

    def describe(self) -> AuthProviderDescription:
        raise AssertionError("gate-4 must not run when skip_auth_readiness=True")


class _DraftWithFindings:
    """A ``ModeloDraftLike`` conformer carrying an arbitrary findings tuple."""

    def __init__(self, findings: tuple[ModeloFindingLike, ...]) -> None:
        self._findings = findings

    @property
    def draft_id(self) -> str:
        return "test-draft"

    @property
    def modelo(self) -> str:
        return "100"

    @property
    def period(self) -> Period:
        return Period.from_year_and_code(2025, "0A")

    @property
    def profile_tax_id(self) -> str:
        return "00000000T"

    @property
    def status(self) -> ModeloDraftStatus:
        return ModeloDraftStatus.APROBADO

    @property
    def values(self) -> tuple[object, ...]:
        return ()

    @property
    def findings(self) -> tuple[ModeloFindingLike, ...]:
        return self._findings


def _preflight() -> Preflight:
    return Preflight(deadline_checker=_UnusedDeadlineChecker(), auth_provider=_UnusedAuthProvider())


def _check(draft: _DraftWithFindings) -> None:
    _preflight().check(draft, today=date(2025, 6, 1), skip_deadline_window=True, skip_auth_readiness=True)


def test_a_clean_draft_with_only_non_error_findings_passes_gate_2() -> None:
    """The legitimate path: warning/info findings never block submission."""
    draft = _DraftWithFindings(
        findings=(
            ModeloFinding(severity=BaseSeverity.WARNING, message="a warning"),
            ModeloFinding(severity=BaseSeverity.INFO, message="an info note"),
        ),
    )
    _check(draft)  # must not raise


def test_a_real_error_severity_finding_blocks_gate_2() -> None:
    """The legitimate path: a genuine ERROR-severity finding does block."""
    draft = _DraftWithFindings(findings=(ModeloFinding(severity=BaseSeverity.ERROR, message="a real error"),))
    with pytest.raises(SubmissionPreflightError, match="error-severity findings"):
        _check(draft)


def test_a_dropped_severity_field_is_refused_not_silently_treated_as_clean() -> None:
    """The bite proof: a finding that has genuinely lost its ``severity`` field
    must fail loud, never silently pass gate-2 as if the draft were clean.

    Before the fix, ``getattr(f, "severity", None)`` on a drifted finding
    returned ``None`` -> ``_enum_value(None)`` -> ``""`` -> ``"" == "error"``
    is ``False`` -> the finding is silently excluded from ``error_findings``
    -> gate-2 passes SILENTLY, with no exception at all -- exactly the same
    outcome as :func:`test_a_clean_draft_with_only_non_error_findings_passes_gate_2`'s
    genuinely clean draft. The old code could not tell "no errors" from
    "the read broke on an error". This drops ``severity`` straight off a
    real, otherwise-valid ``ModeloFinding`` instance's own ``__dict__`` (not
    a look-alike stand-in) and asserts on the read failing with a
    cause-unique ``AttributeError`` naming the field -- never on
    ``SubmissionPreflightError``, which is the DIFFERENT, correct-behavior
    exception a legitimate error finding raises in the test above. The two
    must stay distinguishable.
    """
    drifted = ModeloFinding(severity=BaseSeverity.ERROR, message="a real error, drifted selector")
    del drifted.__dict__["severity"]
    draft = _DraftWithFindings(findings=(drifted,))

    with pytest.raises(AttributeError, match="severity"):
        _check(draft)
