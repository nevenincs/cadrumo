"""Native login-Keychain targeting, refusal categories, and admitted authorization roles."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
)
from .automation_secret_target import require_automation_secret_target
from .macos_keychain_contracts import (
    AUTH_FAILED,
    INTEGRITY_AUTHORIZATIONS,
    INTERACTION_NOT_ALLOWED,
    INTERACTION_REQUIRED,
    OWNER_AUTHORIZATIONS,
    PARTITION_AUTHORIZATIONS,
    RESTRICTED_AUTHORIZATIONS,
    SAFE_AUTHORIZATIONS,
    SUCCESS,
    KeychainAclRole,
)


def keychain_refusal(code: AutomationCustodyCode = AutomationCustodyCode.INVALID) -> AutomationCustodyError:
    """Construct a typed Keychain refusal without retaining credential content."""
    return AutomationCustodyError(code)


def require_keychain_status(status: int) -> None:
    """Translate native status into the original refusal categories."""
    if status == SUCCESS:
        return
    if status in (INTERACTION_NOT_ALLOWED, AUTH_FAILED, INTERACTION_REQUIRED):
        raise keychain_refusal(AutomationCustodyCode.NEEDS_USER)
    raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)


def require_keychain_target(namespace: str, account: str) -> None:
    """Admit the canonical automation target only on native macOS."""
    require_automation_secret_target(namespace, account)
    if sys.platform != "darwin":
        raise keychain_refusal(AutomationCustodyCode.UNSUPPORTED)


def login_keychain_path() -> str:
    """Select the OS user's canonical login database without environment input."""
    if sys.platform != "darwin":
        raise keychain_refusal(AutomationCustodyCode.UNSUPPORTED)
    import pwd

    uid = os.getuid()
    if uid != os.geteuid():
        raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
    home = Path(pwd.getpwuid(uid).pw_dir)
    path = home / "Library" / "Keychains" / "login.keychain-db"
    if not home.is_absolute() or len(os.fsencode(path)) >= 4096:
        raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
    return str(path)


def keychain_acl_role(authorizations: frozenset[str]) -> KeychainAclRole:
    """Recognize the native default roles; an extra permission is unexplained."""
    if authorizations == RESTRICTED_AUTHORIZATIONS:
        return "restricted"
    if authorizations == SAFE_AUTHORIZATIONS:
        return "safe"
    if authorizations == OWNER_AUTHORIZATIONS:
        return "owner"
    if authorizations == INTEGRITY_AUTHORIZATIONS:
        return "integrity"
    if authorizations == PARTITION_AUTHORIZATIONS:
        return "partition"
    raise keychain_refusal()
