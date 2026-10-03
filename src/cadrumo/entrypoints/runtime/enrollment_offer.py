"""Canonical connection-bound enrollment offer ownership."""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...application.runtime.enrollment_access import RuntimeEnrollmentPrepared
from ...application.runtime.enrollment_recipient import VolatileEnrollmentRecipient
from ...application.user_profile.access_contracts import AccessSession, Availability, OsLoginContext
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.automation_enrollment import (
    AdministrationFacts,
    EnrollmentRequester,
    ProtectedEnrollmentRecipient,
)
from ...core.time.clock import now

if TYPE_CHECKING:
    from ...application.user_profile.automation_enrollment import ProtectedEnrollmentRecipient
    from .profile_host import ProfileConnection, RuntimeProfileHost


@dataclass(slots=True)
class RuntimeEnrollmentOffer:
    """A single native connection owns its request until expiry or disconnect."""

    prepared: RuntimeEnrollmentPrepared
    connection: ProfileConnection
    host: RuntimeProfileHost
    deadline: float
    admitting: Callable[[], bool]
    lock_generation: int
    source_session: AccessSession | None = None
    recipient: VolatileEnrollmentRecipient | None = None
    closed: bool = False

    def requester(self) -> EnrollmentRequester:
        """Return only server-minted coordinates."""
        return EnrollmentRequester(
            runtime_boot_id=self.prepared.runtime_boot_id,
            connection_id=self.prepared.connection_id,
            client_id=self.prepared.client_id,
            destination_id=self.prepared.destination_id,
        )

    def require_live(self) -> None:
        """Reobserve originating login, current root generation and offer lifetime."""
        observation = self.connection.login.observe(credential_facilities=Availability.UNAVAILABLE)
        self._require_offer_window()
        self._require_observed_profile_binding(observation)
        self._require_source_session()
        self._require_current_profile_state()

    def _require_offer_window(self) -> None:
        if (
            self.closed
            or not self.admitting()
            or now() >= self.prepared.expires_at
            or time.monotonic() >= self.deadline
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)

    def _require_observed_profile_binding(self, observation: OsLoginContext) -> None:
        if (
            self.host.store.binding != self.prepared.profile_binding
            or not observation.active
            or observation.locked
            or observation.os_owner_id != self.connection.context.peer.os_owner_id
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)

    def _require_source_session(self) -> None:
        source = self.source_session
        if source is None:
            if self.connection.session_id is not None or self.connection.method != "enrollment":
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        else:
            if self.connection.session_id != source.session_id or self.connection.method != "api_key":
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            current = self.host.authority.automation_request_session(
                connection_id=self.prepared.connection_id, session_id=source.session_id
            )
            if (
                current.grant_id != source.grant_id
                or current.key_id != source.key_id
                or current.client_id != self.prepared.client_id
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)

    def _require_current_profile_state(self) -> None:
        # These canonical reads also validate the current on-disk custody
        # generation. An old host object cannot attest a restored/replaced root.
        lock = self.host.profile_lock_state()
        if lock.generation != self.lock_generation or lock.globally_locked:
            raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
        if not self.host.store.enrollment_state().automation_enabled:
            raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)

    def close(self) -> None:
        """Wake blocked delivery before host drain waits for its callback threads."""
        self.closed = True
        if self.recipient is not None:
            self.recipient.close()


@dataclass(frozen=True)
class RuntimeEnrollmentRequestOwner:
    """Inactive requests use verified connection facts without a human lease."""

    offer: RuntimeEnrollmentOffer

    @contextmanager
    def administration_guard(self) -> Generator[None]:
        """Share the existing profile publication and lifecycle fence."""
        with self.offer.host.guard:
            self.offer.require_live()
            yield

    def facts(self) -> AdministrationFacts:
        """Confer no session or private-operation authority."""
        self.offer.require_live()
        facts = self.offer.host.facts(self.offer.prepared.connection_id)
        return AdministrationFacts(
            profile=facts.profile,
            context=facts.context,
            originating_login_id=self.offer.connection.login.login_id,
            session=None,
        )

    def requester(self) -> EnrollmentRequester:
        """Bind every repeated publication to the same native client."""
        self.offer.require_live()
        return self.offer.requester()

    def recipient(self, requester: EnrollmentRequester) -> ProtectedEnrollmentRecipient:
        """This owner only creates inactive requests."""
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
