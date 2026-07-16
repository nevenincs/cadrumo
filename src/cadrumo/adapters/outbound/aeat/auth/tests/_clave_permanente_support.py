"""Shared Cl@ve Permanente provider test harness.

The helpers in this module provide recording browser/page stand-ins for the
protocol-level Cl@ve Permanente tests. They exercise the same browser-session
shape used by the provider while keeping credential handling, selector
navigation, invalid-credential, and SMS-elevation branches deterministic.

See Also:
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteAuthProvider`
        Provider under test for DNI/NIE + password AEAT read-path login.
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteSessionDetail`
        Public session detail shape asserted by the protocol and live probes.
    :mod:`~adapters.outbound.aeat.auth.tests.test_clave_permanente`
        Protocol-level suite that consumes these recording browser sessions.
    :mod:`~adapters.outbound.aeat.auth.tests.test_clave_permanente_live`
        Live Playwright probe that validates the same provider against AEAT's
        real Cl@ve Permanente surface.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from pydantic import SecretStr

from ......core.config import Settings
from ..._playwright import PlaywrightTimeoutError

if TYPE_CHECKING:
    from .._authenticator import BrowserResponseLike

_EXTERNAL = Settings.external_constants()
_DOMAINS = _EXTERNAL.aeat.domains
_CLAVE_SURFACE = _EXTERNAL.aeat.clave_permanente


def _run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


def _aeat_url(origin: str, path: str) -> str:
    return f"{origin}{path}"


class _RecordingPage:
    """Records fill/click/goto calls; simulates a successful headless login."""

    def __init__(self, *, target_path: str, html: str = "<html></html>") -> None:
        self._target_path = target_path
        self._html = html
        self.clicks: list[str] = []
        self.fills: list[tuple[str, str]] = []
        self.gotos: list[str] = []
        self.url: str = ""
        self.closed = False

    async def goto(self, url: str, *, timeout: float | None = None) -> BrowserResponseLike | None:
        del timeout
        self.gotos.append(url)
        self.url = url

        class _RecordingResponse:
            ok = True
            status = 200

        return _RecordingResponse()

    async def click(self, selector: str) -> None:
        self.clicks.append(selector)

    async def fill(self, selector: str, value: str) -> None:
        self.fills.append((selector, value))

    async def content(self) -> str:
        return self._html

    async def wait_for_url(self, matcher: str, *, timeout: float | None = None) -> None:
        del timeout, matcher
        self.url = _aeat_url(_DOMAINS.www6, self._target_path)

    async def close(self) -> None:
        self.closed = True


class _InitialNavigationTimeoutPage(_RecordingPage):
    @override
    async def goto(self, url: str, *, timeout: float | None = None) -> BrowserResponseLike | None:
        del timeout
        self.gotos.append(url)
        raise PlaywrightTimeoutError("selector navigation timed out")


class _InvalidCredentialsPage(_RecordingPage):
    def __init__(self, *, target_path: str) -> None:
        super().__init__(
            target_path=target_path,
            html=f"<html><body>{_CLAVE_SURFACE.invalid_credentials_marker}</body></html>",
        )


class _ElevationRequiredPage(_RecordingPage):
    def __init__(self, *, target_path: str) -> None:
        super().__init__(
            target_path=target_path,
            html=f"<html><body>{_CLAVE_SURFACE.elevation_sms_marker}</body></html>",
        )


class _RecordingContext:
    def __init__(self, *, target_path: str, page_factory: type[_RecordingPage] = _RecordingPage) -> None:
        self._target_path = target_path
        self._page_factory = page_factory
        self.pages: list[_RecordingPage] = []
        self.closed = False
        self._storage_state: dict[str, object] = {
            "cookies": [{"name": "AEAT_SESSION"}],
            "origins": [],
        }

    async def new_page(self) -> _RecordingPage:
        page = self._page_factory(target_path=self._target_path)
        self.pages.append(page)
        return page

    async def storage_state(self) -> dict[str, object]:
        return self._storage_state

    async def close(self) -> None:
        self.closed = True


class _RecordingBrowserSession:
    """Recording browser session for Cl@ve Permanente protocol-level tests."""

    def __init__(self, *, target_path: str, page_factory: type[_RecordingPage] = _RecordingPage) -> None:
        self._target_path = target_path
        self._page_factory = page_factory
        self.contexts: list[_RecordingContext] = []
        self.closed = False
        self.profile = None

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _RecordingContext:
        del provisioner, storage_state_path, storage_state
        context = _RecordingContext(target_path=self._target_path, page_factory=self._page_factory)
        self.contexts.append(context)
        return context

    async def close(self) -> None:
        self.closed = True


class _InitialNavigationTimeoutBrowserSession(_RecordingBrowserSession):
    def __init__(self, *, target_path: str) -> None:
        super().__init__(target_path=target_path, page_factory=_InitialNavigationTimeoutPage)


class _InvalidCredentialsBrowserSession(_RecordingBrowserSession):
    def __init__(self, *, target_path: str) -> None:
        super().__init__(target_path=target_path, page_factory=_InvalidCredentialsPage)


class _ElevationRequiredBrowserSession(_RecordingBrowserSession):
    def __init__(self, *, target_path: str) -> None:
        super().__init__(target_path=target_path, page_factory=_ElevationRequiredPage)


def _settings_for(tmp_path: Path, **env: str) -> Settings:
    env_overrides = {key.lower(): value for key, value in env.items()}
    expected_keys = {
        "cadrumo_clave_permanente_dni_nie",
        "cadrumo_clave_permanente_password",
    }
    unexpected = set(env_overrides) - expected_keys
    assert unexpected == set()
    return Settings(
        cadrumo_token_dir=tmp_path,
        cadrumo_local_storage_root=tmp_path / "storage",
        cadrumo_clave_permanente_dni_nie=_secret_or_none(env_overrides.get("cadrumo_clave_permanente_dni_nie")),
        cadrumo_clave_permanente_password=_secret_or_none(env_overrides.get("cadrumo_clave_permanente_password")),
    )


def _secret_or_none(value: str | None) -> SecretStr | None:
    return None if value is None else SecretStr(value)
