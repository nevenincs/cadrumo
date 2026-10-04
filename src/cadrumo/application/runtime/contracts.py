"""Credential-free local runtime identity, readiness and refusal contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import CadrumoError
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class RuntimeRefusalCode(StrEnum):
    """Stable transport refusals without peer-controlled diagnostics."""

    UNAVAILABLE = "runtime_unavailable"
    ENDPOINT_NOT_READY = "runtime_endpoint_not_ready"
    OWNER_BUSY = "runtime_owner_busy"
    ENDPOINT_UNTRUSTED = "runtime_endpoint_untrusted"
    PEER_UNTRUSTED = "runtime_peer_untrusted"
    VERSION_MISMATCH = "runtime_version_mismatch"
    ROOT_MISMATCH = "runtime_root_mismatch"
    INVALID_FRAME = "runtime_invalid_frame"
    CONNECTION_CLOSED = "runtime_connection_closed"
    DEADLINE_EXCEEDED = "runtime_deadline_exceeded"
    DRAINING = "runtime_draining"
    CONTAINMENT_UNAVAILABLE = "runtime_containment_unavailable"


class RuntimeRefusalError(CadrumoError):
    """Carry only an allowlisted transport outcome across public boundaries."""

    def __init__(self, code: RuntimeRefusalCode) -> None:
        """Retain only the allowlisted code in the exception's public message."""
        self.reason = code
        super().__init__(code.value)


class RuntimeShutdownIncompleteError(RuntimeRefusalError):
    """The runtime still owns work; its native listener must remain claimed."""

    def __init__(self) -> None:
        """Expose a fixed containment refusal without carrying private diagnostics."""
        super().__init__(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


class RuntimeExitReason(IntEnum):
    """Process exit codes by which a runtime names why it ended.

    The reasons occupy 64-73. Every code in ``RESERVED_RUNTIME_EXIT_CODES``
    already belongs to another owner and never names a runtime reason. A
    runtime never exits ``0`` for its own stop. CPython can exit ``1`` or ``2``
    before runtime code runs, so a supervisor reads those as launch failures.
    The range lies inside BSD ``sysexits.h``, which neither CPython nor the
    runtime emits.

    ``SESSION_END_SETTLE`` and ``ELEVATED_TOKEN_REFUSED`` occur only in
    supervised mode. ``DRAIN_WATCHDOG`` is a forced exit after the drain did not
    settle within its bound.
    """

    SUPERVISOR_STOP = 64
    SIGNAL_STOP = 65
    SESSION_END_SETTLE = 66
    OWNER_BUSY = 67
    ROOT_MISMATCH = 68
    VERSION_MISMATCH = 69
    LOGIN_WITNESS_LOSS = 70
    DRAIN_WATCHDOG = 71
    ELEVATED_TOKEN_REFUSED = 72
    UNEXPECTED_FAILURE = 73


@dataclass(frozen=True, slots=True)
class RuntimeReservedExitCodes:
    """An inclusive range of unsigned exit codes owned outside the runtime."""

    owner: str
    first: int
    last: int

    def __contains__(self, code: int) -> bool:
        """Report whether ``code`` lies in this inclusive range."""
        return self.first <= code <= self.last


RESERVED_RUNTIME_EXIT_CODES: tuple[RuntimeReservedExitCodes, ...] = (
    # Uncaught Python exceptions, CPython configuration errors and forced job termination.
    RuntimeReservedExitCodes("python_failure", 1, 1),
    # argparse and CPython command-line usage errors.
    RuntimeReservedExitCodes("usage", 2, 2),
    # The Windows C runtime's abort().
    RuntimeReservedExitCodes("c_runtime_abort", 3, 3),
    # CPython's finalization failure (120) and the native interpreter host's startup refusals.
    RuntimeReservedExitCodes("native_host", 120, 124),
    # POSIX signal exits reported as 128 + N, and negative codes wrapped to a byte.
    RuntimeReservedExitCodes("posix_signal", 128, 255),
    # NTSTATUS warning and error codes, including STATUS_CONTROL_C_EXIT (0xC000013A).
    RuntimeReservedExitCodes("ntstatus", 0x8000_0000, 0xFFFF_FFFF),
)

_REFUSAL_EXIT_REASONS: Mapping[RuntimeRefusalCode, RuntimeExitReason] = MappingProxyType(
    {
        RuntimeRefusalCode.OWNER_BUSY: RuntimeExitReason.OWNER_BUSY,
        RuntimeRefusalCode.ROOT_MISMATCH: RuntimeExitReason.ROOT_MISMATCH,
        RuntimeRefusalCode.VERSION_MISMATCH: RuntimeExitReason.VERSION_MISMATCH,
    }
)


def runtime_refusal_exit_reason(code: RuntimeRefusalCode) -> RuntimeExitReason:
    """Name the exit reason for a refusal that ended the runtime.

    Only configuration refusals have their own reason. Any other refusal that
    escapes the runtime is an unexpected failure.
    """
    return _REFUSAL_EXIT_REASONS.get(code, RuntimeExitReason.UNEXPECTED_FAILURE)


# The published registry authority's logical generation. An editable install
# keeps its product version while source and authority move, so a runtime and
# its frontends also compare this whenever both name one; channels that carry
# no authority cohort (worker control) leave it unset.
type RuntimeAuthorityGeneration = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class RuntimeClientHello(BaseModel):
    """Nonsecret expected installation cohort and canonical storage identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["client_hello"] = "client_hello"
    protocol_version: Annotated[int, Field(strict=True, ge=2, le=2)] = 2
    product_version: Annotated[str, Field(min_length=1, max_length=64)]
    storage_identity: ContentDigest
    authority_generation: RuntimeAuthorityGeneration | None = None


class RuntimeServerHello(BaseModel):
    """Readiness of an OS-authenticated runtime; the boot ID is not a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["server_hello"] = "server_hello"
    protocol_version: Annotated[int, Field(strict=True, ge=2, le=2)] = 2
    product_version: Annotated[str, Field(min_length=1, max_length=64)]
    storage_identity: ContentDigest
    boot_id: UUID
    authority_generation: RuntimeAuthorityGeneration | None = None


class RuntimePeer(BaseModel):
    """Native peer evidence, produced by the transport rather than wire input."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    os_owner_id: Annotated[str, Field(min_length=1, max_length=256)]
    process_id: Annotated[int, Field(gt=0)] | None


class RuntimeByteChannel(Protocol):
    """An already peer-verified stream with absolute monotonic I/O deadlines."""

    @property
    def peer(self) -> RuntimePeer:
        """Return kernel-derived identity held for this connection."""
        ...

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        """Read a bounded byte count or refuse without exposing partial data."""
        ...

    def read_ready(self) -> bool:
        """Observe available input or EOF without consuming bytes or blocking an idle peer."""
        ...

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        """Send only to this verified peer before the absolute deadline."""
        ...

    def close(self) -> None:
        """Release connection resources, never the shared runtime owner."""
        ...
