"""Regression: the CLI subprocess output is decoded as UTF-8, not the platform default.

The deterministic CLI always emits UTF-8 (its stdout JSON is UTF-8 and
``write_stderr`` reconfigures stderr to UTF-8). ``subprocess.run(..., text=True)``
without an explicit ``encoding`` decodes with ``locale.getpreferredencoding()`` —
cp1252 on Windows — which turns every accented Spanish character in a relayed
envelope or error into double-encoded mojibake (``encontró`` -> ``encontrÃ³``)
for the LLM client. The live-model persona measurement observed exactly this in a
``registry citations view`` error. ``_run_subprocess_tool`` must pin
``encoding="utf-8"`` so the relayed text is faithful on every host.

These tests substitute only the OS process boundary (``subprocess.run``) — the
decode-kwarg wiring and the JSON-envelope round-trip are the real behaviour under
test.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from .. import _server
from .._server import _run_subprocess_tool
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

# A JSON envelope carrying accented Spanish — the exact shape that mojibakes when
# UTF-8 bytes are decoded as cp1252.
_SPANISH_ENVELOPE = '{"status": "error", "message": "No se encontró ninguna cita del registro."}'


def _any_descriptor() -> object:
    return build_tool_descriptors()[0]


def test_subprocess_is_decoded_as_utf8_not_platform_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _spy(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        captured["argv0"] = argv[0]
        return subprocess.CompletedProcess(argv, returncode=1, stdout=_SPANISH_ENVELOPE, stderr="")

    monkeypatch.setattr(_server.subprocess, "run", _spy)

    envelope, is_error = _run_subprocess_tool(_any_descriptor(), {})

    # The decode contract: UTF-8, degrade rather than raise on a stray byte.
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert captured["argv0"] == "aeat"
    # The accented text round-trips faithfully — no mojibake reaches the client.
    assert envelope["message"] == "No se encontró ninguna cita del registro."
    assert "Ã" not in envelope["message"]
    assert is_error is True


def test_real_subprocess_run_with_pinned_kwargs_decodes_spanish() -> None:
    # Ground the fix in real platform behaviour: a real child emitting UTF-8
    # Spanish, decoded with the exact kwargs the server pins, yields the correct
    # characters on THIS host (the one that exhibited the mojibake).
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write('artículo ó é í'.encode('utf-8'))"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    assert completed.stdout == "artículo ó é í"
    assert "Ã" not in completed.stdout
