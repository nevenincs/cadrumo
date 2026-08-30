"""Real model-boundary tests for generic operation state."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import cast

import pytest
from pydantic import BaseModel, ConfigDict, PrivateAttr, ValidationError

from ....core import STRICT_FROZEN_CONFIG
from ....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ..models import (
    OperationIdentity,
    OperationRequest,
    OperationSnapshot,
    OperationTerminalReceipt,
    new_operation_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
_OPERATION_ID = "a" * 64


class SubmittedPayload(BaseModel):
    """Typed domain-owned operand used to exercise the generic request boundary."""

    model_config = STRICT_FROZEN_CONFIG

    value: int


class NonStrictPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: int


class NonFrozenPayload(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    value: int


class MutableListPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: list[int]


class MutableNestedPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: tuple[dict[str, int], ...]


class MappingProxyPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: object


class PrivateStatePayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: int
    _history: list[int] = PrivateAttr(default_factory=list)


class RecursivePayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    child: RecursivePayload | None = None


class NestedValue(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    amount: int


class NestedImmutablePayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    child: NestedValue
    labels: tuple[str, ...]


def _identity() -> OperationIdentity:
    return OperationIdentity(
        operation_id=_OPERATION_ID,
        definition_id="profile.censo.pull",
        subject_ref="profile:active",
    )


def _request() -> OperationRequest[SubmittedPayload]:
    return OperationRequest[SubmittedPayload](
        definition_id="profile.censo.pull",
        subject_ref="profile:active",
        payload=SubmittedPayload(value=7),
        idempotency_key="pull-2026-08-13",
    )


def test_non_terminal_snapshot_roundtrips_as_an_immutable_typed_request() -> None:
    snapshot = OperationSnapshot[SubmittedPayload](
        identity=_identity(),
        request=_request(),
        revision=3,
        lifecycle=OperationLifecycle.RUNNING,
        effect=OperationEffect.UPDATED,
        phase_code="remote_read",
        updated_at=_NOW,
        event_cursor=12,
    )

    restored = OperationSnapshot[SubmittedPayload].model_validate_json(snapshot.model_dump_json())

    assert restored == snapshot
    assert isinstance(restored.request.payload, SubmittedPayload)
    with pytest.raises(ValidationError, match="frozen_instance"):
        restored.revision = 4


def test_terminal_snapshot_requires_one_exact_correlated_receipt() -> None:
    identity = _identity()
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=4,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=_NOW,
        result_ref="result:profile-censo",
    )

    snapshot = OperationSnapshot[SubmittedPayload](
        identity=identity,
        request=_request(),
        revision=4,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        phase_code="settled",
        updated_at=_NOW,
        event_cursor=18,
        terminal_receipt=receipt,
    )

    assert snapshot.terminal_receipt == receipt


@pytest.mark.parametrize(
    "changed",
    [
        {"revision": 5},
        {"condition": OperationTerminalCondition.FAILED},
        {"effect": OperationEffect.PARTIAL},
        {"settled_at": datetime(2026, 8, 13, 12, 1, tzinfo=UTC)},
    ],
)
def test_terminal_snapshot_refuses_receipt_drift(changed: dict[str, object]) -> None:
    identity = _identity()
    receipt_fields: dict[str, object] = {
        "identity": identity,
        "revision": 4,
        "condition": OperationTerminalCondition.SUCCEEDED,
        "effect": OperationEffect.UPDATED,
        "settled_at": _NOW,
        "result_ref": "result:profile-censo",
    }
    receipt_fields.update(changed)
    receipt = OperationTerminalReceipt.model_validate(receipt_fields)

    with pytest.raises(ValidationError, match="terminal receipt"):
        OperationSnapshot[SubmittedPayload](
            identity=identity,
            request=_request(),
            revision=4,
            lifecycle=OperationLifecycle.TERMINAL,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.UPDATED,
            updated_at=_NOW,
            terminal_receipt=receipt,
        )


def test_terminal_condition_is_forbidden_before_terminal_lifecycle() -> None:
    with pytest.raises(ValidationError, match="terminal lifecycle requires exactly one terminal condition"):
        OperationSnapshot[SubmittedPayload](
            identity=_identity(),
            request=_request(),
            revision=1,
            lifecycle=OperationLifecycle.RUNNING,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.NONE,
            updated_at=_NOW,
        )


def test_request_identity_drift_is_refused() -> None:
    request = OperationRequest[SubmittedPayload](
        definition_id="profile.censo.apply",
        subject_ref="profile:active",
        payload=SubmittedPayload(value=7),
    )

    with pytest.raises(ValidationError, match="request definition"):
        OperationSnapshot[SubmittedPayload](
            identity=_identity(),
            request=request,
            revision=0,
            lifecycle=OperationLifecycle.CREATED,
            updated_at=_NOW,
        )


def test_terminal_receipt_enforces_result_and_refusal_meaning() -> None:
    with pytest.raises(ValidationError, match="succeeded operation requires one result reference"):
        OperationTerminalReceipt(
            identity=_identity(),
            revision=1,
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.NONE,
            settled_at=_NOW,
        )

    refusal = OperationTerminalReceipt(
        identity=_identity(),
        revision=1,
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        settled_at=_NOW,
        refusal_ref="refusal:precondition",
    )
    assert refusal.refusal_ref == "refusal:precondition"

    failed = OperationTerminalReceipt(
        identity=_identity(),
        revision=1,
        condition=OperationTerminalCondition.FAILED,
        effect=OperationEffect.NONE,
        settled_at=_NOW,
        diagnostic_ref="sha256:0123456789ab",
    )
    assert failed.diagnostic_ref == "sha256:0123456789ab"

    with pytest.raises(ValidationError):
        OperationTerminalReceipt(
            identity=_identity(),
            revision=1,
            condition=OperationTerminalCondition.FAILED,
            effect=OperationEffect.NONE,
            settled_at=_NOW,
            diagnostic_ref="C:/Users/operator/private.log",
        )


def test_operation_identity_is_random_hex64_and_definition_ids_are_closed_by_shape() -> None:
    first = new_operation_id()
    second = new_operation_id()

    assert len(first) == 64
    assert first != second
    assert set(first) <= set("0123456789abcdef")
    with pytest.raises(ValidationError, match="definition_id"):
        OperationIdentity(operation_id=first, definition_id="CLI Profile Pull", subject_ref="profile:active")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (NonStrictPayload(value=1), "must set strict=True"),
        (NonFrozenPayload(value=1), "must set frozen=True"),
        (MutableListPayload(values=[1, 2]), "payload.values contains mutable or unsupported list"),
        (MutableNestedPayload(values=({"mutable": 1},)), r"payload.values\[0\] contains mutable or unsupported dict"),
    ],
)
def test_operation_request_refuses_payloads_without_deep_immutability(
    payload: BaseModel,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        OperationRequest[BaseModel](
            definition_id="profile.censo.pull",
            subject_ref="profile:active",
            payload=payload,
        )


def test_operation_request_refuses_mapping_proxy_with_mutable_backing() -> None:
    backing = {"value": 1}
    payload = MappingProxyPayload(values=MappingProxyType(backing))

    with pytest.raises(ValidationError, match="mutable or unsupported mappingproxy"):
        OperationRequest[MappingProxyPayload](
            definition_id="profile.censo.pull",
            subject_ref="profile:active",
            payload=payload,
        )

    backing["value"] = 2
    view = cast(Mapping[str, int], payload.values)
    assert view["value"] == 2


def test_operation_request_refuses_private_payload_state() -> None:
    with pytest.raises(ValidationError, match="must not declare private mutable state"):
        OperationRequest[PrivateStatePayload](
            definition_id="profile.censo.pull",
            subject_ref="profile:active",
            payload=PrivateStatePayload(value=1),
        )


def test_operation_request_refuses_cyclic_payload_with_controlled_validation_error() -> None:
    payload = RecursivePayload.model_construct(child=None)
    object.__setattr__(payload, "child", payload)

    with pytest.raises(ValidationError, match=r"payload\.child contains a cyclic reference"):
        OperationRequest[RecursivePayload](
            definition_id="profile.censo.pull",
            subject_ref="profile:active",
            payload=payload,
        )


def test_operation_request_admits_nested_strict_frozen_payload() -> None:
    payload = NestedImmutablePayload(child=NestedValue(amount=3), labels=("remote", "reviewed"))

    request = OperationRequest[NestedImmutablePayload](
        definition_id="profile.censo.pull",
        subject_ref="profile:active",
        payload=payload,
    )

    assert request.payload == payload
