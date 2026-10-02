"""CLI bridges for exact-profile reads of encrypted local verify observations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.live.verify import VerifySurface
from ...application.live.verify_read_operation import (
    VERIFY_LATEST_DEFINITION_ID,
    VERIFY_LIST_DEFINITION_ID,
    VERIFY_VIEW_DEFINITION_ID,
    VerifyLatestPublicResultV1,
    VerifyLatestRequest,
    VerifyListPublicResultV1,
    VerifyListRequest,
    VerifyObservationPublicV1,
    VerifyViewRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.identity_check_verdict import IdentityCheckVerdict
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class VerifyListRead:
    """Keep the settled receipt with the exact-profile verify inventory."""

    completion: RegisteredOperationCompletion[VerifyListPublicResultV1]
    projection: VerifyListPublicResultV1


@dataclass(frozen=True, slots=True)
class VerifyViewRead:
    """Keep the settled receipt with one prefix-correlated verify row."""

    completion: RegisteredOperationCompletion[VerifyObservationPublicV1]
    projection: VerifyObservationPublicV1


@dataclass(frozen=True, slots=True)
class VerifyLatestRead:
    """Keep the settled receipt with one latest lookup, including an empty result."""

    completion: RegisteredOperationCompletion[VerifyLatestPublicResultV1]
    projection: VerifyLatestPublicResultV1


def _submit[ResultT: BaseModel](
    client: RuntimeFrontendClient,
    profile_id: UUID,
    request: BaseModel,
    *,
    result_type: type[ResultT],
    definition_id: str,
) -> RegisteredOperationCompletion[ResultT]:
    """Submit one registered read over the client bound to the active profile."""
    return run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
    )


def _require_read_receipt[ResultT: BaseModel](completed: RegisteredOperationCompletion[ResultT]) -> None:
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
    ):
        raise ValueError("verify read result disagrees with its settled receipt")


def _invalid_frame[ResultT: BaseModel](completed: RegisteredOperationCompletion[ResultT]) -> Exception:
    return submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def read_verify_list_for_cli(
    ctx: typer.Context,
    *,
    surface: VerifySurface | None = None,
    nif: str | None = None,
) -> VerifyListRead:
    """Read filtered exact-profile local verify rows."""
    client = bound_profile_client(ctx)
    profile_id = client.profile_id
    request = VerifyListRequest(profile_id=profile_id, surface=surface, nif=nif)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=VERIFY_LIST_DEFINITION_ID,
        result_type=VerifyListPublicResultV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, VerifyListPublicResultV1):
            raise ValueError("verify list projection has an invalid type")
        if projection.bucket_id != str(profile_id) or projection.count != len(projection.rows):
            raise ValueError("verify list result does not match its submitted profile and rows")
        for row in projection.rows:
            VerifySurface(row.surface)
            IdentityCheckVerdict(row.verdict)
            if row.expected is not None:
                IdentityCheckVerdict(row.expected)
            if (surface is not None and row.surface is not surface) or (nif is not None and row.nif != nif):
                raise ValueError("verify list result exceeds its submitted filters")
        _require_read_receipt(completed)
    except Exception:
        raise _invalid_frame(completed) from None
    return VerifyListRead(completion=completed, projection=projection)


def read_verify_view_for_cli(ctx: typer.Context, *, observation_id: str) -> VerifyViewRead:
    """Read one exact-profile local observation by full digest or unambiguous prefix."""
    client = bound_profile_client(ctx)
    profile_id = client.profile_id
    request = VerifyViewRequest(profile_id=profile_id, observation_id=observation_id)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=VERIFY_VIEW_DEFINITION_ID,
        result_type=VerifyObservationPublicV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, VerifyObservationPublicV1):
            raise ValueError("verify view projection has an invalid type")
        if projection.bucket_id != str(profile_id) or not projection.observation_id.startswith(request.observation_id):
            raise ValueError("verify view result does not match its submitted profile and id")
        VerifySurface(projection.surface)
        IdentityCheckVerdict(projection.verdict)
        if projection.expected is not None:
            IdentityCheckVerdict(projection.expected)
        _require_read_receipt(completed)
    except Exception:
        raise _invalid_frame(completed) from None
    return VerifyViewRead(completion=completed, projection=projection)


def read_verify_latest_for_cli(
    ctx: typer.Context,
    *,
    surface: VerifySurface,
    nif: str,
) -> VerifyLatestRead:
    """Read the latest exact-profile local observation for one surface/NIF pair."""
    client = bound_profile_client(ctx)
    profile_id = client.profile_id
    request = VerifyLatestRequest(profile_id=profile_id, surface=surface, nif=nif)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=VERIFY_LATEST_DEFINITION_ID,
        result_type=VerifyLatestPublicResultV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, VerifyLatestPublicResultV1):
            raise ValueError("verify latest projection has an invalid type")
        if projection.bucket_id != str(profile_id) or projection.surface is not surface or projection.nif != nif:
            raise ValueError("verify latest result does not match its submitted profile and lookup")
        if projection.observation_id is not None:
            IdentityCheckVerdict(projection.verdict)
            if projection.expected is not None:
                IdentityCheckVerdict(projection.expected)
        _require_read_receipt(completed)
    except Exception:
        raise _invalid_frame(completed) from None
    return VerifyLatestRead(completion=completed, projection=projection)


__all__ = [
    "VerifyLatestRead",
    "VerifyListRead",
    "VerifyViewRead",
    "read_verify_latest_for_cli",
    "read_verify_list_for_cli",
    "read_verify_view_for_cli",
]
