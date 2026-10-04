"""PIDFD-bound login capture and fresh lifetime observations."""

from __future__ import annotations

import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.login import RuntimeLoginInventory
from ...application.user_profile.access_contracts import Availability, LoginEligibility, OsLockState, OsLoginContext
from . import linux_login_models as _models
from . import linux_logind_bus as _bus
from . import linux_logind_native as _native
from .linux_gnome_lock import (
    GnomeLockBinding,
    GnomeLockState,
    gnome_user_bus_path,
    require_gnome_login_producer,
    sample_gnome_lock,
)
from .posix import posix_owner_uid


@dataclass(frozen=True)
class LinuxLoginBinding:
    """Immutable native login incarnation; no originating process is retained."""

    os_owner_id: str
    boot_id: UUID
    session_id: str
    created_monotonic_usec: int
    gnome_lock: GnomeLockBinding | None = None

    @property
    def login_id(self) -> str:
        """Identify one boot, native session generation, and Unix owner."""
        return f"linux:{self.boot_id}:{self.session_id}:{self.created_monotonic_usec}:{self.os_owner_id}"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Read this same login again, independently of the peer process lifetime."""
        return observe_linux_login(self, credential_facilities=credential_facilities)


def capture_linux_login(pidfd: int, *, expected_owner: str) -> LinuxLoginBinding:
    """Borrow a kernel-bound peer PIDFD and fence its session around the snapshot."""
    if sys.platform != "linux":
        raise _models._unavailable()
    try:
        _native._ensure_pidfd_alive(pidfd)
        native = _native._NativeLogin()
        boot = _native._boot_id()
        session_id, uid, observation = _capture_login_snapshot(native, pidfd, expected_owner, boot)
        _native._ensure_pidfd_alive(pidfd)
        lock_binding = _capture_optional_gnome_lock(native, session_id, uid)
        if lock_binding is not None:
            _require_same_login_snapshot(native, session_id, observation, boot)
        _native._ensure_pidfd_alive(pidfd)
        return LinuxLoginBinding(expected_owner, boot, session_id, observation.created_monotonic_usec, lock_binding)
    except (OSError, AttributeError, ValueError, TypeError, OverflowError):
        raise _models._unavailable() from None


def _capture_login_snapshot(
    native: _native._NativeLogin, pidfd: int, expected_owner: str, boot: UUID
) -> tuple[str, int, _models.LinuxSessionObservation]:
    session_id, uid = native.peer_session(pidfd)
    if str(uid) != expected_owner:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    observation = native.session(session_id)
    if observation.uid != uid or observation.state not in ("online", "active"):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    if native.peer_session(pidfd) != (session_id, uid) or _native._boot_id() != boot:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    return session_id, uid, observation


def _capture_optional_gnome_lock(native: _native._NativeLogin, session_id: str, uid: int) -> GnomeLockBinding | None:
    lock_binding: GnomeLockBinding | None = None
    with suppress(RuntimeRefusalError, OSError, AttributeError, ValueError, TypeError, OverflowError):
        lock_binding, _ = _gnome_observation(native, session_id, uid)
    return lock_binding


def _require_same_login_snapshot(
    native: _native._NativeLogin,
    session_id: str,
    observation: _models.LinuxSessionObservation,
    boot: UUID,
) -> None:
    if native.session(session_id) != observation or _native._boot_id() != boot:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)


def _gnome_observation(
    native: _native._NativeLogin,
    session_id: str,
    uid: int,
    expected: GnomeLockBinding | None = None,
    *,
    deadline: float | None = None,
) -> tuple[GnomeLockBinding, GnomeLockState]:
    deadline = deadline if deadline is not None else time.monotonic() + _bus._BUS_TIMEOUT_SECONDS
    require_gnome_login_producer(uid)
    path = gnome_user_bus_path(uid)
    socket_identity = path.lstat()
    with _bus._SessionBus(native.library, path=path, peer_uid=uid, deadline=deadline) as bus:
        result = sample_gnome_lock(
            bus, uid=uid, session_id=session_id, peer_session=native.peer_session, expected=expected
        )
        require_gnome_login_producer(uid)
        if gnome_user_bus_path(uid) != path or path.lstat() != socket_identity:
            raise _models._unavailable()
        bus.remaining_usec()
        return result


def observe_linux_login(binding: LinuxLoginBinding, *, credential_facilities: Availability) -> OsLoginContext:
    """Observe exact lifetime without promoting logind's lock hint to authority.

    Only the retained, same-owner GNOME observer can establish lock eligibility.
    Credential readiness remains independent of compositor integration.
    """
    try:
        native, observation, valid = _current_login_snapshot(binding)
        valid, lock_state, eligibility = _current_lock_observation(binding, native, observation, valid)
        return OsLoginContext(
            login_id=binding.login_id,
            os_owner_id=binding.os_owner_id,
            active=valid,
            lock_state=lock_state,
            unattended=eligibility,
            credential_facilities=credential_facilities,
        )
    except (RuntimeRefusalError, OSError, AttributeError, ValueError, TypeError, OverflowError):
        return OsLoginContext(
            login_id=binding.login_id,
            os_owner_id=binding.os_owner_id,
            active=False,
            lock_state=OsLockState.UNKNOWN,
            unattended=LoginEligibility.UNKNOWN,
            credential_facilities=credential_facilities,
        )


def _current_login_snapshot(
    binding: LinuxLoginBinding,
) -> tuple[_native._NativeLogin | None, _models.LinuxSessionObservation | None, bool]:
    boot_matches = _native._boot_id() == binding.boot_id
    native = _native._NativeLogin() if boot_matches else None
    observation = native.session(binding.session_id) if native is not None else None
    valid = (
        observation is not None
        and observation.session_id == binding.session_id
        and str(observation.uid) == binding.os_owner_id
        and observation.created_monotonic_usec == binding.created_monotonic_usec
        and observation.state in ("online", "active")
        and _native._boot_id() == binding.boot_id
    )
    return native, observation, valid


def _current_lock_observation(
    binding: LinuxLoginBinding,
    native: _native._NativeLogin | None,
    observation: _models.LinuxSessionObservation | None,
    valid: bool,
) -> tuple[bool, OsLockState, LoginEligibility]:
    lock_state = OsLockState.UNKNOWN
    eligibility = LoginEligibility.UNKNOWN if valid else LoginEligibility.INELIGIBLE
    if not valid or native is None or binding.gnome_lock is None:
        return valid, lock_state, eligibility
    try:
        _, gnome = _gnome_observation(native, binding.session_id, int(binding.os_owner_id), binding.gnome_lock)
        # Lock observations cannot outlive a changed native login snapshot.
        if native.session(binding.session_id) != observation or _native._boot_id() != binding.boot_id:
            return False, lock_state, LoginEligibility.INELIGIBLE
        lock_state = _gnome_lock_state(gnome, binding.gnome_lock)
        eligibility = gnome.eligibility
    except (RuntimeRefusalError, OSError, AttributeError, ValueError, TypeError, OverflowError):
        pass
    return valid, lock_state, eligibility


def _gnome_lock_state(state: GnomeLockState, captured: GnomeLockBinding) -> OsLockState:
    """Only complete producer states or an advanced lock generation are positive evidence."""
    if state.lock_generation > captured.lock_generation:
        return OsLockState.LOCKED
    if not state.safely_locked:
        return OsLockState.UNLOCKED
    if state.eligibility is LoginEligibility.ELIGIBLE:
        return OsLockState.LOCKED
    return OsLockState.UNKNOWN


def linux_login_inventory(*, expected_owner: str) -> RuntimeLoginInventory:
    """Enumerate trusted owner desktops; incomplete absence never proves logout.

    One existing aggregate bus deadline covers enumeration and GNOME sampling.
    Local filesystem/native operations remain subject to their existing limits.
    The fixed per-user bus currently exposes only one GNOME Shell owner: other
    desktop rows remain uncertain unless that exact row's producer is verified.
    """
    unknown = RuntimeLoginInventory((), False)
    if sys.platform != "linux":
        return unknown
    try:
        uid = posix_owner_uid()
        if expected_owner != str(uid):
            return unknown
        deadline = time.monotonic() + _bus._BUS_TIMEOUT_SECONDS
        boot = _native._boot_id()
        native = _native._NativeLogin()
        with _bus._SessionBus(native.library, deadline=deadline) as bus:
            owner = _trusted_logind_bus_owner(bus)
            if owner is None:
                return unknown
            before = bus.sessions(owner)
            logins, complete = _observe_inventory_sessions(
                bus, native, owner, before, uid, expected_owner, boot, deadline
            )
            if not _inventory_snapshot_is_stable(bus, owner, before, boot):
                return unknown
            bus.remaining_usec()
            return RuntimeLoginInventory(tuple(logins), complete)
    except (RuntimeRefusalError, OSError, AttributeError, ValueError, TypeError, OverflowError):
        return unknown


def _trusted_logind_bus_owner(bus: _bus._SessionBus) -> bytes | None:
    owner = bus.login_owner()
    with bus.call(
        _bus._BUS_DESTINATION, _bus._BUS_PATH, _bus._BUS_DESTINATION, b"GetConnectionUnixUser", owner
    ) as reply:
        if bus.read_integer(reply, b"u") != 0:
            return None
        bus.require_end(reply)
    return owner


def _observe_inventory_sessions(
    bus: _bus._SessionBus,
    native: _native._NativeLogin,
    owner: bytes,
    rows: tuple[_models._SessionReference, ...],
    uid: int,
    expected_owner: str,
    boot: UUID,
    deadline: float,
) -> tuple[list[LinuxLoginBinding], bool]:
    logins: list[LinuxLoginBinding] = []
    complete = True
    for row in rows:
        bus.remaining_usec()
        if row.uid != uid:
            continue
        try:
            login, row_complete = _observe_inventory_row(bus, native, owner, row, uid, expected_owner, boot, deadline)
            complete = complete and row_complete
            if login is not None:
                logins.append(login)
        except (RuntimeRefusalError, OSError, AttributeError, ValueError, TypeError, OverflowError):
            complete = False
    return logins, complete


def _inventory_snapshot_is_stable(
    bus: _bus._SessionBus, owner: bytes, before: tuple[_models._SessionReference, ...], boot: UUID
) -> bool:
    return bus.sessions(owner) == before and bus.login_owner() == owner and _native._boot_id() == boot


def _observe_inventory_row(
    bus: _bus._SessionBus,
    native: _native._NativeLogin,
    owner: bytes,
    row: _models._SessionReference,
    uid: int,
    expected_owner: str,
    boot: UUID,
    deadline: float,
) -> tuple[LinuxLoginBinding | None, bool]:
    first = bus.session_record(owner, row.session_id, expected_path=row.object_path)
    if first.uid != uid:
        raise _models._unavailable()
    if first.known_ineligible:
        stable = bus.session_record(owner, row.session_id, expected_path=row.object_path) == first
        return None, stable
    observation = first.desktop()
    if observation.state not in ("online", "active"):
        raise _models._unavailable()
    lock_binding, state = _gnome_observation(native, row.session_id, uid, deadline=deadline)
    if state.eligibility is not LoginEligibility.ELIGIBLE:
        raise _models._unavailable()
    if bus.session_record(owner, row.session_id, expected_path=row.object_path) != first:
        raise _models._unavailable()
    bus.remaining_usec()
    return LinuxLoginBinding(expected_owner, boot, row.session_id, first.created_monotonic_usec, lock_binding), True
