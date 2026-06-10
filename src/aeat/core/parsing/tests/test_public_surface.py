"""Public package surface tests for :mod:`aeat.core.parsing`."""

from __future__ import annotations

from datetime import date
from importlib import import_module

import pytest

from .. import __all__ as parsing_all
from .. import parse_bool, parse_ddmmyyyy_date, parse_iso8601_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

assert __package__ is not None, "test module must be runnable from a package"
_PARSING_PACKAGE = import_module(__package__.rsplit(".", 1)[0])


def test_public_parsing_surface_exposes_only_public_names() -> None:
    private_aliases = {
        "_parse_bool",
        "_parse_date",
        "_parse_ddmmyyyy_date",
        "_parse_iso8601_date",
    }

    assert private_aliases.isdisjoint(parsing_all)
    for name in private_aliases:
        assert not hasattr(_PARSING_PACKAGE, name)


def test_public_date_parsers_delegate_to_canonical_implementations() -> None:
    assert parse_iso8601_date("2026-06-05") == date(2026, 6, 5)
    assert parse_ddmmyyyy_date("05/06/2026") == date(2026, 6, 5)


def test_public_bool_parser_remains_available() -> None:
    assert parse_bool("sí") is True
    assert parse_bool("no") is False
