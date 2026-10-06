"""Allowlisted authorization refusal at private-operation and effect boundaries."""

from ...core.errors.hierarchy import CadrumoError
from .access_contracts import AccessDenialCode
from .sign_in_refusals import SignInRefusal


class ProfileAccessRefusedError(CadrumoError):
    """Prevent entry into a protected body without disclosing request operands."""

    def __init__(self, reason: AccessDenialCode, *, sign_in: SignInRefusal | None = None) -> None:
        """Carry only the current policy's stable refusal code."""
        self.reason = reason
        self.sign_in = sign_in
        super().__init__(reason.value)
