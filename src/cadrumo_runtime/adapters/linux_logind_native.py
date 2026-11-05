"""Native PIDFD-bound Linux login identity."""

from __future__ import annotations

import ctypes
import os
import select
import sys
from uuid import UUID

from . import linux_login_models, linux_logind_bus
from .linux_login_models import SESSION_ID, unavailable


def boot_id() -> UUID:
    with open("/proc/sys/kernel/random/boot_id", "rb") as source:
        value = source.read(38)
    if len(value) != 37 or value[-1:] != b"\n":
        raise unavailable()
    identity = UUID(value[:-1].decode("ascii"))
    if identity.int == 0 or str(identity).encode("ascii") != value[:-1]:
        raise unavailable()
    return identity


def ensure_pidfd_alive(pidfd: int) -> None:
    if sys.platform == "linux":
        if type(pidfd) is not int or pidfd < 0 or os.get_inheritable(pidfd):
            raise unavailable()
        poller = select.poll()
        poller.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        if poller.poll(0):
            raise unavailable()
        return
    raise unavailable()


class NativeLogin:
    """Fixed native APIs; PID/peer sd-login functions are never used for authority."""

    library: ctypes.CDLL
    libc: ctypes.CDLL

    def __init__(self) -> None:
        if sys.platform != "linux":
            raise unavailable()
        self.library = ctypes.CDLL("libsystemd.so.0")
        self.libc = ctypes.CDLL("libc.so.6")
        self.libc.free.argtypes = (ctypes.c_void_p,)
        self.libc.free.restype = None
        pointer = ctypes.c_void_p
        output = ctypes.POINTER(pointer)
        signatures = {
            "sd_pidfd_get_session": ((ctypes.c_int, output), ctypes.c_int),
            "sd_pidfd_get_owner_uid": ((ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int),
            "sd_bus_new": ((output,), ctypes.c_int),
            "sd_bus_set_fd": ((pointer, ctypes.c_int, ctypes.c_int), ctypes.c_int),
            "sd_bus_set_bus_client": ((pointer, ctypes.c_int), ctypes.c_int),
            "sd_bus_set_method_call_timeout": ((pointer, ctypes.c_uint64), ctypes.c_int),
            "sd_bus_start": ((pointer,), ctypes.c_int),
            "sd_bus_is_ready": ((pointer,), ctypes.c_int),
            "sd_bus_process": ((pointer, output), ctypes.c_int),
            "sd_bus_wait": ((pointer, ctypes.c_uint64), ctypes.c_int),
            "sd_bus_close_unref": ((pointer,), pointer),
            "sd_bus_message_new_method_call": (
                (pointer, output, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p),
                ctypes.c_int,
            ),
            "sd_bus_message_set_auto_start": ((pointer, ctypes.c_int), ctypes.c_int),
            "sd_bus_message_set_allow_interactive_authorization": ((pointer, ctypes.c_int), ctypes.c_int),
            "sd_bus_message_append_basic": ((pointer, ctypes.c_char, pointer), ctypes.c_int),
            "sd_bus_call": ((pointer, pointer, ctypes.c_uint64, pointer, output), ctypes.c_int),
            "sd_bus_message_unref": ((pointer,), pointer),
            "sd_bus_message_get_sender": ((pointer,), ctypes.c_char_p),
            "sd_bus_message_read_basic": ((pointer, ctypes.c_char, pointer), ctypes.c_int),
            "sd_bus_message_enter_container": ((pointer, ctypes.c_char, ctypes.c_char_p), ctypes.c_int),
            "sd_bus_message_exit_container": ((pointer,), ctypes.c_int),
            "sd_bus_message_at_end": ((pointer, ctypes.c_int), ctypes.c_int),
            "sd_bus_message_skip": ((pointer, ctypes.c_char_p), ctypes.c_int),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.library, name)
            function.argtypes = arguments
            function.restype = result

    def peer_session(self, pidfd: int) -> tuple[str, int]:
        session = ctypes.c_void_p()
        uid = ctypes.c_uint32()
        try:
            linux_logind_bus.check(self.library.sd_pidfd_get_session(pidfd, ctypes.byref(session)))
            if not (session.value is not None and session.value):
                raise unavailable()
            raw = ctypes.cast(session, ctypes.c_char_p).value
            if raw is None or len(raw) > 64:
                raise unavailable()
            identity = raw.decode("ascii")
            if not SESSION_ID.fullmatch(identity):
                raise unavailable()
            linux_logind_bus.check(self.library.sd_pidfd_get_owner_uid(pidfd, ctypes.byref(uid)))
            if uid.value == 0xFFFFFFFF:
                raise unavailable()
            return identity, uid.value
        finally:
            if session.value is not None and session.value:
                self.libc.free(session)

    def session(self, session_id: str) -> linux_login_models.LinuxSessionObservation:
        if not SESSION_ID.fullmatch(session_id):
            raise unavailable()
        with linux_logind_bus.SessionBus(self.library) as bus:
            owner = bus.login_owner()
            with bus.call(
                linux_logind_bus.BUS_DESTINATION,
                linux_logind_bus.BUS_PATH,
                linux_logind_bus.BUS_DESTINATION,
                b"GetConnectionUnixUser",
                owner,
            ) as reply:
                if bus.read_integer(reply, b"u") != 0:
                    raise unavailable()
                bus.require_end(reply)
            observation = bus.session_record(owner, session_id).desktop()
            if bus.login_owner() != owner or observation.session_id != session_id:
                raise unavailable()
            bus.remaining_usec()
            return observation
