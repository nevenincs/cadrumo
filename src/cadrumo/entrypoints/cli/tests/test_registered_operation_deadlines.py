"""Registered CLI exchanges refuse empty, expired and non-finite time budgets before any native call."""

from __future__ import annotations

import math
import time
from typing import Never, cast, override
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import RuntimeOperationRequest
from cadrumo.core.config import override_settings

from ..registered_operation_contracts import RegisteredOperationProgress
from ..registered_operation_deadlines import operation_settlement_deadline, provider_login_settlement_seconds
from ..registered_operation_exchange import RegisteredOperationExchange
from ..runtime_registered_operation import run_registered_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _UntouchableClient:
    """Fails the test on any native access, proving the budget was refused first."""

    @override
    def __getattribute__(self, name: str) -> Never:
        raise AssertionError(f"the runtime client was used ({name}) after a refused budget")


class _Payload(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


def _exchange(deadline: float) -> RegisteredOperationExchange:
    return RegisteredOperationExchange(
        cast("RuntimeFrontendClient", _UntouchableClient()),
        uuid4(),
        uuid4(),
        OperationFrontendProjection.CLI,
        deadline,
        lambda: time.monotonic() + 1,
        RegisteredOperationProgress(),
    )


@pytest.mark.parametrize("offset", [math.nan, math.inf, -math.inf, -1.0])
def test_exchange_refuses_an_expired_or_non_finite_settlement_deadline_before_the_client(offset: float) -> None:
    deadline = offset if not math.isfinite(offset) else time.monotonic() + offset
    with pytest.raises(RuntimeRefusalError) as refused:
        _exchange(deadline)(cast("RuntimeOperationRequest", object()))

    assert refused.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED


@pytest.mark.parametrize("timeout", [math.nan, math.inf, -math.inf, 0.0, -1.0, 120.5])
def test_per_exchange_timeout_outside_the_bound_is_refused_before_the_client(timeout: float) -> None:
    with pytest.raises(ValueError, match=r"^modelo operation timeout must be finite and at most 120 seconds$"):
        run_registered_operation(
            cast("RuntimeFrontendClient", _UntouchableClient()),
            _Payload(),
            definition_id="profile.synthetic",
            subject_ref="subject",
            result_type=_Payload,
            request_version=1,
            result_version=1,
            timeout=timeout,
        )


@pytest.mark.parametrize("settlement_timeout", [math.nan, math.inf, 1.0, 3600.5])
def test_settlement_wait_must_be_finite_between_the_timeout_and_one_hour(settlement_timeout: float) -> None:
    with pytest.raises(ValueError, match=r"^operation settlement wait must be finite"):
        operation_settlement_deadline(5.0, settlement_timeout)


def test_settlement_deadline_is_offset_from_the_monotonic_clock() -> None:
    before = time.monotonic()
    deadline = operation_settlement_deadline(5.0, 60.0)
    after = time.monotonic()

    assert before + 60.0 <= deadline <= after + 60.0
    assert before + 5.0 <= operation_settlement_deadline(5.0, None) <= time.monotonic() + 5.0


def test_a_live_read_outwaits_a_fresh_provider_login_before_its_own_budget() -> None:
    """Stopping earlier disconnects the command, retiring its lease and the worker's key custody mid-login."""
    with override_settings(cadrumo_clave_movil_timeout_ms=90_000, cadrumo_browser_navigation_timeout_ms=20_000):
        wait = provider_login_settlement_seconds(after_login=120)
        before = time.monotonic()
        deadline = operation_settlement_deadline(120, wait)

    # 90 s approval window, three 20 s navigations, then the read's own 120 s.
    assert wait == 270.0
    assert deadline - before >= 90 + 120
