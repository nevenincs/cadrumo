"""A bank export whose headers name no column of the statement vocabulary.

Only the column-role mapping lane can read such an export, so the lane's tests
need one. It is the neobank fixture with its date, description and amount
headers renamed to words the vocabulary does not hold; every data byte is kept,
so the movements a mapping imports are the fixture's own.
"""

from __future__ import annotations

from pathlib import Path

from ......tests.inventory import FIXTURES_DIR

__all__ = ["write_unknown_header_export"]

_NEOBANK_EXPORT = FIXTURES_DIR / "financial" / "tabular-dialects" / "bank_neobank_2026Q1.csv"

#: The neobank header with ``booking_date``, ``value_date``, ``reference`` and
#: ``amount_eur`` renamed; the other columns keep their names.
_UNKNOWN_HEADER = "posted,settled,partner_name,memo,type,sum_eur,currency,exchange_rate"


def write_unknown_header_export(directory: Path) -> Path:
    """Write the renamed export into ``directory`` and return its path."""
    header, *data = _NEOBANK_EXPORT.read_bytes().decode("utf-8").splitlines(keepends=True)
    ending = header[len(header.rstrip("\r\n")) :]
    path = directory / "unknown-header-export.csv"
    path.write_bytes((_UNKNOWN_HEADER + ending + "".join(data)).encode("utf-8"))
    return path
