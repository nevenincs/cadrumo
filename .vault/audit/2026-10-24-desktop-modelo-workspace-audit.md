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

### form-offers-what-the-gate-refuses | medium | resolved: the form offered a file the export gate refused
Found while widening the gate-agreement test after the P01 follow-up steps: the form judged calculation notes by attention alone, so an unresolved working figure or a note naming no printed box read as worth checking and the file was offered, while `require_work_unit_calculation_unblocked` refused it. Resolved in `46f9e9219b` by keeping the gate as the authority: `gate_refuses` (`src/cadrumo/application/modelo/calculation_note_gate.py`) is the gate's one condition, each note carries `withholds_filing`, and the header's export hold, the next step and the issue lines read it; `test_work_form_gate_agreement.py` drives every stored note reason, a working figure and a no-box note through the real export and filing gates.

### aeat-reference-not-shown | low | the desktop omits the AEAT reference the TUI's technical toggle shows
The TUI's external filing details show `aeat_reference_id` behind a technical toggle (`src/cadrumo/entrypoints/tui/declarations/external_details.py`). The desktop's read-only view of a return only the AEAT holds shows the row's notes only, because the reference is declared `exclude=True` on `DeclarationsCalendarEntryRefV1` and the public list row also reaches MCP and the scenario fixtures. Carrying it would reverse that custody decision, so it is left as a known gap that needs its own decision.

### list-reads-filing-grade | medium | the declarations list reads an applicability-graded revision as unreadable
`declaration_summary` (`src/cadrumo/application/modelo/declaration_summary.py:84`) and the result-box reader (`src/cadrumo/entrypoints/workbench_generation_composition.py:162`) snapshot at the default FILING grade, so the 2026 Modelo 390 revision, which declares applicability grade, reads as "Could not be read" in the list while its form opens. Plan step P01.S42 routes both through `modelo_form_snapshot`, which reads the law-selected revision at its declared grade.

The plan-close review (P05.S29, 2026-10-24, independent opus lane, feature commits `1671c8dd7d` to `118aa04a65`) failed with the findings below.

### edit-request-bound | critical | Modelo 303 cannot be edited from the desktop, and 347 only just fits one entry
Every preflight and apply carries the whole admitted baseline in the financial-operand body, and the host refuses a body over `REQUEST_LIMIT` = 16,383 bytes (`native/desktop/src-tauri/src/agent/person.rs:20`, `native/desktop/src-tauri/src/shell/modelo/mod.rs:310`). On the real-producer envelopes the admitted baseline alone is 58,049 bytes for 303 (its `permitted_surface` 55,771), 15,936 for 347 and 7,564 for 130; renewal sends the baseline as a plain payload capped near `MAX_PAYLOAD_TEXT` = 12,288 (`native/application/src/person_operations.rs:48`). The TUI and CLI edit these modelos, so parity breaks. P03.S14 was closed on the reply bound only. Decided in the ADR's 2026-10-24 amendment: requests take the assembled-document bound. Reopens P03.S13, P03.S16, P04.S21 and P04.S22.

### mutation-paths-untested | high | No test exercises edit apply, stale renewal, export, recording, receipt or correction
The scenario host answers only the reads, renewal and one preflight; apply, export, file, reconcile and amend are unserved (`native/desktop/frontend/src/dev/modeloFixture.ts:255`), and no spec drives the review, filing or correction views. Reopens P05.S27.

### correction-outcomes | medium | The correction dialog folds committed, unknown, held and refused outcomes into one silent failure
`native/desktop/frontend/src/components/modelo/workspace/WorkspaceScreen.tsx:236` returns failed for anything but settled, including a committed-but-unread amendment, and `CorrectionDialog.tsx:107` shows nothing, inviting a second amendment.

### stale-rebase-divergence | medium | After a renewal the desktop re-checks staged edits by its own rule
The TUI's rebase drops changes whose box no longer accepts them and compares value and origin (`src/cadrumo/entrypoints/tui/modelo/workbench/session.py:218`); the desktop keeps every edit and compares the value text only (`dialogs/ReviewDialog.tsx:257`).

### admission-refusal-words | medium | The desktop drops the edit refusal's own words and infers rules incomplete from an empty next step
The TUI shows the admission refusal's words (`src/cadrumo/entrypoints/tui/modelo/workbench/factory.py:186`); the form projection carries none, and the window picks a key by whether a next step exists (`workspace/Workspace.tsx:298`, `details/TodoRail.tsx:64`).

### client-editability-set | medium | Whether a box takes typing is a hand copy of the application's set
`form/session.ts:214` restates `TYPED_EDITABILITIES` (`src/cadrumo/application/modelo/work_form_typing_effect.py:32`) with an extra rule, and stages an unchanged value the TUI drops.

### export-record-availability | medium | Which artefacts and whether recording is offered are decided separately in each frontend
`dialogs/FilingView.tsx:428` and the TUI's `screen_operation.py:69` hold their own rules and disagree under a verify hold; the server gates still refuse, so nothing unsafe is written.

### stored-subject-list | medium | The stored-subject definitions and the edit body limit are hand copies of host facts
`native/desktop/frontend/src/shell/modelo.ts:55` and `:73` restate the host's subject table and request limit.

### wipe-coverage | low | The wipe leaves numbers and the framework's raw body untouched
`person::wipe` zeroes strings only (`native/desktop/src-tauri/src/agent/person.rs:62`), and the raw invoke body is not copied into a zeroising buffer.

### create-saved-unread | low | A committed-but-unread creation shows as failed and does not re-read the list
`declarations/NewDeclarationDialog.tsx:175`.

### hand-written-presentation-lists | low | Several presentation tables restate closed sets
`form/ValueCell.tsx:40`, `workspace/CheckView.tsx:17`, `dialogs/FilingView.tsx:87`.

### record-drift | low | The decision and plan text no longer match what was built
The reply-parts constraint (now amended), P03.S14's note, and P01.S35's claim that the TUI history switched; only the CLI and the shared event table use the worded history.

### financial-submit-frame | critical | The relay's financial-operand submit could never reach the runtime
Found while fixing edit-request-bound: the relay action added in `1706f66723` sends a bare `operation_financial_input` document, which the runtime refuses as an invalid frame (`src/cadrumo_runtime/host/profile_connection_operations.py:164`); its tests passed against a scripted session holder, so no desktop edit preflight or apply could ever have been admitted live. P03.S43 moves the financial submit, and any plain submission too large for one frame, onto the runtime's existing streamed upload (`operation_submit_payload` header, `operation_payload_ready` acknowledgement naming the descriptor, then bounded secret frames), the path the Python client uses in `operation_transport.py`; the test must drive the real runtime's admission, not the scripted holder alone.

### history-stores-source-path | low | A receipt import's history event keeps the document's full path, which the history read hands out unreduced
`modelo.reconcile.import` records the justificante's `source_path` in the declaration's event history, and `modelo.work.history` returns it under a plain detail value; the desktop host cuts it to a file name before the window sees it, and the history model's validator then refuses that reduced value, so no history envelope is produced for the receipt shapes. A path is not persisted evidence: the event should record the document's digest and file name, and the history read should never return a local path to any client, including MCP. This predates the feature and needs its owner's change.

### hu-navigation-flake | low | One Hungarian scenario failed twice for one lane and never for another
"modelo 347-0A speaks hu" opened the Profile pane instead of the Declarations list for lane B, alone and in a full run, and passed 27 times for the proof lane on the same tree. The suspected cause is the Declarations rail action toggling a page that was already open; it stays a watch item until a trace reproduces it.

The re-review of the fix commits (`788d9231f0`, `f5a6e55f11`, `5da639c4ba`, `ddecebc18e`, independent opus lane, 2026-10-24) found edit-request-bound, financial-submit-frame, correction-outcomes, create-saved-unread, admission-refusal-words, client-editability-set, export-record-availability, stored-subject-list and record-drift resolved, wipe-coverage, mutation-paths-untested and stale-rebase-divergence partly resolved, and these new findings.

### renew-request-value-digest | high | The renewal request journals an unkeyed per-box digest of each staged box's value
`state_digest` is SHA-256 over origin, type and value with no key (`src/cadrumo/application/modelo/work_form_models.py:452`); the desktop sends it as `held_state` in `ModeloEditRenewRequest.staged` (`native/desktop/frontend/src/components/modelo/dialogs/useEditReview.ts:71`), and `modelo.edit.renew` is journaled credential-free (`_supervisor_submission.py:108`). A single amount's digest is reversible by enumeration, which `2026-08-24-modelo-edit-contract-adr` forbids in operation persistence. Reopens P01.S44 and P04.S46.

### desktop-rebase-restage | medium | The desktop keeps a kept edit staged against the old box after a renewal
The TUI re-stages each kept change against the renewed field and drops one now equal to the box's own value (`src/cadrumo/entrypoints/tui/modelo/workbench/session.py:228`); the desktop only removes dropped edits (`useEditReview.ts:182`), and its changed marks vanish on the next review.

### rebase-untested | medium | No spec renders a kept, changed or dropped renewal outcome
`renew-130.json` carries an empty rebase report and the scenario answers it whatever is staged, so "staged edits survive a renewal" would pass with the report ignored.

### live-edit-proof | medium | The live test cannot tell a staging refusal from an operation refusal for edits
`native/application/src/runtime_client.rs:2124` accepts `invalid` for preflight, apply and renew, which staging also answers for a malformed stream; no well-formed edit operand is admitted live.

### ledger-port-stale-bounds | medium | The ledger port restates the removed request-line and character bounds
`native/desktop/frontend/src/shell/ledger.ts:165` and `src/dev/ledgerFixture.ts:73` keep 12,032 characters and a 16,383-byte line; the ledger's to change, from host facts as the modelo port does.

### edit-limit-above-relay | low | An edit body the host accepts can exceed the relay's bound and end the session
`financial_body` and `MODELO_EDIT_BODY_LIMIT` use `REQUEST_LIMIT` (16 MiB + 64 KiB, `native/desktop/src-tauri/src/shell/modelo/mod.rs:307`) while the relay refuses an operand over 16 MiB with an ending refusal (`native/application/src/person_operations.rs:570`).

### fixture-host-reduction-copy | low | The fixtures reimplement the host's path reduction in Python
`modelo_fixtures.py` reads the host's keys but repeats the reduction; a Rust test should prove the host's own reduction yields the committed envelopes.

### raw-body-framework-copy | low | The framework's own copy of a raw invoke body is not wiped
`relay::wiped_body` (`native/desktop/src-tauri/src/shell/relay.rs:88`) copies the body into a zeroising buffer but cannot overwrite the framework's buffer; the decision record should state that bound.

### review-package-availability | low | The window still decides when the review package is ready
`FilingView.tsx:691` keys it on a verified calculation because the export offer does not list the package.

Verified sound by the plan-close review: the closed admitted list pinned to the manifest, exact-profile filling and subject binding, files as session tokens, unknown versus refused on every mutation path with no resend, no logging or web storage in the Modelo host and components, typed entries only through the edit port with the buffer zeroed, list, header, next step, issue lines, sources, AEAT notes and receipt from shared producers, theme-only styling, missing drawn as a dash, and the prototype's interaction design unchanged.

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
