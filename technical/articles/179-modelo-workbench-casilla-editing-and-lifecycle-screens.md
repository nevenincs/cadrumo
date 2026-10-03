# Modelo workbench, casilla editing, and lifecycle screens

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-179` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope and limits

This report covers the 12 assigned files: 4,907 source lines, 206,158 bytes, and 46,652 measured `o200k_base` proxy tokens. All assigned ranges were read across nine bounded pages. This is static analysis: no app, parser, registered operation, filesystem export, registry calculation, or test suite was run. The snapshot contains no tests for this workbench.

## Operator capabilities

The Modelo workbench gives an operator a per-declaration calculation workspace. It reads the current form and an edit admission through a profile/session-bound runtime source, then displays a result/deadline header, attention counts, casillas, official-form grids and repeating-group records. A virtualized casilla list keeps cursor identity by field address, adapts between table and stacked layouts, preserves rate/provenance cues, and lets the operator move between fields needing attention (casilla list (`src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`), attention navigation (`src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`), grid layout (`src/cadrumo/entrypoints/tui/modelo/workbench/grid.py`)). The header shows model/period, effective deadline, result direction, stale calculation/export state and counts for blockers, missing data, assumed values, and checks; it uses the form’s declared result disposition instead of guessing direction from a numeric sign (result presentation (`src/cadrumo/entrypoints/tui/modelo/workbench/header.py`), attention counts (`src/cadrumo/entrypoints/tui/modelo/workbench/header.py`)).

The operator can open a casilla panel to see what it asks, current value and origin, source/earlier filing information, what the box affects, and where it can be changed. For editable fields, each lexeme is passed to the application parser in the selected language and read back in canonical presentation before save is enabled. Assumed values are prefilled; keeping the original value is an explicit choice. Clear and restore are distinct actions, and source-owned/read-only fields offer the owning area where available (editor panel (`src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`), per-keystroke parsing (`src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`)). A bulk-confirm dialog lists each confirmable assumed value with its box, concept and current value, excludes source-fed or otherwise non-confirmable fields with a reason, and enables confirmation only after a deliberate tick (bulk confirmation (`src/cadrumo/entrypoints/tui/modelo/workbench/bulk_confirm.py`)).

The installed workbench stages changes as typed intents, runs preflight, and applies against the edit baseline admitted with the form. It also exposes calculation, verification, local filing, and export. Filing requires a calculation and verification report; exports present available artefact choices and, where applicable, explicit payment/refund/domiciliation elections. A separate result statement warns that local exports are not official AEAT filing evidence and reports completeness and software identity grade (installed adapter (`src/cadrumo/entrypoints/tui/modelo/workbench/installed.py`), edit preflight/apply (`src/cadrumo/entrypoints/tui/modelo/workbench/installed.py`), export request form (`src/cadrumo/entrypoints/tui/modelo/workbench/export.py`)). PDF is offered only when its optional extra is available; the UI does not silently substitute another export (artefact admission (`src/cadrumo/entrypoints/tui/modelo/workbench/export.py`)).

For applicable M303 periods, the workbench asks the operator for a joint-return election and, when the form says it applies, the Modelo 390 exemption evidence. An observed attestation is admitted by a separate registered operation; the resulting attachment identity and digest are passed to calculation. Other supported lifecycle operations include creating/reopening declaration work for a checked Modelo/year/period and reading form/help through registered operations (work creation (`src/cadrumo/entrypoints/tui/modelo/runtime_work_create.py`), workbench runtime reads (`src/cadrumo/entrypoints/tui/modelo/runtime_workbench_reads.py`)).

## Data and effect boundaries

`RuntimeModeloWorkbenchSource` retains one TUI profile/session and one work-unit identity. Each read is submitted, observed to a terminal state, required to have no effect, and resolved as a typed result. The returned form/help must name the selected profile and work unit, and session identity is checked around those reads (runtime source (`src/cadrumo/entrypoints/tui/modelo/runtime_workbench_reads.py`)). The installed screen adapter converts saved changes into scalar or binding intents and judges parsing/preflight against the admitted baseline. A renewed baseline may extend its lifetime, but a declaration that moved is refused while the operator’s staged changes remain with the caller (installed adapter (`src/cadrumo/entrypoints/tui/modelo/workbench/installed.py`), baseline and apply (`src/cadrumo/entrypoints/tui/modelo/workbench/installed.py`)).

Work creation validates the exact TUI client, profile/session, filing-year bounds, matching period year, and supported Modelo before submitting. It accepts only an expected success or the declared applicability refusal, correlates profile/period/Modelo/effect, refreshes the product generation after success, and returns the created/reused declaration only if that generation exposes it (create result checks (`src/cadrumo/entrypoints/tui/modelo/runtime_work_create.py`), create flow (`src/cadrumo/entrypoints/tui/modelo/runtime_work_create.py`)).

The casilla UI consumes form/read-model facts: origin, editability, typed constraints, source bindings, registry revision, calculation identity and help reach. It does not calculate taxes itself. When the lifecycle door submits calculation, edit, verify, file or export, registered application/runtime operations own the operation, validation and persistence. This report does not establish whether those underlying registry rules are legally current or calculations correct.

## Security and safety assessment

The code enforces meaningful session and state boundaries: runtime reads are no-effect operations with exact result identity; edit submissions are typed, baseline-bound and preflighted; work creation is scoped to the retained client; and lifecycle operations require the current admitted calculation/verification identities. Refused lexemes are not kept in the editor; a stale baseline prevents apply rather than overwriting a changed declaration. Bulk confirmation is limited to confirmable assumed values and is a separate affirmative step. Recorded declarations render as facts with no active attention chips and use the correction route for changes.

One privacy question merits checking in the logging configuration: if the field parser raises unexpectedly, the editor logs a traceback with `exc_info=True`, although the user-facing message exposes only a generic unreadable result. Review whether parser exceptions can contain the lexeme or other personal data and whether application logging redacts it (parser failure handling (`src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`)). Export accepts an operator-chosen path and resolves it in the lifecycle door; this chunk does not define filesystem policy or prove confinement, so trace that path through the export operation before making a boundary claim (export path (`src/cadrumo/entrypoints/tui/modelo/lifecycle.py`)).

The UI is carefully designed to prevent ambiguous zero/missing/rate displays and to preserve provenance, especially where assumptions, rates, imported values or earlier filings are involved. Dynamic terminal layout, contrast, parser localization, keyboard behavior and the operation gates still need runtime verification. The source includes comments describing intended behavior but no tests here substantiate those claims. Synthesis should trace the app composition, operation definitions, read models and calculation registry before elevating any UI-only guarantee to a product-wide property.

## Complete assigned-file coverage

All 12 manifest files and their full declared line ranges were read.

- runtime_work_create.py (`src/cadrumo/entrypoints/tui/modelo/runtime_work_create.py`) — 266 lines
- runtime_workbench_reads.py (`src/cadrumo/entrypoints/tui/modelo/runtime_workbench_reads.py`) — 159 lines
- workbench/__init__.py (`src/cadrumo/entrypoints/tui/modelo/workbench/__init__.py`) — 5 lines
- workbench/bulk_confirm.py (`src/cadrumo/entrypoints/tui/modelo/workbench/bulk_confirm.py`) — 240 lines
- workbench/casilla_list.py (`src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`) — 1,538 lines
- workbench/dialog_width.py (`src/cadrumo/entrypoints/tui/modelo/workbench/dialog_width.py`) — 39 lines
- workbench/editor.py (`src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`) — 708 lines
- workbench/editor_explanations.py (`src/cadrumo/entrypoints/tui/modelo/workbench/editor_explanations.py`) — 215 lines
- workbench/export.py (`src/cadrumo/entrypoints/tui/modelo/workbench/export.py`) — 245 lines
- workbench/grid.py (`src/cadrumo/entrypoints/tui/modelo/workbench/grid.py`) — 287 lines
- workbench/header.py (`src/cadrumo/entrypoints/tui/modelo/workbench/header.py`) — 712 lines
- workbench/installed.py (`src/cadrumo/entrypoints/tui/modelo/workbench/installed.py`) — 493 lines
<!-- /preserved:article -->
