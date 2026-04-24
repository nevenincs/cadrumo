"""Unit tests for :mod:`aeat.filing.reconciliation._tolerance`.

Pins the ``Decimal("0.01")`` invariant so any contributor nudging the
constant without also nudging :data:`aeat.verification._verify._DEFAULT_TOLERANCE`
fails the suite immediately. The duplication is deliberate (see
the module docstring); the test backstop catches accidental drift.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ...verification._verify import _DEFAULT_TOLERANCE as VERIFICATION_TOLERANCE
from ._tolerance import RECONCILIATION_TOLERANCE

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def test_tolerance_value_is_one_cent() -> None:
    assert Decimal("0.01") == RECONCILIATION_TOLERANCE


def test_tolerance_is_a_decimal_instance() -> None:
    assert isinstance(RECONCILIATION_TOLERANCE, Decimal)


def test_tolerance_matches_verification_tolerance_by_value() -> None:
    """Local-vs-AEAT tolerance must agree with the local PDF-vs-engine tolerance."""
    assert RECONCILIATION_TOLERANCE == VERIFICATION_TOLERANCE
