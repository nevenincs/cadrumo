"""Registered ledger operation that sets up the taxpayer's own bank accounts.

One exact-profile operation adds, lists, shows, updates, closes and removes own
accounts and designates them for the charge and refund roles. Account numbers
arrive only in the secure request; the published result carries the masked view
(country code and last four characters) and the opaque ``own_account_id``, never
an IBAN, a BIC or a foreign-bank block.

An account that ledger transactions reference is closed rather than removed, so
the transactions keep a resolvable account; a designated account must be
redesignated first.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from typing import Final, Literal
from uuid import UUID

import pydantic
from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.hierarchy import InternalInvariantError
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.transactions.own_accounts import (
    OwnAccountDesignation,
    OwnAccountHolding,
    OwnAccountId,
    OwnAccountRegister,
    OwnAccountRegisterValidationError,
    OwnAccountRole,
    OwnBankAccount,
    OwnBankAccountDetails,
)
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.fenced_result import publish_fenced_result
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .own_account_ports import OwnAccountRepositoryFactory, OwnAccountRepositoryProtocol
from .read_access import resolve_ledger_commit_access, resolve_ledger_read_access
from .transaction_repository import transaction_catalogue_repository

LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID = "ledger.own_account"

OwnAccountAction = Literal["add", "list", "show", "update", "close", "remove", "designate", "undesignate"]

_READ_ACTIONS: Final = frozenset({"list", "show"})
# Public schemas carry the modelo as plain text; the domain Modelo type is rebuilt inside the worker.
_MODELO_PATTERN: Final = r"^[0-9]{3}$"
_DETAIL_FIELDS: Final = (
    "label",
    "holding",
    "iban",
    "swift_bic",
    "bank_name",
    "bank_address",
    "bank_city",
    "bank_country_code",
    "currency",
    "opened_on",
)


class LedgerOwnAccountRequest(BaseModel):
    """One exact-profile own-account action; account material is private input.

    ``add`` takes the full details, ``update`` replaces only the details it
    names, ``close`` takes ``closed_on``, and the designation actions take a
    ``role`` with an optional ``modelo`` (absent means every modelo).
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    action: OwnAccountAction
    own_account_id: OwnAccountId | None = None
    label: str | None = Field(default=None, min_length=1, max_length=80)
    holding: OwnAccountHolding | None = None
    iban: str | None = Field(default=None, max_length=64)
    swift_bic: str | None = Field(default=None, max_length=16)
    bank_name: str | None = Field(default=None, max_length=70)
    bank_address: str | None = Field(default=None, max_length=35)
    bank_city: str | None = Field(default=None, max_length=30)
    bank_country_code: str | None = Field(default=None, max_length=2)
    currency: str | None = Field(default=None, max_length=3)
    opened_on: date | None = None
    closed_on: date | None = None
    role: OwnAccountRole | None = None
    modelo: str | None = Field(default=None, pattern=_MODELO_PATTERN)

    @model_validator(mode="after")
    def _action_fields(self) -> LedgerOwnAccountRequest:
        details = [name for name in _DETAIL_FIELDS if getattr(self, name) is not None]
        needs_id = self.action in {"show", "update", "close", "remove", "designate"}
        if needs_id != (self.own_account_id is not None):
            raise ValueError(f"own account action {self.action!r} {'requires' if needs_id else 'takes no'} account id")
        if details and self.action not in {"add", "update"}:
            raise ValueError(f"own account action {self.action!r} takes no account details")
        if self.action == "add" and (self.label is None or self.holding is None or self.iban is None):
            raise ValueError("adding an own account requires its label, holding and IBAN")
        if self.action == "update" and not details:
            raise ValueError("updating an own account requires at least one detail")
        if (self.action == "close") != (self.closed_on is not None):
            raise ValueError("closed_on is given exactly when closing an own account")
        designating = self.action in {"designate", "undesignate"}
        if designating != (self.role is not None) or (self.modelo is not None and not designating):
            raise ValueError("role and modelo are given only to designate or undesignate")
        return self


class OwnAccountProjection(BaseModel):
    """Masked operator view of one own account."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    own_account_id: OwnAccountId
    label: str
    holding: OwnAccountHolding
    masked_iban: str
    country_code: str = Field(min_length=2, max_length=2)
    sepa_marca: str = Field(min_length=1, max_length=1)
    has_swift_bic: bool
    has_bank_block: bool
    currency: str = Field(min_length=3, max_length=3)
    opened_on: date | None = None
    closed_on: date | None = None

    @classmethod
    def from_account(cls, account: OwnBankAccount) -> OwnAccountProjection:
        """Project an account onto its masked, material-free view."""
        return cls(
            own_account_id=account.own_account_id,
            label=account.label,
            holding=account.holding,
            masked_iban=account.masked_iban,
            country_code=account.country_code,
            sepa_marca=account.sepa_marca.value,
            has_swift_bic=bool(account.swift_bic),
            has_bank_block=bool(account.bank_name),
            currency=account.currency,
            opened_on=account.opened_on,
            closed_on=account.closed_on,
        )


class OwnAccountDesignationProjection(BaseModel):
    """One role designation: role, scope (``None`` for every modelo) and account id."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    role: OwnAccountRole
    modelo: str | None = Field(default=None, pattern=_MODELO_PATTERN)
    own_account_id: OwnAccountId

    @classmethod
    def from_designation(cls, designation: OwnAccountDesignation) -> OwnAccountDesignationProjection:
        """Copy a designation onto the result."""
        modelo = None if designation.modelo is None else designation.modelo.value
        return cls(role=designation.role, modelo=modelo, own_account_id=designation.own_account_id)


class LedgerOwnAccountResult(BaseModel):
    """Encrypted operation result: masked accounts, designations and whether anything changed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    action: OwnAccountAction
    own_account_id: OwnAccountId | None = None
    accounts: tuple[OwnAccountProjection, ...] = ()
    designations: tuple[OwnAccountDesignationProjection, ...] = ()
    changed: bool = False


def _details(fields: dict[str, object]) -> OwnBankAccountDetails:
    """Validate operator details, surfacing the register's registered refusal."""
    try:
        return OwnBankAccountDetails.model_validate(fields)
    except pydantic.ValidationError as error:
        # Input is hidden from these messages, so they never carry account material.
        reasons = "; ".join(detail["msg"] for detail in error.errors())
        raise OwnAccountRegisterValidationError(f"own account details are not valid: {reasons}") from None


def _requested_details(payload: LedgerOwnAccountRequest) -> dict[str, object]:
    return {name: value for name in _DETAIL_FIELDS if (value := getattr(payload, name)) is not None}


def _updated_details(current: OwnBankAccount, payload: LedgerOwnAccountRequest) -> OwnBankAccountDetails:
    merged: dict[str, object] = {name: getattr(current, name) for name in OwnBankAccountDetails.model_fields}
    merged.update(_requested_details(payload))
    return _details(merged)


def _require_unreferenced(bucket_id: str, own_account_id: str) -> None:
    catalogue = transaction_catalogue_repository(bucket_id=bucket_id).load()
    if any(transaction.own_account_id == own_account_id for transaction in catalogue.transactions.values()):
        raise OwnAccountRegisterValidationError(
            f"own account {own_account_id!r} is referenced by ledger transactions; close it instead",
        )


type _RegisterChange = Callable[[OwnAccountRegister], OwnAccountRegister]


def _required[T](value: T | None, name: str) -> T:
    # The request validator already demanded the field for this action.
    if value is None:
        raise InternalInvariantError(f"own account request reached its action without {name}")
    return value


def _modelo(payload: LedgerOwnAccountRequest) -> Modelo | None:
    return None if payload.modelo is None else Modelo(payload.modelo)


def _change_for(payload: LedgerOwnAccountRequest, *, bucket_id: str) -> _RegisterChange:
    """Return the register change ``payload`` asks for; it is re-applied on a concurrent write."""
    if payload.action == "add":
        details = _details(_requested_details(payload))
        return lambda current: current.with_new_account(details)
    if payload.action == "undesignate":
        role = _required(payload.role, "role")
        return lambda current: current.without_designation(role, _modelo(payload))
    account_id = _required(payload.own_account_id, "own_account_id")
    if payload.action == "update":
        return lambda current: current.with_updated_account(
            account_id,
            _updated_details(current.account(account_id), payload),
        )
    if payload.action == "close":
        closed_on = _required(payload.closed_on, "closed_on")
        return lambda current: current.with_closed_account(account_id, closed_on)
    if payload.action == "designate":
        designation = OwnAccountDesignation(
            role=_required(payload.role, "role"),
            modelo=_modelo(payload),
            own_account_id=account_id,
        )
        return lambda current: current.with_designation(designation)

    def remove(current: OwnAccountRegister) -> OwnAccountRegister:
        current.account(account_id)
        _require_unreferenced(bucket_id, account_id)
        return current.without_account(account_id)

    return remove


def _result(
    payload: LedgerOwnAccountRequest,
    register: OwnAccountRegister,
    *,
    own_account_id: str | None,
    changed: bool,
) -> LedgerOwnAccountResult:
    """Project the register for ``payload``: one account when the action names one, else all."""
    if payload.action == "remove":
        accounts: tuple[OwnBankAccount, ...] = ()
        designations = register.designations
    elif own_account_id is None:
        accounts = register.accounts
        designations = register.designations
    else:
        accounts = (register.account(own_account_id),)
        designations = register.designations_of(own_account_id)
    return LedgerOwnAccountResult(
        profile_id=payload.profile_id,
        action=payload.action,
        own_account_id=own_account_id,
        accounts=tuple(OwnAccountProjection.from_account(account) for account in accounts),
        designations=tuple(OwnAccountDesignationProjection.from_designation(item) for item in designations),
        changed=changed,
    )


def apply_own_account_request(
    payload: LedgerOwnAccountRequest,
    *,
    bucket_id: str,
    repository: OwnAccountRepositoryProtocol,
) -> LedgerOwnAccountResult:
    """Read or apply the declared action against the bucket's register and project the masked result."""
    if payload.action in _READ_ACTIONS:
        return _result(payload, repository.load(), own_account_id=payload.own_account_id, changed=False)
    before = repository.load()
    after = repository.mutate(_change_for(payload, bucket_id=bucket_id))
    own_account_id = payload.own_account_id
    if payload.action == "add":
        own_account_id = after.accounts[-1].own_account_id
    return _result(payload, after, own_account_id=own_account_id, changed=after != before)


async def _publish_own_account_action(
    context: OperationExecutorContext,
    *,
    payload: LedgerOwnAccountRequest,
    bucket_id: str,
    repository_factory: OwnAccountRepositoryFactory,
) -> str:
    """Publish reads without effect and settle mutations through the irreversible fence."""

    async def run_action() -> LedgerOwnAccountResult:
        return await asyncio.to_thread(
            apply_own_account_request,
            payload,
            bucket_id=bucket_id,
            repository=repository_factory(bucket_id=bucket_id),
        )

    return await publish_fenced_result(
        context,
        run_action=run_action,
        is_read=payload.action in _READ_ACTIONS,
        result_changed=lambda result: result.changed,
    )


class LedgerOwnAccountExecutor:
    """Apply own-account actions inside the profile worker's access fence."""

    def __init__(self, repository_factory: OwnAccountRepositoryFactory) -> None:
        """Keep the profile-bound register factory in the worker."""
        self._repository_factory = repository_factory

    async def execute(
        self,
        request: OperationRequest[LedgerOwnAccountRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Apply the selected action and publish its encrypted, masked result."""
        payload = request.payload
        if request.definition_id != LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID)
        return await await_cancellation_complete(
            _publish_own_account_action(
                context,
                payload=payload,
                bucket_id=str(payload.profile_id),
                repository_factory=self._repository_factory,
            ),
            task_name="ledger-own-account",
        )


def build_ledger_own_account_definition(repository_factory: OwnAccountRepositoryFactory) -> OperationDefinition:
    """Declare private input, a recorded result and honest mutation effects."""
    return build_single_phase_definition(
        definition_id=LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
        request_type=LedgerOwnAccountRequest,
        result_type=LedgerOwnAccountResult,
        executor_type=LedgerOwnAccountExecutor,
        build=lambda: LedgerOwnAccountExecutor(repository_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def resolve_ledger_own_account_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Require whole-profile scope, and COMMIT for mutations."""
    if request.definition_id != LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID or not isinstance(
        request.payload,
        LedgerOwnAccountRequest,
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolve = resolve_ledger_read_access if request.payload.action in _READ_ACTIONS else resolve_ledger_commit_access
    return resolve(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_own_account_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and encrypted result schemas."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerOwnAccountResult,
        access_resolver=resolve_ledger_own_account_access,
    )


__all__ = [
    "LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID",
    "LedgerOwnAccountExecutor",
    "LedgerOwnAccountRequest",
    "LedgerOwnAccountResult",
    "OwnAccountAction",
    "OwnAccountDesignationProjection",
    "OwnAccountProjection",
    "apply_own_account_request",
    "build_ledger_own_account_definition",
    "build_ledger_own_account_registration",
    "resolve_ledger_own_account_access",
]
