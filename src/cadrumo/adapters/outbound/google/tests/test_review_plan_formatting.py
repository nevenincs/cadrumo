"""The native Sheets renderer consumes the same review display facets as XLSX."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from .....application.storage.calc_sheets.review_workbook import build_review_workbook
from .....application.storage.calc_sheets.tests.review_fixture import review_label, review_snapshot
from .._calc_sheets_apply_formatting import build_number_format_requests

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_native_review_date_and_decimal_formats_match_plan() -> None:
    plan = build_review_workbook(
        review_snapshot(),
        publication_id=UUID(int=2),
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=review_label,
    )
    requests = build_number_format_requests(
        plan, sheet_id_by_tab={tab.value: index for index, tab in enumerate(plan.tabs)}
    )
    formats = {
        request["repeatCell"]["range"]["startColumnIndex"]: request["repeatCell"]["cell"]["userEnteredFormat"][
            "numberFormat"
        ]
        for request in requests
        if request["repeatCell"]["range"]["sheetId"] == 2
    }
    assert formats[1] == {"type": "DATE", "pattern": "yyyy-mm-dd"}
    assert formats[4] == {"type": "NUMBER", "pattern": '#,##0.00" €"'}
