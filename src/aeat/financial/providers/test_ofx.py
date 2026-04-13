"""Unit tests for OFX financial ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.financial import OfxProvider

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "financial"


@pytest.mark.unit
def test_ofx_provider_prefers_fitid_and_payee() -> None:
    """OfxProvider should preserve FITID and payee-derived description."""
    provider = OfxProvider()
    fixture = _FIXTURES / "synthetic-transactions.ofx"
    validation = provider.validate_source(fixture)
    assert validation.is_valid, validation.warnings
    transactions = tuple(provider.ingest(fixture))
    assert len(transactions) == 2
    assert transactions[0].transaction_id == "FIT-001"
    assert transactions[0].counterparty == "CLIENTE DOS"
    assert transactions[1].amount < 0


@pytest.mark.unit
def test_ofx_provider_ingests_every_account_statement(tmp_path: Path) -> None:
    """Multi-account OFX files should emit transactions from every statement block."""
    source = tmp_path / "multi-account.ofx"
    source.write_text(
        """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
  <SIGNONMSGSRSV1>
    <SONRS>
      <STATUS>
        <CODE>0
        <SEVERITY>INFO
      </STATUS>
      <DTSERVER>20260413090000
      <LANGUAGE>ENG
    </SONRS>
  </SIGNONMSGSRSV1>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <TRNUID>1
      <STATUS>
        <CODE>0
        <SEVERITY>INFO
      </STATUS>
      <STMTRS>
        <CURDEF>EUR
        <BANKACCTFROM>
          <BANKID>1234
          <ACCTID>ACC-1
          <ACCTTYPE>CHECKING
        </BANKACCTFROM>
        <BANKTRANLIST>
          <DTSTART>20260401000000
          <DTEND>20260430235959
          <STMTTRN>
            <TRNTYPE>CREDIT
            <DTPOSTED>20260405000000
            <TRNAMT>10.00
            <FITID>ONE
            <NAME>CLIENT ONE
            <MEMO>Invoice one
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
    <STMTTRNRS>
      <TRNUID>2
      <STATUS>
        <CODE>0
        <SEVERITY>INFO
      </STATUS>
      <STMTRS>
        <CURDEF>EUR
        <BANKACCTFROM>
          <BANKID>5678
          <ACCTID>ACC-2
          <ACCTTYPE>CHECKING
        </BANKACCTFROM>
        <BANKTRANLIST>
          <DTSTART>20260401000000
          <DTEND>20260430235959
          <STMTTRN>
            <TRNTYPE>DEBIT
            <DTPOSTED>20260406000000
            <TRNAMT>-5.00
            <FITID>TWO
            <NAME>VENDOR TWO
            <MEMO>Invoice two
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
""",
        encoding="cp1252",
    )
    provider = OfxProvider()
    validation = provider.validate_source(source)
    assert validation.is_valid, validation.warnings
    transactions = tuple(provider.ingest(source))
    assert [transaction.transaction_id for transaction in transactions] == ["ONE", "TWO"]
    assert [transaction.provenance.source_row_index for transaction in transactions] == [1, 2]
    assert transactions[1].raw_fields["ACCTID"] == "ACC-2"
