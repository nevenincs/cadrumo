"""One MCP connection's runtime adapter, admitted by held-person attendance or a configured key."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from threading import Event
from typing import Any, TypeVar
from uuid import UUID

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operator_output.connection_remedies import connection_unavailable_remedy
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.core.async_cleanup import (
    AsyncCloseable,
    AsyncResourceCleanupError,
    await_cancellation_complete,
    close_async_resources,
)
from cadrumo_client.contracts.profile_access import PROFILE_ADMISSION_TIMEOUT_SECONDS, ProfileStatus
from cadrumo_client.transport.credentials import open_installed_credential_client
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installed_client import open_installed_client

from .access_scope import surface_scope
from .admitted_operations import call_admitted_operation
from .authority_query import authority_query
from .corpus_query import corpus_query
from .lifecycle_notices import LifecycleNoticeBoard
from .operation_contract_cache import OperationContractCache
from .protocol_contract import (
    MCP_TOOL_NAMES,
    PERSON_ACT_REMEDY,
    public_value,
    refusal_code,
    refusal_facts,
    sign_in_remedy,
    validate_tool_arguments,
)
from .runtime_admission import (
    AdmissionDenial,
    McpAdmission,
    attend_held_sign_in,
    require_exact_admitted_status,
    selected_profile_id,
)
from .runtime_cleanup import (
    RuntimeAdmissionCleanup,
    RuntimeClientCleanup,
    cleanup_sources,
    preserve_cancellation_body_error,
    retain_cleanup_failure,
)
from .surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, McpSurface

WireResultT = TypeVar("WireResultT")


_SESSION_ENDED = frozenset(
    {
        AccessDenialCode.AUTHENTICATION_REQUIRED.value,
        AccessDenialCode.SESSION_INACTIVE.value,
        AccessDenialCode.SESSION_EXPIRED.value,
        AccessDenialCode.CONNECTION_MISMATCH.value,
    }
)
"""The refusals by which the runtime says the session a connection holds no longer admits anything."""


class RuntimeMcpAdapter:
    """One MCP connection owns one attended lease or a lease admitted by a configured key.

    It offers no way to sign in, to name or request a credential, or to act
    outside its profile: those are the person's acts in Cadrumo.
    """

    def __init__(
        self,
        *,
        profile_id: UUID | None,
        client: FrontendClient | None,
        surface: McpSurface = MCP_SURFACES[DEFAULT_MCP_SURFACE],
        requests_attendance: bool = False,
    ) -> None:
        """Bind a protocol connection to its profile rule, its surface and an optional lease.

        Without ``requests_attendance``, only the configured enrolled key can
        admit the named profile. With it, a call needing the profile requests
        scoped attendance from its held human session. The exact human decision
        admits this connection under that parent's finite lifetime. No person
        receipt or password is presented by this external client.

        A named profile is served only while selected. An unnamed connection
        binds to the first profile that attends it; later selection cannot move
        its authority to another profile. The protocol surface projects a finite
        operation/action ceiling into every runtime admission.
        """
        if requests_attendance and client is not None:
            raise ValueError("a connection requesting attendance starts with no lease")
        if not requests_attendance and profile_id is None:
            raise ValueError("a connection that serves only an enrolled key names its profile")
        if client is not None and (
            client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.EXTERNAL_CLIENT
        ):
            raise FrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        self.profile_id: UUID | None = profile_id
        self.client = client
        self.admission: McpAdmission | None = None if client is None else McpAdmission.KEY
        self.surface = surface
        self._requests_attendance = requests_attendance
        self._named_profile_id = profile_id
        self._retired = Event()
        self._lock = asyncio.Lock()
        self._admission_denial: AdmissionDenial | None = None
        self._contracts = OperationContractCache()
        self._retiring_resources: dict[int, AsyncCloseable] = {}
        self._notices = LifecycleNoticeBoard()
        self._key_reference: UUID | None = None

    async def bootstrap_reference(self, credential_reference: UUID) -> None:
        """Authenticate with the key the person configured at launch, keeping a refusal as this connection's denial.

        The reference comes from the launch configuration and from nowhere
        else: no tool takes one. A refused key leaves the server answering
        its tool list and ``status`` with that refusal, and every later call
        asks the runtime again with the same key, as each command does.
        """
        self._key_reference = credential_reference
        async with self._lock:
            try:
                await self._authenticate_key(credential_reference, await self._bound_profile())
            except Exception as error:
                self._admission_denial = AdmissionDenial.of(error)

    def _retirement(self, client: FrontendClient) -> AsyncCloseable:
        identity = id(client)
        owner = self._retiring_resources.get(identity)
        if owner is None:

            def released() -> None:
                self._retiring_resources.pop(identity, None)

            owner = RuntimeClientCleanup(client, on_closed=released)
            self._retiring_resources[identity] = owner
        return owner

    def _retain_admission_cleanup(self, error: BaseException) -> None:
        """Own native resources retained by an opener that returned no client."""
        for name in ("async_cleanup_error", "cleanup_error"):
            failure = error.__dict__.get(name)
            if isinstance(failure, AsyncResourceCleanupError):
                identity = id(failure)
                if identity not in self._retiring_resources:

                    def released(identity: int = identity) -> None:
                        self._retiring_resources.pop(identity, None)

                    self._retiring_resources[identity] = RuntimeAdmissionCleanup(failure, on_closed=released)

    async def _open_reference_client(self, reference: UUID, *, profile_id: UUID) -> FrontendClient:
        try:
            return await open_installed_credential_client(
                profile_id=profile_id,
                credential_reference=reference,
                frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
                timeout=PROFILE_ADMISSION_TIMEOUT_SECONDS,
                scope=surface_scope(self.surface),
            )
        except BaseException as error:
            self._retain_admission_cleanup(error)
            raise

    async def _bound_profile(self) -> UUID:
        """Return the profile this connection acts for, following the selection only until it is bound.

        Until attendance first admits the connection the selection is read at every call,
        as each command reads it, and with no profile selected nothing is
        held. Once attendance admits it the connection is bound to its profile.
        """
        if self._named_profile_id is not None:
            return self._named_profile_id
        try:
            profile_id = await self._wire(lambda: selected_profile_id(expected=None))
        except Exception:
            await self._release_profile_state(task_name="mcp-unselected-profile-close")
            self.profile_id = None
            raise
        if profile_id != self.profile_id:
            await self._release_profile_state(task_name="mcp-reselected-profile-close")
            self.profile_id = profile_id
        return profile_id

    async def _require_selected(self, profile_id: UUID) -> None:
        """Retain attended authority for a named profile only while it is selected.

        Attendance is requested for the selected profile only. Moving the
        selection releases the earlier attended lease. Key leases are not
        subject to this selection rule.
        """
        if self._named_profile_id is None or self.admission is McpAdmission.KEY:
            return
        try:
            await self._wire(lambda: selected_profile_id(expected=profile_id))
        except Exception:
            await self._release_lease(task_name="mcp-unselected-profile-close")
            raise

    async def _release_profile_state(self, *, task_name: str) -> None:
        """Close every connection held for the bound profile and forget what it remembered."""
        held = tuple(item for item in (self.client,) if item is not None)
        self.client = None
        self.admission = None
        self._contracts.clear()
        for item in held:
            self._notices.released(id(item))
        if held:
            await close_async_resources(*(self._retirement(item) for item in held), task_name=task_name)

    async def _release_lease(self, *, task_name: str) -> None:
        """Close the admitted connection and forget the contracts remembered for its session."""
        client, self.client = self.client, None
        self.admission = None
        self._contracts.clear()
        if client is not None:
            await self._retire_client(client, task_name=task_name)

    def _watch(self, client: FrontendClient) -> Event:
        """Have what the runtime tells this connection reach the next call.

        Its notice that the lease was retired sets a flag, and its lifecycle
        notice is kept for the next tool result. Both arrive on the
        connection's own thread, so nothing waits on either: the next call
        that needs the profile drops a retired lease and asks the runtime once
        to admit the connection again.
        """
        retired = Event()
        client.subscribe_session_retirement(retired.set)
        owner = id(client)
        client.subscribe_lifecycle_notices(lambda notice: self._notices.receive(owner, notice))
        return retired

    async def _restore_key_session(self) -> None:
        """Authenticate a key session anew when the one held is retired, lost, or was refused.

        A healthy connection retains its key session. Each call checks its
        current status and grant; authentication with the launch reference is
        repeated only after refusal, connection loss or session retirement.

        - A key session that is retired, or whose connection is lost, is let
          go and authenticated anew with the stored reference, at most once
          per call and never in a loop.
        - When the runtime refuses, its refusal code (revoked, locked,
          expired, profile mismatch and so on) is the denial the call answers
          with, and no session is held. The next call asks the runtime again.
        - When the runtime admits it, the call proceeds under the new session.
        """
        reference = self._key_reference
        if reference is None:
            return
        if self.client is not None:
            if not self._retired.is_set():
                return
            await self._release_lease(task_name="mcp-retired-key-session-close")
        try:
            await self._authenticate_key(reference, await self._bound_profile())
        except Exception as error:
            self._admission_denial = AdmissionDenial.of(error)

    async def _hold_session(self) -> None:
        """Hold a session for the bound profile, requesting scoped attendance under exact held-human approval.

        The runtime decides. Its refusal is kept as this connection's denial
        and no lease is held, so the call that follows answers with it.
        """
        try:
            profile_id = await self._bound_profile()
            if self.client is not None and self._retired.is_set() and not await self._renew_attendance(profile_id):
                await self._release_lease(task_name="mcp-retired-session-close")
            await self._require_selected(profile_id)
            if self.client is None:
                self.client, self._retired, self.admission = await self._open_attended_client(profile_id)
                # Bound for its life to the profile of its held-human attendance approval.
                self._named_profile_id = profile_id
        except Exception as error:
            self._admission_denial = AdmissionDenial.of(error)
            return
        self._admission_denial = None

    async def _renew_attendance(self, profile_id: UUID) -> bool:
        """Renew an attended lease that ended, on the connection the person approved, and say whether it was.

        The person approved this exact connection under their session. While
        that session lives the runtime issues it a new child without a new
        decision; once it has ended the runtime refuses, and the connection is
        let go like any other whose session ended.
        """
        client = self.client
        if client is None or self.admission is not McpAdmission.ATTENDED:
            return False

        def renew() -> Event:
            if not isinstance(client.request_attendance(), ProfileStatus):
                # Only a fresh ask waits for a decision; this connection's approval did not carry.
                raise FrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value)
            require_exact_admitted_status(client, profile_id=profile_id, admission=McpAdmission.ATTENDED)
            return self._watch(client)

        try:
            self._retired = await self._wire(renew)
        except Exception:
            return False
        return True

    async def _open_attended_client(self, profile_id: UUID) -> tuple[FrontendClient, Event, McpAdmission]:
        """Ask the person holding the exact profile to approve this scoped external connection."""
        attended = await self._open_unadmitted_client(profile_id, on_surface=True)

        def attend() -> Event:
            attend_held_sign_in(attended, profile_id=profile_id)
            return self._watch(attended)

        try:
            return attended, await self._wire(attend), McpAdmission.ATTENDED
        except BaseException as error:
            await self._retire_client(attended, task_name="mcp-attendance-close", primary_error=error)
            raise

    async def _retire_client(
        self,
        client: FrontendClient,
        *,
        task_name: str,
        primary_error: BaseException | None = None,
    ) -> None:
        self._notices.released(id(client))
        await close_async_resources(self._retirement(client), task_name=task_name, primary_error=primary_error)

    async def _release_owned_clients(self, primary_error: BaseException | None) -> None:
        async with self._lock:
            if self.client is not None:
                self._retirement(self.client)
            owners = tuple(self._retiring_resources.values())
            self.client = None
            self.admission = None
            self._contracts.clear()
            await close_async_resources(*owners, task_name="mcp-runtime-clients-close", primary_error=primary_error)

    async def _settle_release(self, primary_error: BaseException | None, failures: list[BaseException]) -> None:
        # A terminal cancellation is an outcome of retained release, not a new cancellation.
        try:
            await self._release_owned_clients(primary_error)
        except BaseException as error:
            failures.append(error)

    async def close(self) -> None:
        """Release only this adapter's connection."""
        primary_error = sys.exception()
        failures: list[BaseException] = []
        diagnostics: dict[int, BaseException] = {}
        if primary_error is not None:
            retain_cleanup_failure(primary_error, (), diagnostics, capture_only=True)
        try:
            await await_cancellation_complete(
                self._settle_release(primary_error, failures), task_name="mcp-runtime-close"
            )
        except asyncio.CancelledError as cancellation:
            sources = cleanup_sources(failures, primary_error)
            retain_cleanup_failure(cancellation, sources, diagnostics)
            preserve_cancellation_body_error(cancellation, sources, primary_error)
            raise
        if primary_error is not None and not isinstance(primary_error, AsyncResourceCleanupError):
            retain_cleanup_failure(primary_error, (), diagnostics)
        if failures:
            raise failures[0]

    def _admitted(self) -> FrontendClient:
        if self.client is None:
            raise (self._admission_denial or AdmissionDenial(AccessDenialCode.AUTHENTICATION_REQUIRED.value)).refusal()
        return self.client

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Serialize all blocking wire calls; cancellation waits for cleanup."""
        if name not in MCP_TOOL_NAMES or name not in self.surface.tools:
            return {"outcome": "refused", "code": "unknown_tool"}
        async with self._lock:
            reply = await self._answer(name, args)
            self._notices.annotate(name, reply)
            return reply

    async def _answer(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Serve one tool call, turning every failure into its stable refusal.

        ``status`` answers whatever holds; every other tool needs a session
        the person's live sign-in or configured key admitted, and without one
        it is refused with the remedy that sends the agent to the person.
        """
        try:
            validate_tool_arguments(name, args)
            await self._hold_or_restore_session()
            if name != "status":
                self._admitted()
            if name == "authority":
                return await self._wire(lambda: authority_query(args))
            if name == "corpus_search":
                return await self._wire(lambda: corpus_query(args))
            return await self._wire(lambda: call_admitted_operation(self, name, args))
        except Exception as error:
            code = refusal_code(error)
            # A sign-in refusal keeps its reason, binding and wait, as the command line reports them.
            reply: dict[str, Any] = {"outcome": "refused", "code": code, **refusal_facts(error)}
            if isinstance(error, FrontendRefusedError) and error.request_faults:
                # The runtime said why, in a registered error's code and message; every tool passes that on.
                reply["faults"] = [public_value(fault) for fault in error.request_faults]
            if self.client is not None and code in _SESSION_ENDED:
                if self.admission is McpAdmission.ATTENDED:
                    # An attended lease is short; the next call asks again on this approved connection.
                    self._retired.set()
                else:
                    # The runtime has ended the held session, whether or not its notice has arrived yet: let it
                    # go, so this answer sends the agent to the person and the next call asks the runtime again.
                    await self._release_lease(task_name="mcp-ended-session-close")
            if code == AccessDenialCode.PERSON_ACT_REQUIRED.value:
                # The runtime refused the person's own act; the agent is told to ask the person.
                reply["remedy"] = PERSON_ACT_REMEDY
            elif (remedy := connection_unavailable_remedy(code)) is not None and remedy:
                reply["remedy"] = remedy
            elif self.client is None and (told := sign_in_remedy(code, reply)) is not None:
                # Nothing admits this server: no live sign-in and no configured key.
                reply["remedy"] = told
            return reply

    async def _hold_or_restore_session(self) -> None:
        if self._requests_attendance:
            await self._hold_session()
        else:
            await self._restore_key_session()

    async def _open_unadmitted_client(self, profile_id: UUID, *, on_surface: bool = False) -> FrontendClient:
        """Open a connection for one profile that holds no session yet."""
        try:
            return await open_installed_client(
                profile_id=profile_id,
                frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
                scope=surface_scope(self.surface) if on_surface else None,
            )
        except BaseException as error:
            self._retain_admission_cleanup(error)
            raise

    async def _replace_lease(self, client: FrontendClient, retired: Event, admission: McpAdmission) -> None:
        """Hold a newly admitted connection and let go of the one it replaces."""
        old_client = self.client
        self.client, self._retired = client, retired
        self.admission = admission
        self._contracts.clear()
        self._admission_denial = None
        if old_client is not None:
            await self._retire_client(old_client, task_name="mcp-reauth-close")

    async def _wire(self, function: Callable[[], WireResultT]) -> WireResultT:
        return await await_cancellation_complete(asyncio.to_thread(function), task_name="mcp-runtime-call")

    async def _authenticate_key(self, credential_reference: UUID, profile_id: UUID) -> None:
        """Hold a session admitted by the key configured at launch, under the grant the person approved for it."""
        client = await self._open_reference_client(credential_reference, profile_id=profile_id)

        def admit() -> Event:
            require_exact_admitted_status(client, profile_id=profile_id)
            return self._watch(client)

        try:
            retired = await self._wire(admit)
        except BaseException as error:
            await self._retire_client(client, task_name="mcp-admission-close", primary_error=error)
            raise
        self._key_reference = credential_reference
        await self._replace_lease(client, retired, McpAdmission.KEY)
