"""Installed service admission and native process-group evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

from .access_vocabulary import AccessScope
from .contracts import ByteChannel
from .extension_records import ExtensionRecordCapability
from .model_runs import MODEL_RUN_CAPABILITY
from .transport import ConnectionContext


class ServiceCapability(StrEnum):
    """Runtime-routed work an installed service descriptor may admit its service for."""

    MODEL_RUN = MODEL_RUN_CAPABILITY
    """The runtime may route a profile worker's model runs to the service."""


class InstalledParentImage(BaseModel):
    """Installed native parent image permitted to start a human frontend holder."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    launch_image: Annotated[str, Field(min_length=1, max_length=32767)]
    image_digest: ContentDigest


class InstalledServiceDescriptor(BaseModel):
    """Immutable installed launch identity and authority ceilings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    service_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")]
    launch_image: Annotated[str, Field(min_length=1, max_length=32767)]
    launch_module: Annotated[str, Field(min_length=1, max_length=256)]
    image_digest: ContentDigest
    descriptor_digest: ContentDigest
    record_capabilities: tuple[ExtensionRecordCapability, ...]
    operation_scope: AccessScope
    allow_descendants: bool = False
    allowed_parent_images: tuple[InstalledParentImage, ...] = ()
    # The arguments the image must be started with, first after the image itself: the role
    # of an image that runs several. Empty for an image that runs one service.
    launch_arguments: tuple[Annotated[str, Field(min_length=1, max_length=256)], ...] = ()
    # Runtime-routed work this installed service is admitted for, beyond its records.
    service_capabilities: tuple[ServiceCapability, ...] = ()

    @field_validator("service_capabilities")
    @classmethod
    def _capabilities_are_distinct(cls, value: tuple[ServiceCapability, ...]) -> tuple[ServiceCapability, ...]:
        if len(set(value)) != len(value):
            raise ValueError("a service capability is declared once")
        return value

    def declares(self, capability: ServiceCapability) -> bool:
        """Whether this installed descriptor admits the service for ``capability``."""
        return capability in self.service_capabilities


@dataclass(frozen=True, slots=True)
class VerifiedServicePeer:
    """Transport-held kernel process incarnation matched to installed policy."""

    service_id: str
    descriptor_digest: str
    process_id: int
    process_incarnation: str
    image_path: str
    image_digest: str
    connection_id: UUID
    runtime_boot_id: UUID
    image_identity: str
    """The hashed image file's device, file id, size and modification time."""


class NativeServiceVerifier(Protocol):
    """Verify retained kernel peers against the installed service identity."""

    def verify_service(
        self, context: ConnectionContext, channel: ByteChannel, descriptor: InstalledServiceDescriptor
    ) -> VerifiedServicePeer | None:
        """Match a retained kernel peer to a trusted dedicated installed image."""
        ...

    def recheck_service(self, context: ConnectionContext, channel: ByteChannel, peer: VerifiedServicePeer) -> bool:
        """Prove the connection still carries the exact process incarnation and image ``peer`` admitted."""
        ...

    def installed_parent_image_matches(self, image_path: str, descriptor_path: str, image_digest: str) -> bool:
        """Verify an allowed parent image against its exact installed digest."""
        ...

    def verify_descendant(
        self, context: ConnectionContext, channel: ByteChannel, service_peer: VerifiedServicePeer, group_id: UUID
    ) -> bool:
        """Recheck kernel parent-chain ancestry and process-incarnation evidence."""
        ...


class ServiceLease(BaseModel):
    """Bind a service admission to its exact profile session and connection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    lease_id: UUID
    session_id: UUID
    profile_id: UUID
    parent_session_id: UUID
    descriptor_digest: ContentDigest
    service_id: str
    runtime_boot_id: UUID
    connection_id: UUID


class ServiceConnect(BaseModel):
    """Request service admission for one exact profile and service identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["service_connect"] = "service_connect"
    request_id: UUID
    profile_id: UUID
    service_id: Annotated[str, Field(min_length=1, max_length=64)]


class ServiceAdmission(BaseModel):
    """Present the profile session that authorizes a connected service."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["service_admission"] = "service_admission"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    recipient_connection_id: UUID
    service_id: Annotated[str, Field(min_length=1, max_length=64)]


class ServiceAdmissionStatusQuery(BaseModel):
    """Observe or cancel one exact pending service admission, never repeat it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["service_admission_status", "service_admission_cancel"]
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    recipient_connection_id: UUID
    service_id: Annotated[str, Field(min_length=1, max_length=64)]
    admission_id: UUID


class ServiceAdmissionPending(BaseModel):
    """A bounded admission handle, with no lease or authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["service_admission_pending"] = "service_admission_pending"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    service_id: str
    admission_id: UUID
    cancelled: bool = False


class ServiceConnected(BaseModel):
    """Report a service connection and its optional profile lease."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["service_connected"] = "service_connected"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    service_id: str
    lease: ServiceLease | None = None
