"""Real-behavior tests for the real-client evidence session secret guard.

The operator-supplied ``--real-client-session`` JSON ships verbatim into a
published ``claude-*.json`` evidence row, so it is scanned for secret-shaped
content before minting. These tests drive the real guard against real JSON
files on disk. No mocks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..emit_real_client_evidence import (
    RealClientSessionError,
    assert_session_carries_no_secret,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write(path: Path, session: object) -> object:
    path.write_text(json.dumps(session), encoding="utf-8")
    return session


def test_benign_session_summary_passes(tmp_path: Path) -> None:
    """A short status-only session summary is accepted."""
    path = tmp_path / "session.json"
    session = _write(
        path,
        {"connected": True, "status": "passed", "tool_called": "cadrumo_modelo_work_calculate", "model": "sonnet"},
    )
    assert_session_carries_no_secret(path, session)


def test_bearer_token_shaped_value_is_refused(tmp_path: Path) -> None:
    """A token-length string cannot ship into a published evidence row."""
    path = tmp_path / "session.json"
    session = _write(
        path,
        {"connected": True, "authorization": "Bearer sk-ThisIsAThirtyTwoPlusCharacterSecretToken"},
    )
    with pytest.raises(RealClientSessionError, match="secret-shaped content"):
        assert_session_carries_no_secret(path, session)


def test_email_address_is_refused(tmp_path: Path) -> None:
    """A personal identifier (email) cannot ship verbatim, even when short."""
    path = tmp_path / "session.json"
    session = _write(path, {"connected": True, "operator": "user@example.com"})
    with pytest.raises(RealClientSessionError, match="secret-shaped content"):
        assert_session_carries_no_secret(path, session)


def test_secret_shaped_dict_key_is_refused(tmp_path: Path) -> None:
    """A token-length dict KEY is refused, not only a value."""
    path = tmp_path / "session.json"
    session = _write(path, {"abcdefghijklmnopqrstuvwxyz0123456789": "present"})
    with pytest.raises(RealClientSessionError, match="secret-shaped content"):
        assert_session_carries_no_secret(path, session)


def test_email_in_dict_key_is_refused(tmp_path: Path) -> None:
    """An email address appearing as a dict KEY is refused."""
    path = tmp_path / "session.json"
    session = _write(path, {"user@example.com": "connected"})
    with pytest.raises(RealClientSessionError, match="secret-shaped content"):
        assert_session_carries_no_secret(path, session)


def test_nested_token_is_refused(tmp_path: Path) -> None:
    """A secret buried in a nested structure is still caught."""
    path = tmp_path / "session.json"
    session = _write(
        path,
        {"connected": True, "auth": {"headers": ["x-api-key: abcdefghijklmnopqrstuvwxyz0123456789"]}},
    )
    with pytest.raises(RealClientSessionError, match="secret-shaped content"):
        assert_session_carries_no_secret(path, session)
