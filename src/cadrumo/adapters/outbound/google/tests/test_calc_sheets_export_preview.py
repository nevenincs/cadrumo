"""The Sheets export dry-run previews without ever writing.

Write-shaped online tests against a real account are project-forbidden, matching
every sibling in this package (see ``test_calc_sheets_apply_no_empty_window.py``
and ``test_calc_sheets_export_integration.py``). What is gated here, offline, is
the same shape those modules already established: the pure diff computation
proven against a REAL modelo plan, and a structural proof that the preview
function's own source never reaches a write-capable helper or a write-shaped
Sheets/Drive action.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable
from datetime import date

import pytest

from .....application.storage.calc_sheets.engine import build_export_plan
from .....domain.calculations.registry.authority import bundled_authority
from .._calc_sheets_apply_values import (
    _build_formula_data,
    changed_cell_addresses,
    payload_written_addresses,
    stale_addresses,
    written_cell_values,
)
from ..calc_sheets_apply import (
    _new_target_export_preview,
    _plan_value_payload,
    preview_export_plan,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _m130_plan():
    snapshot = bundled_authority().snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    return build_export_plan(snapshot)


class TestWrittenCellValuesSharesTheWrittenAddressesWalk:
    """``written_cell_values`` and ``payload_written_addresses`` cannot drift."""

    def test_a_real_plans_value_payload_yields_the_same_address_set_both_ways(self) -> None:
        payload = _plan_value_payload(_m130_plan())
        assert payload, "the plan produced no value payload -- the gate below would be vacuous"

        addresses = payload_written_addresses(payload)
        values = written_cell_values(payload)

        assert set(values) == addresses
        assert len(values) == len(addresses), "one address must map to exactly one value"

    def test_a_multi_cell_row_carries_its_own_two_values(self) -> None:
        entry = {"range": "'Evidencia'!B4", "values": [["left", "right"]]}
        values = written_cell_values([entry])
        assert values == {
            "'Evidencia'!B4": "left",
            "'Evidencia'!C4": "right",
        }

    def test_a_non_anchor_range_refuses_rather_than_under_reporting(self) -> None:
        with pytest.raises(ValueError, match="single-cell anchor"):
            written_cell_values([{"range": "'Evidencia'!A1:C9", "values": [["x"]]}])


class TestChangedCellAddresses:
    """A cell is only ``changed`` when its current content genuinely differs."""

    def test_re_previewing_an_unchanged_spreadsheet_finds_nothing_changed(self) -> None:
        """The byte-identical case: current content already equals every target value."""
        target = written_cell_values(_plan_value_payload(_m130_plan()))
        assert target, "no value payload to diff -- the positive control below would be vacuous"

        changed = changed_cell_addresses(target=target, current=target)

        assert changed == ()

    def test_a_genuinely_different_value_is_reported_changed(self) -> None:
        target = {"'Entradas'!B4": "100.00"}
        current = {"'Entradas'!B4": "50.00"}

        assert changed_cell_addresses(target=target, current=current) == ("'Entradas'!B4",)

    def test_a_decimal_written_as_fixed_point_text_matches_the_number_sheets_already_stores(self) -> None:
        """``coerce_decimal`` normalisation: "1234.50" (payload) == 1234.5 (Sheets)."""
        target = {"'Entradas'!B4": "1234.50"}
        current = {"'Entradas'!B4": 1234.5}

        assert changed_cell_addresses(target=target, current=current) == ()

    def test_a_cell_never_read_back_matches_only_a_blank_target(self) -> None:
        blank_target = {"'Entradas'!B4": ""}
        populated_target = {"'Entradas'!B4": "1.00"}
        current: dict[str, object] = {}

        assert changed_cell_addresses(target=blank_target, current=current) == ()
        assert changed_cell_addresses(target=populated_target, current=current) == ("'Entradas'!B4",)

    def test_a_boolean_cell_is_never_coerced_through_decimal(self) -> None:
        assert changed_cell_addresses(target={"'Entradas'!B4": True}, current={"'Entradas'!B4": True}) == ()
        assert changed_cell_addresses(target={"'Entradas'!B4": True}, current={"'Entradas'!B4": False}) == (
            "'Entradas'!B4",
        )


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

    def test_the_preview_function_only_uses_read_only_drive_lookups(self) -> None:
        """``_find_folder`` / ``_find_spreadsheet`` (read), never their ``_ensure_*`` create counterparts."""
        source = _code_body_source(preview_export_plan)
        assert "_find_folder(" in source
        assert "_find_spreadsheet(" in source


class TestPreviewComputationReusesTheRealAdaptersOwnDiffPrimitives:
    """The preview's clear-set math is the same ``stale_addresses`` the real apply uses."""

    def test_a_preview_against_content_already_matching_the_plan_clears_nothing(self) -> None:
        plan = _m130_plan()
        payload = _plan_value_payload(plan) + _build_formula_data(plan.formula_cells)
        written = payload_written_addresses(payload)

        # "Occupied" == "written" is exactly the re-apply-the-same-plan case
        # the P01 gate already proves clears nothing on the real write path;
        # this asserts the preview's own stale-set math agrees.
        assert stale_addresses(occupied=written, written=written) == ()
