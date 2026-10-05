"""CLI bridges for exact-profile reads of encrypted local verify observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import typer

from ...application.live.verify import VerifySurface
from ...application.live.verify_read_contracts import (
    VerifyLatestPublicResultV1,
    VerifyLatestRequest,
    VerifyListPublicResultV1,
    VerifyListRequest,
    VerifyObservationPublicV1,
    VerifyViewRequest,
)
from ...application.live.verify_read_operation import (
    VERIFY_LATEST_DEFINITION_ID,
    VERIFY_LIST_DEFINITION_ID,
    VERIFY_VIEW_DEFINITION_ID,
)
from ...core.identity_check_verdict import IdentityCheckVerdict
from .registered_operation_contracts import RegisteredOperationCompletion
from .runtime_profile_binding import bound_profile_client
from .runtime_profile_operation import settled_profile_projection, submit_profile_operation


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


class _VerdictCarrier(Protocol):
    """An observation or lookup whose verdicts must belong to the closed vocabulary."""

    @property
    def verdict(self) -> object:
        """Return the observed verdict."""
        ...

    @property
    def expected(self) -> object | None:
        """Return the expected verdict, if one was recorded."""
        ...


def _require_known_verdicts(observation: _VerdictCarrier) -> None:
    IdentityCheckVerdict(observation.verdict)
    if observation.expected is not None:
        IdentityCheckVerdict(observation.expected)


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
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=VERIFY_LIST_DEFINITION_ID,
        result_type=VerifyListPublicResultV1,
    )

    def correlate(projection: VerifyListPublicResultV1) -> None:
        if projection.count != len(projection.rows):
            raise ValueError("verify list result does not match its rows")
        for row in projection.rows:
            VerifySurface(row.surface)
            _require_known_verdicts(row)
            if (surface is not None and row.surface is not surface) or (nif is not None and row.nif != nif):
                raise ValueError("verify list result exceeds its submitted filters")

    projection = settled_profile_projection(completed, VerifyListPublicResultV1, profile_id, correlate)
    return VerifyListRead(completion=completed, projection=projection)


def read_verify_view_for_cli(ctx: typer.Context, *, observation_id: str) -> VerifyViewRead:
    """Read one exact-profile local observation by full digest or unambiguous prefix."""
    client = bound_profile_client(ctx)
    profile_id = client.profile_id
    request = VerifyViewRequest(profile_id=profile_id, observation_id=observation_id)
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=VERIFY_VIEW_DEFINITION_ID,
        result_type=VerifyObservationPublicV1,
    )

    def correlate(projection: VerifyObservationPublicV1) -> None:
        if not projection.observation_id.startswith(request.observation_id):
            raise ValueError("verify view result does not match its submitted id")
        VerifySurface(projection.surface)
        _require_known_verdicts(projection)

    projection = settled_profile_projection(completed, VerifyObservationPublicV1, profile_id, correlate)
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
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=VERIFY_LATEST_DEFINITION_ID,
        result_type=VerifyLatestPublicResultV1,
    )

    def correlate(projection: VerifyLatestPublicResultV1) -> None:
        if projection.surface is not surface or projection.nif != nif:
            raise ValueError("verify latest result does not match its submitted lookup")
        if projection.observation_id is not None:
            _require_known_verdicts(projection)

    projection = settled_profile_projection(completed, VerifyLatestPublicResultV1, profile_id, correlate)
    return VerifyLatestRead(completion=completed, projection=projection)


__all__ = [
    "VerifyLatestRead",
    "VerifyListRead",
    "VerifyViewRead",
    "read_verify_latest_for_cli",
    "read_verify_list_for_cli",
    "read_verify_view_for_cli",
]
