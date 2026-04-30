"""Cross-platform best-effort file-permission hardening for auth state.

Both the FNMT-certificate-backed authenticator and the Cl@ve Móvil
provider persist session-state JSON containing bearer-equivalent
material (storage state cookies, OAuth tokens, refresh tokens). The
files must be restricted to the operator's user account.

POSIX: ``chmod 0o600`` is sufficient. Windows: ``icacls.exe
/inheritance:r /grant:r <user>:(F)`` strips inherited ACLs and
grants full control to the operator only. The ``icacls`` call is
best-effort and tries both ``DOMAIN\\user`` and ``user`` candidate
names so it works on standalone machines and domain-joined hosts.

The helper is shared between :mod:`aeat.auth._authenticator` and
:mod:`aeat.auth._clave_movil` so the Windows-ACL discipline cannot
diverge between the two session writers.
"""

from __future__ import annotations

import contextlib
import getpass
import os
import subprocess
from pathlib import Path

from ..logging import get_logger

_log = get_logger(__name__)


def restrict_file_permissions(path: Path) -> None:
    """Best-effort restrict ``path`` to the operator's user only.

    POSIX: ``os.chmod(path, 0o600)``.

    Windows: shells out to ``icacls.exe`` to strip inherited ACLs
    and grant ``F`` (Full control) to the operator's account only.
    Tries both ``DOMAIN\\user`` and bare ``user`` candidates because
    standalone machines have no ``USERDOMAIN`` and domain-joined
    machines may need the qualified form. Logs at ``WARNING`` if
    every candidate fails — the file remains on disk with whatever
    ACL it inherited from the parent directory.

    Best-effort: every error is swallowed. The auth flow does not
    abort if hardening fails — the operator's session is still
    written; the worst case is a slightly more permissive ACL than
    intended, surfaced via the warning log.
    """
    if os.name == "nt":  # pragma: no cover - Windows-specific
        username = getpass.getuser()
        icacls_path = Path(os.environ.get("SYSTEMROOT", r"C:\\Windows")) / "System32" / "icacls.exe"
        candidates = [username]
        userdomain = os.environ.get("USERDOMAIN")
        if userdomain:
            candidates.insert(0, f"{userdomain}\\{username}")
        result: subprocess.CompletedProcess[str] | None = None
        for candidate in candidates:
            result = subprocess.run(  # noqa: S603 - local best-effort ACL hardening only
                [
                    str(icacls_path),
                    str(path),
                    "/inheritance:r",
                    "/grant:r",
                    f"{candidate}:(F)",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return
        _log.warning(
            "restrict_file_permissions: failed to harden Windows ACLs on %s: %s",
            path,
            result.stderr.strip() if result is not None and result.stderr else "icacls returned non-zero",
        )
        return
    if os.name != "posix":
        return
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


__all__ = ["restrict_file_permissions"]
