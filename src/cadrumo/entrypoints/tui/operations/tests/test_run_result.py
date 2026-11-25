"""A settled operation's result is paged into bounded pages of its own JSON."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from .....core.models import STRICT_FROZEN_CONFIG
from ..run_result import RESULT_PAGE_LINES, result_pages

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _Row(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    index: int
    label: str


class _Listing(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    title: str
    rows: tuple[_Row, ...]


def test_a_short_result_is_one_page_of_its_own_json() -> None:
    listing = _Listing(title="Año 2026", rows=(_Row(index=1, label="uno"),))

    pages = result_pages(listing)

    assert len(pages) == 1
    assert json.loads(pages[0]) == {"title": "Año 2026", "rows": [{"index": 1, "label": "uno"}]}
    assert "Año" in pages[0]


def test_a_long_result_is_cut_into_bounded_pages_that_rejoin_into_the_whole() -> None:
    listing = _Listing(title="long", rows=tuple(_Row(index=index, label=f"row {index}") for index in range(300)))

    pages = result_pages(listing)

    assert len(pages) > 1
    assert all(len(page.splitlines()) <= RESULT_PAGE_LINES for page in pages)
    assert all(len(page.splitlines()) == RESULT_PAGE_LINES for page in pages[:-1])
    assert json.loads("\n".join(pages)) == listing.model_dump(mode="json")
