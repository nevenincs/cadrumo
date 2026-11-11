"""Own bank account register invariants: identity, account validation and designations.

Each refusal is checked through the registered cause the validator raises, so a
validator that started refusing for another reason fails here. All account
numbers are synthetic published examples.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pydantic
import pytest

from ....core.modelo import Modelo
from ...iva.sepa_marca import SepaMarca
from ..own_accounts import (
    OwnAccountDesignation,
    OwnAccountHolding,
    OwnAccountRegister,
    OwnAccountRegisterError,
    OwnAccountRegisterValidationError,
    OwnAccountRole,
    OwnBankAccount,
    OwnBankAccountDetails,
    own_account_id_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ES_IBAN = "ES9121000418450200051332"
_ES_IBAN_2 = "ES7921000813610123456789"
_DE_IBAN = "DE89370400440532013000"
_TR_IBAN = "TR330006100519786457841326"


def _details(iban: object = _ES_IBAN, **overrides: object) -> OwnBankAccountDetails:
    fields: dict[str, object] = {
        "label": "synthetic current account",
        "holding": OwnAccountHolding.TITULAR,
        "iban": iban,
    }
    fields.update(overrides)
    return OwnBankAccountDetails.model_validate(fields)


def _validation_cause(build: Callable[[], object]) -> OwnAccountRegisterValidationError:
    """Return the registered refusal, raised directly or wrapped by Pydantic's validator protocol."""
    with pytest.raises((pydantic.ValidationError, OwnAccountRegisterValidationError)) as caught:
        build()
    refusal = caught.value
    if isinstance(refusal, pydantic.ValidationError):
        refusal = refusal.errors()[0]["ctx"]["error"].__cause__
    assert isinstance(refusal, OwnAccountRegisterValidationError)
    return refusal


def _register(*ibans: str) -> OwnAccountRegister:
    register = OwnAccountRegister()
    for iban in ibans:
        register = register.with_new_account(_details(iban))
    return register


def test_a_printed_iban_is_stored_canonical() -> None:
    account = _details("es91 2100-0418 4502 0005 1332")

    assert account.iban == _ES_IBAN
    assert account.country_code == "ES"
    assert account.sepa_marca is SepaMarca.ESPANA
    assert account.currency == "EUR"


@pytest.mark.parametrize(
    ("iban", "reason"),
    [
        ("ES9121000418450200051333", "mod-97"),
        ("ES91", "ISO 13616"),
        ("", "ISO 13616"),
    ],
)
def test_an_invalid_iban_is_refused_without_echoing_it(iban: str, reason: str) -> None:
    with pytest.raises(pydantic.ValidationError) as caught:
        _details(iban)

    assert reason in str(caught.value)
    if iban:
        assert iban not in str(caught.value)
        assert iban[-4:] not in str(caught.value)


def test_an_account_number_is_required_as_an_iban() -> None:
    cause = _validation_cause(lambda: _details(iban=12345))

    assert "must be a string" in str(cause)


def test_a_sepa_account_needs_no_bank_block_or_bic() -> None:
    account = _details(_DE_IBAN)

    assert account.sepa_marca is SepaMarca.UE_SEPA
    assert account.swift_bic == ""


def test_an_account_outside_sepa_needs_bic_and_the_full_bank_block() -> None:
    cause = _validation_cause(lambda: _details(_TR_IBAN))
    assert "outside the SEPA zone" in str(cause)

    complete = _details(
        _TR_IBAN,
        swift_bic="tcza tr is",
        bank_name="Synthetic Bank",
        bank_address="1 Example Street",
        bank_city="Ankara",
        bank_country_code="tr",
    )
    assert complete.sepa_marca is SepaMarca.RESTO_PAISES
    assert complete.swift_bic == "TCZATRIS"
    assert complete.bank_country_code == "TR"


def test_a_partial_bank_block_is_refused() -> None:
    cause = _validation_cause(lambda: _details(_DE_IBAN, bank_name="Synthetic Bank"))

    assert "name, address, city and country together" in str(cause)


def test_the_bank_country_must_be_the_iban_country() -> None:
    cause = _validation_cause(
        lambda: _details(
            _DE_IBAN,
            bank_name="Synthetic Bank",
            bank_address="1 Example Street",
            bank_city="Paris",
            bank_country_code="FR",
        ),
    )

    assert "IBAN country" in str(cause)


@pytest.mark.parametrize("bic", ["ABCD", "ABCDES2", "ABCDES2X1", "1BCDES2X"])
def test_a_malformed_bic_is_refused(bic: str) -> None:
    cause = _validation_cause(lambda: _details(swift_bic=bic))

    assert "ISO 9362" in str(cause)


def test_an_account_cannot_close_before_it_opened() -> None:
    cause = _validation_cause(lambda: _details(opened_on=date(2026, 3, 1), closed_on=date(2026, 2, 1)))

    assert "close before it opened" in str(cause)


def test_a_bad_currency_is_refused_and_a_padded_one_folds() -> None:
    assert _details(currency=" usd ").currency == "USD"

    cause = _validation_cause(lambda: _details(currency="EURO"))
    assert "ISO 4217" in str(cause)


def test_the_mask_shows_only_country_and_last_four() -> None:
    account = _details()

    assert account.masked_iban == "ES ···· 1332"
    assert "2100" not in account.masked_iban


def test_open_on_respects_both_bounds() -> None:
    account = _details(opened_on=date(2026, 1, 10), closed_on=date(2026, 6, 30))

    assert not account.open_on(date(2026, 1, 9))
    assert account.open_on(date(2026, 1, 10))
    assert account.open_on(date(2026, 6, 30))
    assert not account.open_on(date(2026, 7, 1))


def test_accounts_receive_ordinal_ids_that_are_never_reused() -> None:
    register = _register(_ES_IBAN, _DE_IBAN)
    assert [account.own_account_id for account in register.accounts] == ["acc-01", "acc-02"]

    register = register.without_account("acc-02").with_new_account(_details(_ES_IBAN_2))

    assert [account.own_account_id for account in register.accounts] == ["acc-01", "acc-03"]
    assert register.last_ordinal == 3


def test_ordinal_ids_widen_past_two_digits() -> None:
    assert own_account_id_for(1) == "acc-01"
    assert own_account_id_for(100) == "acc-100"
    with pytest.raises(OwnAccountRegisterValidationError):
        own_account_id_for(0)


def test_the_same_account_number_twice_is_refused() -> None:
    register = _register(_ES_IBAN)

    cause = _validation_cause(lambda: register.with_new_account(_details(_ES_IBAN, label="duplicate")))

    assert "same account number twice" in str(cause)


def test_a_stored_id_beyond_the_last_ordinal_is_refused() -> None:
    account = OwnBankAccount.model_validate({**_details().model_dump(), "own_account_id": "acc-05"})

    cause = _validation_cause(lambda: OwnAccountRegister(last_ordinal=1, accounts=(account,)))

    assert "beyond its last ordinal" in str(cause)


def test_update_replaces_details_and_keeps_the_identity() -> None:
    register = _register(_ES_IBAN)

    updated = register.with_updated_account("acc-01", _details(_ES_IBAN_2, label="renamed"))

    assert updated.account("acc-01").iban == _ES_IBAN_2
    assert updated.account("acc-01").label == "renamed"
    assert updated.last_ordinal == 1


def test_close_records_the_date_once() -> None:
    register = _register(_ES_IBAN).with_closed_account("acc-01", date(2026, 9, 30))

    assert register.account("acc-01").closed_on == date(2026, 9, 30)
    cause = _validation_cause(lambda: register.with_closed_account("acc-01", date(2026, 10, 1)))
    assert "already closed" in str(cause)


def test_an_unknown_account_is_refused() -> None:
    with pytest.raises(OwnAccountRegisterError, match="acc-07"):
        _register(_ES_IBAN).account("acc-07")


def test_a_designation_cannot_name_a_missing_account() -> None:
    designation = OwnAccountDesignation(role=OwnAccountRole.CHARGE, own_account_id="acc-02")

    cause = _validation_cause(lambda: _register(_ES_IBAN).with_designation(designation))

    assert "unregistered accounts" in str(cause)


def test_a_modelo_scoped_designation_wins_over_the_all_scope() -> None:
    register = (
        _register(_ES_IBAN, _ES_IBAN_2)
        .with_designation(OwnAccountDesignation(role=OwnAccountRole.CHARGE, own_account_id="acc-01"))
        .with_designation(
            OwnAccountDesignation(role=OwnAccountRole.CHARGE, modelo=Modelo("303"), own_account_id="acc-02"),
        )
    )

    designated_303 = register.designated(OwnAccountRole.CHARGE, Modelo("303"))
    designated_111 = register.designated(OwnAccountRole.CHARGE, Modelo("111"))
    assert designated_303 is not None
    assert designated_303.own_account_id == "acc-02"
    assert designated_111 is not None
    assert designated_111.own_account_id == "acc-01"


def test_charge_and_refund_roles_never_resolve_through_each_other() -> None:
    register = _register(_ES_IBAN).with_designation(
        OwnAccountDesignation(role=OwnAccountRole.REFUND, own_account_id="acc-01"),
    )

    assert register.designated(OwnAccountRole.CHARGE, Modelo("303")) is None
    refund = register.designated(OwnAccountRole.REFUND, Modelo("303"))
    assert refund is not None
    assert refund.own_account_id == "acc-01"


def test_redesignating_replaces_the_earlier_designation() -> None:
    register = (
        _register(_ES_IBAN, _ES_IBAN_2)
        .with_designation(OwnAccountDesignation(role=OwnAccountRole.REFUND, own_account_id="acc-01"))
        .with_designation(OwnAccountDesignation(role=OwnAccountRole.REFUND, own_account_id="acc-02"))
    )

    assert len(register.designations) == 1
    assert register.designations[0].own_account_id == "acc-02"


def test_a_duplicate_designation_key_in_a_stored_document_is_refused() -> None:
    register = _register(_ES_IBAN, _ES_IBAN_2)
    first = OwnAccountDesignation(role=OwnAccountRole.REFUND, own_account_id="acc-01")
    second = OwnAccountDesignation(role=OwnAccountRole.REFUND, own_account_id="acc-02")

    cause = _validation_cause(
        lambda: OwnAccountRegister(last_ordinal=2, accounts=register.accounts, designations=(first, second)),
    )

    assert "two designations for one role and scope" in str(cause)


def test_a_designated_account_cannot_be_removed() -> None:
    register = _register(_ES_IBAN).with_designation(
        OwnAccountDesignation(role=OwnAccountRole.CHARGE, own_account_id="acc-01"),
    )

    cause = _validation_cause(lambda: register.without_account("acc-01"))
    assert "redesignate before removing" in str(cause)

    cleared = register.without_designation(OwnAccountRole.CHARGE, None).without_account("acc-01")
    assert cleared.accounts == ()


def test_removing_an_absent_designation_is_refused() -> None:
    with pytest.raises(OwnAccountRegisterError, match="no designation"):
        _register(_ES_IBAN).without_designation(OwnAccountRole.REFUND, Modelo("303"))
