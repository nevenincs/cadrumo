"""CLI bridges for exact-profile local justificante snapshot reads."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from ...application.calculations.observations_repository import ObservationSourceKind
from ...application.live.justificante_read_operation import (
    JUSTIFICANTE_LIST_DEFINITION_ID,
    JUSTIFICANTE_SHOW_DEFINITION_ID,
    JustificanteListPublicResultV1,
    JustificanteListRequest,
    JustificanteShowPublicResultV1,
    JustificanteShowRequest,
)
from ...application.live.snapshot_base import SnapshotLifecycleState
from ...core.modelo import Modelo
from ...core.period import Period
from .registered_operation_contracts import RegisteredOperationCompletion
from .runtime_profile_binding import bound_profile_client
from .runtime_profile_operation import settled_profile_projection, submit_profile_operation


@dataclass(frozen=True, slots=True)
class JustificanteListRead:
    """Keep the settled receipt with the exact-profile active snapshot inventory."""

    completion: RegisteredOperationCompletion[JustificanteListPublicResultV1]
    projection: JustificanteListPublicResultV1


@dataclass(frozen=True, slots=True)
class JustificanteShowRead:
    """Keep the settled receipt with one prefix-correlated snapshot view."""

    completion: RegisteredOperationCompletion[JustificanteShowPublicResultV1]
    projection: JustificanteShowPublicResultV1


def read_justificante_list_for_cli(ctx: typer.Context) -> JustificanteListRead:
    """Read exact-profile local active justificante snapshot summaries."""
    client = bound_profile_client(ctx)
    profile_id = client.profile_id
    request = JustificanteListRequest(profile_id=profile_id)
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=JUSTIFICANTE_LIST_DEFINITION_ID,
        result_type=JustificanteListPublicResultV1,
    )

    def correlate(projection: JustificanteListPublicResultV1) -> None:
        if projection.count != len(projection.rows):
            raise ValueError("justificante list result does not match its rows")
        for row in projection.rows:
            Modelo(row.modelo)
            if row.state != SnapshotLifecycleState.ACTIVE.value:
                raise ValueError("justificante list result contains a non-active capture")
            Period.from_year_and_code(row.filing_year, row.period)

    projection = settled_profile_projection(completed, JustificanteListPublicResultV1, profile_id, correlate)
    return JustificanteListRead(completion=completed, projection=projection)


def read_justificante_show_for_cli(ctx: typer.Context, *, snapshot_id: str) -> JustificanteShowRead:
    """Read one exact-profile local snapshot by full id or unambiguous prefix."""
    client = bound_profile_client(ctx)
    profile_id = client.profile_id
    request = JustificanteShowRequest(profile_id=profile_id, snapshot_id=snapshot_id)
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=JUSTIFICANTE_SHOW_DEFINITION_ID,
        result_type=JustificanteShowPublicResultV1,
    )

    def correlate(projection: JustificanteShowPublicResultV1) -> None:
        if not projection.snapshot_id.startswith(request.snapshot_id):
            raise ValueError("justificante show result does not match its submitted id")
        Modelo(projection.modelo)
        ObservationSourceKind(projection.source_kind)
        SnapshotLifecycleState(projection.state)
        Period.from_year_and_code(projection.filing_year, projection.period)

    projection = settled_profile_projection(completed, JustificanteShowPublicResultV1, profile_id, correlate)
    return JustificanteShowRead(completion=completed, projection=projection)


__all__ = [
    "JustificanteListRead",
    "JustificanteShowRead",
    "read_justificante_list_for_cli",
    "read_justificante_show_for_cli",
]
