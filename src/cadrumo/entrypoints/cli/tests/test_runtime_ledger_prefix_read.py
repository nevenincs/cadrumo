"""Prefix-addressed ledger reads accept only a read-only result for the submitted profile and prefix."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_ledger_prefix_read as prefix_read
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "b" * 64
_DEFINITION_ID = "ledger.example"


class _Request(BaseModel):
    profile_id: UUID
    transaction_prefix: str


class _Projection(BaseModel):
    profile_id: UUID
    transaction_prefix: str | None
    include_siblings: bool = False


class _Foreign(BaseModel):
    note: str


def _client() -> RuntimeFrontendClient:
    return cast(RuntimeFrontendClient, SimpleNamespace(profile_id=_PROFILE))


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: BaseModel,
    *,
    effect: OperationEffect = OperationEffect.NONE,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> list[dict[str, object]]:
    submitted: list[dict[str, object]] = []

    def run(_client: object, _request: object, **options: object) -> RegisteredOperationCompletion[BaseModel]:
        submitted.append(options)
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(prefix_read, "run_registered_operation", run)
    return submitted


def _context(error: CliRefusedBoundaryError) -> Mapping[str, object]:
    assert error.context is not None
    return error.context


def _accept_any(_result: _Projection) -> bool:
    return True


def _read(prefix: str | None = "ab", *, extra_matches: Callable[[_Projection], bool] = _accept_any) -> _Projection:
    return prefix_read.read_ledger_prefix_projection(
        _client(),
        _Request(profile_id=_PROFILE, transaction_prefix=prefix or "ab"),
        prefix=prefix,
        definition_id=_DEFINITION_ID,
        result_type=_Projection,
        extra_matches=extra_matches,
    )


def test_a_read_only_result_for_the_submitted_profile_and_prefix_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _Projection(profile_id=_PROFILE, transaction_prefix="ab")
    submitted = _bind(monkeypatch, projection)

    assert _read("ab") == projection
    (options,) = submitted
    assert options["definition_id"] == _DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["request_version"] == options["result_version"] == 1


def test_an_unfiltered_read_must_come_back_without_a_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _Projection(profile_id=_PROFILE, transaction_prefix=None)
    _bind(monkeypatch, projection)

    assert _read(None) == projection


@pytest.mark.parametrize(
    "projection",
    [
        _Projection(profile_id=UUID("5bb00000-0000-4000-8000-0000000000bb"), transaction_prefix="ab"),
        _Projection(profile_id=_PROFILE, transaction_prefix="cd"),
        _Projection(profile_id=_PROFILE, transaction_prefix=None),
        _Foreign(note="not a prefix-scoped projection"),
    ],
)
def test_a_result_for_another_profile_or_prefix_is_an_invalid_frame_that_keeps_the_receipt(
    monkeypatch: pytest.MonkeyPatch, projection: BaseModel
) -> None:
    _bind(monkeypatch, projection)

    with pytest.raises(CliRefusedBoundaryError) as error:
        _read("ab")

    assert _context(error.value)["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
    assert _context(error.value)["operation_id"] == _OPERATION_ID
    assert _context(error.value)["effect"] == OperationEffect.NONE.value
    assert _context(error.value)["terminal_condition"] == OperationTerminalCondition.SUCCEEDED.value


def test_a_mismatched_result_keeps_the_refusal_code_of_its_settled_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    _bind(
        monkeypatch,
        _Projection(profile_id=_PROFILE, transaction_prefix="cd"),
        condition=OperationTerminalCondition.REFUSED,
        refusal_code="REFUSED_EXAMPLE",
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        _read("ab")

    assert _context(error.value)["refusal_code"] == "REFUSED_EXAMPLE"
    assert _context(error.value)["terminal_condition"] == OperationTerminalCondition.REFUSED.value


def test_a_receipt_that_claims_an_effect_is_refused_even_when_the_projection_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind(
        monkeypatch,
        _Projection(profile_id=_PROFILE, transaction_prefix="ab"),
        effect=OperationEffect.UPDATED,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        _read("ab")

    assert _context(error.value)["effect"] == OperationEffect.UPDATED.value


def test_extra_matches_can_refuse_an_otherwise_correlated_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _bind(monkeypatch, _Projection(profile_id=_PROFILE, transaction_prefix="ab", include_siblings=False))

    assert _read("ab", extra_matches=lambda result: not result.include_siblings).include_siblings is False
    with pytest.raises(CliRefusedBoundaryError):
        _read("ab", extra_matches=lambda result: result.include_siblings)


def test_a_worker_refusal_is_annotated_with_the_prefix_verdict_and_re_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    refusal = CliRefusedBoundaryError(RuntimeRefusalCode.UNAVAILABLE.value)
    annotated: list[CliRefusedBoundaryError] = []

    def run(*_args: object, **_options: object) -> RegisteredOperationCompletion[BaseModel]:
        raise refusal

    monkeypatch.setattr(prefix_read, "run_registered_operation", run)
    monkeypatch.setattr(prefix_read, "attach_submitted_ledger_prefix_verdict", annotated.append)

    with pytest.raises(CliRefusedBoundaryError) as raised:
        _read("ab")

    assert raised.value is refusal
    assert annotated == [refusal]
