"""Declaracion parser exception hierarchy tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    AeatError,
    DeclaracionParseError,
    PdfModeloImportError,
    TemplateNotDetectedError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_declaracion_errors_stay_on_core_exception_hierarchy() -> None:
    assert issubclass(DeclaracionParseError, PdfModeloImportError)
    assert issubclass(DeclaracionParseError, AeatError)
    assert issubclass(TemplateNotDetectedError, DeclaracionParseError)
