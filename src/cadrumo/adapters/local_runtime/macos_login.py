"""Kernel peer audit sessions, without guessing macOS lock eligibility."""

from __future__ import annotations

import ctypes
import errno
import socket
import struct
import sys
from dataclasses import dataclass

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from .macos_process import read_macos_process


@dataclass(frozen=True, slots=True)
class MacosPeerAuditToken:
    """Closed kernel-supplied identity from LOCAL_PEERTOKEN, never client JSON."""

    audit_user_id: int
    effective_user_id: int
    effective_group_id: int
    real_user_id: int
    real_group_id: int
    process_id: int
    audit_session_id: int
    process_version: int


def decode_macos_peer_audit_token(payload: bytes, *, expected_owner: str) -> MacosPeerAuditToken:
    """Validate a native audit-token buffer before using any session coordinates.

    Args:
        payload: Exact eight-word native LOCAL_PEERTOKEN record.
        expected_owner: Independently verified native peer UID.
    """
    if len(payload) != 32:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    value = MacosPeerAuditToken(*struct.unpack("=8I", payload))
    if (
        not expected_owner.isdecimal()
        or str(value.effective_user_id) != expected_owner
        or value.real_user_id != value.effective_user_id
        or value.audit_user_id != value.effective_user_id
        or not 0 < value.process_id <= 2_147_483_647
        or not 0 < value.audit_session_id < 0xFFFFFFFE
        or value.process_version <= 0
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    return value


def macos_peer_audit_token(sock: socket.socket, *, expected_owner: str) -> MacosPeerAuditToken:
    """Read and corroborate a retained local socket's kernel audit token.

    Args:
        sock: Connected socket pinned against close by its transport owner.
        expected_owner: Independently verified native peer UID.
    """
    if sys.platform != "darwin" or sock.fileno() < 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    try:
        # Darwin sys/un.h: SOL_LOCAL=0, LOCAL_PEERPID=2, LOCAL_PEERTOKEN=6.
        payload = sock.getsockopt(0, 6, 32)
        token = decode_macos_peer_audit_token(payload, expected_owner=expected_owner)
        pid = struct.unpack("=i", sock.getsockopt(0, 2, 4))[0]
        if pid != token.process_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        before = read_macos_process(pid, expected_owner=expected_owner)
        if sock.getsockopt(0, 6, 32) != payload:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if read_macos_process(pid, expected_owner=expected_owner) != before:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        _require_current_process_version(payload)
        return token
    except (OSError, struct.error):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED) from None


def _require_current_process_version(payload: bytes) -> None:
    # The public libproc API compares the token's pidversion inside the kernel.
    # BSD birth timestamps alone remain unchanged when the peer executes a new
    # program. Its path is only a bounded output buffer and is never disclosed.
    value = (ctypes.c_uint32 * 8).from_buffer_copy(payload)
    buffer = (ctypes.c_ubyte * 4096)()
    try:
        native = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        query = native.proc_pidpath_audittoken
        query.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32)
        query.restype = ctypes.c_int
        ctypes.set_errno(0)
        count = query(ctypes.byref(value), ctypes.byref(buffer), ctypes.sizeof(buffer))
        if count == 0 and ctypes.get_errno() in (errno.EACCES, errno.EPERM):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if type(count) is not int or not 0 < count < ctypes.sizeof(buffer) or buffer[count] != 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    except (AttributeError, OSError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    finally:
        ctypes.memset(ctypes.byref(buffer), 0, ctypes.sizeof(buffer))


@dataclass(frozen=True, slots=True)
class MacosSessionObservation:
    """Security framework session facts; graphic access is not unlocked proof."""

    session_id: int
    attributes: int


def observe_macos_session(session_id: int) -> MacosSessionObservation | None:
    """Query exactly one security session, preserving absence versus unavailability.

    Args:
        session_id: Native audit-session ID captured from the connected peer.
    """
    if sys.platform != "darwin" or type(session_id) is not int or not 0 < session_id < 0xFFFFFFFE:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    try:
        security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
        query = security.SessionGetInfo
        query.argtypes = (ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32))
        query.restype = ctypes.c_int32
        observed, attributes = ctypes.c_uint32(), ctypes.c_uint32()
        status = query(session_id, ctypes.byref(observed), ctypes.byref(attributes))
        if status == -60500:
            return None
        if status != 0 or observed.value != session_id or attributes.value & ~0x1031:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return MacosSessionObservation(observed.value, attributes.value)
    except (AttributeError, OSError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None


@dataclass(frozen=True, slots=True)
class MacosLoginBinding:
    """Native audit-session provenance with conservative fresh eligibility."""

    os_owner_id: str
    audit_session_id: int

    @property
    def login_id(self) -> str:
        """Bind the native owner and Security framework's unique session identity."""
        return f"macos:{self.os_owner_id}:{self.audit_session_id}"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Refuse dependent access until trusted lock/logout evidence is available.

        Args:
            credential_facilities: Independent native custody readiness facts.
        """
        try:
            session = observe_macos_session(self.audit_session_id)
        except RuntimeRefusalError:
            session = None
            eligibility = LoginEligibility.UNKNOWN
        else:
            eligibility = LoginEligibility.INELIGIBLE if session is None else LoginEligibility.UNKNOWN
        active = session is not None and bool(session.attributes & 0x10) and not bool(session.attributes & 0x1001)
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.os_owner_id,
            active=active,
            locked=True,
            unattended=eligibility,
            credential_facilities=credential_facilities,
        )


def capture_macos_login(sock: socket.socket, *, expected_owner: str) -> MacosLoginBinding:
    """Capture exact native socket/session provenance before any secret handoff.

    Args:
        sock: Connected socket pinned by its transport owner.
        expected_owner: Independently verified native peer UID.
    """
    token = macos_peer_audit_token(sock, expected_owner=expected_owner)
    observation = observe_macos_session(token.audit_session_id)
    if observation is None or observation.attributes & 0x1001 or not observation.attributes & 0x10:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    if macos_peer_audit_token(sock, expected_owner=expected_owner) != token:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    return MacosLoginBinding(expected_owner, token.audit_session_id)


__all__ = [
    "MacosLoginBinding",
    "MacosPeerAuditToken",
    "MacosSessionObservation",
    "capture_macos_login",
    "decode_macos_peer_audit_token",
    "macos_peer_audit_token",
    "observe_macos_session",
]
