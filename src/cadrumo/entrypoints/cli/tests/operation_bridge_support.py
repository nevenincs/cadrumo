"""Fake the profile-bound registered-operation bridge for CLI read-command tests."""

from __future__ import annotations

from collections.abc import Mapping
from types import ModuleType, SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion

from ....core.operations import OperationEffect, OperationTerminalCondition
from .. import operation_profile_operation as profile_operation


def bind_profile_reads(
    monkeypatch: pytest.MonkeyPatch,
    projections: Mapping[str, BaseModel],
    *,
    bridge: ModuleType,
    profile_id: UUID,
    operation_id: str,
    effect: OperationEffect = OperationEffect.NONE,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[BaseModel, dict[str, object]]], list[UUID]]:
    """Serve ``projections`` by definition id and record each submission and profile binding."""
    bound_profiles: list[UUID] = []
    client = SimpleNamespace(profile_id=profile_id)

    def require_client(_ctx: object) -> object:
        bound_profiles.append(client.profile_id)
        return client

    monkeypatch.setattr(bridge, "bound_profile_client", require_client)
    submitted: list[tuple[BaseModel, dict[str, object]]] = []

    def submit(
        submitted_client: object, request: BaseModel, **kwargs: object
    ) -> RegisteredOperationCompletion[BaseModel]:
        assert submitted_client is client
        submitted.append((request, kwargs))
        definition_id = cast(str, kwargs["definition_id"])
        return RegisteredOperationCompletion(
            operation_id=operation_id,
            projection=projections[definition_id],
            effect=effect,
            terminal_condition=terminal_condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(profile_operation, "run_registered_operation", submit)
    return submitted, bound_profiles


def bind_profile_submission(
    monkeypatch: pytest.MonkeyPatch,
    projection: BaseModel | Mapping[str, BaseModel],
    *,
    bridge: ModuleType,
    operation_id: str,
    effect: OperationEffect,
    profile_id: UUID | None = None,
    submit_module: ModuleType | None = None,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[BaseModel, dict[str, object]]], list[UUID]]:
    """Serve one projection (or one per definition id) and record each submission and expected profile.

    ``profile_id`` also pins the active bucket the bridge reads before binding its client.
    """
    if profile_id is not None:
        monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(profile_id))
    bound_profiles: list[UUID] = []
    client = object()

    def require_client(_ctx: object, *, expected_profile_id: UUID) -> object:
        bound_profiles.append(expected_profile_id)
        return client

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[BaseModel, dict[str, object]]] = []

    def submit(
        submitted_client: object, request: BaseModel, **kwargs: object
    ) -> RegisteredOperationCompletion[BaseModel]:
        assert submitted_client is client
        submitted.append((request, kwargs))
        served = projection[cast(str, kwargs["definition_id"])] if isinstance(projection, Mapping) else projection
        return RegisteredOperationCompletion(
            operation_id=operation_id,
            projection=served,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(submit_module or bridge, "run_registered_operation", submit)
    return submitted, bound_profiles
