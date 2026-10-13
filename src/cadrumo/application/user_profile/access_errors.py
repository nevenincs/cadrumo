"""Allowlisted authorization refusal at private-operation and effect boundaries."""

from ...core.errors.hierarchy import CadrumoError
from .access_contracts import AccessDenialCode
from .sign_in_refusals import SignInRefusal


class ProfileAccessRefusedError(CadrumoError):
    """Prevent entry into a protected body without disclosing request operands."""

    def __init__(
        self,
        reason: AccessDenialCode,
        *,
        sign_in: SignInRefusal | None = None,
        holder_operation_id: str | None = None,
    ) -> None:
        """Carry the current policy's stable refusal code, and the operation that holds a busy subject."""
        if holder_operation_id is not None and reason is not AccessDenialCode.SUBJECT_BUSY:
            raise ValueError("only a busy subject names the operation that holds it")
        self.reason = reason
        self.sign_in = sign_in
        # Every error context copies public attributes; only a refusal that has a holder names one.
        self._holder_operation_id = holder_operation_id
        super().__init__(reason.value)

    @property
    def holder_operation_id(self) -> str | None:
        """The unsettled operation that holds a busy subject, when the supervisor named one."""
        return self._holder_operation_id
