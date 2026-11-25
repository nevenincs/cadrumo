"""A failed native signal cannot become a successful logical wake."""

import sys

import pytest

from ..native_wake import NativeWake

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires the native Windows event")
def test_failed_native_signal_remains_unset_and_can_be_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    import win32event

    wake = NativeWake()
    signal = win32event.SetEvent
    attempts = 0

    def fail_once(handle: int) -> None:
        nonlocal attempts
        if int(handle) == wake.waitable:
            attempts += 1
            if attempts == 1:
                raise OSError("synthetic native event failure")
        signal(handle)

    monkeypatch.setattr(win32event, "SetEvent", fail_once)
    with pytest.raises(OSError, match="synthetic native event failure"):
        wake.set()
    assert not wake.is_set()
    assert win32event.WaitForSingleObject(wake.waitable, 0) == win32event.WAIT_TIMEOUT
    wake.set()
    wake.set()
    assert wake.is_set()
    assert attempts == 2
    assert win32event.WaitForSingleObject(wake.waitable, 0) == win32event.WAIT_OBJECT_0
    wake.clear()
    assert not wake.is_set()
    assert win32event.WaitForSingleObject(wake.waitable, 0) == win32event.WAIT_TIMEOUT
