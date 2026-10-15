"""AEAT method and credential editor shared by acquisition and synchronization."""

from __future__ import annotations

from typing import ClassVar, Protocol, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Select, Static

from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....application.auth.sync_readiness import AuthSyncReadiness
from ....application.auth.sync_requirement_text import sync_requirement_reason
from ....application.user_profile.overview import ProfileOverview
from ....core.auth_provider import DEFAULT_CLAVE_MOVIL_ROUTE, AuthProviderKind, ClaveMovilRoute
from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.request_faults import request_fault_line
from ..components.theme import BASE_CSS, tokenised
from .auth_fields import AeatAuthFieldSaveError

_FACT_PATHS = ("identity.tax_id", "auth.dni_nie", "auth.fecha_validez", "auth.numero_soporte")


class AeatAuthSetupPort(Protocol):
    """Exact-profile setup door, with all writes owned by registered operations."""

    async def read_readiness(self) -> AuthSyncReadiness:
        """Read current sync requirements without collecting the profile overview."""
        ...

    async def snapshot(self) -> tuple[ProfileOverview, AuthSyncReadiness]:
        """Read stored facts and the worker's current readiness."""
        ...

    async def save(
        self,
        provider: AuthProviderKind,
        route: ClaveMovilRoute,
        fields: dict[str, str],
        certificate_path: str,
        secret: bytearray | None,
    ) -> tuple[ProfileOverview, AuthSyncReadiness]:
        """Persist entered facts and protected credentials, then reread readiness."""
        ...


def readiness_text(readiness: AuthSyncReadiness | None) -> str:
    """Render only finite requirement identifiers and localized recovery wording."""
    if readiness is None:
        return tr("tui.aeat_auth.unknown")
    if readiness.ready:
        return tr("tui.aeat_auth.ready")
    return "\n".join(
        (
            tr("tui.aeat_auth.blocked"),
            *(
                sync_requirement_reason(requirement.reason)
                for requirement in readiness.requirements
                if not requirement.satisfied
            ),
        )
    )


class AeatAuthSetupScreen(Screen[tuple[ProfileOverview, AuthSyncReadiness] | None]):
    """Show saved method-specific fields and reread authoritative readiness after edits."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    CSS = BASE_CSS + tokenised("""
    #aeat-auth-page { width: 100%; height: 1fr; padding: $cadrumo-space-1 $cadrumo-gutter; }
    #aeat-auth-page Static { height: auto; }
    #aeat-auth-page Input, #aeat-auth-page Select { margin-bottom: $cadrumo-space-1; }
    #aeat-auth-readiness, #aeat-auth-message { margin: $cadrumo-space-1 $cadrumo-space-0; }
    """)

    def __init__(self, door: AeatAuthSetupPort) -> None:
        """Retain the exact-profile operation doors for this editor."""
        super().__init__()
        self._door = door
        self._snapshot: tuple[ProfileOverview, AuthSyncReadiness] | None = None
        self._busy = False

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.aeat_auth.title"), classes="cadrumo-banner", markup=False)
        with VerticalScroll(id="aeat-auth-page"):
            yield Static(tr("tui.aeat_auth.method"), markup=False)
            yield Select(
                [(tr(f"auth.catalogue.{kind.value}_label"), kind.value) for kind in AuthProviderKind],
                allow_blank=True,
                id="aeat-auth-method",
            )
            yield Static(tr("tui.aeat_auth.route"), id="aeat-auth-route-label", markup=False)
            yield Select(
                [
                    (tr("flows.manager.action.auth_clave_movil_route_qr"), ClaveMovilRoute.QR.value),
                    (tr("flows.manager.action.auth_clave_movil_route_app_request"), ClaveMovilRoute.APP_REQUEST.value),
                ],
                value=DEFAULT_CLAVE_MOVIL_ROUTE.value,
                allow_blank=False,
                id="aeat-auth-route",
            )
            for index, path in enumerate(_FACT_PATHS):
                yield Static(tr(f"profile.schema.field.{path}.label"), id=f"aeat-auth-label-{index}", markup=False)
                yield Input(id=f"aeat-auth-field-{index}")
            yield Static(tr("tui.aeat_auth.document_hint"), id="aeat-auth-document-hint", markup=False)
            yield Static(tr("tui.aeat_auth.certificate_path"), id="aeat-auth-path-label", markup=False)
            yield Input(id="aeat-auth-path")
            yield Static("", id="aeat-auth-secret-label", markup=False)
            yield Input(password=True, id="aeat-auth-secret")
            yield Static(readiness_text(None), id="aeat-auth-readiness", markup=False)
            yield Static("", id="aeat-auth-message", markup=False)
            yield Button(tr("tui.aeat_auth.save"), id="aeat-auth-save", disabled=True)
            yield Button(tr("tui.aeat_auth.close"), id="aeat-auth-close")

    def on_mount(self) -> None:
        """Populate fields from persisted data without blocking the event loop."""
        self._visibility()
        self.run_worker(self._load(), group="aeat-auth-load")

    async def _load(self) -> None:
        """Keep the screen responsive while the native runtime reads the profile."""
        try:
            await self._apply(await self._door.snapshot())
        except Exception:
            self.query_one("#aeat-auth-readiness", Static).update(readiness_text(None))

    async def _apply(self, snapshot: tuple[ProfileOverview, AuthSyncReadiness]) -> None:
        self._snapshot = snapshot
        overview, readiness = snapshot
        self.query_one("#aeat-auth-method", Select).value = readiness.provider or Select.NULL
        if readiness.route:
            self.query_one("#aeat-auth-route", Select).value = readiness.route
        fields = {field.path: field for section in overview.sections for field in section.fields}
        for index, path in enumerate(_FACT_PATHS):
            field = fields.get(path)
            if field is not None:
                self.query_one(f"#aeat-auth-label-{index}", Static).update(field.label)
                self.query_one(f"#aeat-auth-field-{index}", Input).value = "" if field.masked else field.value or ""
        self.query_one("#aeat-auth-readiness", Static).update(readiness_text(readiness))
        self.query_one("#aeat-auth-save", Button).disabled = False
        self._visibility()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Offer fields for the selected method and route."""
        if event.select.id in {"aeat-auth-method", "aeat-auth-route"}:
            self._visibility()

    def _visibility(self) -> None:
        method = self.query_one("#aeat-auth-method", Select).value
        route = self.query_one("#aeat-auth-route", Select).value
        movil = method == AuthProviderKind.CLAVE_MOVIL.value
        certificate = method == AuthProviderKind.CERTIFICATE.value
        for selector in ("#aeat-auth-route", "#aeat-auth-route-label"):
            self.query_one(selector).display = movil
        self.query_one("#aeat-auth-document-hint").display = movil and route == ClaveMovilRoute.APP_REQUEST.value
        for index, path in enumerate(_FACT_PATHS):
            visible = index == 0 or (
                not certificate
                and method is not Select.NULL
                and (path == "auth.dni_nie" or (movil and route == ClaveMovilRoute.APP_REQUEST.value))
            )
            self.query_one(f"#aeat-auth-field-{index}").display = visible
            self.query_one(f"#aeat-auth-label-{index}").display = visible
        for selector in ("#aeat-auth-path", "#aeat-auth-path-label"):
            self.query_one(selector).display = certificate
        secret = certificate or method == AuthProviderKind.CLAVE_PERMANENTE.value
        self.query_one("#aeat-auth-secret").display = secret
        self.query_one("#aeat-auth-secret-label").display = secret
        self.query_one("#aeat-auth-secret-label", Static).update(
            tr("tui.aeat_auth.certificate_secret" if certificate else "tui.aeat_auth.password")
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save the selected authentication settings or return to synchronization."""
        if event.button.id == "aeat-auth-close":
            self.action_close()
        elif event.button.id == "aeat-auth-save" and not self._busy:
            self._busy = True
            self.run_worker(self._save(), group="aeat-auth-save")

    async def _save(self) -> None:
        method = self.query_one("#aeat-auth-method", Select).value
        if not isinstance(method, str):
            self.query_one("#aeat-auth-message", Static).update(sync_requirement_reason("auth_method_required"))
            self._busy = False
            return
        secret_field = self.query_one("#aeat-auth-secret", Input)
        secret = bytearray(secret_field.value, "utf-8") if secret_field.value and secret_field.display else None
        secret_field.value = ""
        fields = {
            path: self.query_one(f"#aeat-auth-field-{index}", Input).value
            for index, path in enumerate(_FACT_PATHS)
            if self.query_one(f"#aeat-auth-field-{index}").display
        }
        self._busy = True
        self.query_one("#aeat-auth-save", Button).disabled = True
        self.query_one("#aeat-auth-close", Button).disabled = True
        try:
            route = ClaveMovilRoute(str(self.query_one("#aeat-auth-route", Select).value))
            snapshot = await self._door.save(
                AuthProviderKind(method), route, fields, self.query_one("#aeat-auth-path", Input).value, secret
            )
            await self._apply(snapshot)
            self.query_one("#aeat-auth-path", Input).value = ""
            self.query_one("#aeat-auth-message", Static).update(tr("tui.aeat_auth.saved"))
        except Exception as error:
            message = tr("tui.aeat_auth.failed")
            cause = error.__cause__ if isinstance(error, AeatAuthFieldSaveError) else error
            if isinstance(error, AeatAuthFieldSaveError):
                field = (
                    next(
                        (
                            field
                            for section in self._snapshot[0].sections
                            for field in section.fields
                            if field.path == error.path
                        ),
                        None,
                    )
                    if self._snapshot
                    else None
                )
                message = tr("tui.aeat_auth.field_failed", field=field.label if field else error.path)
            if isinstance(cause, CadrumoError):
                message += "\n" + resolve_error_message(cause)
                if isinstance(cause, FrontendRefusedError):
                    message += "\n" + "\n".join(request_fault_line(fault) for fault in cause.request_faults)
            self.query_one("#aeat-auth-message", Static).update(message)
            try:
                await self._apply(await self._door.snapshot())
            except Exception:
                self._snapshot = None
                self.query_one("#aeat-auth-readiness", Static).update(readiness_text(None))
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))
            self._busy = False
            self.query_one("#aeat-auth-save", Button).disabled = False
            self.query_one("#aeat-auth-close", Button).disabled = False

    def action_close(self) -> None:
        """Return only after the current save settles."""
        if not self._busy:
            self.query_one("#aeat-auth-secret", Input).value = ""
            self.dismiss(self._snapshot)
