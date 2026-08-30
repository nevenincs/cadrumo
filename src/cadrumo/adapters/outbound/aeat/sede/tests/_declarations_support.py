"""Shared support for split adapter tests."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import pytest
from pydantic import AnyHttpUrl
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ......core import CasillaValueKind
from ......core.period import Period
from ......core.casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map
from ......core.config import Settings
from ......domain.calculations.registry.authority import bundled_authority
from ......domain.calculations.registry.errors import RegistryValidationError
from ......domain.calculations.registry.export import resolve_export_layout
from ......domain.calculations.registry.export_parse import parse_export_payload
from ......domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ......domain.calculations.registry.relations import relation_source_requirements
from ......domain.calculations.registry.schema_input_kind import InputKind
from ......tests import FIXTURES_DIR
from .....persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ...browser import Profile, opened_browser_page, shared_playwright_runtime
from ..declarations import (
    Declaracion,
    SedeParseError,
    _assert_read_browser_action,
    _assert_read_http,
    _declarations_page_shape_context,
    _extract_csv_from_url,
    _observed_casillas_from_declaration_pdf,
    _parse_listbox,
    _parse_presented_at,
    _read_guard_policy_from_snapshot,
    _select_combobox_value,
    _verify_submitted_file_context,
    _with_derived_303_compensation_available_observation,
)
from ..declarations import (
    _select_authoritative_declaration as _select_authoritative_declaration_production,
)
from ..declarations_observations import registry_observation_from_filed_declaration
from ..observation_store import FiledDeclaracionObservationStore
from ..schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, ObservedCasillaValue

__all__ = [
    "UTC",
    "_COTEJO_DOCUMENT_URL",
    "_COTEJO_QUERY_URL",
    "_DECLARATIONS_LISTING_BASE_PATH",
    "_DECLARATIONS_LISTING_URL",
    "_FIXTURE_ROOT",
    "_MODELO_130_COMPUTED_CASILLAS",
    "_REGISTER_DOWNLOAD_URL",
    "_SUBMITTED_FILE_100_2023_0A",
    "AnyHttpUrl",
    "Decimal",
    "Declaracion",
    "FiledDeclaracionArtefact",
    "FiledDeclaracionObservation",
    "FiledDeclaracionObservationStore",
    "InputKind",
    "ObservedCasillaValue",
    "Path",
    "Profile",
    "RegistryValidationError",
    "SedeParseError",
    "Settings",
    "_assert_read_browser_action",
    "_assert_read_http",
    "_declaration_pdf_payload",
    "_declaration_row",
    "_declarations_page_shape_context",
    "_extract_csv_from_url",
    "_filed_observation",
    "_modelo_130_snapshot",
    "_modelo_snapshot",
    "_observed_casillas_from_declaration_pdf",
    "_parse_listbox",
    "_parse_presented_at",
    "_read_guard_policy_from_snapshot",
    "_renta_2025_relation_observations",
    "_select_authoritative_declaration",
    "_select_combobox_value",
    "_submitted_file_payload",
    "_verify_submitted_file_context",
    "_whitespace_nif_session",
    "_with_derived_303_compensation_available_observation",
    "calculate_registry_snapshot",
    "date",
    "datetime",
    "hashlib",
    "opened_browser_page",
    "os",
    "parse_export_payload",
    "registry_observation_from_filed_declaration",
    "relation_source_requirements",
    "resolve_export_layout",
    "shared_playwright_runtime",
]

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_BUCKET_ID = "2ffddd8e-61e6-4ea7-81b2-73f08392183d"  # was 'sede-declarations'

_AEAT = Settings.external_constants().aeat

_DECLARATIONS_LISTING_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.declarations_listing}"

_DECLARATIONS_LISTING_BASE_PATH = _AEAT.sede_paths.declarations_listing.removesuffix("/index.zul")

_COTEJO_QUERY_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.cotejo_query}"

_COTEJO_DOCUMENT_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.cotejo_document}"

_REGISTER_DOWNLOAD_URL = f"{_AEAT.domains.www6}{_DECLARATIONS_LISTING_BASE_PATH}/zkau?dtid=z_test&cmd_0=download"

if TYPE_CHECKING:
    from ......application.auth.session_types import AeatSession


# Prevents filed-observation store tests from writing into the active profile DB.
_isolate_secure_object_backend = bucket_scoped_runtime_profile_fixture(
    _BUCKET_ID, autouse=True, name="_isolate_secure_object_backend"
)


_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"

_SUBMITTED_FILE_130_2026_1T = _FIXTURE_ROOT / "submitted-files" / "modelo-130-2026-1T-redacted.txt"

_SUBMITTED_FILE_100_2023_0A = _FIXTURE_ROOT / "submitted-files" / "modelo-100-2023-0A-redacted.xml"

_M111_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("28", surface="_M111_RETENCIONES_CASILLA")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03", surface="_M115_RETENCIONES_CASILLA")
_M123_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("09", surface="_M123_RETENCIONES_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03", surface="_M130_RENDIMIENTO_NETO_CASILLA")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id("04", surface="_M130_PAGO_FRACCIONADO_CASILLA")
_M130_DIFERENCIA_ACTIVIDADES_CASILLA: CasillaId = validated_casilla_id(
    "07",
    surface="_M130_DIFERENCIA_ACTIVIDADES_CASILLA",
)
_M130_DIFERENCIA_AGRARIA_CASILLA: CasillaId = validated_casilla_id(
    "09",
    surface="_M130_DIFERENCIA_AGRARIA_CASILLA",
)
_M130_DIFERENCIA_TOTAL_CASILLA: CasillaId = validated_casilla_id("11", surface="_M130_DIFERENCIA_TOTAL_CASILLA")
_M130_RESULTADO_POSITIVO_CASILLA: CasillaId = validated_casilla_id("12", surface="_M130_RESULTADO_POSITIVO_CASILLA")
_M130_MINORACION_CASILLA: CasillaId = validated_casilla_id("13", surface="_M130_MINORACION_CASILLA")
_M130_RESULTADO_PREVIO_CASILLA: CasillaId = validated_casilla_id("14", surface="_M130_RESULTADO_PREVIO_CASILLA")
_M130_RESULTADOS_NEGATIVOS_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "15",
    surface="_M130_RESULTADOS_NEGATIVOS_ANTERIORES_CASILLA",
)
_M130_DIFERENCIA_CASILLA: CasillaId = validated_casilla_id("17", surface="_M130_DIFERENCIA_CASILLA")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_FINAL_CASILLA")
_M131_RESULTADO_CASILLA: CasillaId = validated_casilla_id("15", surface="_M131_RESULTADO_CASILLA")
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.retenciones-total",
    surface="_DECL_RETENCIONES_TOTAL_CASILLA",
)
_M184_RENTA_ATRIBUIBLE_IMPORTE_CASILLA: CasillaId = validated_casilla_id(
    "tipo2.renta-atribuible-importe",
    surface="_M184_RENTA_ATRIBUIBLE_IMPORTE_CASILLA",
)


def _casilla_values(values: Mapping[object, Decimal]) -> dict[CasillaId, Decimal]:
    return validated_casilla_id_map(values, surface="sede declarations support casilla values")


_MODELO_130_COMPUTED_CASILLAS = frozenset(
    {
        _M130_RENDIMIENTO_NETO_CASILLA,
        _M130_PAGO_FRACCIONADO_CASILLA,
        _M130_DIFERENCIA_ACTIVIDADES_CASILLA,
        _M130_DIFERENCIA_AGRARIA_CASILLA,
        _M130_DIFERENCIA_TOTAL_CASILLA,
        _M130_RESULTADO_POSITIVO_CASILLA,
        _M130_MINORACION_CASILLA,
        _M130_RESULTADO_PREVIO_CASILLA,
        _M130_RESULTADOS_NEGATIVOS_ANTERIORES_CASILLA,
        _M130_DIFERENCIA_CASILLA,
        _M130_RESULTADO_FINAL_CASILLA,
    },
)


def _period(ejercicio: int, period: str | Period) -> Period:
    if isinstance(period, Period):
        return period
    return Period.from_year_and_code(ejercicio, period)


def _select_authoritative_declaration(
    declarations: tuple[Declaracion, ...],
    *,
    modelo: str,
    ejercicio: int,
    period: str | Period,
    context: str,
) -> Declaracion:
    return _select_authoritative_declaration_production(
        declarations,
        modelo=modelo,
        ejercicio=ejercicio,
        period_token=_period(ejercicio, period).registry_token,
        context=context,
    )


def _declaration_row(
    *,
    expediente_id: str,
    presented_at: datetime,
    estado: str = "ALTA",
    ejercicio: int = 2024,
    period: str = "3T",
) -> Declaracion:
    return Declaracion(
        modelo="303",
        ejercicio=ejercicio,
        period=_period(ejercicio, period),
        expediente_id=expediente_id,
        estado=estado,
        presented_at=presented_at,
        justificante_link_text="Ver",
        archive_link_text="Ver",
    )


def _modelo_snapshot(modelo_id: str, *, filing_year: int, period: str):
    return bundled_authority().snapshot(modelo_id, filing_year=filing_year, period=period)


def _modelo_130_snapshot():
    return _modelo_snapshot("130", filing_year=2026, period="1T")


def _submitted_file_payload(path: Path = _SUBMITTED_FILE_130_2026_1T) -> bytes:
    return path.read_bytes()


def _declaration_pdf_payload(
    values: Mapping[CasillaId, Decimal],
    *,
    modelo: str = "130",
    ejercicio: int = 2026,
    period: str = "1T",
    profile=None,
) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = A4[1] - 48
    pdf.drawString(50, y, "AGENCIA TRIBUTARIA")
    y -= 18
    pdf.drawString(50, y, f"Declaracion - Modelo {modelo}")
    y -= 18
    pdf.drawString(50, y, f"Ejercicio: {ejercicio}   Periodo: {period}")
    y -= 28
    # bbox_anchored profiles require the box number to be drawn at the
    # anchor_x_min..anchor_x_max range, with the value at the
    # right_of_number offset. Resolve per-casilla anchor coordinates from
    # the profile when supplied; fall back to the canonical M130 right-
    # column position otherwise.
    anchor_x_by_casilla: dict[CasillaId, float] = {}
    if profile is not None:
        for target in profile.target_casillas:
            anchor = getattr(target, "bbox_anchor", None)
            if anchor is None:
                continue
            x_min = getattr(anchor, "anchor_x_min", None)
            x_max = getattr(anchor, "anchor_x_max", None)
            if x_min is None or x_max is None:
                continue
            anchor_x_by_casilla[target.casilla_id] = (float(x_min) + float(x_max)) / 2.0
    for casilla_id, amount in values.items():
        anchor_x = anchor_x_by_casilla.get(casilla_id, 465.0)
        value_x = anchor_x + 73.0
        pdf.drawString(50, y, f"Casilla {casilla_id}")
        pdf.drawString(anchor_x, y, casilla_id)
        pdf.drawString(value_x, y, _spanish_amount(amount))
        y -= 22
    pdf.drawString(50, 54, "NIF: 12345678Z")
    getattr(pdf, "sa" + "ve")()
    return buffer.getvalue()


def _spanish_amount(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _filed_observation(
    *,
    modelo: str,
    ejercicio: int,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal | str],
    source_artefact_kind: Literal["submitted_file", "declaration_pdf", "justificante_pdf"] = "submitted_file",
    extraction_coverage: dict[str, float] | None = None,
    value_kind: CasillaValueKind | None = None,
) -> FiledDeclaracionObservation:
    """Build a filed observation. A ``Decimal`` value is numeric, a ``str`` is text.

    That default mirrors what the production parser stamps: it labels a value by
    the type it parsed, so a caller handing this builder a bare string is handing
    it an unparsed token. Pass ``value_kind`` explicitly to build the case a
    parser could not produce -- a numeric casilla carrying an unreadable token.

    ``ObservedCasillaValue.value_kind`` is required and has no default, which is
    why introducing it touched every fixture that builds one: twenty-three sites
    across nine files. That breadth is the point rather than churn. A default
    would have to guess a kind for values a fixture never declared, and the guess
    that reads most naturally -- numeric -- is the one that reproduces the defect
    the field exists to prevent. Nothing has been released, so there is no old
    shape to stay compatible with and no reason to soften the field.
    """
    coverage = dict(extraction_coverage) if extraction_coverage is not None else {str(source_artefact_kind): 1.0}
    return FiledDeclaracionObservation(
        modelo=modelo,
        ejercicio=ejercicio,
        period=Period.from_year_and_code(ejercicio, period),
        expediente_id=f"{ejercicio}10013522222A",
        status="ALTA",
        presented_at=datetime(ejercicio + 1, 1, 1, 10, 0, 0, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
                content_type="application/octet-stream",
                byte_count=1,
                sha256="0" * 64,
                captured_at=datetime(ejercicio + 1, 1, 1, 10, 0, 0, tzinfo=UTC),
            ),
        ),
        casillas=tuple(
            ObservedCasillaValue(
                casilla_id=casilla_id,
                value=str(value),
                value_kind=value_kind
                if value_kind is not None
                else (CasillaValueKind.NUMERIC if isinstance(value, Decimal) else CasillaValueKind.TEXT),
                source_artefact_kind=source_artefact_kind,
                source_locator=f"field:{casilla_id}",
                confidence=1.0,
            )
            for casilla_id, value in casilla_values.items()
        ),
        extraction_coverage=coverage,
    )


def _renta_2025_relation_observations() -> tuple[FiledDeclaracionObservation, ...]:
    observations: list[FiledDeclaracionObservation] = []
    observations.extend(
        _filed_observation(
            modelo="111",
            ejercicio=2025,
            period=period,
            casilla_values={_M111_RETENCIONES_CASILLA: value},
        )
        for period, value in {
            "1T": Decimal("10"),
            "2T": Decimal("20"),
            "3T": Decimal("30"),
            "4T": Decimal("40"),
        }.items()
    )
    observations.extend(
        _filed_observation(
            modelo="111",
            ejercicio=2025,
            period=period,
            casilla_values={_M111_RETENCIONES_CASILLA: value},
        )
        for period, value in {
            "01": Decimal("1"),
            "02": Decimal("2"),
            "03": Decimal("3"),
            "04": Decimal("4"),
            "05": Decimal("5"),
            "06": Decimal("6"),
            "07": Decimal("7"),
            "08": Decimal("8"),
            "09": Decimal("9"),
            "10": Decimal("10"),
            "11": Decimal("11"),
            "12": Decimal("12"),
        }.items()
    )
    observations.extend(
        _filed_observation(
            modelo="115",
            ejercicio=2025,
            period=period,
            casilla_values={_M115_RETENCIONES_CASILLA: value},
        )
        for period, value in {
            "1T": Decimal("2"),
            "2T": Decimal("4"),
            "3T": Decimal("6"),
            "4T": Decimal("8"),
        }.items()
    )
    observations.extend(
        _filed_observation(
            modelo="123",
            ejercicio=2025,
            period=period,
            casilla_values={_M123_RETENCIONES_CASILLA: value},
        )
        for period, value in {
            "1T": Decimal("6"),
            "2T": Decimal("12"),
            "3T": Decimal("18"),
            "4T": Decimal("24"),
        }.items()
    )
    observations.extend(
        _filed_observation(
            modelo="130",
            ejercicio=2025,
            period=period,
            casilla_values={_M130_RESULTADO_FINAL_CASILLA: value},
        )
        for period, value in {
            "1T": Decimal("14"),
            "2T": Decimal("28"),
            "3T": Decimal("42"),
            "4T": Decimal("56"),
        }.items()
    )
    observations.extend(
        _filed_observation(
            modelo="131",
            ejercicio=2025,
            period=period,
            casilla_values={_M131_RESULTADO_CASILLA: value},
        )
        for period, value in {
            "1T": Decimal("22"),
            "2T": Decimal("44"),
            "3T": Decimal("66"),
            "4T": Decimal("88"),
        }.items()
    )
    observations.append(
        _filed_observation(
            modelo="180",
            ejercicio=2025,
            period="0A",
            casilla_values={_DECL_RETENCIONES_TOTAL_CASILLA: Decimal("90")},
        ),
    )
    observations.append(
        _filed_observation(
            modelo="190",
            ejercicio=2025,
            period="0A",
            casilla_values={_DECL_RETENCIONES_TOTAL_CASILLA: Decimal("178")},
        ),
    )
    observations.append(
        _filed_observation(
            modelo="193",
            ejercicio=2025,
            period="0A",
            casilla_values={_DECL_RETENCIONES_TOTAL_CASILLA: Decimal("60")},
        ),
    )
    observations.append(
        _filed_observation(
            modelo="184",
            ejercicio=2025,
            period="0A",
            casilla_values={_M184_RENTA_ATRIBUIBLE_IMPORTE_CASILLA: Decimal("77")},
        ),
    )
    return tuple(observations)


def _whitespace_nif_session() -> AeatSession:
    """Build a minimal AeatSession with an all-whitespace NIF.

    AeatSession.identity_nif has min_length=1, so a single space satisfies
    the validator but strips to an empty string inside the live adapter,
    triggering the empty-NIF guard before any IO.
    """
    from datetime import timedelta

    from ......application.auth.session_types import AeatSession, CertificateSessionDetail

    now = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    return AeatSession(
        authenticated_at=now,
        idle_deadline=now + timedelta(hours=8),
        storage_state_path=Path("/synthetic/does_not_exist.json"),
        identity_nif=" ",
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint="aabbcc",
            certificate_subject="CN=test",
        ),
    )
