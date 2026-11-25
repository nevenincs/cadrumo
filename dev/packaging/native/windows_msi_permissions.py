"""Check whether installation files inherit public destination permissions."""

from __future__ import annotations

import os
from pathlib import Path


def public_install_permissions(path: Path) -> bool:
    """Skip publication copies only for destination-inherited public file permissions."""
    if os.name != "nt":
        return True
    import win32security

    security = win32security.GetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION,
    )
    control, _ = security.GetSecurityDescriptorControl()
    acl = security.GetSecurityDescriptorDacl()
    return (
        not control & win32security.SE_DACL_PROTECTED
        and acl is not None
        and all(acl.GetAce(index)[0][1] & win32security.INHERITED_ACE for index in range(acl.GetAceCount()))
    )
