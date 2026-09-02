"""Unit tests for OFX financial ingestion.

Covers FITID + payee preservation on the synthetic single-account
fixture and the multi-account dispatch path that drives every
``STMTTRNRS`` block in a real OFX file.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

import pytest

from ......core.optional_extras import OFX_EXTRA, optional_extra_available
from ......domain.transactions.enums import TransactionDirection
from ......tests import FIXTURES_DIR
from ..base import InvalidFinancialSourceError
from ..ofx import OfxProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = FIXTURES_DIR / "financial"


def test_ofx_provider_prefers_fitid_and_payee() -> None:
    """OfxProvider should preserve FITID, payee, magnitude, and direction.

    Every asserted value is read verbatim from the OFX source the parser
    must faithfully reproduce: the credit TRNAMT 875.55 lifts to a positive
    magnitude with INCOMING flow, and the debit TRNAMT -42.10 lifts to a
    non-negative magnitude with the sign carried into OUTGOING direction.
    """
    assert optional_extra_available(OFX_EXTRA)
    provider = OfxProvider()
    fixture = _FIXTURES / "synthetic-transactions.ofx"
    validation = provider.validate_source(fixture)
    assert validation.is_valid, validation.warnings
    parsed_rows = tuple(provider.ingest(fixture))
    assert len(parsed_rows) == 2

    credit = parsed_rows[0]
    assert credit.raw.provider_transaction_id == "FIT-001"
    assert credit.raw.counterparty == "CLIENTE DOS"
    assert credit.raw.currency == "EUR"
    assert credit.raw.amount == Decimal("875.55")
    assert credit.direction is TransactionDirection.INCOMING
    assert credit.raw.raw_fields["TRNTYPE"] == "CREDIT"
    assert credit.raw.raw_fields["FITID"] == "FIT-001"

    # The second source row is a debit: stored as a non-negative magnitude
    # with the sign lifted into the authoritative OUTGOING direction.
    debit = parsed_rows[1]
    assert debit.raw.provider_transaction_id == "FIT-002"
    assert debit.raw.amount == Decimal("42.10")
    assert debit.raw.amount >= 0
    assert debit.direction is TransactionDirection.OUTGOING


@pytest.mark.parametrize("amount_token", ["NaN", "Infinity"])
def test_ofx_provider_refuses_non_finite_transaction_amounts(
    amount_token: str,
    tmp_path: Path,
) -> None:
    """Validation and ingestion refuse the same non-finite real OFX amount."""
    fixture = _FIXTURES / "synthetic-transactions.ofx"
    fixture_text = fixture.read_text(encoding="utf-8")
    assert "<TRNAMT>875.55" in fixture_text
    source = tmp_path / f"non-finite-{amount_token}.ofx"
    source.write_text(
        fixture_text.replace("<TRNAMT>875.55", f"<TRNAMT>{amount_token}", 1),
        encoding="utf-8",
    )

    provider = OfxProvider()
    validation = provider.validate_source(source)

    assert not validation.is_valid
    assert validation.warnings == (
        f"OFX transaction 1 could not be parsed: unsupported amount value: {amount_token!r}",
    )
    with pytest.raises(
        InvalidFinancialSourceError,
        match=rf"OFX transaction 1 could not be parsed: unsupported amount value: '{amount_token}'",
    ):
        tuple(provider.ingest(source))


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
        <LEDGERBAL>
          <BALAMT>10.00
          <DTASOF>20260430235959
        </LEDGERBAL>
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
        <LEDGERBAL>
          <BALAMT>-5.00
          <DTASOF>20260430235959
        </LEDGERBAL>
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
    assert validation.detected_dialect == "account_count=2"
    assert "ACC-1" not in validation.detected_dialect
    assert "ACC-2" not in validation.detected_dialect
    parsed_rows = tuple(provider.ingest(source))
    assert [parsed.raw.provider_transaction_id for parsed in parsed_rows] == ["ONE", "TWO"]
    assert [parsed.raw.provenance.source_row_index for parsed in parsed_rows] == [1, 2]
    assert parsed_rows[1].raw.raw_fields["ACCTID"] == "ACC-2"


def test_ofx_provider_invalid_source_does_not_expose_filename(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = tmp_path / "12345678Z-private-account.ofx"
    source.write_text("not an OFX document", encoding="utf-8")

    with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.inbound.financial.providers.ofx"):
        validation = OfxProvider().validate_source(source)

    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    rendered_warnings = "\n".join(validation.warnings)
    assert not validation.is_valid
    assert source.name not in rendered_logs
    assert source.name not in rendered_warnings
    assert str(source) not in rendered_logs
    assert str(source) not in rendered_warnings
    assert "<input-ofx>" in rendered_logs
    assert "<input-ofx>" in rendered_warnings


def test_ofx_provider_refuses_spec_incomplete_statement(tmp_path: Path) -> None:
    """A header-valid but spec-incomplete OFX is refused at the parse boundary.

    ofxtools validates the full OFX grammar at conversion time. This statement
    omits the required BANKTRANLIST DTSTART/DTEND and the STMTRS LEDGERBAL, so
    the strict parser rejects it and the provider surfaces a non-valid
    ProviderValidation rather than silently yielding a partial statement.
    """
    source = tmp_path / "incomplete.ofx"
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
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <CURDEF>EUR
        <BANKACCTFROM>
          <BANKID>1234
          <ACCTID>ES1234567890
          <ACCTTYPE>CHECKING
        </BANKACCTFROM>
        <BANKTRANLIST>
          <STMTTRN>
            <TRNTYPE>CREDIT
            <DTPOSTED>20260410120000
            <TRNAMT>10.00
            <FITID>FIT-001
            <NAME>CLIENT ONE
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
""",
        encoding="cp1252",
    )
    validation = OfxProvider().validate_source(source)
    assert not validation.is_valid
    assert validation.warnings
