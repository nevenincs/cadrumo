"""Unit tests for OFX financial ingestion.

Covers FITID + payee preservation on the synthetic single-account
fixture and the multi-account dispatch path that drives every
``STMTTRNRS`` block in a real OFX file.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ......domain.transactions import TransactionDirection
from ......tests import FIXTURES_DIR
from .. import OfxProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = FIXTURES_DIR / "financial"


def test_ofx_provider_prefers_fitid_and_payee() -> None:
    """OfxProvider should preserve FITID and payee-derived description."""
    provider = OfxProvider()
    fixture = _FIXTURES / "synthetic-transactions.ofx"
    validation = provider.validate_source(fixture)
    assert validation.is_valid, validation.warnings
    parsed_rows = tuple(provider.ingest(fixture))
    assert len(parsed_rows) == 2
    assert parsed_rows[0].raw.transaction_id == "FIT-001"
    assert parsed_rows[0].raw.counterparty == "CLIENTE DOS"
    # The second source row is a debit: stored as a non-negative magnitude
    # with the sign lifted into the authoritative OUTGOING direction.
    assert parsed_rows[1].raw.amount >= 0
    assert parsed_rows[1].direction is TransactionDirection.OUTGOING


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
    assert validation.detected_dialect == "account_count=2"
    assert "ACC-1" not in validation.detected_dialect
    assert "ACC-2" not in validation.detected_dialect
    parsed_rows = tuple(provider.ingest(source))
    assert [parsed.raw.transaction_id for parsed in parsed_rows] == ["ONE", "TWO"]
    assert [parsed.raw.provenance.source_row_index for parsed in parsed_rows] == [1, 2]
    assert parsed_rows[1].raw.raw_fields["ACCTID"] == "ACC-2"


def test_ofx_provider_invalid_source_does_not_expose_filename(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = tmp_path / "12345678Z-private-account.ofx"
    source.write_text("not an OFX document", encoding="utf-8")

    with caplog.at_level(logging.DEBUG, logger="aeat.adapters.inbound.financial.providers._ofx"):
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
