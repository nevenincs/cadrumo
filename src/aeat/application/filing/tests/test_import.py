"""Unit tests for :mod:`aeat.application.filing._import`.

Exercises :func:`aeat.application.filing.import_filing_from_justificante`
end-to-end against local justificante fixture PDFs under
``src/aeat/tests/fixtures/justificantes/``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import AnyHttpUrl

from ....core import Period
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.filing import ModeloImportError
from ....domain.justificante import Justificante, JustificanteParseError
from ....tests import FIXTURES_DIR
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from .. import ModeloOperatorProfile, build_draft, import_filing_from_justificante
from .._import import RegistryImportSchemaProvider, _build_submission_record, _normalise_period
from ..runtime import RegistrySchemaAccessor, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIXTURES = FIXTURES_DIR / "justificantes"
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_PAGOS_PREVIOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_FINAL_CASILLA")


@pytest.fixture(scope="module")
def schema_provider() -> RegistrySchemaAccessor:
    return build_runtime_schema_provider()


def test_runtime_schema_provider_exposes_imported_modelo_schema(schema_provider: RegistrySchemaAccessor) -> None:
    collection = schema_provider.get_collection("130")

    casilla_19 = collection.get(_M130_RESULTADO_FINAL_CASILLA)
    assert casilla_19 is not None
    assert casilla_19.casilla_id == _M130_RESULTADO_FINAL_CASILLA


def test_normalise_period_returns_supported_typed_period(
    schema_provider: RegistrySchemaAccessor,
) -> None:
    expected = Period.from_year_and_code(2026, "1T")
    period = _normalise_period(
        modelo="130",
        ejercicio="2026",
        raw_period=expected,
        schema_provider=cast(RegistryImportSchemaProvider, schema_provider),
    )
    assert period == expected
    assert period.model_dump() == {"filing_year": 2026, "code": "1T"}


def test_normalise_period_rejects_typed_period_year_mismatch(
    schema_provider: RegistrySchemaAccessor,
) -> None:
    with pytest.raises(ModeloImportError, match=r"cannot canonicalise period 2025 1T"):
        _normalise_period(
            modelo="130",
            ejercicio="2026",
            raw_period=Period.from_year_and_code(2025, "1T"),
            schema_provider=cast(RegistryImportSchemaProvider, schema_provider),
        )


def test_normalise_period_rejects_period_not_declared_by_registry(
    schema_provider: RegistrySchemaAccessor,
) -> None:
    with pytest.raises(ModeloImportError, match=r"period token '1T' is not declared"):
        _normalise_period(
            modelo="390",
            ejercicio="2021",
            raw_period=Period.from_year_and_code(2021, "1T"),
            schema_provider=cast(RegistryImportSchemaProvider, schema_provider),
        )


def test_normalise_period_accepts_supported_annual_typed_period(
    schema_provider: RegistrySchemaAccessor,
) -> None:
    expected = Period.from_year_and_code(2021, "0A")
    period = _normalise_period(
        modelo="390",
        ejercicio="2021",
        raw_period=expected,
        schema_provider=cast(RegistryImportSchemaProvider, schema_provider),
    )
    assert period == expected


def test_submission_record_preserves_typed_draft_period(
    schema_provider: RegistrySchemaAccessor,
) -> None:
    period = Period.from_year_and_code(2026, "1T")
    draft = build_draft(
        modelo="130",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Import submission test"),
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("100"),
            _M130_GASTOS_CASILLA: Decimal("25"),
            _M130_PAGOS_PREVIOS_CASILLA: Decimal("0"),
            _M130_RETENCIONES_CASILLA: Decimal("0"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        schema_provider=schema_provider,
    )
    justificante = Justificante(
        csv="ABCD1234EFGH5678",
        modelo="130",
        period=period,
        ejercicio="2026",
        presentation_id="1302026ABCD1234",
        presented_at=datetime(2026, 4, 10, 11, 23, 45),
        tax_id="12345678Z",
        total_a_ingresar=Decimal("10.00"),
        verification_url=AnyHttpUrl(justificante_cotejo_url("ABCD1234EFGH5678")),
        source_pdf_path=Path("var") / "justificantes" / "modelo_130_2026Q1.pdf",
        source_pdf_sha256="a" * 64,
        parsed_at=datetime(2026, 4, 10, 9, 25, tzinfo=UTC),
    )

    submission = _build_submission_record(justificante=justificante, draft=draft)

    assert submission.period == period
    assert submission.model_dump(mode="json")["period"] == {"filing_year": 2026, "code": "1T"}


class TestImportFromJustificante:
    """End-to-end reconstruction from local fixture PDFs."""

    def test_modelo_130_justificante_only_import_requires_binding_data(
        self,
        schema_provider: RegistrySchemaAccessor,
    ) -> None:
        pdf = _FIXTURES / "modelo_130_2026Q1.pdf"
        with pytest.raises(ModeloImportError, match="previous_year_economic_activity_net_income"):
            import_filing_from_justificante(pdf, schema_provider=cast(RegistryImportSchemaProvider, schema_provider))

    def test_unsupported_modelo_raises_import_error(self, schema_provider: RegistrySchemaAccessor) -> None:
        pdf = _FIXTURES / "modelo_100_2025A.pdf"
        with pytest.raises(ModeloImportError, match="modelo '100'"):
            import_filing_from_justificante(pdf, schema_provider=cast(RegistryImportSchemaProvider, schema_provider))

    def test_year_only_justificante_period_is_rejected_at_registry_boundary(
        self,
        tmp_path: Path,
        schema_provider: RegistrySchemaAccessor,
    ) -> None:
        pdf = _justificante_pdf_without_period(tmp_path, modelo="130", ejercicio="2026")

        with pytest.raises(ModeloImportError, match="period token '0A'"):
            import_filing_from_justificante(pdf, schema_provider=cast(RegistryImportSchemaProvider, schema_provider))

    def test_missing_pdf_raises_parse_error(
        self,
        tmp_path: Path,
        schema_provider: RegistrySchemaAccessor,
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
