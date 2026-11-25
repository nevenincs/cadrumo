"""Which Sheets channel carries literal text, numbers and generated formulas, and which retry class each request has."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from .....application.storage.calc_sheets.engine import build_export_plan
from .....application.storage.calc_sheets.review_workbook import build_review_workbook
from .....application.storage.calc_sheets.tests.review_fixture import review_label, review_snapshot
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..api import RequestRetryPolicy
from ..calc_sheets_apply import apply_plan_structural_requests, write_plan_values
from ._calc_sheets_support import modelo_130_first_quarter_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FORMULA_TEXT = '=IMPORTXML("https://example.invalid", "x")'


class _Request:
    def __init__(self, kind: str, body: dict[str, Any]) -> None:
        self.kind = kind
        self.body = body


def _sheets() -> Any:
    """A stand-in for the discovery-built resource that records request bodies."""
    values = SimpleNamespace(batchUpdate=lambda **kwargs: _Request("values", kwargs["body"]))
    sheets = SimpleNamespace(
        values=lambda: values,
        batchUpdate=lambda **kwargs: _Request("structure", kwargs["body"]),
    )
    sheets.spreadsheets = lambda: sheets
    return sheets


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[_Request, str, RequestRetryPolicy]] = []

    def __call__(self, request: _Request, *, action: str, retry: RequestRetryPolicy) -> dict[str, Any]:
        self.calls.append((request, action, retry))
        return {}


def _review_plan():
    return build_review_workbook(
        review_snapshot(),
        publication_id=UUID(int=2),
        exported_at=datetime(filing_year_envelope().horizon, 10, 5, tzinfo=UTC),
        label=review_label,
    )


def _cells(body: dict[str, Any]) -> list[object]:
    return [cell for entry in body["data"] for row in entry["values"] for cell in row]


def test_formula_looking_text_is_sent_raw_and_numbers_stay_numbers() -> None:
    plan = _review_plan()
    recorder: Any = _Recorder()

    write_plan_values(execute=recorder, sheets=_sheets(), spreadsheet_id="sheet", plan=plan)

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
    plan = build_export_plan(modelo_130_first_quarter_snapshot())
    assert plan.formula_cells
    recorder: Any = _Recorder()

    write_plan_values(execute=recorder, sheets=_sheets(), spreadsheet_id="sheet", plan=plan)

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
    recorder: Any = _Recorder()

    apply_plan_structural_requests(
        execute=recorder,
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
