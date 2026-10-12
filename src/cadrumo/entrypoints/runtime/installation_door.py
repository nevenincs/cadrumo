"""The runtime's door for sessionless installation acts.

An installation act names no profile session, so nothing a profile login
proves is available to admit it. The door admits it on the same evidence the
confirmed profile deletion uses: the verified native peer and boot, and an
active unlocked login of the peer's own account, reobserved rather than
remembered. An act that changes records also takes the lifecycle exclusion
that serializes custody changes with polling and shutdown. The frontend a
request names is recorded and decides nothing.

The door owns framing. A handler never reads or writes the channel: it asks
its exchange for a passphrase, hands it a recovery code to deliver, and returns
one reply. Secrets cross only in secret frames and are wiped where a mutable
copy exists.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, SecretBytes, ValidationError

from ...adapters.local_runtime.installation_frame_io import (
    InstallationSettledReply,
    installation_reply_payload,
    write_installation_reply,
)
from ...adapters.local_runtime.runtime_frame_io import (
    decode_document,
    read_document,
    read_secret,
    write_document,
    write_secret,
)
from ...application.operations.error_detail import build_operation_error_detail
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeShutdownIncompleteError,
)
from ...application.runtime.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    INSTALLATION_SECRET_HANDOVER_SECONDS,
    InstallationAct,
    InstallationActContract,
    RuntimeInstallationActRequest,
    RuntimeInstallationCompleted,
    RuntimeInstallationFailed,
    RuntimeInstallationRefused,
    RuntimeInstallationSecretDelivery,
    RuntimeInstallationSecretReceipt,
    installation_act_of,
    installation_request_facts,
)
from ...application.runtime.login import RuntimeLoginEvidence
from ...application.runtime.profile_access import RuntimeAccessRefusal, RuntimeSecretReady
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import AccessDenialCode, Availability
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from ...core.config import load_settings, override_settings
from ...core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from ...core.errors.hierarchy import CadrumoError, InternalInvariantError
from ...core.logging import get_logger

if TYPE_CHECKING:
    from .installation_composition import InstallationActRegistry
    from .profile_connections import RuntimeProfileConnections

_LOGGER = get_logger(__name__)

_WRITE_SECONDS: Final[float] = 5.0
_SECRET_READ_SECONDS: Final[float] = 10.0
_REPLY_WRITE_SECONDS: Final[float] = 15.0
_HOST_DRAIN_SECONDS: Final[float] = 15.0


class InstallationActHandler[RequestT: BaseModel](Protocol):
    """Do one act's work and return that act's completed reply.

    The handler builds its reply with :meth:`InstallationActExchange.reply`. It
    may raise a registered error, which reaches the caller as that error on
    every frontend, or an access refusal, which reaches it as that code for as
    long as nothing was changed. A handler that changes records calls
    :meth:`InstallationActExchange.changes_begin` before its first change: an
    access refusal raised after that no longer proves that nothing changed, and
    settles as a failure whose effect is unknown.
    """

    def __call__(self, request: RequestT, exchange: InstallationActExchange, /) -> RuntimeInstallationCompleted:
        """Serve ``request`` using only what ``exchange`` lends."""
        ...


class _LifecycleHold:
    """Whether this act currently holds the lifecycle exclusion, and how to lend it back."""

    def __init__(self, owner: RuntimeProfileConnections, *, held: bool) -> None:
        self._owner = owner
        self.held = held

    def release(self) -> None:
        if self.held:
            self.held = False
            self._owner._drain_guard.release()

    @contextmanager
    def suspended(self) -> Generator[None]:
        """Free the exclusion across a wait on a person, then take it again or refuse."""
        if not self.held:
            yield
            return
        self.release()
        try:
            yield
        finally:
            self.held = self._owner._drain_guard.acquire_delete()
        if not self.held:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)


class InstallationProfileReservation:
    """Exclusive custody of named profiles for the length of one act."""

    def __init__(self, owner: RuntimeProfileConnections, profile_ids: frozenset[UUID]) -> None:
        """Bind the reservation to the profiles it fences."""
        self._owner = owner
        self.profile_ids = profile_ids

    def retire_hosted(self) -> None:
        """Drain and close every reserved profile this runtime is hosting.

        A profile nobody opened has no host and nothing to retire. A host that
        cannot be contained within its bound refuses the act: unknown lock
        evidence is never authority to continue.
        """
        for profile_id in sorted(self.profile_ids, key=str):
            with self._owner._guard:
                host = self._owner._profiles.get(profile_id)
            if host is None:
                continue
            with host.guard:
                worker = host.owner.begin_drain()
            deadline = time.monotonic() + _HOST_DRAIN_SECONDS
            if worker is not None:
                worker.drain(deadline=deadline)
            if not host.owner.wait_construction(deadline=deadline):
                raise RuntimeShutdownIncompleteError()
            host.close()
            self._owner._remove_retired_host(host)


class InstallationActExchange:
    """Everything one handler may ask of the door while its act runs."""

    def __init__(
        self,
        owner: RuntimeProfileConnections,
        *,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeInstallationActRequest,
        contract: InstallationActContract,
        login: RuntimeLoginEvidence,
        lifecycle: _LifecycleHold,
    ) -> None:
        """Bind one admitted request to the connection that sent it."""
        self._owner = owner
        self._context = context
        self._channel = channel
        self._request = request
        self._contract = contract
        self._login = login
        self._lifecycle = lifecycle
        self._secret_received = False
        self._secret_delivered = False
        self._changes_began = False

    @property
    def act(self) -> InstallationAct:
        """Name the act being served."""
        return self._contract.act

    @property
    def storage_root(self) -> Path:
        """Return the storage root this runtime owns."""
        return self._owner.root

    @contextmanager
    def served_settings(self) -> Generator[None]:
        """Resolve settings over the storage root this runtime serves, for the length of one act.

        A runtime is started over a root it is told, and admits, fences and
        drains for that root alone. Its own process settings may name another.
        An act that reads the tree through settings does so inside this scope,
        so that what it works on is what the door admitted it for. Where the
        two already agree the runtime's settings stand, as they do for a
        command run in the same installation.
        """
        if load_settings().cadrumo_local_storage_root.resolve() == self.storage_root.resolve():
            yield
            return
        with override_settings(cadrumo_local_storage_root=self.storage_root):
            yield

    def changes_begin(self) -> None:
        """Say that the handler's next step may change records.

        Until this is called a custody, runtime or access error proves that
        nothing was changed, and reaches the caller as a refusal. From here it
        does not, and the door settles it as a failure whose effect is unknown.
        Only an act admitted under the lifecycle exclusion may begin changes.
        """
        if not self._lifecycle.held:
            raise InternalInvariantError("an installation act admitted as a read cannot begin changes")
        self._changes_began = True

    @property
    def changes_began(self) -> bool:
        """Whether the handler has reached the step that may change records."""
        return self._changes_began

    def secret_store(self) -> AutomationSecretStore:
        """Return the runtime's protected credential store."""
        return self._owner._secret_store()

    def reply[ReplyT: RuntimeInstallationCompleted](self, reply_type: type[ReplyT], /, **members: object) -> ReplyT:
        """Build this act's reply on the coordinates of the request being served."""
        return reply_type.model_validate(
            {
                "request_id": self._request.request_id,
                "runtime_boot_id": self._owner.boot,
                "connection_id": self._context.connection_id,
                **members,
            }
        )

    def require_login(self) -> None:
        """Reobserve the peer's login; a handler calls this again before an irreversible step."""
        observed = self._login.observe(credential_facilities=Availability.UNAVAILABLE)
        if not self._owner._admitting():
            raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
        if not observed.active or not observed.unlocked or observed.os_owner_id != self._context.peer.os_owner_id:
            raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)

    def receive_secret[SecretT: BaseModel](self, document: type[SecretT]) -> SecretT:
        """Ask for the act's one secret frame and decode it as ``document``.

        The frame is requested only after the login is reobserved, and its
        mutable copy is wiped before this returns. The caller drops the decoded
        document as soon as its service has consumed it.
        """
        if not self._contract.takes_secret or self._secret_received:
            raise InternalInvariantError("an installation act takes the one secret its contract declares")
        self._secret_received = True
        self.require_login()
        write_document(
            self._channel,
            RuntimeSecretReady(
                request_id=self._request.request_id,
                runtime_boot_id=self._owner.boot,
                connection_id=self._context.connection_id,
            ),
            deadline=time.monotonic() + _WRITE_SECONDS,
        )
        with read_secret(self._channel, deadline=time.monotonic() + _SECRET_READ_SECONDS) as secret:
            return decode_document(bytes(secret), document)

    def deliver_secret(self, secret: bytearray) -> SecretBytes:
        """Deliver the act's one outbound secret and return what the client read back.

        ``secret`` is consumed and wiped. The client holds the secret wherever
        it keeps such things, then returns its own copy in a secret frame. The
        caller compares that copy with the original before it settles the act,
        so nothing is committed under a secret nobody holds. A client that
        declines is refused with the code it gave.
        """
        try:
            if not self._contract.delivers_secret or self._secret_delivered:
                raise InternalInvariantError("an installation act delivers the one secret its contract declares")
            self._secret_delivered = True
            self.require_login()
            delivery = RuntimeInstallationSecretDelivery(
                request_id=self._request.request_id,
                runtime_boot_id=self._owner.boot,
                connection_id=self._context.connection_id,
                act=self.act,
                delivery_id=uuid4(),
            )
            write_document(self._channel, delivery, deadline=time.monotonic() + _WRITE_SECONDS)
            write_secret(self._channel, secret, deadline=time.monotonic() + _WRITE_SECONDS)
        finally:
            secret[:] = bytes(len(secret))
        with self._lifecycle.suspended():
            receipt = read_document(
                self._channel,
                RuntimeInstallationSecretReceipt,
                deadline=time.monotonic() + INSTALLATION_SECRET_HANDOVER_SECONDS,
            )
        if receipt.delivery_id != delivery.delivery_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if receipt.code is not None:
            raise AutomationCustodyError(receipt.code)
        self.require_login()
        with read_secret(self._channel, deadline=time.monotonic() + _SECRET_READ_SECONDS) as held:
            return SecretBytes(bytes(held))

    @contextmanager
    def reserve_profiles(self, profile_ids: Iterable[UUID]) -> Generator[InstallationProfileReservation]:
        """Fence the named profiles against admission and other custody changes.

        A profile another custody change already holds refuses the act. While
        the reservation is held no connection is admitted to those profiles.
        """
        reserved = frozenset(profile_ids)
        with self._owner._guard:
            if reserved & self._owner._custody_mutations:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            self._owner._custody_mutations.update(reserved)
        try:
            yield InstallationProfileReservation(self._owner, reserved)
        finally:
            with self._owner._guard:
                self._owner._custody_mutations.difference_update(reserved)

    def hosted_profile_ids(self) -> tuple[UUID, ...]:
        """Name the profiles this runtime is hosting now."""
        with self._owner._guard:
            return tuple(self._owner._profiles)


class RuntimeInstallationDoorMixin:
    """Admit, dispatch and settle installation acts for the profile connection service."""

    def installation(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeInstallationActRequest,
    ) -> None:
        """Serve one act, taking the lifecycle exclusion first when it changes records."""
        if self._refused_as_persons_act(context, channel, request_id=request.request_id, frontend=request.frontend):
            return
        lifecycle = _LifecycleHold(self, held=False)
        if installation_request_facts(request).changes_records:
            lifecycle.held = self._drain_guard.acquire_delete()
            if not lifecycle.held:
                write_document(
                    channel,
                    RuntimeAccessRefusal(
                        request_id=request.request_id,
                        runtime_boot_id=self.boot,
                        connection_id=context.connection_id,
                        code=AutomationCustodyCode.CONFLICT,
                    ),
                    deadline=time.monotonic() + _WRITE_SECONDS,
                )
                return
        try:
            result = self._settle_installation_act(context, channel, request, lifecycle)
        finally:
            lifecycle.release()
        try:
            payload = installation_reply_payload(result)
        except ValueError:
            result = self._installation_failure(context, request, installation_act_of(request))
            payload = installation_reply_payload(result)
        write_installation_reply(channel, result, payload, deadline=time.monotonic() + _REPLY_WRITE_SECONDS)

    def _settle_installation_act(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeInstallationActRequest,
        lifecycle: _LifecycleHold,
    ) -> InstallationSettledReply:
        act = installation_act_of(request)
        contract = INSTALLATION_ACT_CONTRACTS[act]
        exchange: InstallationActExchange | None = None
        try:
            if context.runtime_boot_id != self.boot or context.peer != channel.peer:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            login = self._installation_login(context, channel)
            exchange = InstallationActExchange(
                self,
                context=context,
                channel=channel,
                request=request,
                contract=contract,
                login=login,
                lifecycle=lifecycle,
            )
            exchange.require_login()
            with self._guard:
                self._logins[login.login_id] = login
            handler = self._installation_registry().handler_for(request)
            if handler is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            # An idle stop must not cut an admitted act: it holds the same
            # count a submitted operation holds until its reply is decided.
            with self.operation_admission():
                reply = handler(request, exchange)
            if type(reply) is not contract.reply or (reply.request_id, reply.runtime_boot_id, reply.connection_id) != (
                request.request_id,
                self.boot,
                context.connection_id,
            ):
                raise InternalInvariantError("an installation handler returned another act's reply")
            if lifecycle.held and not exchange.changes_began:
                # A handler cannot leave the mark out: without it a refusal
                # raised after its change would be read as nothing changed.
                raise InternalInvariantError("an installation handler changed records without saying where it began")
            return reply
        except (AutomationCustodyError, RuntimeRefusalError, ProfileAccessRefusedError) as error:
            if exchange is not None and exchange.changes_began:
                # The refusal no longer proves that nothing changed, which is what a refusal tells a caller.
                return self._installation_failure(context, request, act, error)
            return RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=error.reason,
            )
        except InternalInvariantError as error:
            # A broken invariant is a fault to diagnose here, not a refusal the caller could act on.
            return self._installation_failure(context, request, act, error)
        except (CadrumoError, ValidationError) as error:
            detail = build_operation_error_detail(error)
            if detail is None:
                return self._installation_failure(context, request, act, error)
            return RuntimeInstallationRefused(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                act=act,
                detail=detail,
            )
        except Exception as error:
            # One act's fault must not end the runtime that hosts every other
            # profile's work. The fault is logged by type and origin only.
            return self._installation_failure(context, request, act, error)

    def _installation_failure(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        request: RuntimeInstallationActRequest,
        act: InstallationAct,
        error: BaseException | None = None,
    ) -> RuntimeInstallationFailed:
        diagnostic_event(
            _LOGGER,
            "installation act failed",
            level=logging.ERROR,
            fields={
                "act": act.value,
                "frontend": request.frontend.value,
                "reason_code": "reply_too_large" if error is None else "unexpected_failure",
                **({} if error is None else diagnostic_error_fields(error)),
            },
        )
        return RuntimeInstallationFailed(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            act=act,
        )

    def _installation_login(
        self: RuntimeProfileConnections, context: RuntimeConnectionContext, channel: RuntimeByteChannel
    ) -> RuntimeLoginEvidence:
        """Return this connection's native login, reusing the incarnation already captured for it."""
        with self._guard:
            admitted = self._connections.get(context.connection_id)
            noticed = self._notice_connections.get(context.connection_id)
        if admitted is not None and admitted.context == context:
            return admitted.login
        if noticed is not None and noticed[0] == context:
            return noticed[1]
        return self._capture(channel)

    def _installation_registry(self: RuntimeProfileConnections) -> InstallationActRegistry:
        with self._guard:
            registry = self._installation_acts
            if registry is None:
                from .installation_composition import production_installation_acts

                registry = production_installation_acts()
                self._installation_acts = registry
            return registry
