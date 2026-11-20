"""Registered profile reads over an installed service's own runtime connection."""

from __future__ import annotations

from collections.abc import Callable
from typing import override
from uuid import UUID

from cadrumo.application.user_profile.capabilities import CapabilityDecision, resolve_capability_from_values
from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from cadrumo.core.capabilities import ServiceCapability
from cadrumo.core.config import Settings
from cadrumo.core.operations import OperationFrontendProjection

from ..contracts.access_refusals import AccessDenialCode
from ..contracts.contracts import RefusalCode, RefusalError
from .frontend_client_contracts import FrontendRefusedError
from .frontend_profile_view_client import ProfileViewFrontend
from .service_client import InstalledServiceClient


class InstalledServiceProfileView(ProfileViewFrontend):
    """Read the exact profile's registered view under the service's current lease.

    The service holds no person's session and no key. Each exchange names the
    lease's session as it stands then, so a lease the runtime withdrew or
    replaced is refused by the runtime and never borrowed from an earlier claim.
    """

    def __init__(self, service: InstalledServiceClient) -> None:
        """Bind the reads to the service's verified connection and its profile."""
        self._service = service
        self._connection = service.connection
        self._profile_id: UUID = service.profile_id
        self._frontend = OperationFrontendProjection.INSTALLED_SERVICE
        self._session_id = None

    @override
    def _session(self) -> UUID:
        lease = self._service.lease
        if lease is None:
            raise FrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value)
        return lease.session_id

    @override
    def subscribe_operation_changes(self, receive: Callable[[], None]) -> Callable[[], None]:
        """Cue ``receive`` for every frame the runtime pushes on this connection, and when it is lost."""
        return self._connection.subscribe_session_events(lambda _event: receive(), disconnected=receive)

    def read_capability(
        self, capability: ServiceCapability, *, settings: Settings, timeout: float
    ) -> CapabilityDecision:
        """Resolve one capability from the profile's facts as they are now, through the profile owner's policy.

        Only the one fact the capability names is kept from what the view served.
        A refusal, a changed record, an answer for another profile or a malformed
        page leaves no decision: the caller is told, never given a default.
        """
        collection = self.read_profile_view((ProfileViewPageKind.FACTS,), timeout=timeout)
        items = collection.items(ProfileViewPageKind.FACTS)
        if collection.profile_id != self.profile_id or not all(isinstance(item, ProfileViewFactItem) for item in items):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        values = {
            item.path: item.value
            for item in items
            if isinstance(item, ProfileViewFactItem) and item.path == capability.schema_path
        }
        return resolve_capability_from_values(capability, profile_values=values, settings=settings)
