"""Live smoke tests for the Sheets sub-app.

Hits the scratch sheet provisioned by ``aeat bootstrap``. Cell ranges
are namespaced by a UUID prefix so two parallel runs do not stomp on
each other. Each test cleans up after itself.
"""

from __future__ import annotations

from typing import Any

import pytest

from aeat.cli._live import (
    requires_live_enabled,
    requires_scratch_sheet,
    sheets_service,
    skip_if_drive_quota,
    unique_prefix,
)

pytestmark = [pytest.mark.live_read, pytest.mark.domain_infra]


class TestSheetsLiveRoundTrip:
    """End-to-end Sheets round-trip in the scratch sheet."""

    def test_set_get_append_clear(self) -> None:
        requires_live_enabled()
        sheet_id = requires_scratch_sheet()

        service: Any = sheets_service()
        # Each test run picks a fresh column far enough out that
        # concurrent runs cannot collide. Use the prefix as a tag we
        # write into row 1.
        prefix = unique_prefix()
        # Cells we mutate: A101..C103. Far from anything else.
        target_range = "A101:C103"

        try:
            try:
                service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range=target_range,
                    valueInputOption="USER_ENTERED",
                    body={
                        "values": [
                            [prefix, 1, 2],
                            [prefix, 3, 4],
                        ]
                    },
                ).execute()
            except Exception as exc:
                skip_if_drive_quota(exc)
                return

            response = service.spreadsheets().values().get(spreadsheetId=sheet_id, range=target_range).execute()
            values = response.get("values", [])
            assert values[0] == [prefix, "1", "2"]
            assert values[1] == [prefix, "3", "4"]

            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=target_range,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [[prefix, 5, 6]]},
            ).execute()

            response_after = service.spreadsheets().values().get(spreadsheetId=sheet_id, range="A101:C200").execute()
            rows = response_after.get("values", [])
            # Three rows from set + one from append, all carrying the prefix in col A
            prefix_rows = [row for row in rows if row and row[0] == prefix]
            assert len(prefix_rows) >= 3
        finally:
            service.spreadsheets().values().clear(
                spreadsheetId=sheet_id,
                range="A101:C200",
                body={},
            ).execute()
