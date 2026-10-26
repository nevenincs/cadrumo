"""Typed ``--json`` payload schemas for ``aeat app modelo spreadsheet``.

Active :class:`OutputSchema` results enter :class:`SchemaEnvelope` through
:func:`emit_envelope`.

Sequence fields use ``list`` rather than ``tuple`` because
``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.

The classes carry the CLI transport shape only. Workbook semantics stay owned
by :mod:`calc_sheets`, and the export plan by :mod:`export`.
"""

from __future__ import annotations

from ...core.json_contract import OutputSchema


class ModeloSpreadsheetPushResult(OutputSchema):
    """JSON envelope for ``aeat app modelo spreadsheet push``.

    Projects :class:`CalcSheetsApplyResult`
    after :func:`build_export_plan` creates
    the pure :class:`SheetExportPlan` and
    :func:`apply_export_plan`
    materialises it in Google Sheets.

    ``dry_run=True`` projects :class:`CalcSheetsExportPreview`
    from :func:`preview_export_plan` instead: Drive and Sheets are read but
    never written. ``folder_id``, ``spreadsheet_id`` and ``spreadsheet_url``
    are ``None`` only on a preview against a target that does not exist yet —
    the first export for a modelo, period and year has nothing to look up.
    ``ranges_to_clear``, ``value_cells_changed`` and ``value_cells_unchanged``
    are populated on a preview only: a real apply rewrites every cell the plan
    carries unconditionally rather than diffing against current content, so
    those fields carry no meaning there.
    """

    operation: str = "modelo.spreadsheet.push"
    profile: str
    modelo: str
    revision: str
    period: str
    year: int
    engine_version: str
    registry_sha: str
    root_folder_id: str
    dry_run: bool = False
    spreadsheet_exists: bool | None = None
    folder_id: str | None = None
    spreadsheet_id: str | None = None
    spreadsheet_url: str | None = None
    value_cells_written: int
    formula_cells_written: int
    protected_ranges_written: int
    tab_count: int
    ranges_to_clear: list[str] = []
    value_cells_changed: int | None = None
    value_cells_unchanged: int | None = None
    formula_cells_to_write: int | None = None


class ModeloSpreadsheetExportResult(OutputSchema):
    """JSON envelope for ``aeat app modelo spreadsheet export``.

    The offline counterpart of ``push``: the same export plan, materialized as
    an ``.xlsx`` workbook and published to the operator's ``--output`` file.
    ``byte_size`` and ``sha256`` describe the file that landed there.
    """

    operation: str = "modelo.spreadsheet.export"
    modelo: str
    revision: str
    period: str
    year: int
    output_path: str
    byte_size: int
    sha256: str
    tab_names: list[str]
    casilla_count: int
    prefill_relations: bool
