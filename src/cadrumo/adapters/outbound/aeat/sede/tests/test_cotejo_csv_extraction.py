"""The expediente parser reads the cotejo CSV by query, not by byte sequence.

AEAT is free to add a parameter to the cotejo link or emit its parameters in
another order without changing which document it serves. A parser that matches
the literal ``?CSV=`` sequence refuses those links, so a filed declaration
becomes unreachable for a reason that is not about the declaration at all.
The canonical extractor parses the query instead; these fixtures pin that.
"""

from __future__ import annotations

import pytest

from ......core.config import Settings
from .._parse import parse_expediente_detail
from ..errors import SedeParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_COTEJO_PATH = Settings.external_constants().aeat.sede_paths.cotejo_query
_CSV = "FIXTURECSV1234X7"
_BASE_URL = Settings.external_constants().aeat.domains.sede
_EXPEDIENTE_ID = "202600000001E"


def _detail_html(query: str) -> str:
    return f'<html><body><a href="{_COTEJO_PATH}?{query}">Cotejo</a></body></html>'


@pytest.mark.parametrize(
    "query",
    [
        f"CSV={_CSV}",
        f"foo=1&CSV={_CSV}",
        f"CSV={_CSV}&foo=1",
        f"foo=1&amp;CSV={_CSV}",
        f"a=1&CSV={_CSV}&b=2",
    ],
)
def test_csv_is_extracted_regardless_of_query_order_or_extras(query: str) -> None:
    ref = parse_expediente_detail(_detail_html(query), expediente_id=_EXPEDIENTE_ID, base_url=_BASE_URL)

    assert ref.csv == _CSV


def test_missing_csv_parameter_is_refused() -> None:
    with pytest.raises(SedeParseError):
        parse_expediente_detail(_detail_html("foo=1"), expediente_id=_EXPEDIENTE_ID, base_url=_BASE_URL)


def test_malformed_csv_value_is_refused() -> None:
    with pytest.raises(SedeParseError):
        parse_expediente_detail(_detail_html("CSV=short"), expediente_id=_EXPEDIENTE_ID, base_url=_BASE_URL)


def test_absent_cotejo_link_is_refused() -> None:
    with pytest.raises(SedeParseError):
        parse_expediente_detail("<html><body>no link</body></html>", expediente_id=_EXPEDIENTE_ID, base_url=_BASE_URL)
