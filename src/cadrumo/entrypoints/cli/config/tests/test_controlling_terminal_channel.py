"""Real-behaviour tests for the terminal-direct secret display channel.

A recovery code is a bearer credential over the whole encrypted store, so
the property that matters is not "it printed" but "it did not print anywhere
durable". These drive the real function against real streams and a real
detached child process: no mocks, and the no-terminal case is exercised by
genuinely detaching from the controlling terminal rather than by patching one
away.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import IO

import pytest

from ...errors import CliRefusedBoundaryError
from ..secure_input import write_to_controlling_terminal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MNEMONIC_INPUT = "abandon ability able about above absent absorb abstract absurd abuse access accident"

_REFUSAL_PROBE = (
    "from cadrumo.entrypoints.cli.config.secure_input import write_to_controlling_terminal\n"
    "from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError\n"
    f"try:\n    write_to_controlling_terminal({_MNEMONIC_INPUT!r})\n"
    "    outcome = 'wrote'\n"
    "except CliRefusedBoundaryError:\n    outcome = 'refused'\n"
    "open({path!r}, 'w', encoding='utf-8').write(outcome)\n"
)


async def _run_redirected_child(
    *, command: list[str], stdout: int | IO[str] | None, stderr: int | IO[str] | None
) -> tuple[int, str]:
    """Run a fixed child while preserving the operator-visible stream routing."""
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=stdout,
        stderr=stderr,
        stdin=asyncio.subprocess.DEVNULL,
    )
    _, captured_stderr = await process.communicate()
    returncode = process.returncode
    if returncode is None:
        raise RuntimeError("the child process did not finish after communicate()")
    return returncode, (captured_stderr or b"").decode("utf-8", errors="replace")


async def _run_detached_child(
    *, command: list[str], stream: int | IO[str], creationflags: int = 0, start_new_session: bool = False
) -> int:
    """Run a fixed child with the platform's real detached-process option."""
    if creationflags:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=stream,
            stderr=stream,
            stdin=asyncio.subprocess.DEVNULL,
            creationflags=creationflags,
        )
    elif start_new_session:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=stream,
            stderr=stream,
            stdin=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
    else:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=stream,
            stderr=stream,
            stdin=asyncio.subprocess.DEVNULL,
        )
    return int(await process.wait())


def test_a_captured_session_refuses_and_leaves_the_streams_clean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Under captured streams the channel refuses, and writes nothing anywhere.

    pytest replaces the standard streams, which is the same shape as the
    production leak this guards: output going somewhere durable rather than to
    a human. Both halves are asserted together because either alone would pass
    for the wrong reason -- a refusal proves nothing if the words were printed
    first, and clean streams prove nothing if the call silently did nothing on
    a surface an operator was told to read from.
    """
    with pytest.raises(CliRefusedBoundaryError):
        write_to_controlling_terminal(_MNEMONIC_INPUT)

    captured = capsys.readouterr()
    assert _MNEMONIC_INPUT not in captured.out
    assert _MNEMONIC_INPUT not in captured.err


def test_a_redirected_child_leaves_no_secret_in_the_captured_file(tmp_path: Path) -> None:
    """An operator running the verb with ``> transcript.txt`` gets no secret in it.

    The realistic leak: output redirected to a file, or teed into a log by a
    supervisor. A channel that resolved to stdout would put a bearer credential
    on disk; this asserts the file stays clean whether the child reached a
    console or refused.
    """
    transcript = tmp_path / "transcript.txt"
    script = (
        "from cadrumo.entrypoints.cli.config.secure_input import write_to_controlling_terminal\n"
        "from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError\n"
        f"try:\n    write_to_controlling_terminal({_MNEMONIC_INPUT!r})\n"
        "except CliRefusedBoundaryError:\n    pass\n"
    )

    with transcript.open("w", encoding="utf-8") as handle:
        returncode, stderr = asyncio.run(
            _run_redirected_child(
                command=[sys.executable, "-c", script],
                stdout=handle,
                stderr=asyncio.subprocess.PIPE,
            ),
        )

    assert returncode == 0, stderr
    assert _MNEMONIC_INPUT not in transcript.read_text(encoding="utf-8")
    assert _MNEMONIC_INPUT not in stderr


def test_a_detached_child_refuses_rather_than_falling_back(tmp_path: Path) -> None:
    """With no controlling terminal at all, the channel refuses.

    Refusing is the safety property: there is nowhere safe to show the secret,
    and falling back to a captured stream would write the bearer credential
    into precisely what the channel bypasses. The child is genuinely detached
    -- a new session on POSIX, no console on Windows -- so this exercises the
    real absence rather than a simulated one.
    """
    outcome_path = tmp_path / "outcome.txt"
    transcript = tmp_path / "detached.txt"
    script = _REFUSAL_PROBE.format(path=str(outcome_path))

    with transcript.open("w", encoding="utf-8") as handle:
        if sys.platform == "win32":
            asyncio.run(
                _run_detached_child(
                    command=[sys.executable, "-c", script],
                    stream=handle,
                    creationflags=0x00000008,
                ),
            )
        else:
            asyncio.run(
                _run_detached_child(
                    command=[sys.executable, "-c", script],
                    stream=handle,
                    start_new_session=True,
                ),
            )

    assert outcome_path.read_text(encoding="utf-8") == "refused"
    assert _MNEMONIC_INPUT not in transcript.read_text(encoding="utf-8")
