"""A byte the author did not write, and a byte the author wrote that is not there.

The distribution tooling reasons about bytes it cannot see. Two of its habits
turn an invisible byte into a wrong answer, in opposite directions.

The first is a raw control byte living in a source file. A regex whose pattern
carries a literal ``ESC`` is correct in the interpreter and invisible in every
channel that renders the file -- terminal output, a grep excerpt, a paste. A
reader who transcribes the pattern from what they SAW writes a different
pattern than the one that shipped: dropping the ``ESC`` from an SGR stripper
leaves ``\\[[0-9;]*m``, which no longer requires the escape introducer and
starts eating ordinary bracketed text. The byte that makes the guard correct is
the one byte the channel deletes, so the file must spell it printably.

The second is the mirror. ``Path.write_text`` without ``newline=`` translates
``\\n`` to ``os.linesep``, so a payload that ALREADY spells ``\\r\\n`` -- the
``.bat`` launchers these lanes stage for the Windows stubs -- is written as
``\\r\\r\\n``. The author wrote two bytes and three arrived. ``cmd`` currently
tolerates the doubled carriage return, which is precisely why nothing reports
it; the emitted artifact is still not the artifact the source describes, and a
consumer less forgiving than ``cmd`` would be the first to say so.

Both properties are DISCOVERED from the tooling trees rather than enumerated, so
a new offender is named the moment it lands. What the discovery cannot see is
stated rather than implied: it judges ``write_text`` payloads by the string
literals reachable in the call's own expression, so a carriage return assembled
at runtime from fragments no literal contains is outside it.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT, UTF_8

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The tooling trees whose emitted artifacts and guard patterns are byte-sensitive.
TOOLING_TREES: Final[tuple[str, ...]] = (
    "dev/packaging",
    "dev/ci",
    "dev/deploy",
    "dev/release",
    "dev/containers",
)

#: Control bytes a source file may legitimately carry: tab, newline, carriage return.
_PERMITTED_CONTROL_BYTES: Final[frozenset[int]] = frozenset({0x09, 0x0A, 0x0D})


def control_bytes(raw: bytes) -> set[int]:
    """Return the raw C0 control bytes in ``raw`` beyond tab, newline, and return."""
    return {byte for byte in raw if byte < 0x20 and byte not in _PERMITTED_CONTROL_BYTES}


def unpinned_carriage_return_writes(source: str, *, filename: str) -> list[int]:
    """Return the lines of ``write_text`` calls that spell a carriage return unpinned.

    A call qualifies when a string literal reachable in its payload expression
    contains ``\\r`` and the call does not pass ``newline=``, which is exactly
    the shape whose emitted bytes differ from the ones the source spells.
    """
    offenders: list[int] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "write_text"):
            continue
        if any(keyword.arg == "newline" for keyword in node.keywords):
            continue
        if not node.args:
            continue
        if any(
            isinstance(literal, ast.Constant) and isinstance(literal.value, str) and "\r" in literal.value
            for literal in ast.walk(node.args[0])
        ):
            offenders.append(node.lineno)
    return offenders


def tooling_sources() -> list[Path]:
    """Every Python source file in the byte-sensitive tooling trees."""
    found: list[Path] = []
    for tree in TOOLING_TREES:
        for path in sorted((REPO_ROOT / tree).rglob("*.py")):
            if "__pycache__" not in path.parts:
                found.append(path)
    return found


def test_the_control_byte_detector_names_a_source_that_carries_one(tmp_path: Path) -> None:
    """The retired form -- a raw ESC in the pattern -- must be detected first."""
    retired = tmp_path / "retired.py"
    retired.write_bytes('_SGR = re.compile(r"\x1b\\[[0-9;]*m")\n'.encode(UTF_8))

    assert control_bytes(retired.read_bytes()) == {0x1B}

    adopted = tmp_path / "adopted.py"
    adopted.write_bytes('_SGR = re.compile(r"\\x1b\\[[0-9;]*m")\n'.encode(UTF_8))

    assert control_bytes(adopted.read_bytes()) == set()


def test_the_printable_escape_strips_exactly_what_the_raw_byte_stripped() -> None:
    """Spelling the escape printably must not change one match decision.

    The negative sample is the load-bearing one: a pattern that lost its ``ESC``
    would strip bracketed text that carries no escape sequence at all.
    """
    raw_byte_form = re.compile("\x1b" + r"\[[0-9;]*m")
    printable_form = re.compile(r"\x1b\[[0-9;]*m")
    truncated_form = re.compile(r"\[[0-9;]*m")

    samples = ("\x1b[32m# comment", "\x1b[0m", "\x1b[1;31mred\x1b[0m", "plain", "[32m literal")
    for sample in samples:
        assert printable_form.sub("", sample) == raw_byte_form.sub("", sample)

    assert truncated_form.sub("", "[32m literal") != raw_byte_form.sub("", "[32m literal")


def test_the_unpinned_write_detector_names_a_carriage_return_payload() -> None:
    """The retired form -- a ``.bat`` payload written unpinned -- must fire first."""
    retired = 'launcher.write_text("@echo off\\r\\nexit /b 0\\r\\n", encoding="utf-8")\n'
    assert unpinned_carriage_return_writes(retired, filename="retired.py") == [1]

    pinned = 'launcher.write_text("@echo off\\r\\nexit /b 0\\r\\n", encoding="utf-8", newline="")\n'
    assert unpinned_carriage_return_writes(pinned, filename="pinned.py") == []

    newline_only = 'script.write_text("#!/bin/sh\\nexit 0\\n", encoding="utf-8")\n'
    assert unpinned_carriage_return_writes(newline_only, filename="posix.py") == []


def test_an_unpinned_carriage_return_write_really_doubles_the_byte(tmp_path: Path) -> None:
    """The defect is a byte outcome, not a style preference, so prove the bytes."""
    payload = "@echo off\r\nexit /b 0\r\n"

    unpinned = tmp_path / "unpinned.bat"
    unpinned.write_text(payload, encoding=UTF_8)

    pinned = tmp_path / "pinned.bat"
    pinned.write_text(payload, encoding=UTF_8, newline="")

    assert pinned.read_bytes() == payload.encode(UTF_8)

    # The doubling is `os.linesep` translation, so it is a property of the host,
    # not of the payload. Where the separator is already `\n` there is nothing to
    # translate and the two writes agree; the pinned form is exact either way.
    if os.linesep == "\r\n":
        assert unpinned.read_bytes().count(b"\r\r\n") == 2
    else:
        assert unpinned.read_bytes() == pinned.read_bytes()


def test_no_tooling_source_carries_an_invisible_control_byte() -> None:
    """No source in the tooling trees may hide a byte its rendering deletes."""
    offenders = {
        path.relative_to(REPO_ROOT).as_posix(): sorted(found)
        for path in tooling_sources()
        if (found := control_bytes(path.read_bytes()))
    }

    assert offenders == {}


def test_every_carriage_return_payload_in_the_tooling_trees_pins_its_newline() -> None:
    """No tooling writer may emit bytes that differ from the ones it spells."""
    offenders = {
        path.relative_to(REPO_ROOT).as_posix(): found
        for path in tooling_sources()
        if (found := unpinned_carriage_return_writes(path.read_text(encoding=UTF_8), filename=str(path)))
    }

    assert offenders == {}
