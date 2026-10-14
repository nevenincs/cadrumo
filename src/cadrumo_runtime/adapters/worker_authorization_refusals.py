"""Exact refusal categories received over worker authorization transport."""

from __future__ import annotations

from typing import NoReturn

from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.profile_access import AccessRefusal


def raise_worker_access_refusal(reply: AccessRefusal) -> NoReturn:
    """Preserve the received access, custody, or native transport refusal type."""
    if isinstance(reply.code, AccessDenialCode):
        raise ProfileAccessRefusedError(reply.code)
    if isinstance(reply.code, AutomationCustodyCode):
        raise AutomationCustodyError(reply.code)
    raise RefusalError(reply.code)
