"""Behaviour regressions for the LIVA art. 103.Dos.2 mandatory-especial advisory.

See Also:
    :func:`~application.calculations.build_prorrata_especial_mandatory_advisory`
        The settlement-time +10% advisory builder under test.
    :func:`~domain.iva.is_especial_mandatory`
        The pure LIVA art. 103.Dos.2 gate the builder consumes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.json_contract import NoticeSeverity
from .. import build_prorrata_especial_mandatory_advisory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_advisory_fires_when_general_exceeds_especial_by_more_than_ten_percent() -> None:
    """A >10% general-over-especial spread makes especial obligatory (art. 103.Dos.2)."""
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("111.00"),
        deduction_under_especial=Decimal("100.00"),
        ejercicio=2026,
    )

    assert notice is not None
    # Non-blocking: a warning notice, never a raised refusal.
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.code == "modelo.work.calculate.prorrata_especial_obligatoria"
    assert notice.context is not None
    # Both compared totals ride on the notice context.
    assert notice.context["deduction_under_general"] == "111.00"
    assert notice.context["deduction_under_especial"] == "100.00"
    assert notice.context["ejercicio"] == "2026"
    assert notice.context["regime"] == "especial"
    assert notice.context["legal_refs"] == "ley-37-1992:art-103"


def test_advisory_silent_at_exactly_ten_percent_boundary() -> None:
    """Exactly +10% does not trip the strict art. 103.Dos.2 threshold (no noise)."""
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("110.00"),
        deduction_under_especial=Decimal("100.00"),
        ejercicio=2026,
    )

    assert notice is None


def test_advisory_silent_when_general_does_not_exceed_especial() -> None:
    """A general deduction at or below the especial deduction never fires."""
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("95.00"),
        deduction_under_especial=Decimal("100.00"),
        ejercicio=2026,
    )

    assert notice is None


def test_advisory_fires_when_especial_is_zero_and_general_is_positive() -> None:
    """A zero especial deduction with any positive general deduction is obligatory."""
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("0.01"),
        deduction_under_especial=Decimal("0.00"),
        ejercicio=2026,
    )

    assert notice is not None
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.context is not None
    assert notice.context["deduction_under_especial"] == "0.00"
