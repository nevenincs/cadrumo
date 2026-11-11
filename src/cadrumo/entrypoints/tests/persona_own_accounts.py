"""Replay a persona's own bank accounts and their role designations through the ledger own-account operation."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel

from ...application.ledger.own_account_operation import (
    LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
    LedgerOwnAccountRequest,
    LedgerOwnAccountResult,
)
from ...domain.transactions.own_accounts import OwnAccountHolding, OwnAccountRole
from ...tests.personas import OwnAccount, Persona

type SettleOperation = Callable[[str, BaseModel], BaseModel | None]
"""Settles one registered operation against the persona's profile and returns its public result."""


class PersonaOwnAccountError(RuntimeError):
    """The own-account operation published no account for a persona account it accepted."""


def _added(account: OwnAccount, profile_id: UUID, settle: SettleOperation) -> str:
    result = settle(
        LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
        LedgerOwnAccountRequest(
            profile_id=profile_id,
            action="add",
            label=account.label,
            holding=OwnAccountHolding(account.holding),
            iban=account.iban,
        ),
    )
    if not isinstance(result, LedgerOwnAccountResult) or result.own_account_id is None:
        raise PersonaOwnAccountError(f"{account.label}: adding the account published no account identity")
    return result.own_account_id


def replay_own_accounts(persona: Persona, profile_id: UUID, settle: SettleOperation) -> None:
    """Register each account the persona states, then designate it for each role it states."""
    for account in persona.own_accounts:
        own_account_id = _added(account, profile_id, settle)
        for designation in account.designations:
            settle(
                LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
                LedgerOwnAccountRequest(
                    profile_id=profile_id,
                    action="designate",
                    own_account_id=own_account_id,
                    role=OwnAccountRole(designation.role),
                    modelo=designation.modelo,
                ),
            )


__all__ = ["PersonaOwnAccountError", "SettleOperation", "replay_own_accounts"]
