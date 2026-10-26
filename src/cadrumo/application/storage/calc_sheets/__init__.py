"""Workbook export planning engine for modelo registry snapshots.

Translates a
:class:`domain.calculations.registry.schema.RegistrySnapshot` into a
:class:`application.storage.calc_sheets.records.SheetExportPlan` whose formulas
produce the same per-casilla rounded values as the local registry runtime. The
plan is consumed by the online Google Sheets apply adapter and by the offline
XLSX materializer, so layout, formulas, styling, provenance, and evidence stay on
one contract.

The package exposes these layers:

- Records (:mod:`application.storage.calc_sheets.records`) — strict
  frozen pydantic v2 types describing the workbook the engine intends to
  produce. The records are the shared vocabulary between the engine driver, both
  workbook materializers, the parity oracle, and the pull adapter.
- Translator (:mod:`application.storage.calc_sheets._translator`) — pure
  function that walks a registry
  :class:`domain.calculations.registry.schema_formula.FormulaExpression` AST and emits a
  Sheets A1 formula string, resolving casilla references through the layout
  planner.
- Engine driver (:mod:`application.storage.calc_sheets.engine`) —
  consumes a
  :class:`domain.calculations.registry.schema.RegistrySnapshot` plus a
  caller-supplied
  :class:`application.storage.calc_sheets.records.OperatorInputs` payload and
  assembles a
  :class:`application.storage.calc_sheets.records.SheetExportPlan` ready for
  either materializer.
- Export tables (:mod:`application.storage.calc_sheets.export_tables`) — owns
  the Guide and Evidencia values and the export identity stamps both
  materializers carry.
- Workbook cells (:mod:`application.storage.calc_sheets.workbook_cells`) —
  resolves the plan into the addressed cell stream every materializer writes, so
  no transport owns an address arithmetic of its own.
- Workbook export (:mod:`application.storage.calc_sheets.workbook_export`) —
  builds one modelo's plan and hands it to an injected materializer port,
  returning the payload with the facts that identify it.

Operator-facing CLI surface lives under
`src/cadrumo/entrypoints/cli/config/google.py`; this package contains
domain and application logic only.

See Also:
    :class:`domain.calculations.registry.schema.RegistrySnapshot`
        Registry-authored calculation surface compiled by the engine.
    :class:`application.storage.calc_sheets.records.SheetExportPlan`
        Shared workbook plan consumed by online and offline renderers.
    :func:`application.storage.calc_sheets.export_tables.evidence_table`
        Evidencia values consumed by both materializers.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
