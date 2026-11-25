"""Boundary tests for the shared ISO-8601 date gate applied to CLI dates.

Exercises the real :func:`parse_iso_date` / :func:`parse_iso_date_str` /
:func:`parse_optional_iso_date_str` helpers in
:mod:`cadrumo.entrypoints.cli.common` — the single owned ISO gate every
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

from cadrumo.tests.english_locale_fixture import english_locale_fixture

__all__ = ["english_locale_fixture"]

from ..date_parsing import parse_iso_date, parse_iso_date_str, parse_optional_iso_date_str

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

# Non-ISO orderings that the gate MUST refuse for an ``invoice_date`` input.
# The compact and ISO week-date forms are what ``date.fromisoformat`` also admits.
_REJECTED = (
    "15/01/2026",
    "01-15-2026",
    "2026/01/15",
    "15-01-2026",
    "2026.01.15",
    "not-a-date",
    "",
    "20260115",
    "2026-W03-4",
    "2026W034",
)


def test_parse_iso_date_refuses_non_iso() -> None:
    for raw in _REJECTED:
        with pytest.raises(typer.BadParameter):
            parse_iso_date(raw, label="invoice-date")


def test_parse_iso_date_accepts_iso() -> None:
    assert parse_iso_date("2026-01-15", label="invoice-date") == date(2026, 1, 15)


def test_parse_iso_date_accepts_surrounding_whitespace() -> None:
    assert parse_iso_date("  2026-01-15  ", label="invoice-date") == date(2026, 1, 15)


def test_parse_iso_date_str_refuses_non_iso() -> None:
    for raw in _REJECTED:
        with pytest.raises(typer.BadParameter):
            parse_iso_date_str(raw, label="invoice-date")


def test_parse_iso_date_str_returns_canonical_string() -> None:
    assert parse_iso_date_str("2026-01-15", label="invoice-date") == "2026-01-15"


def test_parse_optional_iso_date_str_passes_through_none() -> None:
    assert parse_optional_iso_date_str(None, label="invoice-date") is None


def test_parse_optional_iso_date_str_validates_when_present() -> None:
    assert parse_optional_iso_date_str("2026-01-15", label="invoice-date") == "2026-01-15"
    with pytest.raises(typer.BadParameter):
        parse_optional_iso_date_str("15/01/2026", label="invoice-date")


def test_refusal_message_names_field_and_raw() -> None:
    with pytest.raises(typer.BadParameter) as excinfo:
        parse_iso_date("15/01/2026", label="invoice-date")
    message = excinfo.value.message
    assert "invoice-date" in message
    assert "15/01/2026" in message
