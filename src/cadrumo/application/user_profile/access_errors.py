"""Allowlisted authorization refusal at private-operation and effect boundaries."""

from ...core.errors.hierarchy import CadrumoError
from .access_contracts import AccessDenialCode


class ProfileAccessRefusedError(CadrumoError):
    """Prevent entry into a protected body without disclosing request operands."""

    def __init__(self, reason: AccessDenialCode) -> None:
        """Carry only the current policy's stable refusal code."""
        self.reason = reason
        super().__init__(reason.value)
