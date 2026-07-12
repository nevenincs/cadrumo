"""Test the ECB snapshot refresh utility (write/validate path, no network)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .._ecb_provider import EcbReferenceRateProvider
from .._ecb_refresh import refresh_bundled_ecb_rates

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SAMPLE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"'
    ' xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">\n'
    "  <Cube>\n"
    '    <Cube time="2026-02-02"><Cube currency="USD" rate="1.1000"/></Cube>\n'
    "  </Cube>\n"
    "</gesmes:Envelope>\n"
)


def test_refresh_writes_and_validates_snapshot(tmp_path: Path) -> None:
    dest = tmp_path / "eurofxref-bundled.xml"
    count = refresh_bundled_ecb_rates(source_xml=_SAMPLE, dest=dest)
    assert count == 1
    provider = EcbReferenceRateProvider(rates_path=dest)
    assert provider.get_eur_rate("USD", date(2026, 2, 2)) == Decimal("1") / Decimal("1.1000")


def test_refresh_rejects_empty_document(tmp_path: Path) -> None:
    dest = tmp_path / "eurofxref-bundled.xml"
    dest.write_text("<keep/>", encoding="utf-8")
    empty = (
        '<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"'
        ' xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref"><Cube/></gesmes:Envelope>'
    )
    with pytest.raises(ValueError, match="no dated rate sets"):
        refresh_bundled_ecb_rates(source_xml=empty, dest=dest)
    # The existing bundle must be untouched on a bad refresh.
    assert dest.read_text(encoding="utf-8") == "<keep/>"


def test_refresh_refuses_non_https_url() -> None:
    with pytest.raises(ValueError, match="non-https"):
        refresh_bundled_ecb_rates(url="http://example.com/x.xml")
