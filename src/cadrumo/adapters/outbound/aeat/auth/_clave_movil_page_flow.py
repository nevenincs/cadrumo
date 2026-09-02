"""Page-driving mixin for the Cl@ve Móvil auth provider.

This private helper surface supplies the browser automation that
:class:`ClaveMovilAuthProvider` uses for QR dispatch, non-QR DNI/NIE fallback
forms, post-auth landing waits, pending-request cancellation, and the own-name
representation gate. Selectors and path markers come from
:class:`AeatClaveMovilSurface`; browser interactions operate against the
minimal :class:`BrowserPagePort` protocol where possible.

Failure diagnostics captured during page driving are persisted as
:class:`SensitivityClass` ``SESSION`` objects in the active bucket secure
store. Own-name representation continuation is guarded with
:class:`RemoteOperation` before a browser action is executed.
"""

from __future__ import annotations

import abc
import asyncio
import base64
import contextlib
import json
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, NoReturn, Protocol, cast
from urllib.parse import urlsplit

from .....application.auth.protocols import BrowserPagePort
from .....core.config import unwrap_optional_secret
from .....core.errors.hierarchy import AeatLoginAssertionError
from .....core.external_constants import UTF_8_ENCODING
from .....core.logging import get_logger
from .....core.time.clock import now
from .....core.type_guards import is_str_keyed_dict
from .....domain.calculations.registry.remote_state_guard import RemoteOperation, assert_remote_operation_allowed
from ....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....persistence.storage.secure_object_namespaces import CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE
from .._html import parse_html
from .._playwright import PlaywrightError, PlaywrightTimeoutError
from .._representation_gate import (
    dismiss_pre303_alert_modal_if_present,
    wait_for_own_name_representation_selector,
)
from .clave_movil_support import (
    DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS as _DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
)
from .clave_movil_support import (
    DIAGNOSTIC_NAMESPACE as _DIAGNOSTIC_NAMESPACE,
)
from .clave_movil_support import (
    ClaveMovilApprovalTimeoutError,
    ClaveMovilConfigurationError,
    ClaveMovilFailureMode,
    mint_diagnostic_id,
)
from .clave_movil_support import (
    auth_browser_action_policy as _auth_browser_action_policy,
)
from .clave_movil_support import (
    classify_identity as _classify_identity,
)
from .clave_movil_support import (
    extract_verification_code_from_html as _extract_verification_code_from_html,
)
from .clave_movil_support import (
    url_diagnostic as _url_diagnostic,
)

if TYPE_CHECKING:
    from playwright.async_api import Dialog

    from .....core.config import Settings
    from .....core.external_constants import AeatClaveMovilSurface

log = get_logger(__name__)


class _ResponseAttributes(Protocol):
    """The response members the cancellation predicate reads."""

    url: str
    status: int


class _ResponseWaiter(Protocol):
    """The Playwright page call that waits for a matching response."""

    def __call__(
        self, predicate: Callable[[_ResponseAttributes], bool], *, timeout: float | None = ...
    ) -> Awaitable[object]: ...


class _ClaveMovilPageFlowMixin(abc.ABC):
    """Abstract contract consumed by Cl@ve Móvil page-driving helpers.

    Concrete subclasses (:class:`ClaveMovilAuthProvider`) supply the
    configured :class:`AeatClaveMovilSurface`, redacted diagnostic context, and
    navigation settings. The helper methods turn a :class:`BrowserPagePort`
    page into the selector clicks, wait-state checks, and encrypted diagnostics
    needed by the provider lifecycle.
    """

    # ── Abstract contract consumed by page-driving helpers ──────────────────
    # Instance-variable annotations: concrete subclasses assign these in
    # ``__init__``.  Declared here so type checkers resolve ``self._settings``
    # and ``self._navigation_timeout_ms`` without reaching into the subclass.

    _settings: Settings
    _navigation_timeout_ms: int

    @abc.abstractmethod
    def _clave_surface(self) -> AeatClaveMovilSurface:
        """Return the :class:`AeatClaveMovilSurface` constants from external config."""

    @abc.abstractmethod
    def _attempt_context(self) -> dict[str, object]:
        """Return a redacted diagnostic context dict for the current auth attempt."""

    # ── Page-driving helpers ────────────────────────────────────────────────

    @staticmethod
    def _target_path_from_url(target_url: str) -> str:
        """Return just the path portion of ``target_url`` (the selector ``ref=``)."""
        try:
            parsed = urlsplit(target_url)
        except ValueError:
            return target_url
        if not parsed.scheme or not parsed.netloc:
            return target_url
        tail = parsed.path or "/"
        if parsed.query:
            tail = f"{tail}?{parsed.query}"
        return tail

    async def _click_clave_movil_button(self, page: BrowserPagePort) -> None:
        """Click the configured Cl@ve entry button on the required browser page contract."""
        await page.click(self._clave_surface().authorize_button_selector)

    async def _extract_verification_code(self, page: BrowserPagePort) -> str | None:
        wait_for = getattr(page, "wait_for_selector", None)
        text_content = getattr(page, "text_content", None)
        if wait_for is not None and text_content is not None:
            selector = self._clave_surface().verification_code_selector
            try:
                await wait_for(selector, timeout=int(self._settings.cadrumo_browser_selector_probe_timeout_ms))
                raw: object = await text_content(selector)
            except (PlaywrightTimeoutError, PlaywrightError):
                raw = None
            if isinstance(raw, str) and raw.strip():
                return raw.strip()

        content = getattr(page, "content", None)
        if content is None:
            return None
        try:
            html = await content()
        except PlaywrightError:
            return None
        return _extract_verification_code_from_html(html)

    async def _drive_non_qr_fallback(self, page: BrowserPagePort, dni_nie: str) -> None:
        """Submit the configured non-QR DNI/NIE contrast form.

        DNI identities require ``CADRUMO_CLAVE_MOVIL_DNI_FECHA``; NIE identities
        require ``CADRUMO_CLAVE_MOVIL_NIE_SOPORTE``. The selectors come from
        :class:`AeatClaveMovilSurface`, and AEAT pending-request refusals are
        checked before control returns to :class:`ClaveMovilAuthProvider`.
        """
        click = getattr(page, "click", None)
        fill = getattr(page, "fill", None)
        type_text = getattr(page, "type", None)
        wait_for = getattr(page, "wait_for_selector", None)
        if click is None or fill is None or type_text is None or wait_for is None:
            raise AeatLoginAssertionError(
                "Playwright page missing click/fill/type/wait_for_selector; "
                "cannot drive the Cl@ve Móvil non-QR fallback",
            )
        surface = self._clave_surface()
        await click(surface.authorize_button_selector)
        # AEAT can return the 'petición pendiente' refusal in place of the non-QR
        # link page. Detect it here — as the QR route already does right after its
        # entry click — so a pending refusal fails fast with PENDING_PETITION_BLOCKED
        # instead of blocking the full navigation timeout on a link that never renders.
        await self._raise_if_pending_request_error(page)
        await wait_for(
            surface.non_qr_link_selector,
            timeout=self._navigation_timeout_ms,
        )
        await click(surface.non_qr_link_selector)
        await wait_for(surface.nif_input_selector, timeout=self._navigation_timeout_ms)
        await fill(surface.nif_input_selector, "")
        await type_text(surface.nif_input_selector, dni_nie)
        kind = _classify_identity(dni_nie)
        if kind == "DNI":
            await wait_for(surface.dni_fecha_visible_selector, timeout=self._navigation_timeout_ms)
            fecha = (self._settings.cadrumo_clave_movil_dni_fecha or "").strip()
            if not fecha:
                raise ClaveMovilConfigurationError(
                    "CADRUMO_CLAVE_MOVIL_DNI_FECHA is required for the non-QR DNI fallback (format YYYY-MM-DD).",
                )
            await type_text(surface.dni_fecha_input_selector, fecha)
        else:
            await wait_for(surface.nie_soporte_visible_selector, timeout=self._navigation_timeout_ms)
            soporte = unwrap_optional_secret(self._settings.cadrumo_clave_movil_nie_soporte).strip()
            if not soporte:
                raise ClaveMovilConfigurationError(
                    "CADRUMO_CLAVE_MOVIL_NIE_SOPORTE is required for the non-QR NIE fallback.",
                )
            await type_text(surface.nie_soporte_input_selector, soporte)
        await wait_for(surface.continue_button_visible_selector, timeout=self._navigation_timeout_ms)
        await click(surface.continue_button_selector)
        await self._raise_if_pending_request_error(page)

    async def _assert_push_wait_state(
        self,
        page: BrowserPagePort,
        *,
        target_path: str,
        verification_code: str | None,
        used_non_qr_fallback: bool,
    ) -> None:
        """Require an AEAT-observed Cl@ve waiting state before waiting further.

        The wait page is accepted when AEAT shows the expected URL markers,
        configured wait text, or a verification code. If none is observed, the
        helper persists a :class:`SensitivityClass` ``SESSION`` diagnostic and
        raises :class:`ClaveMovilApprovalTimeoutError` with the diagnostic id.
        """
        await self._raise_if_pending_request_error(page)
        current_url = getattr(page, "url", "") or ""
        surface = self._clave_surface()
        if target_path in current_url and surface.selector_access_path_marker not in current_url:
            return
        if verification_code:
            return

        content = getattr(page, "content", None)
        html = ""
        if content is not None:
            try:
                html = await content()
            except PlaywrightError:
                html = ""
        normalized = " ".join(html.replace("\xa0", " ").split()).lower()
        wait_markers = tuple(marker.lower() for marker in surface.wait_text_markers)
        url_markers = (
            surface.obtener_clave_movil_path_marker,
            surface.obtener_clave_movil_qr_path_marker,
        )
        has_wait_marker = any(marker in normalized for marker in wait_markers)
        has_wait_url = any(marker in current_url for marker in url_markers)
        if has_wait_marker or has_wait_url:
            log.info(
                "ClaveMovilAuthProvider: detected Cl@ve wait state url=%s non_qr=%s verification_code_present=%s",
                current_url,
                used_non_qr_fallback,
                bool(verification_code),
            )
            return

        diagnostic_id = await self._dump_diagnostic(page, reason="push-wait-state-not-reached")
        raise ClaveMovilApprovalTimeoutError(
            "AEAT Cl@ve Móvil did not reach a browser-observed confirmation waiting state "
            "after submitting the login form.",
            failure_mode=ClaveMovilFailureMode.PUSH_WAIT_STATE_NOT_REACHED,
            context={
                "reason": "aeat-clave-movil-wait-state-not-reached",
                "current_url": _url_diagnostic(current_url),
                "target_path": target_path,
                "used_non_qr_fallback": used_non_qr_fallback,
                "verification_code_present": bool(verification_code),
                "diagnostic_id": diagnostic_id,
            },
        )

    async def _raise_if_pending_request_error(self, page: BrowserPagePort) -> None:
        """Detect AEAT's 'petición pendiente' refusal page and fail fast.

        After the configured continue button is clicked, AEAT sometimes returns the
        non-QR landing page in an error state: "No ha sido posible
        generar una nueva petición de autenticación con Cl@ve Móvil.
        Por su seguridad, acceda a la APP Cl@ve … y rechace la petición
        pendiente — o espere a que caduque tras un máximo de 5 minutos."
        This happens when a prior login left an unresolved request
        alive server-side. The polling loop that normally redirects on
        browser-side completion is never rendered, so the authenticator would otherwise
        sit on the page until the outer timeout fires. Fail fast with the
        observed pending-request facts.
        """
        content = getattr(page, "content", None)
        if content is None:
            return
        try:
            html = await content()
        except PlaywrightError:
            return
        normalized = " ".join(html.replace("\xa0", " ").split()).lower()
        pending_markers = self._clave_surface().pending_petition_text_markers
        if any(marker in normalized for marker in pending_markers):
            diagnostic_id = await self._dump_diagnostic(page, reason="pending-request-refusal")
            raise ClaveMovilApprovalTimeoutError(
                "AEAT refused to issue a new Cl@ve Móvil authentication request: a prior "
                "authentication request is still pending server-side.",
                failure_mode=ClaveMovilFailureMode.PENDING_PETITION_BLOCKED,
                context={
                    "reason": "aeat-refused-new-clave-movil-petition",
                    "url": getattr(page, "url", "") or "",
                    "detected_markers": tuple(marker for marker in pending_markers if marker in normalized),
                    "diagnostic_id": diagnostic_id,
                },
                translated_message="adapters.aeat.clave_movil.errors.pending_petition_blocked",
            )

    async def _cancel_pending_auth_request(self, page: BrowserPagePort) -> None:
        """Best-effort cancellation for a Cl@ve request left open by timeout.

        Cancellation is cleanup for a prior :class:`ClaveMovilApprovalTimeoutError`.
        Any failure is logged and suppressed so the original auth failure remains
        the error returned to the provider caller.
        """
        current_url = getattr(page, "url", "") or ""
        if self._clave_surface().obtener_clave_movil_path_marker not in current_url:
            return
        evaluate = getattr(page, "evaluate", None)
        try:
            if evaluate is not None:
                clave_global = json.dumps(self._clave_surface().obtener_clave_movil_browser_global)
                cancelled = await asyncio.wait_for(
                    evaluate(
                        f"""
                        () => {{
                          const button = document.querySelector("#botonCancelar");
                          if (button && typeof button.click === "function") {{
                            button.click();
                            return true;
                          }}
                          const clave = window[{clave_global}];
                          if (clave && typeof clave.cancelarPeticion === "function") {{
                            clave.cancelarPeticion();
                            return true;
                          }}
                          return false;
                        }}
                        """,
                    ),
                    timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                )
                if cancelled and await self._wait_for_cancel_confirmation(page):
                    log.info("ClaveMovilAuthProvider: confirmed cancellation of pending Cl@ve request")
                    return
            click = getattr(page, "click", None)
            if click is not None:
                await asyncio.wait_for(
                    click("#botonCancelar"),
                    timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                )
                if await self._wait_for_cancel_confirmation(page):
                    log.info("ClaveMovilAuthProvider: confirmed cancellation of pending Cl@ve request")
                    return
            log.warning("ClaveMovilAuthProvider: pending Cl@ve cancellation was requested but not confirmed")
        except Exception as exc:  # cancellation is cleanup; preserve the original auth timeout
            log.warning("ClaveMovilAuthProvider: pending Cl@ve cancellation failed: %s", exc)

    async def _wait_for_cancel_confirmation(self, page: BrowserPagePort) -> bool:
        # The port declares no ``wait_for_response``; only the Playwright-backed
        # page carries it. State the call this cleanup makes.
        wait_for_response = cast("_ResponseWaiter | None", getattr(page, "wait_for_response", None))
        if wait_for_response is not None:
            surface = self._clave_surface()
            try:
                response = await asyncio.wait_for(
                    wait_for_response(
                        lambda candidate: bool(
                            surface.cancelar_clave_movil_path_marker in str(getattr(candidate, "url", ""))
                            and int(getattr(candidate, "status", 599)) < 400
                        ),
                        timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS * 1000,
                    ),
                    timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                )
                return int(getattr(response, "status", 599)) < 400
            except (TimeoutError, PlaywrightTimeoutError, PlaywrightError):
                return False

        wait_for_timeout = getattr(page, "wait_for_timeout", None)
        if wait_for_timeout is not None:
            with contextlib.suppress(TimeoutError, PlaywrightTimeoutError):
                await asyncio.wait_for(
                    wait_for_timeout(1000),
                    timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                )
        else:
            await asyncio.sleep(1)
        return not await self._page_still_shows_pending_request(page)

    async def _page_still_shows_pending_request(self, page: BrowserPagePort) -> bool:
        content = getattr(page, "content", None)
        if content is None:
            return True
        try:
            html = await content()
        except PlaywrightError:
            return True
        normalized = " ".join(html.replace("\xa0", " ").split()).lower()
        pending_markers = self._clave_surface().pending_petition_text_markers
        return any(marker in normalized for marker in pending_markers)

    @staticmethod
    def _attach_dialog_autodismiss(page: BrowserPagePort) -> None:
        """Auto-accept any JS dialog AEAT pops during login.

        Playwright blocks the page until ``dialog`` events are handled;
        AEAT sometimes surfaces cookie / representation-consent modals
        that would otherwise silently stall the authenticator.
        """
        on = getattr(page, "on", None)
        if on is None:
            return

        pending: set[asyncio.Task[object]] = set()

        def _handle(dialog: Dialog) -> None:
            accept = getattr(dialog, "accept", None)
            if accept is None:
                return
            log.debug(
                "ClaveMovilAuthProvider: auto-accepting dialog type=%s message=%r",
                getattr(dialog, "type", "?"),
                getattr(dialog, "message", ""),
            )
            result = accept()
            if asyncio.iscoroutine(result):
                task = asyncio.create_task(result)
                pending.add(task)
                task.add_done_callback(pending.discard)

        on("dialog", _handle)

    async def _dump_diagnostic(self, page: BrowserPagePort, *, reason: str) -> str | None:
        """Capture page URL + HTML + screenshot on login failure for offline triage.

        Stores artefacts as encrypted session-class objects so a human
        can inspect what AEAT served at the moment the authenticator
        gave up without leaving bearer-equivalent page state in
        plaintext files. The secure object is written with
        :class:`SensitivityClass` ``SESSION`` classification under the Cl@ve
        diagnostic namespace.
        """
        try:
            captured_at = now()
            diagnostic_id = mint_diagnostic_id(captured_at)
            url = getattr(page, "url", "") or ""
            payload: dict[str, object] = {
                "diagnostic_id": diagnostic_id,
                "reason": reason,
                "url": url,
                "captured_at": captured_at.isoformat(),
                "auth_attempt": self._attempt_context(),
            }
            if self._is_authenticated_representation_landing(url):
                payload.update(
                    phone_state="app_prompted_and_accepted",
                    phone_state_source="aeat_authenticated_landing",
                    phone_state_observed_at=captured_at.isoformat(),
                )
            content = getattr(page, "content", None)
            if content is not None:
                try:
                    payload["html"] = await asyncio.wait_for(
                        content(),
                        timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                    )
                except (TimeoutError, PlaywrightTimeoutError):
                    payload["html_capture_error"] = "timeout"
            screenshot = getattr(page, "screenshot", None)
            if screenshot is not None:
                try:
                    image = await asyncio.wait_for(
                        screenshot(full_page=True),
                        timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                    )
                    if isinstance(image, (bytes, bytearray)):
                        payload["screenshot_png_base64"] = base64.b64encode(bytes(image)).decode("ascii")
                except (TimeoutError, PlaywrightTimeoutError):
                    payload["screenshot_capture_error"] = "timeout"
            secure_object_repository_for_active_bucket().save(
                namespace=_DIAGNOSTIC_NAMESPACE,
                object_key=diagnostic_id,
                classification=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.sensitivity,
                schema_version=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.schema_version,
                written_at=captured_at,
                payload=json.dumps(payload, sort_keys=True, default=str).encode(UTF_8_ENCODING),
            )
            log.warning(
                "ClaveMovilAuthProvider: encrypted diagnostic captured id=%s (url=%s reason=%s)",
                diagnostic_id,
                url,
                reason,
            )
            return diagnostic_id
        except Exception:  # diagnostic dump is best-effort; Playwright screenshot/content errors must not raise
            log.warning("ClaveMovilAuthProvider: diagnostic dump failed", exc_info=True)
            return None

    def _is_authenticated_representation_landing(self, url: str) -> bool:
        """Return whether AEAT exposed its post-Cl@ve representation gate."""
        try:
            path = urlsplit(url).path
        except ValueError:
            return False
        surface = self._clave_surface()
        return surface.dialogo_representacion_path_marker in path and surface.selector_access_path_marker not in path

    @staticmethod
    def _exception_already_has_diagnostic(exc: Exception) -> bool:
        """Return whether an auth exception already carries a diagnostic id."""
        context = getattr(exc, "context", None)
        if not is_str_keyed_dict(context):
            return False
        return bool(context.get("diagnostic_id"))

    async def _wait_for_post_auth_landing(
        self,
        page: BrowserPagePort,
        target_path: str,
        timeout_ms: int,
    ) -> None:
        """Poll until the browser reaches ``target_path`` or timeout.

        After Cl@ve completion AEAT may interpose the representation
        dispatcher. Only the authenticated user's own-name continuation
        is allowed here; representative/third-party action remains
        fail-closed because it would require represented-taxpayer data.
        """
        deadline = time.perf_counter() + timeout_ms / 1000
        while time.perf_counter() < deadline:
            current = getattr(page, "url", "") or ""
            surface = self._clave_surface()
            await self._raise_if_pending_request_error(page)
            if target_path in current and surface.selector_access_path_marker not in current:
                return
            # Only match the representation dispatcher when it is the URL PATH,
            # not the `ref=` query parameter (which contains it URL-
            # encoded on the push-waiting page).
            try:
                current_path = urlsplit(current).path
            except ValueError:
                current_path = ""
            if (
                surface.dialogo_representacion_path_marker in current_path
                and surface.selector_access_path_marker not in current
            ):
                await self._continue_own_name_representation(page)
            await asyncio.sleep(0.5)
        log.warning(
            "ClaveMovilAuthProvider: post-auth landing timeout target_path=%r timeout_ms=%d",
            target_path,
            timeout_ms,
        )
        raise TimeoutError(f"page did not navigate to {target_path!r} within {timeout_ms}ms")

    async def _continue_own_name_representation(self, page: BrowserPagePort) -> None:
        """Continue only through AEAT's authenticated own-name selector.

        The click is checked as a :class:`RemoteOperation` browser action before
        execution. Representative or unknown representation states raise
        :class:`AeatLoginAssertionError` instead of selecting a third-party path.
        """
        assert_remote_operation_allowed(
            _auth_browser_action_policy(self._settings),
            RemoteOperation(
                kind="browser_action",
                action=self._settings.external_constants().aeat.pre303.representation_own_name_action_label,
            ),
        )
        pre303 = self._settings.external_constants().aeat.pre303
        wait_for = getattr(page, "wait_for_selector", None)
        click = getattr(page, "click", None)
        if wait_for is None or click is None:
            raise AeatLoginAssertionError(
                "Playwright page does not expose wait_for_selector()/click(); "
                "cannot drive AEAT own-name representation gate",
            )
        try:
            selected_own_name = await self._wait_for_own_name_representation_selector(page)
            await self._dismiss_pre303_alert_modal_if_present(page)
            if not await self._own_name_representation_is_already_selected(page):
                await click(selected_own_name)
            await click(pre303.representation_submit_selector)
        except PlaywrightError as exc:
            raise AeatLoginAssertionError(
                "AEAT representation gate did not expose the own-name continuation expected for the "
                "authenticated profile user.",
                context={
                    "failure_mode": "representation_gate_own_name_unavailable",
                    "landing_url": getattr(page, "url", None),
                    "blocked_operation": "representative_or_unknown_representation_gate",
                },
            ) from exc

    async def _wait_for_own_name_representation_selector(self, page: BrowserPagePort) -> str:
        """Return the configured own-name selector that AEAT renders first."""
        pre303 = self._settings.external_constants().aeat.pre303

        def _raise_configuration_error(message: str) -> NoReturn:
            raise AeatLoginAssertionError(message)

        return await wait_for_own_name_representation_selector(
            page,
            own_name_label_selector=pre303.representation_own_name_label_selector,
            own_name_selector=pre303.representation_own_name_selector,
            probe_timeout_ms=self._settings.cadrumo_browser_selector_probe_timeout_ms,
            raise_configuration_error=_raise_configuration_error,
        )

    async def _own_name_representation_is_already_selected(self, page: BrowserPagePort) -> bool:
        """Return whether AEAT already selected the own-name representation radio."""
        pre303 = self._settings.external_constants().aeat.pre303
        content = getattr(page, "content", None)
        if content is None:
            return False
        html = await content()
        soup = parse_html(html)
        own_name = soup.select_one(pre303.representation_own_name_selector)
        representative = soup.select_one(pre303.representation_representative_selector)
        if representative is not None and _html_input_checked(representative):
            raise AeatLoginAssertionError(
                "AEAT representation gate has representative mode selected; refusing to continue.",
                context={
                    "failure_mode": "representation_gate_representative_selected",
                    "landing_url": getattr(page, "url", None),
                    "blocked_operation": "representative_or_unknown_representation_gate",
                },
            )
        return own_name is not None and _html_input_checked(own_name)

    async def _dismiss_pre303_alert_modal_if_present(self, page: BrowserPagePort) -> None:
        """Dismiss the visible Pre303 alert modal before submitting own-name access.

        Delegates to the canonical, collapsed implementation in
        :func:`~adapters.outbound.aeat._representation_gate.dismiss_pre303_alert_modal_if_present`
        (operator directive: this and the sede wallet reader's independent
        copy were a critical double declaration; the sede copy is deleted,
        this predicate is canonical). This caller declines silently when the
        modal is present but not shown, matching its own pre-collapse
        behaviour unchanged.
        """
        pre303 = self._settings.external_constants().aeat.pre303
        await dismiss_pre303_alert_modal_if_present(
            page,
            alert_modal_selector=pre303.alert_modal_selector,
            alert_continue_button_text=pre303.alert_continue_button_text,
        )


def _html_input_checked(node: object) -> bool:
    has_attr = getattr(node, "has_attr", None)
    return bool(has_attr is not None and has_attr("checked"))


__all__ = ["_ClaveMovilPageFlowMixin"]
