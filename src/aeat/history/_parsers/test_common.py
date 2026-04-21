"""Unit tests for the shared detail-page parser helpers.

Covers the header-aware column resolution added in response to
Gemini review feedback on PR #195 — the parser must survive AEAT
reordering the ``Casilla``/``Valor`` columns between campaigns.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup, Tag

from .._errors import HistoryParseError
from ._common import extract_casillas

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_CANONICAL_ORDER = """
<table class="casillas">
  <thead>
    <tr><th>Casilla</th><th>Valor</th><th>Descripcion</th></tr>
  </thead>
  <tbody>
    <tr><td>01</td><td>1.234,56</td><td>Ingresos</td></tr>
    <tr><td>02</td><td>0,00</td><td>Gastos</td></tr>
  </tbody>
</table>
"""

_REORDERED_COLUMNS = """
<table class="casillas">
  <thead>
    <tr><th>Descripcion</th><th>Valor</th><th>Casilla</th></tr>
  </thead>
  <tbody>
    <tr><td>Ingresos</td><td>1.234,56</td><td>01</td></tr>
    <tr><td>Gastos</td><td>0,00</td><td>02</td></tr>
  </tbody>
</table>
"""

_HEADERLESS = """
<table class="casillas">
  <tbody>
    <tr><td>01</td><td>1.234,56</td></tr>
    <tr><td>02</td><td>0,00</td></tr>
  </tbody>
</table>
"""

_MISSING_COLUMN = """
<table class="casillas">
  <thead>
    <tr><th>Codigo</th><th>Importe</th></tr>
  </thead>
  <tbody>
    <tr><td>01</td><td>1.234,56</td></tr>
  </tbody>
</table>
"""


def _table(html: str) -> Tag:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    assert isinstance(table, Tag)
    return table


def test_extract_casillas_canonical_order() -> None:
    casillas, warnings = extract_casillas(_table(_CANONICAL_ORDER))
    assert casillas == {"01": "1.234,56", "02": "0,00"}
    assert warnings == ()


def test_extract_casillas_reordered_columns() -> None:
    casillas, warnings = extract_casillas(_table(_REORDERED_COLUMNS))
    # Header-aware resolution picks the right cells even though AEAT
    # moved Casilla to column 2.
    assert casillas == {"01": "1.234,56", "02": "0,00"}
    assert warnings == ()


def test_extract_casillas_headerless_fallback() -> None:
    casillas, warnings = extract_casillas(_table(_HEADERLESS))
    assert casillas == {"01": "1.234,56", "02": "0,00"}
    assert warnings == ()


def test_extract_casillas_missing_required_column() -> None:
    with pytest.raises(HistoryParseError):
        extract_casillas(_table(_MISSING_COLUMN))
