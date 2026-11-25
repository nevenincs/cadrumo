"""Parser boundary error-path tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..errors import DeclaracionParseError
from ..parser import parse_declaracion
from .parser_boundary_support import (
    MODELO_130_SYNTHETIC_FIXTURE,
    modelo_130_snapshot,
    specimen_period,
    write_declaration_pdf,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]


def test_parser_requires_a_known_registry_model_after_template_resolution(tmp_path: Path) -> None:
    pdf_path = tmp_path / "modelo-999.pdf"
    exercise = filing_year_envelope().horizon
    write_declaration_pdf(pdf_path, modelo="999", ejercicio=str(exercise), values={"01": Decimal("1.00")})

    with pytest.raises(DeclaracionParseError) as excinfo:
        parse_declaracion(
            pdf_path,
            modelo_override="999",
            año_override=exercise,
            period_override="1T",
        )
    assert excinfo.value.translated_message == "adapters.inbound.declaracion.errors.registry_snapshot_required"
    assert excinfo.value.context is not None
    assert excinfo.value.context.get("modelo") == "999"
    error = excinfo.value.context.get("error", "")
    assert isinstance(error, str)
    assert "is not present in the calculation registry" in error


def test_parser_contains_an_invalid_period_override_as_a_parse_failure() -> None:
    """A malformed caller override must not leak the core period family."""
    pdf_path = MODELO_130_SYNTHETIC_FIXTURE

    with pytest.raises(DeclaracionParseError) as excinfo:
        parse_declaracion(
            pdf_path,
            modelo_override="130",
            año_override=specimen_period(MODELO_130_SYNTHETIC_FIXTURE).filing_year,
            period_override="NOT-A-PERIOD",
            registry_snapshot=modelo_130_snapshot(),
        )

    assert excinfo.value.translated_message == "adapters.inbound.declaracion.errors.period_unresolved"
