---
tags:
  - '#audit'
  - '#desktop-modelo-workspace'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:1eb131dc4496680192823bbfc29bb4cd91271458c606323c253a6ca0ccdd1516'
related:
  - "[[2026-10-23-desktop-modelo-workspace-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace desktop-modelo-workspace with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `desktop-modelo-workspace` audit: `P01 phase-close review`

## Scope

The formal phase-close review of P01 (steps S01 to S10, commits `1671c8dd7d` to `636c54e71f`, with the related relay commits `73546c4f0f` and `1706f66723` and the locale move `cf293aaee2`), run on 2026-10-24 by an independent opus review lane against the governing decisions. It checked parity with the TUI code each step moved, the public contract and boundaries, private-data handling of typed edit entries, the list read's access, test strength, and what the desktop would still have to classify itself compared with the frozen prototype. Checks the reviewer ran: 152 focused application and entrypoint tests passed, the contract manifest check and import contracts passed, the S01 mutation claim reproduced, and 54 real forms and 154 catalogue keys in four languages were scanned without writing to the repository.

## Findings

### list-availability-states | high | the declarations list drops unavailable, stale and never-captured states
`ModeloDeclarationsListProjectionV1` (`src/cadrumo/application/modelo/declarations_list_operation.py:51`) carries only rows; the workspace zones' availability and the calendar sources' availability and observation times captured by `read_declaration_list_inputs` (`src/cadrumo/application/workbench_generation_reader.py:431`) are discarded, while the TUI shows them beside the same rows (`src/cadrumo/entrypoints/tui/declarations/portfolio_rendering.py:35`). With AEAT evidence never captured or a stale zone, the window would show a list that reads as a profile holding nothing, against the rule to preserve unavailable, stale, unknown and genuinely empty states. Reopens S07.

### header-classification | high | the header's counts, result view, deadline urgency and file view still live only in the TUI
`attention_chips`, `result_view` and `_selected_result`, `deadline_view` with its urgency thresholds, `deadline_help` and `file_view` (`src/cadrumo/entrypoints/tui/modelo/workbench/header.py:248`, `:372`, `:402`, `:467`) have no read-model field; the per-level counts exist only as functions (`src/cadrumo/application/modelo/work_form_next_step.py:135`) and the export-gate hint is carried nowhere. The prototype re-derives all of it (`Workspace.tsx:78`, `:175`, `:601`, `:692`; `Panels.tsx:66`, `:176`; `vocabulary.ts` dueWords, resultWords). P04.S19 would otherwise rebuild these rules in React or disagree with the TUI.

### list-row-classification | medium | list rows leave days remaining, group words and creation targets to the window
`ModeloDeclarationListRowV1` (`src/cadrumo/application/modelo/declarations_list.py:360`) carries the deadline but no days remaining, overdue or tone (the prototype counts days from the client clock, `DeclarationsHub.tsx:142`); the group words are a TUI table (`portfolio_rendering.py:20`); `creation_targets` (`src/cadrumo/application/modelo/declarations_workspace_contracts.py:283`) is not carried though the new-declaration dialog needs it. The prototype also offers AEAT-side steps (check, link, correction, verify for calculated rows) the read model does not state, and the matching catalogue keys are unreferenced.

### next-step-overlays | medium | the next step omits the retained apply prerequisite and a recorded filing without a receipt
The TUI forces resolve while an apply prerequisite is held (`src/cadrumo/entrypoints/tui/modelo/workbench/screen_next_step.py:250`), and the prototype offers adding the AEAT receipt until it is verified (`Workspace.tsx:124`); `form_next_step` and `ModeloWorkbenchFormReadV1.next_step` (`src/cadrumo/application/modelo/workbench_read.py:99`) know neither.

### standing-two-paths | medium | the stored standing has no validator and the TUI recomputes it
The builder stores `standing` for the window, but the TUI calls `field_needs_filer` itself (`casilla_list_models.py:134`, `page_items.py:249`, `vocabulary.py:321`); `revised_field` keeps a stale standing unless passed one (`src/cadrumo/application/modelo/work_form_models.py:481`), and the design-constant copy keeps its blockers (`work_form_layout.py:115`). They agree on present data and a parity test exists.

### design-constant-figure | low | a design-constant box holding its own figure now shows none
`field_value_text` returns nothing for any design constant (`src/cadrumo/application/modelo/work_form_wording.py:404`), narrower than its docstring; before `a88d4e0e72` such a non-rate value showed its figure. A scan of 54 real forms found no affected box, and the real-form test skips the case (`test_grid_tables_real.py:556`).

### typed-entry-details | low | the typed-entry path is sound; three small points
Typed text is excluded from every dump and representation and apply refuses it at intake and in its request. The apply refusal reuses the generic wrong-model code; parsed values stay in the preflight's encrypted result custody, as form reads do; an ambiguous-separator refusal echoes digits derived from the entry, by design.

### gate-agreement-test | low | the gate-agreement test checks reason sets, not the gates
`test_work_form_next_step.py:128` asserts against the refused-reason sets rather than driving the export and local-filing gates, and the registry-grade halt through the read is tested only through its helper.

### page-applicability-words | low | page applicability words are still chosen in the TUI
`does_not_apply_text` (`src/cadrumo/entrypoints/tui/modelo/workbench/wording.py:26`) picks its key by period kind; the window would repeat that choice.

### closure-as-recorded | low | any edit closure words the form as recorded
`worded_form` derives recorded from any edit closure (`work_form_wording.py:425`); the only closure today is recorded as filed, but a new one would silently switch to the filed wording.

Verified sound: the next-step ladder and missing-value count are identical to the removed TUI code; origin, editability and source wording are faithful moves; no TUI module re-exports a moved name; the public round trip covers the new fields; the list read is exact-profile with whole-profile consent and no commit action; neither relay names a definition, the runtime refuses definitions without a financial operand, and both relays drop or overwrite the input after sending; every moved catalogue key exists in all four languages. Not verified by the reviewer: the full TUI and Rust suites (relying on the ledger's results), the full type and Ruff gates, the S02 mutation claim, and a live end-to-end financial submit through the Rust relay to a worker.

## Recommendations

- list-availability-states: carry the zones' availability and the calendar sources' states, worded, on the list projection, and have the TUI read them (reopen S07).
- header-classification: project the attention counts, the result view, the deadline view (text and tone), the file view and the export-gate reason on the form read model, and switch the TUI header to them.
- list-row-classification: add days remaining with tone, group words and creation targets to the list; the read model states whether AEAT-side steps exist, and the TUI and window render that answer.
- next-step-overlays: fold the retained prerequisite and the receipt step into the next step, or record in the governing decision that frontends add them as they add apply.
- standing-two-paths: have the TUI read the stored standing, or validate it against origin and blockers.
- design-constant-figure: narrow the condition to an empty value, or correct the docstring, and test a design constant that holds a figure.
- typed-entry-details: give the apply refusal its own code, and record the encrypted retention of parsed values in the decision record.
- gate-agreement-test, page-applicability-words, closure-as-recorded: drive the real gates and the read in the test; project the applicability words; key the filed wording on the recorded closure itself.
