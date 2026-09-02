"""Capture filed-declaration evidence after the register reader selects a row."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....core.casilla_id import CasillaId
from .....core.config import Settings
from .....core.i18n import tr
from .....core.observed_header_fact import ObservedHeaderFact
from .....core.period import Period
from .....domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from .....domain.calculations.registry.errors import RegistryValidationError
from .....domain.calculations.registry.relations import relation_source_requirements, source_presence_gaps
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.snapshot_coordinate import registry_snapshot_id
from .._playwright import BrowserContext, Locator, Page, Playwright
from ._declarations_fetch import (
    capture_row_pdf_artefact,
    capture_submitted_file_artefact,
    listing_url_for,
    origin_of,
)
from .declarations_observations import (
    FiledDeclaracionArtefactSink,
    _declaration_pdf_extraction_profile_provisional,
    _observed_casillas_from_declaration_pdf,
    _read_guard_policy_from_snapshot,
    _register_row_artefact,
    _registry_snapshot_for_declaration,
    _store_artefact,
    _submitted_file_coverage_for_casillas,
    _with_derived_303_compensation_available_observation,
    observed_casillas_from_submitted_file,
    observed_header_facts_from_submitted_file,
)
from .declarations_schema import Declaracion
from .errors import JustificanteFetchError, SedeNavigationError, SedeParseError
from .schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, ObservedCasillaValue

if TYPE_CHECKING:
    from .....application.auth.session_types import AeatSession
    from .....domain.calculations.registry.schema import ModeloRevision


async def capture_filed_declaration_observation(
    session: AeatSession,
    declaration: Declaracion,
    *,
    registry_snapshot: RegistrySnapshot | None = None,
    settings: Settings | None = None,
    playwright: Playwright | None = None,
    artefact_sink: FiledDeclaracionArtefactSink | None = None,
) -> FiledDeclaracionObservation:
    """Capture a :class:`FiledDeclaracionObservation` with read-only evidence.

    The observation begins with the register row and captures each artefact AEAT
    exposes for it: the justificante/declaration PDF and, when present, the
    submitted-file download. Submitted files are parsed through the registry
    export layout selected for the declaration snapshot.

    Args:
        session: Authenticated AEAT session.
        declaration: Register row to observe.
        registry_snapshot: Optional pre-built snapshot for the declaration.
        settings: Optional settings override.
        playwright: Optional pre-started Playwright instance.
        artefact_sink: Optional callable storing each captured artefact.
    """
    authenticated_identity = (session.identity_nif or "").strip()
    if not authenticated_identity:
        raise SedeNavigationError(
            "AeatSession.identity_nif is empty; cannot bind live filing observation",
            translated_message=tr("adapters.sede.errors.empty_identity_nif"),
        )
    from .declarations import open_declarations_register

    async with open_declarations_register(session, settings=settings, playwright=playwright) as register:
        return await register.capture_observation(
            declaration,
            registry_snapshot=registry_snapshot,
            artefact_sink=artefact_sink,
        )


def _record_submitted_file_extraction_error(
    metadata: dict[str, str],
    error: RegistryValidationError | SedeParseError,
) -> None:
    """Persist the adapter's own submitted-file parser refusal verbatim."""
    metadata["submitted_file_extraction_error"] = str(error)


async def capture_filed_declaration_observation_from_row(
    session: AeatSession,
    declaration: Declaracion,
    *,
    row_locator: Locator,
    page: Page,
    context: BrowserContext,
    registry_snapshot: RegistrySnapshot | None,
    artefact_sink: FiledDeclaracionArtefactSink | None,
) -> FiledDeclaracionObservation:
    authenticated_identity = (session.identity_nif or "").strip()
    if not authenticated_identity:
        raise SedeNavigationError(
            "AeatSession.identity_nif is empty; cannot bind live filing observation",
            translated_message="adapters.sede.errors.empty_identity_nif",
        )
    snapshot = registry_snapshot or _registry_snapshot_for_declaration(declaration)
    read_policy = _read_guard_policy_from_snapshot(snapshot)
    filing_period = declaration.period
    observation_key = (declaration.modelo, declaration.ejercicio, filing_period, declaration.expediente_id)
    from pydantic import AnyHttpUrl

    listing_url = AnyHttpUrl(
        listing_url_for(
            origin_of(getattr(page, "url", None)),
            modelo=declaration.modelo,
            ejercicio=declaration.ejercicio,
        ),
    )
    register_row, register_row_body = _register_row_artefact(declaration, source_url=listing_url)
    artefacts: list[FiledDeclaracionArtefact] = [
        _store_artefact(artefact_sink, observation_key=observation_key, artefact=register_row, body=register_row_body),
    ]
    casillas: tuple[ObservedCasillaValue, ...] = ()
    headers: tuple[ObservedHeaderFact, ...] = ()
    extraction_coverage: dict[str, float] = {}
    metadata = {"tipo_solicitud": declaration.tipo_solicitud or "", "observaciones": declaration.observaciones or ""}

    justificante, justificante_body = await capture_row_pdf_artefact(
        context=context,
        row_locator=row_locator,
        declaration=declaration,
        cell_index=declaration.justificante_cell_index,
        kind="justificante_pdf",
        read_policy=read_policy,
    )
    artefacts.append(
        _store_artefact(artefact_sink, observation_key=observation_key, artefact=justificante, body=justificante_body),
    )

    declaration_pdf_body: bytes | None = None
    if declaration.declaration_copy_link_text and declaration.declaration_copy_cell_index is not None:
        declaration_pdf, declaration_pdf_body = await capture_row_pdf_artefact(
            context=context,
            row_locator=row_locator,
            declaration=declaration,
            cell_index=declaration.declaration_copy_cell_index,
            kind="declaration_pdf",
            read_policy=read_policy,
        )
        artefacts.append(
            _store_artefact(
                artefact_sink,
                observation_key=observation_key,
                artefact=declaration_pdf,
                body=declaration_pdf_body,
            ),
        )

    if declaration.archive_link_text and declaration.archive_cell_index is not None:
        try:
            submitted_artefact, submitted_body = await capture_submitted_file_artefact(
                context=context,
                page=page,
                row_locator=row_locator,
                declaration=declaration,
                cell_index=declaration.archive_cell_index,
                read_policy=read_policy,
            )
        except (JustificanteFetchError, SedeNavigationError) as exc:
            metadata["submitted_file_capture_error"] = str(exc)
        else:
            submitted_artefact = _store_artefact(
                artefact_sink,
                observation_key=observation_key,
                artefact=submitted_artefact,
                body=submitted_body,
            )
            artefacts.append(submitted_artefact)
            try:
                casillas = observed_casillas_from_submitted_file(
                    snapshot=snapshot,
                    declaration=declaration,
                    body=submitted_body,
                    artefact=submitted_artefact,
                )
                extraction_coverage["submitted_file"] = _submitted_file_coverage_for_casillas(
                    snapshot=snapshot,
                    body=submitted_body,
                    casillas=casillas,
                )
                headers = observed_header_facts_from_submitted_file(snapshot=snapshot, body=submitted_body)
            except (RegistryValidationError, SedeParseError) as exc:
                _record_submitted_file_extraction_error(metadata, exc)

    if not casillas and declaration_pdf_body is not None:
        casillas = _observed_casillas_from_declaration_pdf(
            snapshot=snapshot,
            declaration=declaration,
            body=declaration_pdf_body,
        )
        extraction_coverage["declaration_pdf"] = 1.0
        if _declaration_pdf_extraction_profile_provisional(snapshot):
            metadata["declaration_pdf_extraction_profile_provisional"] = "true"
    elif not casillas and not declaration.archive_link_text and declaration_pdf_body is None:
        raise SedeParseError(
            f"AEAT declaration {declaration.expediente_id!r} did not expose submitted-file or declaration-copy data",
        )

    return FiledDeclaracionObservation(
        modelo=declaration.modelo,
        ejercicio=declaration.ejercicio,
        period=filing_period,
        expediente_id=declaration.expediente_id,
        status=declaration.estado,
        presented_at=declaration.presented_at,
        authenticated_identity=authenticated_identity,
        artefacts=tuple(artefacts),
        casillas=casillas,
        headers=headers,
        metadata=metadata,
        extraction_coverage=extraction_coverage,
        registry_snapshot_id=registry_snapshot_id(
            modelo=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
            filing_year=declaration.ejercicio,
            period=declaration.period.registry_token,
        ),
    )


async def capture_previous_filing_observations(
    session: AeatSession,
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: Period,
    settings: Settings | None = None,
    playwright: Playwright | None = None,
    artefact_sink: FiledDeclaracionArtefactSink | None = None,
) -> tuple[FiledDeclaracionObservation, ...]:
    """Capture observations required by registry previous-filing bindings.

    The binding requirements choose the source modelo, filing year, and period;
    this function selects the authoritative filed row and refuses incomplete
    observed-source coverage before returning its evidence.
    """
    from .declarations import open_declarations_register

    observations: list[FiledDeclaracionObservation] = []
    async with open_declarations_register(session, settings=settings, playwright=playwright) as register:
        for requirement in previous_filing_observation_requirements(
            revision,
            filing_year=filing_year,
            period=period.registry_token,
        ):
            source_period = requirement.periods[0]
            rows = await register.walk(modelo=requirement.source_modelo, ejercicio=requirement.filing_year)
            declaration = _select_authoritative_declaration(
                tuple(row for row in rows if row.period.registry_token == source_period),
                modelo=requirement.source_modelo,
                ejercicio=requirement.filing_year,
                period_token=source_period,
                context="previous-filing requirement",
            )
            observation = _with_derived_303_compensation_available_observation(
                await register.capture_observation(declaration, artefact_sink=artefact_sink),
            )
            observed_casillas: set[CasillaId] = {casilla.casilla_id for casilla in observation.casillas}
            missing, missing_presence_groups = source_presence_gaps(
                required_source_casilla_ids=requirement.enforced_source_casilla_ids,
                source_presence_groups=requirement.source_presence_groups,
                observed_source_casilla_ids=observed_casillas,
            )
            if missing:
                raise SedeParseError(
                    f"previous-filing requirement {requirement.source_modelo!r}/{requirement.filing_year}/"
                    f"{source_period!r} missing observed casillas {missing!r}",
                )
            if missing_presence_groups:
                raise SedeParseError(
                    f"previous-filing requirement {requirement.source_modelo!r}/{requirement.filing_year}/"
                    f"{source_period!r} is missing required source-presence groups {list(missing_presence_groups)!r}",
                )
            observations.append(observation)
    return tuple(observations)


async def capture_relation_source_observations(
    session: AeatSession,
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: Period,
    settings: Settings | None = None,
    playwright: Playwright | None = None,
    artefact_sink: FiledDeclaracionArtefactSink | None = None,
) -> tuple[FiledDeclaracionObservation, ...]:
    """Capture observations required by registry cross-model relations.

    A relation may require several source periods. Every selected filed row is
    validated for the casillas the relation declares before it is returned.
    """
    from .declarations import open_declarations_register

    required_source_casilla_ids: dict[tuple[str, int, str], set[CasillaId]] = {}
    for requirement in relation_source_requirements(revision, filing_year=filing_year, period=period.registry_token):
        for source_period in requirement.periods:
            key = (requirement.source_modelo, requirement.filing_year, source_period)
            required_source_casilla_ids.setdefault(key, set()).update(requirement.source_casilla_ids)

    observations: list[FiledDeclaracionObservation] = []
    async with open_declarations_register(session, settings=settings, playwright=playwright) as register:
        for (modelo, source_year, source_period), source_casilla_ids in sorted(required_source_casilla_ids.items()):
            rows = await register.walk(modelo=modelo, ejercicio=source_year)
            declaration = _select_authoritative_declaration(
                tuple(row for row in rows if row.period.registry_token == source_period),
                modelo=modelo,
                ejercicio=source_year,
                period_token=source_period,
                context="relation source requirement",
            )
            observation = _with_derived_303_compensation_available_observation(
                await register.capture_observation(declaration, artefact_sink=artefact_sink),
            )
            observed_casillas: set[CasillaId] = {casilla.casilla_id for casilla in observation.casillas}
            missing = sorted(source_casilla_ids.difference(observed_casillas))
            if missing:
                raise SedeParseError(
                    f"relation source requirement {modelo!r}/{source_year}/{source_period!r} "
                    f"missing observed casillas {missing!r}",
                )
            observations.append(observation)
    return tuple(observations)


def _select_authoritative_declaration(
    declarations: tuple[Declaracion, ...],
    *,
    modelo: str,
    ejercicio: int,
    period_token: str,
    context: str,
) -> Declaracion:
    """Select the latest accepted register row for one filed period."""
    if not declarations:
        raise SedeParseError(f"{context} {modelo!r}/{ejercicio}/{period_token!r} found no filed declaration")
    active = tuple(row for row in declarations if row.estado.upper() == "ALTA")
    return max(active or declarations, key=lambda row: (row.presented_at, row.expediente_id))


__all__ = [
    "capture_filed_declaration_observation",
    "capture_previous_filing_observations",
    "capture_relation_source_observations",
]
