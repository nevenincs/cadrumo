"""The exact profile's own answer to whether its documents may be read away from this computer."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from cadrumo.application.user_profile.capabilities import CapabilityDecision
from cadrumo.core.capabilities import ServiceCapability
from cadrumo.core.config import Settings
from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.service_client import InstalledServiceClient
from cadrumo_client.transport.service_profile_view import InstalledServiceProfileView

from ..providers.application.attachment_releases import DisclosureRefusalCode

_LOGGER = get_logger(__name__)


class ProfileCloudEligibility(StrEnum):
    """What the profile says; an answer that could not be read is never an opt-in."""

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    UNREADABLE = "unreadable"


class CapabilityView(Protocol):
    """The registered profile read that resolves one capability for the exact profile."""

    def read_capability(
        self, capability: ServiceCapability, *, settings: Settings, timeout: float
    ) -> CapabilityDecision:
        """Resolve the capability now, or refuse."""
        ...


class ProfileCloudEligibilityRead:
    """Read the capability through the profile's registered view, at every call.

    The service holds no profile storage and no key. It asks the runtime under its
    own lease and keeps nothing between calls: a change to the profile, a sign-out
    or a withdrawn lease is seen by the next decision, not by a later one.
    """

    def __init__(self, *, view: CapabilityView, timeout_seconds: float) -> None:
        """Bind the reads to a view, each bounded by ``timeout_seconds``."""
        self._view = view
        self._timeout = timeout_seconds

    @classmethod
    def over(cls, client: InstalledServiceClient, *, timeout_seconds: float) -> ProfileCloudEligibilityRead:
        """Read through the service's own runtime connection."""
        return cls(view=InstalledServiceProfileView(client), timeout_seconds=timeout_seconds)

    def read(self, *, settings: Settings) -> ProfileCloudEligibility:
        """Answer from the profile as it is now; a failed read is ``UNREADABLE``."""
        try:
            decision = self._view.read_capability(
                ServiceCapability.CLOUD_EVIDENCE_UPLOAD, settings=settings, timeout=self._timeout
            )
        except (FrontendRefusedError, RefusalError, TimeoutError, OSError, ValueError) as error:
            diagnostic_event(_LOGGER, "profile_cloud_eligibility_unreadable", fields=diagnostic_error_fields(error))
            return ProfileCloudEligibility.UNREADABLE
        return ProfileCloudEligibility.ELIGIBLE if decision.enabled else ProfileCloudEligibility.NOT_ELIGIBLE


def disclosure_bar(read: ProfileCloudEligibilityRead, settings: Settings) -> DisclosureRefusalCode | None:
    """Name the first bar to an off-host attachment release, read as it stands now.

    Gestor mode bars it outright, then the deployment must have opted in, then the
    exact profile's own setting is read through the runtime. A profile that cannot
    be read is a bar of its own: it is never taken for an opt-in.
    """
    if settings.cadrumo_evidence_gestor_mode:
        return DisclosureRefusalCode.GESTOR_MODE
    if not settings.cadrumo_evidence_cloud_upload_permitted:
        return DisclosureRefusalCode.CLOUD_UPLOAD_NOT_PERMITTED
    match read.read(settings=settings):
        case ProfileCloudEligibility.ELIGIBLE:
            return None
        case ProfileCloudEligibility.NOT_ELIGIBLE:
            return DisclosureRefusalCode.PROFILE_NOT_ELIGIBLE
        case ProfileCloudEligibility.UNREADABLE:
            return DisclosureRefusalCode.PROFILE_UNREADABLE
