"""Sessionless installation acts over one native-verified runtime connection.

This client needs no profile and holds no session. It sends one act, carries
the act's secret frames when the act has them, and returns the act's reply. It
never starts, stops or supervises the runtime: an absent runtime is a typed
refusal.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import NoReturn, Self

from pydantic import SecretBytes

from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, close_async_resources
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.paths import effective_storage_root
from cadrumo.domain.calculations.registry.authority_location import published_authority_generation

from ..contracts.contracts import ClientHello, EndpointPresence, RefusalCode, RefusalError
from ..contracts.deadline_budget import deadline_after
from ..contracts.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    INSTALLATION_SECRET_HANDOVER_SECONDS,
    InstallationActRequest,
    InstallationCompleted,
    InstallationFailed,
    InstallationRefused,
    InstallationReplyTransfer,
    InstallationSecretDelivery,
    InstallationSecretReceipt,
    installation_act_of,
)
from ..contracts.profile_access import AccessRefusal, SecretReady
from .frame_io import read_secret, write_document
from .framing import VerifiedConnection
from .frontend_client_contracts import FrontendRefusedError
from .installation_frame_io import read_installation_reply
from .posix_endpoint import PosixEndpoint
from .startup import LaunchDoor
from .transport_cleanup import TransportCleanup
from .verified_transport import HeldExchange
from .windows import WindowsEndpoint

type InstallationSecretHolder = Callable[[bytearray], SecretBytes | None]
"""Hold one delivered secret and return the copy read back from where it was put.

The buffer is wiped when the holder returns. ``None`` declines the secret, and
the act then settles without committing anything that depended on it.
"""


def installation_passphrase_document(passphrase: bytearray) -> bytearray:
    """Build the one secret frame of an act that proves a profile passphrase.

    ``passphrase`` is consumed and wiped. The returned buffer is consumed by
    :meth:`InstallationClient.perform`.
    """
    try:
        return bytearray(canonical_json_bytes({"passphrase": passphrase.decode("utf-8")}))
    finally:
        passphrase[:] = bytes(len(passphrase))


class InstallationClient:
    """Own one verified connection for acts that name no profile session.

    Blocking wire methods should be called off a UI event loop.
    """

    def __init__(self, connection: VerifiedConnection) -> None:
        """Bind one verified connection; nothing is sent until an act is performed."""
        self._connection = connection

    @classmethod
    async def open(cls, launch: LaunchDoor, *, timeout: float = 10) -> Self:
        """Use the canonical owner-verified launch door before any act."""
        return cls(await launch.open(timeout=timeout))

    def __enter__(self) -> Self:
        """Retain this owned connection for a synchronous scope."""
        return self

    def __exit__(self, *_exc: object) -> None:
        """Close this client's owned connection."""
        self.close()

    async def __aenter__(self) -> Self:
        """Retain this owned connection for an asynchronous scope."""
        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Close this client's owned connection."""
        await await_cancellation_complete(asyncio.to_thread(self.close), task_name="installation-runtime-close")

    def close(self) -> None:
        """End this connection without stopping the shared runtime."""
        self._connection.close()

    def cleanup_owner(self, *, primary_error: BaseException | None) -> TransportCleanup:
        """Retain one owner for this exact connection's release."""
        retained = None if primary_error is None else primary_error.__dict__.get("_transport_cleanup")
        if isinstance(retained, TransportCleanup) and (
            retained.resource is self or retained.resource is self._connection
        ):
            retained.resource = self
            return retained
        return TransportCleanup(self)

    def perform[ReplyT: InstallationCompleted](
        self,
        request: InstallationActRequest,
        reply_type: type[ReplyT],
        *,
        secret: bytearray | None = None,
        hold_secret: InstallationSecretHolder | None = None,
        timeout: float | None = None,
    ) -> ReplyT | InstallationRefused | InstallationFailed:
        """Send one act and return how it settled.

        Args:
            request: The act's request.
            reply_type: The reply the act's contract declares for it.
            secret: The act's one secret frame, for an act that takes one. It
                is consumed and wiped, and is sent only after the runtime says
                it is ready.
            hold_secret: Receives the act's delivered secret, for an act that
                delivers one, and returns the copy read back.
            timeout: Seconds for the whole exchange. Omitted, the act's own
                deadline from the contract table applies, plus the handover
                bound for an act that delivers a secret. A client that stops
                waiting does not learn how an act that changes records
                settled: the contract's ``outcome_read_by`` names the act that
                reads it.

        Returns:
            The act's completed reply, or the typed refusal or failure its
            handler settled with.

        Raises:
            FrontendRefusedError: The host refused admission.
            RefusalError: The transport refused, or a frame broke the act's contract.
        """
        try:
            contract = INSTALLATION_ACT_CONTRACTS[installation_act_of(request)]
            if (
                contract.reply is not reply_type
                or contract.takes_secret != (secret is not None)
                or contract.delivers_secret != (hold_secret is not None)
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            if timeout is None:
                timeout = contract.deadline_seconds + (
                    INSTALLATION_SECRET_HANDOVER_SECONDS if contract.delivers_secret else 0
                )
            reply = _exchange_act(
                self._connection, request, secret=secret, hold_secret=hold_secret, deadline=deadline_after(timeout)
            )
            if isinstance(reply, AccessRefusal):
                _raise_wire_refusal(reply)
            if isinstance(reply, InstallationRefused | InstallationFailed):
                if reply.act is not contract.act:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            if not isinstance(reply, reply_type):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            return reply
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))


def _raise_wire_refusal(reply: AccessRefusal) -> NoReturn:
    """Keep runtime failure provenance distinct from an authoritative access denial."""
    if isinstance(reply.code, RefusalCode):
        raise RefusalError(reply.code)
    raise FrontendRefusedError(reply.code.value, sign_in=reply.sign_in)


def _exchange_act(
    connection: VerifiedConnection,
    request: InstallationActRequest,
    *,
    secret: bytearray | None,
    hold_secret: InstallationSecretHolder | None,
    deadline: float,
) -> object:
    """Hold one correlated exchange until the act settles, serving its secret frames in between.

    The connection holds the exchange, so this act cannot interleave with
    another request on the same connection and a failed frame closes the
    connection exactly as any other exchange does.
    """
    act = installation_act_of(request)
    with connection.held_exchange(request, request.request_id, deadline=deadline, secret=secret) as exchange:
        secret_sent = secret_held = False
        while True:
            received = exchange.reply().root
            if isinstance(received, SecretReady):
                if secret is None or secret_sent:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                secret_sent = True
                exchange.send_secret(secret)
            elif isinstance(received, InstallationSecretDelivery):
                if hold_secret is None or secret_held or received.act is not act:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                secret_held = True
                _hold_delivered_secret(exchange, received, hold_secret, deadline=deadline)
            elif isinstance(received, InstallationReplyTransfer):
                return read_installation_reply(exchange.channel, received, deadline=deadline).root
            else:
                return received


def _hold_delivered_secret(
    exchange: HeldExchange,
    delivery: InstallationSecretDelivery,
    hold_secret: InstallationSecretHolder,
    *,
    deadline: float,
) -> None:
    """Receive one delivered secret, let the holder keep it, and return the copy read back."""
    with read_secret(exchange.channel, deadline=deadline) as delivered:
        try:
            held = hold_secret(delivered)
            code = None if held is not None else AutomationCustodyCode.MISSING
        except AutomationCustodyError as error:
            held, code = None, error.reason
    write_document(
        exchange.channel,
        InstallationSecretReceipt(
            delivery_id=delivery.delivery_id, outcome="held" if held is not None else "refused", code=code
        ),
        deadline=deadline,
    )
    if held is not None:
        exchange.send_secret(bytearray(held.get_secret_value()))


class _OwnedRelease:
    """Retain a blocking native release until it succeeds, off the caller's event loop."""

    def __init__(self, close: Callable[[], None]) -> None:
        self._close = close
        self._released = False

    async def close(self) -> None:
        if not self._released:
            await asyncio.to_thread(self._close)
            self._released = True


def _installed_endpoint(root: Path) -> WindowsEndpoint | PosixEndpoint:
    """Name the native endpoint that owns ``root``."""
    return WindowsEndpoint(storage_root=root) if sys.platform == "win32" else PosixEndpoint(storage_root=root)


async def installed_connection_presence() -> EndpointPresence:
    """Observe whether a local service endpoint owns the effective storage root, without opening a connection to use.

    Only ``ABSENT`` proves that none does. A refusal to connect does not: an
    endpoint whose owner is busy, a wait that ran out and a client that cannot
    name its own cohort all refuse with one code while a service is alive. A
    caller that would perform a service operation itself asks this first.
    """
    try:
        root = effective_storage_root().resolve(strict=True)
    except FileNotFoundError:
        # An endpoint is named by its root's identity, so a root that does not exist has none.
        return EndpointPresence.ABSENT
    except OSError:
        return EndpointPresence.INDETERMINATE
    try:
        endpoint = _installed_endpoint(root)
    except RefusalError:
        return EndpointPresence.INDETERMINATE
    endpoint_release = _OwnedRelease(endpoint.close)
    try:
        observed = await asyncio.to_thread(endpoint.presence)
    except BaseException as error:
        await close_async_resources(
            endpoint_release, task_name="installation-connection-presence-close", primary_error=error
        )
        raise
    await close_async_resources(
        endpoint_release, task_name="installation-connection-presence-close", primary_error=None
    )
    return observed


async def open_installed_installation_client(*, timeout: float = 10) -> InstallationClient:
    """Connect to the running owner of the effective storage root.

    This opens no profile and reads no credential. An absent or untrusted
    endpoint returns a typed refusal; nothing here starts a service. The
    refusal does not say that no runtime is running:
    :func:`installed_connection_presence` answers that.
    """
    try:
        root = effective_storage_root().resolve(strict=True)
        product_version = version("cadrumo")
    except (OSError, PackageNotFoundError):
        raise RefusalError(RefusalCode.UNAVAILABLE) from None
    endpoint = _installed_endpoint(root)
    endpoint_release = _OwnedRelease(endpoint.close)
    try:
        launch = LaunchDoor(
            endpoint,
            expected=ClientHello(
                product_version=product_version,
                storage_identity=endpoint.storage_identity,
                authority_generation=published_authority_generation(),
            ),
        )
        client = await InstallationClient.open(launch, timeout=timeout)
    except BaseException as error:
        await close_async_resources(
            endpoint_release, task_name="installation-runtime-endpoint-close", primary_error=error
        )
        raise
    try:
        await close_async_resources(
            endpoint_release, task_name="installation-runtime-endpoint-close", primary_error=None
        )
    except AsyncResourceCleanupError as error:
        refusal = RefusalError(RefusalCode.UNAVAILABLE)
        refusal.__dict__["async_cleanup_error"] = error
        await close_async_resources(
            _OwnedRelease(client.close), task_name="installation-runtime-client-close", primary_error=refusal
        )
        raise refusal from error
    except BaseException as error:
        await close_async_resources(
            _OwnedRelease(client.close), task_name="installation-runtime-client-close", primary_error=error
        )
        raise
    return client
