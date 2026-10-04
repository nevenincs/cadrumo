"""GNOME observer protocol, native association and login release fences.

Protocol fixtures exercise decisions without claiming compositor acceptance.
Actual desktop activation and lifecycle acceptance require a provisioned host.
"""

from __future__ import annotations

import ctypes
import os
import sys
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility
from cadrumo.core.config import override_settings

from .. import linux_gnome_lock, linux_login, linux_logind_native
from ..linux_gnome_lock import (
    GNOME_LOGIN_BUS_NAME,
    GNOME_LOGIN_OBJECT_PATH,
    GnomeLockBinding,
    GnomeLockState,
    read_gnome_lock_state,
    sample_gnome_lock,
)
from ..linux_login import LinuxLoginBinding
from ..linux_login_models import LinuxSessionObservation
from ..linux_pidfd import open_linux_pidfd

pytestmark = [pytest.mark.hex_outbound_adapter, pytest.mark.unit]

_EPOCH = UUID("a1111111-1111-4111-8111-111111111111")
_BOOT = UUID("22222222-2222-4222-8222-222222222222")
_OWNER = b":1.42"
_STATE: tuple[int | bytes, ...] = (1, str(_EPOCH).encode(), 1, 0, 0, 0, b"user")


class _ProtocolBus:
    def __init__(self, state: tuple[int | bytes, ...] = _STATE) -> None:
        self.state = state
        self.values: deque[int | bytes] = deque()
        self.calls: list[tuple[bytes, bytes, bytes, bytes, bytes | None]] = []
        self.owner_reads = 0
        self.change_owner_after_state = False
        self.uid = 1000
        self.pid = 42

    @contextmanager
    def call(
        self, destination: bytes, path: bytes, interface: bytes, method: bytes, argument: bytes | None = None
    ) -> Generator[ctypes.c_void_p]:
        self.calls.append((destination, path, interface, method, argument))
        if method == b"GetState":
            assert destination == _OWNER
            assert path == GNOME_LOGIN_OBJECT_PATH and interface == GNOME_LOGIN_BUS_NAME
            assert argument is None
            self.values = deque(self.state)
        elif method == b"GetId":
            self.values = deque([b"a" * 32])
        elif method == b"GetNameOwner":
            self.owner_reads += 1
            changed = self.change_owner_after_state and self.owner_reads > 3
            self.values = deque([b":1.99" if changed else _OWNER])
        elif method == b"GetConnectionUnixUser":
            self.values = deque([self.uid])
        elif method == b"GetConnectionUnixProcessID":
            self.values = deque([self.pid])
        else:
            raise AssertionError(method)
        yield ctypes.c_void_p(1)

    def read_string(self, reply: ctypes.c_void_p, kind: bytes, *, maximum: int = 128) -> bytes:
        assert reply.value == 1 and kind in (b"s", b"o")
        value = self.values.popleft()
        if not isinstance(value, bytes) or len(value) > maximum:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return value

    def read_integer(self, reply: ctypes.c_void_p, kind: bytes) -> int:
        assert reply.value == 1 and kind in (b"u", b"b")
        value = self.values.popleft()
        if not isinstance(value, int):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return value

    def require_end(self, reply: ctypes.c_void_p) -> None:
        assert reply.value == 1
        if self.values:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def test_supported_response_reads_live_closed_state_without_session_labels() -> None:
    bus = _ProtocolBus()
    state = read_gnome_lock_state(bus, _OWNER)
    assert state == GnomeLockState(_EPOCH, 1, False, False, "user")
    assert not state.safely_locked and state.eligibility is LoginEligibility.ELIGIBLE
    assert [call[3] for call in bus.calls] == [b"GetState"]


@pytest.mark.parametrize(
    "state",
    [
        (2, str(_EPOCH).encode(), 1, 0, 0, 0, b"user"),
        (True, str(_EPOCH).encode(), 1, 0, 0, 0, b"user"),
        (1, b"00000000-0000-0000-0000-000000000000", 1, 0, 0, 0, b"user"),
        (1, str(_EPOCH).upper().encode(), 1, 0, 0, 0, b"user"),
        (1, str(_EPOCH).encode(), 0, 0, 0, 0, b"user"),
        (1, str(_EPOCH).encode(), 1, -1, 0, 0, b"user"),
        (1, str(_EPOCH).encode(), 1, 0, 2, 0, b"user"),
        (1, str(_EPOCH).encode(), 1, 0, 0, 2, b"user"),
        (1, str(_EPOCH).encode(), 1, 0, 0, 0, b"gdm"),
        (*_STATE, b"unreviewed"),
    ],
)
def test_unsupported_or_malformed_response_never_releases_unlock(state: tuple[int | bytes, ...]) -> None:
    with pytest.raises((RuntimeRefusalError, ValueError)):
        read_gnome_lock_state(_ProtocolBus(state), _OWNER)


@pytest.mark.parametrize(
    ("locked", "active", "mode", "expected"),
    [
        (False, False, "user", LoginEligibility.ELIGIBLE),
        (True, True, "unlock-dialog", LoginEligibility.ELIGIBLE),
        (True, False, "user", LoginEligibility.UNKNOWN),
        (False, True, "user", LoginEligibility.UNKNOWN),
        (False, False, "unlock-dialog", LoginEligibility.UNKNOWN),
        (True, True, "user", LoginEligibility.UNKNOWN),
    ],
)
def test_lock_animation_and_session_transitions_cannot_claim_unlocked(
    locked: bool, active: bool, mode: str, expected: LoginEligibility
) -> None:
    state = GnomeLockState(_EPOCH, 1, locked, active, mode)
    assert state.eligibility is expected
    assert state.safely_locked is not (expected is LoginEligibility.ELIGIBLE and not locked and not active)


@pytest.mark.skipif(sys.platform != "linux", reason="Real Linux PIDFD lifetime primitive")
@pytest.mark.parametrize("failure", [None, "session", "uid", "owner", "restart", "unassociated"])
def test_native_pidfd_session_and_same_owner_bracket_the_response(
    monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    bus = _ProtocolBus()
    bus.uid = os.getuid()
    bus.pid = os.getpid()
    bus.change_owner_after_state = failure == "owner"
    expected = GnomeLockBinding(b"a" * 32, _OWNER, bus.pid, _EPOCH)
    if failure == "restart":
        expected = replace(expected, epoch=_BOOT)
    peer_calls: list[int] = []

    @contextmanager
    def owned_process(_pid: int, _uid: int) -> Generator[int]:
        descriptor = open_linux_pidfd(os.getpid())
        try:
            yield descriptor
        finally:
            os.close(descriptor)

    def peer_session(descriptor: int) -> tuple[str, int]:
        peer_calls.append(descriptor)
        if failure == "unassociated":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return ("other" if failure == "session" else "c42", bus.uid + (failure == "uid"))

    monkeypatch.setattr(linux_gnome_lock, "_shell_pidfd", owned_process)
    if failure is not None:
        with pytest.raises(RuntimeRefusalError) as caught:
            sample_gnome_lock(bus, uid=bus.uid, session_id="c42", peer_session=peer_session, expected=expected)
        assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    else:
        binding, state = sample_gnome_lock(
            bus, uid=bus.uid, session_id="c42", peer_session=peer_session, expected=expected
        )
        assert binding == expected and not state.safely_locked
        assert len(peer_calls) == 2 and peer_calls[0] == peer_calls[1]
    assert all(call[3] not in (b"Lock", b"Unlock", b"Prompt", b"Eval") for call in bus.calls)
    if failure in ("session", "uid", "unassociated"):
        assert not any(call[3] == b"GetState" for call in bus.calls)


@pytest.mark.parametrize("failure", [False, True])
def test_bound_login_release_requires_current_observer_and_preserves_custody_independence(
    monkeypatch: pytest.MonkeyPatch, failure: bool
) -> None:
    observation = LinuxSessionObservation("c42", 1000, 500_000, "user", "wayland", "online", True)
    observer = GnomeLockBinding(b"a" * 32, _OWNER, 42, _EPOCH)
    binding = LinuxLoginBinding("1000", _BOOT, "c42", 500_000, observer)

    class NativeLogin:
        def session(self, session_id: str) -> LinuxSessionObservation:
            assert session_id == "c42"
            return observation

    def current_observer(
        _native: object, session_id: str, uid: int, expected: GnomeLockBinding | None = None
    ) -> tuple[GnomeLockBinding, GnomeLockState]:
        assert (session_id, uid, expected) == ("c42", 1000, observer)
        if failure:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return observer, GnomeLockState(_EPOCH, 1, False, False, "user")

    monkeypatch.setattr(linux_logind_native, "_NativeLogin", NativeLogin)
    monkeypatch.setattr(linux_logind_native, "_boot_id", lambda: _BOOT)
    monkeypatch.setattr(linux_login, "_gnome_observation", current_observer)
    result = binding.observe(credential_facilities=Availability.UNAVAILABLE)
    assert result.active and result.locked is failure
    assert result.unattended is (LoginEligibility.UNKNOWN if failure else LoginEligibility.ELIGIBLE)
    assert result.credential_facilities is Availability.UNAVAILABLE


def test_missing_observer_never_reselects_an_enabled_later_producer(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = LinuxLoginBinding("1000", _BOOT, "c42", 500_000)
    observation = LinuxSessionObservation("c42", 1000, 500_000, "user", "wayland", "online", False)

    class NativeLogin:
        def session(self, _session_id: str) -> LinuxSessionObservation:
            return observation

    def unexpectedly_called(*_args: object) -> None:
        raise AssertionError("A missing capture must remain UNKNOWN")

    monkeypatch.setattr(linux_logind_native, "_NativeLogin", NativeLogin)
    monkeypatch.setattr(linux_logind_native, "_boot_id", lambda: _BOOT)
    monkeypatch.setattr(linux_login, "_gnome_observation", unexpectedly_called)
    result = binding.observe(credential_facilities=Availability.AVAILABLE)
    assert result.active and result.locked and result.unattended is LoginEligibility.UNKNOWN


def test_a_complete_lock_unlock_between_polls_cannot_reactivate_attended_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer = GnomeLockBinding(b"a" * 32, _OWNER, 42, _EPOCH, 2)
    binding = LinuxLoginBinding("1000", _BOOT, "c42", 500_000, observer)
    observation = LinuxSessionObservation("c42", 1000, 500_000, "user", "wayland", "online", False)

    class NativeLogin:
        def session(self, _session_id: str) -> LinuxSessionObservation:
            return observation

    def current_observer(
        _native: object, _session_id: str, _uid: int, expected: GnomeLockBinding | None = None
    ) -> tuple[GnomeLockBinding, GnomeLockState]:
        assert expected == observer
        return observer, GnomeLockState(_EPOCH, 10, False, False, "user", 3)

    monkeypatch.setattr(linux_logind_native, "_NativeLogin", NativeLogin)
    monkeypatch.setattr(linux_logind_native, "_boot_id", lambda: _BOOT)
    monkeypatch.setattr(linux_login, "_gnome_observation", current_observer)
    result = binding.observe(credential_facilities=Availability.UNAVAILABLE)
    assert result.active and result.locked
    # Existing unattended policy still separately requires native custody.
    assert result.unattended is LoginEligibility.ELIGIBLE
    assert result.credential_facilities is Availability.UNAVAILABLE


@pytest.mark.skipif(sys.platform != "linux", reason="Native passwd and no-follow filesystem primitives")
def test_insecure_storage_ancestor_refuses_before_any_bus_call(tmp_path: Path) -> None:
    writable_ancestor = tmp_path / "writable-ancestor"
    writable_ancestor.mkdir()
    os.chmod(writable_ancestor, 0o777)  # noqa: S103 - deliberately unsafe refusal fixture
    root = writable_ancestor / "storage"
    assert writable_ancestor in root.parents and writable_ancestor.stat().st_mode & 0o022
    with override_settings(cadrumo_local_storage_root=root), pytest.raises(RuntimeRefusalError) as refused:
        linux_gnome_lock.require_gnome_login_producer(os.getuid())
    assert refused.value.reason is RuntimeRefusalCode.UNAVAILABLE
