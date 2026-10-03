"""One MCP connection's authenticated runtime and enrollment adapter."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from typing import Any, TypeVar
from uuid import UUID

from cadrumo.adapters.local_runtime.automation_requester import (
    AutomationRequesterJourney,
    AutomationRequesterUncertainError,
)
from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
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
from .protocol_contract import (
    MCP_TOOL_NAMES,
    parse_model,
    public_value,
    refusal_code,
    validate_tool_arguments,
)
from .runtime_admission import require_exact_admitted_status
from .runtime_cleanup import (
    RuntimeAdmissionCleanup,
    RuntimeClientCleanup,
    cleanup_sources,
    preserve_cancellation_body_error,
    retain_cleanup_failure,
)

_TIMEOUT = 30.0
WireResultT = TypeVar("WireResultT")


class RuntimeMcpAdapter:
    """One MCP connection owns one admitted lease and independent enrollment door."""

    def __init__(self, *, profile_id: UUID, client: RuntimeFrontendClient | None) -> None:
        """Bind a protocol connection to one immutable profile and optional lease."""
        if client is not None and (
            client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.MCP
        ):
            raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        self.profile_id = profile_id
        self.client = client
        self._lock = asyncio.Lock()
        self._enrollment_client: RuntimeFrontendClient | None = None
        self._enrollment: NativeEnrollmentClient | None = None
        self._enrollment_reference: UUID | None = None
        self._requester: AutomationRequesterJourney | None = None
        self._startup_denial: str | None = None
        self._retiring_resources: dict[int, AsyncCloseable] = {}

    async def bootstrap_reference(self, credential_reference: UUID) -> None:
        """Try the normal authentication door while keeping public MCP reachable."""
        result = await self.call("authenticate", {"credential_reference": str(credential_reference)})
        if result.get("outcome") == "authenticated":
            return
        code = result.get("code")
        self._startup_denial = code if isinstance(code, str) else "runtime_unavailable"

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

    async def _open_reference_client(self, reference: UUID, *, timeout: float | None = None) -> RuntimeFrontendClient:
        try:
            if timeout is not None:
                return await open_installed_credential_client(
                    profile_id=self.profile_id,
                    credential_reference=reference,
                    frontend=OperationFrontendProjection.MCP,
                    timeout=timeout,
                )
            return await open_installed_credential_client(
                profile_id=self.profile_id, credential_reference=reference, frontend=OperationFrontendProjection.MCP
            )
        except BaseException as error:
            self._retain_admission_cleanup(error)
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
            raise RuntimeFrontendRefusedError(self._startup_denial or "authentication_required")
        return self.client

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Serialize all blocking wire calls; cancellation waits for cleanup."""
        if name not in MCP_TOOL_NAMES:
            return {"outcome": "refused", "code": "unknown_tool"}
        async with self._lock:
            try:
                validate_tool_arguments(name, args)
                if name == "authorization_prepare":
                    return await self._authorization_prepare(args)
                if name == "authorization_request":
                    return await self._wire(lambda: self._authorization_request(args))
                if name == "authorization_poll":
                    return await self._wire(self._authorization_poll)
                if name == "authenticate":
                    return await self._authenticate(args)
                if name == "authority":
                    return await self._wire(lambda: authority_query(args))
                return await self._wire(lambda: call_admitted_operation(self, name, args))
            except AutomationRequesterUncertainError as error:
                return {"outcome": "unresolved", "request_id": str(error.request_id), "code": error.reason}
            except Exception as error:
                return {"outcome": "refused", "code": refusal_code(error)}

    async def _wire(self, function: Callable[[], WireResultT]) -> WireResultT:
        return await await_cancellation_complete(asyncio.to_thread(function), task_name="mcp-runtime-call")

    async def _authorization_prepare(self, args: dict[str, Any]) -> dict[str, Any]:
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
        client = await self._open_enrollment_client(reference)
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
            "profile_id": str(self.profile_id),
            "request_id": str(prepared.enrollment_request_id),
            "client_id": str(prepared.client_id),
            "destination_id": str(prepared.destination_id),
            "expires_at": prepared.expires_at.isoformat(),
        }

    async def _open_enrollment_client(self, reference: UUID | None) -> RuntimeFrontendClient:
        if reference is not None:
            return await self._open_reference_client(reference)
        try:
            return await open_installed_runtime_client(
                profile_id=self.profile_id, frontend=OperationFrontendProjection.MCP
            )
        except BaseException as error:
            self._retain_admission_cleanup(error)
            raise

    @staticmethod
    def _prepare_enrollment(client: RuntimeFrontendClient, reference: UUID | None) -> NativeEnrollmentClient:
        secret_store = installed_automation_secret_store()
        if reference is None:
            return client.prepare_enrollment(secret_store)
        return client.prepare_grant_change(secret_store)

    def _authorization_request(self, args: dict[str, Any]) -> dict[str, Any]:
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
            return asyncio.run(self._reconcile_enrollment(enrollment, proposal, original_reference, submitted, timeout))

        self._requester = AutomationRequesterJourney(
            enrollment, timeout=300, reconcile=None if original_reference is None else reconcile
        )
        receipt = self._requester.submit(proposal)
        return {"outcome": "recorded", "receipt": public_value(receipt)}

    async def _reconcile_enrollment(
        self,
        enrollment: NativeEnrollmentClient,
        proposal: EnrollmentProposal,
        original_reference: UUID | None,
        submitted: AutomationReceiptProjection,
        timeout: float,
    ) -> AutomationReceiptProjection:
        reference = self._reconciliation_reference(enrollment, proposal, original_reference)
        deadline = time.monotonic() + timeout
        fresh = await self._open_reference_client(reference, timeout=timeout)
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

    async def _authenticate(self, args: dict[str, Any]) -> dict[str, Any]:
        credential_reference = UUID(args["credential_reference"])
        client = await self._open_reference_client(credential_reference)
        try:
            status = await self._wire(lambda: require_exact_admitted_status(client, profile_id=self.profile_id))
        except BaseException as error:
            await self._retire_client(client, task_name="mcp-admission-close", primary_error=error)
            raise
        result = {"outcome": "authenticated", "status": public_value(status)}
        old_client = self.client
        self.client = client
        self._startup_denial = None
        if old_client is not None:
            await self._retire_client(old_client, task_name="mcp-reauth-close")
        return result
