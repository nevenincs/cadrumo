"""Portable Darwin native-record validation, without claiming a native kqueue run."""

from __future__ import annotations

import asyncio
import ctypes
import errno
from types import SimpleNamespace

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources

from .. import macos_process as native
from ..macos_process import _BsdProcessInfo, decode_macos_process_info

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _record() -> _BsdProcessInfo:
    value = _BsdProcessInfo()
    value.pid, value.parent_pid, value.group_id = 123, 100, 123
    value.uid = value.real_uid = value.saved_uid = 501
    value.status = 2
    value.started_seconds, value.started_microseconds = 1000, 500
    return value


def _payload(record: _BsdProcessInfo) -> bytes:
    return ctypes.string_at(ctypes.byref(record), ctypes.sizeof(record))


def test_process_record_retains_creation_identity_and_owner_without_account_names() -> None:
    first = decode_macos_process_info(_payload(_record()), pid=123, expected_owner="501")
    assert first.pid == first.process_group_id == 123 and first.parent_pid == 100
    assert first.os_owner_id == "501" and (first.started_seconds, first.started_microseconds) == (1000, 500)
    successor = _record()
    successor.started_microseconds = 501
    assert decode_macos_process_info(_payload(successor), pid=123, expected_owner="501") != first


@pytest.mark.parametrize(
    "field,value",
    [
        ("pid", 124),
        ("uid", 502),
        ("real_uid", 502),
        ("saved_uid", 502),
        ("status", 5),
        ("flags", 4),
        ("started_seconds", 0),
        ("started_microseconds", 1_000_000),
        ("group_id", 0),
    ],
)
def test_foreign_reused_or_exiting_native_process_evidence_refuses(field: str, value: int) -> None:
    record = _record()
    setattr(record, field, value)
    with pytest.raises(RuntimeRefusalError) as caught:
        decode_macos_process_info(_payload(record), pid=123, expected_owner="501")
    assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED


def test_partial_native_process_record_cannot_be_used_as_an_identity() -> None:
    with pytest.raises(RuntimeRefusalError):
        decode_macos_process_info(_payload(_record())[:-1], pid=123, expected_owner="501")


class _NativeQuery:
    argtypes: tuple[object, ...] = ()
    restype: object = None

    def __init__(self, *, count: int, error_number: int, record: _BsdProcessInfo) -> None:
        self.count = count
        self.error_number = error_number
        self.record = record

    def __call__(self, pid: int, flavor: int, argument: int, buffer: ctypes.c_void_p, size: int) -> int:
        assert pid == 123 and flavor == 3 and argument == 0 and size == ctypes.sizeof(_BsdProcessInfo)
        ctypes.memmove(buffer, ctypes.byref(self.record), size)
        ctypes.set_errno(self.error_number)
        return self.count


class _NativeLibrary:
    def __init__(self, query: _NativeQuery) -> None:
        self.proc_pidinfo = query


@pytest.mark.parametrize(
    "count,error_number,foreign,expected",
    [
        (0, errno.EPERM, False, RuntimeRefusalCode.UNAVAILABLE),
        (0, errno.ESRCH, False, RuntimeRefusalCode.PEER_UNTRUSTED),
        (135, errno.EPERM, False, RuntimeRefusalCode.PEER_UNTRUSTED),
        (136, errno.EPERM, True, RuntimeRefusalCode.PEER_UNTRUSTED),
    ],
)
def test_only_zero_count_native_permission_transition_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    error_number: int,
    foreign: bool,
    expected: RuntimeRefusalCode,
) -> None:
    record = _record()
    if foreign:
        record.uid = record.real_uid = record.saved_uid = 502
    query = _NativeQuery(count=count, error_number=error_number, record=record)

    def load(name: str, *, use_errno: bool) -> _NativeLibrary:
        assert name == "/usr/lib/libproc.dylib" and use_errno
        return _NativeLibrary(query)

    monkeypatch.setattr(native.sys, "platform", "darwin")
    monkeypatch.setattr(native.ctypes, "CDLL", load)
    with pytest.raises(RuntimeRefusalError) as refused:
        native.read_macos_process(123, expected_owner="501")
    assert refused.value.reason is expected


class _NativeWatchCall:
    argtypes: tuple[object, ...] = ()
    restype: object = None

    def __init__(self, result: int) -> None:
        self.result = result

    def __call__(self, *arguments: object) -> int:
        return self.result


class _WatchNativePort:
    def __init__(self, *, initial: BaseException | None = None, close_failure: BaseException | None = None) -> None:
        self.initial = initial
        self.close_failure = close_failure
        self.close_calls: list[int] = []
        self.inheritance: list[tuple[int, bool]] = []

    def set_inheritable(self, descriptor: int, inheritable: bool) -> None:
        self.inheritance.append((descriptor, inheritable))
        if self.initial is not None:
            raise self.initial

    def close(self, descriptor: int) -> None:
        self.close_calls.append(descriptor)
        if self.close_failure is not None:
            raise self.close_failure

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        query = _NativeQuery(count=ctypes.sizeof(_BsdProcessInfo), error_number=0, record=_record())
        system = SimpleNamespace(kqueue=_NativeWatchCall(17), kevent=_NativeWatchCall(0))

        def load(name: str, *, use_errno: bool) -> _NativeLibrary | SimpleNamespace:
            assert use_errno
            if name == "/usr/lib/libproc.dylib":
                return _NativeLibrary(query)
            assert name == "/usr/lib/libSystem.B.dylib"
            return system

        # Isolate the native seam; the real interpreter's platform and ctypes
        # remain unchanged while record decoding and watch ownership run.
        monkeypatch.setattr(native, "sys", SimpleNamespace(platform="darwin"))
        monkeypatch.setattr(native, "ctypes", SimpleNamespace(**{**vars(ctypes), "CDLL": load}))
        monkeypatch.setattr(native, "os", SimpleNamespace(set_inheritable=self.set_inheritable, close=self.close))


def _constructor_primary(mode: str) -> BaseException:
    if mode == "typed":
        return RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    if mode == "cancel":
        return asyncio.CancelledError("original constructor cancellation")
    assert mode == "native"
    return OSError(errno.EPERM, "native registration failed")


def _assert_constructor_primary(error: BaseException, original: BaseException, mode: str) -> None:
    if mode == "native":
        assert isinstance(error, RuntimeRefusalError)
        assert error.reason is RuntimeRefusalCode.UNAVAILABLE
        assert error.__cause__ is original
    else:
        assert error is original


def test_native_close_error_retires_watch_without_closing_reused_descriptor(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = OSError(errno.EIO, "native close outcome uncertain")
    port = _WatchNativePort(close_failure=failure)
    port.install(monkeypatch)
    observation = decode_macos_process_info(_payload(_record()), pid=123, expected_owner="501")
    watch = native.MacosProcessWatch(observation)
    assert port.inheritance == [(17, False)]
    with pytest.raises(OSError) as caught:
        watch.close()
    assert caught.value is failure
    with pytest.raises(RuntimeRefusalError) as retired:
        watch.wait(timeout=0)
    assert retired.value.reason is RuntimeRefusalCode.UNAVAILABLE
    # The same numeric slot may now belong to somebody else. This port's
    # failure does not certify physical release; a second close is forbidden.
    port.close_failure = None
    watch.close()
    assert port.close_calls == [17]


@pytest.mark.parametrize("mode", ["typed", "cancel", "native"])
def test_failed_constructor_preserves_primary_and_native_close_diagnostic(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    original = _constructor_primary(mode)
    cleanup = OSError(errno.EIO, "native close outcome uncertain")
    port = _WatchNativePort(initial=original, close_failure=cleanup)
    port.install(monkeypatch)
    observation = decode_macos_process_info(_payload(_record()), pid=123, expected_owner="501")
    with pytest.raises(BaseException) as caught:
        native.MacosProcessWatch(observation)
    _assert_constructor_primary(caught.value, original, mode)
    assert caught.value.__dict__["cleanup_error"] is cleanup
    assert port.inheritance == [(17, False)]
    assert port.close_calls == [17]


@pytest.mark.parametrize("mode", ["typed", "cancel", "native"])
def test_failed_constructor_successful_close_keeps_primary(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    original = _constructor_primary(mode)
    port = _WatchNativePort(initial=original)
    port.install(monkeypatch)
    observation = decode_macos_process_info(_payload(_record()), pid=123, expected_owner="501")
    with pytest.raises(BaseException) as caught:
        native.MacosProcessWatch(observation)
    _assert_constructor_primary(caught.value, original, mode)
    assert "cleanup_error" not in caught.value.__dict__
    assert port.close_calls == [17]


class _EarlierCleanupOwner:
    def __init__(self) -> None:
        self.calls = 0

    async def close(self) -> None:
        self.calls += 1
        if self.calls == 1:
            raise OSError(errno.EIO, "earlier independent resource close failed")


@pytest.mark.parametrize("mode", ["typed", "cancel", "native"])
@pytest.mark.parametrize("field", ["cleanup_error", "async_cleanup_error", "aliased"])
def test_constructor_close_failure_preserves_existing_canonical_cleanup_owners(
    monkeypatch: pytest.MonkeyPatch, field: str, mode: str
) -> None:
    earlier = _EarlierCleanupOwner()
    with pytest.raises(AsyncResourceCleanupError) as prior:
        asyncio.run(close_async_resources(earlier, task_name="earlier-cleanup", primary_error=None))
    assert prior.value.resources == (earlier,)
    original = _constructor_primary(mode)
    if field == "aliased":
        original.__dict__["cleanup_error"] = original.__dict__["async_cleanup_error"] = prior.value
    else:
        original.__dict__[field] = prior.value
    cleanup = OSError(errno.EIO, "native close outcome uncertain")
    port = _WatchNativePort(initial=original, close_failure=cleanup)
    port.install(monkeypatch)
    observation = decode_macos_process_info(_payload(_record()), pid=123, expected_owner="501")
    with pytest.raises(BaseException) as caught:
        native.MacosProcessWatch(observation)
    _assert_constructor_primary(caught.value, original, mode)
    retained = caught.value.__dict__["cleanup_error" if field == "aliased" else field]
    assert isinstance(retained, AsyncResourceCleanupError)
    assert retained.resources == (earlier,)
    if field in {"cleanup_error", "aliased"}:
        assert retained.__cause__ is cleanup
        if field == "aliased":
            assert caught.value.__dict__["async_cleanup_error"] is retained
    else:
        assert retained is prior.value
        assert caught.value.__dict__["cleanup_error"] is cleanup
    asyncio.run(retained.retry_cleanup())
    assert earlier.calls == 2
    assert port.close_calls == [17]
