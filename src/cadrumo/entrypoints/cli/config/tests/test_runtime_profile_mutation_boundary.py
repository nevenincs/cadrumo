"""CLI mutation refusals retain what the native operation actually settled."""

from __future__ import annotations

import json
from typing import cast
from uuid import uuid4

import pytest

from cadrumo_client.commands.errors import CliRecordedOperationError, CliRefusedBoundaryError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.profile_mutations import ProfileMutationCompletion, ProfileMutationRunError

from .....application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from .....application.operator_actions.preconditions import profile_required_facts_missing_verdict
from .....application.user_profile.profile_operation_contracts import (
    ProfileCompleteSetupOperationRequest,
    ProfileMutationOperationProjection,
)
from .....core.errors.error_codes import get_registered_error_code
from .....core.operations import OperationEffect, OperationTerminalCondition
from ...common import cli_policy_refusal_projection
from ...errors import render_error_payload
from ..profile_mutation import execute_profile_mutation
from ..profile_row_commands import parse_row_key, parse_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _RefusedReadClient:
    def read_profile_view(self, *_args: object, **_kwargs: object) -> object:
        raise FrontendRefusedError("profile.view.stale_revision")


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

    monkeypatch.setattr("cadrumo.entrypoints.cli.config.profile_mutation.run_profile_mutation", complete)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        execute_profile_mutation(cast(FrontendClient, _RefusedReadClient()), request, deadline=10**12)

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

    monkeypatch.setattr("cadrumo.entrypoints.cli.config.profile_mutation.run_profile_mutation", refuse)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        execute_profile_mutation(cast(FrontendClient, _RefusedReadClient()), request, deadline=10**12)

    assert caught.value.context == {
        "reason": reason,
        "operation_id": operation_id,
        "effect": OperationEffect.NONE.value,
        "terminal_condition": OperationTerminalCondition.REFUSED.value,
    }


def test_terminal_refusal_with_recorded_detail_keeps_its_code_and_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    operation_id = "d" * 64
    verdict = profile_required_facts_missing_verdict(modelo=None, field_paths=("identity.tax_id",))
    # The detail as the client decodes it from the worker's recorded document.
    detail = OperationErrorDetailV1.model_validate_json(
        OperationErrorDetailV1(
            kind=OperationErrorDetailKind.REGISTERED_ERROR,
            error_code="REFUSED_USER_PROFILE_VALIDATION",
            message_key="errors.refused.refused_user_profile_validation",
            context=(),
            precondition_verdict_json=verdict.model_dump_json(),
        ).model_dump_json()
    )
    request = ProfileCompleteSetupOperationRequest(
        profile_id=uuid4(), expected_revision=2, expected_content_digest="e" * 64
    )

    def refuse(_client: object, _request: object, *, timeout: float) -> ProfileMutationCompletion:
        assert timeout > 0
        raise ProfileMutationRunError(
            operation_id=operation_id,
            code="REFUSED_USER_PROFILE_VALIDATION",
            terminal_condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            detail=detail,
        )

    monkeypatch.setattr("cadrumo.entrypoints.cli.config.profile_mutation.run_profile_mutation", refuse)
    with pytest.raises(CliRecordedOperationError) as caught:
        execute_profile_mutation(cast(FrontendClient, _RefusedReadClient()), request, deadline=10**12)

    error = caught.value
    assert get_registered_error_code(error).code == "REFUSED_USER_PROFILE_VALIDATION"
    assert error.terminal_precondition_verdict == verdict
    assert error.context is not None
    assert error.context["operation_id"] == operation_id
    assert error.context["terminal_condition"] == OperationTerminalCondition.REFUSED.value
    projection = cli_policy_refusal_projection(error)
    assert projection is not None
    rendered = json.loads(render_error_payload(error, as_json=True, action=projection.precondition_action))["error"]
    assert rendered["code"] == "REFUSED_USER_PROFILE_VALIDATION"
    assert rendered["action"]["failed_condition_id"] == verdict.failed_condition_id
    assert rendered["action"]["action"]["action_id"] == "operator.profile.edit"


def test_row_tokens_reject_invalid_assignments_and_identity_before_private_operation() -> None:
    assert parse_values(["description=Another activity"]) == {"description": "Another activity"}
    assert parse_row_key("base") == ""
    assert parse_row_key("004") == "4"
    with pytest.raises(CliRefusedBoundaryError):
        parse_values(["not-an-assignment"])
    with pytest.raises(CliRefusedBoundaryError):
        parse_values(["description=first", "description=second"])
    with pytest.raises(CliRefusedBoundaryError):
        parse_row_key("bad-row")
