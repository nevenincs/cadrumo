"""Public package surface tests for :mod:`aeat.core.parsing`."""

from __future__ import annotations

from datetime import date

import pytest

import aeat.core.parsing as parsing

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_public_parsing_surface_exposes_only_public_names() -> None:
    private_aliases = {
        "_parse_bool",
        "_parse_date",
        "_parse_ddmmyyyy_date",
        "_parse_iso8601_date",
    }

    assert private_aliases.isdisjoint(parsing.__all__)
    for name in private_aliases:
        assert not hasattr(parsing, name)


def test_public_date_parsers_delegate_to_canonical_implementations() -> None:
    assert parsing.parse_iso8601_date("2026-06-05") == date(2026, 6, 5)
    assert parsing.parse_ddmmyyyy_date("05/06/2026") == date(2026, 6, 5)


def test_public_bool_parser_remains_available() -> None:
    assert parsing.parse_bool("sí") is True
    assert parsing.parse_bool("no") is False
