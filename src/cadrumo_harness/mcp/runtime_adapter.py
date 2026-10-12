"""One MCP connection's runtime adapter, admitted by the person's sign-in or a configured key."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from threading import Event
from typing import Any, TypeVar
from uuid import UUID

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.application.operations.mcp_surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, McpSurface
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operator_output.runtime_remedies import runtime_unavailable_remedy
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.runtime.profile_access import PROFILE_ADMISSION_TIMEOUT_SECONDS
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.core.async_cleanup import (
    AsyncCloseable,
    AsyncResourceCleanupError,
    await_cancellation_complete,
    close_async_resources,
)

from .admitted_operations import call_admitted_operation
from .authority_query import authority_query
from .corpus_query import corpus_query
from .lifecycle_notices import LifecycleNoticeBoard
from .operation_contract_cache import OperationContractCache
from .protocol_contract import (
    MCP_TOOL_NAMES,
    public_value,
    refusal_code,
    refusal_facts,
    validate_tool_arguments,
)
from .public_operation_discovery import SESSIONLESS_DISCOVERY_TOOLS, discover_public_operations
from .runtime_admission import (
    AdmissionDenial,
    McpAdmission,
    require_exact_admitted_status,
    resume_shared_sign_in,
    selected_profile_id,
)
from .runtime_cleanup import (
    RuntimeAdmissionCleanup,
    RuntimeClientCleanup,
    cleanup_sources,
    preserve_cancellation_body_error,
    retain_cleanup_failure,
)

WireResultT = TypeVar("WireResultT")


class RuntimeMcpAdapter:
    """One MCP connection owns one admitted lease, from the person's sign-in or a key the person configured.

    It offers no way to sign in, to name or request a credential, or to act
    outside its profile: those are the person's acts in Cadrumo.
    """

    def __init__(
        self,
        *,
        profile_id: UUID | None,
        client: RuntimeFrontendClient | None,
        surface: McpSurface = MCP_SURFACES[DEFAULT_MCP_SURFACE],
        resumes_sign_in: bool = False,
    ) -> None:
        """Bind a protocol connection to its profile rule, its surface and an optional lease.

        Without ``resumes_sign_in`` the connection serves an enrolled key:
        ``profile_id`` names its one immutable profile, and only a key admits
        it. With it the connection also asks the runtime to resume the
        person's sign-in whenever a call needs the profile and no session is
        held, and only for the installation's selected profile. A named
        ``profile_id`` still binds the connection, so the sign-in is resumed
        only while that profile is the selected one; with none named, the
        connection acts for whichever profile is selected at each call.

        The surface decides which tools answer and which operations search and
        describe reveal. That is a convenience: every admission this adapter
        opens names the surface to the runtime, which is what holds the
        connection to it.
        """
        if resumes_sign_in and client is not None:
            raise ValueError("a connection that resumes the sign-in starts with no lease")
        if not resumes_sign_in and profile_id is None:
            raise ValueError("a connection that serves only an enrolled key names its profile")
        if client is not None and (
            client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.MCP
        ):
            raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        self.profile_id: UUID | None = profile_id
        self.client = client
        self.admission: McpAdmission | None = None if client is None else McpAdmission.KEY
        self.surface = surface
        self._resumes_sign_in = resumes_sign_in
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

    def _retirement(self, client: RuntimeFrontendClient) -> AsyncCloseable:
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

    async def _open_reference_client(self, reference: UUID, *, profile_id: UUID) -> RuntimeFrontendClient:
        try:
            if self.surface.narrows:
                # A surface that narrows nothing is not named, so that
                # admission is opened exactly as it is without a surface.
                return await open_installed_credential_client(
                    profile_id=profile_id,
                    credential_reference=reference,
                    frontend=OperationFrontendProjection.MCP,
                    timeout=PROFILE_ADMISSION_TIMEOUT_SECONDS,
                    surface=self.surface.name,
                )
            return await open_installed_credential_client(
                profile_id=profile_id, credential_reference=reference, frontend=OperationFrontendProjection.MCP
            )
        except BaseException as error:
            self._retain_admission_cleanup(error)
            raise

    async def _bound_profile(self) -> UUID:
        """Return the profile this connection acts for, following the selection when none was named.

        The selection is then read at every call that needs the profile, as
        each command reads it. Whatever this connection holds for another
        profile is released before the new one is bound, and with no profile
        selected it holds nothing.
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
        """Let the person's sign-in serve a named profile only while it is the selected one.

        A sign-in is resumed for the profile the installation has selected and
        for no other, so a lease resumed earlier is released once the
        selection has moved on. A lease admitted by key is not held to this.
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

    def _watch(self, client: RuntimeFrontendClient) -> Event:
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

        The rule, which is the command line's: each command under a key
        authenticates anew with the reference that admitted it.

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
        """Hold a session for the bound profile, asking the runtime at most once to resume the sign-in.

        The runtime decides. Its refusal is kept as this connection's denial
        and no lease is held, so the call that follows answers with it.
        """
        try:
            profile_id = await self._bound_profile()
            if self.client is not None and self._retired.is_set():
                await self._release_lease(task_name="mcp-retired-session-close")
            await self._require_selected(profile_id)
            if self.client is None:
                self.client, self._retired = await self._open_signed_in_client(profile_id)
                self.admission = McpAdmission.SIGN_IN
        except Exception as error:
            self._admission_denial = AdmissionDenial.of(error)
            return
        self._admission_denial = None

    async def _open_signed_in_client(self, profile_id: UUID) -> tuple[RuntimeFrontendClient, Event]:
        client = await self._open_unadmitted_client(profile_id, on_surface=True)

        def resume() -> Event:
            resume_shared_sign_in(client, profile_id=profile_id)
            return self._watch(client)

        try:
            return client, await self._wire(resume)
        except BaseException as error:
            await self._retire_client(client, task_name="mcp-sign-in-resume-close", primary_error=error)
            raise

    async def _retire_client(
        self,
        client: RuntimeFrontendClient,
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

    def _admitted(self) -> RuntimeFrontendClient:
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
        """Serve one tool call, turning every failure into its stable refusal."""
        try:
            validate_tool_arguments(name, args)
            if name == "authority":
                return await self._wire(lambda: authority_query(args))
            if name == "corpus_search":
                return await self._wire(lambda: corpus_query(args))
            await self._hold_or_restore_session()
            if name in SESSIONLESS_DISCOVERY_TOOLS:
                return await self._wire(lambda: self._discover(name, args))
            return await self._wire(lambda: call_admitted_operation(self, name, args))
        except Exception as error:
            code = refusal_code(error)
            # A sign-in refusal keeps its reason, binding and wait, as the command line reports them.
            reply: dict[str, Any] = {"outcome": "refused", "code": code, **refusal_facts(error)}
            if isinstance(error, RuntimeFrontendRefusedError) and error.request_faults:
                # The runtime said why, in a registered error's code and message; every tool passes that on.
                reply["faults"] = [public_value(fault) for fault in error.request_faults]
            if remedy := runtime_unavailable_remedy(code):
                reply["remedy"] = remedy
            return reply

    def _discover(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Answer ``search`` or ``describe`` from the runtime under a live session, and without one all the same.

        With no session the answer is read from the contracts this package
        ships, so it needs neither a sign-in nor a running runtime. A lease the
        runtime no longer admits is no session, as ``status`` reports it, and a
        lease whose runtime is gone cannot be asked: both are answered from the
        shipped contracts too. A refusal under a live session stands, because it
        is that session's own: an operation outside its scope, say.
        """
        if self.client is not None:
            try:
                return call_admitted_operation(self, name, args)
            except (RuntimeFrontendRefusedError, RuntimeRefusalError):
                if self._session_is_live():
                    raise
        return discover_public_operations(name, args, self.surface)

    def _session_is_live(self) -> bool:
        """Say whether the runtime still admits the lease held, by the witness every admission is held to."""
        client, profile_id, admission = self.client, self.profile_id, self.admission
        if client is None or profile_id is None or admission is None:
            return False
        try:
            require_exact_admitted_status(client, profile_id=profile_id, admission=admission)
        except (RuntimeFrontendRefusedError, RuntimeRefusalError):
            return False
        return True

    async def _hold_or_restore_session(self) -> None:
        if self._resumes_sign_in:
            await self._hold_session()
        else:
            await self._restore_key_session()

    async def _open_unadmitted_client(self, profile_id: UUID, *, on_surface: bool = False) -> RuntimeFrontendClient:
        """Open a connection for one profile that holds no session yet."""
        try:
            if on_surface and self.surface.narrows:
                # Named as on the key route, so the runtime holds the lease to the same surface.
                return await open_installed_runtime_client(
                    profile_id=profile_id, frontend=OperationFrontendProjection.MCP, surface=self.surface.name
                )
            return await open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.MCP)
        except BaseException as error:
            self._retain_admission_cleanup(error)
            raise

    async def _replace_lease(self, client: RuntimeFrontendClient, retired: Event, admission: McpAdmission) -> None:
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
