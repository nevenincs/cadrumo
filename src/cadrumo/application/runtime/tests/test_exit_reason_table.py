"""The runtime exit-reason table keeps every reason distinct and clear of codes owned elsewhere."""

from __future__ import annotations

import signal

import pytest

from cadrumo.application.runtime.contracts import (
    RESERVED_RUNTIME_EXIT_CODES,
    RuntimeExitReason,
    RuntimeRefusalCode,
    runtime_refusal_exit_reason,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_STATUS_CONTROL_C_EXIT = 0xC000013A
_STATUS_ACCESS_VIOLATION = 0xC0000005
_STATUS_STACK_BUFFER_OVERRUN = 0xC0000409
_STATUS_BREAKPOINT = 0x80000003


def _reserved(code: int) -> bool:
    return any(code in reserved for reserved in RESERVED_RUNTIME_EXIT_CODES)


def test_every_supervisor_reason_has_its_own_code() -> None:
    assert {reason.name for reason in RuntimeExitReason} == {
        "SUPERVISOR_STOP",
        "SIGNAL_STOP",
        "SESSION_END_SETTLE",
        "OWNER_BUSY",
        "ROOT_MISMATCH",
        "VERSION_MISMATCH",
        "LOGIN_WITNESS_LOSS",
        "DRAIN_WATCHDOG",
        "ELEVATED_TOKEN_REFUSED",
        "UNEXPECTED_FAILURE",
    }
    codes = [reason.value for reason in RuntimeExitReason]
    assert len(set(codes)) == len(codes)
    assert codes == list(range(64, 74))


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(1, id="python-failure"),
        pytest.param(2, id="argparse-usage"),
        pytest.param(3, id="c-runtime-abort"),
        *(pytest.param(code, id=f"native-host-{code}") for code in range(120, 125)),
        *(pytest.param(128 + number, id=f"posix-signal-{number}") for number in (1, 2, 6, 9, 15, 64)),
        pytest.param(_STATUS_CONTROL_C_EXIT, id="status-control-c-exit"),
        pytest.param(_STATUS_ACCESS_VIOLATION, id="status-access-violation"),
        pytest.param(_STATUS_STACK_BUFFER_OVERRUN, id="status-stack-buffer-overrun"),
        pytest.param(_STATUS_BREAKPOINT, id="status-breakpoint"),
    ],
)
def test_codes_owned_elsewhere_are_reserved_and_never_a_reason(code: int) -> None:
    assert _reserved(code)
    assert code not in {reason.value for reason in RuntimeExitReason}


def test_no_reason_lies_in_a_reserved_range_or_beyond_a_posix_status_byte() -> None:
    assert not [reason for reason in RuntimeExitReason if _reserved(reason.value)]
    assert all(0 < reason.value <= 0xFF for reason in RuntimeExitReason)
    assert not _reserved(0)


def test_posix_signal_reservation_covers_every_signal_this_platform_defines() -> None:
    numbers = {int(number) for number in signal.Signals}
    assert all(_reserved(128 + number) for number in numbers)


@pytest.mark.parametrize(
    ("refusal", "reason"),
    [
        (RuntimeRefusalCode.OWNER_BUSY, RuntimeExitReason.OWNER_BUSY),
        (RuntimeRefusalCode.ROOT_MISMATCH, RuntimeExitReason.ROOT_MISMATCH),
        (RuntimeRefusalCode.VERSION_MISMATCH, RuntimeExitReason.VERSION_MISMATCH),
        (RuntimeRefusalCode.UNAVAILABLE, RuntimeExitReason.UNEXPECTED_FAILURE),
        (RuntimeRefusalCode.ENDPOINT_UNTRUSTED, RuntimeExitReason.UNEXPECTED_FAILURE),
        (RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE, RuntimeExitReason.UNEXPECTED_FAILURE),
    ],
)
def test_refusals_map_to_their_exit_reason(refusal: RuntimeRefusalCode, reason: RuntimeExitReason) -> None:
    assert runtime_refusal_exit_reason(refusal) is reason


def test_every_refusal_has_an_exit_reason_outside_the_reserved_codes() -> None:
    for refusal in RuntimeRefusalCode:
        assert not _reserved(runtime_refusal_exit_reason(refusal).value)
