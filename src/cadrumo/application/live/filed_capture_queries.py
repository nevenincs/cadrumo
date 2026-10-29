"""Filed capture query planning and register reads.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Sequence
from typing import TYPE_CHECKING

from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalError

from ...core.async_cleanup import has_async_cleanup_failure
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.schema import (
    ModeloRevision,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .errors import LiveApplicationInputError, LiveIvaSurfaceTimeoutError
from .filed_data import (
    BulkFiledDataListingReport,
    FiledDataListingReport,
    FiledDataListingRow,
    filed_data_listing_row,
)
from .filed_data_ports import (
    FiledDataCapturePort,
    FiledEffectGuard,
    FiledRegisterDeclarationProtocol,
)
from .remote_state_models import (
    FiledDataCaptureFailureRow,
)
from .remote_state_outcomes import bounded_context_text
from .session import SessionWriteReporter

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def filed_data_capture_failure_row(
    *,
    modelo: str,
    year: int,
    error: BaseException,
    declaration: FiledRegisterDeclarationProtocol | None = None,
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


def _filed_capture_revisions_for_year(
    revisions: Sequence[ModeloRevision],
    *,
    year: int,
) -> tuple[ModeloRevision, ...]:
    """Return this modelo's revisions that cover the requested filing year."""
    return tuple(revision for revision in revisions if revision.period_selector.includes_year(year))


def _declares_filed_declarations_read_surface(revisions: Sequence[ModeloRevision]) -> bool:
    """Whether a covering registry revision authorizes the declarations-register read."""
    return any(
        ref.surface == "authenticated_read_surface" and ref.id.endswith("filed-declarations-read")
        for revision in revisions
        for ref in revision.live_cross_references
    )


def _registered_modelo_revisions(
    modelo: str,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[ModeloRevision, ...] | None:
    """Load the explicitly enumerated revisions for one registry modelo."""
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return _registered_modelo_revisions(modelo, operation=indexed_operation)
    try:
        directory = operation.modelo_directory(modelo)
        revisions = tuple(operation.revision(modelo, metadata.id) for metadata in directory.revisions)
    except (RegistrySnapshotError, ValueError):
        return None
    return revisions or None


def filed_capture_unsupported_reason(
    *,
    modelo: str,
    year: int,
    operation: PinnedAuthorityOperation | None = None,
) -> str | None:
    """Explain why the registry does not authorize this register query."""
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return filed_capture_unsupported_reason(modelo=modelo, year=year, operation=indexed_operation)
    revisions = _registered_modelo_revisions(modelo, operation=operation)
    if revisions is None:
        return f"registry has no modelo definition for {modelo!r}"
    revisions = _filed_capture_revisions_for_year(revisions, year=year)
    if not revisions:
        return f"registry has no revision for modelo {modelo!r} filing year {year}"
    if _declares_filed_declarations_read_surface(revisions):
        return None
    # States only what is knowable here. Whether AEAT serves a modelo at the
    # consulta view is not derivable from our own registry's silence, and the
    # previous wording asserted it was, so an operator read a claim about AEAT's
    # coverage that nothing in this tree supports. The register's own modelo
    # combobox is the authority, and the discovery verb reads it.
    return (
        f"modelo {modelo!r} declares no authenticated filed-declarations read surface in this "
        "deployment's registry, so the declarations register was not queried for it. Whether AEAT "
        "serves this modelo at the consulta view is not recorded here. Run "
        "`aeat app live filed discover` to read the register's own modelo list and settle it"
    )


def plan_filed_capture_queries(
    resolved_modelos: Sequence[str],
    *,
    year_from: int,
    year_to: int,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[list[tuple[str, int]], list[FiledDataCaptureFailureRow]]:
    """Plan the ``(modelo, year)`` pairs a bulk filed-data walk should query.

    Shared by :func:`list_filed_data_bulk` and :func:`capture_filed_data_bulk`:
    walks each requested modelo across the year range newest-first and diverts
    any pair the declarations register cannot serve into a typed unsupported
    failure row instead of querying it, so an unserviceable modelo/year is
    reported rather than silently dropped.

    Returns:
        The queryable ``(modelo, year)`` pairs and the unsupported failure rows,
        each in walk order.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return plan_filed_capture_queries(
                resolved_modelos,
                year_from=year_from,
                year_to=year_to,
                operation=indexed_operation,
            )
    query_pairs: list[tuple[str, int]] = []
    failures: list[FiledDataCaptureFailureRow] = []
    for code in resolved_modelos:
        for year in range(year_to, year_from - 1, -1):
            unsupported_reason = filed_capture_unsupported_reason(modelo=code, year=year, operation=operation)
            if unsupported_reason is not None:
                failures.append(
                    _unsupported_filed_capture_failure_row(modelo=code, year=year, reason=unsupported_reason),
                )
                continue
            query_pairs.append((code, year))
    return query_pairs, failures


async def await_filed_register_walk(
    awaitable: Awaitable[tuple[FiledRegisterDeclarationProtocol, ...]],
    *,
    modelo: str,
    year: int,
    timeout_ms: int,
) -> tuple[FiledRegisterDeclarationProtocol, ...]:
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


async def walk_or_failure_row(
    awaitable: Awaitable[tuple[FiledRegisterDeclarationProtocol, ...]],
    *,
    modelo: str,
    year: int,
    timeout_ms: int,
    failures: list[FiledDataCaptureFailureRow],
) -> tuple[FiledRegisterDeclarationProtocol, ...] | None:
    """Absorb one modelo/year register query's failure into a row, or return its rows.

    Takes the walk awaitable rather than the register that produces it: the
    register was only ever used to build this one coroutine, so the narrower
    parameter drops a dependency the helper never needed and lets the absorption
    arm be exercised with a real coroutine, the way the sibling
    :func:`await_filed_register_walk` already is.

    Shared bulk-path arm behind :func:`list_filed_data_bulk` and
    :func:`capture_filed_data_bulk`: on a remote walk failure the exception is folded
    into ``failures`` as a :class:`FiledDataCaptureFailureRow` and ``None`` is
    returned so the caller can skip the pair.

    A register page whose grid declares more records than it rendered is refused
    by the walker rather than returned short, and that refusal arrives here like
    any other walk failure — one pair reported as failed while the sweep
    continues. Truncation deliberately gets no bulk-level mechanism of its own:
    a second reporting channel would let a partial capture be counted as a
    success on one path and a failure on the other.
    """
    try:
        return await await_filed_register_walk(
            awaitable,
            modelo=modelo,
            year=year,
            timeout_ms=timeout_ms,
        )
    except (ProfileAccessRefusedError, AutomationCustodyError, RefusalError):
        raise
    except Exception as exc:
        if has_async_cleanup_failure(exc):
            raise
        failures.append(filed_data_capture_failure_row(modelo=modelo, year=year, error=exc))
        return None


async def list_filed_data(
    *,
    filed_data_port: FiledDataCapturePort,
    modelo: str,
    year_from: int,
    year_to: int,
    authority_operation: PinnedAuthorityOperation | None = None,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
) -> FiledDataListingReport:
    """List declarations via AEAT and return a :class:`FiledDataListingReport`."""
    if year_from > year_to:
        raise LiveApplicationInputError(
            translated_message="live.errors.year_range_invalid",
        )

    rows: list[FiledDataListingRow] = []
    register_scope = (
        filed_data_port.open_register(
            operation="live-expedientes-read",
            authority_operation=authority_operation,
            effect_guard=effect_guard,
            on_session_write=on_session_write,
        )
        if authority_operation is not None
        else filed_data_port.open_register(
            operation="live-expedientes-read", effect_guard=effect_guard, on_session_write=on_session_write
        )
    )
    async with register_scope as register:
        for year in range(year_to, year_from - 1, -1):
            declarations = await await_filed_register_walk(
                register.walk(modelo=modelo, ejercicio=year),
                modelo=modelo,
                year=year,
                timeout_ms=register.walk_timeout_ms,
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
    filed_data_port: FiledDataCapturePort,
    year_from: int,
    year_to: int,
    modelos: tuple[str, ...] | None = None,
    operation: PinnedAuthorityOperation | None = None,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
) -> BulkFiledDataListingReport:
    """List filed declarations across modelos with one authenticated register session.

    Args:
        year_from: First filing year to query.
        year_to: Last filing year to query.
        modelos: Modelo codes to walk; every registry modelo when omitted.
        operation: Caller-held generation-pinned authority operation; opened from
            the indexed bundled authority when omitted.
        filed_data_port: Composed register acquisition capability. Its outer
            implementation owns session and browser lifecycles.
        effect_guard: Commit guard for encrypted session writes during authentication.
        on_session_write: Effect receipt callback for a published session write.

    Returns:
        A :class:`BulkFiledDataListingReport` of the per-modelo rows and failures.
    """
    if year_from > year_to:
        raise LiveApplicationInputError(
            translated_message="live.errors.year_range_invalid",
        )

    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return await list_filed_data_bulk(
                filed_data_port=filed_data_port,
                year_from=year_from,
                year_to=year_to,
                modelos=modelos,
                operation=indexed_operation,
                effect_guard=effect_guard,
                on_session_write=on_session_write,
            )
    resolved_modelos = modelos if modelos is not None else operation.modelo_ids()
    rows: list[FiledDataListingRow] = []
    query_pairs, failures = plan_filed_capture_queries(
        resolved_modelos,
        year_from=year_from,
        year_to=year_to,
        operation=operation,
    )

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

    async with filed_data_port.open_register(
        operation="live-expedientes-read",
        authority_operation=operation,
        effect_guard=effect_guard,
        on_session_write=on_session_write,
    ) as register:
        for code, year in query_pairs:
            declarations = await walk_or_failure_row(
                register.walk(modelo=code, ejercicio=year),
                modelo=code,
                year=year,
                timeout_ms=register.walk_timeout_ms,
                failures=failures,
            )
            if declarations is None:
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
