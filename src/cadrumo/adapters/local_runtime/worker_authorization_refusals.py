"""Exact refusal categories received over worker authorization transport."""

from __future__ import annotations

from typing import NoReturn

from ...application.runtime.contracts import RuntimeRefusalError
from ...application.runtime.profile_access import RuntimeAccessRefusal
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError


def raise_worker_access_refusal(reply: RuntimeAccessRefusal) -> NoReturn:
    """Preserve the received access, custody, or native transport refusal type."""
    if isinstance(reply.code, AccessDenialCode):
        raise ProfileAccessRefusedError(reply.code)
    if isinstance(reply.code, AutomationCustodyCode):
        raise AutomationCustodyError(reply.code)
    raise RuntimeRefusalError(reply.code)
