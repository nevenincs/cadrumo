"""Unit tests for the two-tier atomic-write helper in
:mod:`cadrumo.core.atomic_write`.

Every failure test induces a REAL error (a directory occupying the target
path so :func:`os.replace` genuinely refuses it, or a wrongly-typed payload
so the underlying ``write``/``os.write`` call genuinely raises) rather than
patching or mocking any part of the write sequence, per the project's
real-behaviour testing discipline.
"""

from __future__ import annotations

import os
import stat
import threading
from pathlib import Path

import pytest

from ..atomic_write import (
    _write_all,
    atomic_write_bytes,
    atomic_write_hardened_bytes,
    atomic_write_hardened_text,
    atomic_write_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _tmp_leftovers(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.tmp"))


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

        with pytest.raises(TypeError):
            atomic_write_bytes(target, "not-bytes")  # type: ignore[arg-type]

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
        payload = bytes(range(256)) * 4096
        read_fd, write_fd = os.pipe()
        os.set_blocking(write_fd, False)
        received = bytearray()
        reader_errors: list[BaseException] = []

        def _drain_pipe() -> None:
            try:
                while chunk := os.read(read_fd, 4096):
                    received.extend(chunk)
            except BaseException as exc:
                reader_errors.append(exc)

        reader = threading.Thread(target=_drain_pipe, daemon=True)
        reader.start()
        try:
            _write_all(write_fd, payload)
        finally:
            os.close(write_fd)

        reader.join(timeout=5.0)
        try:
            assert not reader.is_alive(), "real pipe reader did not finish"
            assert reader_errors == []
            assert bytes(received) == payload
        finally:
            os.close(read_fd)

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

        with pytest.raises(TypeError):
            atomic_write_hardened_bytes(target, "not-bytes")  # type: ignore[arg-type]

        assert target.read_bytes() == b"OLD-SECRET"
        assert _tmp_leftovers(tmp_path) == []
