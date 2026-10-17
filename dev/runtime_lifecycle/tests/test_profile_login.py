"""The suite's person-owned CLI login preserves persistence and secret boundaries."""

import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from .. import proof_support
from ..caller_owned_root import AcceptanceError, Programs
from ..proof_support import Profile, login_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("persisted", [True, False])
def test_login_reports_actual_persistence_and_sends_password_only_on_stdin(
    monkeypatch: pytest.MonkeyPatch, persisted: bool
) -> None:
    profile = Profile(name="synthetic", password=secrets.token_urlsafe(24))
    calls: list[tuple[tuple[str, ...], Mapping[str, str] | None]] = []

    def cli(
        _programs: Programs,
        _environment: Mapping[str, str],
        *arguments: str,
        secret: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        calls.append((arguments, secret))
        return 0, {
            "status": "success" if persisted else "warning",
            "result": {"session_persisted": persisted},
            "notices": [] if persisted else [{"code": "config.login.session_not_persisted"}],
        }

    monkeypatch.setattr(proof_support, "run_cli", cli)
    programs = Programs(Path("aeat"), Path("runtime"), Path("mcp"))
    assert login_profile(programs, {}, profile) is persisted
    assert calls == [(("config", "login", "synthetic", "--secrets-stdin"), {"passphrase": profile.password})]
    assert profile.password not in repr(profile)


@pytest.mark.parametrize(
    "document",
    [
        {"status": "success", "result": {}},
        {"status": "success", "result": {"session_persisted": "true"}},
        {"status": "success", "result": {"session_persisted": False}},
    ],
)
def test_login_rejects_missing_malformed_or_contradictory_persistence(
    monkeypatch: pytest.MonkeyPatch, document: dict[str, Any]
) -> None:
    monkeypatch.setattr(proof_support, "run_cli", lambda *_args, **_kwargs: (0, document))
    with pytest.raises(AcceptanceError, match="persistence"):
        login_profile(Programs(Path("aeat"), Path("runtime"), Path("mcp")), {}, Profile("test", "secret"))
