"""IVA history CLI routing preserves exact-profile worker accounting."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.contracts.contracts import RefusalCode

from ....application.live.iva_wallet_history_capture_operation import (
    IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID,
    IvaWalletHistoryCapturePublicResultV1,
    IvaWalletHistoryCaptureRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import app_live_iva_commands as handler
from .. import operation_iva_history_capture as bridge
from ..app_live_iva_wallet_results import IvaWalletCaptureHistoryResult
from .operation_bridge_support import bind_profile_submission

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_OUTPUT_ROOT = Path("iva-history")


def _projection() -> IvaWalletHistoryCapturePublicResultV1:
    return IvaWalletHistoryCapturePublicResultV1(
        output_root=str(_OUTPUT_ROOT),
        year_from=2023,
        year_to=2025,
        captured_count=1,
        observation_paths=("history/2025/303.json",),
        artefact_refs=("sha256:abcd",),
        casilla_count=4,
        calculation_observation_count=1,
        calculation_observation_keys=("history:2025:303",),
        reloaded_history_count=1,
        failed_declaration_count=1,
        failed_declarations=("303/2024/4T",),
    )


_bind = partial(
    bind_profile_submission,
    bridge=bridge,
    operation_id=_OPERATION_ID,
    profile_id=_PROFILE,
)


def _read() -> bridge.IvaWalletHistoryCaptureRead:
    return bridge.read_iva_wallet_history_capture_for_cli(
        cast(typer.Context, cast(object, None)),
        year_from=2023,
        year_to=2025,
        output_root=_OUTPUT_ROOT,
    )


def test_registered_history_capture_uses_exact_profile_and_preserves_accounting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted, bound_profiles = _bind(monkeypatch, _projection(), effect=OperationEffect.UPDATED)

    read = _read()

    assert read.completion.operation_id == _OPERATION_ID
    assert read.projection == _projection()
    assert bound_profiles == [_PROFILE]
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == IvaWalletHistoryCaptureRequest(
        profile_id=_PROFILE,
        output_root=_OUTPUT_ROOT,
        year_from=2023,
        year_to=2025,
    )
    assert options["definition_id"] == IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is IvaWalletHistoryCapturePublicResultV1
    assert options["request_version"] == 1
    assert options["result_version"] == 1


def test_history_capture_without_a_named_root_leaves_the_default_to_the_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted, _bound_profiles = _bind(monkeypatch, _projection(), effect=OperationEffect.UPDATED)

    read = bridge.read_iva_wallet_history_capture_for_cli(
        cast(typer.Context, cast(object, None)), year_from=2023, year_to=2025, output_root=None
    )

    assert submitted[0][0].output_root is None
    assert read.projection.output_root == str(_OUTPUT_ROOT)


@pytest.mark.parametrize("mismatch", ["output_root", "year_range", "effect", "terminal", "refusal"])
def test_mismatched_scope_or_receipt_refuses_with_correlated_operation(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    condition = OperationTerminalCondition.SUCCEEDED
    refusal_code = None
    if mismatch == "output_root":
        projection = projection.model_copy(update={"output_root": "other-root"})
    elif mismatch == "year_range":
        projection = projection.model_copy(update={"year_to": 2024})
    elif mismatch == "effect":
        effect = OperationEffect.NONE
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    elif mismatch == "refusal":
        refusal_code = RefusalCode.UNAVAILABLE.value
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
    assert error.value.context["reason"] == RefusalCode.INVALID_FRAME.value


def test_history_command_emits_existing_cli_payload_from_registered_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.UPDATED,
    )
    read = bridge.IvaWalletHistoryCaptureRead(completion=completion, projection=projection)
    monkeypatch.setattr(handler, "emit_live_auth_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handler, "resolve_optional_root", lambda value, _default: value or _OUTPUT_ROOT)
    monkeypatch.setattr(bridge, "read_iva_wallet_history_capture_for_cli", lambda *_args, **_kwargs: read)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.iva_wallet_pull_history_cmd(
        cast(typer.Context, cast(object, None)), year_from=2023, year_to=2025, output_root=_OUTPUT_ROOT
    )

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.iva_wallet.pull_history"
    result = cast(IvaWalletCaptureHistoryResult, envelope["result"])
    assert result.output_root == str(_OUTPUT_ROOT)
    assert result.year_from == 2023
    assert result.year_to == 2025
    assert result.captured_count == 1
    assert result.casilla_count == 4
    assert result.observation_paths == ["history/2025/303.json"]
    assert result.artefact_refs == ["sha256:abcd"]
    assert result.calculation_observation_keys == ["history:2025:303"]
    assert result.reloaded_history_count == 1
    assert result.failed_declaration_count == 1
    assert result.failed_declarations == ["303/2024/4T"]
    lines = envelope["lines"]
    assert isinstance(lines, tuple)
    assert "captured_count=1" in lines
    assert "calculation_observation_count=1" in lines
    assert "failed_declaration_count=1" in lines
