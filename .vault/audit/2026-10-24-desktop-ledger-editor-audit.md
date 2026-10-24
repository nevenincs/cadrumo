---
tags:
  - '#audit'
  - '#desktop-ledger-editor'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:1430ef9d99d4401a0884abd5f0e5495ace61ec0a016caed8ef99a3ff39925f39'
related:
  - "[[2026-10-23-desktop-ledger-editor-plan]]"
  - "[[2026-10-23-desktop-ledger-editor-adr]]"
---

# `desktop-ledger-editor` audit: `Desktop Ledger editor: prototype reviews and binding interaction rulings`

## Scope

This audit covers the interactive prototype of the desktop Ledger editor, reviewed before the page is implemented (plan P03). The prototype is a standalone HTML page built from the app's real palette, tokens and conventions, with synthetic data. It was reviewed in two rounds by independent reviewers who drove it headlessly with keyboard and mouse:

- Round 1 used three lenses: adversarial, usability, and design system with accessibility.
- Round 2 verified the revision.

The reports, scripts and screenshots stayed in the session's scratch space. This record keeps the findings that were raised and the rulings that resolve them. The rulings bind the implementation, alongside `2026-10-23-desktop-ledger-editor-adr`.

## Findings

### Round 1 · adversarial | critical | the UI could make a person believe something false, and could send values to operations that ignore them

The review raised 3 critical, 12 high, 13 medium and 5 low findings. The critical ones:

- A cleared value was planned into the bulk classification, where a blank cell means "unchanged".
- A staged classification read "Reviewed" before anything was saved.
- Invoice quantities bypassed the number grammar.

The high findings covered:

- conflicting edits to the same row in one review;
- model approval recorded as a manual decision;
- permanent links staged in one click;
- fields routed to operations that don't accept them;
- invented defaults;
- outcome states that didn't match how the bulk saves;
- selection reaching rows the person can't see;
- paste rewriting identities;
- two different percent grammars;
- export ignoring staged changes;
- undo not rebased after apply;
- readiness recomputed locally.

### Round 1 · usability | critical | measured task walkthroughs found irreversible traps and slow bulk work

The review raised 3 critical, 10 high, 14 medium and 3 low findings. The critical ones:

- Matching offered every pair with the same amount, and a link can't be undone.
- "Set for all" changed rows hidden by a search.
- Export could write one format under another format's file name.

The high findings covered:

- a default import account;
- search confined to one period;
- no grouping by counterparty or description, estimated at about 600 inputs for 120 rows;
- readiness chips that didn't lead to the fix;
- a stale check time;
- the invoice drawer's default kind and focus;
- duplicate invoices on confirm;
- a review dialog that didn't scale;
- a tray limited to one section;
- no handling of duplicates at import.

### Round 1 · design system and accessibility | critical | state markers did not reach assistive technology

The review raised 1 critical, 8 high, 8 medium and 1 low findings. The critical one: changed, refused, locked, model and outcome markers existed only as tooltips. The high findings were:

- shell-owned chords taken by the grid;
- a drawer that claimed to be modal but wasn't;
- implementation names in ordinary prompts;
- no forced-colours rules;
- lifecycle state shown by tint alone;
- faint text failing contrast on tinted rows;
- too little fitting at 1280 and 1440;
- a grid keyboard model that diverged from the ARIA grid pattern.

### Round 2 · verification | high | revision 1 fixed most findings but left eight design gaps

The verdict was conditional go. The gaps the implementer must not decide:

- M1: guarding permanent links.
- M2: the keyboard map (bare-letter shortcuts ate typing).
- M3: readiness pill semantics.
- M4: one classify-selection command for every route.
- M5: model approval that shows what it writes.
- M6: the right-hand panel and the inspector index.
- M7: invoice number suggestion per series.
- M8: one counting unit.

Revision 2 resolved all eight. The prototype then passed 51 regression checks and an axe audit of 162 light and dark contexts with no violations.

### Owner corrections during review | high | period selection and succinctness

The owner made three corrections during the reviews:

- A ledger can go back decades, so no year control may be a fixed toggle.
- An over-built year field and decade grid were rejected in favour of one simple dropdown with navigation buttons.
- The interface must be succinct, showing glyphs and counts rather than sentences.

## Recommendations

The following rulings bind the Ledger page's implementation. Revision 1 comes first (R1 to R22, with R21 as revised). Revision 2 follows (M1 to M8 and the listed medium and low items), and it amends revision 1 where they differ: M3 amends R1 on readiness and staged changes.

### Revision 1 rulings

#### R1. Truth on screen
- The grid, the status cell, the inspector header, the strip and every count show stored state only (ADV-02). A staged row carries an unsaved marker: a dashed 2px leading bar in ink, distinct from the brand selection edge, plus the text "→ Business · not saved". The marker is ink, not the warning tone; DS-12 holds that a staged edit is not a problem. Add a "Has unsaved changes" filter and a "12 of 32 staged" progress note (U decision 1).
- Readiness is frozen at the last check. After an apply, or while changes are staged, the strip says "Out of date · 12 changes since 10:41 · Check again". Checking again updates the time, and a check also runs automatically after each apply (ADV-15, U-08).
- Status vocabulary (U-19):

  | Stored state | Shown as |
  | --- | --- |
  | pending | To classify |
  | reviewed, with issues | Needs fixing · n |
  | reviewed, no issues | Done |
  | skipped | Skipped by rule |
  | excluded | Excluded |

  Lifecycle shows as its own neutral badge: Archived, Set aside or Split (DS-06). Pending gets the `circle` glyph. `circle-dashed` is reserved for unknown and not-measured states. No-rate uses `circle-off`, and `ban` is reserved for refused (DS-12, ADV-19).
- Sealed states use their real words: "Verified (sealed)", "Filed locally · AEAT status not confirmed", "Filed · receipt confirmed" and "Superseded" (ADV-18).

#### R2. Routing by operation (ADV-01, ADV-07, ADV-04)
Put one table in the model that lists which fields each operation accepts. Route every staged value by that table and by whether it sets or clears:

| Operation | Use it for |
| --- | --- |
| `ledger.classify.bulk` | Setting classification, category, business share, usage ratio, base, rate, IVA amount, IVA category, IRPF category and notes on rows that are, or will be, Business, Personal or Mixed. It never carries a clear. |
| `ledger.classify` (single, field mask) | Setting or clearing the VAT-identification state, counterparty country, deduction fact kind and investment asset. Clearing category, IVA category or business share on a classified row. M210 fields. |
| `ledger.update` (single, field mask) | Description, dates, amount, direction, currency, counterparty, group label and own account. Setting or clearing base, rate, IVA amount or IRPF category on an unclassified row, and clearing them on any row. Replacing notes. |
| Lifecycle, link, attach/detach, split, merge, remove | Each through its own operation. |

- Each row is checked for conflicts against its effective staged state before it is sent:
  - A transfer combined with a tax field, or with any classification other than Personal or unclassified, is a blocker.
  - A lifecycle or structural action combined with an edit to the same row is a blocker, resolved by "Drop the edits" or "Drop the action".
  - Exclude combined with a classification is a blocker.
- `lockReason` is evaluated against the staged row.
- Order of work for one row: classification, then corrections, then link and attach, then lifecycle and structural actions.
- Across rows: the bulk parts go first, then single classify calls, then corrections, then adds, then actions.
- The plan is described in plain words, with operation ids only under "Technical details" (DS-04, U-11, U-20). Example: "92 movements saved together · 40 saved one at a time (about 2 minutes) · 2 new movements".
- The bulk is one revision-guarded save per part. Each part shows one spinner, then its per-row results. Two batch-level states are designed:
  - "Not saved: the ledger changed while saving. Nothing in this part was saved." The changes stay staged, with a Re-read action.
  - "Outcome unknown". Writes pause.
- An "unchanged" row re-reads and shows its stored value before its staged change is dropped (ADV-09).
- Starting an apply clears the undo history except for refused and not-sent changes. After an apply, Ctrl+Z explains that applied changes cannot be undone here (ADV-14).
- At apply, the period is re-read. Every staged row's `modified_at` and id are compared; a mismatch shows the old stored value, the new stored value and the staged value, offers "Keep mine" or "Take theirs", and needs an acknowledgement. Rows that were removed or moved elsewhere are flagged (ADV-17, U decision 6).

#### R3. One number and date grammar (ADV-03, ADV-12)
- Amounts, prices and quantities go through the canonical parser: dot decimal, no grouping, no exponent, refusals echo the raw value. Amounts allow 2 decimals, quantities up to 6 decimals, and unit prices up to 6.
- Percent fields (IVA rate, business share, usage ratio, retención) all use one percent grammar. Typed and pasted values mean the same thing: `50` means 50%, a bare value between 0 and 1 is refused with "Write 50 for 50%", and copying emits `50%`.
- The grid shows dates without a year only when the window sits inside one calendar year. Otherwise it shows the year, and so does every before → after line (ADV-26, U-24).

#### R4. No invented defaults (ADV-08, U-04, U-09)
- Add movement starts with direction and account empty. "Unbound" is offered under the label "No account".
- Counterparty country shows "Not stated" until someone states it. Source jurisdiction is its own field.
- Import has no default account. The account is set per file in the preview and labelled "detected from the file" when the provider or IBAN identifies it; otherwise the person must choose.
- Document direction has no default unless the context implies it. Invoice Kind has no default; the editor opens with "Invoice I issued" / "Invoice I received".
- "New invoice from this movement" leaves the line rate on "Choose a rate" and the price blank, and shows the movement amount as a hint.
- Dates are always asked for: account opened on and closed on.
- A Mixed suggestion that has no share is refused until a share is entered.

#### R5. Model suggestions are reviews (ADV-05)
- A suggestion is the pending review of `ledger.classify.review`. Apply answers it with approve, bound to the shown review's digest, and it is recorded as "Model · llm:<model> · approved by you". Reject records a rejection with a required reason.
- Suggestions are in the tray as their own kind, and the history names the model.
- "Ask the model for each" runs one review per movement. The review lists the suggestions one at a time, so they can be approved together after they have been read.

#### R6. Links are permanent (ADV-06, U-01)
- Suggestions are assigned one-to-one and ranked by: invoice number found in the description, then the shortest issue-to-payment gap, then counterparty, then amount.
- Each movement shows its one best suggestion, with "Other candidates (n)" behind it.
- When candidates tie, the suggestion carries an Ambiguous badge and opens a chooser instead of a single Link button.
- Scores are replaced by evidence chips: "Number in description" and "Paid 2 days after issue". Each suggestion shows the invoice date and payment status.
- Staging a link removes every competing suggestion that uses the same invoice or movement.
- The review has a "Permanent" section with a lock: "A link cannot be removed later", and a confirmation tick for each link.
- The advice about wrong links tells the truth: there is no way to remove a link here.
- A link whose outcome is unknown is never retried before the period is re-read.

#### R7. Selection and paste safety (ADV-10, ADV-11, U-02)
- The header checkbox replaces the selection with the visible rows; Ctrl-click adds them to it.
- When some selected rows are hidden, a warning bar says "2 of 6 selected are hidden · Show them · Keep only visible", and bulk set buttons are labelled "Set for 4 visible + 2 hidden". When none of the selected rows is visible, bulk set is disabled until the person chooses.
- A multi-row paste, or any paste that touches an identity column, opens a preview first. The preview names the target columns and counts the cells changed, refused, dropped past the end, and the movements that will get a new identity. Its actions are Paste and Cancel.
- A pasted blank means unchanged; only Delete clears.
- Tabs and newlines in single-line fields, and unclosed quotes, are refused.

#### R8. Grouping, bulk speed and rules (U-06, U-21, U-23)
- Add grouping by Counterparty and by normalised Description (digits and references stripped). The Needs review view groups by counterparty by default.
- Group headers carry quick actions:
  - Business ▾ (with category), Personal, Mixed…
  - Category ▾
  - Make a rule from this group
- In the multi-selection inspector, every field applies when chosen. The share field sits inline with Mixed.
- Counts state what is skipped: "Set for 276 (64 sealed skipped)". A change that would create more than 10 single writes shows the cost and offers to classify first.
- Tax fields are skipped on Personal rows.
- Setting Business in bulk asks for a category in the same step.
- A rule from a selection or a group opens as a dialog over the grid. It can match on counterparty, on description contains (plain words, with an Advanced regex toggle) or on an amount range. It is prefilled from common values, and offers "matches 14 · also classify them now (staged)". Order replaces the priority number.
- Applying rules is staged like every other write.

#### R9. Readiness that leads to the fix (U-07)
- A reason chip filters the grid, switches to the right column preset, marks the missing cells and opens the inspector on Classification.
- Each reason has its own fix action: Derive figures, Set category, Set share, or "Set afectación in Profile ›".
- `N` moves to the next issue.
- Chips wrap or end with "+n more". "32 to classify" is a chip of its own (ADV-33).

#### R10. Information architecture (U-26)
- Primary section tabs: **Movements**, **Invoices**, **Documents**. A "Setup ▾" menu holds **Rules**, **Registers** and **Health**.
- Matching becomes:
  - a "To match" saved view on Movements, with a Match column that shows the best suggestion;
  - an "Unmatched" filter on Invoices;
  - the Invoice section of the inspector.
- The pair queue stays reachable as the "To match" view's side list.
- The inspector is one scroll with a sticky section index, in this order: Classification (first), Documents, Invoice, Details, History and Used in. Actions move to a ⋯ menu in the inspector header.
  - Pending rows open on Classification.
  - Closing returns focus to the active cell. Alt+I opens the inspector and focuses its index (DS-10).
- "Used in" links to the declaration ("Open in Declarations ›"). A date change that moves a row to another quarter says "Moves to 2026 3T · affects Modelo 303 3T" (U-24).

#### R11. The tray, apply and leaving the page (U-12, ADV-16, U-27, U-29)
- The tray is page-wide, on every section. Matching links, rule applies and inspector edits all stage into it.
- Leaving the page, signing out, switching profile or closing the window with staged work asks first: Review and save · Discard · Cancel. At 50 or more staged changes, the tray suggests saving in parts.
- Tray wording: "4 edits on 1 movement · not saved yet". The "only in this window" note moves into a tooltip and into the leave guard.
- An unknown outcome leaves a persistent alert after a re-read: "was saved" or "was not saved, staged again". The row's history records it.
- Per-row × in the review; Revert cell (Ctrl+Alt+Z) and Revert movement in the context menu and the inspector (U-14).
- An "unknown" add keeps its draft and its key. An unknown link or export is never retried before a re-read (ADV-28).

#### R12. Import, export and documents (U-03, U-13, ADV-13, ADV-27, U-10, U-25)
- **Import preview duplicates.** The contract imports likely duplicates and flags them; there is no skip. The preview shows each duplicate next to the existing movement, in a popover inside the dialog, and says it will be imported and flagged. After the import:
  - duplicates carry a "Possible duplicate" marker in the status cell, with "Archive as duplicate" and "Keep both";
  - "Show imported" shows the batch's own date span.
- **Import flow.** When nothing is new, the preview says "Nothing new to import" and disables Apply. Focus moves to each step's heading or primary action, and after "Show imported" to the first imported row (U-17).
- **Export.**
  - The destination is the last step. Changing the format or period clears it.
  - Only file names are shown, never folders.
  - It warns when the period isn't ready or changes are staged, offering "Review and save" or "Export without them".
  - It explains what the count excludes and remembers the last format.
  - It offers "Also copy invoices (TSV)" and lists every year with movements.
- **Documents.** Before confirming, check the invoice number, NIF and total against the catalogue: "Already in the catalogue: attach this PDF to it, or confirm anyway". After confirming, offer the matching movement link. Field provenance uses plain words, for example "Read from the PDF, totals agree".

#### R13. Invoice editor (DS-03, U-09, U-15)
- The editor is a modal Sheet (right side, scrim, focus trap, Escape) that focuses its first field.
- Retención amount is computed from the rate and stays editable. The panel shows "To be paid 1,166.00 (− 165.00 retención)", with rate chips for 15%, 7% and 19%.
- The editor suggests the next number in the series. Issued lines don't show expense categories.
- Payment status and payment id are editable (ADV-23).

#### R14. Split (U-16)
- The remainder fills in automatically. Each part can be classified in the dialog, including its category; that classification is staged to run after the split. The reason is optional.
- The parent shows as Split, with its parts nested under it.
- A hint offers the alternative: "Partly used for work? Use Mixed with a share instead."

#### R15. Search (U-05)
- Words match separately. Search also matches months, amounts written either way (`36.30` / `36,30`), notes and invoice numbers.
- A period-scoped result ends with "3 more in other periods → Show".
- A partial window says "5 found in the 200 loaded · Load all 340".

#### R16. Accessibility and keyboard (DS-01, DS-02, DS-09, DS-11, DS-17, U-18)
- **State announcements.**
  - Each row has a hidden status description, referenced by its cells through `aria-describedby`.
  - Changed cells add "changed, was …". Refused cells set `aria-invalid` and announce the reason. Locked cells keep `aria-readonly` and announce the reason.
  - Moving the active cell is announced in a polite live region.
- **Chords.** Every chord matches its exact modifiers. Shell chords pass through, tested by dispatch. The page has no Ctrl+K of its own: its actions register with the shell palette, which the prototype shows as the shell's own palette.
- **Grid keys.**
  - In navigation, Tab leaves the grid. While editing, Tab commits and moves right in every editor.
  - Headers can be reached: ArrowUp from the first row moves to them. On a header, Enter or Space sorts, Ctrl+Left/Right reorders and Alt+Left/Right resizes.
  - The column chooser has move up and move down. The inspector resizes through the ResizeHandle pattern, with `aria-valuenow`.
- **Comboboxes.** They are named, families are groups, and the hint and error are linked through `aria-describedby`.
- **Truncated text.** Shows a tooltip on hover and focus. The inspector, the review and group headers wrap instead of truncating.

#### R17. Visual system (DS-05, DS-07, DS-08, DS-12, DS-13, DS-14, DS-16, DS-18)
- **Forced colours.** Add rules for the selected row, the selection edge, classification marks (drawn as borders), primary buttons, the chosen tab and segment, and overlay edges.
- **Contrast.** Use muted text, not faint, on selected, in-range and wash surfaces. Show a range as an inset ink outline. Refused text uses the foreground colour, with a destructive edge. The ring on an unfocused active cell is muted.
- **Density.**

  | Column | Width |
  | --- | --- |
  | Status | 7.5rem |
  | Date | 4.5rem |
  | Description | flex 2, minimum 12rem |
  | Counterparty | flex 1.5, minimum 9rem |
  | Direction | 5rem |
  | Amount | 6.5rem, sticky |
  | Classification | 8rem |

  - The inspector is 20rem below 1440 px.
  - Header tabs scroll with a cue. Import and Export collapse to icon buttons when space is short.
- **Tokens.**
  - `--layer-popover` becomes 55. No `--layer-popover-modal`, no `--layer-proto`.
  - Grid-local layers under `isolation:isolate`: `--layer-grid-sticky` 1, `--layer-grid-head` 2, `--layer-grid-head-sticky` 3 and `--layer-grid-editor` 4.
  - `--elevation-docked` for the tray.
  - Dialog widths `--spacing-dialog-md` 32rem, `--spacing-dialog-lg` 46rem and `--spacing-dialog-xl` 60rem. Sheet width `--spacing-sheet` 44rem.
  - `--inspector-w` 20rem and `--inspector-min` 17.5rem.
  - Row heights alias the control-height tokens, and `--mark-edge` replaces the 1.5px edges.
  - Everything else uses existing utilities.
- **Icons.** Prune to the DS-14 list.
- **Pane header.** It composes the PaneHeaderFrame pattern: a children slot between the title and the controls, a `div` and not a nested `<header>`, and the maximize control kept.
- **Small fixes.**
  - Tab counts become separate labelled badges, so "Movements32" no longer reads as one word.
  - The rail shows no red count. If it shows one, it is a neutral pill with a full name.
  - Chord hints sit in tooltips, and `aria-keyshortcuts` is set.
  - Dates use tabular figures.
  - Action columns get sr-only headers. Scroll regions can be focused.
  - Scheme switching uses `data-scheme`. The danger zone is a section variant.

#### R18. Copy (U-20)
Plain words everywhere, as listed in U-20, using the user's own words for things. Operation ids, idempotency keys and digests appear only under "Technical details". The labels are:

| Instead of | Use |
| --- | --- |
| Stash | Set aside |
| Preflight | What's still missing |
| Participation index | Declaration links |
| Lifecycle | State |
| Apply n operations | Save n changes |

#### R19. Phone width (U-22)
Below 760px, Movements uses cards: description, amount with direction, and a classification chip that opens a sheet. The section tabs become a select. Shortcut hints are hidden on touch.

#### R20. First run (U-28)
An empty ledger shows a checklist: register your accounts, import a statement, then review what the rules caught.

#### R21. Period selector: one simple dropdown, any year (owner, 2026-10-24, revised)
A ledger can go back decades, so no control may be limited to a fixed set of years. The selector must still be simple. The owner rejected the year-field, decade-grid and "±1 / ±10" design as overly complicated: moving between years is navigation, not arithmetic.

- **The control.** One dropdown button showing the current period, for example `2026 · 3T ▾`, flanked by `‹` and `›` buttons that step to the previous or next period at the same granularity, crossing year boundaries (1T 2026 ‹ 4T 2025).
- **The dropdown.**
  - First row: `‹  2026  ›`. These are navigation buttons that move the year shown in the dropdown, with no lower or upper limit inside the period grammar.
  - Below it: Year · 1T 2T 3T 4T · the twelve months as a compact grid · and "All periods" set apart.
  - Choosing an item applies it and closes the dropdown.
- **What is not in it.** No typed year field, no help text about keys or ranges, no decade grid, no "No movements" cells, no per-year counts.
- **Long jumps.** A plain list of the years that have movements sits at the bottom of the dropdown, as one compact row of year buttons. It wraps or scrolls, and its words are only "Years with movements". Choosing one jumps the dropdown to that year. This list comes from the data, never from a fixed range.
- **Keyboard.** The `‹` and `›` buttons and every item are focusable. Arrow keys move between items in the grid. Escape closes the dropdown and returns focus to the trigger.
- **Where it applies.** The page header, Export, Health, the import period, the ratios year, the prorrata ejercicio and the inventory year all use the same component. Year-only places, such as the ratios year, hide the period part.
- **Fixtures.** The synthetic data keeps rows in earlier years (2003, 2011, 2019, 2024, 2025) so that navigation is exercised.

#### R22. Succinct by default (owner, 2026-10-24)
Say it with a glyph and a number wherever that is unambiguous. Put the words in the tooltip and the accessible name, not in the chrome.

**Example.** "Ready for calculation: No · 43 movements to fix" becomes a warning pill reading `[!] 43`.
- Its tooltip and accessible name: "Not ready for calculation · 43 movements to fix".
- Clicking it filters the grid to those movements.
- When the period is ready, it becomes a success pill reading `[✓]`, with the tooltip "Ready for calculation · checked 10:41".
- When readiness is out of date or not yet measured, it becomes a muted pill reading `[◌]` (`circle-dashed`), with the tooltip "Not checked since 12 changes".

**Rules**

| Element | Show | Words go in |
| --- | --- | --- |
| Readiness strip | One pill per state: glyph + count. Reasons: one chip each, short noun plus count, e.g. "Category 5", "IVA rate 3". | The strip carries no sentence. The time shows only in the tooltip. |
| Section tab counts | A count badge, e.g. `Movements 32`. | The tooltip says what it counts: "32 to classify". |
| Status cell | Glyph, plus the count where there is one. | The word is visible only in the comfortable density; always in the accessible name. |
| Lock, model and outcome markers | Glyph only. | Tooltip and row description. |
| Changes tray | "12 · Review" at rest. | Expanding it shows counts by kind. |
| Toolbar buttons | Icons wherever the icon is conventional (search, filter, group, sort, columns, density, export, import), with tooltips and shortcuts. "Review & apply" and "Add" keep their text. | Tooltips and shortcut hints. |
| Inspector | Field labels, kept short. | Help text sits behind an info icon, not inline. |
| Review dialog | Leads with a one-line summary of counts. | Details expand per kind. |
| Empty and error states | Short: one line plus one action. | |

- **Never lose meaning:**
  - Every glyph-only control or marker has an accessible name and a tooltip.
  - No glyph means two things (DS-12).
  - Destructive or irreversible actions still say what they do in words: "Remove", "Link · permanent".
- **Copy budget:**
  - Banners: at most 8 words plus an action.
  - Pill and chip labels: at most 2 words.
  - Prefer numbers over sentences.

### Revision 2 rulings

#### M1. Permanent links are guarded (V-01, V-19, V-20)
- **Picker.** The manual link picker sorts candidates into "Settles this amount" and "Other invoices".
  - An invoice staged for another movement is shown disabled: "staged for REPSOL E.S. AV. CORTES".
  - An invoice already linked to other movements is still offered, because one invoice may settle several movements (partial payments). It shows "already linked to 1 movement".
- **Permanent rows in the review.** Each row shows both sides, for example `72.60 · Arroyo Asesores SL · 5 Oct 2026 ↔ GT-2026-0917 · 1,548.80 · Imprenta Gráficas Turia SL · 17 Sep 2026`.
  - Mismatch chips: "Amount differs by 1,476.20", "Different counterparty", "Invoice also linked elsewhere".
  - A row with any mismatch needs a second tick, "I know they differ", before Save is enabled.
- **Copy.**
  - Ambiguous case: "Usually one movement settles one invoice. Link both only for partial payments."
  - Every link button: "Link · permanent". Toast: "Link staged · permanent once saved".
  - A rival row: "T-0412-33 is staged for REPSOL E.S. AV. CORTES · Show it".

#### M2. Keyboard map (V-02, V-04, V-30)
- In the grid, printable keys always start editing. No bare-letter shortcut exists on the grid or anywhere on the page.
- **Shortcuts.**
  - F8 goes to the next readiness issue and Shift+F8 to the previous one.
  - Alt+B, Alt+P and Alt+M classify the selection as Business, Personal or Mixed, through the M4 command.
  - None of these is a shell chord. Re-check them against `App.tsx`'s chord list during implementation.
- **Alt+I** is handled once, at page level:
  - inspector closed: open it and focus its index;
  - focus inside the inspector: close it and return focus to the active cell;
  - inspector open with focus in the grid: move focus to the index.
- The shell keeps its capture-phase chord listener. Cell editors never stop a shell chord, and a test asserts this while an editor is open.
- The shortcuts sheet and `aria-keyshortcuts` follow this map.

#### M3. Readiness pills (V-03, V-14, V-31; R22 stands)
The owner's R22 example decides: glyph and count, no visible label. The full sentence goes in the tooltip and the accessible name, so the reviewer's two-word labels are not adopted. The three pills each count a different thing, and each filters to exactly the set it counts:

| Pill | Counts | Hidden when |
| --- | --- | --- |
| `⚠ n` | movements with a readiness issue other than "to classify" | n is 0 |
| `○ n` | movements to classify | n is 0 |
| `⊘ n` | movements without an EUR rate | n is 0 |

- When every count is 0 and the check is current, the strip shows a single `✓`. When nothing has been checked, it shows `◌`.
- Staged progress is not a separate pill. It shows as a small "n staged" line inside the `○` pill's tooltip. In the pill it is drawn as a thin fill of the pill's track, which carries no text.
- **Readiness and staged changes (V-31; amends R1).** Readiness describes stored data, so staged changes do not make it "out of date". The `⚠` and `○` tooltips end with "· n unsaved changes not included". The muted `◌` appears only when stored data changed since the last check. After each save, a check runs automatically.

#### M4. One classify-selection command (V-06, V-29, V-23)
- `classifySelection(kind)` is the only route. The inspector segments, Alt+B/P/M, the palette entries and the group-header buttons all call it.
- When some selected rows are hidden, it is disabled with the reason "2 of 3 selected are hidden · Show them · Keep only visible". The palette shows that reason. When the window is partial, it says "loaded rows only".
- Business always asks for a category, in one step. Mixed always asks for a share.
- It is disabled on transfer rows and groups, with a reason.
- Toast: "Business · Software subscriptions · 14 movements staged".

#### M5. Model approval shows what it writes (V-07, V-32)
- In the review, an approval row lists each field it writes, before and after: classification, share, category, IVA category.
- Figures derived from registry rates (base, rate, IVA) are separate staged corrections. They are labelled "worked out by Cadrumo", routed by R2, and marked as changed in the inspector.
- A Mixed approval without a share is held: "Enter a share to approve". It is never saved with the share empty.
- In the inspector, the Model suggestion block is one split button, "Ask the model ▾" (Classification · With IVA figures · Suggest a split), with the ⓘ inline on the heading.

#### M6. The right-hand panel and the inspector index (V-08, V-15)
- **The right-hand panel** has two modes: "To match" (the pair queue) and "Movement" (the inspector). Choosing a pair opens that movement's Invoice section in the same panel, so only one side panel is open at a time. The Match column comes right after Amount, and the grid keeps at least 40rem.
- **The inspector** is one scroll with a sticky jump index. The index has five entries: Classify, Documents, Invoice, Details, History. History includes "Used in" as a subsection.
  - The index uses scroll-spy, with `aria-current="location"` and a muted underline on the current section.
  - If it doesn't fit, the last entries collapse into "More ▾". It is never clipped.

#### M7. Invoice number suggestion (V-10)
- **Basis.** The suggestion is computed within the series and class: the highest numeric suffix, in the issue year, of the Series field's series, or of the most used ordinary series when Series is blank. Its zero padding is kept.
- **Wording.** "Next in series F: F-2026-021 · Use".
- **Rectificativas.** No suggestion is offered until a series is chosen.

#### M8. One counting unit (V-13, V-09)
- The tray, the review title and the Save button all count the same unit: movements changed, plus actions, plus new movements. For example: "10 · Review", then "Save 8 · 2 held back".
- Edit counts appear only in the tray's tooltip and its expanded line: "15 edits on 9 movements · 1 new".
- The staged progress in the `○` pill counts only movements to classify whose staged change sets a classification or approves one.

#### Also apply in this revision (medium and low)
- V-05: use the Combobox primitive in the inspector, and return focus after a commit.
- V-11: keep undo for changes that weren't saved.
- V-12: ask about a conflict only when both sides changed the same field.
- V-16: a readiness chip replaces the selection.
- V-17: confirm before discarding an invoice in progress.
- V-18: one overlay rectangle for a range, and forced-colours frames.
- V-21: no date or currency defaults.
- V-22: the leave guard covers shell navigation (state where it registers) and window close.
- V-24: a quarter move names the declaration it affects.
- V-25: rules have display names.
- V-26: the identity-change mark gets its own glyph.
- V-27: the date editor gets enough width.
- V-28: accessible names contain no glyphs; tooltips give the value and shortcut; badges say what they count.
- V-33: copy fixes.

## Phase-close review: P01 (host channel) and P02 (grid primitive), 2026-10-24

The review covered commits a573a74940..434aaab711 and d2dc93f4b2 (P01), and 17bb7ce7d8..39bb1d1cd9 (P02). It checked them against `2026-10-23-desktop-ledger-editor-adr`, the shell, capabilities and design-system ADRs, and the rulings above. **Verdict: P01 fails, so P01.S01 and P01.S02 are reopened. P02 passes with medium findings.**

### P01 · unknown-relay-unavailable | high | a mutation the runtime may have taken is reported as refused when the relay answers "unavailable"

- **Where:** `native/desktop/src-tauri/src/shell/relay.rs:135-148` and `native/desktop/src-tauri/src/shell/ledger/mod.rs:563-571, 648-650`.
- **What happens:** the native relay turns a lost or late reply after submit, start or respond into `operation_refused` with code `unavailable` (`native/application/src/person_operations.rs:381-396`). The host treats that refusal as final, and the page shows a refusal without pausing writes.
- **Fix:** for mutations, map relay `unavailable` to `unknown` and carry the operation id. Add tests for submit and for respond.

### P01 · unknown-after-settle | high | a settled write is reported as never sent when the post-settle session recheck fails

- **Where:** `native/desktop/src-tauri/src/shell/ledger/mod.rs:829` (`still_holding` after settle).
- **What happens:** the post-settle recheck can fail with `not_signed_in` or `unavailable`. These codes carry no operation id, and the page maps them to "not sent".
- **Fix:** for mutations, a failed recheck becomes `unknown` with the operation id, and the result is dropped. Reads keep the disclosure guard.

### P01 · result-path-source-name | high | `ledger.evidence.batch` results can pass the full local path to the window

- **Where:** `native/desktop/src-tauri/src/shell/ledger/mod.rs:363-419`. The path comes from `unresolved[].source_name`, built with `str(path)` at `src/cadrumo/application/ledger/batch_ingest.py:787`.
- **What happens:** the key-based reduction does not list `source_name`. It also does not cover refusal-detail `context` values, `precondition_verdict_json`, or review documents.
- **Fix:** replace each path substituted for the submission, and its parent folder, with its file name in every string of the result, the refusal detail and the review document. Add `source_name` to the reduced keys.

### P01 · own-account-wipe-native | high | the own account's IBAN and bank block are copied unwiped inside the host process by the native relay

- **Where:** `native/application/src/person_operations.rs:533` builds a plain `String`, and `:1500-1509` sends it with `exchange`, not `exchange_wiping`.
- **Owner:** the native sign-in feature, CADRUMO-RUST-NATIVE, which has been asked to apply the fix.
- **Fix:** hold the payload in `Zeroizing<String>` and send it with `exchange_wiping`. Add a test that asserts the overwrite.

### P01 · relay-bound-pin | medium | the host's payload bound is pinned to the retired Python relay, not the native one it now feeds

- **Fix:** assert `PAYLOAD_LIMIT + PAYLOAD_HEADROOM == person_operations::MAX_PAYLOAD_TEXT` in Rust.

### Plan · plan-coverage-links | medium | the plan's `related:` omits the ADRs its Description names as governing

- **Fix:** link the design-system, shell, capabilities and ledger data-contract ADRs.

### P02 · grid-shell-chords-copy | medium | the grid keeps its own frozen copy of the shell's chords, and its test asserts that copy

- **Fix:** the shell supplies the shell-chord predicate from its action registry, and the test uses the real registry.

### P02 · grid-altgr-chords | medium | Ctrl+Alt+letter opens an editor on Windows, swallowing Revert cell (R11)

- **Fix:** treat Ctrl+Alt as text only when it produces a character other than the key's own letter, or when AltGraph is held.

### P02 · grid-select-all-r7 | medium | the header checkbox cannot add the visible rows to the selection

- **Fix:** without a modifier, replace the selection; with a modifier, add to it. Test both.

### P01 · scenario-host-fidelity | low | the scenario ledger is looser than the host in three places

- It does not use the host's write/read classes.
- It does not apply the host's character and line-byte bounds.
- It refuses to observe a write whose outcome is unknown.

### P02 · lower-points | low | four smaller items

- No test checks that shell chords still work while a cell editor is open.
- The combobox keeps a stale `enter` press.
- The position phrase counts section rows.
- 434aaab711 has no ledger row.

**Verified by the review:**
- Admission of the closed 87-id list.
- Digest-bound review answers.
- Unknown on lost replies and timeouts.
- Size bounds.
- Session-bound file tokens.
- Secret-only raw bodies on the host side.
- No values in logs.
- Matching TS and Rust shapes.
- The product bundle boundary.
- Grid keyboard, ARIA, windowing, sticky columns, forced colours and tokens, per R16 and R17.

## P03 phase-close review, 2026-10-24

Revision required: 2 high, 4 medium and 5 low findings, none critical. Scope: base a88d4e0e72 to 2ee7b77c63. The two highs reopen P03.S09 (apply runner and the page-wide pause), P03.S14 (Setup writes) and P03.S18 (the plan model). Verified by the review: the plan links every governing ADR; `ledgerApply.ts` chains split-part classifications and the attach after `ledger.evidence.add`; no ledger value reaches storage or logs; data is dropped on profile change and sign-out; ESLint passes over the ledger, shell and grid files.

### P03 · setup-unknown-not-held | high | Setup writes are not held after an unknown outcome, `saved_unread` is reported as a failure, and the pause is not page-wide

Scenario: in Registers › Assets, the person submits `ledger.actividad-asset.create` and the relay answers `unknown`. The pane shows the warning line, but the submit button is enabled again with the same revision document in the form. A second click sends the same create, with no re-read in between. The same happens with Rule › Save (`ledger.rule.add`), Inventory create and movement add, Prorrata, Capital goods, Counterparties and Ratios.

If the host answers `saved_unread` (the write committed but its result could not be read, src-tauri/src/shell/settle.rs:309-315), `callFailure` turns it into `failed`. The person reads "failed" for a write that saved, and is invited to send it again.

The pause is also per surface. An unknown outcome in the staged apply disables only the tray’s Review. Invoices, Import, Documents and Setup keep writing, because LedgerPage hands none of them the pause. For example, while an unknown `ledger.link` to invoice X is paused, Invoices › Remove X is still offered.

The ADR requires: "never retried automatically; the page pauses writes until it re-reads".

Evidence:
- `native/desktop/frontend/src/components/ledger/setup/setupModel.ts:60-68`: only `unknown` maps to unknown.
- `setup/SetupParts.tsx:437-455`: `useSetupWrite.run` clears `last` and holds nothing after an unknown.
- `setup/RuleDialog.tsx:171-177`: `ready` ignores `saved?.kind`.
- `setup/AssetsPane.tsx:361`: the submit is gated only on `!ready || write.busy`.
- `components/ledger/LedgerPage.tsx:465-518`: the sections get no pause.
- `editing/useLedgerApply.ts:166, 237`: the pause gates only `apply`.

Fix: lift one page-level "writes paused" state that every writer (staged apply, Setup, Invoices, Import, Documents) checks and sets on `unknown` or `saved_unread`. Map `saved_unread` to unknown in `callFailure`. Keep each form’s send disabled until its re-read resolves the outcome.

### P03 · approval-after-corrections | high | A staged model approval is answered after the same row’s corrections, so its baseline-guarded commit is refused

Scenario: on movement A the person approves the model’s suggestion (staged `suggestion`) and also edits A’s notes, description, counterparty, date, own account or group label.

`checkRow` raises `suggestion_and_edits` only for classification fields, so the plan holds nothing back. `planApply` then orders the steps bulk, classify, update, add, and finally the actions, the `answer` among them. The notes (bulk) or the description (update, which also gives A a new id) are written first.

The review then commits with `expected_current=baseline`. That baseline is the whole transaction as it stood when the model was asked, so the commit fails ("transaction changed since it was opened") or no longer locates A. The review is consumed and the person has to ask the model again.

This also breaks R2’s per-row order (classification first, then corrections). Swapping the order would not fix it: a later bulk row always re-sends the row’s effective classification (`bulkRow`, ledgerPlan.ts:796-799), which is the pre-approval value, and would overwrite the approved one.

A second route to the same refusal: `ruleApplyClashes` ignores staged suggestions. A staged rule apply whose dry run names A can run before the answer and change A.

Evidence:
- `src/shell/ledgerPlan.ts:661-669`: the check is limited to `CLASSIFICATION_FIELDS`.
- `ledgerPlan.ts:995-1001`: answers run after the updates.
- `ledgerPlan.ts:525-534`: `ruleApplyClashes`.
- `src/cadrumo/application/ledger/llm_review_execution.py:204-216`.
- `src/cadrumo/application/ledger/actions_manual.py:1049-1058`: whole-row equality.

Fix: hold a staged approval back when the same row has any field edit or a clashing rule apply (as structural actions already are), offering "Drop the edits" or "Drop the approval". Add a plan test that combines a description or notes edit with an approval.

### P03 · sealed-never-supplied | medium | The page never knows which movements are sealed, so the locks, the skip counts and the review’s sealed hold never fire

Scenario: a movement cited by a finalized Modelo revision is still editable in the grid. "Set for 276" counts no sealed rows as skipped. The review plans the edit as "saved together", and the product then refuses the row (bulk `finalized_blockers`). The page claims what it cannot do, contrary to R1 and R8 ("Set for 276 (64 sealed skipped)") and R2 ("`lockReason` is evaluated against the staged row"). The product’s own guard prevents a wrong write, so the impact is false promises and refusals, not data loss.

Evidence:
- `components/ledger/LedgerPage.tsx:622-626`: `editing` is passed without `sealed`.
- `movements/MovementsSection.tsx:652`: falls back to `NO_SEALED`.
- `inspector/LedgerInspector.tsx:141, 194`: `SelectionInspector` and `ActionDialog` get `NO_SEALED`.
- `editing/ReviewDialog.tsx:1208`: `planApply(content, { rows })` without `sealed`.
- Only the single-row inspector derives `sealed`, from `ledger.track` (`inspector/MovementInspector.tsx:193-195`).

Fix: read the sealed set once per window, or for the staged rows when the review opens (`ledger.track` participation), and pass it to the grid, the inspectors, `ActionDialog` and the review’s `planApply`.

### P03 · redundant-share-clear | medium | Reclassifying Mixed rows away from Mixed adds one single write per row that the bulk already covers

Scenario: select 120 stored Mixed movements and choose Business (M4) or Personal, or type it in the grid. `classifyCells` and `rowCells` stage a `business_pct` clear with the classification. `routeChange` sends that clear through `ledger.classify.single`, because the bulk carries no clears.

The bulk part alone already clears the share: `_command_from_patch` drops `business_pct` whenever the classification is set to anything but Mixed. The apply therefore makes 120 extra one-at-a-time writes (about 6 minutes at `SINGLE_WRITE_SECONDS`), and each reports "unchanged". The plan line says "120 saved one at a time" for a change that costs one bulk part.

Evidence:
- `src/shell/ledgerCommands.ts:166-172`.
- `components/ledger/editing/editingModel.ts:367-373`.
- `src/shell/ledgerPlan.ts:81, 124-128`.
- `src/cadrumo/application/ledger/actions_manual.py:1451-1453`.

Fix: do not stage, or do not route, a share clear on a row whose staged classification is set to a non-Mixed value. Let the classification write carry it.

### P03 · status-done-unchecked | medium | Every reviewed movement is drawn "Done" with the success glyph while readiness is unchecked or failed

Scenario: `ledger.preflight` fails, or is still running on first load. The strip correctly shows `◌`. Meanwhile every reviewed row’s status cell reads "Done" in the success tone, because the per-row issue count falls back to 0. An unknown issue count is drawn as no issues, against R1 and R22 and the ADR rule that unknown is never drawn as zero.

Evidence:
- `components/ledger/movements/MovementsGrid.tsx:135-140`: `?.length ?? 0`.
- `movements/movementWords.ts:79-87`: `issues > 0 ? needs_fixing : done`.
- `movements/movementsModel.ts:337`: `sets.checked` exists but is not consulted by `StatusCell`.

Fix: pass `checked` to `StatusCell`. While unchecked, draw reviewed rows with the not-measured state (`circle-dashed`) instead of Done.

### P03 · permanent-link-unknowns | medium | The permanent-link review treats an unread invoice, or a different currency, as "no mismatch"

Scenario 1: `ledger.invoice.list` fails when the review opens. `invoices` becomes null, each link row shows only the raw invoice id with no mismatch chips, and one tick enables Save for an irreversible link.

Scenario 2: a 100.00 USD movement linked to a 100.00 EUR invoice raises no "Amount differs" chip, because `linkMismatches` compares the numbers only. M1 requires both sides and their differences to be shown, with a second tick, before Save.

Evidence:
- `components/ledger/editing/useLedgerApply.ts:190-196`: the failed read becomes `null`.
- `editing/ReviewDialog.tsx:1304-1316`: a missing invoice gives `mismatches: []`.
- `editing/editingModel.ts:943-963`: no currency comparison.

Fix: while a link’s invoice could not be read, hold the link with "Invoice could not be read · Re-read". Add a currency mismatch kind that needs the second tick.

### P03 · rule-apply-unknown-finding | low | An unknown rule apply re-reads to an empty finding

`resolveUnknown` returns an empty map for `rule_apply`, which names no `transactionId` and whose `actionRows` is empty. `reread` therefore sets `findings = []`, and the banner draws an empty neutral alert with only Dismiss. The person is never told whether the rules ran.

Evidence: `src/shell/ledgerApply.ts:682-736`, `components/ledger/editing/useLedgerApply.ts:295`, `editing/LedgerEditing.tsx:164-211`.

Fix: report the action itself as undetermined, keyed by the action id, and word it.

### P03 · output-language | low | Bulk row refusals arrive in Spanish whatever the window’s language

No caller passes `outputLanguage` to `planApply`, so the bulk request omits `output_language` and the worker renders each failure reason in its default, `es`.

Evidence: `components/ledger/editing/ReviewDialog.tsx:1208`, `src/shell/ledgerPlan.ts:287, 343-345`, `src/cadrumo/core/external_constants.py:551`.

Fix: pass the chrome language to `planApply`.

### P03 · superseded-reviews | low | Superseded or abandoned model reviews are left pending

Each re-ask (with a share or a rejection reason), each switch to another movement, and each dropped staged approval leaves the earlier `ledger.classify.review` paused at its review. `port.cancel` is never called anywhere on the page; in src/components/ledger the only `.cancel(` calls are the cell editors’ own.

Evidence: `components/ledger/inspector/ModelSuggestion.tsx:88-93, 95-146, 200`.

Fix: cancel the superseded operation at its observed revision.

### P03 · readiness-dead-code | low | Unused readiness helpers contradict M3

`readinessCurrency` counts staged changes as "out of date" ("Staged changes count"), which M3 reversed. Neither it nor `readinessAfterSave` has a production caller; only `tests/ledger-window.spec.ts` uses them.

Evidence: `src/shell/ledgerWindow.ts:535-566`.

Fix: remove both and their tests, or bring them in line with M3.

### P03 · split-followups-silent | low | A split whose result does not list its parts drops the staged part classifications without a word

When `child_transaction_ids` is missing or has the wrong length, `followUps` returns `[]`. The split counts as applied and leaves the stage with its part classifications, and the report shows no line for them.

Evidence: `src/shell/ledgerApply.ts:326-328, 533`.

Fix: emit a report row that says the parts’ classifications were not sent.
