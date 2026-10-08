"""CLI mutation refusals retain what the native operation actually settled."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest

from .....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from .....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from .....adapters.local_runtime.profile_mutations import ProfileMutationCompletion, ProfileMutationRunError
from .....application.user_profile.profile_operation_contracts import (
    ProfileCompleteSetupOperationRequest,
    ProfileMutationOperationProjection,
)
from .....core.operations import OperationEffect, OperationTerminalCondition
from ...errors import CliRefusedBoundaryError
from .._profile_repeatable_row import _parse_row_key, _parse_values
from .._runtime_profile_mutation import execute_profile_mutation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _RefusedReadClient:
    def read_profile_view(self, *_args: object, **_kwargs: object) -> object:
        raise RuntimeFrontendRefusedError("profile.view.stale_revision")


def test_post_commit_view_refusal_keeps_known_success_and_operation_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = uuid4()
    operation_id = "a" * 64
    request = ProfileCompleteSetupOperationRequest(
        profile_id=profile_id, expected_revision=2, expected_content_digest="b" * 64
    )

    def complete(_client: object, _request: object, *, timeout: float) -> ProfileMutationCompletion:
        assert timeout > 0
        return ProfileMutationCompletion(
            operation_id=operation_id,
            projection=ProfileMutationOperationProjection(profile_id=profile_id, record_revision=3),
            effect=OperationEffect.UPDATED,
        )

    monkeypatch.setattr("cadrumo.entrypoints.cli.config._runtime_profile_mutation.run_profile_mutation", complete)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        execute_profile_mutation(cast(RuntimeFrontendClient, _RefusedReadClient()), request, deadline=10**12)

    error = caught.value
    assert error.translated_message == "cli.config.profile.mutation.committed_view_unavailable"
    assert error.context == {
        "operation_id": operation_id,
        "commit_state": "succeeded",
        "record_revision": 3,
        "read_state": "unavailable",
    }


def test_terminal_operation_refusal_keeps_reason_and_settlement_context(monkeypatch: pytest.MonkeyPatch) -> None:
    operation_id = "b" * 64
    reason = "refusal:profile.mutation.denied"
    request = ProfileCompleteSetupOperationRequest(
        profile_id=uuid4(), expected_revision=2, expected_content_digest="c" * 64
    )

    def refuse(_client: object, _request: object, *, timeout: float) -> ProfileMutationCompletion:
        assert timeout > 0
        raise ProfileMutationRunError(
            operation_id=operation_id,
            code=reason,
            terminal_condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
        )

    monkeypatch.setattr("cadrumo.entrypoints.cli.config._runtime_profile_mutation.run_profile_mutation", refuse)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        execute_profile_mutation(cast(RuntimeFrontendClient, _RefusedReadClient()), request, deadline=10**12)

    assert caught.value.context == {
        "reason": reason,
        "operation_id": operation_id,
        "effect": OperationEffect.NONE.value,
        "terminal_condition": OperationTerminalCondition.REFUSED.value,
    }


def test_row_tokens_reject_invalid_assignments_and_identity_before_private_operation() -> None:
    assert _parse_values(["description=Another activity"]) == {"description": "Another activity"}
    assert _parse_row_key("base") == ""
    assert _parse_row_key("004") == "4"
    with pytest.raises(CliRefusedBoundaryError):
        _parse_values(["not-an-assignment"])
    with pytest.raises(CliRefusedBoundaryError):
        _parse_values(["description=first", "description=second"])
    with pytest.raises(CliRefusedBoundaryError):
        _parse_row_key("bad-row")
