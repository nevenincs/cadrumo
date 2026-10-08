"""Local-only preview and pure payload comparison helpers.

Preview inventories a new publication without reading an earlier document.
Actual provider acceptance uses the application OAuth route in the live campaign.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable
from datetime import date

import pytest

from .....application.storage.calc_sheets.engine import build_export_plan
from .....domain.calculations.registry.tests.published_authority import published_snapshot
from .._calc_sheets_apply_values import (
    written_cell_values,
)
from ..calc_sheets_apply import (
    _new_target_export_preview,
    _plan_value_payload,
    preview_export_plan,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _m130_plan():
    snapshot = published_snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    return build_export_plan(snapshot)


class TestNewTargetPreview:
    """A target with nothing on Drive yet previews as all-new, nothing to clear."""

    def test_every_value_cell_previews_as_changed_and_nothing_is_stale(self) -> None:
        plan = _m130_plan()
        preview = _new_target_export_preview(plan)

        assert preview.spreadsheet_exists is False
        assert preview.spreadsheet_id is None
        assert preview.spreadsheet_url is None
        assert preview.folder_id is None
        assert preview.ranges_to_clear == ()
        assert preview.value_cells_unchanged == 0
        assert preview.value_cells_changed == len(written_cell_values(_plan_value_payload(plan)))
        assert preview.formula_cells_to_write == len(plan.formula_cells)


def _code_body_source(func: Callable[..., object]) -> str:
    """Return a function's source with its docstring stripped.

    The docstring legitimately narrates the write helpers and Sheets actions
    this function must NOT reach, so scanning raw ``inspect.getsource`` output
    for those same names produces a false positive against prose. Parsing and
    dropping the leading docstring statement scans only the executable body.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    func_node = tree.body[0]
    assert isinstance(func_node, ast.FunctionDef)
    first_statement = func_node.body[0]
    if (
        isinstance(first_statement, ast.Expr)
        and isinstance(first_statement.value, ast.Constant)
        and isinstance(first_statement.value.value, str)
    ):
        func_node.body = func_node.body[1:]
    return ast.unparse(func_node)


class TestPreviewNeverWrites:
    """The preview function's own source never reaches a write-capable call."""

    def test_the_preview_function_never_names_a_write_helper_or_a_write_action(self) -> None:
        source = _code_body_source(preview_export_plan)

        # Helpers that create, clear, or rewrite Drive/Sheets content.
        for forbidden_call in (
            "_create_folder",
            "_ensure_folder",
            "_create_spreadsheet",
            "_ensure_plan_tabs_and_grid",
            "_force_spreadsheet_locale",
            "_write_plan_values",
            "_clear_stale_addresses",
            "_apply_plan_structural_requests",
        ):
            assert forbidden_call not in source, f"preview_export_plan must never call {forbidden_call}"

        # Sheets/Drive action labels this module only ever attaches to a
        # write-shaped request (batchUpdate / batchClear / create).
        for forbidden_action in (
            "values.batchUpdate",
            "values.batchClear",
            "spreadsheets.batchUpdate",
            "spreadsheets.create",
            "files.create",
            "files.update",
        ):
            assert forbidden_action not in source, f"preview_export_plan must never reach a {forbidden_action} action"

    def test_preview_needs_no_remote_service_and_inventories_only_a_new_document(self) -> None:
        from .....tests.google_credentials import unused_google_credentials

        plan = _m130_plan()
        result = preview_export_plan(plan, credentials=unused_google_credentials(), root_folder_id="local-root-id")
        assert result.spreadsheet_exists is False
        assert result.spreadsheet_id is None
        assert result.ranges_to_clear == ()
        assert result.value_cells_changed > 0
