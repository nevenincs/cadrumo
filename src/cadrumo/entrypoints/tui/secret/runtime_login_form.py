"""Textual runtime-login form and control-state rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Footer, Input, Label, Select, Static

from ....core.i18n.render import tr
from ..components.status import PinnedStatusBar
from ..components.theme import install_cadrumo_themes
from ..components.widgets import ContentScroll
from .runtime_login_contracts import RuntimeLoginMethod

if TYPE_CHECKING:
    from .runtime_login import RuntimeLoginScreen


class RuntimeLoginFormMixin:
    """Own login form composition, proof-mode presentation, and input capture."""

    def compose(self: RuntimeLoginScreen) -> ComposeResult:
        """Compose the profile, proof, recovery, and action controls."""
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
            yield Checkbox(tr("tui.runtime_login.stay_signed_in"), value=False, id="runtime-login-persist")
            yield Label(tr("tui.runtime_login.credential_label_api_reference"), id="runtime-login-reference-label")
            yield Input(id="runtime-login-reference")
            with Horizontal(id="runtime-login-actions", classes="credential-actions"):
                yield Button(tr("tui.runtime_login.cancel"), id="runtime-login-cancel")
                yield Button(tr("tui.runtime_login.submit"), id="runtime-login-submit", classes="-primary")
                if self._requester_factory is not None:
                    yield Button(tr("tui.automation_request.enroll"), id="runtime-login-request-access")
            yield Label(tr("tui.runtime_access.resume_password"))
            yield Input(password=True, id="runtime-login-resume-password")
            yield Label(tr("tui.runtime_access.resume_grants"))
            yield Input(id="runtime-login-resume-grants")
            yield Button(tr("tui.runtime_access.resume"), id="runtime-login-resume")
        yield Footer()

    def on_mount(self: RuntimeLoginScreen) -> None:
        """Install the theme and default to the password field."""
        self._input_fields = tuple(self.query(Input))
        install_cadrumo_themes(self.app)
        title = tr("tui.runtime_login.title")
        self.title = title
        self.query_one("#runtime-login-banner", Static).update(title)
        self.query_one("#runtime-login-credential", Input).focus()
        self._show_method(RuntimeLoginMethod.PASSWORD)
        self._controls()
        if self._resume_preselected is not None:
            self.call_after_refresh(
                self._start_login_attempt, self._resume_preselected, RuntimeLoginMethod.RECEIPT, None, None
            )

    def _show_method(self: RuntimeLoginScreen, method: RuntimeLoginMethod) -> None:
        """Show one proof family and discard values from the previous one."""
        credential = self.query_one("#runtime-login-credential", Input)
        reference = self.query_one("#runtime-login-reference", Input)
        credential.value = ""
        reference.value = ""
        persistence = self.query_one("#runtime-login-persist", Checkbox)
        persistence.value = False
        persistence.display = method is RuntimeLoginMethod.PASSWORD
        persistence.disabled = self._busy or not persistence.display
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

    def _controls(self: RuntimeLoginScreen) -> None:
        method = cast("Select[RuntimeLoginMethod]", self.query_one("#runtime-login-method", Select)).value
        for selector, kind in (
            ("#runtime-login-profile", Select),
            ("#runtime-login-method", Select),
            ("#runtime-login-persist", Checkbox),
            ("#runtime-login-credential", Input),
            ("#runtime-login-reference", Input),
            ("#runtime-login-resume-password", Input),
            ("#runtime-login-resume-grants", Input),
            ("#runtime-login-submit", Button),
            ("#runtime-login-cancel", Button),
            *((("#runtime-login-request-access", Button),) if self._requester_factory is not None else ()),
        ):
            self.query_one(selector, kind).disabled = self._busy or (
                (
                    selector == "#runtime-login-credential"
                    and method in {RuntimeLoginMethod.RECEIPT, RuntimeLoginMethod.API_REFERENCE}
                )
                or (selector == "#runtime-login-reference" and method is not RuntimeLoginMethod.API_REFERENCE)
                or (selector == "#runtime-login-persist" and method is not RuntimeLoginMethod.PASSWORD)
            )
        selected = cast("Select[str]", self.query_one("#runtime-login-profile", Select)).value
        profile_id = self._profile_ids.get(selected) if isinstance(selected, str) else None
        self.query_one("#runtime-login-resume", Button).disabled = (
            self._busy or profile_id is None or profile_id in self._uncertain_resumes
        )

    def _request_access(self: RuntimeLoginScreen) -> None:
        selected = cast("Select[str]", self.query_one("#runtime-login-profile", Select)).value
        factory = self._requester_factory
        if not isinstance(selected, str) or selected not in self._profile_ids or factory is None:
            return
        try:
            self.app.push_screen(factory(self._profile_ids[selected]))
        except Exception:
            self._status_refused()

    def _selected_login(self: RuntimeLoginScreen) -> tuple[str, RuntimeLoginMethod] | None:
        selected = cast("Select[str]", self.query_one("#runtime-login-profile", Select)).value
        method = cast("Select[RuntimeLoginMethod]", self.query_one("#runtime-login-method", Select)).value
        if (
            not isinstance(selected, str)
            or selected not in self._profile_ids
            or not isinstance(method, RuntimeLoginMethod)
        ):
            self._status_refused()
            return None
        return selected, method

    def _reference_input(
        self: RuntimeLoginScreen, method: RuntimeLoginMethod, credential: Input, raw: str
    ) -> tuple[bool, UUID | None]:
        if method is not RuntimeLoginMethod.API_REFERENCE:
            return True, None
        try:
            reference = UUID(raw)
        except ValueError:
            reference = None
        if reference is None or str(reference) != raw:
            credential.value = ""
            self.query_one("#runtime-login-status", PinnedStatusBar).show_error(
                tr("tui.runtime_login.reference_invalid")
            )
            return False, None
        return True, reference

    @staticmethod
    def _proof_input(method: RuntimeLoginMethod, credential: Input) -> bytearray | None:
        proof = (
            bytearray(credential.value.encode("utf-8"))
            if method in {RuntimeLoginMethod.PASSWORD, RuntimeLoginMethod.API_KEY}
            else None
        )
        credential.value = ""
        return proof

    def _start_login_attempt(
        self: RuntimeLoginScreen,
        selected: str,
        method: RuntimeLoginMethod,
        proof: bytearray | None,
        reference: UUID | None,
        *,
        persist_receipt: bool = False,
    ) -> None:
        label = next(choice.label for choice in self._choices if choice.profile_id == selected)
        self._busy = True
        self._pending_proof = proof
        self._controls()
        self.query_one("#runtime-login-status", PinnedStatusBar).show_progress(tr("tui.runtime_login.progress"))
        self._worker = self.run_worker(
            self._attempt(
                self._profile_ids[selected], label, method, proof, reference, persist_receipt=persist_receipt
            ),
            name="tui-runtime-login",
            group="tui-runtime-login",
            exclusive=True,
            exit_on_error=False,
        )
