"""Workbook export planning engine for modelo registry snapshots.

Translates a
:class:`domain.calculations.registry.RegistrySnapshot` into a
:class:`application.storage.calc_sheets.records.SheetExportPlan` whose formulas
produce the same per-casilla rounded values as the local registry runtime. The
plan is consumed by the Google Sheets apply adapter, so layout, formulas,
styling, provenance, and evidence stay on one contract.

The package exposes three layers:

- Records (:mod:`application.storage.calc_sheets.records`) — strict
  frozen pydantic v2 types describing the workbook the engine intends to
  produce. The records are the shared vocabulary between the engine driver, the
  apply adapter, the parity oracle, and the pull adapter.
- Translator (:mod:`application.storage.calc_sheets._translator`) — pure
  function that walks a registry
  :class:`domain.calculations.registry.FormulaExpression` AST and emits a
  Sheets A1 formula string, resolving casilla references through the layout
  planner.
- Engine driver (:mod:`application.storage.calc_sheets.engine`) —
  consumes a
  :class:`domain.calculations.registry.RegistrySnapshot` plus a
  caller-supplied
  :class:`application.storage.calc_sheets.records.OperatorInputs` payload and
  assembles a
  :class:`application.storage.calc_sheets.records.SheetExportPlan` ready for the
  apply adapter.
- Export tables (:mod:`application.storage.calc_sheets.export_tables`) — owns
  the Guide and Evidencia values consumed by the live apply adapter.

Operator-facing CLI surface lives under
`src/cadrumo/entrypoints/cli/config/google.py`; this package contains
domain and application logic only.

See Also:
    :class:`domain.calculations.registry.RegistrySnapshot`
        Registry-authored calculation surface compiled by the engine.
    :class:`application.storage.calc_sheets.records.SheetExportPlan`
        Shared workbook plan consumed by online and offline renderers.
    :func:`application.storage.calc_sheets.export_tables.evidence_table`
        Evidencia values consumed by the live apply adapter.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
