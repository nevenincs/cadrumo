"""Which Sheets channel carries literal text, numbers and generated formulas, and which retry class each request has."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import pytest

from .....application.storage.calc_sheets.engine import build_export_plan
from .....application.storage.calc_sheets.review_workbook import build_review_workbook
from .....application.storage.calc_sheets.tests.review_fixture import review_label, review_snapshot
from .....domain.calculations.registry.tests.published_authority import published_snapshot
from ..api import RequestRetryPolicy
from ..calc_sheets_apply import _apply_plan_structural_requests, _write_plan_values

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import SheetsResource

    from ..api import GoogleRequestExecutor

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FORMULA_TEXT = '=IMPORTXML("https://example.invalid", "x")'


class _Request:
    def __init__(self, kind: str, body: dict[str, Any]) -> None:
        self.kind = kind
        self.body = body


class _Values:
    def batchUpdate(self, *, body: dict[str, Any], **_selector: str) -> _Request:  # noqa: N802 - Google API name
        return _Request("values", body)


class _Sheets:
    def spreadsheets(self) -> _Sheets:
        return self

    def values(self) -> _Values:
        return _Values()

    def batchUpdate(self, *, body: dict[str, Any], **_selector: str) -> _Request:  # noqa: N802 - Google API name
        return _Request("structure", body)


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[_Request, str, RequestRetryPolicy]] = []

    def __call__(self, request: _Request, *, action: str, retry: RequestRetryPolicy) -> dict[str, Any]:
        self.calls.append((request, action, retry))
        return {}


def _executor(recorder: _Recorder) -> GoogleRequestExecutor:
    """Present the recording double as the executor boundary the writers take."""
    return cast("GoogleRequestExecutor", recorder)


def _sheets() -> SheetsResource:
    """Present the minimal Sheets double as the resource the writers take."""
    return cast("SheetsResource", _Sheets())


def _review_plan():
    return build_review_workbook(
        review_snapshot(),
        publication_id=UUID(int=2),
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=review_label,
    )


def _cells(body: dict[str, Any]) -> list[object]:
    return [cell for entry in body["data"] for row in entry["values"] for cell in row]


def test_formula_looking_text_is_sent_raw_and_numbers_stay_numbers() -> None:
    plan = _review_plan()
    recorder = _Recorder()

    _write_plan_values(execute=_executor(recorder), sheets=_sheets(), spreadsheet_id="sheet", plan=plan)

    literal_request, _, _ = recorder.calls[0]
    assert literal_request.body["valueInputOption"] == "RAW"
    cells = _cells(literal_request.body)
    assert _FORMULA_TEXT in cells
    assert 25.2 in cells
    assert all(isinstance(cell, (str, bool, float)) for cell in cells)
    for request, action, _ in recorder.calls[1:]:
        assert action == "sheets.spreadsheets.values.batchUpdate.formulas"
        assert _FORMULA_TEXT not in _cells(request.body)


def test_only_generated_formulas_use_user_entered_input() -> None:
    plan = build_export_plan(published_snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1)))
    assert plan.formula_cells
    recorder = _Recorder()

    _write_plan_values(execute=_executor(recorder), sheets=_sheets(), spreadsheet_id="sheet", plan=plan)

    by_input = {
        request.body["valueInputOption"]: request for request, _, _ in recorder.calls if request.kind == "values"
    }
    assert set(by_input) == {"RAW", "USER_ENTERED"}
    entered = _cells(by_input["USER_ENTERED"].body)
    assert len(entered) == len(plan.formula_cells)
    assert all(isinstance(cell, str) and cell.startswith("=") for cell in entered)
    assert not any(isinstance(cell, str) and cell in entered for cell in _cells(by_input["RAW"].body))


def test_structural_batch_that_creates_unkeyed_metadata_is_never_transport_retried() -> None:
    plan = _review_plan()
    recorder = _Recorder()

    _apply_plan_structural_requests(
        execute=_executor(recorder),
        sheets=_sheets(),
        spreadsheet_id="sheet",
        spreadsheet={},
        plan=plan,
        sheet_id_by_tab={tab.value: index for index, tab in enumerate(plan.tabs)},
    )

    ((request, action, retry),) = recorder.calls
    assert action == "sheets.spreadsheets.batchUpdate.structural"
    assert any("createDeveloperMetadata" in item for item in request.body["requests"])
    assert retry is RequestRetryPolicy.SINGLE_ATTEMPT
