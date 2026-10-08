"""Native PIDFD capability used by Linux private-worker containment."""

from __future__ import annotations

import os
import select
import sys

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from .. import linux_pidfd, linux_worker_process

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_outbound_adapter,
]


@pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux PIDFD capability")
def test_native_pidfd_pins_live_process_without_inheriting_handle() -> None:
    if sys.platform != "linux":
        pytest.skip("requires native Linux PIDFD capability")
    descriptor = linux_pidfd.open_linux_pidfd(os.getpid())
    try:
        assert not os.get_inheritable(descriptor)
        poller = select.poll()
        poller.register(descriptor, select.POLLIN | select.POLLERR | select.POLLHUP)
        assert not poller.poll(0)
    finally:
        os.close(descriptor)


@pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux PIDFD capability")
def test_missing_native_pidfd_symbol_refuses_without_process_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linux_pidfd.ctypes, "CDLL", lambda *_args, **_kwargs: object())
    with pytest.raises(RuntimeRefusalError) as refused:
        linux_pidfd.open_linux_pidfd(os.getpid())
    assert refused.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


@pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux PIDFD capability")
def test_oversized_pid_refuses_before_native_integer_conversion(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_open(*_args: object, **_kwargs: object) -> object:
        pytest.fail("oversized PID must not reach the native pid_t boundary")

    monkeypatch.setattr(linux_pidfd.ctypes, "CDLL", forbidden_open)
    with pytest.raises(RuntimeRefusalError) as refused:
        linux_pidfd.open_linux_pidfd(2_147_483_648)
    assert refused.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_linux_polling_refuses_unsupported_platform_before_handle_access(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    monkeypatch.setattr(linux_worker_process.sys, "platform", platform)
    with pytest.raises(RuntimeRefusalError) as alive_refusal:
        linux_worker_process._pidfd_alive(-1)
    assert alive_refusal.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE

    process = linux_worker_process.LinuxOwnedProcess(pid=os.getpid(), pidfd=-1)
    with pytest.raises(RuntimeRefusalError) as wait_refusal:
        process.wait(timeout=0)
    assert wait_refusal.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
