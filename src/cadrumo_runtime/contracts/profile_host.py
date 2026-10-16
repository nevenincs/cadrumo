"""Host-owned lifecycle ports after the native transport handshake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cadrumo_client.contracts.access_management import (
    AutomationDeny,
    ProfileRecoveryPrepare,
    ProfileResume,
    SessionInventory,
)
from cadrumo_client.contracts.attendance import (
    AttendanceAsk,
    AttendanceDecide,
    AttendanceDecided,
    AttendanceInventory,
    AttendancePending,
)
from cadrumo_client.contracts.bootstrap import PasswordReset, PasswordResetPrepare
from cadrumo_client.contracts.bootstrap_delete import ProfileDelete, ProfileDeletePrepare
from cadrumo_client.contracts.contracts import ByteChannel, ChannelWake
from cadrumo_client.contracts.enrollment_access import EnrollmentRequest
from cadrumo_client.contracts.extension_records import ExtensionRecordRequest
from cadrumo_client.contracts.installation_requests import InstallationActRequest
from cadrumo_client.contracts.operation_access import OperationRequest
from cadrumo_client.contracts.profile_access import (
    AccessRefusal,
    ProfileDisclosurePage,
    ProfileDisclosurePageRequest,
    ProfileLogin,
    ProfileStatus,
    SessionRequest,
    SessionsLocked,
)
from cadrumo_client.contracts.service_access import ServiceAdmission, ServiceConnect
from cadrumo_client.contracts.session_events import ConnectionEvent
from cadrumo_client.contracts.sign_in import HumanSignedOut, SignInStatusReply, SignInStatusRequest
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.native_wake import NativeWake

from .profile_worker import ProfileWorkerDrained


@dataclass(frozen=True)
class ProfileDrainResult:
    """Host-only proof of receipts and containment, never a public wire reply."""

    receipts: tuple[ProfileWorkerDrained, ...]
    missing_receipts: tuple[UUID, ...]
    uncontained: tuple[UUID, ...]
    unsettled: tuple[UUID, ...]
    parent_settled_profiles: tuple[UUID, ...] = ()

    @property
    def lacks_settlement_evidence(self) -> bool:
        """Keep missing worker receipts distinct from confirmed parent settlement."""
        return bool(set(self.missing_receipts) - set(self.parent_settled_profiles))


class ProfileHandler(Protocol):
    """Host-owned profile admission and lifetime hooks after the native handshake."""

    def connect_events(
        self, context: ConnectionContext, channel: ByteChannel | None = None, *, queued: NativeWake | None = None
    ) -> None:
        """Register an already verified stream for bounded retirement notices.

        ``queued`` is set whenever an event waits for the stream's writer, which
        blocks on it together with the channel between requests.
        """
        ...

    def take_events(self, context: ConnectionContext) -> tuple[ConnectionEvent, ...]:
        """Take one bounded batch, or refuse an overflowed connection."""
        ...

    def event_flushed(self, context: ConnectionContext, event: ConnectionEvent) -> None:
        """Record successful writing by this connection's sole writer, not user acknowledgement."""
        ...

    def handle(
        self,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ProfileLogin
        | SessionRequest
        | ProfileDisclosurePageRequest
        | SignInStatusRequest
        | AttendanceAsk
        | AttendanceDecide,
    ) -> (
        ProfileStatus
        | ProfileDisclosurePage
        | SessionsLocked
        | SignInStatusReply
        | HumanSignedOut
        | AttendancePending
        | AttendanceInventory
        | AttendanceDecided
        | AccessRefusal
    ):
        """Admit or observe only the exact current connection."""
        ...

    def disconnect(self, context: ConnectionContext) -> None:
        """Fence this connection without terminating other independently admitted work."""
        ...

    def operation(self, context: ConnectionContext, channel: ByteChannel, request: OperationRequest) -> None:
        """Resolve and write a canonical projection while holding current output authority."""
        ...

    def enrollment(self, context: ConnectionContext, channel: ByteChannel, request: EnrollmentRequest) -> None:
        """Complete one exact pre-unlock exchange on the verified native channel."""
        ...

    def manage_access(
        self,
        context: ConnectionContext,
        channel: ByteChannel,
        request: AutomationDeny | ProfileRecoveryPrepare | ProfileResume | SessionInventory,
    ) -> None:
        """Complete one exact access-management exchange on the verified channel."""
        ...

    def bootstrap_delete(
        self, context: ConnectionContext, channel: ByteChannel, request: ProfileDeletePrepare | ProfileDelete
    ) -> None:
        """Host a confirmed existing deletion journal without profile admission."""
        ...

    def bootstrap(
        self, context: ConnectionContext, channel: ByteChannel, request: PasswordResetPrepare | PasswordReset
    ) -> None:
        """Run an exact bootstrap custody transaction with separate proof."""
        ...

    def installation(self, context: ConnectionContext, channel: ByteChannel, request: InstallationActRequest) -> None:
        """Serve one sessionless installation act on the verified native channel."""
        ...

    def service(
        self, context: ConnectionContext, channel: ByteChannel, request: ServiceConnect | ServiceAdmission
    ) -> None:
        """Register or human-admit an exact installed service peer."""
        ...

    def extension_record(
        self, context: ConnectionContext, channel: ByteChannel, request: ExtensionRecordRequest
    ) -> None:
        """Exchange admitted opaque extension records through protected frames."""
        ...

    def poll(self) -> None:
        """Revalidate leases without requiring a frontend call."""
        ...

    @property
    def lifecycle_wake(self) -> ChannelWake:
        """Return the flag set when the wait for the next lifecycle pass must be decided again."""
        ...

    def lifecycle_due_in(self) -> float | None:
        """Return the seconds until a pass is due with nothing happening, or ``None`` when only a call brings one."""
        ...

    def lifecycle_changed(self) -> None:
        """Have a pass look, soon but coalesced, at what a request or a disconnect changed."""
        ...

    def close(self) -> None:
        """Fence and settle owned profile custody before runtime ownership is released."""
        ...

    def drain(self, *, deadline: float) -> ProfileDrainResult:
        """Fence admissions and drain all workers under one monotonic deadline."""
        ...
