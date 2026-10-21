"""The closed custody failure codes that cross the wire, and the refusal that carries one.

None carries a native error, a secret or client input.
"""

from __future__ import annotations

from enum import StrEnum

from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.request_faults import RequestFault


class AutomationCustodyCode(StrEnum):
    """Credential-free automation custody failures."""

    UNAVAILABLE = "unavailable"
    NEEDS_USER = "needs_user"
    UNSUPPORTED = "unsupported"
    MISSING = "missing"
    INVALID = "invalid"
    CONFLICT = "conflict"
    CREDENTIAL_REJECTED = "credential_rejected"
    REQUESTER_DISCONNECTED = "requester_disconnected"


class AutomationCustodyError(CadrumoError):
    """Safe failure code with no native error or secret-bearing input."""

    def __init__(self, code: AutomationCustodyCode, *, request_faults: tuple[RequestFault, ...] = ()) -> None:
        """Retain only a safe code and, for a request refused as invalid, the faults that say why.

        Raises:
            ValueError: Faults are given for a code other than ``INVALID``.
        """
        if request_faults and code is not AutomationCustodyCode.INVALID:
            raise ValueError("only an invalid request carries request faults")
        self.reason = code
        self.request_faults = request_faults
        super().__init__(code.value)
