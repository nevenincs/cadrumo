"""Exact-profile runtime login with an owned, cancellation-complete connection."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import TYPE_CHECKING, ClassVar, cast, override
from uuid import UUID

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, Select, Static
from textual.worker import Worker, WorkerCancelled, WorkerError, WorkerFailed

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.profile_access import RuntimeProfileStatus
from ....application.user_profile.access_contracts import AuthorityState
from ....application.user_profile.login_interaction import ProfileLoginChoice
from ....application.user_profile.login_session import ProfileReceiptRefusedError
from ....core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, close_async_resources
from ....core.i18n.render import tr
from ....core.time.clock import now
from ..components.app_access import TypedAppAccess
from ..components.status import PinnedStatusBar
from ..components.theme import BASE_CSS, install_cadrumo_themes, tokenised
from ..components.widgets import ContentScroll
from .automation_requester import RuntimeAutomationRequesterScreen
from .credentials import CREDENTIAL_PANEL_CSS

if TYPE_CHECKING:
    from ..runtime_management import RuntimeManagementCleanup

type RuntimeRequesterFactory = Callable[[UUID], RuntimeAutomationRequesterScreen]


class RuntimeLoginMethod(StrEnum):
    """The explicitly selected proof family for one runtime login attempt."""

    PASSWORD = auto()
    API_KEY = auto()
    API_REFERENCE = auto()
    RECEIPT = auto()


@dataclass(frozen=True, slots=True)
class RuntimeLoginHandoff:
    """Transfer the one verified connection, without claiming local custody."""

    profile_id: UUID
    profile_label: str
    method: RuntimeLoginMethod
    status: RuntimeProfileStatus
    client: RuntimeFrontendClient = field(repr=False)


type RuntimeClientOpener = Callable[[UUID], Awaitable[RuntimeFrontendClient]]
type RuntimeCredentialClientOpener = Callable[[UUID, UUID], Awaitable[RuntimeFrontendClient]]
type RuntimeLoginAcceptor = Callable[[RuntimeLoginHandoff], bool]


async def _open_to_completion(
    opener: RuntimeClientOpener, profile_id: UUID
) -> tuple[RuntimeFrontendClient, asyncio.CancelledError | None]:
    """Retain an acquired client even when the screen is cancelled during open."""

    async def invoke() -> RuntimeFrontendClient:
        return await opener(profile_id)

    opening = asyncio.create_task(invoke(), name="tui-runtime-login-open")
    cancellation: asyncio.CancelledError | None = None
    while not opening.done():
        try:
            await asyncio.shield(opening)
        except asyncio.CancelledError as caught:
            if cancellation is None:
                cancellation = caught
        except BaseException:
            break
    try:
        return opening.result(), cancellation
    except BaseException:
        if cancellation is not None:
            await await_cancellation_complete(opening, task_name="tui-runtime-login-open", cancellation=cancellation)
        raise


class _LoginCleanup:
    """Keep one untransferred connection or failed admission until close succeeds."""

    def __init__(self, close: Callable[[], Awaitable[None]], *, released: Callable[[], None]) -> None:
        self._close = close
        self._released = released

    async def close(self) -> None:
        await self._close()
        self._released()


class RuntimeLoginScreen(TypedAppAccess, Screen[RuntimeLoginHandoff | None]):
    """Prompt for one exact profile and proof without opening local custody."""

    BINDINGS: ClassVar = [Binding("escape", "abandon", "", show=False)]
    SCOPED_CSS = False
    DEFAULT_CSS = tokenised(
        BASE_CSS
        + CREDENTIAL_PANEL_CSS
        + """
    #runtime-login-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
    """
    )

    def __init__(
        self,
        *,
        choices: Sequence[ProfileLoginChoice],
        open_client: RuntimeClientOpener,
        open_credential_client: RuntimeCredentialClientOpener | None = None,
        requester_factory: RuntimeRequesterFactory | None = None,
        accept_handoff: RuntimeLoginAcceptor,
        preselected: str | None = None,
        runtime_management_cleanup: RuntimeManagementCleanup | None = None,
    ) -> None:
        """Bind a nonsecret profile inventory and an exact-client opener."""
        super().__init__()
        if not choices:
            raise ValueError("runtime login requires a profile choice")
        parsed: dict[str, UUID] = {}
        for choice in choices:
            identity = UUID(choice.profile_id)
            if str(identity) != choice.profile_id or choice.profile_id in parsed:
                raise ValueError("runtime login requires distinct canonical profile identities")
            parsed[choice.profile_id] = identity
        self._choices = tuple(choices)
        self._profile_ids = parsed
        self._preselected = preselected if preselected in parsed else self._choices[0].profile_id
        self._open_client = open_client
        self._open_credential_client = open_credential_client
        self._requester_factory = requester_factory
        self._accept_handoff = accept_handoff
        self._runtime_management_cleanup = runtime_management_cleanup
        self._busy = False
        self._live = True
        self._transferred = False
        self._worker: Worker[None] | None = None
        self._pending_proof: bytearray | None = None
        self._input_fields: tuple[Input, ...] = ()
        self._cleanup_owners: dict[int, _LoginCleanup] = {}
        self._uncertain_resumes: set[UUID] = set()

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="runtime-login-banner", classes="cadrumo-banner")
        yield PinnedStatusBar(id="runtime-login-status")
        with (
            ContentScroll(classes="cadrumo-scroll"),
            Vertical(classes="cadrumo-column"),
            Vertical(id="runtime-login-body", classes="cadrumo-panel"),
        ):
            yield Label(tr("tui.runtime_login.profile_label"), classes="field-label")
            yield Select[str](
                [(choice.label, choice.profile_id) for choice in self._choices],
                value=self._preselected,
                allow_blank=False,
                id="runtime-login-profile",
            )
            yield Label(tr("tui.runtime_login.method_label"), classes="field-label")
            yield Select[RuntimeLoginMethod](
                [
                    (tr("tui.runtime_login.method_password"), RuntimeLoginMethod.PASSWORD),
                    (tr("tui.runtime_login.method_api_key"), RuntimeLoginMethod.API_KEY),
                    *(
                        [(tr("tui.runtime_login.method_api_reference"), RuntimeLoginMethod.API_REFERENCE)]
                        if self._open_credential_client is not None
                        else []
                    ),
                    (tr("tui.runtime_login.method_receipt"), RuntimeLoginMethod.RECEIPT),
                ],
                value=RuntimeLoginMethod.PASSWORD,
                allow_blank=False,
                id="runtime-login-method",
            )
            yield Label(tr("tui.runtime_login.credential_label_password"), id="runtime-login-credential-label")
            yield Static("", id="runtime-login-credential-hint", classes="field-hint")
            yield Input(password=True, id="runtime-login-credential")
            yield Label(tr("tui.runtime_login.credential_label_api_reference"), id="runtime-login-reference-label")
            yield Input(id="runtime-login-reference")
            with Horizontal(id="runtime-login-actions", classes="credential-actions"):
                yield Button(tr("tui.runtime_login.cancel"), id="runtime-login-cancel")
                yield Button(tr("tui.runtime_login.submit"), id="runtime-login-submit", classes="-primary")
                if self._requester_factory is not None:
                    yield Button(tr("tui.automation_request.enroll"), id="runtime-login-request-access")
                yield Button(tr("tui.runtime_management.open"), id="runtime-login-runtime-status")
            yield Label(tr("tui.runtime_access.resume_password"))
            yield Input(password=True, id="runtime-login-resume-password")
            yield Label(tr("tui.runtime_access.resume_grants"))
            yield Input(id="runtime-login-resume-grants")
            yield Button(tr("tui.runtime_access.resume"), id="runtime-login-resume")
        yield Footer()

    def on_mount(self) -> None:
        """Install the theme and default to the password field."""
        self._input_fields = tuple(self.query(Input))
        install_cadrumo_themes(self.app)
        title = tr("tui.runtime_login.title")
        self.title = title
        self.query_one("#runtime-login-banner", Static).update(title)
        self.query_one("#runtime-login-credential", Input).focus()
        self._show_method(RuntimeLoginMethod.PASSWORD)
        self._controls()

    def _active(self) -> bool:
        """Check liveness afresh after each asynchronous native boundary."""
        return self._live and self.is_mounted

    async def on_unmount(self) -> None:
        """Drain native work and close an untransferred client before exit."""
        self._live = False
        for input_field in self._input_fields:
            input_field.value = ""
        self._input_fields = ()
        worker = self._worker
        try:
            if not self._transferred and worker is not None:
                worker.cancel()
                with suppress(WorkerCancelled, WorkerError, WorkerFailed):
                    await await_cancellation_complete(worker.wait(), task_name="tui-runtime-login-drain")
        finally:
            try:
                await close_async_resources(
                    *tuple(self._cleanup_owners.values()), task_name="tui-runtime-login-release"
                )
            finally:
                if self._pending_proof is not None:
                    self._pending_proof[:] = bytes(len(self._pending_proof))
                    self._pending_proof = None

    def _retain_reference_cleanup(self, error: BaseException) -> None:
        """Adopt cleanup ownership before a failed opener becomes a UI refusal."""
        for name in ("async_cleanup_error", "cleanup_error"):
            failure = error.__dict__.get(name)
            if isinstance(failure, AsyncResourceCleanupError):
                identity = id(failure)
                self._retain_cleanup_owner(identity, failure.retry_cleanup)

    def _retain_cleanup_owner(self, identity: int, close: Callable[[], Awaitable[None]]) -> _LoginCleanup:
        owner = self._cleanup_owners.get(identity)
        if owner is None:

            def released() -> None:
                self._cleanup_owners.pop(identity, None)

            owner = _LoginCleanup(close, released=released)
            self._cleanup_owners[identity] = owner
        return owner

    def on_select_changed(self, event: Select.Changed) -> None:
        """Switch proof labels without reinterpreting a previously entered value."""
        if self._busy:
            return
        if event.select.id == "runtime-login-profile":
            self.query_one("#runtime-login-resume-password", Input).value = ""
            self.query_one("#runtime-login-resume-grants", Input).value = ""
            self._controls()
            return
        if event.select.id != "runtime-login-method":
            return
        method = event.value
        if not isinstance(method, RuntimeLoginMethod):
            return
        self._show_method(method)

    def _show_method(self, method: RuntimeLoginMethod) -> None:
        """Show one proof family and discard values from the previous one."""
        credential = self.query_one("#runtime-login-credential", Input)
        reference = self.query_one("#runtime-login-reference", Input)
        credential.value = ""
        reference.value = ""
        credential.display = method in {RuntimeLoginMethod.PASSWORD, RuntimeLoginMethod.API_KEY}
        credential.disabled = not credential.display
        reference.display = method is RuntimeLoginMethod.API_REFERENCE
        reference.disabled = not reference.display
        self.query_one("#runtime-login-reference-label", Label).display = reference.display
        label = self.query_one("#runtime-login-credential-label", Label)
        label.display = credential.display
        if credential.display:
            label.update(
                tr(
                    "tui.runtime_login.credential_label_password"
                    if method is RuntimeLoginMethod.PASSWORD
                    else "tui.runtime_login.credential_label_api_key"
                )
            )
        self.query_one("#runtime-login-credential-hint", Static).update(
            tr("tui.runtime_login.credential_hint_receipt")
            if method is RuntimeLoginMethod.RECEIPT
            else tr("tui.runtime_login.credential_hint_api_reference")
            if method is RuntimeLoginMethod.API_REFERENCE
            else tr("tui.runtime_login.credential_hint_api_key")
            if method is RuntimeLoginMethod.API_KEY
            else ""
        )

    def _controls(self) -> None:
        method = cast("Select[RuntimeLoginMethod]", self.query_one("#runtime-login-method", Select)).value
        for selector, kind in (
            ("#runtime-login-profile", Select),
            ("#runtime-login-method", Select),
            ("#runtime-login-credential", Input),
            ("#runtime-login-reference", Input),
            ("#runtime-login-resume-password", Input),
            ("#runtime-login-resume-grants", Input),
            ("#runtime-login-submit", Button),
            ("#runtime-login-cancel", Button),
            ("#runtime-login-runtime-status", Button),
            *((("#runtime-login-request-access", Button),) if self._requester_factory is not None else ()),
        ):
            self.query_one(selector, kind).disabled = self._busy or (
                (
                    selector == "#runtime-login-credential"
                    and method in {RuntimeLoginMethod.RECEIPT, RuntimeLoginMethod.API_REFERENCE}
                )
                or (selector == "#runtime-login-reference" and method is not RuntimeLoginMethod.API_REFERENCE)
            )
        selected = cast("Select[str]", self.query_one("#runtime-login-profile", Select)).value
        profile_id = self._profile_ids.get(selected) if isinstance(selected, str) else None
        self.query_one("#runtime-login-resume", Button).disabled = (
            self._busy or profile_id is None or profile_id in self._uncertain_resumes
        )

    async def _close_untransferred(self, client: RuntimeFrontendClient, *, primary_error: BaseException | None) -> None:
        """Keep each candidate in the existing pool until its native close succeeds."""

        async def close_candidate() -> None:
            await asyncio.to_thread(client.close)

        owner = self._retain_cleanup_owner(id(client), close_candidate)
        cancellation = primary_error if isinstance(primary_error, asyncio.CancelledError) else None
        interrupted_failure = None if cancellation is None else cancellation.__dict__.get("cleanup_error")
        if isinstance(interrupted_failure, BaseException) and not isinstance(
            interrupted_failure, AsyncResourceCleanupError
        ):
            primary_error = interrupted_failure
        await close_async_resources(
            owner, task_name="tui-runtime-login-close", primary_error=primary_error, cancellation=cancellation
        )

    def _resume_unknown(self, profile_id: UUID, code: str) -> None:
        """Fence replay of a dispatched recovery whose effect was not confirmed."""
        self._uncertain_resumes.add(profile_id)
        if self._active():
            self.query_one("#runtime-login-status", PinnedStatusBar).show_warning(
                f"{tr('tui.runtime_access.resume')}: {tr('tui.runtime_management.availability.unknown')} ({code})"
            )

    async def _resume_attempt(self, profile_id: UUID, proof: bytearray, grants: frozenset[UUID]) -> None:
        """Own fresh recovery and release; recovery never produces a login handoff."""
        client: RuntimeFrontendClient | None = None
        primary_error: BaseException | None = None
        dispatched = False
        completed = False
        try:
            try:

                async def open_recovery(selected: UUID) -> RuntimeFrontendClient:
                    try:
                        return await self._open_client(selected)
                    except BaseException as error:
                        self._retain_reference_cleanup(error)
                        raise

                client, interrupted_open = await _open_to_completion(open_recovery, profile_id)
                if interrupted_open is not None:
                    raise interrupted_open
                if not self._active():
                    return
                if client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.TUI:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                dispatched = True
                receipt = await await_cancellation_complete(
                    asyncio.to_thread(client.recover_profile, proof, grants=grants),
                    task_name="tui-runtime-profile-resume",
                )
                if receipt.profile_id != profile_id or receipt.reactivated_grants != grants:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                completed = True
                if self._active():
                    self.query_one("#runtime-login-status", PinnedStatusBar).show_success(
                        tr("tui.runtime_access.completed")
                    )
            except RuntimeFrontendRefusedError as error:
                primary_error = error
                if dispatched and error.reason in {code.value for code in RuntimeRefusalCode}:
                    self._resume_unknown(profile_id, error.reason)
                else:
                    self._status_refused(error.reason)
            except RuntimeRefusalError as error:
                primary_error = error
                if dispatched:
                    self._resume_unknown(profile_id, error.reason.value)
                else:
                    self._status_refused(error.reason.value)
            except asyncio.CancelledError as error:
                primary_error = error
                if dispatched:
                    self._resume_unknown(profile_id, RuntimeRefusalCode.UNAVAILABLE.value)
                raise
            except Exception as error:
                primary_error = error
                if dispatched:
                    self._resume_unknown(profile_id, RuntimeRefusalCode.UNAVAILABLE.value)
                else:
                    self._status_refused(RuntimeRefusalCode.UNAVAILABLE.value)
            finally:
                proof[:] = bytes(len(proof))
                if self._pending_proof is proof:
                    self._pending_proof = None
                if client is not None:
                    await self._close_untransferred(
                        client, primary_error=primary_error if primary_error is not None else sys.exception()
                    )
        except AsyncResourceCleanupError:
            # The pool already retains the failed candidate; never re-run recovery.
            if self._active():
                status = self.query_one("#runtime-login-status", PinnedStatusBar)
                if completed:
                    status.show_warning(
                        f"{tr('tui.runtime_access.completed')} ({RuntimeRefusalCode.UNAVAILABLE.value})"
                    )
                else:
                    self._status_refused(RuntimeRefusalCode.UNAVAILABLE.value)
        finally:
            self._busy = False
            if self._active():
                self.query_one("#runtime-login-resume-password", Input).value = ""
                self.query_one("#runtime-login-resume-grants", Input).value = ""
                self._controls()

    def action_resume(self) -> None:
        """Freeze exact profile, explicit selected grants and one fresh masked proof."""
        if self._busy:
            return
        selected = cast("Select[str]", self.query_one("#runtime-login-profile", Select)).value
        if not isinstance(selected, str) or selected not in self._profile_ids:
            self._status_refused()
            return
        profile_id = self._profile_ids[selected]
        if profile_id in self._uncertain_resumes:
            self.query_one("#runtime-login-resume-password", Input).value = ""
            self.query_one("#runtime-login-resume-grants", Input).value = ""
            self._resume_unknown(profile_id, RuntimeRefusalCode.UNAVAILABLE.value)
            return
        password = self.query_one("#runtime-login-resume-password", Input)
        grants_field = self.query_one("#runtime-login-resume-grants", Input)
        proof = bytearray(password.value.encode("utf-8"))
        password.value = ""
        raw = grants_field.value.strip()
        grants_field.value = ""
        try:
            parts = () if not raw else tuple(item.strip() for item in raw.split(","))
            selected_grants = tuple(UUID(item) for item in parts)
            if len(set(selected_grants)) != len(selected_grants):
                raise ValueError("repeated selected grant")
        except ValueError:
            proof[:] = bytes(len(proof))
            self.query_one("#runtime-login-status", PinnedStatusBar).show_error(tr("tui.runtime_access.invalid_grants"))
            return
        if not proof:
            self.query_one("#runtime-login-status", PinnedStatusBar).show_error(
                tr("tui.runtime_login.credential_required")
            )
            return
        self._busy = True
        self._pending_proof = proof
        self._controls()
        self.query_one("#runtime-login-status", PinnedStatusBar).show_progress(tr("tui.runtime_access.busy"))
        self._worker = self.run_worker(
            self._resume_attempt(profile_id, proof, frozenset(selected_grants)),
            name="tui-runtime-profile-resume",
            group="tui-runtime-login",
            exclusive=True,
            exit_on_error=False,
        )

    def _status_refused(self, code: str | None = None) -> None:
        if self._active():
            message = tr("tui.runtime_login.refused")
            self.query_one("#runtime-login-status", PinnedStatusBar).show_error(
                message if code is None else f"{message} ({code})"
            )
            if (
                cast("Select[RuntimeLoginMethod]", self.query_one("#runtime-login-method", Select)).value
                is RuntimeLoginMethod.RECEIPT
            ):
                self.query_one("#runtime-login-method", Select).focus()
            elif (
                cast("Select[RuntimeLoginMethod]", self.query_one("#runtime-login-method", Select)).value
                is RuntimeLoginMethod.API_REFERENCE
            ):
                self.query_one("#runtime-login-reference", Input).focus()
            else:
                self.query_one("#runtime-login-credential", Input).focus()

    async def _attempt(
        self, profile_id: UUID, label: str, method: RuntimeLoginMethod, proof: bytearray | None, reference: UUID | None
    ) -> None:
        """Retain every opened client until closed or explicitly handed off."""
        client: RuntimeFrontendClient | None = None
        transferred = False
        primary_error: BaseException | None = None
        try:
            if method is RuntimeLoginMethod.API_REFERENCE:
                opener = self._open_credential_client
                if opener is None or reference is None or proof is not None:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

                async def open_reference(selected: UUID) -> RuntimeFrontendClient:
                    try:
                        return await opener(selected, reference)
                    except BaseException as error:
                        self._retain_reference_cleanup(error)
                        raise

                client, interrupted_open = await _open_to_completion(open_reference, profile_id)
            else:
                client, interrupted_open = await _open_to_completion(self._open_client, profile_id)
            if interrupted_open is not None:
                raise interrupted_open
            if not self._active():
                return
            if client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.TUI:
                self._status_refused()
                return
            if method is RuntimeLoginMethod.API_REFERENCE:
                status = await await_cancellation_complete(
                    asyncio.to_thread(client.status), task_name="tui-runtime-login-reference-status"
                )
            elif method is RuntimeLoginMethod.RECEIPT:
                if proof is not None:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                status = await await_cancellation_complete(
                    asyncio.to_thread(client.resume_receipt), task_name="tui-runtime-login-receipt"
                )
            else:
                if proof is None:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if method is RuntimeLoginMethod.PASSWORD:
                    proving = asyncio.to_thread(client.login_password, proof)
                else:
                    proving = asyncio.to_thread(client.login_api_key, proof)
                status = await await_cancellation_complete(proving, task_name="tui-runtime-login-proof")
            # The proof has no purpose after its owned exchange completes.
            # Erase it before any receiving owner or dismissal callback runs.
            if proof is not None:
                proof[:] = bytes(len(proof))
                if self._pending_proof is proof:
                    self._pending_proof = None
            if not self._active():
                return
            access = status.status
            if (
                not access.connected
                or not access.credential_authenticated
                or not access.profile_bound
                or access.denial is not None
                or access.profile_id != profile_id
                or access.session_id is None
                or access.session_id != client.session_id
                or access.session_expires_at is None
                or access.session_expires_at <= now()
                or (
                    method in {RuntimeLoginMethod.API_KEY, RuntimeLoginMethod.API_REFERENCE}
                    and (
                        not access.grant_valid
                        or access.grant_state is not AuthorityState.ACTIVE
                        or access.grant_expires_at is None
                        or access.grant_expires_at <= now()
                    )
                )
            ):
                self._status_refused()
                return
            handoff = RuntimeLoginHandoff(
                profile_id=profile_id, profile_label=label, method=method, status=status, client=client
            )
            # Textual may only resolve a future or queue an async callback;
            # neither proves the receiving owner accepted the live client.
            if not self._accept_handoff(handoff):
                self._status_refused()
                return
            self._transferred = True
            transferred = True
            dismissal = self.dismiss(handoff)
            await await_cancellation_complete(dismissal, task_name="tui-runtime-login-dismiss")
        except (RuntimeFrontendRefusedError, RuntimeRefusalError, ProfileReceiptRefusedError) as error:
            primary_error = error
            code = error.reason if isinstance(error, RuntimeFrontendRefusedError) else error.reason.value
            self._status_refused(code)
        except asyncio.CancelledError as error:
            primary_error = error
            raise
        except Exception as error:
            primary_error = error
            if not transferred:
                self._status_refused()
        finally:
            if proof is not None:
                proof[:] = bytes(len(proof))
                if self._pending_proof is proof:
                    self._pending_proof = None
            try:
                if client is not None and not transferred:
                    await self._close_untransferred(
                        client,
                        primary_error=primary_error if primary_error is not None else sys.exception(),
                    )
            finally:
                self._busy = False
                if self._active():
                    self._controls()

    def action_submit(self) -> None:
        """Freeze exact profile and method before copying one masked proof."""
        if self._busy:
            return
        selected = cast("Select[str]", self.query_one("#runtime-login-profile", Select)).value
        method = cast("Select[RuntimeLoginMethod]", self.query_one("#runtime-login-method", Select)).value
        if (
            not isinstance(selected, str)
            or selected not in self._profile_ids
            or not isinstance(method, RuntimeLoginMethod)
        ):
            self._status_refused()
            return
        credential = self.query_one("#runtime-login-credential", Input)
        reference_field = self.query_one("#runtime-login-reference", Input)
        reference_raw = reference_field.value.strip()
        reference_field.value = ""
        reference: UUID | None = None
        if method is RuntimeLoginMethod.API_REFERENCE:
            try:
                reference = UUID(reference_raw)
            except ValueError:
                reference = None
            if reference is None or str(reference) != reference_raw:
                credential.value = ""
                self.query_one("#runtime-login-status", PinnedStatusBar).show_error(
                    tr("tui.runtime_login.reference_invalid")
                )
                return
        proof = (
            bytearray(credential.value.encode("utf-8"))
            if method in {RuntimeLoginMethod.PASSWORD, RuntimeLoginMethod.API_KEY}
            else None
        )
        credential.value = ""
        if method in {RuntimeLoginMethod.PASSWORD, RuntimeLoginMethod.API_KEY} and not proof:
            self.query_one("#runtime-login-status", PinnedStatusBar).show_error(
                tr("tui.runtime_login.credential_required")
            )
            return
        label = next(choice.label for choice in self._choices if choice.profile_id == selected)
        self._busy = True
        self._pending_proof = proof
        self._controls()
        self.query_one("#runtime-login-status", PinnedStatusBar).show_progress(tr("tui.runtime_login.progress"))
        self._worker = self.run_worker(
            self._attempt(self._profile_ids[selected], label, method, proof, reference),
            name="tui-runtime-login",
            group="tui-runtime-login",
            exclusive=True,
            exit_on_error=False,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch only explicit submit or abandon controls."""
        if event.button.id == "runtime-login-submit":
            self.action_submit()
        elif event.button.id == "runtime-login-resume":
            self.action_resume()
        elif event.button.id == "runtime-login-cancel":
            self.action_abandon()
        elif event.button.id == "runtime-login-request-access" and not self._busy:
            selected = cast("Select[str]", self.query_one("#runtime-login-profile", Select)).value
            factory = self._requester_factory
            if isinstance(selected, str) and selected in self._profile_ids and factory is not None:
                try:
                    self.app.push_screen(factory(self._profile_ids[selected]))
                except Exception:
                    self._status_refused()
        elif event.button.id == "runtime-login-runtime-status" and not self._busy:
            from ..runtime_management import RuntimeManagementScreen

            self.app.push_screen(RuntimeManagementScreen(cleanup=self._runtime_management_cleanup))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the masked field submits the chosen proof family."""
        if event.input.id in {"runtime-login-credential", "runtime-login-reference"}:
            self.action_submit()

    def action_abandon(self) -> None:
        """Dismiss only when no owned native exchange is pending."""
        if not self._busy:
            for input_field in self._input_fields:
                input_field.value = ""
            self.dismiss(None)


__all__ = [
    "RuntimeClientOpener",
    "RuntimeCredentialClientOpener",
    "RuntimeLoginAcceptor",
    "RuntimeLoginHandoff",
    "RuntimeLoginMethod",
    "RuntimeLoginScreen",
    "RuntimeRequesterFactory",
]
