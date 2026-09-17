"""A recorded, in-memory stand-in for the AEAT Sede filed-declaration register.

The port answers register walks and captures from a script the test sets
between CLI calls, so everything downstream of the transport -- artefact
storage, justificante parsing, reconciliation, observation persistence -- runs
for real. Every identity, amount and receipt is synthetic.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, override
from zoneinfo import ZoneInfo

from pydantic import AnyHttpUrl
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ....adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ....adapters.outbound.aeat.sede.schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaValue,
)
from ....application.live.filed_data_ports import (
    FiledArtefactSink,
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledDeclarationAvailabilityReportProtocol,
    FiledRegisterDeclarationProtocol,
)
from ....application.live.filed_observation_ports import FiledObservationProtocol
from ....core.casilla_id import validated_casilla_id
from ....core.casilla_value_kind import CasillaValueKind
from ....core.external_constants import load_external_constants
from ....core.period import Period
from ....core.time.clock import now as now_utc
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.published_authority import published_snapshot

_MADRID = ZoneInfo("Europe/Madrid")


@dataclass(frozen=True, slots=True)
class RecordedPresentation:
    """One presentation AEAT's register holds, with the content AEAT recorded for it."""

    period: Period
    expediente_id: str
    csv: str
    presented_at: datetime
    casilla_values: Mapping[str, Decimal]
    total_a_ingresar: Decimal
    tipo_solicitud: str | None = None


@dataclass(slots=True)
class RecordedSedeRegister:
    """What the register holds for the next pull; the test replaces it between pulls."""

    modelo: str
    tax_id: str
    full_name: str
    presentations: tuple[RecordedPresentation, ...] = ()
    walks: list[tuple[str, int]] = field(default_factory=list)
    captured_expedientes: list[str] = field(default_factory=list)

    def holds(self, *presentations: RecordedPresentation) -> None:
        """Script the presentations the next walk returns."""
        self.presentations = presentations


def _justificante_pdf(register: RecordedSedeRegister, presentation: RecordedPresentation) -> bytes:
    """Render a synthetic receipt carrying the fields the justificante parser reads."""
    period = presentation.period
    presented_local = presentation.presented_at.astimezone(_MADRID)
    presentation_id = justificante_number(register.modelo, presentation.csv, presentation.presented_at)
    external = load_external_constants().aeat
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4, invariant=1)
    _, height = A4
    lines = (
        ("Helvetica-Bold", 14, "AGENCIA TRIBUTARIA"),
        ("Helvetica-Bold", 12, "Justificante de presentacion"),
        ("Helvetica", 10, f"Modelo: {register.modelo}"),
        ("Helvetica", 10, f"Ejercicio: {period.filing_year}"),
        ("Helvetica", 10, f"Periodo: {period.registry_token}"),
        ("Helvetica", 10, f"NIF: {register.tax_id}"),
        ("Helvetica", 10, f"Apellidos y nombre o razon social: {register.full_name}"),
        ("Helvetica", 10, f"Numero de justificante: {presentation_id}"),
        ("Helvetica", 10, f"Fecha y hora de presentacion: {presented_local:%Y-%m-%d %H:%M:%S}"),
        ("Helvetica", 10, f"Codigo Seguro de Verificacion: {presentation.csv}"),
        ("Helvetica", 10, f"Total a ingresar: {presentation.total_a_ingresar} euros"),
        ("Helvetica", 10, "Puede verificar la autenticidad de este documento en:"),
        ("Helvetica", 10, f"{external.domains.sede}{external.help_pages.csv_verification}"),
    )
    y = height - 25 * mm
    for font, size, text in lines:
        page.setFont(font, size)
        page.drawString(20 * mm, y, text)
        y -= 8 * mm
    page.showPage()
    page.save()
    return buffer.getvalue()


def _cotejo_url(csv: str) -> AnyHttpUrl:
    external = load_external_constants().aeat
    return AnyHttpUrl(f"{external.domains.www6}{external.sede_paths.cotejo_document}?CSV={csv}")


def _declarations_url() -> AnyHttpUrl:
    external = load_external_constants().aeat
    return AnyHttpUrl(f"{external.domains.www6}{external.sede_paths.declarations_listing}")


def _submitted_file(register: RecordedSedeRegister, presentation: RecordedPresentation) -> bytes:
    """A deterministic stand-in body for the submitted fichero the casillas are read from."""
    rows = ";".join(f"{casilla_id}={value}" for casilla_id, value in sorted(presentation.casilla_values.items()))
    return f"{register.modelo}|{presentation.expediente_id}|{rows}".encode("ascii")


def _stored(
    artefact_sink: FiledArtefactSink | None,
    key: tuple[str, int, Period, str],
    *,
    kind: Literal["justificante_pdf", "submitted_file"],
    source_url: AnyHttpUrl,
    content_type: str,
    body: bytes,
    captured_at: datetime,
) -> FiledDeclaracionArtefact:
    artefact = FiledDeclaracionArtefact(
        kind=kind,
        source_url=source_url,
        content_type=content_type,
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=captured_at,
    )
    if artefact_sink is None:
        return artefact
    stored = artefact_sink(key, artefact, body)
    assert isinstance(stored, FiledDeclaracionArtefact)
    return stored


class _RecordedRegisterSession(FiledDataRegisterPort):
    def __init__(self, register: RecordedSedeRegister) -> None:
        self._register = register

    @property
    @override
    def walk_timeout_ms(self) -> int:
        return 60_000

    @override
    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[FiledRegisterDeclarationProtocol, ...]:
        self._register.walks.append((modelo, ejercicio))
        if modelo != self._register.modelo:
            return ()
        return tuple(
            Declaracion(
                modelo=modelo,
                ejercicio=ejercicio,
                period=presentation.period,
                expediente_id=presentation.expediente_id,
                estado="ALTA",
                tipo_solicitud=presentation.tipo_solicitud,
                presented_at=presentation.presented_at,
                justificante_link_text="Ver",
            )
            for presentation in self._register.presentations
            if presentation.period.filing_year == ejercicio
        )

    @override
    async def capture_observation(
        self,
        declaration: FiledRegisterDeclarationProtocol,
        *,
        artefact_sink: FiledArtefactSink | None = None,
    ) -> FiledObservationProtocol:
        register = self._register
        presentation = next(item for item in register.presentations if item.expediente_id == declaration.expediente_id)
        register.captured_expedientes.append(presentation.expediente_id)
        key = (register.modelo, presentation.period.filing_year, presentation.period, presentation.expediente_id)
        # Artefacts are stamped when this capture reads them, as a live capture does.
        captured_at = now_utc()
        receipt = _stored(
            artefact_sink,
            key,
            kind="justificante_pdf",
            source_url=_cotejo_url(presentation.csv),
            content_type="application/pdf",
            body=_justificante_pdf(register, presentation),
            captured_at=captured_at,
        )
        submitted = _stored(
            artefact_sink,
            key,
            kind="submitted_file",
            source_url=_declarations_url(),
            content_type="application/octet-stream",
            body=_submitted_file(register, presentation),
            captured_at=captured_at,
        )
        period = presentation.period
        return FiledDeclaracionObservation(
            modelo=register.modelo,
            ejercicio=period.filing_year,
            period=period,
            expediente_id=presentation.expediente_id,
            status="ALTA",
            presented_at=presentation.presented_at,
            authenticated_identity=register.tax_id,
            artefacts=(receipt, submitted),
            casillas=tuple(
                ObservedCasillaValue(
                    casilla_id=validated_casilla_id(casilla_id, surface="recorded register casilla"),
                    value=str(value),
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator=f"recorded:{casilla_id}",
                    confidence=1.0,
                )
                for casilla_id, value in sorted(presentation.casilla_values.items())
            ),
            metadata={"tipo_solicitud": presentation.tipo_solicitud} if presentation.tipo_solicitud else {},
            extraction_coverage={"submitted_file": 1.0},
            registry_snapshot_ref=published_snapshot(
                register.modelo,
                filing_year=period.filing_year,
                period=period.registry_token,
            ).snapshot_ref,
        )


class RecordedSedeFiledDataPort(FiledDataCapturePort):
    """Serve register walks and captures from a :class:`RecordedSedeRegister`."""

    def __init__(self, register: RecordedSedeRegister) -> None:
        """Bind the scripted register the test controls."""
        self._register = register

    @asynccontextmanager
    @override
    async def open_register(self, *, operation: str) -> AsyncIterator[FiledDataRegisterPort]:
        del operation
        yield _RecordedRegisterSession(self._register)

    @override
    async def discover_availability(self, *, operation: str) -> FiledDeclarationAvailabilityReportProtocol:
        raise AssertionError(f"the recorded register scripts no availability discovery ({operation})")

    @override
    async def capture_source_observations(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        artefact_sink: FiledArtefactSink | None = None,
        operation: str,
    ) -> tuple[FiledObservationProtocol, ...]:
        raise AssertionError(f"the recorded register scripts no source capture ({operation})")


def justificante_number(modelo: str, csv: str, presented_at: datetime) -> str:
    """The Numero de justificante a synthetic receipt prints for one presentation."""
    return f"{modelo}{presented_at.astimezone(_MADRID):%Y%m%d}{csv}"


def madrid_instant(year: int, month: int, day: int, hour: int) -> datetime:
    """Return a whole-second UTC instant for a Madrid wall-clock presentation time."""
    return datetime(year, month, day, hour, tzinfo=_MADRID).astimezone(UTC)
