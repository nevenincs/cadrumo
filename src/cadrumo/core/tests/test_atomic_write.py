"""Unit tests for the two-tier atomic-write helper in
:mod:`cadrumo.core.atomic_write`.

Every failure test induces a REAL error (a directory occupying the target
path so :func:`os.replace` genuinely refuses it, or a wrongly-typed payload
so the underlying ``write``/``os.write`` call genuinely raises) rather than
patching or mocking any part of the write sequence, per the project's
real-behaviour testing discipline.
"""

from __future__ import annotations

import multiprocessing
import os
import stat
import threading
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from ..atomic_write import (
    _write_all,
    atomic_write_bytes,
    atomic_write_hardened_bytes,
    atomic_write_hardened_text,
    atomic_write_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PIPE_PAYLOAD = bytes(range(256)) * 4096
_CHILD_TIMEOUT_SECONDS = 5.0
_COOPERATIVE_ATTEMPTS = 8
_EXIT_BACKPRESSURE = 21
_EXIT_INCOMPLETE = 22
_EXIT_READER_FAILURE = 23


def _tmp_leftovers(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.tmp"))


def _close_fd(fd: int) -> None:
    with suppress(OSError):
        os.close(fd)


def _fill_nonblocking_pipe(write_fd: int) -> None:
    block = b"x" * 65_536
    while True:
        try:
            written = os.write(write_fd, block)
        except BlockingIOError:
            return
        if written <= 0:
            raise OSError("real pipe fill made no progress")


def _no_reader_backpressure_child() -> None:
    read_fd, write_fd = os.pipe()
    try:
        os.set_blocking(write_fd, False)
        _fill_nonblocking_pipe(write_fd)
        try:
            _write_all(write_fd, b"blocked")
        except BlockingIOError:
            return
        raise AssertionError("full nonblocking pipe did not propagate backpressure")
    finally:
        _close_fd(write_fd)
        _close_fd(read_fd)


def _cooperative_short_write_child() -> None:
    read_fd, write_fd = os.pipe()
    received = bytearray()
    reader_errors: list[BaseException] = []

    def _drain_pipe() -> None:
        try:
            while chunk := os.read(read_fd, 65_536):
                received.extend(chunk)
        except BaseException as exc:
            reader_errors.append(exc)

    reader = threading.Thread(target=_drain_pipe, daemon=True)
    reader_started = False
    outcome = 0
    try:
        os.set_blocking(write_fd, False)
        reader.start()
        reader_started = True
        try:
            _write_all(write_fd, _PIPE_PAYLOAD)
        except BlockingIOError:
            outcome = _EXIT_BACKPRESSURE
        finally:
            _close_fd(write_fd)
            write_fd = -1

        reader.join(timeout=_CHILD_TIMEOUT_SECONDS)
        if reader.is_alive() or reader_errors:
            outcome = _EXIT_READER_FAILURE
        elif outcome == 0 and received != _PIPE_PAYLOAD:
            outcome = _EXIT_INCOMPLETE
    finally:
        _close_fd(write_fd)
        _close_fd(read_fd)
        if reader_started:
            reader.join(timeout=0.25)
    raise SystemExit(outcome)


def _bounded_child_exitcode(target: Callable[[], None]) -> int:
    process = multiprocessing.get_context("spawn").Process(target=target)
    process.start()
    try:
        process.join(timeout=_CHILD_TIMEOUT_SECONDS)
        if process.is_alive():
            process.terminate()
            process.join(timeout=_CHILD_TIMEOUT_SECONDS)
            if process.is_alive():
                process.kill()
                process.join(timeout=_CHILD_TIMEOUT_SECONDS)
            target_name = getattr(target, "__name__", type(target).__name__)
            pytest.fail(f"child writer {target_name} exceeded the bounded timeout")
        assert process.exitcode is not None
        return process.exitcode
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=_CHILD_TIMEOUT_SECONDS)
            if process.is_alive():
                process.kill()
                process.join(timeout=_CHILD_TIMEOUT_SECONDS)
        process.close()


class TestStandardTier:
    """Behaviour of :func:`atomic_write_bytes` / :func:`atomic_write_text`."""

    def test_bytes_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.bin"
        atomic_write_bytes(target, b"\x00\x01hello\xff")
        assert target.read_bytes() == b"\x00\x01hello\xff"

    def test_text_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.txt"
        atomic_write_text(target, "hola\nmundo\n", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "hola\nmundo\n"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c" / "payload.bin"
        atomic_write_bytes(target, b"nested")
        assert target.read_bytes() == b"nested"

    def test_leaves_no_tmp_file_after_success(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.bin"
        atomic_write_bytes(target, b"clean")
        assert _tmp_leftovers(tmp_path) == []

    def test_overwrites_existing_target(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.bin"
        atomic_write_bytes(target, b"first")
        atomic_write_bytes(target, b"second")
        assert target.read_bytes() == b"second"

    def test_replace_failure_cleans_tmp_and_never_clobbers_target(self, tmp_path: Path) -> None:
        """A real ``os.replace`` failure (target occupied by a directory)."""
        target = tmp_path / "payload.bin"
        target.mkdir()
        (target / "marker.txt").write_text("still a directory", encoding="utf-8")

        with pytest.raises(OSError):
            atomic_write_bytes(target, b"would-be payload")

        assert target.is_dir()
        assert (target / "marker.txt").read_text(encoding="utf-8") == "still a directory"
        assert _tmp_leftovers(tmp_path) == []

    def test_write_failure_cleans_tmp_and_preserves_existing_target(self, tmp_path: Path) -> None:
        """A real ``handle.write`` failure (wrongly-typed payload mid-write)."""
        target = tmp_path / "payload.bin"
        atomic_write_bytes(target, b"OLD-CONTENT")

        invalid_payload: Any = "not-bytes"
        with pytest.raises(TypeError):
            atomic_write_bytes(target, invalid_payload)

        assert target.read_bytes() == b"OLD-CONTENT"
        assert _tmp_leftovers(tmp_path) == []


class TestHardenedTier:
    """Behaviour of :func:`atomic_write_hardened_bytes` / :func:`atomic_write_hardened_text`."""

    def test_bytes_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"\x00\x01secret\xff")
        assert target.read_bytes() == b"\x00\x01secret\xff"

    def test_write_all_completes_real_pipe_short_writes(self) -> None:
        """A capacity-limited OS pipe must receive the complete payload."""
        outcomes: list[int] = []
        for _attempt in range(_COOPERATIVE_ATTEMPTS):
            outcome = _bounded_child_exitcode(_cooperative_short_write_child)
            outcomes.append(outcome)
            assert outcome in {0, _EXIT_BACKPRESSURE}, outcomes
            if outcome == 0:
                break
        else:
            pytest.fail(f"all cooperative real-pipe attempts met transient backpressure: {outcomes}")

    def test_write_all_propagates_permanent_nonblocking_backpressure(self) -> None:
        assert _bounded_child_exitcode(_no_reader_backpressure_child) == 0

    def test_bytes_roundtrip_preserves_newline_bytes(self, tmp_path: Path) -> None:
        """A 0x0A byte must survive verbatim (no Windows text-mode CRLF translation).

        Binary payloads written through the hardened tier (ciphertext, master
        keys, fichero-BOE / PDF bytes) routinely contain 0x0A bytes. If the
        underlying fd is opened in text mode on Windows, os.write translates
        every 0x0A to 0x0D0A and lengthens the file, silently corrupting the
        payload and breaking every content-hash / decrypt check downstream.
        This pins the byte-exact contract on every platform.
        """
        payload = b"line-one\nline-two\r\nbinary\x00\x0a\xff-tail\n"
        target = tmp_path / "newline.bin"
        atomic_write_hardened_bytes(target, payload)
        written = target.read_bytes()
        assert written == payload
        assert len(written) == len(payload)

    def test_text_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.txt"
        atomic_write_hardened_text(target, "passphrase-material", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "passphrase-material"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "secret.bin"
        atomic_write_hardened_bytes(target, b"nested-secret")
        assert target.read_bytes() == b"nested-secret"

    def test_leaves_no_tmp_file_after_success(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"clean")
        assert _tmp_leftovers(tmp_path) == []

    def test_default_mode_is_0o600_on_posix(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"mode-check")
        if os.name != "nt":
            actual_mode = stat.S_IMODE(target.stat().st_mode)
            assert actual_mode == 0o600

    def test_explicit_mode_is_applied_on_posix(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"mode-check", mode=0o640)
        if os.name != "nt":
            actual_mode = stat.S_IMODE(target.stat().st_mode)
            assert actual_mode == 0o640

    def test_overwrites_existing_target(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"first")
        atomic_write_hardened_bytes(target, b"second")
        assert target.read_bytes() == b"second"

    def test_replace_failure_cleans_tmp_and_never_clobbers_target(self, tmp_path: Path) -> None:
        """A real ``os.replace`` failure (target occupied by a directory)."""
        target = tmp_path / "secret.bin"
        target.mkdir()
        (target / "marker.txt").write_text("still a directory", encoding="utf-8")

        with pytest.raises(OSError):
            atomic_write_hardened_bytes(target, b"would-be secret")

        assert target.is_dir()
        assert (target / "marker.txt").read_text(encoding="utf-8") == "still a directory"
        assert _tmp_leftovers(tmp_path) == []

    def test_write_failure_cleans_tmp_and_preserves_existing_target(self, tmp_path: Path) -> None:
        """A real ``os.write`` failure (wrongly-typed payload mid-write)."""
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"OLD-SECRET")

        invalid_payload: Any = "not-bytes"
        with pytest.raises(TypeError):
            atomic_write_hardened_bytes(target, invalid_payload)

        assert target.read_bytes() == b"OLD-SECRET"
        assert _tmp_leftovers(tmp_path) == []
