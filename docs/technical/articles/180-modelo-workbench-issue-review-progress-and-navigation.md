# Modelo workbench issue review, progress and navigation

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-180` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope and limits

This report covers all 15 assigned workbench files: 5,159 source lines, 200,207 bytes, and 46,314 measured `o200k_base` proxy tokens. All declared ranges were read completely over nine bounded helper pages; page 2 was repeated at a lower output cap after the first attempt exceeded the display context. This is static analysis only. No application, registered operation, UI, calculation, export, or tests were run. The chunk implements presentation and action routing; it does not establish the correctness of the application operations behind its ports.

## Operator capabilities

The workbench turns calculation and verification results into one review list. `issue_lines` converts form issues into user-facing findings; the shared scale orders blockers, missing values, confirmations, checks, and information. It also accounts for applicable fields that have not been entered or whose calculated defaults still need confirmation. When a calculation/verification finding already covers a missing box, the projection avoids making the same omission look like two separate findings. Findings may reveal box numbers, the relevant form area, and—on demand—technical codes, source facts, or legal references (finding projection (`src/cadrumo/entrypoints/tui/modelo/workbench/issue_projection.py`), severity scale and unentered-box counts (`src/cadrumo/entrypoints/tui/modelo/workbench/issue_scale.py`)).

The issue dialog groups these items by severity, reports counts, and updates the Enter description to match the highlighted row. Enter moves to a box or section when the issue has a destination; otherwise it expands/collapses its detail. Separate keys request recalculation, open the value-owning area, confirm assumed values in the selected part of the form, or reveal technical detail. Actions return typed choices to the workbench instead of performing business operations inside the modal (issue screen (`src/cadrumo/entrypoints/tui/modelo/workbench/issues.py`), shared issue options and width-aware footer (`src/cadrumo/entrypoints/tui/modelo/workbench/issue_screen_components.py`)).

The navigator gives pages and sections readable headings, attention counts, fold state, and a current-position cue. It suppresses technical identifiers as headings, groups repeated section headings, and switches to a one-line breadcrumb on narrow screens. A page explicitly marked inapplicable for the period is dimmed, starts closed, and is excluded from missing/assumed counts; a page whose applicability is unknown remains in the work. Recorded declarations suppress to-do marks and counts. The symbol panel is built from the same mark vocabulary used by the workbench and checks at import that every drawable mark is explained exactly once (readable page and section titles, inapplicable counts (`src/cadrumo/entrypoints/tui/modelo/workbench/navigator.py`), page/section rows (`src/cadrumo/entrypoints/tui/modelo/workbench/navigator.py`), legend (`src/cadrumo/entrypoints/tui/modelo/workbench/legend.py`)).

The casilla list can show all values, values needing attention, operator-entered values, records-fed values, calculated values, or nonzero amounts. It retains staged values across filters, renders official grids in column order, keeps literals and hidden cells in their table positions, and exposes repeating records as read-only tables when the full form is shown. Findings about repeating-record columns contribute attention to the section holding their table. Staged changes can be shown afterward as a before/after result grouped into operator, calculated, sourced, and other changes, with each row returning to its box (page construction and record findings (`src/cadrumo/entrypoints/tui/modelo/workbench/page_items.py`), filters and page item generation (`src/cadrumo/entrypoints/tui/modelo/workbench/page_items.py`), result comparison (`src/cadrumo/entrypoints/tui/modelo/workbench/result.py`)).

## How it works and what it trusts

The screen is given separate reader and action ports. The reader supplies a form, help cards and the reason editing is refused; the action port parses typed edits, preflights/applies changes, calculates, verifies, files, exports, and reads an export result. Staged changes cross that boundary as typed semantic addresses and `SET`, `CLEAR`, or `RESTORE` intents, while parser results distinguish an accepted typed scalar from a refusal. This chunk supplies the interface and front-end contract, not its composition root or backend implementation (typed ports and operations (`src/cadrumo/entrypoints/tui/modelo/workbench/ports.py`)).

Progress is derived from the form's counts, staged-change count, verification and filing state. Its four steps are fill, calculate, review and file; the first incomplete step is current. The next action asks to apply staged changes first, then handles recorded state, stale calculations, missing/assumed values, checks, blockers and export/recording. A calculation note that only verification can decide directs the operator to verification, and an export from an earlier calculation directs them to export again. Assumed values and blockers withhold exporting to the AEAT and recording a filing. This is a local presentation decision based on supplied facts, not a substitute for backend admission (progress state (`src/cadrumo/entrypoints/tui/modelo/workbench/progress.py`), next-action ordering (`src/cadrumo/entrypoints/tui/modelo/workbench/progress.py`)).

Before an apply, the review lists every staged change with its prior and proposed reading and explains whether it clears, restores, sets, or displaces a source/calculated value. It highlights rebased changes whose baseline changed and can name values that may be returned to source when the declaration does not record which values the operator entered. Blocking preflight notes disable Apply; unknown-entry or rebase conditions require acknowledgement. Applying remains a returned decision for the caller to execute (effect and risk wording (`src/cadrumo/entrypoints/tui/modelo/workbench/review.py`), acknowledgement and Apply gate (`src/cadrumo/entrypoints/tui/modelo/workbench/review.py`)).

Bulk confirmation is scoped to the section under the cursor, falling back to the current page; it never selects the whole declaration at once. It lists only values with the `DEFAULT_TO_CONFIRM` origin and routes to an individual editor if none in scope can be confirmed from the list. The next-confirm action searches forward in form order and skips pages that do not apply this period (confirmation scope and dialog admission (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_confirmation.py`)).

The main screen reads in a worker thread, retains presentation state such as page/filter/sort/cursor, and refreshes help-card caches after a fresh form read. It prevents its own navigation/action keys from firing while a docked editor owns input, and gates editing on both an action port and the form's edit-admitted flag; recorded forms are rendered as read-only. A failed form read logs the exception and shows a generic message. The screen does not own repositories or registry operations (screen setup and read refresh (`src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`), fresh-read state handling (`src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`)).

## Security, quality and unresolved questions

The presentation layer has useful guardrails: values stay typed across its action port; staged edits require preflight/review; source displacement and uncertain operator-entry attribution are surfaced; confirmations are limited to a local form scope; explicit inapplicability is not treated as missing data; and filing progress withholds export/recording while assumptions or blockers remain. The issue and legend tables include totality checks, and footer keys are hidden when the current row has no corresponding action. These controls are visible in this chunk, but they rely on form/read-model integrity and the application implementation behind the ports. The UI flags do not independently authorize an operation.

One conditional privacy point: the read-failure path includes `exc_info=True` while limiting the log message itself to the exception type. Whether a traceback can disclose personal values depends on reader exceptions and logging redaction, which are outside this chunk (read error handling (`src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`)). No test code is assigned here, so keyboard behavior, Textual event semantics, narrow-terminal layouts, arithmetic of attention counts, and lifecycle gating are unverified dynamically.

Synthesis should trace the port implementations, the producer of `ModeloWorkForm` and its issues/counts, the operation lifecycle that consumes the returned decisions, and the `SourceSurface` navigation targets. It should also verify that `ModeloFormValueChangeV1` contains the complete set of changes to report and that preflight's `operator_entries_unknown`/stale facts map to the acknowledgements shown. This report confirms the presentation policy only; legal content, calculation accuracy, backend authorization, export path safety and persistence are not established by these files.

## Complete assigned-file coverage

Every manifest file and full declared line range was read.

- issue_projection.py (`src/cadrumo/entrypoints/tui/modelo/workbench/issue_projection.py`) — 367 lines
- issue_scale.py (`src/cadrumo/entrypoints/tui/modelo/workbench/issue_scale.py`) — 370 lines
- issue_screen_components.py (`src/cadrumo/entrypoints/tui/modelo/workbench/issue_screen_components.py`) — 248 lines
- issues.py (`src/cadrumo/entrypoints/tui/modelo/workbench/issues.py`) — 395 lines
- keys.py (`src/cadrumo/entrypoints/tui/modelo/workbench/keys.py`) — 36 lines
- legend.py (`src/cadrumo/entrypoints/tui/modelo/workbench/legend.py`) — 242 lines
- navigator.py (`src/cadrumo/entrypoints/tui/modelo/workbench/navigator.py`) — 590 lines
- page_items.py (`src/cadrumo/entrypoints/tui/modelo/workbench/page_items.py`) — 575 lines
- ports.py (`src/cadrumo/entrypoints/tui/modelo/workbench/ports.py`) — 219 lines
- progress.py (`src/cadrumo/entrypoints/tui/modelo/workbench/progress.py`) — 436 lines
- result.py (`src/cadrumo/entrypoints/tui/modelo/workbench/result.py`) — 224 lines
- review.py (`src/cadrumo/entrypoints/tui/modelo/workbench/review.py`) — 447 lines
- screen.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`) — 688 lines
- screen_confirmation.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_confirmation.py`) — 174 lines
- screen_constants.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_constants.py`) — 148 lines
<!-- /preserved:article -->
