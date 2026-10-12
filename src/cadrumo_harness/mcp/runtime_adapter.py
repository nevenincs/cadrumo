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
from cadrumo.adapters.local_runtime.installation_client import (
    RuntimeInstallationClient,
    open_installed_installation_client,
)
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.operations.mcp_surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, McpSurface
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operator_output.runtime_remedies import runtime_unavailable_remedy
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.installation_requests import InstallationAct
from cadrumo.application.runtime.profile_access import PROFILE_ADMISSION_TIMEOUT_SECONDS, RuntimeProfileStatus
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, ProfileAccessStatus
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
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
from .held_secrets import held_secret_custody
from .installation_acts import perform_installation_act, prepare_installation_act
from .lifecycle_notices import LifecycleNoticeBoard
from .operation_contract_cache import OperationContractCache
from .protocol_contract import (
    MCP_TOOL_NAMES,
    parse_model,
    public_value,
    refusal_code,
    validate_tool_arguments,
)
from .public_operation_discovery import SESSIONLESS_DISCOVERY_TOOLS, discover_public_operations
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
from .session_acts import (
    NO_SESSION,
    SECRET_FIELDS,
    UNADMITTED_SESSION_ACTIONS,
    SessionActRefusedError,
    SessionSecrets,
    assess_profile_deletion,
    change_password,
    delete_assessed_profile,
    read_sign_in_status,
    require_only,
    reset_password,
    resolve_named_profile,
    resume_profile,
    select_signed_in_profile,
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
        self._notices = LifecycleNoticeBoard()
        self._key_reference: UUID | None = None

    async def bootstrap_reference(self, credential_reference: UUID) -> None:
        """Try the normal authentication door while keeping public MCP reachable."""
        result = await self.call("authenticate", {"credential_reference": str(credential_reference)})
        if result.get("outcome") == "authenticated":
            return
        code = result.get("code")
        self._admission_denial = code if isinstance(code, str) else "runtime_unavailable"

    def _retirement(self, client: RuntimeFrontendClient | RuntimeInstallationClient) -> AsyncCloseable:
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
        selection has moved on. A lease admitted by key or by the typed password
        is not held to this.
        """
        if self._named_profile_id is None or self.admission in {McpAdmission.KEY, McpAdmission.TYPED_SIGN_IN}:
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
            await self._authenticate({"credential_reference": str(reference)}, await self._bound_profile())
        except Exception as error:
            self._admission_denial = refusal_code(error)

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
        client: RuntimeFrontendClient | RuntimeInstallationClient,
        *,
        task_name: str,
        primary_error: BaseException | None = None,
    ) -> None:
        self._notices.released(id(client))
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

    def held_secret(self, reference: UUID) -> bytearray:
        """Read the secret held under ``reference`` into a buffer the call wipes, spending it if it is a one-use one.

        A reference that names nothing held is a mistaken argument, and is
        answered as any other one is. Callers read only at the moment they
        send, after every other check.

        Raises:
            ValueError: No secret is held under the reference.
            AutomationCustodyError: The credential store could not be read.
        """
        try:
            return held_secret_custody(installed_automation_secret_store()).take(reference)
        except AutomationCustodyError as refused:
            if refused.reason in {AutomationCustodyCode.MISSING, AutomationCustodyCode.INVALID}:
                raise ValueError("no secret is held under that reference") from None
            raise

    def check_held_secret(self, reference: UUID) -> None:
        """Confirm that a secret is held under ``reference``, as a call is checked, without spending it.

        Raises:
            ValueError: No secret is held under the reference.
            AutomationCustodyError: The credential store could not be read.
        """
        try:
            held_secret_custody(installed_automation_secret_store()).verify(reference)
        except AutomationCustodyError as refused:
            if refused.reason in {AutomationCustodyCode.MISSING, AutomationCustodyCode.INVALID}:
                raise ValueError("no secret is held under that reference") from None
            raise

    def _call_secrets(self, args: dict[str, Any]) -> SessionSecrets:
        """Take the secrets out of one call's arguments; none is read from the store until it is sent."""
        return SessionSecrets(args, take=self.held_secret, verify=self.check_held_secret)

    async def _check_references(self, secrets: SessionSecrets) -> None:
        """Refuse a call whose reference names nothing held, off the event loop as every store read is."""
        if secrets.by_reference:
            await self._wire(secrets.check)

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
            if name in _KEY_ROUTE_TOOLS:
                return await self._call_key_route_tool(name, args)
            if name == "session":
                return await self._call_session_tool(args)
            if name == "installation":
                return await self._call_installation_tool(args)
            await self._hold_or_restore_session()
            if name in SESSIONLESS_DISCOVERY_TOOLS:
                return await self._wire(lambda: self._discover(name, args))
            return await self._wire(lambda: call_admitted_operation(self, name, args))
        except AutomationRequesterUncertainError as error:
            return {"outcome": "unresolved", "request_id": str(error.request_id), "code": error.reason}
        except SessionActRefusedError as refused:
            return refused.reply()
        except Exception as error:
            code = refusal_code(error)
            reply: dict[str, Any] = {"outcome": "refused", "code": code}
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

    def _session_token(self) -> str:
        """Say how this connection's own session stands, as ``status`` names it."""
        if self.client is None or self.admission is None or self._retired.is_set():
            return NO_SESSION
        return self.admission.value

    async def _call_session_tool(self, args: dict[str, Any]) -> dict[str, Any]:
        """Serve one session act; its secrets leave the call here and are wiped whatever follows."""
        secrets = self._call_secrets(args)
        try:
            await self._check_references(secrets)
            action = args["action"]
            if action in UNADMITTED_SESSION_ACTIONS:
                reply = await self._unadmitted_session_act(action, args, secrets)
                reply.setdefault("session", self._session_token())
                return reply
            secrets.require(action)
            await self._hold_or_restore_session()
            reply = await self._wire(lambda: call_admitted_operation(self, "session", args))
            if reply.get("session") == NO_SESSION:
                # The act ended this connection's own session, so its lease is not kept.
                await self._release_lease(task_name="mcp-ended-session-close")
            return reply
        finally:
            secrets.wipe()

    async def _call_installation_tool(self, args: dict[str, Any]) -> dict[str, Any]:
        """Serve one installation act; its secret leaves the call here and is wiped whatever follows."""
        secrets = self._call_secrets(args)
        try:
            await self._check_references(secrets)
            return await self._installation_act(args, secrets)
        finally:
            secrets.wipe()

    async def _installation_act(self, args: dict[str, Any], secrets: SessionSecrets) -> dict[str, Any]:
        """Send one sessionless act on a connection opened for it alone.

        No profile session is asked for, resumed or held: the runtime admits
        the act on the verified connection and the person's own login.
        """
        prepared = prepare_installation_act(args, secrets, self.surface)
        try:
            client = await open_installed_installation_client()
        except BaseException as error:
            self._retain_admission_cleanup(error)
            raise
        try:
            return await self._wire(
                lambda: perform_installation_act(
                    client, prepared, held_secrets=lambda: held_secret_custody(installed_automation_secret_store())
                )
            )
        finally:
            await self._retire_client(client, task_name="mcp-installation-act-close", primary_error=sys.exception())

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

    async def _on_own_connection(
        self, profile_id: UUID, act: Callable[[RuntimeFrontendClient], dict[str, Any]]
    ) -> dict[str, Any]:
        """Run one act on a connection opened for it alone and closed whatever it answers."""
        client = await self._open_unadmitted_client(profile_id)
        try:
            return await self._wire(lambda: act(client))
        finally:
            await self._retire_client(client, task_name="mcp-session-act-close", primary_error=sys.exception())

    async def _unadmitted_session_act(
        self, action: str, args: dict[str, Any], secrets: SessionSecrets
    ) -> dict[str, Any]:
        """Serve an act that proves itself with its own secret, or needs none, on its own connection."""
        if action == "sign_in":
            return await self._sign_in(args, secrets)
        if action == "delete_profile":
            return await self._delete_profile(args, secrets)
        if action == "enable_recovery":
            require_only(args, action, "profile")
            profile_id = await self._named_or_bound_profile(args)
            enrolment = {"action": InstallationAct.RECOVERY_ENROLL.value, "profile_id": str(profile_id)}
            return await self._installation_act(enrolment, secrets)
        if action == "sign_in_status":
            secrets.require(action)
            require_only(args, action)
            return await self._on_own_connection(await self._bound_profile(), read_sign_in_status)
        if action == "resume":
            secrets.require(action, "secret")
            require_only(args, action, "grants")
            grants = frozenset(UUID(item) for item in args.get("grants", ()))

            def resume(client: RuntimeFrontendClient) -> dict[str, Any]:
                (proof,) = secrets.take("secret")
                return resume_profile(client, proof, grants)

            return await self._on_own_connection(await self._bound_profile(), resume)
        secrets.require(action, *SECRET_FIELDS)
        if action == "reset_password":
            require_only(args, action, "profile")
            profile_id = await self._named_or_bound_profile(args)
            reply = await self._on_own_connection(
                profile_id, lambda client: reset_password(client, *secrets.take(*SECRET_FIELDS))
            )
        else:
            require_only(args, action)
            profile_id = await self._bound_profile()

            def fresh_client() -> RuntimeFrontendClient:
                return asyncio.run(self._open_unadmitted_client(profile_id))

            reply = await self._on_own_connection(
                profile_id,
                lambda client: change_password(client, *secrets.take(*SECRET_FIELDS), fresh_client=fresh_client),
            )
        if reply["outcome"] != "unresolved" and profile_id == self.profile_id:
            # The new password fenced every session admitted under the old one.
            await self._release_lease(task_name="mcp-replaced-password-close")
        return reply

    async def _named_or_bound_profile(self, args: dict[str, Any]) -> UUID:
        named = args.get("profile")
        if named is None:
            return await self._bound_profile()
        return await self._wire(lambda: resolve_named_profile(named))

    async def _sign_in_profile(self, args: dict[str, Any], *, store: bool) -> UUID:
        """Return the profile a sign-in is for, never moving a connection off the profile it is bound to.

        A connection started for one profile signs in to that profile alone.
        One that follows the selection signs in to another profile only when
        the sign-in is stored, which selects that profile as ``config login``
        does.
        """
        if "profile" not in args:
            return await self._bound_profile()
        target = await self._named_or_bound_profile(args)
        bound = self._named_profile_id
        if bound is None and not store:
            bound = await self._bound_profile()
        if bound is not None and bound != target:
            raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        return target

    async def _sign_in(self, args: dict[str, Any], secrets: SessionSecrets) -> dict[str, Any]:
        """Sign in with the typed password, or a raw key, and hold the session it admits."""
        secrets.require("sign_in", "secret")
        require_only(args, "sign_in", "method", "store", "profile")
        keyed = args.get("method", "password") == "api_key"
        store = args.get("store", False)
        if keyed and store:
            raise ValueError("only a password sign-in can be stored")
        profile_id = await self._sign_in_profile(args, store=store)
        admission = McpAdmission.KEY if keyed else McpAdmission.TYPED_SIGN_IN
        client = await self._open_unadmitted_client(profile_id, on_surface=True)

        def admit() -> tuple[RuntimeProfileStatus, ProfileAccessStatus, Event]:
            (proof,) = secrets.take("secret")
            admitted = client.login_api_key(proof) if keyed else client.login_password(proof, persist_receipt=store)
            status = require_exact_admitted_status(client, profile_id=profile_id, admission=admission)
            if store:
                select_signed_in_profile(profile_id)
            return admitted, status, self._watch(client)

        try:
            admitted, status, retired = await self._wire(admit)
        except BaseException as error:
            await self._retire_client(client, task_name="mcp-sign-in-close", primary_error=error)
            raise
        if profile_id != self.profile_id:
            await self._release_profile_state(task_name="mcp-reselected-profile-close")
            self.profile_id = profile_id
        await self._replace_lease(client, retired, admission)
        self._key_reference = None
        reply: dict[str, Any] = {
            "outcome": "signed_in",
            "session": admission.value,
            "status": public_value(status_on_surface(status, self.surface)),
        }
        if admitted.human_login is not None:
            reply["sign_in"] = public_value(admitted.human_login)
        return reply

    async def _delete_profile(self, args: dict[str, Any], secrets: SessionSecrets) -> dict[str, Any]:
        """Report what deleting the named profile would destroy, and destroy it only when confirmed."""
        secrets.require("delete_profile")
        require_only(args, "delete_profile", "profile", "confirm")
        if "profile" not in args:
            raise ValueError("delete_profile names its profile")
        preflight = await self._wire(lambda: assess_profile_deletion(args["profile"]))
        if not args.get("confirm", False):
            return {"outcome": "profile_assessed", "deleted": False, **preflight.reply}
        reply = await self._on_own_connection(
            preflight.profile_id, lambda client: delete_assessed_profile(client, preflight)
        )
        if preflight.profile_id == self.profile_id:
            await self._release_profile_state(task_name="mcp-deleted-profile-close")
        return reply

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
            return status, self._watch(client)

        try:
            status, retired = await self._wire(admit)
        except BaseException as error:
            await self._retire_client(client, task_name="mcp-admission-close", primary_error=error)
            raise
        result = {"outcome": "authenticated", "status": public_value(status_on_surface(status, self.surface))}
        self._key_reference = credential_reference
        await self._replace_lease(client, retired, McpAdmission.KEY)
        return result
