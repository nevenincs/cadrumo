"""One MCP connection's authenticated runtime and enrollment adapter."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from threading import Event
from typing import Any, TypeVar
from uuid import UUID

from cadrumo.adapters.local_runtime.automation_requester import (
    AutomationRequesterJourney,
    AutomationRequesterUncertainError,
)
from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.operations.mcp_surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, McpSurface
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operator_output.runtime_remedies import runtime_unavailable_remedy
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import PROFILE_ADMISSION_TIMEOUT_SECONDS
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, ProfileAccessStatus
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentStage,
)
from cadrumo.core.async_cleanup import (
    AsyncCloseable,
    AsyncResourceCleanupError,
    await_cancellation_complete,
    close_async_resources,
)
from cadrumo.core.time.clock import now

from .admitted_operations import call_admitted_operation
from .authority_query import authority_query
from .corpus_query import corpus_query
from .operation_contract_cache import OperationContractCache
from .protocol_contract import (
    MCP_TOOL_NAMES,
    parse_model,
    public_value,
    refusal_code,
    validate_tool_arguments,
)
from .runtime_admission import (
    McpAdmission,
    require_exact_admitted_status,
    resume_shared_sign_in,
    selected_profile_id,
    status_on_surface,
)
from .runtime_cleanup import (
    RuntimeAdmissionCleanup,
    RuntimeClientCleanup,
    cleanup_sources,
    preserve_cancellation_body_error,
    retain_cleanup_failure,
)

_TIMEOUT = 30.0
_KEY_ROUTE_TOOLS = frozenset({"authorization_prepare", "authorization_request", "authorization_poll", "authenticate"})
WireResultT = TypeVar("WireResultT")


class RuntimeMcpAdapter:
    """One MCP connection owns one admitted lease and independent enrollment door."""

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
        self._enrollment_client: RuntimeFrontendClient | None = None
        self._enrollment: NativeEnrollmentClient | None = None
        self._enrollment_reference: UUID | None = None
        self._requester: AutomationRequesterJourney | None = None
        self._admission_denial: str | None = None
        self._contracts = OperationContractCache()
        self._retiring_resources: dict[int, AsyncCloseable] = {}

    async def bootstrap_reference(self, credential_reference: UUID) -> None:
        """Try the normal authentication door while keeping public MCP reachable."""
        result = await self.call("authenticate", {"credential_reference": str(credential_reference)})
        if result.get("outcome") == "authenticated":
            return
        code = result.get("code")
        self._admission_denial = code if isinstance(code, str) else "runtime_unavailable"

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

    async def _open_reference_client(
        self, reference: UUID, *, profile_id: UUID, timeout: float | None = None
    ) -> RuntimeFrontendClient:
        try:
            if self.surface.narrows:
                # A surface that narrows nothing is not named, so that
                # admission is opened exactly as it is without a surface.
                return await open_installed_credential_client(
                    profile_id=profile_id,
                    credential_reference=reference,
                    frontend=OperationFrontendProjection.MCP,
                    timeout=PROFILE_ADMISSION_TIMEOUT_SECONDS if timeout is None else timeout,
                    surface=self.surface.name,
                )
            if timeout is not None:
                return await open_installed_credential_client(
                    profile_id=profile_id,
                    credential_reference=reference,
                    frontend=OperationFrontendProjection.MCP,
                    timeout=timeout,
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
        held = tuple(item for item in (self._enrollment_client, self.client) if item is not None)
        self._enrollment_client = None
        self._enrollment = None
        self._enrollment_reference = None
        self._requester = None
        self.client = None
        self.admission = None
        self._contracts.clear()
        if held:
            await close_async_resources(*(self._retirement(item) for item in held), task_name=task_name)

    async def _release_lease(self, *, task_name: str) -> None:
        """Close the admitted connection and forget the contracts remembered for its session."""
        client, self.client = self.client, None
        self.admission = None
        self._contracts.clear()
        if client is not None:
            await self._retire_client(client, task_name=task_name)

    def _retirement_notice(self, client: RuntimeFrontendClient) -> Event:
        """Have the runtime's notice that this lease was retired mark it for the next call.

        The notice arrives on the connection's own thread, so it only sets a
        flag. Nothing waits on it: the next call that needs the profile drops
        the lease and asks the runtime once whether a sign-in can be resumed.
        A connection that serves an enrolled key keeps the lease it has.
        """
        retired = Event()
        if self._resumes_sign_in:
            client.subscribe_session_retirement(retired.set)
        return retired

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
            self._admission_denial = refusal_code(error)
            return
        self._admission_denial = None

    async def _open_signed_in_client(self, profile_id: UUID) -> tuple[RuntimeFrontendClient, Event]:
        try:
            if self.surface.narrows:
                # Named as on the key route, so the runtime holds the resumed lease to the same surface.
                client = await open_installed_runtime_client(
                    profile_id=profile_id, frontend=OperationFrontendProjection.MCP, surface=self.surface.name
                )
            else:
                client = await open_installed_runtime_client(
                    profile_id=profile_id, frontend=OperationFrontendProjection.MCP
                )
        except BaseException as error:
            self._retain_admission_cleanup(error)
            raise

        def resume() -> Event:
            resume_shared_sign_in(client, profile_id=profile_id)
            return self._retirement_notice(client)

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
        await close_async_resources(self._retirement(client), task_name=task_name, primary_error=primary_error)

    async def _release_owned_clients(self, primary_error: BaseException | None) -> None:
        async with self._lock:
            if self._enrollment_client is not None:
                self._retirement(self._enrollment_client)
            if self.client is not None:
                self._retirement(self.client)
            owners = tuple(self._retiring_resources.values())
            self._enrollment_client = None
            self._enrollment = None
            self._enrollment_reference = None
            self._requester = None
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
        """Release only this adapter's connection and pending enrollment."""
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
            raise RuntimeFrontendRefusedError(self._admission_denial or "authentication_required")
        return self.client

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Serialize all blocking wire calls; cancellation waits for cleanup."""
        if name not in MCP_TOOL_NAMES or name not in self.surface.tools:
            return {"outcome": "refused", "code": "unknown_tool"}
        async with self._lock:
            try:
                validate_tool_arguments(name, args)
                if name == "authority":
                    return await self._wire(lambda: authority_query(args))
                if name == "corpus_search":
                    return await self._wire(lambda: corpus_query(args))
                if name in _KEY_ROUTE_TOOLS:
                    return await self._call_key_route_tool(name, args)
                if self._resumes_sign_in:
                    await self._hold_session()
                return await self._wire(lambda: call_admitted_operation(self, name, args))
            except AutomationRequesterUncertainError as error:
                return {"outcome": "unresolved", "request_id": str(error.request_id), "code": error.reason}
            except Exception as error:
                code = refusal_code(error)
                reply: dict[str, Any] = {"outcome": "refused", "code": code}
                if remedy := runtime_unavailable_remedy(code):
                    reply["remedy"] = remedy
                return reply

    async def _wire(self, function: Callable[[], WireResultT]) -> WireResultT:
        return await await_cancellation_complete(asyncio.to_thread(function), task_name="mcp-runtime-call")

    async def _call_key_route_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Serve enrollment and key authentication for the bound profile; neither resumes a sign-in."""
        profile_id = await self._bound_profile()
        if name == "authorization_prepare":
            return await self._authorization_prepare(args, profile_id)
        if name == "authorization_request":
            return await self._wire(lambda: self._authorization_request(args, profile_id))
        if name == "authorization_poll":
            return await self._wire(self._authorization_poll)
        return await self._authenticate(args, profile_id)

    async def _authorization_prepare(self, args: dict[str, Any], profile_id: UUID) -> dict[str, Any]:
        reference = UUID(args["credential_reference"]) if "credential_reference" in args else None
        if self._enrollment_client is not None:
            enrollment = self._enrollment
            receipt = None if enrollment is None else enrollment.receipt
            finished = receipt is not None and receipt.stage in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}
            expired = enrollment is not None and now() >= enrollment.prepared.expires_at
            if not finished and not expired:
                raise ValueError("one pending authorization per connection")
            # Retire only the request transport. A completed grant and this
            # adapter's independently admitted session retain their own lives.
            previous = self._enrollment_client
            self._enrollment_client = None
            self._enrollment = None
            self._enrollment_reference = None
            self._requester = None
            await self._retire_client(previous, task_name="mcp-enrollment-retire")
        client = await self._open_enrollment_client(reference, profile_id)
        try:
            enrollment = await self._wire(lambda: self._prepare_enrollment(client, reference))
        except BaseException as error:
            await self._retire_client(client, task_name="mcp-enrollment-close", primary_error=error)
            raise
        self._enrollment_client = client
        self._enrollment = enrollment
        self._enrollment_reference = reference
        prepared = enrollment.prepared
        return {
            "outcome": "prepared",
            "profile_id": str(profile_id),
            "request_id": str(prepared.enrollment_request_id),
            "client_id": str(prepared.client_id),
            "destination_id": str(prepared.destination_id),
            "expires_at": prepared.expires_at.isoformat(),
        }

    async def _open_enrollment_client(self, reference: UUID | None, profile_id: UUID) -> RuntimeFrontendClient:
        if reference is not None:
            return await self._open_reference_client(reference, profile_id=profile_id)
        try:
            return await open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.MCP)
        except BaseException as error:
            self._retain_admission_cleanup(error)
            raise

    @staticmethod
    def _prepare_enrollment(client: RuntimeFrontendClient, reference: UUID | None) -> NativeEnrollmentClient:
        secret_store = installed_automation_secret_store()
        if reference is None:
            return client.prepare_enrollment(secret_store)
        return client.prepare_grant_change(secret_store)

    def _authorization_request(self, args: dict[str, Any], profile_id: UUID) -> dict[str, Any]:
        enrollment = self._enrollment
        if enrollment is None:
            raise ValueError("authorization_prepare required")
        if self._requester is not None:
            raise ValueError("one proposal per prepared request")
        proposal = parse_model(EnrollmentProposal, args["proposal"])
        original_reference = self._enrollment_reference
        if (proposal.kind is EnrollmentKind.ENROLL) != (original_reference is None):
            raise ValueError("grant changes require an authenticated prepared request")

        def reconcile(submitted: AutomationReceiptProjection, *, timeout: float) -> AutomationReceiptProjection:
            reference = self._reconciliation_reference(enrollment, proposal, original_reference)
            return asyncio.run(self._reconcile_enrollment(reference, profile_id, submitted, timeout))

        self._requester = AutomationRequesterJourney(
            enrollment, timeout=300, reconcile=None if original_reference is None else reconcile
        )
        receipt = self._requester.submit(proposal)
        return {"outcome": "recorded", "receipt": public_value(receipt)}

    async def _reconcile_enrollment(
        self, reference: UUID, profile_id: UUID, submitted: AutomationReceiptProjection, timeout: float
    ) -> AutomationReceiptProjection:
        deadline = time.monotonic() + timeout
        fresh = await self._open_reference_client(reference, profile_id=profile_id, timeout=timeout)
        try:
            return fresh.reconcile_enrollment(submitted.request_id, timeout=deadline - time.monotonic())
        finally:
            await self._retire_client(fresh, task_name="mcp-reconcile-close", primary_error=sys.exception())

    @staticmethod
    def _reconciliation_reference(
        enrollment: NativeEnrollmentClient, proposal: EnrollmentProposal, original_reference: UUID | None
    ) -> UUID:
        reference = (
            enrollment.delivered_credential_metadata().credential_reference
            if proposal.kind is EnrollmentKind.ROTATE
            else original_reference
        )
        if reference is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reference

    def _authorization_poll(self) -> dict[str, Any]:
        if self._requester is None:
            raise ValueError("no authorization request")
        receipt = self._requester.step()
        completion = self._requester.completion
        return {
            "outcome": "recorded",
            "receipt": public_value(receipt),
            "delivery_state": "processed" if completion is not None else "waiting",
        }

    async def _authenticate(self, args: dict[str, Any], profile_id: UUID) -> dict[str, Any]:
        credential_reference = UUID(args["credential_reference"])
        client = await self._open_reference_client(credential_reference, profile_id=profile_id)

        def admit() -> tuple[ProfileAccessStatus, Event]:
            status = require_exact_admitted_status(client, profile_id=profile_id)
            return status, self._retirement_notice(client)

        try:
            status, retired = await self._wire(admit)
        except BaseException as error:
            await self._retire_client(client, task_name="mcp-admission-close", primary_error=error)
            raise
        result = {"outcome": "authenticated", "status": public_value(status_on_surface(status, self.surface))}
        old_client = self.client
        self.client, self._retired = client, retired
        self.admission = McpAdmission.KEY
        self._contracts.clear()
        self._admission_denial = None
        if old_client is not None:
            await self._retire_client(old_client, task_name="mcp-reauth-close")
        return result
