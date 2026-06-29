"""Filed-declaration capture services for live AEAT workflows.

The listing helpers read AEAT declaration-register rows without downloading
artefacts. The capture helpers download the selected filed-declaration artefacts
through the authenticated Sede adapter, persist encrypted
:class:`FiledDeclaracionObservation` payloads and artefacts, promote extracted
casillas into registry-grounded calculation observations, and attempt to stamp
matching current :class:`ModeloRecord` filings with live
:class:`ExternalEvidence`.

Source capture resolves a :class:`ValidatedRegistryAuthority` snapshot before
asking the Sede adapter which prior declarations a target filing needs, so
cross-period inputs remain registry-authored rather than adapter-inferred.

See Also:
    :func:`aeat.application.live._session.active_verified_session`
        Enforces the read-only live gate before the register walker is opened.
    :func:`aeat.application.live._filed_observation_persistence.persist_latest_filed_calculation_observations`
        Persists the latest captured filed observations as calculation-history
        evidence.
    :func:`aeat.application.live._filed_observation_persistence.enroll_filed_justificante_evidence`
        Persists matching justificante metadata and stamps current filing
        records when the receipt matches.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path

from ...adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    capture_previous_filing_observations,
    capture_relation_source_observations,
    open_declarations_register,
    shared_playwright,
)
from ...core import Period, require_active_bucket_id
from ...core.resources import bundled_path, resources
from ...domain.calculations.registry import ValidatedRegistryAuthority
from ._errors import LiveApplicationInputError, LiveIvaSurfaceTimeoutError
from ._filed_data import (
    BulkFiledDataListingReport,
    FiledDataListingReport,
    FiledDataListingRow,
    filed_data_listing_row,
    select_declarations_for_capture,
)
from ._filed_observation_persistence import (
    _filed_observation_identity_key,
    enroll_filed_justificante_evidence,
    persist_latest_filed_calculation_observations,
)
from ._remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    SourceFiledDataCaptureReport,
)
from ._remote_state_outcomes import bounded_context_text
from ._session import active_verified_session


def filed_data_capture_failure_row(
    *,
    modelo: str,
    year: int,
    error: BaseException,
    declaration: Declaracion | None = None,
) -> FiledDataCaptureFailureRow:
    """Map one failed capture into a :class:`FiledDataCaptureFailureRow`."""
    failed_period = declaration.period if declaration is not None else None
    return FiledDataCaptureFailureRow(
        modelo=declaration.modelo if declaration is not None else modelo,
        year=declaration.ejercicio if declaration is not None else year,
        period=failed_period,
        expediente_id=declaration.expediente_id if declaration is not None else None,
        error_type=error.__class__.__name__,
        message=bounded_context_text(error),
    )


def _unsupported_filed_capture_failure_row(
    *,
    modelo: str,
    year: int,
    reason: str,
) -> FiledDataCaptureFailureRow:
    return FiledDataCaptureFailureRow(
        modelo=modelo,
        year=year,
        error_type="LiveApplicationInputError",
        message=reason,
    )


def _filed_capture_unsupported_reason(*, modelo: str, year: int) -> str | None:
    registry_modelos = {str(definition.id): definition for definition in resources().modelos.all()}
    definition = registry_modelos.get(modelo)
    if definition is None:
        return f"registry has no modelo definition for {modelo!r}"
    revisions = tuple(
        revision for revision in definition.revisions.values() if revision.period_selector.includes_year(year)
    )
    if not revisions:
        return f"registry has no revision for modelo {modelo!r} filing year {year}"
    filed_read_refs = tuple(
        ref
        for revision in revisions
        for ref in revision.live_cross_references
        if ref.surface == "authenticated_read_surface" and ref.id.endswith("filed-declarations-read")
    )
    if filed_read_refs:
        return None
    return (
        f"AEAT declarations register does not offer modelo {modelo!r}; "
        "registry revision declares no filed-declarations live read surface"
    )


async def _await_filed_register_walk(
    awaitable: Awaitable[tuple[Declaracion, ...]],
    *,
    modelo: str,
    year: int,
    timeout_ms: int,
) -> tuple[Declaracion, ...]:
    """Bound one AEAT filed-register modelo/year query."""
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_ms / 1000)
    except TimeoutError as exc:
        raise LiveIvaSurfaceTimeoutError(
            f"live filed declaration register query for modelo {modelo} year {year} did not complete "
            f"within {timeout_ms} ms",
            surface="filed_declarations_register_walk",
            timeout_ms=timeout_ms,
            progress_context={"modelo": modelo, "year": year},
        ) from exc


async def list_filed_data(
    *,
    modelo: str,
    year_from: int,
    year_to: int,
) -> FiledDataListingReport:
    """List declarations via AEAT and return a :class:`FiledDataListingReport`."""
    if year_from > year_to:
        raise LiveApplicationInputError(
            message="from-year must be less than or equal to to-year",
            translated_message="live.errors.year_range_invalid",
        )

    session, settings = await active_verified_session(operation="live-expedientes-read")
    walk_timeout_ms = settings.aeat_live_filed_register_walk_timeout_ms
    rows: list[FiledDataListingRow] = []
    async with (
        shared_playwright(session) as playwright,
        open_declarations_register(
            session,
            settings=settings,
            playwright=playwright,
        ) as register,
    ):
        for year in range(year_to, year_from - 1, -1):
            declarations = await _await_filed_register_walk(
                register.walk(modelo=modelo, ejercicio=year),
                modelo=modelo,
                year=year,
                timeout_ms=walk_timeout_ms,
            )
            rows.extend(filed_data_listing_row(declaration) for declaration in declarations)
    return FiledDataListingReport(
        modelo=modelo,
        year_from=year_from,
        year_to=year_to,
        row_count=len(rows),
        rows=tuple(rows),
    )


async def list_filed_data_bulk(
    *,
    year_from: int,
    year_to: int,
    modelos: tuple[str, ...] | None = None,
) -> BulkFiledDataListingReport:
    """List filed declarations across modelos with one authenticated register session.

    Returns:
        A :class:`BulkFiledDataListingReport` of the per-modelo rows and failures.
    """
    if year_from > year_to:
        raise LiveApplicationInputError(
            message="from-year must be less than or equal to to-year",
            translated_message="live.errors.year_range_invalid",
        )

    resolved_modelos = modelos if modelos is not None else tuple(str(m.id) for m in resources().modelos.all())
    rows: list[FiledDataListingRow] = []
    failures: list[FiledDataCaptureFailureRow] = []
    query_pairs: list[tuple[str, int]] = []
    for code in resolved_modelos:
        for year in range(year_to, year_from - 1, -1):
            unsupported_reason = _filed_capture_unsupported_reason(modelo=code, year=year)
            if unsupported_reason is not None:
                failures.append(
                    _unsupported_filed_capture_failure_row(modelo=code, year=year, reason=unsupported_reason),
                )
                continue
            query_pairs.append((code, year))

    if not query_pairs:
        return BulkFiledDataListingReport(
            modelos=tuple(resolved_modelos),
            year_from=year_from,
            year_to=year_to,
            row_count=0,
            failed_count=len(failures),
            rows=(),
            failures=tuple(failures),
        )

    session, settings = await active_verified_session(operation="live-expedientes-read")
    walk_timeout_ms = settings.aeat_live_filed_register_walk_timeout_ms
    async with (
        shared_playwright(session) as playwright,
        open_declarations_register(
            session,
            settings=settings,
            playwright=playwright,
        ) as register,
    ):
        for code, year in query_pairs:
            try:
                declarations = await _await_filed_register_walk(
                    register.walk(modelo=code, ejercicio=year),
                    modelo=code,
                    year=year,
                    timeout_ms=walk_timeout_ms,
                )
            except Exception as exc:
                failures.append(filed_data_capture_failure_row(modelo=code, year=year, error=exc))
                continue
            rows.extend(filed_data_listing_row(declaration) for declaration in declarations)

    return BulkFiledDataListingReport(
        modelos=tuple(resolved_modelos),
        year_from=year_from,
        year_to=year_to,
        row_count=len(rows),
        failed_count=len(failures),
        rows=tuple(rows),
        failures=tuple(failures),
    )


async def capture_filed_data(
    *,
    modelo: str,
    year: int,
    output_root: Path,
    period: Period | None = None,
    expediente_id: str | None = None,
    limit: int | None = None,
) -> FiledDataCaptureReport:
    """Capture filed-declaration artefacts and return a :class:`FiledDataCaptureReport`.

    The report accounts for persisted observation manifests, encrypted artefact
    references, saved justificante CSVs, stamped
    :class:`aeat.domain.modelos.ModeloRecord` ids, conflicts, and calculation
    observation keys produced from the captured AEAT rows.
    """
    session, settings = await active_verified_session()
    walk_timeout_ms = settings.aeat_live_filed_register_walk_timeout_ms
    store = FiledDeclaracionObservationStore(output_root)
    observation_paths: list[str] = []
    artefact_refs: list[str] = []
    justificante_csvs: list[str] = []
    filing_record_ids: list[str] = []
    conflicting_filing_record_ids: list[str] = []
    observations_for_calculation: list[FiledDeclaracionObservation] = []
    justificante_csvs_by_observation: dict[tuple[str, int, str, str], tuple[str, ...]] = {}
    casilla_count = 0
    bucket_id = require_active_bucket_id()

    async with (
        shared_playwright(session) as playwright,
        open_declarations_register(
            session,
            playwright=playwright,
        ) as register,
    ):
        declarations = await _await_filed_register_walk(
            register.walk(modelo=modelo, ejercicio=year),
            modelo=modelo,
            year=year,
            timeout_ms=walk_timeout_ms,
        )
        selected = select_declarations_for_capture(
            declarations,
            period=period,
            expediente_id=expediente_id,
            limit=limit,
        )
        for declaration in selected:
            observation = await register.capture_observation(
                declaration,
                artefact_sink=store.persist_artefact,
            )
            manifest_path = store.persist_observation(observation)
            observation_paths.append(capture_report_path(manifest_path, output_root=output_root))
            artefact_refs.extend(
                storage_ref
                for artefact in observation.artefacts
                for storage_ref in (artefact.storage_ref,)
                if storage_ref is not None
            )
            enrollment = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)
            justificante_csvs.extend(enrollment.justificante_csvs)
            justificante_csvs_by_observation[_filed_observation_identity_key(observation)] = (
                enrollment.justificante_csvs
            )
            filing_record_ids.extend(enrollment.filing_record_ids)
            conflicting_filing_record_ids.extend(enrollment.conflicting_filing_record_ids)
            casilla_count += len(observation.casillas)
            observations_for_calculation.append(observation)

    calculation_observation_keys = persist_latest_filed_calculation_observations(
        tuple(observations_for_calculation),
        justificante_csvs_by_observation=justificante_csvs_by_observation,
    )

    return FiledDataCaptureReport(
        output_root=str(output_root),
        modelo=modelo,
        year=year,
        captured_count=len(observation_paths),
        observation_paths=tuple(observation_paths),
        artefact_refs=tuple(artefact_refs),
        justificante_metadata_count=len(tuple(dict.fromkeys(justificante_csvs))),
        justificante_csvs=tuple(dict.fromkeys(justificante_csvs)),
        filing_evidence_stamped_count=len(tuple(dict.fromkeys(filing_record_ids))),
        filing_record_ids=tuple(dict.fromkeys(filing_record_ids)),
        filing_evidence_conflict_count=len(tuple(dict.fromkeys(conflicting_filing_record_ids))),
        filing_evidence_conflict_record_ids=tuple(dict.fromkeys(conflicting_filing_record_ids)),
        casilla_count=casilla_count,
        calculation_observation_count=len(calculation_observation_keys),
        calculation_observation_keys=tuple(calculation_observation_keys),
    )


async def capture_filed_data_bulk(
    *,
    year_from: int,
    year_to: int,
    output_root: Path,
    modelos: tuple[str, ...] | None = None,
    limit: int | None = None,
) -> BulkFiledDataCaptureReport:
    """Capture filed declarations across a year range and return a :class:`BulkFiledDataCaptureReport`.

    Unsupported modelo/year pairs are recorded as failures before live contact.
    Supported pairs share one authenticated register session and then follow the
    same persistence, justificante enrolment, and calculation-observation path as
    :func:`capture_filed_data`.
    """
    if year_from > year_to:
        raise LiveApplicationInputError(
            message="from-year must be less than or equal to to-year",
            translated_message="live.errors.year_range_invalid",
        )

    resolved_modelos = modelos if modelos is not None else tuple(str(m.id) for m in resources().modelos.all())
    store = FiledDeclaracionObservationStore(output_root)
    observation_paths: list[str] = []
    artefact_refs: list[str] = []
    justificante_csvs: list[str] = []
    filing_record_ids: list[str] = []
    conflicting_filing_record_ids: list[str] = []
    observations_for_calculation: list[FiledDeclaracionObservation] = []
    justificante_csvs_by_observation: dict[tuple[str, int, str, str], tuple[str, ...]] = {}
    failures: list[FiledDataCaptureFailureRow] = []
    casilla_count = 0
    query_pairs: list[tuple[str, int]] = []
    for code in resolved_modelos:
        for year in range(year_to, year_from - 1, -1):
            unsupported_reason = _filed_capture_unsupported_reason(modelo=code, year=year)
            if unsupported_reason is not None:
                failures.append(
                    _unsupported_filed_capture_failure_row(modelo=code, year=year, reason=unsupported_reason),
                )
                continue
            query_pairs.append((code, year))

    if not query_pairs:
        return BulkFiledDataCaptureReport(
            output_root=str(output_root),
            modelos=tuple(resolved_modelos),
            year_from=year_from,
            year_to=year_to,
            captured_count=0,
            failed_count=len(failures),
            observation_paths=(),
            artefact_refs=(),
            justificante_metadata_count=0,
            justificante_csvs=(),
            filing_evidence_stamped_count=0,
            filing_record_ids=(),
            filing_evidence_conflict_count=0,
            filing_evidence_conflict_record_ids=(),
            casilla_count=0,
            calculation_observation_count=0,
            calculation_observation_keys=(),
            failures=tuple(failures),
        )

    session, settings = await active_verified_session(operation="live-expedientes-read")
    walk_timeout_ms = settings.aeat_live_filed_register_walk_timeout_ms
    bucket_id = require_active_bucket_id()

    async with (
        shared_playwright(session) as playwright,
        open_declarations_register(
            session,
            settings=settings,
            playwright=playwright,
        ) as register,
    ):
        for code, year in query_pairs:
            try:
                declarations = await _await_filed_register_walk(
                    register.walk(modelo=code, ejercicio=year),
                    modelo=code,
                    year=year,
                    timeout_ms=walk_timeout_ms,
                )
            except Exception as exc:
                failures.append(filed_data_capture_failure_row(modelo=code, year=year, error=exc))
                continue
            if limit is not None:
                remaining = limit - len(observation_paths)
                if remaining <= 0:
                    break
                declarations = declarations[:remaining]
            for declaration in declarations:
                try:
                    observation = await register.capture_observation(
                        declaration,
                        artefact_sink=store.persist_artefact,
                    )
                except Exception as exc:
                    failures.append(
                        filed_data_capture_failure_row(
                            modelo=code,
                            year=year,
                            declaration=declaration,
                            error=exc,
                        ),
                    )
                    continue
                manifest_path = store.persist_observation(observation)
                observation_paths.append(capture_report_path(manifest_path, output_root=output_root))
                artefact_refs.extend(
                    storage_ref
                    for artefact in observation.artefacts
                    for storage_ref in (artefact.storage_ref,)
                    if storage_ref is not None
                )
                enrollment = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)
                justificante_csvs.extend(enrollment.justificante_csvs)
                justificante_csvs_by_observation[_filed_observation_identity_key(observation)] = (
                    enrollment.justificante_csvs
                )
                filing_record_ids.extend(enrollment.filing_record_ids)
                conflicting_filing_record_ids.extend(enrollment.conflicting_filing_record_ids)
                casilla_count += len(observation.casillas)
                observations_for_calculation.append(observation)
            if limit is not None and len(observation_paths) >= limit:
                break

    calculation_observation_keys = persist_latest_filed_calculation_observations(
        tuple(observations_for_calculation),
        justificante_csvs_by_observation=justificante_csvs_by_observation,
    )
    return BulkFiledDataCaptureReport(
        output_root=str(output_root),
        modelos=tuple(resolved_modelos),
        year_from=year_from,
        year_to=year_to,
        captured_count=len(observation_paths),
        failed_count=len(failures),
        observation_paths=tuple(observation_paths),
        artefact_refs=tuple(artefact_refs),
        justificante_metadata_count=len(tuple(dict.fromkeys(justificante_csvs))),
        justificante_csvs=tuple(dict.fromkeys(justificante_csvs)),
        filing_evidence_stamped_count=len(tuple(dict.fromkeys(filing_record_ids))),
        filing_record_ids=tuple(dict.fromkeys(filing_record_ids)),
        filing_evidence_conflict_count=len(tuple(dict.fromkeys(conflicting_filing_record_ids))),
        filing_evidence_conflict_record_ids=tuple(dict.fromkeys(conflicting_filing_record_ids)),
        casilla_count=casilla_count,
        calculation_observation_count=len(calculation_observation_keys),
        calculation_observation_keys=tuple(calculation_observation_keys),
        failures=tuple(failures),
    )


async def capture_source_filed_data(
    *,
    modelo: str,
    year: int,
    period: Period,
    output_root: Path,
    registry_root: Path | None = None,
    source_root: Path | None = None,
) -> SourceFiledDataCaptureReport:
    """Capture source observations and return a :class:`SourceFiledDataCaptureReport`."""
    session, settings = await active_verified_session()
    if registry_root is None and source_root is None:
        authority = resources().modelos.authority
    else:
        authority = ValidatedRegistryAuthority.load(
            registry_root or bundled_path("registry", "aeat"),
            source_root=source_root or bundled_path(),
        )
    snapshot = authority.snapshot(
        modelo,
        filing_year=year,
        period=period.registry_token,
    )
    store = FiledDeclaracionObservationStore(output_root)
    observation_paths: list[str] = []
    artefact_refs: list[str] = []
    justificante_csvs: list[str] = []
    filing_record_ids: list[str] = []
    conflicting_filing_record_ids: list[str] = []
    observations_for_calculation: list[FiledDeclaracionObservation] = []
    justificante_csvs_by_observation: dict[tuple[str, int, str, str], tuple[str, ...]] = {}
    casilla_count = 0
    seen: set[tuple[str, int, str, str]] = set()
    bucket_id = require_active_bucket_id()

    async with shared_playwright(session) as playwright:
        observations = (
            await capture_previous_filing_observations(
                session,
                snapshot.revision,
                filing_year=year,
                period=period,
                settings=settings,
                playwright=playwright,
                artefact_sink=store.persist_artefact,
            )
        ) + (
            await capture_relation_source_observations(
                session,
                snapshot.revision,
                filing_year=year,
                period=period,
                settings=settings,
                playwright=playwright,
                artefact_sink=store.persist_artefact,
            )
        )
    for observation in observations:
        key = (
            observation.modelo,
            observation.ejercicio,
            observation.period.registry_token,
            observation.expediente_id,
        )
        if key in seen:
            continue
        seen.add(key)
        manifest_path = store.persist_observation(observation)
        observation_paths.append(capture_report_path(manifest_path, output_root=output_root))
        artefact_refs.extend(
            storage_ref
            for artefact in observation.artefacts
            for storage_ref in (artefact.storage_ref,)
            if storage_ref is not None
        )
        enrollment = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)
        justificante_csvs.extend(enrollment.justificante_csvs)
        justificante_csvs_by_observation[_filed_observation_identity_key(observation)] = enrollment.justificante_csvs
        filing_record_ids.extend(enrollment.filing_record_ids)
        conflicting_filing_record_ids.extend(enrollment.conflicting_filing_record_ids)
        casilla_count += len(observation.casillas)
        observations_for_calculation.append(observation)

    calculation_observation_keys = persist_latest_filed_calculation_observations(
        tuple(observations_for_calculation),
        justificante_csvs_by_observation=justificante_csvs_by_observation,
    )

    return SourceFiledDataCaptureReport(
        output_root=str(output_root),
        target_modelo=modelo,
        target_year=year,
        target_period=period,
        captured_count=len(observation_paths),
        observation_paths=tuple(observation_paths),
        artefact_refs=tuple(artefact_refs),
        justificante_metadata_count=len(tuple(dict.fromkeys(justificante_csvs))),
        justificante_csvs=tuple(dict.fromkeys(justificante_csvs)),
        filing_evidence_stamped_count=len(tuple(dict.fromkeys(filing_record_ids))),
        filing_record_ids=tuple(dict.fromkeys(filing_record_ids)),
        filing_evidence_conflict_count=len(tuple(dict.fromkeys(conflicting_filing_record_ids))),
        filing_evidence_conflict_record_ids=tuple(dict.fromkeys(conflicting_filing_record_ids)),
        casilla_count=casilla_count,
        calculation_observation_count=len(calculation_observation_keys),
        calculation_observation_keys=tuple(calculation_observation_keys),
    )


def capture_report_path(path: Path, *, output_root: Path) -> str:
    """Return a stable report path relative to the configured output root when possible."""
    try:
        return path.relative_to(output_root).as_posix()
    except ValueError:
        return str(path)


__all__ = [
    "capture_filed_data",
    "capture_filed_data_bulk",
    "capture_report_path",
    "capture_source_filed_data",
    "filed_data_capture_failure_row",
    "list_filed_data",
    "list_filed_data_bulk",
]
