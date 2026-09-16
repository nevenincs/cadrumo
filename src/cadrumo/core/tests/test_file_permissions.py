"""Directory hardening leaves the owner-only boundary ``icacls`` would leave.

On Windows the DACL is rewritten in process. The reference is the real
``icacls.exe /inheritance:r /grant:r <operator>:(OI)(CI)F`` run on an identically
prepared twin directory, so the comparison is against the tool whose semantics
the rewrite claims, not against a restatement of the rewrite. Each shape covers
one rule of that command: inherited ACEs stripped and the DACL protected,
foreign explicit ACEs kept in order, the operator's same-flag allow ACE replaced
in place, other operator ACEs kept, and a NULL DACL replaced.

Hardening is best-effort and swallows its own failures, so a broken rewrite
leaves the twin unprotected rather than raising. Every shape therefore also
requires the protected bit, which the unhardened twin demonstrably lacks.

Hosts without Windows ACLs assert the POSIX mode instead, with its own
positive control, so this module asserts something on every platform.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process

from ..file_permissions import _dacl_of, _operator_account_candidates, restrict_directory_permissions

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_USERS_SID = "*S-1-5-32-545"
_GUESTS_SID = "*S-1-5-32-546"

type _DaclShape = tuple[bool, str, tuple[tuple[int, int, int, str], ...]]


def _icacls(path: Path, *args: str) -> tuple[int, str]:
    executable = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "icacls.exe"
    completed = run_audited_process(
        [str(executable), str(path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return completed.returncode, f"{completed.stdout!s}{completed.stderr!s}"


def _operator() -> str:
    """The first account spelling ``icacls`` accepts, as the retired loop chose it."""
    import pywintypes
    import win32security

    for candidate in _operator_account_candidates():
        try:
            win32security.LookupAccountName(None, candidate)
        except pywintypes.error:
            continue
        return candidate
    raise AssertionError("no operator account spelling resolves on this host")


def _dacl_shape(path: Path) -> _DaclShape:
    import win32security

    descriptor = win32security.GetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.OWNER_SECURITY_INFORMATION,
    )
    control, _revision = descriptor.GetSecurityDescriptorControl()
    owner = win32security.ConvertSidToStringSid(descriptor.GetSecurityDescriptorOwner())
    dacl = _dacl_of(descriptor)
    aces: list[tuple[int, int, int, str]] = []
    if dacl is not None:
        for index in range(dacl.GetAceCount()):
            ace = dacl.GetAce(index)
            (ace_type, ace_flags), mask, sid = ace[0], ace[1], ace[-1]
            aces.append((ace_type, ace_flags, mask, win32security.ConvertSidToStringSid(sid)))
    return bool(control & win32security.SE_DACL_PROTECTED), owner, tuple(aces)


def _fresh(_path: Path) -> None:
    return None


def _foreign_explicit_aces(path: Path) -> None:
    for args in (
        ("/grant", f"{_USERS_SID}:(R)"),
        ("/deny", f"{_GUESTS_SID}:(W)"),
        ("/grant", f"{_operator()}:(RX)"),
    ):
        assert _icacls(path, *args)[0] == 0


def _operator_same_flags_before_foreign(path: Path) -> None:
    assert _icacls(path, "/grant", f"{_USERS_SID}:(OI)(CI)(R)")[0] == 0
    assert _icacls(path, "/grant", f"{_operator()}:(OI)(CI)(RX)")[0] == 0


def _operator_deny_and_other_flags(path: Path) -> None:
    assert _icacls(path, "/deny", f"{_operator()}:(D)")[0] == 0
    assert _icacls(path, "/grant", f"{_operator()}:(OI)(RX)")[0] == 0


def _null_dacl(path: Path) -> None:
    import win32security

    win32security.SetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        None,
        None,
    )


_SHAPES: dict[str, Callable[[Path], None]] = {
    "inherited-only": _fresh,
    "foreign-explicit-aces": _foreign_explicit_aces,
    "operator-same-flags-before-foreign": _operator_same_flags_before_foreign,
    "operator-deny-and-other-flags": _operator_deny_and_other_flags,
    "null-dacl": _null_dacl,
}


@pytest.mark.parametrize("shape", sorted(_SHAPES))
def test_directory_hardening_matches_icacls(tmp_path: Path, shape: str) -> None:
    rewritten = tmp_path / "rewritten"
    reference = tmp_path / "reference"
    rewritten.mkdir()
    reference.mkdir()

    if os.name != "nt":
        restrict_directory_permissions(rewritten)
        assert stat.S_IMODE(rewritten.stat().st_mode) == 0o700
        rewritten.chmod(0o755)
        assert stat.S_IMODE(rewritten.stat().st_mode) != 0o700, (
            "the platform accepted a mode change without applying it, so the assertion above proves nothing"
        )
        return

    for directory in (rewritten, reference):
        _SHAPES[shape](directory)
    prepared = _dacl_shape(rewritten)
    assert prepared == _dacl_shape(reference), "the twins must start from the same DACL"
    assert prepared[0] is (shape == "null-dacl"), "only the NULL-DACL shape starts protected"

    restrict_directory_permissions(rewritten)
    returncode, output = _icacls(reference, "/inheritance:r", "/grant:r", f"{_operator()}:(OI)(CI)F")
    assert returncode == 0, output

    hardened = _dacl_shape(rewritten)
    assert hardened == _dacl_shape(reference)
    assert hardened[0], "hardening must protect the DACL"
    import win32security

    assert all(not flags & win32security.INHERITED_ACE for _type, flags, _mask, _sid in hardened[2]), (
        "no inherited ACE may survive"
    )
