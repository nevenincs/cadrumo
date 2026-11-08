"""The closed failure categories an operation reports across the wire, each with one plain sentence and one action."""

from __future__ import annotations

from enum import StrEnum


class DependencyFailureCategory(StrEnum):
    """The closed failure categories; each maps to one plain sentence and at most one action."""

    OFFLINE = "offline"
    HOST_UNREACHABLE = "host_unreachable"
    SECURE_CONNECTION_FAILED = "secure_connection_failed"
    BLOCKED_BY_NETWORK = "blocked_by_network"
    DISK_FULL = "disk_full"
    NO_PERMISSION = "no_permission"
    DAMAGED_DOWNLOAD = "damaged_download"
    NOT_ENOUGH_MEMORY = "not_enough_memory"
    MEMORY_BUSY = "memory_busy"
    PROGRAM_MISSING = "program_missing"
    PROGRAM_NOT_RUNNING = "program_not_running"
    INTERRUPTED = "interrupted"
    NEEDS_SIGN_IN = "needs_sign_in"
    NOT_IN_THIS_BUILD = "not_in_this_build"
    CANCELLED = "cancelled"
    UNEXPECTED = "unexpected"
