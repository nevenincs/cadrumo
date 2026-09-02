"""Regression: the CLI subprocess output is decoded as UTF-8, not the platform default.

The deterministic CLI always emits UTF-8 (its stdout JSON is UTF-8 and
``write_stderr`` reconfigures stderr to UTF-8). ``subprocess.run(..., text=True)``
without an explicit ``encoding`` decodes with ``locale.getpreferredencoding()`` —
cp1252 on Windows — which turns every accented Spanish character in a relayed
envelope or error into double-encoded mojibake (``encontró`` -> ``encontrÃ³``)
for the LLM client. The live-model persona measurement observed exactly this in a
``registry citations view`` error. ``_run_subprocess_tool`` must pin
``encoding="utf-8"`` so the relayed text is faithful on every host.

The decode contract now lives in the supervised call runtime
(:func:`~cadrumo_harness.mcp._call_runtime.run_supervised`), which pins
``encoding="utf-8"``; these tests exercise it against a real child emitting
UTF-8 Spanish, so the fix is grounded in real platform behaviour rather than an
injected stub.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from .._call_runtime import run_supervised

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_supervised_run_decodes_utf8_not_the_platform_default() -> None:
    # A real child writing raw UTF-8 accented bytes; the runtime must decode them
    # as UTF-8 (not cp1252 on Windows), so no mojibake reaches the LLM client.
    result = run_supervised(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write('No se encontró la cita'.encode('utf-8'))"],
        timeout_s=30.0,
        encoding="utf-8",
    )
    assert result.timed_out is False
    assert result.stdout == "No se encontró la cita"
    assert "Ã" not in result.stdout


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
