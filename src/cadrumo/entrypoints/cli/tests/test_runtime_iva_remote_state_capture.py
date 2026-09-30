"""Combined IVA evidence CLI bridge preserves the registered public result."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.live.errors import LiveIvaAcquisitionFailureMode
from ....application.live.iva_remote_state_capture_operation import (
    IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID,
    IvaRemoteStateCapturePublicResultV1,
    IvaRemoteStateCaptureRequest,
    LiveIvaAuthOutcomePublicV1,
    LiveIvaSurfaceOutcomePublicV1,
)
from ....application.live.remote_state_models import (
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from .. import _app_live as handler
from .. import runtime_iva_remote_state_capture as bridge
from .._app_live_iva_wallet_payloads import IvaWalletPullEvidenceResult
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_OUTPUT_ROOT = Path("iva-evidence")


def _projection() -> IvaRemoteStateCapturePublicResultV1:
    return IvaRemoteStateCapturePublicResultV1(
        acquisition_manifest_id="manifest-ref",
        output_root=str(_OUTPUT_ROOT),
        year_from=2022,
        year_to=2024,
        target_year=2025,
        target_period="1T",
        auth=LiveIvaAuthOutcomePublicV1(
            status=LiveIvaReadStatus.FAILED,
            outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
            failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
            failure_type="ClaveMovilApprovalTimeoutError",
            diagnostic_ref=None,
            provider_kind="clave_movil",
            reused_persisted_session=False,
            fresh=None,
        ),
        filed_history_succeeded=False,
        wallet_succeeded=True,
        outcomes=(
            LiveIvaSurfaceOutcomePublicV1(
                surface=LiveIvaReadSurface.FILED_HISTORY,
                status=LiveIvaReadStatus.FAILED,
                outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                failure_type="ClaveMovilApprovalTimeoutError",
                failure_context_json=(
                    '{"progress":{"ejercicio":2025,"modelo":"303","stage":"walk_declarations_register"}}'
                ),
                captured_count=None,
                calculation_observation_count=None,
            ),
            LiveIvaSurfaceOutcomePublicV1(
                surface=LiveIvaReadSurface.WALLET_CARTERA,
                status=LiveIvaReadStatus.SUCCEEDED,
                outcome_mode=LiveIvaAcquisitionFailureMode.AUTHENTICATED,
                failure_mode=None,
                failure_type=None,
                failure_context_json=None,
                captured_count=1,
                calculation_observation_count=0,
            ),
        ),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: IvaRemoteStateCapturePublicResultV1,
    *,
    effect: OperationEffect = OperationEffect.UPDATED,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[IvaRemoteStateCaptureRequest, dict[str, object]]], list[UUID]]:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    bound_profiles: list[UUID] = []

    def require_client(_ctx: object, *, expected_profile_id: UUID):
        bound_profiles.append(expected_profile_id)
        return object()

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[IvaRemoteStateCaptureRequest, dict[str, object]]] = []

    def submit(_client: object, request: IvaRemoteStateCaptureRequest, **kwargs: object):
        submitted.append((request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _read() -> bridge.IvaRemoteStateCaptureRead:
    return bridge.read_iva_remote_state_capture_for_cli(
        cast(typer.Context, cast(object, None)),
        output_root=_OUTPUT_ROOT,
        year_from=2022,
        year_to=2024,
        target_year=2025,
        target_period=Period.from_year_and_code(2025, "1T"),
        taxpayer_nif="X1234567L",
    )


def test_registered_combined_capture_uses_exact_profile_scope_and_restores_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted, bound_profiles = _bind(monkeypatch, _projection())

    read = _read()

    assert bound_profiles == [_PROFILE]
    assert read.completion.operation_id == _OPERATION_ID
    assert read.report.target_period == Period.from_year_and_code(2025, "1T")
    assert read.report.filed_history is None
    assert read.report.wallet is None
    assert read.report.filed_history_succeeded is False
    assert read.report.wallet_succeeded is True
    assert read.report.outcomes[0].failure_context == {
        "progress": {"ejercicio": 2025, "modelo": "303", "stage": "walk_declarations_register"}
    }
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == IvaRemoteStateCaptureRequest(
        profile_id=_PROFILE,
        output_root=_OUTPUT_ROOT,
        year_from=2022,
        year_to=2024,
        target_year=2025,
        target_period="1T",
        taxpayer_nif="X1234567L",
    )
    assert options["definition_id"] == IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is IvaRemoteStateCapturePublicResultV1
    assert options["request_version"] == 1
    assert options["result_version"] == 1


@pytest.mark.parametrize(
    "mismatch",
    [
        "output_root",
        "year_from",
        "year_to",
        "target_year",
        "target_period",
        "effect",
        "terminal",
        "refusal",
        "bad_context",
    ],
)
def test_scope_or_receipt_mismatch_refuses_with_correlated_operation(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    condition = OperationTerminalCondition.SUCCEEDED
    refusal_code = None
    if mismatch == "output_root":
        projection = projection.model_copy(update={"output_root": "other-root"})
    elif mismatch == "year_from":
        projection = projection.model_copy(update={"year_from": 2023})
    elif mismatch == "year_to":
        projection = projection.model_copy(update={"year_to": 2023})
    elif mismatch == "target_year":
        projection = projection.model_copy(update={"target_year": 2024})
    elif mismatch == "target_period":
        projection = projection.model_copy(update={"target_period": "2T"})
    elif mismatch == "effect":
        effect = OperationEffect.NONE
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    elif mismatch == "refusal":
        refusal_code = RuntimeRefusalCode.UNAVAILABLE.value
    elif mismatch == "bad_context":
        outcomes = (
            projection.outcomes[0].model_copy(update={"failure_context_json": "[]"}),
            projection.outcomes[1],
        )
        projection = projection.model_copy(update={"outcomes": outcomes})
    _bind(
        monkeypatch,
        projection,
        effect=effect,
        condition=condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        _read()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_combined_capture_command_preserves_payload_lines_and_surface_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.UPDATED,
    )
    report = bridge._report(
        projection,
        request=IvaRemoteStateCaptureRequest(
            profile_id=_PROFILE,
            output_root=_OUTPUT_ROOT,
            year_from=2022,
            year_to=2024,
            target_year=2025,
            target_period="1T",
            taxpayer_nif="X1234567L",
        ),
    )
    read = bridge.IvaRemoteStateCaptureRead(completion=completion, projection=projection, report=report)
    monkeypatch.setattr(handler, "emit_live_auth_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bridge, "read_iva_remote_state_capture_for_cli", lambda *_args, **_kwargs: read)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.iva_wallet_pull_evidence_cmd(
        cast(typer.Context, cast(object, None)),
        year_from=2022,
        year_to=2024,
        target_year=2025,
        target_period="1T",
        taxpayer_nif="X1234567L",
        output_root=_OUTPUT_ROOT,
    )

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.iva_wallet.pull_evidence"
    result = cast(IvaWalletPullEvidenceResult, envelope["result"])
    assert result.output_root == str(_OUTPUT_ROOT)
    assert result.year_from == 2022
    assert result.year_to == 2024
    assert result.target_year == 2025
    assert result.target_period == Period.from_year_and_code(2025, "1T")
    assert result.acquisition_manifest_id == "manifest-ref"
    assert result.auth.status is LiveIvaReadStatus.FAILED
    assert result.auth.outcome_mode is LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT
    assert result.auth.provider_kind == "clave_movil"
    assert result.filed_history_succeeded is False
    assert result.wallet_succeeded is True
    assert result.outcomes[0].failure_type == "ClaveMovilApprovalTimeoutError"
    assert result.outcomes[0].failure_context == {
        "progress": {"ejercicio": 2025, "modelo": "303", "stage": "walk_declarations_register"}
    }
    assert result.outcomes[1].captured_count == 1
    lines = cast(tuple[str, ...], envelope["lines"])
    assert "filed_history_succeeded=False" in lines
    assert "wallet_succeeded=True" in lines
    assert any(
        "failure_context=progress={ejercicio:2025,modelo:303,stage:walk_declarations_register}" in line
        for line in lines
    )
