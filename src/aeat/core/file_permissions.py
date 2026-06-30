r"""Cross-platform best-effort file-permission hardening for auth state.

Both the FNMT-certificate-backed authenticator and the Cl@ve Móvil
provider persist session-state JSON containing bearer-equivalent
material (storage-state cookies, OAuth tokens, refresh tokens). The
files must be restricted to the operator's user account.

POSIX: ``chmod 0o600`` is sufficient. Windows: ``icacls.exe
/inheritance:r /grant:r <user>:(F)`` strips inherited ACLs and grants
full control to the operator only. The ``icacls`` call is best-effort
and tries both ``DOMAIN\\user`` and ``user`` candidate names so it works
on standalone machines and domain-joined hosts.

The helper is shared between
:mod:`aeat.adapters.outbound.aeat.auth._authenticator` and
:mod:`aeat.adapters.outbound.aeat.auth._clave_movil` so the Windows-ACL
discipline cannot diverge between the two session writers.

This module is a compatibility/public hardening primitive for plaintext files;
the active AEAT browser-session persistence backend stores session state through
secure objects. The Windows branch reads ``SYSTEMROOT`` and ``USERDOMAIN`` as OS
ambient context only. It does not read AEAT-prefixed configuration or make
permission tightening an authorization decision.

The public :func:`restrict_file_permissions` entry point accepts a
:class:`~pathlib.Path` target and deliberately returns ``None`` even when the
best-effort hardening step cannot be applied.
"""

from __future__ import annotations

import getpass
import os
import subprocess
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


def restrict_file_permissions(path: Path) -> None:
    r"""Best-effort restrict ``path`` to the operator's user account.

    POSIX: calls :func:`os.chmod` with mode ``0o600``.

    Windows: shells out to ``icacls.exe`` to strip inherited ACLs and
    grant ``F`` (Full control) to the operator's account only. Tries
    both ``DOMAIN\\user`` and bare ``user`` candidates because standalone
    machines have no ``USERDOMAIN`` and domain-joined machines may need
    the qualified form. The subprocess is time-bounded so a wedged
    ``icacls.exe`` cannot block the auth-state writer indefinitely. Logs
    at ``WARNING`` when every candidate fails — the file stays on disk
    with whatever ACL it inherited from its parent directory.

    Best-effort: every error is swallowed so the auth flow never aborts
    on a hardening side-effect. Worst case is a slightly more permissive
    ACL than intended, surfaced via the warning log. Callers that need a
    confidentiality boundary should use the secure-object storage path rather
    than relying on this post-write permission adjustment.

    Args:
        path: Path to the file whose permissions must be tightened.
    """
    if os.name == "nt":  # pragma: no cover - Windows-specific
        # Wrap every Windows-only call in a single try/except so the
        # docstring's "best-effort, never raises" contract holds even
        # when icacls.exe is missing from PATH (FileNotFoundError),
        # getpass.getuser() raises (no operator name available), or
        # the subprocess.run hits an unexpected OSError.
        try:
            username = getpass.getuser()
            # os.environ.get allowlist: SYSTEMROOT / USERDOMAIN are Windows OS-integration
            # variables, not AEAT-prefixed config.  There is no Settings field for them
            # because they are OS-provided ambient context, not application configuration.
            # The single-surface invariant test scanner only flags AEAT_* keys; these are
            # intentionally read directly from the OS environment here.
            icacls_path = Path(os.environ.get(_SYSTEMROOT_ENV_VAR, r"C:\\Windows")) / "System32" / "icacls.exe"
            candidates = [username]
            userdomain = os.environ.get(_USERDOMAIN_ENV_VAR)
            if userdomain:
                candidates.insert(0, f"{userdomain}\\{username}")
            result: subprocess.CompletedProcess[str] | None = None
            for candidate in candidates:
                result = subprocess.run(
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
                    timeout=_ICACLS_TIMEOUT_SECONDS,
                )
                if result.returncode == 0:
                    return
            _log.warning(
                "restrict_file_permissions: failed to harden Windows ACLs on %s: %s",
                path,
                result.stderr.strip() if result is not None and result.stderr else "icacls returned non-zero",
            )
        except Exception:
            # Catch Exception (not just OSError) so the docstring's
            # "every error is swallowed" contract truly holds. The
            # candidates that have actually been observed are
            # ``OSError`` (icacls.exe missing → FileNotFoundError;
            # subprocess.run / icacls write to a path the operator
            # cannot ACL), but a future ``getpass`` / ``subprocess``
            # internal change could surface other exception types
            # here, and the auth flow must NOT abort because of a
            # best-effort hardening side-effect. ``KeyError`` is
            # not in the catch list because ``os.environ.get``
            # returns ``None`` rather than raising on a missing key.
            _log.warning(
                "restrict_file_permissions: best-effort hardening failed on %s",
                path,
                exc_info=True,
            )
        return
    if os.name != "posix":
        return
    try:
        os.chmod(path, 0o600)
    except OSError:
        _log.debug("restrict_file_permissions: chmod failed on %s", path, exc_info=True)


__all__ = ["restrict_file_permissions"]
