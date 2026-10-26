"""Ledger import binds statement rows to the taxpayer's own bank accounts.

Every case parses a real OFX statement through the registered provider
dispatch and the application import planner; only synthetic accounts are used.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from .....application.ledger.actions_import import (
    LedgerProviderID,
    evaluate_import_rows,
    prepare_ledger_source_import,
)
from .....application.ledger.models import LedgerSourceImportCommand
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.transactions.errors import TransactionValidationError
from .....domain.transactions.models import TransactionCatalogue, derive_transaction_id
from .....domain.transactions.own_accounts import OwnAccountHolding, OwnAccountRegister, OwnBankAccountDetails
from ..ledger_import import build_ledger_import_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]

_IBAN_ONE = "ES9121000418450200051332"
_IBAN_TWO = "ES7921000813610123456789"

_OFX_TEMPLATE = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS>\
<DTSERVER>20260430120000<LANGUAGE>ENG</SONRS></SIGNONMSGSRSV1>\
<BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>\
<STMTRS><CURDEF>EUR<BANKACCTFROM><BANKID>0001<ACCTID>{acctid}<ACCTTYPE>CHECKING\
</BANKACCTFROM><BANKTRANLIST><DTSTART>20260401<DTEND>20260430\
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260415<TRNAMT>121.00<FITID>ofx-001\
<NAME>Client SL<MEMO>Invoice 1</STMTTRN>\
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260416<TRNAMT>-50.00<FITID>ofx-002\
<NAME>Proveedor SA<MEMO>Compra material</STMTTRN>\
</BANKTRANLIST><LEDGERBAL><BALAMT>71.00<DTASOF>20260430</LEDGERBAL>\
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


_CSV_STATEMENT = (
    "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
    "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
    "2026-04-16,Proveedor SA,Compra material,-50.00,EUR,n26-002\n"
)


@pytest.fixture(autouse=True)
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Plan every ledger row inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _statement(tmp_path: Path, name: str, acctid: str) -> Path:
    path = tmp_path / name
    path.write_text(_OFX_TEMPLATE.format(acctid=acctid), encoding="ascii")
    return path


def _csv_statement(tmp_path: Path) -> Path:
    """A statement format that carries no account identifier."""
    path = tmp_path / "statement.csv"
    path.write_text(_CSV_STATEMENT, encoding="utf-8")
    return path


def _register(*ibans: str) -> OwnAccountRegister:
    register = OwnAccountRegister()
    for index, iban in enumerate(ibans, start=1):
        register = register.with_new_account(
            OwnBankAccountDetails(label=f"Account {index}", holding=OwnAccountHolding.TITULAR, iban=iban),
        )
    return register


def _bound_ids(path: Path, register: OwnAccountRegister, own_account_id: str | None = None) -> list[str | None]:
    provider = LedgerProviderID.CSV if path.suffix == ".csv" else LedgerProviderID.OFX
    prepared = prepare_ledger_source_import(
        LedgerSourceImportCommand(path=path, provider=provider.value, own_account_id=own_account_id),
        ports=build_ledger_import_ports(),
        own_accounts=register,
    )
    return [row.own_account_id for row in prepared.source.parsed_rows]


def test_a_chosen_account_binds_rows_whose_statement_names_it(tmp_path: Path) -> None:
    """The statement's ACCTID, as IBAN or as domestic account number, matches the chosen account."""
    register = _register(_IBAN_ONE, _IBAN_TWO)

    assert _bound_ids(_statement(tmp_path, "iban.ofx", _IBAN_ONE), register, "acc-01") == ["acc-01", "acc-01"]
    assert _bound_ids(_statement(tmp_path, "ccc.ofx", _IBAN_TWO[4:]), register, "acc-02") == ["acc-02", "acc-02"]


def test_a_statement_naming_another_account_refuses_the_chosen_one(tmp_path: Path) -> None:
    """A chosen account the statement contradicts is refused, not silently applied."""
    with pytest.raises(TransactionValidationError) as refusal:
        _bound_ids(_statement(tmp_path, "other.ofx", _IBAN_TWO), _register(_IBAN_ONE, _IBAN_TWO), "acc-01")

    assert refusal.value.translated_message == "errors.transaction.ledger_import_own_account_mismatch"


def test_an_unregistered_chosen_account_is_refused(tmp_path: Path) -> None:
    """Only a registered own account can receive rows."""
    with pytest.raises(TransactionValidationError) as refusal:
        _bound_ids(_statement(tmp_path, "one.ofx", _IBAN_ONE), _register(_IBAN_ONE), "acc-07")

    assert refusal.value.translated_message == "errors.transaction.own_account_unknown"


def test_without_a_choice_only_a_unique_registered_match_binds(tmp_path: Path) -> None:
    """A named registered account binds on its own; an unknown or absent identifier stays unassigned."""
    register = _register(_IBAN_ONE, _IBAN_TWO)

    assert _bound_ids(_statement(tmp_path, "two.ofx", _IBAN_TWO), register) == ["acc-02", "acc-02"]
    assert _bound_ids(_statement(tmp_path, "unknown.ofx", "ES7620770024003102575766"), register) == [None, None]
    assert _bound_ids(_csv_statement(tmp_path), register) == [None, None]
    assert _bound_ids(_statement(tmp_path, "empty-register.ofx", _IBAN_ONE), OwnAccountRegister()) == [None, None]


def test_a_statement_without_an_identifier_takes_the_chosen_account(tmp_path: Path) -> None:
    """A missing ACCTID is not a contradiction of the operator's choice."""
    assert _bound_ids(_csv_statement(tmp_path), _register(_IBAN_ONE), "acc-01") == [
        "acc-01",
        "acc-01",
    ]


def test_identical_movements_on_two_own_accounts_both_import(tmp_path: Path) -> None:
    """The second account's statement is not skipped as a re-import of the first."""
    register = _register(_IBAN_ONE, _IBAN_TWO)
    ports = build_ledger_import_ports()

    def plan(path: Path, catalogue: TransactionCatalogue):
        prepared = prepare_ledger_source_import(
            LedgerSourceImportCommand(path=path, provider=LedgerProviderID.OFX.value),
            ports=ports,
            own_accounts=register,
        )
        return evaluate_import_rows(bucket_id="preview", catalogue=catalogue, parsed_rows=prepared.source.parsed_rows)

    first = plan(_statement(tmp_path, "one.ofx", _IBAN_ONE), TransactionCatalogue())
    second = plan(
        _statement(tmp_path, "two.ofx", _IBAN_TWO),
        TransactionCatalogue.model_validate({"transactions": {tx.transaction_id: tx for tx in first.imported}}),
    )
    unbound_again = plan(
        _statement(tmp_path, "one-again.ofx", _IBAN_ONE),
        TransactionCatalogue.model_validate({"transactions": {tx.transaction_id: tx for tx in first.imported}}),
    )

    assert [tx.own_account_id for tx in first.imported] == ["acc-01", "acc-01"]
    assert [tx.own_account_id for tx in second.imported] == ["acc-02", "acc-02"]
    assert second.skipped_refs == ()
    assert len(unbound_again.skipped_refs) == 2
    assert {tx.transaction_id for tx in first.imported}.isdisjoint({tx.transaction_id for tx in second.imported})
    assert all(tx.transaction_id == derive_transaction_id(tx.raw, own_account_id="acc-01") for tx in first.imported)
