"""The live lane's capture never writes a secret.

The positive controls plant a secret where a careless capture would carry it:
in a tool argument, JSON-escaped inside a stream line, and under a secret-named
key the scrubber was never told about. The scrubber must replace the known
ones, and the writer must refuse, writing nothing, when anything survives.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..live.capture import CaptureLeakError, Scrubber, write_capture

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PLANTED_SIGN_IN = "Live-eval-planted-password-0123456789!"
_MODEL_KEY = "sk-ant-api03-plantedplantedplanted"
_HOST_PATH = "C:\\Users\\someone\\private\\token-file"


def _scrubber() -> Scrubber:
    return Scrubber(
        (("password", _PLANTED_SIGN_IN), ("model_credential", _MODEL_KEY), ("HOST_VAR", _HOST_PATH), ("SHORT", "1"))
    )


def test_known_secrets_are_replaced_in_every_encoding(tmp_path: Path) -> None:
    line = json.dumps({"type": "tool_use", "input": {"note": f"path {_HOST_PATH} and {_PLANTED_SIGN_IN}"}})
    document = {"stream": [line], "argument": {"passphrase": _PLANTED_SIGN_IN}, "key": _MODEL_KEY}
    path = write_capture(tmp_path, "trajectory.json", document, _scrubber())
    written = path.read_text(encoding="utf-8")
    for planted in (_PLANTED_SIGN_IN, _MODEL_KEY, _HOST_PATH, json.dumps(_HOST_PATH)[1:-1]):
        assert planted not in written
    assert "[scrubbed:password]" in written
    assert "[scrubbed:HOST_VAR]" in written


def test_a_short_host_value_is_not_scrubbed_out_of_ordinary_text(tmp_path: Path) -> None:
    written = write_capture(tmp_path, "receipt.json", {"runs": 1}, _scrubber()).read_text(encoding="utf-8")
    assert '"runs": 1' in written


def test_an_unknown_secret_under_a_secret_name_refuses_the_write(tmp_path: Path) -> None:
    document = {"tool_calls": [{"arguments": {"secret": "an-unlisted-secret-value"}}]}
    with pytest.raises(CaptureLeakError, match="secret-shaped"):
        write_capture(tmp_path, "trajectory.json", document, _scrubber())
    assert not (tmp_path / "trajectory.json").exists()


def test_an_unknown_model_credential_refuses_the_write(tmp_path: Path) -> None:
    with pytest.raises(CaptureLeakError):
        write_capture(tmp_path, "trajectory.json", {"text": "sk-ant-api03-someotherkeyvalue"}, _scrubber())
    assert list(tmp_path.iterdir()) == []


def test_a_secret_learned_mid_run_is_scrubbed(tmp_path: Path) -> None:
    scrubber = _scrubber()
    late = "a-value-the-harness-learned-after-the-run-started"
    scrubber.add("late_secret", late)
    written = write_capture(tmp_path, "t.json", {"note": f"saw {late}"}, scrubber)
    assert late not in written.read_text(encoding="utf-8")


def test_the_residual_sweep_sees_a_known_secret_the_scrubber_missed() -> None:
    scrubber = _scrubber()
    assert scrubber.residual(f"left behind: {_PLANTED_SIGN_IN}")
    assert scrubber.residual('{"passphrase": "[scrubbed:password]"}') == []
