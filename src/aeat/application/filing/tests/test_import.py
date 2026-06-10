"""Unit tests for :mod:`aeat.application.filing._import`.

Exercises :func:`aeat.application.filing.import_filing_from_justificante`
end-to-end against local justificante fixture PDFs under
``src/aeat/tests/fixtures/justificantes/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from ....domain.filing import ModeloImportError
from ....domain.justificante import JustificanteParseError
from ....tests import FIXTURES_DIR
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from .. import import_filing_from_justificante
from .._import import RegistryImportSchemaProvider
from ..runtime import RegistrySchemaProvider, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIXTURES = FIXTURES_DIR / "justificantes"


@pytest.fixture(scope="module")
def schema_provider() -> RegistrySchemaProvider:
    return build_runtime_schema_provider()


def test_runtime_schema_provider_exposes_imported_modelo_schema() -> None:
    collection = build_runtime_schema_provider().get_collection("130")

    casilla_19 = collection.get("19")
    assert casilla_19 is not None
    assert casilla_19.id == "19"


class TestImportFromJustificante:
    """End-to-end reconstruction from local fixture PDFs."""

    def test_modelo_130_justificante_only_import_requires_binding_data(
        self, schema_provider: RegistrySchemaProvider
    ) -> None:
        pdf = _FIXTURES / "modelo_130_2026Q1.pdf"
        with pytest.raises(ModeloImportError, match="previous_year_economic_activity_net_income"):
            import_filing_from_justificante(pdf, schema_provider=cast(RegistryImportSchemaProvider, schema_provider))

    def test_unsupported_modelo_raises_import_error(self, schema_provider: RegistrySchemaProvider) -> None:
        pdf = _FIXTURES / "modelo_100_2025A.pdf"
        with pytest.raises(ModeloImportError, match="modelo '100'"):
            import_filing_from_justificante(pdf, schema_provider=cast(RegistryImportSchemaProvider, schema_provider))

    def test_year_only_period_rejected_for_quarterly_registry_revision(
        self,
        tmp_path: Path,
        schema_provider: RegistrySchemaProvider,
    ) -> None:
        pdf = _justificante_pdf_without_period(tmp_path, modelo="130", ejercicio="2026")

        with pytest.raises(ModeloImportError, match="period token '0A'"):
            import_filing_from_justificante(pdf, schema_provider=cast(RegistryImportSchemaProvider, schema_provider))

    def test_missing_pdf_raises_parse_error(
        self,
        tmp_path: Path,
        schema_provider: RegistrySchemaProvider,
    ) -> None:
        missing = tmp_path / "nonexistent.pdf"
        with pytest.raises(JustificanteParseError, match="not found"):
            import_filing_from_justificante(
                missing,
                schema_provider=cast(RegistryImportSchemaProvider, schema_provider),
            )


def _justificante_pdf_without_period(tmp_path: Path, *, modelo: str, ejercicio: str) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    target = tmp_path / f"modelo_{modelo}_{ejercicio}_year_only.pdf"
    c = canvas.Canvas(str(target), pagesize=A4)
    c.drawString(100, 760, "AGENCIA TRIBUTARIA")
    c.drawString(100, 735, f"Modelo: {modelo}")
    c.drawString(100, 710, f"Ejercicio: {ejercicio}")
    c.drawString(100, 685, "NIF: Y0000001S")
    c.drawString(100, 660, f"Numero de justificante: {modelo}{ejercicio}ABCD1234")
    c.drawString(100, 635, "Fecha y hora de presentacion: 2026-04-10 11:23:45")
    c.drawString(100, 610, "Resultado: A ingresar 10,00")
    c.drawString(100, 585, justificante_cotejo_url("ABCD1234EFGH5678"))
    c.showPage()
    c.save()
    return target
