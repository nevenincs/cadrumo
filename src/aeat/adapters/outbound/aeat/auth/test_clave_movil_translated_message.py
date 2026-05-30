"""Real-behavior tests for AeatLoginAssertionError translated_message threading (S276).

Coverage:
- S276-A: _load_persisted raises AeatLoginAssertionError with translated_message
  set to the no_persisted_session key when session_store.load returns None.
- S276-B: probe_persisted_session raises AeatLoginAssertionError with
  translated_message set to no_persisted_session when no persisted session exists.
- S276-C: resume_session raises AeatLoginAssertionError with translated_message
  set to session_expired when the idle deadline has passed.
- S276-D: resume_session raises AeatLoginAssertionError with translated_message
  set to storage_state_hash_mismatch when the storage-state hash does not match.
- S276-E: _click_clave_movil_button raises AeatLoginAssertionError with
  translated_message set to page_missing_click when page has no click attribute.
- S276-F: locale keys for all four sites resolve to non-placeholder strings in
  the catalogue.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .....core.config import Settings
from .....core.i18n import tr
from .....tests.secure_sql import isolated_runtime_profile
from ._authenticator import AeatLoginAssertionError
from ._clave_movil import ClaveMovilAuthProvider, _ClaveMovilSessionMetadata
from ._providers import AuthProviderKind

if TYPE_CHECKING:
    pass

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]

_CLAVE_MOVIL_LOCALE_KEYS = [
    "adapters.auth.clave_movil.errors.no_persisted_session",
    "adapters.auth.clave_movil.errors.session_expired",
    "adapters.auth.clave_movil.errors.storage_state_hash_mismatch",
    "adapters.auth.clave_movil.errors.page_missing_click",
]


@pytest.fixture(autouse=True)
def _isolated_secure_session_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="clave-movil-translated-message-test"):
        yield


def _settings_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    from pydantic_settings import SettingsConfigDict

    for name in Settings.env_var_names():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path))
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    class _IsolatedSettings(Settings):
        model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8", env_ignore_empty=True)

    return _IsolatedSettings()


class _MinimalContext:
    """Minimal browser context stand-in that records new_page calls."""

    def __init__(self) -> None:
        self._storage_state: dict[str, object] = {"cookies": [{"name": "AEAT_SESSION"}], "origins": []}
        self.closed = False

    async def new_page(self) -> _MinimalPage:
        return _MinimalPage()

    async def storage_state(self) -> dict[str, object]:
        return self._storage_state

    async def close(self) -> None:
        self.closed = True


class _MinimalPage:
    """Page stand-in that omits the click attribute to trigger page_missing_click."""

    def __init__(self) -> None:
        self.url = ""


class _MinimalBrowserSession:
    def __init__(self) -> None:
        self.contexts: list[_MinimalContext] = []
        self.closed = False

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _MinimalContext:
        ctx = _MinimalContext()
        self.contexts.append(ctx)
        return ctx

    async def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# S276-A: _load_persisted raises with no_persisted_session translated_message
# ---------------------------------------------------------------------------


def test_load_persisted_no_session_carries_translated_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_load_persisted raises AeatLoginAssertionError with no_persisted_session key
    when _session_store.load returns None (no file on disk)."""
    settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
    provider = ClaveMovilAuthProvider(settings)
    storage_state_path = tmp_path / "nonexistent-storage.json"

    with pytest.raises(AeatLoginAssertionError) as exc_info:
        provider._load_persisted(storage_state_path)

    exc = exc_info.value
    assert exc.translated_message == "adapters.auth.clave_movil.errors.no_persisted_session"


# ---------------------------------------------------------------------------
# S276-B: probe_persisted_session carries no_persisted_session translated_message
# ---------------------------------------------------------------------------


def test_probe_persisted_session_carries_no_persisted_session_translated_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """probe_persisted_session raises AeatLoginAssertionError with translated_message
    set to no_persisted_session when no session file exists."""
    settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
    provider = ClaveMovilAuthProvider(settings)
    browser_session = _MinimalBrowserSession()

    async def run() -> None:
        with pytest.raises(AeatLoginAssertionError) as exc_info:
            await provider.probe_persisted_session(browser_session=browser_session)
        exc = exc_info.value
        assert exc.translated_message == "adapters.auth.clave_movil.errors.no_persisted_session"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# S276-C: resume_session raises with session_expired translated_message
# ---------------------------------------------------------------------------


def test_probe_persisted_session_expired_carries_translated_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """probe_persisted_session raises AeatLoginAssertionError with session_expired key
    when the persisted metadata's idle_deadline is in the past."""
    from . import _session_store

    settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
    provider = ClaveMovilAuthProvider(settings)
    # Use the canonical storage path so _storage_state_path() locates the record.
    storage_state_path = provider._storage_state_path()

    # Build an expired metadata record.
    expired_at = datetime.now(UTC) - timedelta(hours=1)
    metadata = _ClaveMovilSessionMetadata(
        authenticated_at=expired_at - timedelta(hours=8),
        idle_deadline=expired_at,
        identity_nif="12345678Z",
        used_non_qr_fallback=False,
        verification_code=None,
        # idle_deadline is checked before hash; any 64-char hex value suffices here.
        storage_state_sha256="deadbeef" * 8,
    )
    storage_state: dict[str, object] = {"cookies": [{"name": "AEAT_SESSION"}], "origins": []}
    _session_store.save(
        storage_state_path,
        storage_state=storage_state,
        metadata=metadata.model_dump(mode="json"),
    )

    async def run() -> None:
        with pytest.raises(AeatLoginAssertionError) as exc_info:
            await provider.probe_persisted_session(browser_session=_MinimalBrowserSession())
        exc = exc_info.value
        assert exc.translated_message == "adapters.auth.clave_movil.errors.session_expired"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# S276-D: resume_session raises with storage_state_hash_mismatch translated_message
# ---------------------------------------------------------------------------


def test_resume_locked_hash_mismatch_carries_translated_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_resume_locked raises AeatLoginAssertionError with storage_state_hash_mismatch key
    when the persisted sha256 does not match the metadata sha256."""
    from . import _session_store

    settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
    provider = ClaveMovilAuthProvider(settings)
    # Use the canonical storage path so _storage_state_path() locates the record.
    storage_state_path = provider._storage_state_path()

    now = datetime.now(UTC)
    metadata = _ClaveMovilSessionMetadata(
        authenticated_at=now - timedelta(hours=1),
        idle_deadline=now + timedelta(hours=7),
        identity_nif="12345678Z",
        used_non_qr_fallback=False,
        verification_code=None,
        # Deliberately wrong sha256 (64 hex chars) so it never matches the real persisted hash.
        storage_state_sha256="a" * 64,
    )
    storage_state: dict[str, object] = {"cookies": [{"name": "AEAT_SESSION"}], "origins": []}
    _session_store.save(
        storage_state_path,
        storage_state=storage_state,
        metadata=metadata.model_dump(mode="json"),
    )

    async def run() -> None:
        with pytest.raises(AeatLoginAssertionError) as exc_info:
            # Call private method directly to isolate this raise path.
            await provider._resume_locked(  # type: ignore[attr-defined]
                storage_state_path,
                browser_session=_MinimalBrowserSession(),
                target_url=None,
            )
        exc = exc_info.value
        assert exc.translated_message == "adapters.auth.clave_movil.errors.storage_state_hash_mismatch"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# S276-E: _click_clave_movil_button raises with page_missing_click
# ---------------------------------------------------------------------------


def test_click_clave_movil_button_missing_click_carries_translated_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_click_clave_movil_button raises AeatLoginAssertionError with page_missing_click
    key when the page stand-in has no click attribute."""
    settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
    provider = ClaveMovilAuthProvider(settings)
    page = _MinimalPage()  # no click() method

    async def run() -> None:
        with pytest.raises(AeatLoginAssertionError) as exc_info:
            # Access the private method directly to isolate this raise.
            await provider._click_clave_movil_button(page)  # type: ignore[arg-type]
        exc = exc_info.value
        assert exc.translated_message == "adapters.auth.clave_movil.errors.page_missing_click"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# S276-F: locale keys resolve to non-placeholder strings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", _CLAVE_MOVIL_LOCALE_KEYS)
def test_clave_movil_locale_key_resolves_to_real_copy(key: str) -> None:
    """Every new Cl@ve Movil locale key resolves to non-placeholder copy."""
    resolved = tr(key)
    assert key not in resolved, f"Key {key!r} was not replaced in the locale catalogue"
    assert len(resolved) > 10, f"Key {key!r} resolved to suspiciously short string: {resolved!r}"
