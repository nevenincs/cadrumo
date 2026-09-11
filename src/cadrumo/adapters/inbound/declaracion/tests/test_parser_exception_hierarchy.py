"""Declaracion parser exception hierarchy tests."""

from __future__ import annotations

import pytest

from .....core.errors.hierarchy import CadrumoError
from .....domain.justificante.errors import PdfModeloImportError
from ..errors import DeclaracionParseError, TemplateNotDetectedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_declaracion_errors_stay_on_core_exception_hierarchy() -> None:
    assert issubclass(DeclaracionParseError, PdfModeloImportError)
    assert issubclass(DeclaracionParseError, CadrumoError)
    assert issubclass(TemplateNotDetectedError, DeclaracionParseError)
