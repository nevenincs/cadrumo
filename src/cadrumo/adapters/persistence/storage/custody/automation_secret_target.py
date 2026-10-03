"""The one validity rule for a native automation secret's namespace and account."""

from __future__ import annotations

from typing import Final

from .....application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError

AUTOMATION_NAMESPACE_PREFIX: Final = "cadrumo.automation."
"""Every automation secret lives below this namespace, so no other credential is addressable."""

_MAX_TARGET_CHARACTERS: Final = 1024


def require_automation_secret_target(namespace: str, account: str) -> None:
    """Refuse a namespace/account pair no native credential store may be asked for.

    The namespace must sit strictly below :data:`AUTOMATION_NAMESPACE_PREFIX`,
    the account must be present, the pair must stay within the native size
    ceiling, and neither may carry a control character or text that cannot be
    encoded as UTF-8. The checks are the same for every native backend; each
    backend adds only its own platform availability check afterwards.

    Raises:
        AutomationCustodyError: With the ``INVALID`` code when the pair is refused.
    """
    if (
        not isinstance(namespace, str)
        or not isinstance(account, str)
        or not namespace.startswith(AUTOMATION_NAMESPACE_PREFIX)
        or len(namespace) <= len(AUTOMATION_NAMESPACE_PREFIX)
        or not account
        or len(namespace) + len(account) > _MAX_TARGET_CHARACTERS
        or any(ord(character) < 32 or ord(character) == 127 for character in namespace + account)
    ):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID)
    try:
        namespace.encode("utf-8", errors="strict")
        account.encode("utf-8", errors="strict")
    except UnicodeError:
        raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
