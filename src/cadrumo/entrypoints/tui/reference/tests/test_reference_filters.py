"""The reference form reads a date coordinate with the same grammar as every other reference surface."""

from __future__ import annotations

import pytest

from .....core.time.clock import today_madrid
from ..filters import ReferenceFilterError, query_from_form
from ..reads import ReferenceRead

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_an_extended_date_is_the_as_of_coordinate() -> None:
    day = today_madrid()

    query = query_from_form(ReferenceRead.DESCRIBE, {"modelo": "303", "as_of": day.isoformat()})

    assert query.as_of == day


@pytest.mark.parametrize("written", [today_madrid().strftime("%Y%m%d"), today_madrid().strftime("%G-W%V-%u")])
def test_a_compact_or_week_date_is_refused_as_the_mcp_query_refuses_it(written: str) -> None:
    with pytest.raises(ReferenceFilterError) as refused:
        query_from_form(ReferenceRead.DESCRIBE, {"modelo": "303", "as_of": written})

    assert refused.value.fields == ("as_of",)
