"""Runtime contract for the declaration parser's word record alias."""

from __future__ import annotations

from typing import Any

import pytest

from .. import parser as _parser

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_pdfword_alias_is_dict_str_any() -> None:
    """The parser-internal word record remains ``dict[str, Any]``."""
    assert _parser._PdfWord == dict[str, Any]
