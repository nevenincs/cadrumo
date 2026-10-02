"""Client-owned MCP projection of the installed profile-bound runtime."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict, TypeVar, cast
from uuid import UUID, uuid4

import anyio
from pydantic import BaseModel, ValidationError

from cadrumo.adapters.local_runtime.automation_requester import (
    AutomationRequesterJourney,
    AutomationRequesterUncertainError,
)
from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.modelo.registry_discovery import (
    registry_bindings_for_year,
    registry_casilla_for_registry_scope,
    registry_casillas_for_registry_scope,
    registry_describe_modelo_for_registry_scope,
    registry_formulas_for_registry_scope,
    registry_list_modelos,
    registry_support_matrix,
)
from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRequestV1,
    OperationDetachRequestV1,
    OperationObservationRequestV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationManage,
    RuntimeOperationObserve,
    RuntimeOperationReview,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.projection_pages import ProjectionPage, ProjectionPageRequest
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, ProfileAccessStatus
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
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
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_store import AuthorityStoreError
from cadrumo.domain.calculations.registry.errors import (
    AuthorityDescriptorUnavailableError,
    RegistryError,
    RegistryValidationError,
)

if TYPE_CHECKING:
    from mcp.server import Server

_TIMEOUT = 30.0
WireResultT = TypeVar("WireResultT")


class _FieldSchema(TypedDict):
    """One supported JSON Schema property declaration."""

    type: str
    enum: NotRequired[list[str]]
    minimum: NotRequired[int]


class _ToolSchema(TypedDict):
    """The stable object schema advertised for one tool."""

    type: str
    additionalProperties: bool
    properties: dict[str, _FieldSchema]
    required: list[str]


def _schema(required: Mapping[str, _FieldSchema], optional: Mapping[str, _FieldSchema] | None = None) -> _ToolSchema:
    fields = dict(required)
    fields.update(optional or {})
    return {"type": "object", "additionalProperties": False, "properties": fields, "required": list(required)}


_TEXT: _FieldSchema = {"type": "string"}
_DOC: _FieldSchema = {"type": "object"}
_TOOLS = (
    ("status", "Current exact-profile authorization and availability", _schema({})),
    (
        "authorization_prepare",
        "Prepare enrollment, or an own-grant change using a protected credential reference",
        _schema({}, {"credential_reference": _TEXT}),
    ),
    ("authorization_request", "Submit a proposal for the prepared destination", _schema({"proposal": _DOC})),
    ("authorization_poll", "Inspect or complete this connection's pending authorization", _schema({})),
    (
        "authenticate",
        "Admit this connection using a protected credential reference",
        _schema({"credential_reference": _TEXT}),
    ),
    (
        "authority",
        "Query one pinned published tax authority generation",
        _schema(
            {
                "query": {
                    "type": "string",
                    "enum": ["modelos", "support", "describe", "casillas", "casilla", "formulas", "bindings"],
                }
            },
            {"modelo": _TEXT, "filing_year": {"type": "integer"}, "period": _TEXT, "casilla": _TEXT, "as_of": _TEXT},
        ),
    ),
    ("search", "Find currently permitted registered operations", _schema({}, {"query": _TEXT})),
    ("describe", "Read one current registered operation contract and input schema", _schema({"definition_id": _TEXT})),
    (
        "execute",
        "Submit one registered operation under current profile authority",
        _schema(
            {"definition_id": _TEXT, "subject_ref": _TEXT, "payload": _DOC},
            {"idempotency_key": _TEXT, "start": {"type": "boolean"}},
        ),
    ),
    ("observe", "Read a currently authorized operation observation", _schema({"observation": _DOC})),
    ("result", "Read a settled registered result with fresh disclosure checks per page", _schema({"result": _DOC})),
    (
        "result_page",
        "Read one bounded settled result page with fresh disclosure checks",
        _schema({"result": _DOC, "page": _DOC}),
    ),
    ("review", "Read a currently authorized review projection", _schema({"review": _DOC})),
    (
        "respond",
        "Inspect, apply, or reject a pending review owned by this admitted session",
        _schema(
            {
                "action": {"type": "string", "enum": ["inspect", "apply", "reject"]},
                "operation_id": _TEXT,
                "interaction_id": _TEXT,
                "revision": {"type": "integer", "minimum": 0},
            },
            {"reason_code": _TEXT},
        ),
    ),
    (
        "control",
        "Start, resume, cancel, or detach a registered operation",
        _schema(
            {"action": {"type": "string", "enum": ["start", "resume", "cancel", "detach"]}, "operation_id": _TEXT},
            {"expected_revision": {"type": "integer", "minimum": 0}},
        ),
    ),
)


def _public(value: object) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _result_object(value: object) -> dict[str, Any] | None:
    """Narrow one JSON-shaped result object for its known public fields."""
    if not isinstance(value, dict):
        return None
    # Results are assembled by this adapter as string-keyed objects; nested
    # dictionaries are the object values in those same JSON results.
    return cast(dict[str, Any], value)


def _has_refusal(value: dict[str, Any]) -> bool:
    if value.get("outcome") in {"refused", "unresolved"}:
        return True
    start = _result_object(value.get("start"))
    if start is not None and start.get("outcome") == "unresolved":
        return True
    if value.get("outcome") != "reply":
        return False
    reply = _result_object(value.get("reply"))
    if reply is not None:
        if reply.get("kind") == "access_refusal":
            return True
        for key in ("observation", "document"):
            envelope = _result_object(reply.get(key))
            if envelope is not None and envelope.get("outcome") == "refused":
                return True
    document = _result_object(value.get("document"))
    if document is not None:
        return str(document.get("outcome")) == "refused"
    page = _result_object(value.get("page"))
    if page is not None:
        # Byte transport can carry a registered refusal. Classify only a
        # complete canonical document; a fragment or digest grants no outcome.
        try:
            released = ProjectionPage.model_validate(page)
            if released.offset:
                return False
            encoded = released.decode()
            if len(encoded) != released.total_bytes or sha256_hex(encoded) != released.document_digest:
                return False
            refusal = OperationResultProjectionRefusalV1.model_validate_json(encoded)
            return canonical_json_bytes(refusal.model_dump(mode="json")) == encoded
        except (ValueError, TypeError):
            return False
    return False


def _parse[M: BaseModel](model: type[M], value: object) -> M:
    return model.model_validate_json(canonical_json_bytes(value))


def _validate_args(name: str, args: dict[str, object]) -> None:
    schema: _ToolSchema = next(row[2] for row in _TOOLS if row[0] == name)
    properties = schema["properties"]
    if set(args) - set(properties) or set(schema["required"]) - set(args):
        raise ValueError("unknown or missing tool field")
    for key, value in args.items():
        declaration = properties[key]
        kind = declaration["type"]
        field_value: object = value
        if kind == "string" and not isinstance(field_value, str):
            raise ValueError("invalid tool field")
        if kind == "object" and not isinstance(field_value, dict):
            raise ValueError("invalid tool field")
        if kind == "boolean" and not isinstance(field_value, bool):
            raise ValueError("invalid tool field")
        if kind == "integer":
            if not isinstance(field_value, int) or isinstance(field_value, bool):
                raise ValueError("invalid tool field")
            if field_value < declaration.get("minimum", 0):
                raise ValueError("invalid tool field")
        if "enum" in declaration and (not isinstance(field_value, str) or field_value not in declaration["enum"]):
            raise ValueError("invalid tool field")


def _refusal(error: Exception) -> str:
    if isinstance(error, (RuntimeFrontendRefusedError, RuntimeRefusalError, AutomationCustodyError)):
        reason = error.reason
        if isinstance(reason, Enum):
            return str(reason.value)
        return str(reason)
    if isinstance(error, AuthorityDescriptorUnavailableError):
        return "published_authority_unavailable"
    if isinstance(error, RegistryValidationError):
        return "published_authority_query_refused"
    if isinstance(error, (AuthorityStoreError, RegistryError)):
        return "published_authority_invalid"
    if isinstance(error, (ValidationError, ValueError, TypeError, KeyError)):
        return "invalid_request"
    return "runtime_unavailable"


def _require_exact_admitted_status(client: RuntimeFrontendClient, *, profile_id: UUID) -> ProfileAccessStatus:
    """Treat a live, exact MCP lease as the only successful admission witness."""
    if client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.MCP:
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    session_id = client.session_id
    status = client.status().status
    if status.denial is not None:
        raise RuntimeFrontendRefusedError(status.denial.value)
    if status.session_expires_at is None or status.session_expires_at <= now():
        raise RuntimeFrontendRefusedError(AccessDenialCode.SESSION_EXPIRED.value)
    if not status.grant_valid:
        raise RuntimeFrontendRefusedError(AccessDenialCode.GRANT_INACTIVE.value)
    if (
        not status.connected
        or not status.credential_authenticated
        or not status.profile_bound
        or status.profile_id != profile_id
        or status.session_id != session_id
    ):
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    return status


@dataclass(frozen=True, slots=True)
class _RuntimeClientCleanup:
    """Retain a blocking connection owner until close succeeds or is retried."""

    client: RuntimeFrontendClient
    on_closed: Callable[[], None] | None = None

    async def close(self) -> None:
        await asyncio.to_thread(self.client.close)
        if self.on_closed is not None:
            self.on_closed()


@dataclass(frozen=True, slots=True)
class _RuntimeAdmissionCleanup:
    """Own cleanup left by an admission that never returned its connection."""

    failure: AsyncResourceCleanupError
    on_closed: Callable[[], None]

    async def close(self) -> None:
        await self.failure.retry_cleanup()
        self.on_closed()


class RuntimeMcpAdapter:
    """One MCP connection owns one admitted lease and independent enrollment door."""

    def __init__(self, *, profile_id: UUID, client: RuntimeFrontendClient | None) -> None:
        """Bind a protocol connection to one immutable profile and optional lease."""
        if client is not None and (
            client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.MCP
        ):
            from cadrumo.application.user_profile.access_contracts import AccessDenialCode

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

            owner = _RuntimeClientCleanup(client, on_closed=released)
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

                    self._retiring_resources[identity] = _RuntimeAdmissionCleanup(failure, on_closed=released)

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

    async def close(self) -> None:
        """Release only this adapter's connection and pending enrollment."""
        primary_error = sys.exception()
        failures: list[BaseException] = []
        diagnostics: dict[int, BaseException] = {}

        def retain_cleanup(target: BaseException, *sources: BaseException, capture_only: bool = False) -> None:
            retained: AsyncResourceCleanupError | None = None
            seen: set[int] = set()
            seen_errors: set[int] = set()
            pending = [target, *sources]
            while pending:
                error = pending.pop(0)
                if id(error) in seen_errors:
                    continue
                seen_errors.add(id(error))
                body_error = error.__dict__.get("body_error")
                if isinstance(body_error, BaseException):
                    pending.append(body_error)
                candidates: list[object] = [error] if isinstance(error, AsyncResourceCleanupError) else []
                candidates.extend(error.__dict__.get(name) for name in ("async_cleanup_error", "cleanup_error"))
                for candidate in candidates:
                    if isinstance(candidate, AsyncResourceCleanupError) and id(candidate) not in seen:
                        seen.add(id(candidate))
                        retained = candidate if retained is None else retained.merged_with(candidate)
                    elif isinstance(candidate, BaseException) and not isinstance(candidate, AsyncResourceCleanupError):
                        diagnostics[id(candidate)] = candidate
            if retained is not None and not capture_only:
                if diagnostics:
                    diagnostic = AsyncResourceCleanupError(
                        (),
                        tuple(diagnostics.values()),
                        retry_task_name="mcp-runtime-close-diagnostics",
                        close_attempts=1,
                    )
                    retained = retained.merged_with(diagnostic)
                    retained.__cause__ = (
                        next(iter(diagnostics.values()))
                        if len(diagnostics) == 1
                        else BaseExceptionGroup("Earlier MCP cleanup diagnostics", list(diagnostics.values()))
                    )
                target.__dict__["async_cleanup_error"] = retained
                target.__dict__["cleanup_error"] = retained

        if primary_error is not None:
            # Native cleanup can replace a raw diagnostic attached to a
            # cancellation. Keep its exact identity before cleanup starts.
            retain_cleanup(primary_error, capture_only=True)

        async def release() -> None:
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

        async def settle() -> None:
            # A terminal cancellation is an outcome of the retained release,
            # rather than a new cancellation of the caller awaiting shield.
            try:
                await release()
            except BaseException as error:
                failures.append(error)

        try:
            await await_cancellation_complete(settle(), task_name="mcp-runtime-close")
        except asyncio.CancelledError as cancellation:
            sources = (*failures, *((primary_error,) if primary_error is not None else ()))
            retain_cleanup(cancellation, *sources)
            if "body_error" not in cancellation.__dict__:
                for error in sources:
                    body_error = error.__dict__.get("body_error")
                    if isinstance(body_error, BaseException):
                        cancellation.__dict__["body_error"] = body_error
                        break
                else:
                    if primary_error is not None and not isinstance(primary_error, asyncio.CancelledError):
                        cancellation.__dict__["body_error"] = primary_error
            raise
        if primary_error is not None and not isinstance(primary_error, AsyncResourceCleanupError):
            retain_cleanup(primary_error)
        if failures:
            raise failures[0]

    def _admitted(self) -> RuntimeFrontendClient:
        if self.client is None:
            raise RuntimeFrontendRefusedError(self._startup_denial or "authentication_required")
        return self.client

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Serialize all blocking wire calls; cancellation waits for cleanup."""
        if name not in {row[0] for row in _TOOLS}:
            return {"outcome": "refused", "code": "unknown_tool"}
        async with self._lock:
            try:
                _validate_args(name, args)
                if name == "authorization_prepare":
                    return await self._authorization_prepare(args)
                if name == "authorization_request":
                    return await self._wire(lambda: self._authorization_request(args))
                if name == "authorization_poll":
                    return await self._wire(self._authorization_poll)
                if name == "authenticate":
                    return await self._authenticate(args)
                if name == "authority":
                    return await self._wire(lambda: _authority_query(args))
                return await self._wire(lambda: self._call_admitted(name, args))
            except AutomationRequesterUncertainError as error:
                return {"outcome": "unresolved", "request_id": str(error.request_id), "code": error.reason}
            except Exception as error:
                return {"outcome": "refused", "code": _refusal(error)}

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
        if reference is None:
            try:
                client = await open_installed_runtime_client(
                    profile_id=self.profile_id, frontend=OperationFrontendProjection.MCP
                )
            except BaseException as error:
                self._retain_admission_cleanup(error)
                raise
        else:
            client = await self._open_reference_client(reference)
        try:
            enrollment = await self._wire(
                lambda: (
                    client.prepare_enrollment(installed_automation_secret_store())
                    if reference is None
                    else client.prepare_grant_change(installed_automation_secret_store())
                )
            )
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

    def _authorization_request(self, args: dict[str, Any]) -> dict[str, Any]:
        enrollment = self._enrollment
        if enrollment is None:
            raise ValueError("authorization_prepare required")
        if self._requester is not None:
            raise ValueError("one proposal per prepared request")
        proposal = _parse(EnrollmentProposal, args["proposal"])
        original_reference = self._enrollment_reference
        if (proposal.kind is EnrollmentKind.ENROLL) != (original_reference is None):
            raise ValueError("grant changes require an authenticated prepared request")

        def reconcile(submitted: AutomationReceiptProjection, *, timeout: float) -> AutomationReceiptProjection:
            # This callback runs on the serialized wire thread. Reuse the CLI's
            # fresh-key recovery after approval invalidates the source lease.
            reference = (
                enrollment.delivered_credential_metadata().credential_reference
                if proposal.kind is EnrollmentKind.ROTATE
                else original_reference
            )
            if reference is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            deadline = time.monotonic() + timeout
            fresh = asyncio.run(self._open_reference_client(reference, timeout=timeout))
            try:
                return fresh.reconcile_enrollment(submitted.request_id, timeout=deadline - time.monotonic())
            finally:
                asyncio.run(self._retire_client(fresh, task_name="mcp-reconcile-close", primary_error=sys.exception()))

        self._requester = AutomationRequesterJourney(
            enrollment, timeout=300, reconcile=None if original_reference is None else reconcile
        )
        receipt = self._requester.submit(proposal)
        return {"outcome": "recorded", "receipt": _public(receipt)}

    def _authorization_poll(self) -> dict[str, Any]:
        if self._requester is None:
            raise ValueError("no authorization request")
        receipt = self._requester.step()
        completion = self._requester.completion
        return {
            "outcome": "recorded",
            "receipt": _public(receipt),
            "delivery_state": "processed" if completion is not None else "waiting",
        }

    async def _authenticate(self, args: dict[str, Any]) -> dict[str, Any]:
        credential_reference = UUID(args["credential_reference"])
        client = await self._open_reference_client(credential_reference)
        try:
            status = await self._wire(lambda: _require_exact_admitted_status(client, profile_id=self.profile_id))
        except BaseException as error:
            await self._retire_client(client, task_name="mcp-admission-close", primary_error=error)
            raise
        result = {"outcome": "authenticated", "status": _public(status)}
        old_client = self.client
        self.client = client
        self._startup_denial = None
        if old_client is not None:
            await self._retire_client(old_client, task_name="mcp-reauth-close")
        return result

    def _call_admitted(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "status" and self.client is None:
            return {
                "outcome": "status",
                "profile_id": str(self.profile_id),
                "authenticated": False,
                "denial": self._startup_denial or "authentication_required",
            }
        client = self._admitted()
        if name == "status":
            return {"outcome": "status", "status": _public(client.status().status)}
        deadline = time.monotonic() + _TIMEOUT
        if name == "search":
            status = _require_exact_admitted_status(client, profile_id=self.profile_id)
            query = str(args.get("query", "")).casefold()
            matches: list[Any] = []
            for definition_id in sorted(status.effective_scope.operations):
                if query not in definition_id.casefold():
                    continue
                try:
                    description = client.describe(definition_id, deadline=deadline)
                except RuntimeFrontendRefusedError as error:
                    if error.reason in {"frontend_denied", "operation_denied"}:
                        continue
                    raise
                matches.append(_public(description.contract))
            return {"outcome": "found", "operations": matches}
        if name == "describe":
            return {
                "outcome": "described",
                "description": _public(client.describe(args["definition_id"], deadline=deadline)),
            }
        if name == "execute":
            definition_id = args["definition_id"]
            client.describe(definition_id, deadline=deadline)
            payload_json = json.dumps(args["payload"], ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            request_id = uuid4()
            submission = RuntimeOperationSubmit(
                request_id=request_id,
                profile_id=client.profile_id,
                session_id=client.session_id,
                definition_id=definition_id,
                subject_ref=args["subject_ref"],
                payload_json=payload_json,
                idempotency_key=args.get("idempotency_key"),
            )
            try:
                reply = client.operation(submission, deadline=deadline)
                if not isinstance(reply, RuntimeOperationSubmitted):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            except RuntimeRefusalError as error:
                # The request may be durable even when its reply is lost.
                # A request id is correlation, never an operation receipt.
                return {
                    "outcome": "unresolved",
                    "code": _refusal(error),
                    "request_id": str(request_id),
                    "definition_id": definition_id,
                }
            except TimeoutError:
                # Native transports normally normalize this; a failed close
                # can still surface the underlying timeout after dispatch.
                return {
                    "outcome": "unresolved",
                    "code": RuntimeRefusalCode.DEADLINE_EXCEEDED.value,
                    "request_id": str(request_id),
                    "definition_id": definition_id,
                }
            except OSError:
                return {
                    "outcome": "unresolved",
                    "code": RuntimeRefusalCode.CONNECTION_CLOSED.value,
                    "request_id": str(request_id),
                    "definition_id": definition_id,
                }
            response: dict[str, Any] = {"outcome": "submitted", "receipt": _public(reply.receipt)}
            if args.get("start", True) and reply.receipt.secret_requirement is None:
                try:
                    ack = client.operation(
                        RuntimeOperationControl(
                            action="operation_start",
                            request_id=uuid4(),
                            profile_id=client.profile_id,
                            session_id=client.session_id,
                            operation_id=reply.receipt.operation_id,
                        ),
                        deadline=deadline,
                    )
                    if not isinstance(ack, RuntimeOperationAcknowledged):
                        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                    response["start"] = _public(ack)
                except Exception as error:
                    # Submission is already durable. A lost start reply must
                    # retain its receipt so callers reconcile instead of replay.
                    response["start"] = {"outcome": "unresolved", "code": _refusal(error)}
            return response
        if name == "observe":
            request = _parse(OperationObservationRequestV1, args["observation"])
            reply = client.operation(
                RuntimeOperationObserve(
                    request_id=uuid4(),
                    profile_id=client.profile_id,
                    session_id=client.session_id,
                    observation=request,
                ),
                deadline=deadline,
            )
            return {"outcome": "reply", "reply": _public(reply)}
        if name == "result":
            request = _parse(OperationResultProjectionRequestV1, args["result"])
            return {"outcome": "reply", "document": client.read_result_document(request, deadline=deadline)}
        if name == "result_page":
            request = _parse(OperationResultProjectionRequestV1, args["result"])
            page = _parse(ProjectionPageRequest, args["page"])
            return {"outcome": "reply", "page": _public(client.read_result_page(request, page, deadline=deadline))}
        if name == "review":
            request = _parse(OperationReviewProjectionRequestV1, args["review"])
            reply = client.operation(
                RuntimeOperationReview(
                    request_id=uuid4(),
                    profile_id=client.profile_id,
                    session_id=client.session_id,
                    review=request,
                ),
                deadline=deadline,
            )
            return {"outcome": "reply", "reply": _public(reply)}
        if name == "respond":
            action = args["action"]
            if "reason_code" in args and action != "reject":
                raise ValueError("only rejection accepts a reason code")
            response_fields = {
                "operation_id": args["operation_id"],
                "interaction_id": args["interaction_id"],
                "revision": args["revision"],
                "actor_ref": f"session:{client.session_id}",
            }
            if action == "inspect":
                response_request = _parse(OperationResponseControlRequestV1, response_fields)
            elif action == "apply":
                response_request = _parse(
                    OperationResponseApplyRequestV1,
                    response_fields | {"responded_at": now().isoformat()},
                )
            else:
                response_request = _parse(
                    OperationResponseRejectRequestV1,
                    response_fields | {"responded_at": now().isoformat(), "reason_code": args.get("reason_code")},
                )
            reply = client.operation(
                RuntimeOperationManage(
                    request_id=uuid4(),
                    profile_id=client.profile_id,
                    session_id=client.session_id,
                    management=response_request,
                ),
                deadline=deadline,
            )
            return {"outcome": "reply", "reply": _public(reply)}
        if name == "control":
            action = args["action"]
            operation_id = args["operation_id"]
            if action in {"start", "resume"}:
                if "expected_revision" in args:
                    raise ValueError("revision is not used by start or resume")
                reply = client.operation(
                    RuntimeOperationControl(
                        action="operation_start" if action == "start" else "operation_resume",
                        request_id=uuid4(),
                        profile_id=client.profile_id,
                        session_id=client.session_id,
                        operation_id=operation_id,
                    ),
                    deadline=deadline,
                )
            else:
                if "expected_revision" not in args:
                    raise ValueError("cancel and detach require a revision")
                kind = OperationCancellationRequestV1 if action == "cancel" else OperationDetachRequestV1
                management = _parse(
                    kind, {"operation_id": operation_id, "expected_revision": args["expected_revision"]}
                )
                reply = client.operation(
                    RuntimeOperationManage(
                        request_id=uuid4(),
                        profile_id=client.profile_id,
                        session_id=client.session_id,
                        management=management,
                    ),
                    deadline=deadline,
                )
            return {"outcome": "reply", "reply": _public(reply)}
        raise ValueError("unsupported tool")


def _authority_query(args: dict[str, Any]) -> dict[str, Any]:
    """Return one canonical public report under a single publication pin."""
    query = args["query"]
    allowed: dict[str, set[str]] = {
        "modelos": {"filing_year"},
        "support": set(),
        "bindings": {"modelo", "filing_year", "as_of"},
        "describe": {"modelo", "filing_year", "period", "as_of"},
        "casillas": {"modelo", "filing_year", "period", "as_of"},
        "casilla": {"modelo", "filing_year", "period", "casilla", "as_of"},
        "formulas": {"modelo", "filing_year", "period", "as_of"},
    }
    if query not in allowed:
        raise ValueError("unknown authority query")
    supplied = set(args) - {"query"}
    required: set[str] = (
        {"modelo", "filing_year"}
        if query == "bindings"
        else ({"modelo", "filing_year", "period"} if query not in {"modelos", "support"} else set())
    )
    if query == "casilla":
        required.add("casilla")
    if supplied - allowed[query] or required - supplied:
        raise ValueError("invalid authority query coordinates")
    if "filing_year" in args and not 1900 <= args["filing_year"] <= 9999:
        raise ValueError("invalid filing year")
    as_of = date.fromisoformat(args["as_of"]) if "as_of" in args else None
    with bundled_indexed_authority().operation() as operation:
        if query == "modelos":
            report = registry_list_modelos(year=args.get("filing_year"), operation=operation)
        elif query == "support":
            report = registry_support_matrix(operation=operation)
        elif query == "bindings":
            report = registry_bindings_for_year(
                args["modelo"], filing_year=args["filing_year"], as_of=as_of, operation=operation
            )
        else:
            filing_year, period = args["filing_year"], args["period"]
            if query == "describe":
                report = registry_describe_modelo_for_registry_scope(
                    args["modelo"], filing_year=filing_year, period=period, as_of=as_of, operation=operation
                )
            elif query == "casillas":
                report = registry_casillas_for_registry_scope(
                    args["modelo"], filing_year=filing_year, period=period, as_of=as_of, operation=operation
                )
            elif query == "casilla":
                report = registry_casilla_for_registry_scope(
                    args["modelo"],
                    args["casilla"],
                    filing_year=filing_year,
                    period=period,
                    as_of=as_of,
                    operation=operation,
                )
            elif query == "formulas":
                report = registry_formulas_for_registry_scope(
                    args["modelo"], filing_year=filing_year, period=period, as_of=as_of, operation=operation
                )
            else:
                raise ValueError("unknown authority query")
        pin = operation.generation
        return {
            "outcome": "published",
            "logical_generation": pin.logical_generation,
            "reader_incarnation": pin.reader_incarnation,
            "report": _public(report),
        }


def build_server(adapter: RuntimeMcpAdapter) -> Server:
    """Register the stable protocol surface around one connection-owned adapter."""
    from mcp.server import Server
    from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, TextContent, Tool

    async def list_tools(_context: object, _params: object) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(name=name, description=description, input_schema=cast(dict[str, Any], schema))
                for name, description, schema in _TOOLS
            ]
        )

    async def call_tool(_context: object, params: CallToolRequestParams) -> CallToolResult:
        result = await adapter.call(params.name, params.arguments or {})
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False, separators=(",", ":")))],
            structured_content=result,
            is_error=_has_refusal(result),
        )

    return Server("cadrumo", on_list_tools=list_tools, on_call_tool=call_tool)


def serve(*, profile_id: UUID, credential_reference: UUID | None = None) -> None:
    """Run one stdio adapter; EOF closes its lease, never the shared runtime."""
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.stdio import stdio_server

    async def run() -> None:
        adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
        try:
            if credential_reference is not None:
                await adapter.bootstrap_reference(credential_reference)
            server = build_server(adapter)
            async with stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(NotificationOptions(), experimental_capabilities={}),
                )
        finally:
            await adapter.close()

    anyio.run(run)
