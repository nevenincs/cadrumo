"""Tests for the shared real-filesystem obstruction helper.

The helper exists so crash-window tests can make a real write fail without a
test double. Its own value therefore rests entirely on the obstruction really
obstructing: a helper that silently failed to inject would leave every test
built on it asserting a success path while claiming to assert a failure. These
tests pin that both ways -- the refusal happens under obstruction, and the same
write succeeds without it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ..core.atomic_write import atomic_write_bytes, atomic_write_text
from ..core.directory_scan import iter_directory
from ..core.external_constants import UTF_8_ENCODING
from .path_obstruction import PathObstructionError, obstructed_path, replace_would_refuse

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ORIGINAL = b"the bytes that were there before the obstruction"


class TestObstructionRefusesEveryRealWriteMechanism:
    """Each syscall the storage substrate writes through must refuse."""

    def test_open_for_writing_is_refused(self, tmp_path: Path) -> None:
        target = tmp_path / "target.json"

        with obstructed_path(target), pytest.raises(OSError):
            target.open("wb")

    def test_os_replace_onto_the_target_is_refused(self, tmp_path: Path) -> None:
        """The rename half, proven directly rather than inferred from ``open``.

        Every :mod:`~cadrumo.core.atomic_write` tier stages a sibling tempfile
        and completes with :func:`os.replace`, so a helper that only blocked
        ``open`` would not block the writers it is meant to fault.
        """
        target = tmp_path / "target.json"
        staging = tmp_path / "staging"
        staging.mkdir()

        with obstructed_path(target):
            assert replace_would_refuse(target, staging_dir=staging)

    @pytest.mark.parametrize("tier", ["bytes", "text"])
    def test_the_projects_atomic_writers_are_refused(self, tmp_path: Path, tier: str) -> None:
        """The obstruction faults the actual helper production writes through."""
        target = tmp_path / "target.json"

        with obstructed_path(target), pytest.raises(OSError):
            if tier == "bytes":
                atomic_write_bytes(target, b"payload")
            else:
                atomic_write_text(target, "payload", encoding=UTF_8_ENCODING)


class TestPositiveControl:
    """Without the obstruction the same writes succeed.

    This is what makes the refusals above evidence. If the writes failed for
    an unrelated reason -- a missing parent, a read-only tmp_path, a helper
    signature drift -- every test in the class above would pass while proving
    nothing about the obstruction.
    """

    def test_atomic_write_succeeds_on_an_unobstructed_path(self, tmp_path: Path) -> None:
        target = tmp_path / "target.json"

        atomic_write_bytes(target, b"payload")

        assert target.read_bytes() == b"payload"

    def test_the_same_path_is_writable_again_after_the_block_exits(self, tmp_path: Path) -> None:
        """The fault is scoped to the block, so a later assertion is not poisoned."""
        target = tmp_path / "target.json"

        with obstructed_path(target), pytest.raises(OSError):
            atomic_write_bytes(target, b"during")

        atomic_write_bytes(target, b"after")
        assert target.read_bytes() == b"after"

    def test_os_replace_succeeds_on_an_unobstructed_path(self, tmp_path: Path) -> None:
        """Pairs with the rename refusal: the probe reports False when it should."""
        target = tmp_path / "target.json"
        staging = tmp_path / "staging"
        staging.mkdir()

        assert not replace_would_refuse(target, staging_dir=staging)


class TestRestoration:
    """The block leaves the filesystem as it found it."""

    def test_a_pre_existing_file_is_restored_byte_for_byte(self, tmp_path: Path) -> None:
        """A store that reads the file after the failure must see what it wrote."""
        target = tmp_path / "index.json"
        target.write_bytes(_ORIGINAL)

        with obstructed_path(target), pytest.raises(OSError):
            atomic_write_bytes(target, b"replacement")

        assert target.read_bytes() == _ORIGINAL

    def test_an_absent_path_is_absent_again(self, tmp_path: Path) -> None:
        target = tmp_path / "absent.json"

        with obstructed_path(target):
            assert target.is_dir()

        assert not target.exists()

    def test_restoration_runs_when_the_block_raises(self, tmp_path: Path) -> None:
        """Cleanup is in ``finally``, so a failing assertion cannot strand a directory."""
        target = tmp_path / "index.json"
        target.write_bytes(_ORIGINAL)

        with pytest.raises(ValueError, match="raised inside the block"), obstructed_path(target):
            raise ValueError("raised inside the block")

        assert target.is_file()
        assert target.read_bytes() == _ORIGINAL


class TestVacuityGuards:
    """The helper refuses states in which it would not be measuring its own fault."""

    def test_an_already_obstructed_path_is_refused(self, tmp_path: Path) -> None:
        """Otherwise the block would measure a condition it did not create.

        It would also delete, on exit, a directory belonging to whatever put
        it there.
        """
        target = tmp_path / "already"
        target.mkdir()
        (target / "keep").write_text("keep", encoding=UTF_8_ENCODING)

        with pytest.raises(PathObstructionError, match="already a directory"), obstructed_path(target):
            pass  # pragma: no cover - the block must not be entered

        assert (target / "keep").is_file()

    def test_a_block_that_dissolves_the_obstruction_is_refused(self, tmp_path: Path) -> None:
        """An entry-only check would let a vacuous block exit green.

        If the code under test removes the obstruction and then writes
        successfully, every assertion inside describes an ordinary success
        path while the test claims to describe a failure. Checking the fault
        only when it is planted cannot see that; checking it again at the end
        can.
        """
        target = tmp_path / "target.json"

        with pytest.raises(PathObstructionError, match="did not survive"), obstructed_path(target):
            (target / "blocker").unlink()
            target.rmdir()

        assert not target.exists()

    def test_the_obstruction_is_not_empty(self, tmp_path: Path) -> None:
        """An empty directory is removable, so a writer could dissolve the fault."""
        target = tmp_path / "target.json"

        with obstructed_path(target):
            assert any(iter_directory(target))
            with pytest.raises(OSError):
                os.rmdir(target)
