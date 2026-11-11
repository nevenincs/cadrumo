"""The AEAT declarations register a persona's prior filings are captured from, recorded in memory.

A persona's ``[[aeat_filings]]`` are returns the taxpayer filed with the AEAT.
The replay brings each in through the registered filed capture, reading this
recorded register where the production composition reads the AEAT Sede. The
register serves what a capture there would read: the register row, the filed
declaration's casillas, and the justificante PDF fetched under the cotejo URL
that carries its CSV. Every step after the read is the production one: the
encrypted artefact store, the receipt parse and its digest, CSV, filing-target
and taxpayer checks, the filing-chain reconciliation and the calculation
history.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime, time
from uuid import UUID

from ...adapters.outbound.aeat.sede.schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclarationAvailability,
    FiledDeclarationAvailabilityReport,
    ObservedCasillaValue,
)
from ...application.live.expedientes_ports import ExpedientesDeclaration
from ...application.live.filed_data_ports import (
    DeferredFiledObservations,
    FiledArtefactSink,
    FiledDataRegisterPort,
    FiledEffectGuard,
    FiledRegisterDeclarationProtocol,
)
from ...application.live.filed_observation_ports import FiledObservationProtocol
from ...application.live.session import SessionWriteReporter
from ...core.bucket_pointer import require_active_bucket_id
from ...core.casilla_value_kind import CasillaValueKind
from ...core.external_constants import load_external_constants
from ...core.hashing import sha256_hex
from ...core.period import Period
from ...core.time.clock import madrid_wall_clock_to_utc, now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema import ModeloRevision
from ...tests.pdf_fixtures import text_pdf_bytes
from ...tests.personas import AeatFiling, Persona, YearEnvelope

PRESENTED_TIME = time(10, 30)
"""The Europe/Madrid wall-clock time of day a persona's AEAT filing was presented at."""

_DECLARATION_LOCATOR = "persona-aeat-filing"
"""The source locator every recorded casilla names: the persona's stated filing."""


def cotejo_source_url(csv: str) -> str:
    """The cotejo document URL a capture fetches a justificante under: the AEAT's own, carrying ``csv``."""
    aeat = load_external_constants().aeat
    return f"{aeat.domains.www6}{aeat.sede_paths.cotejo_document}?CSV={csv}"


def justificante_pdf_bytes(
    *, modelo: str, year: int, period: str, tax_id: str, csv: str, number: str, presented_at: datetime
) -> bytes:
    """A justificante PDF in the AEAT annual receipt layout, as the receipt parser reads one.

    ``presented_at`` is the naive Europe/Madrid wall clock the receipt prints.
    """
    return text_pdf_bytes(
        (
            f"Modelo {modelo}",
            f"Ejercicio {year}",
            f"Periodo {period}",
            f"NIF Presentador: {tax_id}",
            f"Código Seguro de Verificación {csv}",
            f"Presentación realizada el: {presented_at:%d-%m-%Y} a las {presented_at:%H:%M:%S}",
            f"Número de justificante: {number}",
            f"La autenticidad de este documento puede comprobarse en {cotejo_source_url(csv)}",
        )
    )


@dataclass(frozen=True, slots=True)
class RecordedFiling:
    """One filed return as the AEAT register holds it: its row, its declaration and its receipt bytes."""

    declaration: ExpedientesDeclaration
    observation: FiledDeclaracionObservation
    """The declaration as a capture reads it, its artefacts not yet stored."""
    justificante: bytes


def recorded_filing(
    persona: Persona, filing: AeatFiling, *, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> RecordedFiling:
    """What the AEAT register holds for one of the persona's AEAT filings.

    The declaration is filed by the persona's taxpayer, and its registry
    coordinate is the snapshot ``operation`` selects for the return, as the
    Sede capture selects it.
    """
    year = filing.year.resolve(envelope)
    period = Period.from_year_and_code(year, filing.period)
    # The receipt prints the Europe/Madrid wall clock; the register row names the instant it reads as.
    printed_at = datetime.combine(filing.presented.resolve(envelope), PRESENTED_TIME)
    presented_at = madrid_wall_clock_to_utc(printed_at)
    tax_id = persona.identity(persona.taxpayer)
    expediente_id = f"{year}{filing.modelo}{filing.justificante}"
    body = justificante_pdf_bytes(
        modelo=filing.modelo,
        year=year,
        period=filing.period,
        tax_id=tax_id,
        csv=filing.csv,
        number=filing.justificante,
        presented_at=printed_at,
    )
    snapshot = operation.snapshot(filing.modelo, filing_year=year, period=filing.period)
    observation = FiledDeclaracionObservation(
        modelo=filing.modelo,
        ejercicio=year,
        period=period,
        expediente_id=expediente_id,
        status="ALTA",
        presented_at=presented_at,
        authenticated_identity=tax_id,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="justificante_pdf",
                source_url=cotejo_source_url(filing.csv),
                content_type="application/pdf",
                byte_count=len(body),
                sha256=sha256_hex(body),
                captured_at=now(),
            ),
        ),
        casillas=tuple(
            ObservedCasillaValue(
                casilla_id=casilla,
                value=value,
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="declaration_pdf",
                source_locator=_DECLARATION_LOCATOR,
                confidence=1.0,
            )
            for casilla, value in filing.casillas
        ),
        extraction_coverage={"declaration_pdf": 1.0},
        registry_snapshot_ref=snapshot.snapshot_ref,
    )
    declaration = ExpedientesDeclaration(
        modelo=filing.modelo,
        ejercicio=year,
        period=period,
        expediente_id=expediente_id,
        estado="ALTA",
        presented_at=presented_at,
        justificante_link_text="Justificante",
        archive_link_text=None,
    )
    return RecordedFiling(declaration=declaration, observation=observation, justificante=body)


def _stored(filing: RecordedFiling, sink: FiledArtefactSink) -> FiledObservationProtocol:
    """Store the receipt through the capture's artefact sink and return the declaration naming it."""
    observation = filing.observation
    (artefact,) = observation.artefacts
    key = (observation.modelo, observation.ejercicio, observation.period, observation.expediente_id)
    stored = sink(key, artefact, filing.justificante)
    return observation.model_copy(
        update={"artefacts": (artefact.model_copy(update={"storage_ref": stored.storage_ref}),)}
    )


@dataclass(frozen=True, slots=True)
class _DeferredFiling:
    """A read filing whose receipt bytes await the capture's local write."""

    filing: RecordedFiling

    def persist_artefacts(self, sink: FiledArtefactSink) -> FiledObservationProtocol:
        return _stored(self.filing, sink)


class _RecordedRegisterSession:
    """One open register session over the filings recorded for the profile it was opened for."""

    walk_timeout_ms = 1000

    def __init__(self, filings: tuple[RecordedFiling, ...]) -> None:
        self._filings = filings

    def _filing(self, declaration: FiledRegisterDeclarationProtocol) -> RecordedFiling:
        for filing in self._filings:
            if filing.declaration.expediente_id == declaration.expediente_id:
                return filing
        raise LookupError(f"the register holds no expediente {declaration.expediente_id}")

    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[FiledRegisterDeclarationProtocol, ...]:
        return tuple(
            filing.declaration
            for filing in self._filings
            if (filing.declaration.modelo, filing.declaration.ejercicio) == (modelo, ejercicio)
        )

    async def capture_observation(
        self, declaration: FiledRegisterDeclarationProtocol, *, artefact_sink: FiledArtefactSink | None = None
    ) -> FiledObservationProtocol:
        filing = self._filing(declaration)
        return filing.observation if artefact_sink is None else _stored(filing, artefact_sink)

    async def capture_observation_deferred(self, declaration: FiledRegisterDeclarationProtocol) -> _DeferredFiling:
        return _DeferredFiling(self._filing(declaration))


class RecordedAeatRegister:
    """The AEAT declarations register as each profile's recorded filings show it.

    A capture reads the filings recorded for the profile it runs for, the
    worker's active one; a profile with none recorded has an empty register.
    The register holds no registry-selected source captures.
    """

    def __init__(self) -> None:
        self._filings: dict[str, tuple[RecordedFiling, ...]] = {}

    @contextmanager
    def serving(self, profile_id: UUID, filings: tuple[RecordedFiling, ...]) -> Generator[None]:
        """Serve ``filings`` as the register of ``profile_id`` while the block runs."""
        key = str(profile_id)
        if key in self._filings:
            raise RuntimeError(f"the register already serves profile {key}")
        self._filings[key] = filings
        try:
            yield
        finally:
            del self._filings[key]

    def _active(self) -> tuple[RecordedFiling, ...]:
        return self._filings.get(require_active_bucket_id(), ())

    @asynccontextmanager
    async def open_register(
        self,
        *,
        operation: str,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> AsyncGenerator[FiledDataRegisterPort]:
        del operation, authority_operation, effect_guard, on_session_write
        yield _RecordedRegisterSession(self._active())

    async def discover_availability(
        self,
        *,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> FiledDeclarationAvailabilityReport:
        del operation, effect_guard, on_session_write
        years: dict[str, set[int]] = {}
        for filing in self._active():
            years.setdefault(filing.declaration.modelo, set()).add(filing.declaration.ejercicio)
        return FiledDeclarationAvailabilityReport(
            items=tuple(
                FiledDeclarationAvailability(modelo=modelo, ejercicios=tuple(sorted(offered, reverse=True)))
                for modelo, offered in sorted(years.items())
            ),
            discovered_at=now(),
        )

    async def capture_source_observations(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        artefact_sink: FiledArtefactSink | None = None,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> tuple[FiledObservationProtocol, ...]:
        raise NotImplementedError("the recorded register holds declarations, not registry-selected sources")

    async def capture_source_observations_deferred(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> DeferredFiledObservations:
        raise NotImplementedError("the recorded register holds declarations, not registry-selected sources")


PERSONA_AEAT_REGISTER = RecordedAeatRegister()
"""The one register every persona world's filed captures read."""


__all__ = [
    "PERSONA_AEAT_REGISTER",
    "PRESENTED_TIME",
    "RecordedAeatRegister",
    "RecordedFiling",
    "cotejo_source_url",
    "justificante_pdf_bytes",
    "recorded_filing",
]
