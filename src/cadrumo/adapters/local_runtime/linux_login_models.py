"""Typed logind session records and their native validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

_SESSION_ID = re.compile(r"[A-Za-z0-9_]{1,64}\Z", re.ASCII)

_SESSION_PATH = re.compile(rb"/org/freedesktop/login1/session/[A-Za-z0-9_]{1,192}\Z", re.ASCII)


def _unavailable() -> RuntimeRefusalError:
    return RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _valid_session_identifier(value: object) -> bool:
    return type(value) is str and _SESSION_ID.fullmatch(value) is not None


def _valid_owner_id(value: object) -> bool:
    return type(value) is int and 0 <= value < 0xFFFFFFFF


def _valid_session_generation(value: object) -> bool:
    return type(value) is int and 0 < value < 0xFFFFFFFFFFFFFFFF


def _valid_native_label(value: object) -> bool:
    return type(value) is str and 1 <= len(value) <= 64 and value.isascii()


@dataclass(frozen=True)
class LinuxSessionObservation:
    """Minimal typed native snapshot; account names and remote data are discarded."""

    session_id: str
    uid: int
    created_monotonic_usec: int
    session_class: str
    session_type: str
    state: str
    locked_hint: bool

    def __post_init__(self) -> None:
        """Reject unsupported or malformed native facts before they become evidence."""
        if not _valid_session_identifier(self.session_id):
            raise _unavailable()
        if not _valid_owner_id(self.uid):
            raise _unavailable()
        if not _valid_session_generation(self.created_monotonic_usec):
            raise _unavailable()
        if self.session_class != "user" or self.session_type not in ("x11", "wayland"):
            raise _unavailable()
        if self.state not in ("active", "online", "closing") or type(self.locked_hint) is not bool:
            raise _unavailable()


@dataclass(frozen=True)
class _SessionRecord:
    """Typed native properties before supported-desktop admission is decided."""

    session_id: str
    uid: int
    created_monotonic_usec: int
    session_class: str
    session_type: str
    state: str
    locked_hint: bool

    def __post_init__(self) -> None:
        if not _valid_session_identifier(self.session_id):
            raise _unavailable()
        if not _valid_owner_id(self.uid):
            raise _unavailable()
        if not _valid_session_generation(self.created_monotonic_usec):
            raise _unavailable()
        if not all(_valid_native_label(value) for value in (self.session_class, self.session_type, self.state)):
            raise _unavailable()
        if type(self.locked_hint) is not bool:
            raise _unavailable()

    def desktop(self) -> LinuxSessionObservation:
        """Keep the original class=user, x11/wayland admission unchanged."""
        return LinuxSessionObservation(
            self.session_id,
            self.uid,
            self.created_monotonic_usec,
            self.session_class,
            self.session_type,
            self.state,
            self.locked_hint,
        )

    @property
    def known_ineligible(self) -> bool:
        """Exclude only exact closing or positively noninteractive native facts."""
        noninteractive = ("manager", "manager-early", "background", "background-light", "greeter", "lock-screen")
        if (
            self.session_class not in ("user", *noninteractive)
            or self.session_type not in ("x11", "wayland", "tty", "mir", "unspecified")
            or self.state not in ("online", "active", "closing")
        ):
            return False
        return self.state == "closing" or (
            self.state in ("online", "active") and (self.session_class in noninteractive or self.session_type == "tty")
        )


@dataclass(frozen=True)
class _SessionReference:
    session_id: str
    uid: int
    object_path: bytes

    def __post_init__(self) -> None:
        if not _valid_session_identifier(self.session_id):
            raise _unavailable()
        if not _valid_owner_id(self.uid):
            raise _unavailable()
        if type(self.object_path) is not bytes or not _SESSION_PATH.fullmatch(self.object_path):
            raise _unavailable()
