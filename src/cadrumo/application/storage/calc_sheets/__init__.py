"""Workbook export planning engine for modelo registry snapshots.

Translates a
:class:`domain.calculations.registry.RegistrySnapshot` into a
:class:`application.storage.calc_sheets.records.SheetExportPlan` whose formulas
produce the same per-casilla rounded values as the local registry runtime. The
plan is shared by the Google Sheets apply adapter and the offline XLSX
materializer, so layout, formulas, styling, provenance, and evidence stay on
one contract.

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
- Offline export
  (:mod:`application.storage.calc_sheets.workbook_export`) — serializes
  the same plan into XLSX bytes plus the machine-readable evidence sidecar.

Operator-facing CLI surface lives under
`src/cadrumo/entrypoints/cli/_config/_google.py`; this package contains
domain and application logic only.

See Also:
    :class:`domain.calculations.registry.RegistrySnapshot`
        Registry-authored calculation surface compiled by the engine.
    :class:`application.storage.calc_sheets.records.SheetExportPlan`
        Shared workbook plan consumed by online and offline renderers.
    :func:`application.storage.calc_sheets.workbook_export.serialize_offline_export`
        Offline XLSX plus evidence-sidecar serializer for operator-directed
        exports.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
