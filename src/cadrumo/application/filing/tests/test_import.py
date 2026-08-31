"""Unit tests for :mod:`cadrumo.application.filing._import`.

Exercises :func:`cadrumo.application.filing.import_filing_from_justificante`
end-to-end against local justificante fixture PDFs under
``src/cadrumo/tests/fixtures/justificantes/``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import AnyHttpUrl

from ....adapters.inbound.pdf.utils import source_pdf_reference_path
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.config import override_settings
from ....core.errors.error_codes import resolve_error_message
from ....core.period import Period
from ....domain.filing.errors import ModeloImportError
from ....domain.justificante import Justificante, JustificanteParseError
from ....domain.submission.models import make_submission_id
from ....tests import FIXTURES_DIR
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from .._import import (
    RegistryImportSchemaProvider,
    _build_submission_record,
    _normalise_period,
    import_filing_from_justificante,
)
from ..draft_construction import build_draft
from ..runtime import ModeloOperatorProfile, RegistrySchemaAccessor, build_runtime_schema_provider

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


@pytest.mark.parametrize(
    ("modelo", "ejercicio", "expected"),
    [
        ("130", "2026", Period.from_year_and_code(2026, "1T")),
        ("390", "2021", Period.from_year_and_code(2021, "0A")),
    ],
    ids=("quarterly", "annual"),
)
def test_normalise_period_returns_supported_typed_period(
    schema_provider: RegistrySchemaAccessor,
    modelo: str,
    ejercicio: str,
    expected: Period,
) -> None:
    period = _normalise_period(
        modelo=modelo,
        ejercicio=ejercicio,
        raw_period=expected,
        schema_provider=cast(RegistryImportSchemaProvider, schema_provider),
    )
    assert period == expected
    assert period.model_dump() == {"filing_year": expected.filing_year, "code": expected.code}


@pytest.mark.parametrize(
    ("modelo", "ejercicio", "raw_period", "expected_key", "expected_context"),
    [
        (
            "130",
            "2026",
            Period.from_year_and_code(2025, "1T"),
            "application.filing.errors.period_ejercicio_mismatch",
            {"modelo": "130"},
        ),
        (
            "390",
            "2021",
            Period.from_year_and_code(2021, "1T"),
            "application.filing.import.errors.period_token_undeclared",
            {"modelo": "390", "filing_year": 2021, "period_code": "1T"},
        ),
    ],
    ids=("year-mismatch", "registry-period-missing"),
)
def test_normalise_period_rejects_unsupported_typed_period(
    schema_provider: RegistrySchemaAccessor,
    modelo: str,
    ejercicio: str,
    raw_period: Period,
    expected_key: str,
    expected_context: dict[str, object],
) -> None:
    """Both refusals name the offending pair through the typed error, not prose.

    The refusals render through the locale catalogues, so the rendered string is
    the catalogue's business and changes with a translation edit. What the
    caller can rely on is the translated_message key and the typed context the
    renderer interpolates, and that is what is asserted here.
    """
    with pytest.raises(ModeloImportError) as exc_info:
        _normalise_period(
            modelo=modelo,
            ejercicio=ejercicio,
            raw_period=raw_period,
            schema_provider=cast(RegistryImportSchemaProvider, schema_provider),
        )
    error = exc_info.value
    assert error.translated_message == expected_key
    context = error.context
    assert context is not None
    assert expected_context.items() <= context.items(), context
    with override_settings(cadrumo_output_language="en"):
        assert resolve_error_message(error)


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
        source_pdf_path=source_pdf_reference_path("a" * 64),
        source_pdf_sha256="a" * 64,
        parsed_at=datetime(2026, 4, 10, 9, 25, tzinfo=UTC),
    )

    submission = _build_submission_record(justificante=justificante, draft=draft)

    assert submission.period == period
    assert submission.model_dump(mode="json")["period"] == {"filing_year": 2026, "code": "1T"}
    assert submission.submission_id == make_submission_id(draft.draft_id, 1)


def test_submission_record_preserves_an_aware_receipt_instant(
    schema_provider: RegistrySchemaAccessor,
) -> None:
    period = Period.from_year_and_code(2026, "1T")
    draft = build_draft(
        modelo="130",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Aware import test"),
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
    presented_at = datetime(2026, 4, 10, 11, 23, 45, tzinfo=UTC)
    justificante = Justificante(
        csv="ABCD1234EFGH5678",
        modelo="130",
        period=period,
        ejercicio="2026",
        presentation_id="1302026ABCD1234",
        presented_at=presented_at,
        tax_id="12345678Z",
        total_a_ingresar=Decimal("10.00"),
        verification_url=AnyHttpUrl(justificante_cotejo_url("ABCD1234EFGH5678")),
        source_pdf_path=source_pdf_reference_path("a" * 64),
        source_pdf_sha256="a" * 64,
        parsed_at=datetime(2026, 4, 10, 9, 25, tzinfo=UTC),
    )

    submission = _build_submission_record(justificante=justificante, draft=draft)

    assert submission.submitted_at == presented_at
    assert submission.attempts[0].started_at == presented_at


class TestImportFromJustificante:
    """End-to-end reconstruction from local fixture PDFs."""

    def test_modelo_130_justificante_only_import_requires_binding_data(
        self,
        schema_provider: RegistrySchemaAccessor,
    ) -> None:
        pdf = _FIXTURES / "modelo_130_2026Q1.pdf"
        with pytest.raises(ModeloImportError) as excinfo:
            import_filing_from_justificante(
                pdf,
                schema_provider=cast(RegistryImportSchemaProvider, schema_provider),
            )
        # The operator-facing message names the failing stage, not the binding:
        # the builder's typed context carries the modelo, revision and registry
        # error type, and the binding that has no supplied value is carried by
        # the chained registry refusal it wraps. That chained context is the
        # durable home of the name, so it is what is asserted.
        causes = []
        cause = excinfo.value.__cause__
        while cause is not None:
            causes.append(cause)
            cause = cause.__cause__
        contexts = [dict(getattr(cause, "context", {}) or {}) for cause in causes]
        assert any(
            context.get("binding_id") == "irpf.previous_year_economic_activity_net_income" for context in contexts
        ), contexts

    def test_unsupported_modelo_raises_import_error(self, schema_provider: RegistrySchemaAccessor) -> None:
        pdf = _FIXTURES / "modelo_100_2025A.pdf"
        with pytest.raises(ModeloImportError) as excinfo:
            import_filing_from_justificante(
                pdf,
                schema_provider=cast(RegistryImportSchemaProvider, schema_provider),
            )
        assert "modelo '100'" in resolve_error_message(excinfo.value)

    def test_year_only_justificante_period_is_rejected_at_registry_boundary(
        self,
        tmp_path: Path,
        schema_provider: RegistrySchemaAccessor,
    ) -> None:
        pdf = _justificante_pdf_without_period(tmp_path, modelo="130", ejercicio="2026")

        with pytest.raises(ModeloImportError) as excinfo:
            import_filing_from_justificante(
                pdf,
                schema_provider=cast(RegistryImportSchemaProvider, schema_provider),
            )
        error = excinfo.value
        assert error.translated_message == "application.filing.import.errors.period_token_undeclared"
        context = error.context
        assert context is not None
        assert context["period_code"] == "0A"

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
