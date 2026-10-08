"""The verify-capture CLI bridge accepts only its exact settled result."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.live.verify import VerifySurface
from ....application.live.verify_capture_operation import (
    VERIFY_NIF_IVA_CAPTURE_DEFINITION_ID,
    VERIFY_TGVI_CAPTURE_DEFINITION_ID,
    VerifyCapturePublicResultV1,
    VerifyCaptureRequest,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.identity_check_verdict import IdentityCheckVerdict
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_verify_capture as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_FOREIGN_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 9, 29, 10, 30, tzinfo=UTC)
_NIF = "B12345674"
_OBSERVATION_ID = "c" * 64


def _projection(
    *,
    bucket_id: UUID = _PROFILE,
    surface: VerifySurface = VerifySurface.NIF_IVA,
    nif: str = _NIF,
    expected: IdentityCheckVerdict | None = IdentityCheckVerdict.VALID,
) -> VerifyCapturePublicResultV1:
    return VerifyCapturePublicResultV1(
        bucket_id=str(bucket_id),
        observation_id=_OBSERVATION_ID,
        surface=surface,
        nif=nif,
        verdict=IdentityCheckVerdict.VALID,
        expected=expected,
        matched_expectation=True if expected is IdentityCheckVerdict.VALID else None,
        checked_at=_NOW,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: BaseModel,
    *,
    effect: OperationEffect = OperationEffect.UPDATED,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[BaseModel, dict[str, object]]], list[UUID]]:
    client = SimpleNamespace(profile_id=_PROFILE)
    bound_profiles: list[UUID] = []

    def require_client(_ctx: object) -> object:
        bound_profiles.append(client.profile_id)
        return client

    monkeypatch.setattr(bridge, "bound_profile_client", require_client)
    submitted: list[tuple[BaseModel, dict[str, object]]] = []

    def submit(
        submitted_client: object,
        request: BaseModel,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[BaseModel]:
        assert submitted_client is client
        submitted.append((request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=terminal_condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _context() -> typer.Context:
    return cast(typer.Context, cast(object, None))


@pytest.mark.parametrize(
    "effect",
    [OperationEffect.UPDATED, OperationEffect.NONE],
    ids=["new-observation", "deduplicated-observation"],
)
def test_capture_submits_exact_profile_shape_and_accepts_only_success_effects(
    monkeypatch: pytest.MonkeyPatch,
    effect: OperationEffect,
) -> None:
    submitted, bound_profiles = _bind(monkeypatch, _projection(), effect=effect)
    raw_nif = " b12345674 "

    result = bridge.read_verify_capture_for_cli(
        _context(),
        surface=VerifySurface.NIF_IVA,
        nif=raw_nif,
        expected=IdentityCheckVerdict.VALID,
    )

    assert bound_profiles == [_PROFILE]
    assert result == _projection()
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == VerifyCaptureRequest(
        profile_id=_PROFILE,
        nif=raw_nif,
        expected=IdentityCheckVerdict.VALID,
    )
    assert options["definition_id"] == VERIFY_NIF_IVA_CAPTURE_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is VerifyCapturePublicResultV1
    assert options["request_version"] == options["result_version"] == 1
    assert options["timeout"] == 120


@pytest.mark.parametrize(
    ("projection_update", "effect", "terminal_condition", "refusal_code"),
    [
        ({"bucket_id": str(_FOREIGN_PROFILE)}, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, None),
        ({"surface": VerifySurface.TGVI}, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, None),
        ({"nif": "C12345678"}, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, None),
        (
            {"expected": IdentityCheckVerdict.INVALID},
            OperationEffect.UPDATED,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        ({}, OperationEffect.UNKNOWN, OperationTerminalCondition.SUCCEEDED, None),
        ({}, OperationEffect.UPDATED, OperationTerminalCondition.REFUSED, "REFUSED_PROFILE_MISMATCH"),
        ({}, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, "REFUSED_PROFILE_MISMATCH"),
    ],
    ids=[
        "foreign-profile",
        "wrong-surface",
        "wrong-nif",
        "wrong-expectation",
        "unknown-effect",
        "refused",
        "refusal-code",
    ],
)
def test_scope_or_receipt_mismatch_is_correlated_invalid_frame(
    monkeypatch: pytest.MonkeyPatch,
    projection_update: dict[str, object],
    effect: OperationEffect,
    terminal_condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    projection = _projection().model_copy(update=projection_update)
    _bind(
        monkeypatch,
        projection,
        effect=effect,
        terminal_condition=terminal_condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        bridge.read_verify_capture_for_cli(
            _context(),
            surface=VerifySurface.NIF_IVA,
            nif=_NIF,
            expected=IdentityCheckVerdict.VALID,
        )

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
    assert error.value.context["effect"] == effect.value
    assert error.value.context["terminal_condition"] == terminal_condition.value


def test_tgvi_capture_uses_its_registered_definition(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection(surface=VerifySurface.TGVI, expected=None).model_copy(update={"matched_expectation": None})
    submitted, _bound_profiles = _bind(monkeypatch, projection, effect=OperationEffect.NONE)

    result = bridge.read_verify_capture_for_cli(
        _context(),
        surface=VerifySurface.TGVI,
        nif=_NIF,
        expected=None,
    )

    assert result.surface is VerifySurface.TGVI
    assert submitted[0][1]["definition_id"] == VERIFY_TGVI_CAPTURE_DEFINITION_ID
    assert submitted[0][1]["subject_ref"] == profile_operation_subject(str(_PROFILE))
