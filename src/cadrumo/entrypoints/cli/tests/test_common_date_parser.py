"""Boundary tests for the shared ISO-8601 date gate applied to CLI dates.

Exercises the real :func:`_parse_iso_date` / :func:`_parse_iso_date_str` /
:func:`_parse_optional_iso_date_str` helpers in
:mod:`cadrumo.entrypoints.cli._common` — the single owned ISO gate every
date-typed CLI input (including ``--invoice-date`` on the business-invoice and
evidence commands, research F5) now routes through. No mocks, no skips: each
case drives ``date.fromisoformat`` and asserts a concrete ``date`` or a real
``typer.BadParameter`` refusal.

The canonical gate refuses every non-ISO ordering by construction, so the
DD/MM-vs-MM/DD ambiguity never arises.
"""

from __future__ import annotations

from datetime import date

import pytest
import typer

from ._english_locale_fixture import english_locale_fixture

__all__ = ["english_locale_fixture"]

from .._date_parsing import _parse_iso_date, _parse_iso_date_str, _parse_optional_iso_date_str

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

# Non-ISO orderings that the gate MUST refuse for an ``invoice_date`` input.
_REJECTED = ("15/01/2026", "01-15-2026", "2026/01/15", "15-01-2026", "2026.01.15", "not-a-date", "")


def test_parse_iso_date_refuses_non_iso() -> None:
    for raw in _REJECTED:
        with pytest.raises(typer.BadParameter):
            _parse_iso_date(raw, label="invoice-date")


def test_parse_iso_date_accepts_iso() -> None:
    assert _parse_iso_date("2026-01-15", label="invoice-date") == date(2026, 1, 15)


def test_parse_iso_date_accepts_surrounding_whitespace() -> None:
    assert _parse_iso_date("  2026-01-15  ", label="invoice-date") == date(2026, 1, 15)


def test_parse_iso_date_str_refuses_non_iso() -> None:
    for raw in _REJECTED:
        with pytest.raises(typer.BadParameter):
            _parse_iso_date_str(raw, label="invoice-date")


def test_parse_iso_date_str_returns_canonical_string() -> None:
    assert _parse_iso_date_str("2026-01-15", label="invoice-date") == "2026-01-15"


def test_parse_optional_iso_date_str_passes_through_none() -> None:
    assert _parse_optional_iso_date_str(None, label="invoice-date") is None


def test_parse_optional_iso_date_str_validates_when_present() -> None:
    assert _parse_optional_iso_date_str("2026-01-15", label="invoice-date") == "2026-01-15"
    with pytest.raises(typer.BadParameter):
        _parse_optional_iso_date_str("15/01/2026", label="invoice-date")


def test_refusal_message_names_field_and_raw() -> None:
    with pytest.raises(typer.BadParameter) as excinfo:
        _parse_iso_date("15/01/2026", label="invoice-date")
    message = excinfo.value.message
    assert "invoice-date" in message
    assert "15/01/2026" in message
