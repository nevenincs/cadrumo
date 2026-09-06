"""Tests for the printed-vs-derived IVA advisory cross-check."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..evidence_advisory import printed_iva_advisory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_no_advisory_without_evidence_or_derived() -> None:
    assert printed_iva_advisory(None, Decimal("21.00")) is None
    assert printed_iva_advisory("IVA 21,00", None) is None


def test_no_advisory_when_printed_matches_derived() -> None:
    assert printed_iva_advisory("Base 100,00 IVA 21,00 Total 121,00", Decimal("21.00")) is None


def test_advisory_fires_on_mismatch() -> None:
    advisory = printed_iva_advisory("Base 100,00 IVA 10,00 Total 110,00", Decimal("21.00"))
    assert advisory is not None
    assert "10.00" in advisory
    assert "21.00" in advisory
    assert "advisory only" in advisory


def test_parses_spanish_thousands_format() -> None:
    # 1.234,56 -> 1234.56; mismatch vs derived 21.00 -> advisory.
    advisory = printed_iva_advisory("IVA 1.234,56", Decimal("21.00"))
    assert advisory is not None
    assert "1234.56" in advisory


def test_parses_dot_decimal_format() -> None:
    advisory = printed_iva_advisory("IVA 10.50", Decimal("21.00"))

    assert advisory is not None
    assert "10.50" in advisory


def test_unparseable_or_absent_printed_iva_yields_no_advisory() -> None:
    assert printed_iva_advisory("no tax figures here", Decimal("21.00")) is None


def test_a_spanish_thousands_figure_is_refused_rather_than_truncated() -> None:
    """The regex must hand the coercer the whole token, not a well-formed prefix.

    A printed ``8.000`` was matched as ``8.00``, so the coercer -- which drops
    ``8.000`` precisely because the convention cannot be settled -- received an
    unambiguous eight euros and returned it. The advisory then reported "the
    attached evidence appears to print an IVA of 8.00" against a document
    printing 8.000: a thousandfold error inside the message whose whole job is
    catching errors, and one an operator has no way to see through.
    """
    assert printed_iva_advisory("IVA 8.000", Decimal("21.00")) is None


def test_a_thousands_figure_with_no_decimals_is_refused_at_any_magnitude() -> None:
    """Round thousands are ordinary on an invoice, so this is not an edge case."""
    assert printed_iva_advisory("IVA 1.500", Decimal("21.00")) is None
    assert printed_iva_advisory("IVA: 12.345.678", Decimal("21.00")) is None


def test_an_unsettleable_figure_is_silent_rather_than_reported_wrongly() -> None:
    """Silence is the honest answer when the printed figure cannot be read.

    The advisory exists to make an operator look again. Reporting a figure the
    parser is not sure of would make them look at the wrong thing, which is
    worse than not raising it: the derived value is authoritative either way,
    and a false alarm teaches them to dismiss the true ones.
    """
    assert printed_iva_advisory("IVA 8.000", Decimal("8000.00")) is None


def test_every_settleable_format_still_reaches_the_comparison() -> None:
    """The fix must not silence the formats that were working.

    A stricter pattern that refused real figures would close the advisory
    entirely while every test about refusals kept passing.
    """
    assert printed_iva_advisory("IVA 1.234,56", Decimal("21.00")) is not None
    assert printed_iva_advisory("IVA 10,00", Decimal("21.00")) is not None
    assert printed_iva_advisory("IVA 10.50", Decimal("21.00")) is not None
    assert printed_iva_advisory("IVA 8", Decimal("21.00")) is not None
