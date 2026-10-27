"""Allowlisted authorization refusal at private-operation and effect boundaries."""

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.sign_in_outcomes import SignInRefusal

from ...core.errors.hierarchy import CadrumoError


class ProfileAccessRefusedError(CadrumoError):
    """Prevent entry into a protected body without disclosing request operands."""

    def __init__(
        self,
        reason: AccessDenialCode,
        *,
        sign_in: SignInRefusal | None = None,
        holder_operation_id: str | None = None,
        recovery_remaining_seconds: int | None = None,
    ) -> None:
        """Carry the current policy's stable refusal code, and the operation that holds a busy subject.

        A session suspended for custody recovery also carries the whole
        seconds left in its recovery window.
        """
        if holder_operation_id is not None and reason is not AccessDenialCode.SUBJECT_BUSY:
            raise ValueError("only a busy subject names the operation that holds it")
        if recovery_remaining_seconds is not None and reason is not AccessDenialCode.CUSTODY_RECOVERING:
            raise ValueError("only a session suspended for custody recovery carries a recovery window")
        self.reason = reason
        self.sign_in = sign_in
        # Every error context copies public attributes; only a refusal that has a holder names one.
        self._holder_operation_id = holder_operation_id
        self._recovery_remaining_seconds = recovery_remaining_seconds
        super().__init__(reason.value)

    @property
    def holder_operation_id(self) -> str | None:
        """The unsettled operation that holds a busy subject, when the supervisor named one."""
        return self._holder_operation_id

    @property
    def recovery_remaining_seconds(self) -> int | None:
        """Whole seconds left in a suspended session's recovery window, for a ``custody_recovering`` refusal."""
        return self._recovery_remaining_seconds
