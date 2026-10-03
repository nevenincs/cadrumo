"""Protected rotation client owns proofs and never retries the mutation."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.auth.operation_definitions import (
    PROFILE_ROTATION_OPERATION_DEFINITION_ID,
    AuthOperationPorts,
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from cadrumo.application.auth.passphrase_operation_access import PROFILE_ROTATION_RESULT_SCHEMA_ID
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.models import OperationIdentity
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
)
from cadrumo.application.operations.secret_submission import OperationSecretRequirement
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)

from ..frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ..profile_mutations import ProfileMutationRunError
from ..profile_password_rotation import run_profile_password_rotation

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_OPERATION_ID = "a" * 64
_ROTATION_SECRET_KIND = "profile.passphrase.rotation"  # noqa: S105 -- public broker discriminator, not a credential.


def _contract() -> OperationPublicDefinitionContractV1:
    # Only the rotation definition is selected; its factory does not consult
    # the unrelated provider ports when composing its canonical manifest.
    definitions = build_auth_operation_definitions(ports=cast(AuthOperationPorts, object()))
    rotation = next(item for item in definitions if item.definition_id == PROFILE_ROTATION_OPERATION_DEFINITION_ID)
    registration = build_auth_operation_registrations((rotation,))[0]
    assert registration.contract.result_schema is not None
    assert registration.contract.result_schema.schema_id == PROFILE_ROTATION_RESULT_SCHEMA_ID
    return registration.contract


def _refused_observation(
    *, contract: OperationPublicDefinitionContractV1, profile_id: UUID
) -> OperationObservationSuccessV1:
    instant = datetime.now(UTC)
    operation_id = _OPERATION_ID
    subject_ref = profile_operation_subject(str(profile_id))
    contract_set = OperationPublicContractSetV1.build((contract,))
    projection = OperationPublicProjectionV1(
        operation_id=operation_id,
        definition_id=contract.definition_id,
        subject_ref=subject_ref,
        revision=3,
        anchor_cursor=3,
        definition_contract=contract,
        contract_set_digest=contract_set.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        phase_code=None,
        started_at=instant,
        updated_at=instant,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None,
        refusal_ref="refusal:rotation.denied",
        failure_error_code=None,
        diagnostic_ref=None,
    )
    event_page = OperationPublicEventPageV1(
        operation_id=operation_id,
        anchor_cursor=3,
        requested_cursor=3,
        status=OperationReplayStatus.CAUGHT_UP,
        events=(),
        next_cursor=3,
        restart_cursor=None,
    )
    return OperationObservationSuccessV1(projection=projection, event_page=event_page)


class _Client:
    def __init__(
        self,
        *,
        profile_id: UUID,
        frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
        contract: OperationPublicDefinitionContractV1 | None = None,
        contract_error: RuntimeFrontendRefusedError | None = None,
        login_error: RuntimeFrontendRefusedError | None = None,
        terminal_refusal: bool = False,
    ) -> None:
        self.profile_id = profile_id
        self.frontend = frontend
        self.session_id = uuid4()
        self._contract = contract or _contract()
        self._contract_error = contract_error
        self._login_error = login_error
        self._terminal_refusal = terminal_refusal
        self.contract_calls = 0
        self.submissions = 0
        self.starts = 0
        self.secret_submissions = 0
        self.login_calls = 0
        self.close_calls = 0

    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        del deadline
        assert definition_id == PROFILE_ROTATION_OPERATION_DEFINITION_ID
        self.contract_calls += 1
        if self._contract_error is not None:
            raise self._contract_error
        return self._contract

    def operation(self, request: object, *, deadline: float) -> object:
        del deadline
        if isinstance(request, RuntimeOperationSubmit):
            self.submissions += 1
            assert request.profile_id == self.profile_id
            return RuntimeOperationSubmitted(
                request_id=request.request_id,
                runtime_boot_id=uuid4(),
                connection_id=uuid4(),
                receipt=OperationSubmissionReceiptV1(
                    operation_id=_OPERATION_ID,
                    secret_requirement=OperationSecretRequirement(
                        identity=OperationIdentity(
                            operation_id=_OPERATION_ID,
                            definition_id=PROFILE_ROTATION_OPERATION_DEFINITION_ID,
                            subject_ref=profile_operation_subject(str(self.profile_id)),
                        ),
                        interaction_id="b" * 64,
                        revision=0,
                        secret_kind=_ROTATION_SECRET_KIND,
                        expires_at=datetime.now(UTC) + timedelta(minutes=5),
                    ),
                ),
            )
        if isinstance(request, RuntimeOperationControl):
            self.starts += 1
            return RuntimeOperationAcknowledged(
                request_id=request.request_id,
                runtime_boot_id=uuid4(),
                connection_id=uuid4(),
                operation_id=_OPERATION_ID,
            )
        if isinstance(request, RuntimeOperationObserve):
            if self._terminal_refusal:
                observation = _refused_observation(contract=self._contract, profile_id=self.profile_id)
                return RuntimeOperationObserved(
                    request_id=request.request_id,
                    runtime_boot_id=uuid4(),
                    connection_id=uuid4(),
                    observation=observation,
                )
            # A committed rotation deliberately retires the original lease.
            raise RuntimeFrontendRefusedError(AccessDenialCode.CONNECTION_MISMATCH.value)
        raise AssertionError("unexpected canonical operation request")

    def submit_secret(
        self, requirement: OperationSecretRequirement, secret: bytearray, *, timeout: float
    ) -> RuntimeOperationAcknowledged:
        assert requirement.identity.operation_id == _OPERATION_ID
        assert timeout > 0
        self.secret_submissions += 1
        secret[:] = bytes(len(secret))
        return RuntimeOperationAcknowledged(
            request_id=uuid4(), runtime_boot_id=uuid4(), connection_id=uuid4(), operation_id=_OPERATION_ID
        )

    def login_password(self, secret: bytearray, *, timeout: float) -> None:
        assert timeout > 0
        self.login_calls += 1
        secret[:] = bytes(len(secret))
        if self._login_error is not None:
            raise self._login_error
        self.session_id = uuid4()

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.close_calls += 1


def _proofs() -> tuple[bytearray, bytearray, bytearray]:
    return (
        bytearray(b"current-private-proof"),
        bytearray(b"replacement-private-proof"),
        bytearray(b"replacement-private-proof"),
    )


def _run(
    original: _Client,
    proofs: tuple[bytearray, bytearray, bytearray],
    *,
    fresh_client: Callable[[], _Client],
    timeout: float = 60,
) -> None:
    run_profile_password_rotation(
        cast(RuntimeFrontendClient, original),
        current_passphrase=proofs[0],
        new_passphrase=proofs[1],
        new_passphrase_confirmation=proofs[2],
        fresh_client=lambda: cast(RuntimeFrontendClient, fresh_client()),
        timeout=timeout,
    )


def _assert_wiped(proofs: tuple[bytearray, bytearray, bytearray]) -> None:
    assert all(not any(buffer) for buffer in proofs)


@pytest.mark.parametrize("timeout", [0, -1, math.inf, math.nan, 121])
def test_invalid_timeout_wipes_all_proofs_before_contract_access(timeout: float) -> None:
    original = _Client(profile_id=uuid4())
    proofs = _proofs()
    with pytest.raises(ValueError):
        _run(original, proofs, fresh_client=lambda: original, timeout=timeout)
    _assert_wiped(proofs)
    assert original.contract_calls == original.submissions == original.close_calls == 0


def test_preflight_refusal_wipes_all_proofs_without_mutation() -> None:
    original = _Client(
        profile_id=uuid4(), contract_error=RuntimeFrontendRefusedError(AccessDenialCode.OPERATION_DENIED.value)
    )
    proofs = _proofs()
    with pytest.raises(RuntimeFrontendRefusedError) as caught:
        _run(original, proofs, fresh_client=lambda: original)
    assert caught.value.reason == AccessDenialCode.OPERATION_DENIED.value
    _assert_wiped(proofs)
    assert original.contract_calls == 1 and original.submissions == original.close_calls == 0


def test_invalid_utf8_frame_refuses_without_retaining_credential_exception() -> None:
    original = _Client(profile_id=uuid4())
    proofs = (
        bytearray(b"\xffprivate-proof"),
        bytearray(b"replacement-private-proof"),
        bytearray(b"replacement-private-proof"),
    )
    with pytest.raises(ProfileMutationRunError) as caught:
        _run(original, proofs, fresh_client=lambda: original)
    assert caught.value.operation_id == _OPERATION_ID
    assert caught.value.reason == "runtime_invalid_frame"
    assert caught.value.__context__ is None
    assert caught.value.context == {
        "reason": "runtime_invalid_frame",
        "operation_id": _OPERATION_ID,
        "effect": "unknown",
    }
    assert "private-proof" not in str(caught.value)
    _assert_wiped(proofs)
    assert original.submissions == 1 and original.secret_submissions == original.starts == 0


def test_terminal_refusal_uses_public_refusal_reference_and_keeps_effect_context() -> None:
    original = _Client(profile_id=uuid4(), terminal_refusal=True)
    proofs = _proofs()

    with pytest.raises(ProfileMutationRunError) as caught:
        _run(original, proofs, fresh_client=lambda: pytest.fail("refused operation must not read a fresh result"))

    assert caught.value.reason == "refusal:rotation.denied"
    assert caught.value.operation_id == _OPERATION_ID
    assert caught.value.terminal_condition is OperationTerminalCondition.REFUSED
    assert caught.value.effect is OperationEffect.NONE
    assert caught.value.context == {
        "reason": "refusal:rotation.denied",
        "operation_id": _OPERATION_ID,
        "effect": OperationEffect.NONE.value,
        "terminal_condition": OperationTerminalCondition.REFUSED.value,
    }
    assert original.submissions == original.secret_submissions == original.starts == 1
    _assert_wiped(proofs)


def test_fresh_factory_cannot_return_borrowed_original_or_close_it() -> None:
    original = _Client(profile_id=uuid4())
    proofs = _proofs()
    with pytest.raises(ProfileMutationRunError) as caught:
        _run(original, proofs, fresh_client=lambda: original)
    assert caught.value.operation_id == _OPERATION_ID
    assert caught.value.reason == AccessDenialCode.CONNECTION_MISMATCH.value
    _assert_wiped(proofs)
    assert original.submissions == original.secret_submissions == original.starts == 1
    assert original.close_calls == 0


@pytest.mark.parametrize("wrong", ["profile", "frontend"])
def test_wrong_fresh_candidate_is_closed_without_receiving_replacement_proof(wrong: str) -> None:
    original = _Client(profile_id=uuid4())
    candidate = _Client(
        profile_id=uuid4() if wrong == "profile" else original.profile_id,
        frontend=OperationFrontendProjection.TUI if wrong == "frontend" else original.frontend,
    )
    proofs = _proofs()
    with pytest.raises(ProfileMutationRunError) as caught:
        _run(original, proofs, fresh_client=lambda: candidate)
    assert caught.value.reason == AccessDenialCode.PROFILE_MISMATCH.value
    assert candidate.login_calls == 0 and candidate.close_calls == 1
    assert original.close_calls == 0
    _assert_wiped(proofs)


def test_retryable_new_host_admission_never_resubmits_mutation() -> None:
    original = _Client(profile_id=uuid4())
    first = _Client(
        profile_id=original.profile_id,
        login_error=RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value),
    )
    second = _Client(
        profile_id=original.profile_id,
        login_error=RuntimeFrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value),
    )
    candidates = iter((first, second))
    proofs = _proofs()
    with pytest.raises(ProfileMutationRunError) as caught:
        _run(original, proofs, fresh_client=lambda: next(candidates))
    assert caught.value.operation_id == _OPERATION_ID
    assert caught.value.reason == AccessDenialCode.AUTHENTICATION_REQUIRED.value
    assert original.submissions == original.secret_submissions == original.starts == 1
    assert first.login_calls == second.login_calls == 1
    assert first.close_calls == second.close_calls == 1
    assert original.close_calls == 0
    _assert_wiped(proofs)
