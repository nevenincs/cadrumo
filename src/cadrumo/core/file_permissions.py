r"""Cross-platform best-effort directory-permission hardening for sensitive files.

App-owned sensitive plaintext files must be restricted to the operator's user
account. Browser session state is persisted through secure objects and does not
use this plaintext-file helper.

POSIX: ``chmod 0o700`` is sufficient. Windows: the DACL is rewritten in
process to what ``icacls.exe /inheritance:r /grant:r <user>:<rights>`` would
leave -- inherited ACEs stripped and the DACL protected, explicit ACEs kept,
and the operator's full-control grant set with ``SetEntriesInAcl``'s
``SET_ACCESS`` rule. The operator is resolved from ``DOMAIN\\user`` and then
``user`` so it works on standalone machines and domain-joined hosts.

The Windows branch reads ``USERDOMAIN`` as operating-system ambient context
only. It does not read Cadrumo configuration or make permission tightening an
authorization decision.

"""

from __future__ import annotations

import getpass
import os
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Final

from .logging import get_logger

if TYPE_CHECKING:
    from _win32typing import PyACL, PySECURITY_DESCRIPTOR

_log = get_logger(__name__)

# Named so grep surfaces every read of the operator's domain qualifier.
_USERDOMAIN_ENV_VAR: Final[str] = "USERDOMAIN"


def _operator_account_candidates() -> list[str]:
    username = getpass.getuser()
    # os.environ.get allowlist: USERDOMAIN is a Windows OS-integration
    # variable, not AEAT-prefixed config, so it is read from the environment
    # rather than from Settings.
    userdomain = os.environ.get(_USERDOMAIN_ENV_VAR)
    return [f"{userdomain}\\{username}", username] if userdomain else [username]


def _dacl_of(descriptor: PySECURITY_DESCRIPTOR) -> PyACL | None:
    """Return the descriptor's DACL, or ``None`` for a NULL DACL.

    The published stub declares a ``PyACL`` return, but a NULL DACL -- no DACL
    at all, which grants everyone access -- comes back as ``None``.
    """
    return descriptor.GetSecurityDescriptorDacl()


def _grant_operator_full_control(path: Path, account: str, *, inheritable: bool) -> None:
    """Rewrite ``path``'s DACL as ``icacls /inheritance:r /grant:r account:F`` would.

    Inherited ACEs are dropped and the DACL is protected; explicit ACEs are
    kept, and ``SET_ACCESS`` replaces the account's explicit allow ACE carrying
    the same inheritance flags in place, or appends one.
    """
    import ntsecuritycon
    import win32security

    operator_sid = win32security.LookupAccountName(None, account)[0]
    descriptor = win32security.GetNamedSecurityInfo(
        str(path), win32security.SE_FILE_OBJECT, win32security.DACL_SECURITY_INFORMATION
    )
    current = _dacl_of(descriptor)
    explicit = win32security.ACL() if current is None else current
    for index in reversed(range(explicit.GetAceCount())):
        if explicit.GetAce(index)[0][1] & win32security.INHERITED_ACE:
            explicit.DeleteAce(index)
    grant = {
        "AccessPermissions": ntsecuritycon.FILE_ALL_ACCESS,
        "AccessMode": win32security.SET_ACCESS,
        "Inheritance": (
            win32security.OBJECT_INHERIT_ACE | win32security.CONTAINER_INHERIT_ACE
            if inheritable
            else win32security.NO_INHERITANCE
        ),
        "Trustee": {
            "TrusteeForm": win32security.TRUSTEE_IS_SID,
            "TrusteeType": win32security.TRUSTEE_IS_USER,
            "Identifier": operator_sid,
        },
    }
    win32security.SetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        explicit.SetEntriesInAcl((grant,)),
        None,
    )


def _windows_restrict_to_operator(path: Path, *, inheritable: bool) -> None:
    r"""Strip inherited ACEs from ``path`` and grant the operator full control.

    The ONE Windows ACL implementation. ``inheritable`` selects the grant: a
    directory takes object- and container-inherit so every file and
    subdirectory created inside it inherits the restriction, a file takes a
    non-inheritable grant.

    The DACL is rewritten in process. This used to spawn ``icacls.exe`` --
    twice per call wherever ``USERDOMAIN`` does not resolve -- at ~28 ms per
    spawn. Directory inheritance is still the intended shape: hardening the
    containing directory once and letting the kernel apply the ACL to new
    children keeps per-file writes free of any ACL call.

    Best-effort by contract: every error is swallowed and logged, because a
    hardening side-effect must never abort the flow that triggered it.
    """
    try:
        # Imported here: pywin32 costs several milliseconds to import, and
        # only a process that actually hardens a directory should pay it.
        import pywintypes

        failure = "no operator account candidate was tried"
        for candidate in _operator_account_candidates():
            try:
                _grant_operator_full_control(path, candidate, inheritable=inheritable)
            except pywintypes.error as error:
                # Mirrors the retired icacls loop: any failure for one account
                # spelling moves on to the next.
                failure = f"{candidate}: {error.strerror}"
                continue
            return
        _log.warning("restrict permissions: failed to harden Windows ACLs on %s: %s", path, failure)
    except Exception:
        _log.warning("restrict permissions: best-effort hardening failed on %s", path, exc_info=True)


def restrict_directory_permissions(path: Path) -> None:
    """Best-effort restrict ``path`` and everything later created inside it.

    The O(1) confidentiality boundary for a storage tree. POSIX applies mode
    ``0o700``; Windows strips inherited ACEs and grants the operator
    ``(OI)(CI)F``, so files written into the tree afterwards inherit the
    restriction with no per-write cost.

    Call this when a storage root or namespace directory is created. Do NOT
    call a per-file variant on the write path to achieve the same thing --
    see :func:`_windows_restrict_to_operator` for the measured reason.
    """
    if os.name == "nt":  # pragma: no cover - Windows-specific
        _windows_restrict_to_operator(path, inheritable=True)
        return
    if os.name != "posix":
        return
    try:
        # 0o700 (owner-only) is the intended confidentiality boundary for a
        # secrets/financial-data storage root, not a weaker default to relax.
        os.chmod(path, stat.S_IRWXU)
    except OSError:
        _log.debug("restrict_directory_permissions: chmod failed on %s", path, exc_info=True)


__all__ = ["restrict_directory_permissions"]
