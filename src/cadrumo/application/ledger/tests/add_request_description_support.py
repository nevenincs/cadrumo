"""The description the runtime serves for ``ledger.add``, taken from the real registered operation."""

from __future__ import annotations

from functools import lru_cache

from ...ledger.action_ports import LedgerActionPorts
from ...operations.registry import OperationPublicDefinitionDescriptionV1, OperationRegistry
from ...prorrata_register.ports import ProrrataRegisterServiceRepositoryProtocol
from .. import add_operation
from ..ledger_add_contracts import LEDGER_ADD_OPERATION_DEFINITION_ID
from ..own_account_ports import OwnAccountRepositoryProtocol


@lru_cache(maxsize=1)
def ledger_add_registry() -> OperationRegistry:
    """A registry holding the real ``ledger.add`` definition and public registration.

    The factories are never called: describing an operation constructs no executor.
    """

    def unused_ports(**_: object) -> LedgerActionPorts:
        raise AssertionError("describing ledger.add must not open ledger ports")

    def unused_register(**_: object) -> ProrrataRegisterServiceRepositoryProtocol:
        raise AssertionError("describing ledger.add must not open the prorrata register")

    def unused_own_accounts(**_: object) -> OwnAccountRepositoryProtocol:
        raise AssertionError("describing ledger.add must not open own accounts")

    definition = add_operation.build_ledger_add_definition(unused_ports, unused_register, unused_own_accounts)
    return OperationRegistry(
        definitions=(definition,), public_registrations=(add_operation.build_ledger_add_registration(definition),)
    )


def ledger_add_description() -> OperationPublicDefinitionDescriptionV1:
    """The fingerprint-checked description of ``ledger.add`` the runtime serves."""
    return ledger_add_registry().describe_public_definition(LEDGER_ADD_OPERATION_DEFINITION_ID)
