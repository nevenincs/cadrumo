r"""Cross-platform best-effort file-permission hardening for sensitive files.

App-owned sensitive plaintext files must be restricted to the operator's user
account. Browser session state is persisted through secure objects and does not
use this plaintext-file helper.

POSIX: ``chmod 0o600`` is sufficient. Windows: ``icacls.exe
/inheritance:r /grant:r <user>:(F)`` strips inherited ACLs and grants
full control to the operator only. The ``icacls`` call is best-effort
and tries both ``DOMAIN\\user`` and ``user`` candidate names so it works
on standalone machines and domain-joined hosts.

The Windows branch reads ``SYSTEMROOT`` and ``USERDOMAIN`` as operating-system
ambient context only. It does not read Cadrumo configuration or make permission
tightening an authorization decision.

The public :func:`restrict_file_permissions` entry point accepts a
:class:`~pathlib.Path` target and deliberately returns ``None`` even when the
best-effort hardening step cannot be applied.

"""

from __future__ import annotations

import getpass
import os
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from .logging import get_logger

_log = get_logger(__name__)

# Windows environment variable names used to locate icacls.exe and the
# operator's domain-qualified username.  Named constants so grep surfaces
# every usage site rather than having bare strings spread across the code.
_SYSTEMROOT_ENV_VAR: Final[str] = "SYSTEMROOT"
_USERDOMAIN_ENV_VAR: Final[str] = "USERDOMAIN"
_ICACLS_TIMEOUT_SECONDS: Final[float] = 10.0


def _run_permission_command(
    args: Sequence[str],
    *,
    timeout: float = _ICACLS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _restrict_posix_file_permissions(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        _log.debug("restrict_file_permissions: chmod failed on %s", path, exc_info=True)


def _windows_restrict_to_operator(path: Path, *, inheritable: bool) -> None:
    r"""Strip inherited ACEs from ``path`` and grant the operator full control.

    The ONE Windows ACL implementation. ``inheritable`` selects the rights
    string: a directory takes ``(OI)(CI)F`` so every file and subdirectory
    created inside it inherits the restriction, a file takes plain ``F``.

    Directory inheritance is why this is affordable. Restricting each file as
    it is written costs an ``icacls.exe`` spawn per write (~28 ms measured),
    which is O(N) across the blob and journal writers and turns a bulk import
    of taxpayer evidence into minutes of subprocess overhead. Hardening the
    containing directory once and letting the kernel apply the ACL to new
    children is O(1) and gives the same confidentiality.

    Best-effort by contract: every error is swallowed and logged, because a
    hardening side-effect must never abort the flow that triggered it.
    """
    try:
        username = getpass.getuser()
        # os.environ.get allowlist: SYSTEMROOT / USERDOMAIN are Windows
        # OS-integration variables, not AEAT-prefixed config, so they are read
        # from the environment rather than from Settings.
        icacls_path = Path(os.environ.get(_SYSTEMROOT_ENV_VAR, r"C:\Windows")) / "System32" / "icacls.exe"
        rights = "(OI)(CI)F" if inheritable else "(F)"
        candidates = [username]
        userdomain = os.environ.get(_USERDOMAIN_ENV_VAR)
        if userdomain:
            candidates.insert(0, f"{userdomain}\\{username}")
        result: subprocess.CompletedProcess[str] | None = None
        for candidate in candidates:
            result = _run_permission_command(
                [
                    str(icacls_path),
                    str(path),
                    "/inheritance:r",
                    "/grant:r",
                    f"{candidate}:{rights}",
                ],
            )
            if result.returncode == 0:
                return
        _log.warning(
            "restrict permissions: failed to harden Windows ACLs on %s: %s",
            path,
            result.stderr.strip() if result is not None and result.stderr else "icacls returned non-zero",
        )
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


def restrict_file_permissions(path: Path) -> None:
    r"""Best-effort restrict a single ``path`` to the operator's user account.

    POSIX applies mode ``0o600``; Windows delegates to the one ACL
    implementation, :func:`_windows_restrict_to_operator`, with non-inheritable
    rights.

    Prefer :func:`restrict_directory_permissions` on the containing directory.
    This per-file variant costs an ``icacls.exe`` spawn per call on Windows
    (~28 ms measured), so it is for one-shot targets written outside a hardened
    tree -- never for a write path that runs per record. The durable writers
    deliberately do NOT call it; their confidentiality comes from the storage
    tree's inherited ACL.

    Best-effort: every error is swallowed and logged, so a hardening
    side-effect never aborts the flow that triggered it.
    """
    if os.name == "nt":  # pragma: no cover - Windows-specific
        _windows_restrict_to_operator(path, inheritable=False)
        return
    if os.name != "posix":
        return
    _restrict_posix_file_permissions(path)


__all__ = ["restrict_directory_permissions", "restrict_file_permissions"]
