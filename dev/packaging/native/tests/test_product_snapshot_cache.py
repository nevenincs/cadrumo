"""The product snapshot's source digest comes from the digest cache, and equals the repository's own."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from dev.source_tree import content_digest

from ..hashing import digest_cache, transformed_digest
from ..product import _source_digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LONG_AGO = time.time_ns() - 3600 * 1_000_000_000


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.utime(path, ns=(_LONG_AGO, _LONG_AGO))


def _repository(root: Path, attributes: bytes) -> tuple[str, ...]:
    _write(root / ".gitattributes", attributes)
    _write(root / "src/module.py", b"value = 1\r\nother = 2\r\n")
    _write(root / "src/script.cmd", b"echo one\necho two\n")
    _write(root / "src/data.bin", b"\x00\x01\r\n\x02")
    _write(root / "src/same.py", b"value = 1\r\nother = 2\r\n")
    return ("src/data.bin", "src/module.py", "src/same.py", "src/script.cmd")


def test_the_cached_source_digest_is_the_repositorys_content_digest(tmp_path: Path) -> None:
    files = _repository(tmp_path / "repo", b"* text=auto\n*.cmd text eol=crlf\n*.bin binary\n")
    expected = content_digest(tmp_path / "repo", files)
    assert _source_digest(tmp_path / "repo", files) == expected
    with digest_cache(tmp_path / "build"):
        assert _source_digest(tmp_path / "repo", files) == expected
    with digest_cache(tmp_path / "build"):
        assert _source_digest(tmp_path / "repo", files) == expected


def test_a_changed_line_ending_rule_is_not_answered_from_the_cache(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    files = _repository(root, b"* text=auto\n")
    with digest_cache(tmp_path / "build"):
        before = _source_digest(root, files)
    # The same bytes, now to be checked out with CRLF: the recorded content changes.
    _write(root / ".gitattributes", b"* text=auto\n*.py text eol=crlf\n")
    with digest_cache(tmp_path / "build"):
        after = _source_digest(root, files)
    assert after == content_digest(root, files) != before


def test_a_file_with_the_same_content_and_treatment_is_not_transformed_again(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _repository(root, b"* text=auto\n")
    calls: list[bytes] = []

    def lowered(raw: bytes) -> bytes:
        calls.append(raw)
        return raw.lower()

    with digest_cache(tmp_path / "build"):
        first = transformed_digest(root / "src/module.py", "lowered", lowered)
        second = transformed_digest(root / "src/same.py", "lowered", lowered)
        other = transformed_digest(root / "src/same.py", "uppered", bytes.upper)
    assert first == second != other
    assert len(calls) == 1
    with digest_cache(tmp_path / "build"):
        assert transformed_digest(root / "src/module.py", "lowered", lowered) == first
    assert len(calls) == 1
