"""Shared Cl@ve Movil provider test harness."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from pydantic import SecretStr

from ......core.config import Settings
from ..._playwright import PlaywrightError, PlaywrightTimeoutError

if TYPE_CHECKING:
    from .._authenticator import BrowserResponseLike

_EXTERNAL = Settings.external_constants()
_DOMAINS = _EXTERNAL.aeat.domains
_CLAVE_SURFACE = _EXTERNAL.aeat.clave_movil
_PRE303_SURFACE = _EXTERNAL.aeat.pre303


def _run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


def _aeat_url(origin: str, path: str) -> str:
    return f"{origin}{path}"


class _RecordingPage:
    def __init__(
        self,
        *,
        target_path: str,
        verification_code: str = "YLL",
        authenticated: bool = False,
    ) -> None:
        self._target_path = target_path
        self._verification_code = verification_code
        self._authenticated = authenticated
        self.clicks: list[str] = []
        self.fills: list[tuple[str, str]] = []
        self.types: list[tuple[str, str]] = []
        self.gotos: list[str] = []
        self.url: str = ""
        self.closed = False

    async def goto(self, url: str, *, timeout: float | None = None) -> BrowserResponseLike | None:
        del timeout
        self.gotos.append(url)
        if self._authenticated and _CLAVE_SURFACE.selector_access_path_marker in url:
            self.url = _aeat_url(_DOMAINS.www6, self._target_path)
        else:
            self.url = url

        class _RecordingResponse:
            status = 200

        return _RecordingResponse()

    async def click(self, selector: str) -> None:
        self.clicks.append(selector)
        if selector == _CLAVE_SURFACE.authorize_button_selector:
            self.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.obtener_clave_movil_qr_path)
        elif selector == _CLAVE_SURFACE.non_qr_link_selector:
            self.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.autentica_dni_nie_contraste_path)
        elif selector in (_CLAVE_SURFACE.continue_button_selector, _PRE303_SURFACE.representation_submit_selector):
            self.url = _aeat_url(_DOMAINS.www6, self._target_path)

    async def fill(self, selector: str, value: str) -> None:
        self.fills.append((selector, value))

    async def type(self, selector: str, value: str, *, delay: float | None = None) -> None:
        del delay
        self.types.append((selector, value))

    async def wait_for_selector(self, selector: str, *, timeout: float | None = None) -> None:
        del selector, timeout

    async def text_content(self, selector: str) -> str | None:
        if selector == _CLAVE_SURFACE.verification_code_selector:
            self.url = _aeat_url(_DOMAINS.www6, self._target_path)
            return self._verification_code
        return None

    async def content(self) -> str:
        return "<html></html>"

    async def wait_for_url(self, matcher: str | Callable[[str], bool], *, timeout: float | None = None) -> None:
        del timeout
        self.url = _aeat_url(_DOMAINS.www6, self._target_path)
        if not isinstance(matcher, str) and not matcher(self.url):
            raise TimeoutError("matcher rejected simulated URL")

    async def close(self) -> None:
        self.closed = True


class _InitialNavigationTimeoutPage(_RecordingPage):
    @override
    async def goto(self, url: str, *, timeout: float | None = None) -> BrowserResponseLike | None:
        del timeout
        self.gotos.append(url)
        raise PlaywrightTimeoutError("selector navigation timed out")


class _RepresentationAlertPage(_RecordingPage):
    @override
    async def content(self) -> str:
        return f"""
        <div id="{_PRE303_SURFACE.alert_modal_selector.lstrip("#")}" class="modal show">
          <button>{_PRE303_SURFACE.alert_continue_button_text.title()}</button>
        </div>
        """


class _OwnNameInputOnlyRepresentationPage(_RecordingPage):
    @override
    async def wait_for_selector(self, selector: str, *, timeout: float | None = None) -> None:
        del timeout
        if selector == _PRE303_SURFACE.representation_own_name_label_selector:
            raise PlaywrightError("label not present")
        if selector == _PRE303_SURFACE.representation_own_name_selector:
            return
        await super().wait_for_selector(selector)


class _SelectorDispatchPage(_RecordingPage):
    @override
    async def goto(self, url: str, *, timeout: float | None = None) -> BrowserResponseLike | None:
        del timeout
        self.gotos.append(url)
        self.url = url

        class _RecordingResponse:
            status = 200

        return _RecordingResponse()

    @override
    async def click(self, selector: str) -> None:
        self.clicks.append(selector)
        if selector == _CLAVE_SURFACE.authorize_button_selector:
            self.url = _aeat_url(_DOMAINS.www1, self._target_path)


class _PendingPetitionPage(_RecordingPage):
    @override
    async def content(self) -> str:
        return (
            "<html><body>No ha sido posible generar una nueva petición de autenticación "
            "con Cl@ve Móvil. Rechace la petición pendiente en la APP Cl@ve.</body></html>"
        )


class _NoPushWaitStatePage(_RecordingPage):
    @override
    async def content(self) -> str:
        return "<html><body>Servicio no disponible temporalmente</body></html>"


class _CancelResponse:
    def __init__(self, *, status: int = 200) -> None:
        self.status = status
        self.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.cancelar_clave_movil_path)


class _CancelableClavePage(_RecordingPage):
    def __init__(self, *, target_path: str, status: int = 200) -> None:
        super().__init__(target_path=target_path)
        self.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.obtener_clave_movil_non_qr_path)
        self.cancel_response = _CancelResponse(status=status)
        self.evaluate_calls = 0
        self.wait_for_response_calls = 0
        self.evaluated_script = ""

    async def evaluate(self, script: str) -> bool:
        self.evaluated_script = script
        self.evaluate_calls += 1
        return True

    async def wait_for_response(self, matcher: Callable[[object], bool], *, timeout: float | None = None) -> object:
        del timeout
        self.wait_for_response_calls += 1
        if matcher(self.cancel_response):
            return self.cancel_response
        raise TimeoutError("cancel response matcher did not match")


class _RecordingContext:
    def __init__(
        self,
        *,
        target_path: str,
        verification_code: str = "YLL",
        authenticated: bool = False,
    ) -> None:
        self._target_path = target_path
        self._verification_code = verification_code
        self._authenticated = authenticated
        self.pages: list[_RecordingPage] = []
        self.closed = False
        self._storage_state: dict[str, object] = {
            "cookies": [{"name": "AEAT_SESSION"}],
            "origins": [],
        }

    async def new_page(self) -> _RecordingPage:
        page = _RecordingPage(
            target_path=self._target_path,
            verification_code=self._verification_code,
            authenticated=self._authenticated,
        )
        self.pages.append(page)
        return page

    async def storage_state(self) -> dict[str, object]:
        return self._storage_state

    async def close(self) -> None:
        self.closed = True


class _HangingCloseContext(_RecordingContext):
    @override
    async def close(self) -> None:
        await asyncio.sleep(60)


class _SelectorDispatchContext(_RecordingContext):
    @override
    async def new_page(self) -> _SelectorDispatchPage:
        page = _SelectorDispatchPage(target_path=self._target_path)
        self.pages.append(page)
        return page


class _InitialNavigationTimeoutContext(_RecordingContext):
    @override
    async def new_page(self) -> _InitialNavigationTimeoutPage:
        page = _InitialNavigationTimeoutPage(target_path=self._target_path)
        self.pages.append(page)
        return page


class _RecordingBrowserSession:
    """Recording browser session for Cl@ve Movil protocol-level tests."""

    def __init__(self, *, target_path: str, verification_code: str = "YLL") -> None:
        self._target_path = target_path
        self._verification_code = verification_code
        self.contexts: list[_RecordingContext] = []
        self.closed = False

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _RecordingContext:
        del provisioner
        authenticated = storage_state_path is not None or storage_state is not None
        context = _RecordingContext(
            target_path=self._target_path,
            verification_code=self._verification_code,
            authenticated=authenticated,
        )
        self.contexts.append(context)
        return context

    async def close(self) -> None:
        self.closed = True


class _HangingCloseBrowserSession(_RecordingBrowserSession):
    @override
    async def close(self) -> None:
        await asyncio.sleep(60)


class _SelectorDispatchBrowserSession(_RecordingBrowserSession):
    @override
    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _SelectorDispatchContext:
        del provisioner, storage_state_path, storage_state
        context = _SelectorDispatchContext(target_path=self._target_path)
        self.contexts.append(context)
        return context


class _InitialNavigationTimeoutBrowserSession(_RecordingBrowserSession):
    @override
    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _InitialNavigationTimeoutContext:
        del provisioner, storage_state_path, storage_state
        context = _InitialNavigationTimeoutContext(target_path=self._target_path)
        self.contexts.append(context)
        return context


def _settings_for(tmp_path: Path, **env: str) -> Settings:
    env_overrides = {key.lower(): value for key, value in env.items()}
    expected_keys = {
        "aeat_clave_movil_dni_fecha",
        "aeat_clave_movil_dni_nie",
        "aeat_clave_movil_nie_soporte",
        "aeat_clave_prefer_non_qr",
    }
    unexpected = set(env_overrides) - expected_keys
    assert unexpected == set()
    return Settings(
        aeat_token_dir=tmp_path,
        aeat_local_storage_root=tmp_path / "storage",
        aeat_clave_prefer_non_qr=_bool_setting(env_overrides.get("aeat_clave_prefer_non_qr")),
        aeat_clave_movil_dni_nie=_secret_or_none(env_overrides.get("aeat_clave_movil_dni_nie")),
        aeat_clave_movil_dni_fecha=env_overrides.get("aeat_clave_movil_dni_fecha"),
        aeat_clave_movil_nie_soporte=_secret_or_none(env_overrides.get("aeat_clave_movil_nie_soporte")),
    )


def _secret_or_none(value: str | None) -> SecretStr | None:
    return None if value is None else SecretStr(value)


def _bool_setting(value: str | None) -> bool:
    return False if value is None else value.lower() == "true"
