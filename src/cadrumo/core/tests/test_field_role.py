"""The column-role vocabulary is closed and its tokens are the stored form.

Two properties carry weight here. The set is CLOSED: role assignment is an
allow-list selection, so a set that admitted an arbitrary string would turn the
mapping step from a selection into free text — exactly the laundering the axis
exists to prevent. And ``UNMAPPED`` must be a real member rather than an absence,
because a column whose meaning was not established has to be representable; a
mapping that could only express recognised columns would force an unrecognised
one to be either guessed or dropped silently.

Tokens are pinned to literals rather than derived from member names: deriving
them would restate the implementation and pass whatever the class said.
"""

from __future__ import annotations

import pytest

from ..field_role import FieldRole

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_EXPECTED_TOKENS = {
    "UNMAPPED": "unmapped",
    "TRANSACTION_ID": "transaction_id",
    "COUNTERPARTY_NIF": "counterparty_nif",
    "COUNTERPARTY_NAME": "counterparty_name",
    "INVOICE_NUMBER": "invoice_number",
    "INVOICE_DATE": "invoice_date",
    # The bank-movement pair. Enumerated here rather than left to the set
    # difference to notice, because these two are exactly the members whose
    # ABSENCE from the vocabulary is the defect: a booked date read under
    # INVOICE_DATE, or a movement amount read under GRAND_TOTAL, is a
    # mislabelling that produces a well-formed row saying the wrong thing.
    "BOOKED_DATE": "booked_date",
    "MOVEMENT_AMOUNT": "movement_amount",
    "TAXABLE_BASE": "taxable_base",
    "IVA_RATE": "iva_rate",
    "IVA_AMOUNT": "iva_amount",
    "IVA_CATEGORY": "iva_category",
    "IRPF_CATEGORY": "irpf_category",
    "RETENCION_AMOUNT": "retencion_amount",
    "RECARGO_AMOUNT": "recargo_amount",
    "SUPLIDO_AMOUNT": "suplido_amount",
    "GRAND_TOTAL": "grand_total",
    "CURRENCY": "currency",
    "COUNTRY_CODE": "country_code",
    "NOTES": "notes",
    "CLASSIFICATION": "classification",
    "CATEGORY_ID": "category_id",
    "BUSINESS_PCT": "business_pct",
    "USAGE_RATIO_ID": "usage_ratio_id",
}


def test_the_member_set_is_exactly_the_declared_roles() -> None:
    """A silent addition or removal reddens here as a set difference."""
    assert {member.name for member in FieldRole} == set(_EXPECTED_TOKENS)


@pytest.mark.parametrize(("name", "token"), sorted(_EXPECTED_TOKENS.items()))
def test_each_member_carries_its_expected_token(name: str, token: str) -> None:
    """Member value equals the token a mapping records."""
    assert FieldRole[name].value == token


@pytest.mark.parametrize(("name", "token"), sorted(_EXPECTED_TOKENS.items()))
def test_each_token_hydrates_back_to_its_member(name: str, token: str) -> None:
    """The read direction: a recorded token resolves to the member that wrote it."""
    assert FieldRole(token) is FieldRole[name]


def test_an_unrecognised_role_token_is_refused() -> None:
    """The positive controls above mean nothing unless the set is truly closed.

    A permissive enum would satisfy every assertion above while admitting any
    header string a source table happened to carry.
    """
    with pytest.raises(ValueError, match="importe_retencion"):
        FieldRole("importe_retencion")


def test_an_unestablished_meaning_is_representable_rather_than_absent() -> None:
    """``UNMAPPED`` exists so an unrecognised column need not be guessed."""
    assert FieldRole.UNMAPPED in set(FieldRole)
    assert FieldRole.UNMAPPED != FieldRole.NOTES
