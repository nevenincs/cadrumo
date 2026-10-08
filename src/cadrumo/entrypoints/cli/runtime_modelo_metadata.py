"""CLI boundary for exact-profile registered modelo work metadata actions."""

from __future__ import annotations

import time
from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ...adapters.local_runtime.modelo_metadata import (
    ModeloMetadataRunError,
    read_modelo_work_metadata,
    run_modelo_metadata_mutation,
)
from ...application.modelo.metadata_read_operation import ModeloWorkMetadataRequest
from ...application.modelo.work_addressing import ModeloWorkAddressNotFoundError
from ...application.modelo.work_change_contracts import (
    ModeloWorkDiscardBaseline,
    ModeloWorkDiscardPublicResultV2,
    ModeloWorkDiscardRequest,
    ModeloWorkRenamePublicResultV2,
    ModeloWorkRenameRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import remaining_budget
from ...application.user_profile.access_contracts import AccessDenialCode
from ...core.bucket_pointer import resolve_active_bucket_id
from ...domain.modelos.work_unit import WorkUnit
from ._modelo_behavior_support import work_address_for_cli
from ._modelo_cli_support import selector_bad_parameter
from .common import no_active_profile_refusal
from .errors import CliRefusedBoundaryError
from .runtime_profile_binding import require_profile_client

_TIMEOUT_SECONDS = 120.0


def _client(ctx: typer.Context, *, expected_profile_id: UUID | None = None) -> RuntimeFrontendClient:
    if expected_profile_id is not None:
        return require_profile_client(ctx, expected_profile_id=expected_profile_id)
    target = resolve_active_bucket_id()
    if target is None:
        raise no_active_profile_refusal()
    return require_profile_client(ctx, expected_profile_id=UUID(target))


def _request(
    client: RuntimeFrontendClient,
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
) -> ModeloWorkMetadataRequest:
    if bucket_id is not None and bucket_id.strip() and bucket_id.strip() != str(client.profile_id):
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    try:
        address = work_address_for_cli(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
        )
    except ModeloWorkAddressNotFoundError as error:
        raise selector_bad_parameter(error) from error
    return ModeloWorkMetadataRequest(
        profile_id=client.profile_id,
        work_unit_id=address.work_unit_id or address.operator_work_unit_id,
        modelo=address.modelo,
        year=address.filing_year,
        period=PublicPeriod.from_period(address.period) if address.period is not None else None,
        revision=address.registry_revision_id,
    )


def _read_unit(
    client: RuntimeFrontendClient,
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    deadline: float,
) -> WorkUnit:
    request = _request(
        client,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    observed = read_modelo_work_metadata(client, request, timeout=remaining_budget(deadline))
    return observed.projection.unit.to_work_unit()


def _refuse(error: Exception) -> CliRefusedBoundaryError:
    if isinstance(error, ModeloMetadataRunError):
        return CliRefusedBoundaryError(error.reason, context=error.context)
    if isinstance(error, RuntimeFrontendRefusedError):
        return CliRefusedBoundaryError(error.reason, context=error.context)
    if isinstance(error, RuntimeRefusalError):
        return CliRefusedBoundaryError(error.reason.value, context={"reason": error.reason.value})
    raise TypeError("unsupported modelo metadata refusal")


def read_modelo_work_unit(
    ctx: typer.Context,
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    expected_profile_id: UUID | None = None,
) -> WorkUnit:
    """Read one CLI-selected unit through its exact bound runtime profile."""
    client = _client(ctx, expected_profile_id=expected_profile_id)
    try:
        return _read_unit(
            client,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
            deadline=time.monotonic() + _TIMEOUT_SECONDS,
        )
    except (ModeloMetadataRunError, RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
        raise _refuse(error) from error


def rename_modelo_work(
    ctx: typer.Context,
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    name: str,
    actor: str | None,
) -> WorkUnit:
    """Return the actual writer snapshot for one selected registered rename."""
    client = _client(ctx)
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    try:
        unit = _read_unit(
            client,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
            deadline=deadline,
        )
        completed = run_modelo_metadata_mutation(
            client,
            ModeloWorkRenameRequest(
                work_unit_id=unit.work_unit_id,
                new_name=name,
                observed_name=unit.name,
                observed_updated_at=unit.updated_at,
                actor=actor or str(client.profile_id),
            ),
            timeout=remaining_budget(deadline),
        )
        result = completed.projection
        if not isinstance(result, ModeloWorkRenamePublicResultV2):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return result.unit.to_work_unit()
    except (ModeloMetadataRunError, RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
        raise _refuse(error) from error


def discard_modelo_work(
    ctx: typer.Context,
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    reason: str | None,
    actor: str | None,
) -> WorkUnit:
    """Bind one observed baseline to the canonical discard writer."""
    client = _client(ctx)
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    try:
        unit = _read_unit(
            client,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
            deadline=deadline,
        )
        completed = run_modelo_metadata_mutation(
            client,
            ModeloWorkDiscardRequest(
                baseline=ModeloWorkDiscardBaseline(
                    work_unit_id=unit.work_unit_id,
                    name=unit.name,
                    observed_updated_at=unit.updated_at,
                ),
                reason=reason,
                actor=actor or str(client.profile_id),
            ),
            timeout=remaining_budget(deadline),
        )
        result = completed.projection
        if not isinstance(result, ModeloWorkDiscardPublicResultV2):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return result.unit.to_work_unit()
    except (ModeloMetadataRunError, RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
        raise _refuse(error) from error


__all__ = ["discard_modelo_work", "read_modelo_work_unit", "rename_modelo_work"]
