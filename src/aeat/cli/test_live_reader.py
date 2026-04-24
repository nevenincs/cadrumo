"""Unit tests for :mod:`aeat.cli._live_reader`."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..config import load_settings
from ._live_reader import LiveSessionUnavailableError, build_live_status_reader

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@pytest.mark.asyncio
async def test_missing_session_raises_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absent a persisted auth sidecar, the helper must fail closed."""
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    settings = load_settings()
    with pytest.raises(LiveSessionUnavailableError) as excinfo:
        async with build_live_status_reader(settings):
            pytest.fail("unreachable")  # pragma: no cover
    assert "aeat auth login" in str(excinfo.value)


@pytest.mark.asyncio
async def test_persisted_session_surfaces_followup_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a sidecar exists, the helper surfaces the follow-up hint.

    The production path to a fully-wired authenticator lives behind a
    follow-up issue; the helper raises :class:`LiveSessionUnavailableError`
    with a discoverable next-step rather than importing a partial
    implementation. The test asserts on the error text so a future PR
    that lands the real wiring will visibly break this expectation
    (and the author will extend coverage).
    """
    import json

    from ..auth import AuthProviderKind
    from .auth._paths import storage_state_paths

    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    settings = load_settings()
    paths = storage_state_paths(settings, AuthProviderKind.CERTIFICATE)
    paths.metadata.parent.mkdir(parents=True, exist_ok=True)
    paths.metadata.write_text(
        json.dumps(
            {
                "provider_kind": AuthProviderKind.CERTIFICATE.value,
                "identity_nif": "X1234567L",
                "authenticated_at": "2026-04-21T10:00:00+00:00",
                "idle_deadline": "2027-04-21T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(LiveSessionUnavailableError) as excinfo:
        async with build_live_status_reader(settings):
            pytest.fail("unreachable")  # pragma: no cover
    assert "follow-up" in str(excinfo.value)
