"""The shared recovery handoff writes a complete document and closes its descriptor."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.recovery_handover import _write_recovery_handoff

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CODE = "ABCD-EFGH-JKLM-NPQR"


def _open_for_write(path: Path) -> int:
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)


def _assert_closed(descriptor: int) -> None:
    with pytest.raises(OSError):
        os.fstat(descriptor)


def test_a_partial_write_still_delivers_the_whole_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "handoff.json"
    descriptor = _open_for_write(target)
    real_write = os.write

    def three_bytes_at_a_time(fd: int, data: bytes | memoryview) -> int:
        return real_write(fd, bytes(data[:3]))

    monkeypatch.setattr(os, "write", three_bytes_at_a_time)
    _write_recovery_handoff(descriptor, _CODE)

    assert json.loads(target.read_bytes()) == {"recovery_code": _CODE}
    assert target.read_bytes().endswith(b"\n")
    _assert_closed(descriptor)


def test_a_descriptor_that_accepts_nothing_is_refused_and_still_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor = _open_for_write(tmp_path / "handoff.json")
    monkeypatch.setattr(os, "write", lambda fd, data: 0)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _write_recovery_handoff(descriptor, _CODE)

    assert refused.value.translated_message == "cli.config.profile.recovery.handoff_unwritable"
    _assert_closed(descriptor)
