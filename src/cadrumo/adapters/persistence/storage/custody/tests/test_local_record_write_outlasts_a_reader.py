"""A local-record write waits out a reader, and still refuses a permanent block.

Windows refuses to replace a file while another process holds it open, and this
record is the login handover witness: readers are ordinary, because any process
inspecting the in-flight login opens it. The writer therefore has to outlast a
reader's handle rather than fail on meeting one -- an exhausted budget here does
not delay the login, it refuses it.

The budget was eight attempts ten milliseconds apart. Measured against eight
concurrent readers, roughly one write in ten exhausted that budget and raised;
at three readers none did, which is why the shortfall was invisible to any test
that did not apply real pressure.

Both halves are asserted, because a budget can fail in two directions. Too short
refuses a login that only needed to wait; unbounded would hang forever on a
denial that never clears -- and Windows reports a reader's handle and a denying
ACL with the same code, so nothing but the budget separates them.

Driven by holding a real handle for a real interval: no patching, and no
dependence on how loaded the machine is, because the hold is released on a timer
well inside the budget rather than raced against it.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from .. import (
    ProfileCustodyRecordError,
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_LIMIT = 4096
_FIRST = b'{"phase":"prepared"}'
_SECOND = b'{"phase":"published"}'

#: Longer than the retired eighty-millisecond budget, far inside the current one.
_HOLD_SECONDS = 0.3


def test_a_write_outlasts_a_reader_that_releases_its_handle(tmp_path: Path) -> None:
    """DISCRIMINATING: the write must survive a reader, not fail on one.

    The handle is released on a timer, so the write succeeds if and only if the
    budget outlasts the hold. Under the retired budget the hold outlives every
    attempt and the write is refused.
    """
    path = tmp_path / "handover-journal"
    write_profile_custody_local_record(path, _FIRST, publish_once=True)

    handle = path.open("rb")
    release = threading.Timer(_HOLD_SECONDS, handle.close)
    release.start()
    try:
        write_profile_custody_local_record(path, _SECOND, publish_once=False)
    finally:
        release.cancel()
        handle.close()

    assert read_optional_profile_custody_local_record(path, maximum_bytes=_LIMIT) == _SECOND


def test_a_permanent_native_write_block_is_still_refused(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: every platform refuses a durable write barrier.

    Windows holds the destination open, the native permanent blocker that its
    retry budget must eventually refuse. POSIX permits replacement of an open
    reader, so it instead presents a real directory at the destination and
    proves the no-follow atomic replacement refuses rather than overwriting it.
    """
    path = tmp_path / "handover-journal"
    write_profile_custody_local_record(path, _FIRST, publish_once=True)

    if os.name != "nt":
        path.unlink()
        path.mkdir()
        with pytest.raises(ProfileCustodyRecordError, match="cannot be atomically written"):
            write_profile_custody_local_record(path, _SECOND, publish_once=False)
        assert path.is_dir()
        return

    handle = path.open("rb")
    try:
        with pytest.raises(ProfileCustodyRecordError, match="cannot be atomically written"):
            write_profile_custody_local_record(path, _SECOND, publish_once=False)
    finally:
        handle.close()

    assert read_optional_profile_custody_local_record(path, maximum_bytes=_LIMIT) == _FIRST
