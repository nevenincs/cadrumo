"""Exact-profile runtime login with an owned, cancellation-complete connection."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import ClassVar, cast, override
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
from ....core.async_cleanup import await_cancellation_complete
from ....core.i18n.render import tr
from ....core.time.clock import now
from ..components.app_access import TypedAppAccess
from ..components.status import PinnedStatusBar
from ..components.theme import BASE_CSS, install_cadrumo_themes, tokenised
from ..components.widgets import ContentScroll
from .automation_requester import RuntimeAutomationRequesterScreen
from .credentials import CREDENTIAL_PANEL_CSS

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
            cancellation = caught
        except BaseException:
            break
    try:
        return opening.result(), cancellation
    except BaseException:
        if cancellation is not None:
            raise cancellation from None
        raise


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
        self._busy = False
        self._live = True
        self._transferred = False
        self._worker: Worker[None] | None = None
        self._pending_proof: bytearray | None = None

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
        yield Footer()

    def on_mount(self) -> None:
        """Install the theme and default to the password field."""
        install_cadrumo_themes(self.app)
        title = tr("tui.runtime_login.title")
        self.title = title
        self.query_one("#runtime-login-banner", Static).update(title)
        self.query_one("#runtime-login-credential", Input).focus()
        self._show_method(RuntimeLoginMethod.PASSWORD)

    def _active(self) -> bool:
        """Check liveness afresh after each asynchronous native boundary."""
        return self._live and self.is_mounted

    async def on_unmount(self) -> None:
        """Drain native work and close an untransferred client before exit."""
        self._live = False
        worker = self._worker
        try:
            if not self._transferred and worker is not None:
                worker.cancel()
                with suppress(WorkerCancelled, WorkerError, WorkerFailed, asyncio.CancelledError):
                    await await_cancellation_complete(worker.wait(), task_name="tui-runtime-login-drain")
        finally:
            if self._pending_proof is not None:
                self._pending_proof[:] = bytes(len(self._pending_proof))
                self._pending_proof = None

    def on_select_changed(self, event: Select.Changed) -> None:
        """Switch proof labels without reinterpreting a previously entered value."""
        if event.select.id != "runtime-login-method" or self._busy:
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
        try:
            if method is RuntimeLoginMethod.API_REFERENCE:
                opener = self._open_credential_client
                if opener is None or reference is None or proof is not None:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

                async def open_reference(selected: UUID) -> RuntimeFrontendClient:
                    return await opener(selected, reference)

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
            code = error.reason if isinstance(error, RuntimeFrontendRefusedError) else error.reason.value
            self._status_refused(code)
        except asyncio.CancelledError:
            raise
        except Exception:
            if not transferred:
                self._status_refused()
        finally:
            if proof is not None:
                proof[:] = bytes(len(proof))
                if self._pending_proof is proof:
                    self._pending_proof = None
            if client is not None and not transferred:
                await await_cancellation_complete(asyncio.to_thread(client.close), task_name="tui-runtime-login-close")
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

            self.app.push_screen(RuntimeManagementScreen())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the masked field submits the chosen proof family."""
        if event.input.id in {"runtime-login-credential", "runtime-login-reference"}:
            self.action_submit()

    def action_abandon(self) -> None:
        """Dismiss only when no owned native exchange is pending."""
        if not self._busy:
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
