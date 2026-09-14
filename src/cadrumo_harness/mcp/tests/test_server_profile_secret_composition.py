"""Startup ordering for the MCP profile-secret channel."""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import server as server_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_profile_secret_load_follows_adapter_composition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Profile resume cannot read custody state before the frontend binds its ports."""
    events: list[tuple[str, Path | None]] = []
    channel = tmp_path / "profile-secret.json"
    monkeypatch.setattr(
        server_module,
        "_ensure_adapter_composition",
        lambda: events.append(("compose", None)),
    )

    server_module._load_profile_secret_after_composition(
        channel,
        loader=lambda path: events.append(("load", path)),
    )

    assert events == [("compose", None), ("load", channel)]
