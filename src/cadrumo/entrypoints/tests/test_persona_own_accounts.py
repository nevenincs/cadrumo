"""A persona's stated own bank accounts reach the register with the roles it designates them for."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...application.ledger.own_account_operation import (
    LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
    LedgerOwnAccountRequest,
    LedgerOwnAccountResult,
)
from ...core.iban import mask_iban
from ...domain.transactions.own_accounts import OwnAccountHolding, OwnAccountRole
from ...tests.personas import persona_ids
from .persona_materialisation import ReplayScope, materialised_persona, run_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("persona_id", persona_ids())
def test_the_register_holds_the_accounts_a_persona_states_with_their_designations(
    tmp_path: Path, persona_id: str
) -> None:
    with materialised_persona(persona_id, tmp_path, ReplayScope.FULL) as materialised:
        persona, world = materialised.persona, materialised.world
        listed = run_operation(
            world,
            LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
            LedgerOwnAccountRequest(profile_id=world.profile_id, action="list"),
            LedgerOwnAccountResult,
        )

    # The register hands out ordinal identities in the order the accounts are added.
    stated = {f"acc-{index:02d}": account for index, account in enumerate(persona.own_accounts, start=1)}
    assert {item.own_account_id: (item.label, item.holding, item.masked_iban) for item in listed.accounts} == {
        own_account_id: (account.label, OwnAccountHolding(account.holding), mask_iban(account.iban))
        for own_account_id, account in stated.items()
    }
    assert {(item.role, item.modelo, item.own_account_id) for item in listed.designations} == {
        (OwnAccountRole(designation.role), designation.modelo, own_account_id)
        for own_account_id, account in stated.items()
        for designation in account.designations
    }


def test_a_persona_with_a_refund_states_the_account_that_receives_it(tmp_path: Path) -> None:
    with materialised_persona("asalariada-familia", tmp_path, ReplayScope.FULL) as materialised:
        persona, world = materialised.persona, materialised.world
        listed = run_operation(
            world,
            LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
            LedgerOwnAccountRequest(profile_id=world.profile_id, action="list"),
            LedgerOwnAccountResult,
        )

    (account,) = persona.own_accounts
    assert [(item.role, item.modelo) for item in listed.designations] == [(OwnAccountRole.REFUND, "100")]
    assert [item.masked_iban for item in listed.accounts] == [mask_iban(account.iban)]
