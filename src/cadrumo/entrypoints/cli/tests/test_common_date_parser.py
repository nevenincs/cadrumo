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

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.tests.english_locale_fixture import english_locale_fixture

__all__ = ["english_locale_fixture"]

from ..date_parsing import parse_iso_date, parse_iso_date_str, parse_optional_iso_date_str

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_ISO = f"{_YEAR}-01-15"

# Non-ISO orderings that the gate MUST refuse for an ``invoice_date`` input.
# The compact and ISO week-date forms are what ``date.fromisoformat`` also admits.
_REJECTED = (
    f"15/01/{_YEAR}",
    f"01-15-{_YEAR}",
    f"{_YEAR}/01/15",
    f"15-01-{_YEAR}",
    f"{_YEAR}.01.15",
    "not-a-date",
    "",
    f"{_YEAR}0115",
    f"{_YEAR}-W03-4",
    f"{_YEAR}W034",
)


def test_parse_iso_date_refuses_non_iso() -> None:
    for raw in _REJECTED:
        with pytest.raises(typer.BadParameter):
            parse_iso_date(raw, label="invoice-date")


def test_parse_iso_date_accepts_iso() -> None:
    assert parse_iso_date(_ISO, label="invoice-date") == date(_YEAR, 1, 15)


def test_parse_iso_date_accepts_surrounding_whitespace() -> None:
    assert parse_iso_date(f"  {_ISO}  ", label="invoice-date") == date(_YEAR, 1, 15)


def test_parse_iso_date_str_refuses_non_iso() -> None:
    for raw in _REJECTED:
        with pytest.raises(typer.BadParameter):
            parse_iso_date_str(raw, label="invoice-date")


def test_parse_iso_date_str_returns_canonical_string() -> None:
    assert parse_iso_date_str(_ISO, label="invoice-date") == _ISO


def test_parse_optional_iso_date_str_passes_through_none() -> None:
    assert parse_optional_iso_date_str(None, label="invoice-date") is None


def test_parse_optional_iso_date_str_validates_when_present() -> None:
    assert parse_optional_iso_date_str(_ISO, label="invoice-date") == _ISO
    with pytest.raises(typer.BadParameter):
        parse_optional_iso_date_str(f"15/01/{_YEAR}", label="invoice-date")


def test_refusal_message_names_field_and_raw() -> None:
    with pytest.raises(typer.BadParameter) as excinfo:
        parse_iso_date(f"15/01/{_YEAR}", label="invoice-date")
    message = excinfo.value.message
    assert "invoice-date" in message
    assert f"15/01/{_YEAR}" in message
