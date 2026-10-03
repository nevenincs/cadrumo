"""Frontend deadline budgets stay finite and fail closed on any non-finite instant."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from .. import deadline_budget
from ..contracts import RuntimeRefusalCode, RuntimeRefusalError
from ..deadline_budget import (
    RUNTIME_EXCHANGE_MAX_TIMEOUT_SECONDS,
    bounded_deadline_after,
    deadline_after,
    remaining_budget,
    require_finite_budget,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deadline_budget, "time", SimpleNamespace(monotonic=lambda: 1_000.0))


@pytest.mark.usefixtures("frozen_clock")
def test_remaining_budget_returns_the_positive_time_left() -> None:
    assert remaining_budget(1_002.5) == 2.5


@pytest.mark.usefixtures("frozen_clock")
@pytest.mark.parametrize("deadline", [1_000.0, 999.0, -math.inf, math.nan, math.inf])
def test_remaining_budget_refuses_expired_and_non_finite_deadlines(deadline: float) -> None:
    with pytest.raises(RuntimeRefusalError) as refused:
        remaining_budget(deadline)
    assert refused.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED


@pytest.mark.usefixtures("frozen_clock")
def test_deadline_after_offsets_the_monotonic_clock() -> None:
    assert deadline_after(3.0) == 1_003.0


@pytest.mark.parametrize("timeout", [0.0, -1.0, math.nan, math.inf])
def test_deadline_after_refuses_an_empty_or_non_finite_budget(timeout: float) -> None:
    with pytest.raises(RuntimeRefusalError) as refused:
        deadline_after(timeout)
    assert refused.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED


@pytest.mark.usefixtures("frozen_clock")
def test_bounded_deadline_after_accepts_the_inclusive_maximum() -> None:
    assert bounded_deadline_after(RUNTIME_EXCHANGE_MAX_TIMEOUT_SECONDS, subject="probe") == 1_120.0
    assert bounded_deadline_after(300.0, subject="probe", maximum_seconds=300.0) == 1_300.0


@pytest.mark.parametrize("timeout", [0.0, -1.0, 120.5, math.nan, math.inf])
def test_bounded_deadline_after_rejects_an_out_of_range_caller_budget(timeout: float) -> None:
    with pytest.raises(ValueError, match=r"^probe timeout must be finite and at most 120 seconds$"):
        bounded_deadline_after(timeout, subject="probe")


@pytest.mark.parametrize("timeout", [0.0, -1.0, math.nan, math.inf, -math.inf])
def test_require_finite_budget_refuses_an_empty_or_non_finite_budget(timeout: float) -> None:
    with pytest.raises(RuntimeRefusalError) as refused:
        require_finite_budget(timeout)
    assert refused.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED


@pytest.mark.parametrize("timeout", [0.001, 3.0, 3600.0])
def test_require_finite_budget_returns_a_positive_finite_budget_unchanged(timeout: float) -> None:
    assert require_finite_budget(timeout) == timeout
