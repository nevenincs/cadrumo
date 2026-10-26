"""An in-memory own-account door over the application's own request logic.

Each request is applied with ``apply_own_account_request`` against a register
held in memory, so screens are driven by the same request validation and masked
projection the registered operation publishes. Removal is refused the way the
worker refuses a referenced account, because the reference check reads the
profile's transaction catalogue, which an in-memory register does not have.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from .....application.ledger.own_account_operation import (
    LedgerOwnAccountRequest,
    LedgerOwnAccountResult,
    apply_own_account_request,
)
from .....core.errors.hierarchy import RecordedRegisteredError
from .....domain.transactions.own_accounts import OwnAccountRegister
from ...account import AccountSessionExpiredError

OWN_ACCOUNT_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
SYNTHETIC_ES_IBAN = "ES9121000418450200051332"
SYNTHETIC_ES_IBAN_2 = "ES7921000813610123456789"
OWN_ACCOUNT_REFUSAL_CODE = "REFUSED_LEDGER_OWN_ACCOUNT_REGISTER_VALIDATION"
OWN_ACCOUNT_REFUSAL_KEY = "errors.refused.refused_ledger_own_account_register_validation"


class _MemoryRegister:
    def __init__(self) -> None:
        self.register = OwnAccountRegister()

    def load(self) -> OwnAccountRegister:
        return self.register

    def mutate(self, change: Callable[[OwnAccountRegister], OwnAccountRegister]) -> OwnAccountRegister:
        self.register = change(self.register)
        return self.register


class MemoryOwnAccountDoor:
    """Apply requests through the application's own action logic; refuse removal as the worker does."""

    def __init__(self) -> None:
        """Start with an empty register and no recorded requests."""
        self.repository = _MemoryRegister()
        self.requests: list[LedgerOwnAccountRequest] = []
        self.expired = False

    @property
    def profile_id(self) -> UUID:
        """The synthetic profile every request names."""
        return OWN_ACCOUNT_PROFILE_ID

    async def __call__(self, request: LedgerOwnAccountRequest) -> LedgerOwnAccountResult:
        """Record and apply one request."""
        self.requests.append(request)
        if self.expired:
            raise AccountSessionExpiredError()
        if request.action == "remove":
            raise RecordedRegisteredError(OWN_ACCOUNT_REFUSAL_CODE, translated_message=OWN_ACCOUNT_REFUSAL_KEY)
        return self.apply(request)

    def apply(self, request: LedgerOwnAccountRequest) -> LedgerOwnAccountResult:
        """Apply one request synchronously, for seeding a register before a screen opens."""
        return apply_own_account_request(request, bucket_id=str(OWN_ACCOUNT_PROFILE_ID), repository=self.repository)


__all__ = [
    "OWN_ACCOUNT_PROFILE_ID",
    "OWN_ACCOUNT_REFUSAL_CODE",
    "OWN_ACCOUNT_REFUSAL_KEY",
    "SYNTHETIC_ES_IBAN",
    "SYNTHETIC_ES_IBAN_2",
    "MemoryOwnAccountDoor",
]
