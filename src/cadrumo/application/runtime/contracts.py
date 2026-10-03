"""Credential-free local runtime identity, readiness and refusal contracts."""

from __future__ import annotations

from enum import StrEnum
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


class RuntimeClientHello(BaseModel):
    """Nonsecret expected installation cohort and canonical storage identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["client_hello"] = "client_hello"
    protocol_version: Annotated[int, Field(strict=True, ge=2, le=2)] = 2
    product_version: Annotated[str, Field(min_length=1, max_length=64)]
    storage_identity: ContentDigest


class RuntimeServerHello(BaseModel):
    """Readiness of an OS-authenticated runtime; the boot ID is not a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["server_hello"] = "server_hello"
    protocol_version: Annotated[int, Field(strict=True, ge=2, le=2)] = 2
    product_version: Annotated[str, Field(min_length=1, max_length=64)]
    storage_identity: ContentDigest
    boot_id: UUID


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
