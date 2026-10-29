"""Bounded frontend access to one native-verified profile runtime connection."""

from __future__ import annotations

import asyncio
import hmac
import time
from collections.abc import Callable
from threading import Event, RLock
from typing import Literal, Self, cast, override
from uuid import UUID, uuid4

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.logging import get_logger
from cadrumo.core.profile_session import ProfileSessionRefusalReason

from ..contracts.access_refusals import AccessDenialCode
from ..contracts.access_vocabulary import AccessScope
from ..contracts.attendance import (
    AttendanceAsk,
    AttendanceDecide,
    AttendanceDecided,
    AttendanceInventory,
    AttendancePending,
)
from ..contracts.automation_codes import AutomationCustodyCode
from ..contracts.contracts import RefusalCode, RefusalError
from ..contracts.deadline_budget import (
    DEFAULT_TIMEOUT_POLICY,
    MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    TimeoutDeadline,
    deadline_after,
)
from ..contracts.model_runs import ModelRunRequested
from ..contracts.profile_access import (
    ProfileLogin,
    ProfileStatus,
    SessionRequest,
)
from ..contracts.service_access import (
    ServiceAdmission,
    ServiceAdmissionPending,
    ServiceAdmissionStatusQuery,
    ServiceConnected,
)
from ..contracts.session_events import (
    AttendanceAnswered,
    AttendanceChanged,
    ConnectionEvent,
    LifecycleNotice,
    OperationChanged,
    PresentationRequested,
    ProfileLanguageChanged,
    ProfileLoginChanged,
    ProfileRecordsChanged,
    ServiceAdmissionChanged,
    ServiceLeaseChanged,
    SessionEvent,
    SignInChanged,
)
from ..contracts.sign_in import HumanSignedOut, SignInStatusReply
from ..contracts.sign_in_outcomes import ProfileReceiptRefusedError
from .framing import VerifiedConnection
from .frontend_client_contracts import FrontendRefusedError
from .frontend_receipt import RECEIPT_PROOF_ATTEMPTS, receipt_refusal
from .frontend_session_client import FrontendSessionClient
from .startup import LaunchDoor
from .transport_cleanup import TransportCleanup


def _admitted_login_session(reply: ProfileStatus, profile_id: UUID) -> UUID:
    status = reply.status
    if (
        status.denial is not None
        or not status.connected
        or not status.credential_authenticated
        or not status.profile_bound
        or status.profile_id != profile_id
        or status.session_id is None
    ):
        raise FrontendRefusedError(
            status.denial.value if status.denial is not None else AccessDenialCode.PROFILE_MISMATCH.value
        )
    return status.session_id


class FrontendClient(FrontendSessionClient):
    """Own one exact profile/frontend connection and its connection-bound lease.

    The caller retains this object only for its frontend session. Every method
    derives the profile and session coordinates from a successful native login;
    copied IDs and ambient profile selection cannot retarget it. Blocking wire
    methods should be called off a UI event loop.
    """

    def __init__(
        self,
        connection: VerifiedConnection,
        *,
        profile_id: UUID,
        frontend: OperationFrontendProjection,
        scope: AccessScope | None = None,
    ) -> None:
        """Bind one verified connection to an explicit immutable frontend target."""
        self._connection = connection
        self._profile_id = profile_id
        self._frontend = frontend
        self._scope = scope
        self._session_id: UUID | None = None
        self._connection_purpose: Literal["fresh", "admission", "recovery", "enrollment", "bootstrap", "attendance"] = (
            "fresh"
        )
        self._event_guard = RLock()
        self._retirement_epoch = 0
        self._retirement_receivers: list[Callable[[], None]] = []
        self._event_subscription: Callable[[], None] | None = None
        self._notice_receivers: list[Callable[[LifecycleNotice], None]] = []
        self._language_receivers: list[Callable[[ProfileLanguageChanged], None]] = []
        self._record_receivers: list[Callable[[], None]] = []
        self._lifecycle_notice: LifecycleNotice | None = None
        self._sign_in_receivers: list[Callable[[], None]] = []
        self._attendance_receivers: list[Callable[[], None]] = []
        self._answer_receivers: list[Callable[[], None]] = []
        self._operation_receivers: list[Callable[[], None]] = []

    def _handle_global_event(self, event: ConnectionEvent) -> bool:
        if isinstance(event, ProfileLoginChanged):
            return True
        if isinstance(event, LifecycleNotice):
            with self._event_guard:
                self._lifecycle_notice = event
                receivers = tuple(self._notice_receivers)
            for receive_notice in receivers:
                receive_notice(event)
            return True
        if isinstance(event, SignInChanged):
            with self._event_guard:
                receivers_sign_in = tuple(self._sign_in_receivers)
            for receive_sign_in in receivers_sign_in:
                receive_sign_in()
            return True
        return False

    def _handle_profile_event(self, event: ConnectionEvent) -> bool:
        if isinstance(event, ServiceAdmissionChanged):
            return True
        if isinstance(event, AttendanceAnswered):
            # The asker holds no session until its approved ask is read.
            with self._event_guard:
                receivers_answer = tuple(self._answer_receivers)
            for receive_answer in receivers_answer:
                receive_answer()
            return True
        if isinstance(event, AttendanceChanged):
            with self._event_guard:
                receivers_attendance = tuple(self._attendance_receivers) if event.session_id == self._session_id else ()
            for receive_attendance in receivers_attendance:
                receive_attendance()
            return True
        return False

    def _handle_session_event(self, event: ConnectionEvent) -> bool:
        if isinstance(event, OperationChanged):
            with self._event_guard:
                receivers_operation = tuple(self._operation_receivers) if event.session_id == self._session_id else ()
            for receive_operation in receivers_operation:
                receive_operation()
            return True
        if isinstance(event, ProfileRecordsChanged):
            with self._event_guard:
                receivers_records = tuple(self._record_receivers) if event.session_id == self._session_id else ()
            for receive_records in receivers_records:
                receive_records()
            return True
        return False

    def _handle_presentation_event(self, event: ConnectionEvent) -> bool:
        if isinstance(event, PresentationRequested):
            return True
        if isinstance(event, ProfileLanguageChanged):
            with self._event_guard:
                receivers_language = tuple(self._language_receivers) if event.session_id == self._session_id else ()
            for receive_language in receivers_language:
                receive_language(event)
            return True
        return False

    def _session_retired(self, event: ConnectionEvent) -> None:
        if self._handle_global_event(event):
            return
        profile_event = cast(
            SessionEvent
            | ProfileLanguageChanged
            | ProfileRecordsChanged
            | ServiceLeaseChanged
            | ServiceAdmissionChanged
            | AttendanceChanged
            | AttendanceAnswered
            | OperationChanged
            | PresentationRequested
            | ModelRunRequested,
            event,
        )
        if profile_event.profile_id != self.profile_id or isinstance(
            profile_event, ServiceLeaseChanged | ModelRunRequested
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        if (
            self._handle_profile_event(event)
            or self._handle_session_event(event)
            or self._handle_presentation_event(event)
        ):
            return
        with self._event_guard:
            self._retirement_epoch += 1
            if self._session_id != cast(SessionEvent, event).session_id:
                return
            self._session_id = None
            receivers = tuple(self._retirement_receivers)
            observers = tuple(self._operation_receivers)
        for receive in (*receivers, *observers):
            try:
                receive()
            except Exception as error:
                get_logger(__name__).warning("retirement callback failed error_type=%s", type(error).__name__)

    def _connection_failed(self) -> None:
        with self._event_guard:
            self._retirement_epoch += 1
            self._session_id = None
            receivers = tuple(self._retirement_receivers)
            # A sign-in watch reads its status again and learns the connection is gone.
            watchers = tuple(self._sign_in_receivers)
            # An operation waiter observes again and is refused at once.
            observers = tuple(self._operation_receivers)
            # So does an asker waiting for its answer.
            askers = tuple(self._answer_receivers)
        for receive in (*receivers, *watchers, *observers, *askers):
            try:
                receive()
            except Exception as error:
                get_logger(__name__).warning("disconnect callback failed error_type=%s", type(error).__name__)

    def subscribe_session_retirement(self, receive: Callable[[], None]) -> Callable[[], None]:
        """Subscribe a nonblocking private-view clearing callback, never a proof consumer."""
        if self._event_subscription is None:
            self._event_subscription = self._connection.subscribe_session_events(
                self._session_retired, disconnected=self._connection_failed
            )
        with self._event_guard:
            self._retirement_receivers.append(receive)
            inactive = self._session_id is None
        if inactive:
            receive()

        def unsubscribe() -> None:
            with self._event_guard:
                if receive in self._retirement_receivers:
                    self._retirement_receivers.remove(receive)

        return unsubscribe

    def subscribe_lifecycle_notices(self, receive: Callable[[LifecycleNotice], None]) -> Callable[[], None]:
        """Observe nonsecret notices without changing authentication or requesting manager actions."""
        if self._event_subscription is None:
            self._event_subscription = self._connection.subscribe_session_events(
                self._session_retired, disconnected=self._connection_failed
            )
        with self._event_guard:
            self._notice_receivers.append(receive)
            retained = self._lifecycle_notice
        if retained is not None:
            receive(retained)

        def unsubscribe() -> None:
            with self._event_guard:
                if receive in self._notice_receivers:
                    self._notice_receivers.remove(receive)

        return unsubscribe

    def subscribe_profile_language_changes(
        self, receive: Callable[[ProfileLanguageChanged], None]
    ) -> Callable[[], None]:
        """Observe exact-profile invalidation without refreshing or extending authority."""
        if self._event_subscription is None:
            self._event_subscription = self._connection.subscribe_session_events(
                self._session_retired, disconnected=self._connection_failed
            )
        with self._event_guard:
            self._language_receivers.append(receive)

        def unsubscribe() -> None:
            with self._event_guard:
                if receive in self._language_receivers:
                    self._language_receivers.remove(receive)

        return unsubscribe

    def subscribe_profile_record_changes(self, receive: Callable[[], None]) -> Callable[[], None]:
        """Observe record invalidation without reading values or extending authority."""
        if self._event_subscription is None:
            self._event_subscription = self._connection.subscribe_session_events(
                self._session_retired, disconnected=self._connection_failed
            )
        with self._event_guard:
            self._record_receivers.append(receive)

        def unsubscribe() -> None:
            with self._event_guard:
                if receive in self._record_receivers:
                    self._record_receivers.remove(receive)

        return unsubscribe

    @classmethod
    async def open(
        cls,
        launch: LaunchDoor,
        *,
        profile_id: UUID,
        frontend: OperationFrontendProjection,
        timeout: float | None = None,
        timeout_deadline: TimeoutDeadline | None = None,
        scope: AccessScope | None = None,
    ) -> Self:
        """Use the canonical owner-verified launch door before any credential."""
        return cls(
            await launch.open(timeout=timeout, timeout_deadline=timeout_deadline),
            profile_id=profile_id,
            frontend=frontend,
            scope=scope,
        )

    def __enter__(self) -> Self:
        """Retain this owned connection for a synchronous frontend scope."""
        return self

    def __exit__(self, *_exc: object) -> None:
        """Close this frontend's owned connection."""
        self.close()

    async def __aenter__(self) -> Self:
        """Retain this owned connection for an asynchronous frontend scope."""
        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Close this frontend's owned connection."""
        await await_cancellation_complete(asyncio.to_thread(self.close), task_name="frontend-runtime-close")

    def close(self) -> None:
        """End this connection's lease without stopping the shared runtime."""
        self._session_id = None
        self._connection.close()

    def cleanup_owner(self, *, primary_error: BaseException | None) -> TransportCleanup:
        """Fence this client and retain one owner for its exact connection."""
        self._session_id = None
        retained = None if primary_error is None else primary_error.__dict__.get("_transport_cleanup")
        if isinstance(retained, TransportCleanup) and (
            retained.resource is self or retained.resource is self._connection
        ):
            # The failed exchange already owns this native release. Rebinding
            # that same owner also clears frontend state without duplicating
            # the connection's retry path in a merged cleanup attachment.
            retained.resource = self
            return retained
        return TransportCleanup(self)

    def _login(
        self,
        method: str,
        secret: bytearray,
        *,
        timeout: float,
        persist_receipt: bool = False,
        hand_over: bool = False,
    ) -> ProfileStatus:
        try:
            if self._connection_purpose in {"recovery", "enrollment", "bootstrap"}:
                raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            if self._session_id is not None:
                raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            self._connection_purpose = "admission"
            document: dict[str, object] = {
                "request_id": uuid4(),
                "profile_id": self.profile_id,
                "frontend": self.frontend,
                "method": method,
                "persist_receipt": persist_receipt,
                "hand_over": hand_over,
            }
            if self._scope is not None:
                document["scope"] = self._scope.model_dump(mode="python")
            request = ProfileLogin.model_validate(document)
            with self._event_guard:
                epoch = self._retirement_epoch
            reply = self._reply(
                self._connection.login(request, secret, deadline=deadline_after(timeout)), ProfileStatus
            )
            session_id = _admitted_login_session(reply, self.profile_id)
            if self._event_subscription is None:
                self._event_subscription = self._connection.subscribe_session_events(
                    self._session_retired, disconnected=self._connection_failed
                )
            with self._event_guard:
                if epoch != self._retirement_epoch:
                    raise FrontendRefusedError(AccessDenialCode.SESSION_INACTIVE.value)
                self._session_id = session_id
            return reply
        finally:
            secret[:] = bytes(len(secret))

    def login_password(
        self,
        secret: bytearray,
        *,
        timeout: float = DEFAULT_TIMEOUT_POLICY.timeout_seconds,
        persist_receipt: bool = False,
    ) -> ProfileStatus:
        """Consume an explicit password only on the one-use verified secret frame."""
        return self._login("password", secret, timeout=timeout, persist_receipt=persist_receipt)

    def login_api_key(
        self, secret: bytearray, *, timeout: float = DEFAULT_TIMEOUT_POLICY.timeout_seconds
    ) -> ProfileStatus:
        """Consume an explicit key without attempting human receipt fallback."""
        return self._login("api_key", secret, timeout=timeout)

    def resume_receipt(
        self, *, timeout: float = DEFAULT_TIMEOUT_POLICY.timeout_seconds, hand_over: bool = False
    ) -> ProfileStatus:
        """Present the exact profile's keychain-held receipt proof on one verified frame.

        This process reads only the proof and the receipt locator. It never
        unwraps, extends or deletes the receipt: the runtime verifies the
        proof against this connection's login and the current sign-in
        generation, and deletes a receipt it refuses. A runtime refusal of the
        receipt returns as :class:`ProfileReceiptRefusedError`, like a local
        one, so callers keep one fallback path. A resume continues the sign-in
        and signs no other profile out. ``hand_over`` is the person signing in
        to this profile with it, which signs every other profile out as a
        password sign-in does.

        A sign-in that completes between the borrow and the runtime's check
        replaces the receipt, so the proof read before it no longer unwraps
        what the runtime reads. Such a refusal is retried with a fresh borrow,
        a bounded number of times and only while the borrowed proof differs
        from the one refused.
        """
        from .receipt_proof import borrow_receipt_proof

        deadline = time.monotonic() + timeout
        attempts = 0
        presented = bytearray()
        stale: ProfileReceiptRefusedError | None = None
        try:
            while True:
                with borrow_receipt_proof(profile_id=self.profile_id) as proof:
                    if stale is not None and hmac.compare_digest(proof, presented):
                        # No sign-in replaced the receipt: the proof was refused for itself.
                        raise stale
                    presented[:] = bytes(len(presented))
                    # The exchange wipes the proof it presents; this copy tells a later borrow apart.
                    presented = bytearray(proof)
                    attempts += 1
                    try:
                        return self._login(
                            "receipt", proof, timeout=max(0.0, deadline - time.monotonic()), hand_over=hand_over
                        )
                    except FrontendRefusedError as error:
                        refused = receipt_refusal(error)
                        if refused is None:
                            raise
                        # A proof that no longer unwraps the receipt may only be stale: a sign-in
                        # completing meanwhile replaced the receipt, and a fresh borrow reads its proof.
                        if (
                            refused.reason is not ProfileSessionRefusalReason.TAMPERED
                            or attempts >= RECEIPT_PROOF_ATTEMPTS
                            or time.monotonic() >= deadline
                        ):
                            raise refused from error
                        refused.__cause__ = error
                        stale = refused
        finally:
            presented[:] = bytes(len(presented))

    def request_attendance(
        self, *, timeout: float = DEFAULT_TIMEOUT_POLICY.timeout_seconds
    ) -> AttendancePending | ProfileStatus:
        """Ask to be attended by the person's held sign-in; nothing is admitted until the person decides.

        A connection the person already approved under a sign-in that is
        still live is admitted again at once, and the status says so.
        """
        return self._attendance(self._attendance_ask("attendance_request", None), timeout=timeout)

    def attendance_status(
        self, attendance_id: UUID, *, timeout: float = DEFAULT_TIMEOUT_POLICY.timeout_seconds
    ) -> AttendancePending | ProfileStatus:
        """Observe this connection's own ask; an approved one binds the attended session here."""
        return self._attendance(self._attendance_ask("attendance_status", attendance_id), timeout=timeout)

    def service_admission(
        self,
        recipient_connection_id: UUID,
        service_id: str,
        *,
        request_id: UUID | None = None,
        timeout: float | None = None,
    ) -> ServiceConnected:
        """Start once, then claim on a cue without occupying this person's wire slot."""
        owner_deadline = (
            DEFAULT_TIMEOUT_POLICY.deadline() if timeout is None else TimeoutDeadline(deadline_after(timeout))
        )
        changed = Event()
        session_id = self._session()

        def observed(event: ConnectionEvent) -> None:
            if (
                isinstance(event, ServiceAdmissionChanged)
                and event.profile_id == self.profile_id
                and event.session_id == session_id
            ):
                changed.set()

        unsubscribe = self._connection.subscribe_session_events(observed, disconnected=changed.set)
        try:
            reply = self._connection.service_access(
                ServiceAdmission(
                    request_id=request_id or uuid4(),
                    profile_id=self.profile_id,
                    session_id=session_id,
                    recipient_connection_id=recipient_connection_id,
                    service_id=service_id,
                ),
                deadline=owner_deadline.instant,
            )
            while isinstance(reply, ServiceAdmissionPending):
                admission_id = reply.admission_id
                changed.clear()
                reply = self._connection.service_access(
                    ServiceAdmissionStatusQuery(
                        action="service_admission_status",
                        request_id=uuid4(),
                        profile_id=self.profile_id,
                        session_id=session_id,
                        recipient_connection_id=recipient_connection_id,
                        service_id=service_id,
                        admission_id=admission_id,
                    ),
                    deadline=owner_deadline.instant,
                )
                if isinstance(reply, ServiceAdmissionPending) and not changed.wait(owner_deadline.remaining_seconds()):
                    raise RefusalError(RefusalCode.TIMEOUT)
            return self._reply(reply, ServiceConnected)
        finally:
            unsubscribe()

    def attendance_inventory(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> AttendanceInventory:
        """List the asks pending for this person's profile, as the holder of its live sign-in."""
        return self._reply(
            self._connection.attendance(
                AttendanceDecide(
                    action="attendance_inventory",
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                ),
                deadline=deadline_after(timeout),
            ),
            AttendanceInventory,
        )

    def decide_attendance(
        self, attendance_id: UUID, *, approve: bool, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> AttendanceDecided:
        """Approve or decline one exact ask under this connection's own human session."""
        return self._reply(
            self._connection.attendance(
                AttendanceDecide(
                    action="attendance_decision",
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                    attendance_id=attendance_id,
                    approve=approve,
                ),
                deadline=deadline_after(timeout),
            ),
            AttendanceDecided,
        )

    def _attendance_ask(
        self, action: Literal["attendance_request", "attendance_status"], attendance_id: UUID | None
    ) -> AttendanceAsk:
        if self._connection_purpose not in {"fresh", "attendance"} or (
            self._session_id is not None and self._connection_purpose != "attendance"
        ):
            raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
        # An attended connection asks again when its short lease ends. The runtime answers with the
        # child it still holds, or issues a new one under the same approval while the person's session lives.
        self._session_id = None
        self._connection_purpose = "attendance"
        return AttendanceAsk(
            action=action,
            request_id=uuid4(),
            profile_id=self.profile_id,
            frontend=self.frontend,
            scope=self._scope,
            attendance_id=attendance_id,
        )

    def _attendance(self, request: AttendanceAsk, *, timeout: float) -> AttendancePending | ProfileStatus:
        with self._event_guard:
            epoch = self._retirement_epoch
        reply = self._connection.attendance(request, deadline=deadline_after(timeout))
        if isinstance(reply, AttendancePending):
            return reply
        admitted = self._reply(reply, ProfileStatus)
        status = admitted.status
        if (
            status.denial is not None
            or not status.connected
            or not status.profile_bound
            or status.profile_id != self.profile_id
            or status.session_id is None
        ):
            raise FrontendRefusedError(
                status.denial.value if status.denial is not None else AccessDenialCode.PROFILE_MISMATCH.value
            )
        if self._event_subscription is None:
            self._event_subscription = self._connection.subscribe_session_events(
                self._session_retired, disconnected=self._connection_failed
            )
        with self._event_guard:
            if epoch != self._retirement_epoch:
                raise FrontendRefusedError(AccessDenialCode.SESSION_INACTIVE.value)
            self._session_id = status.session_id
        return admitted

    def watch_sign_in(
        self, receive: Callable[[], None], *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> SignInStatusReply:
        """Read presence, then cue ``receive`` whenever any sign-in may have changed, until the connection closes.

        A cue is only a reason to read the status again; it carries no state.
        """
        self._observe_events()
        with self._event_guard:
            self._sign_in_receivers.append(receive)
        return self.sign_in_status(timeout=timeout, watch=True)

    def subscribe_attendance_changes(self, receive: Callable[[], None]) -> Callable[[], None]:
        """Cue ``receive`` when asks pending for this session's person change; re-read the inventory to see them."""
        self._observe_events()
        with self._event_guard:
            self._attendance_receivers.append(receive)

        def unsubscribe() -> None:
            with self._event_guard:
                if receive in self._attendance_receivers:
                    self._attendance_receivers.remove(receive)

        return unsubscribe

    def subscribe_attendance_answers(self, receive: Callable[[], None]) -> Callable[[], None]:
        """Cue ``receive`` when this connection's own ask is answered, or the connection is lost.

        The cue carries no answer; read the ask's status again to learn it.
        """
        self._observe_events()
        with self._event_guard:
            self._answer_receivers.append(receive)

        def unsubscribe() -> None:
            with self._event_guard:
                if receive in self._answer_receivers:
                    self._answer_receivers.remove(receive)

        return unsubscribe

    @override
    def subscribe_operation_changes(self, receive: Callable[[], None]) -> Callable[[], None]:
        """Cue ``receive`` when an operation this session observes may have advanced, or the connection is lost.

        The cue names no operation; observe again to learn what changed.
        """
        self._observe_events()
        with self._event_guard:
            self._operation_receivers.append(receive)

        def unsubscribe() -> None:
            with self._event_guard:
                if receive in self._operation_receivers:
                    self._operation_receivers.remove(receive)

        return unsubscribe

    def _observe_events(self) -> None:
        if self._event_subscription is None:
            self._event_subscription = self._connection.subscribe_session_events(
                self._session_retired, disconnected=self._connection_failed
            )

    def human_sign_out(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> HumanSignedOut:
        """Revoke profile-wide human access using this connection's proven human session."""
        if self._session_id is None:
            self.resume_receipt(timeout=timeout)
        result = self._reply(
            self._connection.session(
                SessionRequest(
                    action="human_sign_out", request_id=uuid4(), profile_id=self.profile_id, session_id=self._session()
                ),
                deadline=deadline_after(timeout),
            ),
            HumanSignedOut,
        )
        if result.profile_id != self.profile_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._session_id = None
        return result
