"""Point the components client at a replay of recorded role conversations, for the TUI's setup tests.

The fixture names a built binary for the client, gives it a throwaway storage
root and swaps only the process launch for a
:class:`~cadrumo.tests.components_role_dispatch.RoleReplay`.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from cadrumo.tests.components_role_dispatch import RoleReplay

from .....adapters.outbound.components import client as components_client
from .....adapters.outbound.components.role_image import DEVELOPMENT_ROLE_IMAGE_VARIABLE

__all__ = ["role_replay_fixture"]


@pytest.fixture(name="role_replay")
def role_replay_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., RoleReplay]:
    """Name a built binary for the client and answer its starts: ``role_replay(status=["status_quick"])``."""
    image = tmp_path / "cadrumo.exe"
    image.write_bytes(b"")
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    monkeypatch.setenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, str(image))
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "root"))

    def answer(
        *, stall_after: Mapping[str, int] | None = None, unstartable: bool = False, **transcripts: Sequence[str]
    ) -> RoleReplay:
        replay = RoleReplay(transcripts, stall_after=stall_after or {}, unstartable=unstartable)
        monkeypatch.setattr(components_client, "launch_components_role", replay)
        return replay

    return answer
