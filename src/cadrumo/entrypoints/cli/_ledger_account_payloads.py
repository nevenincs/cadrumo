"""Typed ``--json`` payload schemas for the ``app ledger account`` commands.

Every payload shows an own account only through its mask (country code and last
four characters) and its opaque ``own_account_id``. No account number, BIC or
foreign-bank block appears in any output, so a command transcript or captured
JSON envelope never carries account material.
"""

from __future__ import annotations

from datetime import date

from ...application.ledger.own_account_operation import OwnAccountDesignationProjection, OwnAccountProjection
from ...core.json_contract import OutputSchema
from ...core.text_bounds import NonEmptyStr


class OwnAccountPayload(OutputSchema):
    """Masked view of one own account."""

    own_account_id: NonEmptyStr
    label: NonEmptyStr
    holding: NonEmptyStr
    masked_iban: NonEmptyStr
    country_code: NonEmptyStr
    sepa_marca: NonEmptyStr
    has_swift_bic: bool
    has_bank_block: bool
    currency: NonEmptyStr
    opened_on: date | None = None
    closed_on: date | None = None

    @classmethod
    def from_projection(cls, account: OwnAccountProjection) -> OwnAccountPayload:
        """Copy the worker's masked projection onto the wire shape."""
        return cls(
            own_account_id=account.own_account_id,
            label=account.label,
            holding=account.holding.value,
            masked_iban=account.masked_iban,
            country_code=account.country_code,
            sepa_marca=account.sepa_marca,
            has_swift_bic=account.has_swift_bic,
            has_bank_block=account.has_bank_block,
            currency=account.currency,
            opened_on=account.opened_on,
            closed_on=account.closed_on,
        )


class OwnAccountDesignationPayload(OutputSchema):
    """One role designation; ``modelo`` ``None`` designates for every modelo."""

    role: NonEmptyStr
    modelo: str | None = None
    own_account_id: NonEmptyStr

    @classmethod
    def from_projection(cls, designation: OwnAccountDesignationProjection) -> OwnAccountDesignationPayload:
        """Copy one designation onto the wire shape."""
        return cls(
            role=designation.role.value,
            modelo=designation.modelo,
            own_account_id=designation.own_account_id,
        )


class OwnAccountListResult(OutputSchema):
    """Every own account and every role designation."""

    accounts: tuple[OwnAccountPayload, ...]
    designations: tuple[OwnAccountDesignationPayload, ...]


class OwnAccountShowResult(OutputSchema):
    """One own account and the designations that name it."""

    account: OwnAccountPayload
    designations: tuple[OwnAccountDesignationPayload, ...]


class OwnAccountChangeResult(OutputSchema):
    """The outcome of one register change.

    ``changed`` is ``False`` for a change that left the register as it was, such
    as an update repeating the stored values.
    """

    own_account_id: str | None = None
    changed: bool
    accounts: tuple[OwnAccountPayload, ...]
    designations: tuple[OwnAccountDesignationPayload, ...]


__all__ = [
    "OwnAccountChangeResult",
    "OwnAccountDesignationPayload",
    "OwnAccountListResult",
    "OwnAccountPayload",
    "OwnAccountShowResult",
]
