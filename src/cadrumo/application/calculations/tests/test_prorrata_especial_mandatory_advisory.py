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
from ..prorrata_regularizacion import build_prorrata_especial_mandatory_advisory

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


def test_advisory_fires_at_exactly_ten_percent_boundary_from_2015() -> None:
    """Art. 103.Dos.2.º reads "exceda en un 10 por ciento o más", so the boundary itself is obligatory.

    110 against 100 is an excess of exactly ten percent. "O más" reaches the
    margin, so the advisory must fire. The paired below-margin case keeps the
    assertion from passing on a predicate that always fires.
    """
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("110.00"),
        deduction_under_especial=Decimal("100.00"),
        ejercicio=2026,
    )

    assert notice is not None
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.code == "modelo.work.calculate.prorrata_especial_obligatoria"
    assert notice.context is not None
    assert notice.context["margin_percentage"] == "10"
    assert notice.context["margin_inclusive"] == "true"

    assert (
        build_prorrata_especial_mandatory_advisory(
            deduction_under_general=Decimal("109.99"),
            deduction_under_especial=Decimal("100.00"),
            ejercicio=2026,
        )
        is None
    )


def test_advisory_applies_the_original_twenty_percent_margin_before_2015() -> None:
    """Before Ley 28/2014 the margin was twenty percent and carried no "o más".

    The same amounts that are obligatory for a 2026 ejercicio are not for a
    2014 one, and the pre-2015 margin only trips once passed.
    """
    assert (
        build_prorrata_especial_mandatory_advisory(
            deduction_under_general=Decimal("110.00"),
            deduction_under_especial=Decimal("100.00"),
            ejercicio=2014,
        )
        is None
    )
    assert (
        build_prorrata_especial_mandatory_advisory(
            deduction_under_general=Decimal("120.00"),
            deduction_under_especial=Decimal("100.00"),
            ejercicio=2014,
        )
        is None
    )
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("120.01"),
        deduction_under_especial=Decimal("100.00"),
        ejercicio=2014,
    )
    assert notice is not None
    assert notice.context is not None
    # The envelope reports the margin the predicate actually applied. The
    # original redaction's twenty percent is not inclusive, so a reader can
    # tell which text produced the obligation.
    assert notice.context["margin_percentage"] == "20"
    assert notice.context["margin_inclusive"] == "false"


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
