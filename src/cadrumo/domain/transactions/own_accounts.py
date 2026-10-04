"""The taxpayer's own bank accounts and their modelo role designations.

An own account is an account the taxpayer holds, as titular or cotitular,
attested when it is entered. The register is the one store of those accounts:
the ledger links transactions to them and every modelo resolves its charge
(domiciliación) and refund (devolución) account from the designations held here.

Identity is a register-assigned ordinal (``acc-01``, ``acc-02``...). It is never
derived from the account number and never reused, so it is safe in command
arguments, receipts and events and stable across golden replays. The account
number is IBAN-only: an account outside the SEPA zone additionally needs its
SWIFT-BIC and the full foreign-bank block that the DR303 cuenta-devolución
record carries for ``Marca SEPA = 3``.

This module holds the document and its invariants only; it reads no store and
resolves no filing. Every field is financial identity data, so the models hide
rejected input from validation errors and no message names an account number.

See Also:
    :mod:`adapters.persistence.profile.own_accounts`
        FINANCIAL secure-object repository for this document.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core.errors.hierarchy import CadrumoError, CoreValidationError, pydantic_validation_boundary
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.iban import BIC_SHAPE_RE, IBAN_SHAPE_RE, iban_mod_97, mask_iban, normalise_iban
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.parsing.codes import normalise_iso_4217_currency
from ..iva.sepa_marca import SepaMarca, derive_sepa_marca

OWN_ACCOUNT_REGISTER_SCHEMA_VERSION: Final = "1"
"""Schema version stamped on the register document."""

_OWN_ACCOUNT_ID_PREFIX: Final = "acc-"


class OwnAccountRegisterError(CadrumoError):
    """Raised when the own-account register refuses an operation."""


class OwnAccountRegisterValidationError(OwnAccountRegisterError):
    """Raised when a register document, account or designation fails its invariants."""


OwnAccountId = Annotated[str, StringConstraints(pattern=r"^acc-[0-9]{2,}$")]
"""Opaque register-assigned ordinal identity of one own account."""


def own_account_id_for(ordinal: int) -> str:
    """Return the identity of the ``ordinal``-th account the register ever assigned."""
    if ordinal < 1:
        raise OwnAccountRegisterValidationError("own account ordinals start at 1")
    return f"{_OWN_ACCOUNT_ID_PREFIX}{ordinal:02d}"


def _ordinal_of(own_account_id: str) -> int:
    return int(own_account_id.removeprefix(_OWN_ACCOUNT_ID_PREFIX))


class OwnAccountHolding(StrEnum):
    """How the taxpayer holds the account; only a holder's account is an own account."""

    TITULAR = "titular"
    COTITULAR = "cotitular"


class OwnAccountRole(StrEnum):
    """The modelo role an account is designated for."""

    CHARGE = "charge"
    """Cuenta de cargo: the account AEAT debits for a domiciliación."""
    REFUND = "refund"
    """Cuenta de devolución: the account AEAT pays a refund into."""


class OwnBankAccountDetails(BaseModel):
    """The operator-entered facts of one own account, without its register identity.

    Attributes:
        label: Operator name for the account, shown beside its mask.
        holding: The taxpayer's attested holding of the account.
        iban: Canonical IBAN (uppercase, separator-free, mod-97 verified).
        swift_bic: SWIFT-BIC; required outside the SEPA zone.
        bank_name: Foreign-bank name; required outside the SEPA zone.
        bank_address: Foreign-bank address; required outside the SEPA zone.
        bank_city: Foreign-bank city; required outside the SEPA zone.
        bank_country_code: Foreign-bank country; equals the IBAN country when given.
        currency: ISO 4217 currency the account is held in.
        opened_on: When the account was opened, when known.
        closed_on: When the account was closed; a closed account is kept, not deleted.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    label: str = Field(min_length=1, max_length=80)
    holding: OwnAccountHolding
    iban: str
    swift_bic: str = ""
    bank_name: str = Field(default="", max_length=70)
    bank_address: str = Field(default="", max_length=35)
    bank_city: str = Field(default="", max_length=30)
    bank_country_code: str = ""
    currency: str = DEFAULT_CURRENCY
    opened_on: date | None = None
    closed_on: date | None = None

    @field_validator("label", "bank_name", "bank_address", "bank_city", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("iban", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_iban(cls, value: object) -> object:
        if not isinstance(value, str):
            raise OwnAccountRegisterValidationError("own account iban must be a string")
        canonical = normalise_iban(value)
        if not IBAN_SHAPE_RE.match(canonical):
            raise OwnAccountRegisterValidationError("own account iban does not match the ISO 13616 shape")
        if iban_mod_97(canonical) != 1:
            raise OwnAccountRegisterValidationError("own account iban fails the mod-97 check")
        return canonical

    @field_validator("swift_bic", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_bic(cls, value: object) -> object:
        if not isinstance(value, str):
            raise OwnAccountRegisterValidationError("own account swift_bic must be a string")
        canonical = value.replace(" ", "").upper()
        if canonical and not BIC_SHAPE_RE.match(canonical):
            raise OwnAccountRegisterValidationError("own account swift_bic must be 8 or 11 characters per ISO 9362")
        return canonical

    @field_validator("bank_country_code", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_bank_country(cls, value: object) -> object:
        if not isinstance(value, str):
            raise OwnAccountRegisterValidationError("own account bank_country_code must be a string")
        canonical = value.strip().upper()
        if canonical and (len(canonical) != 2 or not canonical.isascii() or not canonical.isalpha()):
            raise OwnAccountRegisterValidationError("own account bank_country_code must be ISO 3166-1 alpha-2")
        return canonical

    @field_validator("currency", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_currency(cls, value: object) -> object:
        try:
            return normalise_iso_4217_currency(value)
        except CoreValidationError as exc:
            raise OwnAccountRegisterValidationError(str(exc)) from exc

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _bank_block_invariants(self) -> OwnBankAccountDetails:
        block = (self.bank_name, self.bank_address, self.bank_city, self.bank_country_code)
        if any(block) and not all(block):
            raise OwnAccountRegisterValidationError(
                "the foreign-bank block needs its name, address, city and country together",
            )
        if self.bank_country_code and self.bank_country_code != self.country_code:
            raise OwnAccountRegisterValidationError("the foreign-bank country must be the IBAN country")
        if self.sepa_marca is SepaMarca.RESTO_PAISES and not (self.swift_bic and all(block)):
            raise OwnAccountRegisterValidationError(
                "an account outside the SEPA zone needs its SWIFT-BIC and the full foreign-bank block",
            )
        if self.opened_on is not None and self.closed_on is not None and self.closed_on < self.opened_on:
            raise OwnAccountRegisterValidationError("an account cannot close before it opened")
        return self

    @property
    def country_code(self) -> str:
        """The account country: the IBAN's ISO 3166-1 prefix."""
        return self.iban[:2]

    @property
    def sepa_marca(self) -> SepaMarca:
        """The DR303 ``Marca SEPA`` the account country derives."""
        return derive_sepa_marca(iban=self.iban)

    @property
    def masked_iban(self) -> str:
        """The operator-facing mask: country code and last four characters."""
        return mask_iban(self.iban)

    def open_on(self, day: date) -> bool:
        """Whether the account can be used on ``day``: opened by then and not yet closed."""
        if self.opened_on is not None and day < self.opened_on:
            return False
        return self.closed_on is None or day <= self.closed_on


class OwnBankAccount(OwnBankAccountDetails):
    """One own account with its register-assigned identity."""

    own_account_id: OwnAccountId

    def with_details(self, details: OwnBankAccountDetails) -> OwnBankAccount:
        """Return this account with ``details`` replacing every operator-entered fact."""
        return OwnBankAccount.model_validate({**_detail_fields(details), "own_account_id": self.own_account_id})


def _detail_fields(details: OwnBankAccountDetails) -> dict[str, object]:
    return {name: getattr(details, name) for name in OwnBankAccountDetails.model_fields}


class OwnAccountDesignation(BaseModel):
    """One role designation: the account a role resolves to, for one modelo or for all.

    ``modelo`` ``None`` is the ALL scope. A modelo-scoped designation wins over
    the ALL designation of the same role.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    role: OwnAccountRole
    modelo: Modelo | None = None
    own_account_id: OwnAccountId

    @property
    def key(self) -> tuple[OwnAccountRole, str | None]:
        """The designation key ``(role, modelo)``; unique within the register."""
        return (self.role, None if self.modelo is None else self.modelo.value)


class OwnAccountRegister(BaseModel):
    """Encrypted register document: the taxpayer's own accounts and their designations.

    ``last_ordinal`` is the highest ordinal ever assigned, so an identity is
    never handed out twice even after its account is removed.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    schema_version: str = OWN_ACCOUNT_REGISTER_SCHEMA_VERSION
    last_ordinal: int = Field(default=0, ge=0)
    accounts: tuple[OwnBankAccount, ...] = ()
    designations: tuple[OwnAccountDesignation, ...] = ()

    @field_validator("schema_version")
    @classmethod
    @pydantic_validation_boundary
    def _schema_version_supported(cls, value: str) -> str:
        if value != OWN_ACCOUNT_REGISTER_SCHEMA_VERSION:
            raise OwnAccountRegisterValidationError(f"unsupported own-account register schema_version {value!r}")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _register_invariants(self) -> OwnAccountRegister:
        ids = [account.own_account_id for account in self.accounts]
        if len(ids) != len(set(ids)):
            raise OwnAccountRegisterValidationError("register carries a repeated own_account_id")
        if any(_ordinal_of(account_id) > self.last_ordinal for account_id in ids):
            raise OwnAccountRegisterValidationError("register carries an own_account_id beyond its last ordinal")
        ibans = [account.iban for account in self.accounts]
        if len(ibans) != len(set(ibans)):
            raise OwnAccountRegisterValidationError("register carries the same account number twice")
        keys = [designation.key for designation in self.designations]
        if len(keys) != len(set(keys)):
            raise OwnAccountRegisterValidationError("register carries two designations for one role and scope")
        unknown = sorted({designation.own_account_id for designation in self.designations} - set(ids))
        if unknown:
            raise OwnAccountRegisterValidationError(f"designations name unregistered accounts: {unknown}")
        return self

    def next_account_id(self) -> str:
        """The identity the next added account receives."""
        return own_account_id_for(self.last_ordinal + 1)

    def account(self, own_account_id: str) -> OwnBankAccount:
        """Return the account ``own_account_id`` or refuse."""
        for account in self.accounts:
            if account.own_account_id == own_account_id:
                return account
        raise OwnAccountRegisterValidationError(f"own account {own_account_id!r} is not registered")

    def designated(self, role: OwnAccountRole, modelo: Modelo) -> OwnBankAccount | None:
        """Resolve ``role`` for ``modelo``: its scoped designation, else the ALL one, else ``None``."""
        scoped = {designation.key: designation for designation in self.designations}
        designation = scoped.get((role, modelo.value)) or scoped.get((role, None))
        return None if designation is None else self.account(designation.own_account_id)

    def designations_of(self, own_account_id: str) -> tuple[OwnAccountDesignation, ...]:
        """The designations that name ``own_account_id``."""
        return tuple(d for d in self.designations if d.own_account_id == own_account_id)

    def with_new_account(self, details: OwnBankAccountDetails) -> OwnAccountRegister:
        """Return a register with ``details`` added under the next ordinal identity."""
        account = OwnBankAccount.model_validate({**_detail_fields(details), "own_account_id": self.next_account_id()})
        return self._replace(last_ordinal=self.last_ordinal + 1, accounts=(*self.accounts, account))

    def with_updated_account(self, own_account_id: str, details: OwnBankAccountDetails) -> OwnAccountRegister:
        """Return a register with the operator-entered facts of ``own_account_id`` replaced."""
        current = self.account(own_account_id)
        return self._replace(
            accounts=tuple(
                current.with_details(details) if account is current else account for account in self.accounts
            ),
        )

    def with_closed_account(self, own_account_id: str, closed_on: date) -> OwnAccountRegister:
        """Return a register with ``own_account_id`` closed on ``closed_on``."""
        current = self.account(own_account_id)
        if current.closed_on is not None:
            raise OwnAccountRegisterValidationError(f"own account {own_account_id!r} is already closed")
        closed = OwnBankAccountDetails.model_validate({**_detail_fields(current), "closed_on": closed_on})
        return self.with_updated_account(own_account_id, closed)

    def without_account(self, own_account_id: str) -> OwnAccountRegister:
        """Return a register without ``own_account_id``; a designated account is refused.

        The caller refuses removal of an account that transactions reference; such
        an account is closed instead.
        """
        current = self.account(own_account_id)
        if self.designations_of(own_account_id):
            raise OwnAccountRegisterValidationError(
                f"own account {own_account_id!r} is designated for a role; redesignate before removing it",
            )
        return self._replace(accounts=tuple(account for account in self.accounts if account is not current))

    def with_designation(self, designation: OwnAccountDesignation) -> OwnAccountRegister:
        """Return a register where ``designation`` replaces any earlier one for its role and scope."""
        kept = tuple(existing for existing in self.designations if existing.key != designation.key)
        return self._replace(designations=(*kept, designation))

    def without_designation(self, role: OwnAccountRole, modelo: Modelo | None) -> OwnAccountRegister:
        """Return a register without the designation for ``role`` and ``modelo``; an absent one is refused."""
        key = (role, None if modelo is None else modelo.value)
        kept = tuple(existing for existing in self.designations if existing.key != key)
        if len(kept) == len(self.designations):
            raise OwnAccountRegisterValidationError("no designation exists for that role and scope")
        return self._replace(designations=kept)

    def _replace(
        self,
        *,
        last_ordinal: int | None = None,
        accounts: tuple[OwnBankAccount, ...] | None = None,
        designations: tuple[OwnAccountDesignation, ...] | None = None,
    ) -> OwnAccountRegister:
        # Rebuilt through the constructor, not model_copy, so every invariant reruns.
        return OwnAccountRegister(
            last_ordinal=self.last_ordinal if last_ordinal is None else last_ordinal,
            accounts=self.accounts if accounts is None else accounts,
            designations=self.designations if designations is None else designations,
        )


__all__ = [
    "OWN_ACCOUNT_REGISTER_SCHEMA_VERSION",
    "OwnAccountDesignation",
    "OwnAccountHolding",
    "OwnAccountId",
    "OwnAccountRegister",
    "OwnAccountRegisterError",
    "OwnAccountRegisterValidationError",
    "OwnAccountRole",
    "OwnBankAccount",
    "OwnBankAccountDetails",
    "own_account_id_for",
]
