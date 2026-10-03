"""A local-record replacement waits only for handle contention, never an ACL denial.

Waiting out a reader is bounded by a budget, and the budget is what separates a
transient handle from a permanent block when Windows reports both the same way.
A denial raised without a contention code -- here a directory ACL that forbids
creating the staging file -- cannot clear by waiting, so the writer must refuse
it immediately rather than spend the whole budget first.

Driven by a real deny entry on a real directory, with the refusal timed against
the retry budget: waiting it out would take at least the budget, refusing it
takes one failed open.
"""

from __future__ import annotations

import getpass
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

from ..errors import ProfileCustodyRecordError
from ..filesystem import (
    _LOCAL_RECORD_REPLACE_BUDGET_SECONDS,
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.windows_only, pytest.mark.hex_persistence_adapter]

_LIMIT = 4096
_FIRST = b'{"phase":"prepared"}'
_SECOND = b'{"phase":"published"}'
_THIRD = b'{"phase":"settled"}'


def _set_operator_access(directory: Path, rights: int) -> None:
    """Replace the directory's DACL with one allow entry for the operator."""
    import win32security

    operator = win32security.LookupAccountName(None, getpass.getuser())[0]
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAceEx(
        win32security.ACL_REVISION,
        win32security.OBJECT_INHERIT_ACE | win32security.CONTAINER_INHERIT_ACE,
        rights,
        operator,
    )
    win32security.SetNamedSecurityInfo(
        str(directory),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        dacl,
        None,
    )


@contextmanager
def _directory_refusing_new_files(directory: Path) -> Generator[None]:
    """Grant the operator read, delete and DACL rights only, so creating a file is denied."""
    import ntsecuritycon

    read_only = (
        ntsecuritycon.FILE_GENERIC_READ
        | ntsecuritycon.FILE_GENERIC_EXECUTE
        | ntsecuritycon.DELETE
        | ntsecuritycon.WRITE_DAC
    )
    _set_operator_access(directory, read_only)
    try:
        yield
    finally:
        _set_operator_access(directory, ntsecuritycon.FILE_ALL_ACCESS)


def test_an_acl_denied_replacement_is_refused_without_spending_the_budget(tmp_path: Path) -> None:
    path = tmp_path / "handover-journal"
    write_profile_custody_local_record(path, _FIRST, publish_once=True)
    # The first replacement pays the one-time import cost of the atomic writer,
    # which must not be charged to the refusal being timed.
    write_profile_custody_local_record(path, _SECOND, publish_once=False)

    with _directory_refusing_new_files(tmp_path):
        started = time.monotonic()
        with pytest.raises(ProfileCustodyRecordError, match="cannot be atomically written"):
            write_profile_custody_local_record(path, _THIRD, publish_once=False)
        elapsed = time.monotonic() - started

    assert elapsed < _LOCAL_RECORD_REPLACE_BUDGET_SECONDS / 2
    assert read_optional_profile_custody_local_record(path, maximum_bytes=_LIMIT) == _SECOND
