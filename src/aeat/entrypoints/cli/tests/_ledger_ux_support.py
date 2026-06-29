"""Shared real-CLI harness for ledger UX regression tests."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ._ledger_validation_support import open_bucket_session

_N26_HEADER = "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"

_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"

_FOUR_ROW_CSV = (
    _N26_HEADER
    + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
    + "2026-04-16,Proveedor SA,Compra material,-50.00,EUR,n26-002\n"
    + "2026-04-17,Cliente Dos,Factura dos,200.00,EUR,n26-003\n"
    + "2026-04-18,Cafe Oscar,Reunion negocios,-12.00,EUR,n26-004\n"
)

_FOUR_ROW_OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX><BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>\
<STMTRS><CURDEF>EUR<BANKACCTFROM><BANKID>0001<ACCTID>ES111<ACCTTYPE>CHECKING\
</BANKACCTFROM><BANKTRANLIST><DTSTART>20260401<DTEND>20260430\
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260415<TRNAMT>121.00<FITID>ofx-001\
<NAME>Client SL<MEMO>Invoice 1</STMTTRN>\
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260416<TRNAMT>-50.00<FITID>ofx-002\
<NAME>Proveedor SA<MEMO>Compra material</STMTTRN>\
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260417<TRNAMT>200.00<FITID>ofx-003\
<NAME>Cliente Dos<MEMO>Factura dos</STMTTRN>\
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260418<TRNAMT>-12.00<FITID>ofx-004\
<NAME>Cafe Oscar<MEMO>Reunion negocios</STMTTRN>\
</BANKTRANLIST><LEDGERBAL><BALAMT>259.00<DTASOF>20260430</LEDGERBAL>\
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def _invoke(args: Sequence[str], *, env: Mapping[str, str] | None = None) -> Result:
    return invoke_cached_cli(args, env=env)


@contextmanager
def _open_ledger_ux_session(tmp_path: Path) -> Iterator[None]:
    with open_bucket_session(tmp_path):
        yield


def _imported_transaction_id(tmp_path: Path) -> str:
    statement = tmp_path / "statement.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    imported = _invoke(["app", "ledger", "import", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    rows = payload.get("result", payload).get("rows", [])
    assert rows, listed.output
    return rows[0]["transaction_id"]
