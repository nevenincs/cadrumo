"""Admission and registered-choice selection for automation requests."""

from __future__ import annotations

import math
from uuid import UUID

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from ....application.user_profile.access_contracts import DisclosureCategory
from . import automation_requester_contracts as _contracts


def validate_client_admission(
    profile_id: UUID,
    client: RuntimeFrontendClient | None,
    open_client: _contracts.RequesterClientOpener | None,
    reviewer_client: RuntimeFrontendClient | None,
    journey_timeout: float,
) -> None:
    """Enforce exact profile/frontend bindings and the bounded journey timeout."""
    if (client is None) == (open_client is None):
        raise ValueError("requester needs exactly one client source")
    if client is not None and (
        client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.TUI
    ):
        raise ValueError("requester client must be the exact TUI profile")
    if reviewer_client is not None and (
        reviewer_client.profile_id != profile_id or reviewer_client.frontend is not OperationFrontendProjection.TUI
    ):
        raise ValueError("reviewer must be the exact TUI profile")
    if not math.isfinite(journey_timeout) or not 0 < journey_timeout <= 300:
        raise ValueError("requester journey timeout must be finite and at most five minutes")


def operation_choices(contracts: OperationPublicContractSetV1) -> tuple[str, ...]:
    """Keep only operations that the TUI is permitted to request."""
    return tuple(
        str(row.definition_id)
        for row in contracts.definitions
        if OperationFrontendProjection.TUI in row.permitted_frontends
    )


def disclosure_choices(
    contracts: OperationPublicContractSetV1,
) -> tuple[tuple[str, DisclosureCategory], ...]:
    """Offer only registered schemas, plus the defined operation metadata projection."""
    return tuple(
        sorted(
            {
                (str(schema.schema_id), category)
                for row in contracts.definitions
                if OperationFrontendProjection.TUI in row.permitted_frontends
                for schema in (
                    row.result_schema,
                    row.review_projection_schema,
                    row.interaction_response_schema,
                    row.workspace_refresh_target_schema,
                )
                if schema is not None
                for category in DisclosureCategory
            }
            | {(OPERATION_OBSERVATION_PROJECTION_ID, DisclosureCategory.OPERATION_METADATA)}
        )
    )
