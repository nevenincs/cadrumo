# Modelo workbench editing, source map, and operation flow

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-181` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope and limits

This report covers all 20 assigned files: 5,092 source lines, 211,132 bytes, and 47,481 measured `o200k_base` proxy tokens. All manifest lines were read fully across nine bounded pages. This is static analysis; no TUI, operation, calculation, source import, or test suite was run. Several files describe facts supplied by application read models and operation projections, so their correctness and freshness depend on code outside this chunk.

## Product capabilities

The Modelo workbench lets a filer search the whole declaration by box number or words, jump directly to an exact box number, sort across pages by number, amount, or attention, filter values, fold the navigator, and move between fields requiring action. Numeric search ranks an exact box before a prefix; leading zeros are normalized for exact matching, while typed leading zeros are retained for prefix matches. Text search folds case and accents across the box, readable label, and description. Hits show the current staged value, page, and origin, and the help band explains the highlighted result (search data and matching (`src/cadrumo/entrypoints/tui/modelo/workbench/search.py`), ranking and exact go-to (`src/cadrumo/entrypoints/tui/modelo/workbench/search.py`)).

Each field's help can explain its label, description, rate, origin, source, formula, boxes it feeds, quoted official text, legal references, constraints, and editability. Full help cards are fetched off the event loop and cached by box and output language; a generation guard discards stale results after a form refresh or language change. On filed declarations, the same band explains what a value holds and why it is read-only. The source map groups every form field by provenance, distinguishes a source that produced a value from one returning none or not yet read, names earlier declarations and the AEAT import date when those facts are available, and routes a selected source to its owning product area where a destination exists (help card handling (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_help.py`), source classification (`src/cadrumo/entrypoints/tui/modelo/workbench/sources.py`), group construction (`src/cadrumo/entrypoints/tui/modelo/workbench/sources.py`)).

Edits remain in an in-memory session until review and apply. The session admits typed sets only for declared typed editabilities, clears only operator-entered values, restores an overridden source only where the field permits it, and confirms only fields admitted as confirmable. Entering the value already held by an operator-owned field removes the staged edit; keeping an assumed value remains a staged confirmation. If the declaration changes, edits are rechecked against its current fields; changes that no longer apply are dropped and those whose prior value or origin moved are marked for renewed review (edit session rules (`src/cadrumo/entrypoints/tui/modelo/workbench/session.py`), rebase behavior (`src/cadrumo/entrypoints/tui/modelo/workbench/session.py`)).

Calculation and filing actions are presented as one next step at a time. Calculation warns and asks before proceeding when operator-entry attribution is unknown, and collects ordinary M303 filing evidence when the action port says it is required. Export requires a verified form and is withheld for staged edits, unresolved blockers, or assumed values; recording a filing requires confirmation and refuses an export produced from an earlier calculation. The UI routes calculation, verification, apply, export and local filing through the supplied action port and supervised operation modal, then refreshes the product and may show a before/after list of changed boxes. A stale edit baseline triggers rebase and review again; operation refusal keeps the saved values and shows the refusal explanation (calculation prerequisites (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_next_step.py`), export and filing gates (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_operation.py`), operation settlement and refresh (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_operation.py`)).

## Data, trust boundaries, and safety

The view layer receives forms, help cards and operation behavior through explicit reader/action ports. It does not calculate taxes or persist field values itself. Operation submission yields a controller port bound to one submitted operation and actor; observation is paged, pending reviews have separate exact control ports, and cancellation is described as a request rather than rollback (operation controller contract (`src/cadrumo/entrypoints/tui/operations/controller_port.py`)).

Navigation is constrained by a closed six-destination catalogue. Frozen models tie focus to its destination; non-available routes must have neither a screen factory nor admitted action candidates; available routes require an inspectable factory; action identifiers must be unique and route-local. Search navigation compares the result's admission with the route's current admission and refuses unavailable or mismatched destinations before creating a screen (destination catalogue and route validation (`src/cadrumo/entrypoints/tui/navigation.py`), search-result admission and screen creation (`src/cadrumo/entrypoints/tui/navigation.py`)). This establishes front-end routing consistency, not access control to underlying business actions.

The visual vocabulary centralizes glyphs, meanings, colors and field standings. Import-time checks make the origin and attention mappings total over their enums, require a count for each non-done state, and reject ambiguous marks. Rows, page summaries, progress and legends reuse that vocabulary. The source and help views treat provenance as supplied facts: an earlier-filing carry with no applicable prior declaration is explicitly distinguished from a source that has not yet been read, and held zero is not presented as empty (field counting and shared states (`src/cadrumo/entrypoints/tui/modelo/workbench/vocabulary.py`), origin/source wording (`src/cadrumo/entrypoints/tui/modelo/workbench/vocabulary.py`)).

The UI keeps an editor docked across resize so typed input is not lost, gives the list focus after the panel closes, and guards its own hotkeys while the dock has focus. Leaving with staged edits presents an explicit discard confirmation. Review errors and read/operation failures show a generic user notice; the code logs exception tracebacks. Whether those traces can expose personal values depends on exception contents and the logging configuration, which this chunk does not establish (editor mount and close lifecycle (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_editor.py`), leave confirmation (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_footer.py`), operation error handling (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_operation.py`)).

## Implementation assessment and follow-up

The strongest design feature is the separation between typed in-memory presentation intent and application operations, combined with rebasing, preflight, explicit review and user acknowledgement for changes whose effects are uncertain. Navigation contracts fail closed for unknown, mismatched, stale, unavailable or unregistered routes. Provenance and “not yet read” are modeled separately, so the UI can avoid implying that absent data is zero or that an unattempted import returned nothing.

No confirmed product defect is established in this chunk. No tests are assigned here, and static reading cannot validate Textual focus/event behavior, translations, layout under real terminal widths, registry-backed calculations, or host route composition. Conditional privacy risk remains around exception tracebacks. Synthesis should trace the concrete reader/action adapters and operation definitions; verify that mutation handlers revalidate backend admission and export paths; and confirm that source policies, imported-data dates, operator-entry attribution and earlier-filing labels are produced from authoritative current state. Bundled legal excerpts in help cards are presentation material, not independent legal validation.

## Complete assigned-file coverage

All 20 manifest files and their complete declared line ranges were read.

- screen_editor.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_editor.py`) — 213 lines
- screen_footer.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_footer.py`) — 249 lines
- screen_help.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_help.py`) — 167 lines
- screen_help_content.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_help_content.py`) — 146 lines
- screen_navigation.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_navigation.py`) — 186 lines
- screen_next_step.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_next_step.py`) — 253 lines
- screen_operation.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_operation.py`) — 318 lines
- screen_presentation.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_presentation.py`) — 279 lines
- screen_review.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_review.py`) — 168 lines
- screen_widgets.py (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_widgets.py`) — 35 lines
- search.py (`src/cadrumo/entrypoints/tui/modelo/workbench/search.py`) — 336 lines
- session.py (`src/cadrumo/entrypoints/tui/modelo/workbench/session.py`) — 281 lines
- sorting.py (`src/cadrumo/entrypoints/tui/modelo/workbench/sorting.py`) — 192 lines
- sources.py (`src/cadrumo/entrypoints/tui/modelo/workbench/sources.py`) — 795 lines
- status_bar.py (`src/cadrumo/entrypoints/tui/modelo/workbench/status_bar.py`) — 45 lines
- vocabulary.py (`src/cadrumo/entrypoints/tui/modelo/workbench/vocabulary.py`) — 775 lines
- wording.py (`src/cadrumo/entrypoints/tui/modelo/workbench/wording.py`) — 90 lines
- navigation.py (`src/cadrumo/entrypoints/tui/navigation.py`) — 461 lines
- operations/__init__.py (`src/cadrumo/entrypoints/tui/operations/__init__.py`) — 5 lines
- operations/controller_port.py (`src/cadrumo/entrypoints/tui/operations/controller_port.py`) — 98 lines
<!-- /preserved:article -->
