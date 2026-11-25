---
tags:
  - '#audit'
  - '#desktop-ledger-editor'
date: '2026-10-24'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:e22f44a10e7af4f3a277176b5747d2f728f8c21151b93501391cc3bca915cca4'
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

## P03 usability and design review, 2026-10-24

An adversarial walkthrough of ten quarterly-books tasks at 1440×900 and 1280×800, in both schemes, against the scenario host. 2 critical, 6 high, 10 medium and 7 low findings. Owner ruling taken under the standing "no decisions from me" authorization: `status-column-wasted` amends R17, so in compact density the Status column is 2.75rem; it stays 7.5rem in comfortable density, where R22 shows the word. Still deferred, as S14 recorded: rule matching on counterparty or amount range needs a product contract change.

#### Task walkthroughs

- **Steps** counts deliberate inputs. A click or a chord is one step. Typing a word is one step.
- **Seconds** has two parts:
  - the scripted wall time, from Playwright with zero latency;
  - in brackets, an estimate for a practised person. The estimate uses keystroke-level timings: about 1.1 s per point-and-click, 0.3 s per key, 1 s per typed word and 1.5 s for each read-and-decide.

| # | Task | Route taken | Steps | Seconds | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | Classify 10 unclassified movements as Business with a category, in bulk | Period ▾ → Year → `○ 18` → tick row 1 → Shift-tick row 10 → Alt+B (**does nothing**) → inspector "Business…" → category ▾ → type "software" → Enter → "Stage for 10" | 11 | 6.3 (≈ 24) | **Trap.** Alt+B is dead from a checkbox. Keyboard Shift+Space/Shift+↓ selects 1 row while 10 are outlined. Description is clipped. Income rows are given an expense category. |
| 2 | Mixed expense at 30% | click row → Alt+M → type 30 → Enter | 4 | 1.3 (≈ 5) | Pass with a trap: focus drops to `<body>`, and no category is asked, so the row comes back "Needs fixing" after saving |
| 3 | Every movement from one counterparty in a quarter, grouped by category | ‹ (to 3T) → search → type "Talleres" → Group ▾ → Category | 5 | 3.6 (≈ 9) | Pass. The group menu stays open after the choice. The group header has no "Make a rule". |
| 4 | Fix a counterparty typo, then undo | click cell → F2 → End → type → Enter → Ctrl+Z (Ctrl+Y redoes) | 6 | 1.4 (≈ 6) | Pass |
| 5a | Review staged changes and save | tray "Review" → Save 3 → Done | 3 | 1.5 (≈ 7) | Pass, but focus drops to `<body>` after Done |
| 5b | Same, with the outcome unknown | as 5a, with `nextWrites(["unknown"])` | 3 | 1.9 | **Trap.** The dialog is titled "Nothing saved" while its body says "may or may not have saved". |
| 5c | Same, with the save refused | as 5a, with `nextWrites(["refused"])` | 3 | 1.7 | Pass with copy defect: "Refused: precondition_failed." |
| 6 | Import a bank statement (preview, choose the account, apply) | Import → Choose files… → Preview → Account ▾ → Import exactly these files (2) → Show imported movements | 6 | 7.1 (≈ 20) | Pass with gaps: no duplicate comparison in the preview, no duplicate marker in the grid afterwards, and a detected account that cannot be changed |
| 7 | Export the quarter | Export → XLSX → Export without them → Choose… → Export (40) | 5 | 3.3 (≈ 12) | Pass. At 1280×800 the Export button is below the fold. The readiness count disagrees with the page. |
| 8 | Confirm a received invoice from Documents and link it to its movement | Documents → document → Invoice I received → As read: ES → Confirm as invoice → Link · permanent → tray Review → tick → Save | 9 | 6.3 to Review (≈ 28) | Pass for the PDF. The scanned ticket cannot be judged because the image is never shown. Focus drops to `<body>` after three of the steps. |
| 9 | Add a classification rule from a selection | search "farmacia" → header tick → Alt+I (the inspector didn't open on the tick) → scroll to "Make a rule…" → dialog → Save rule | 6 | 3.2 (≈ 15) | **Trap.** A rule built from 8 matching movements says "Matches 0 loaded". It can match on description only. |
| 10 | What's missing for a quarter, in Health | Setup ▾ → Health → Check | 3 | 2.7 (≈ 6) | Pass. It says "Not checked in this window yet" although the strip has already measured readiness, and it uses ⚠ for classification where the strip uses ○. |

Keyboard coverage, all checked live:

- These work: ↑ ↓ ← → Home End Ctrl+Home Ctrl+End PageDown, F2, typing to edit, Enter to commit and move down, Escape to cancel, Ctrl+Z / Ctrl+Y, Ctrl+C on a range (gives TSV), the multi-cell paste preview, Delete to clear, ↑ from row 1 into the header, F8 / Shift+F8 (goes to the missing cell), Alt+I (open → focus the index → back to the grid), Ctrl+K (shell palette with Classify actions), and the period dropdown's arrow grid, Escape and focus return.
- These fail or diverge: Alt+B/P/M from a checkbox; Shift+↓ after Shift+Space; Space on its own (no effect); and focus after dialogs (below).

### UX · classify-flow-hides-description | critical | The "to classify" and reason-chip flows scroll the grid sideways, so Description and Counterparty slide under the sticky Status and Date columns while you are being asked to classify

- **What I did.** At 1280×800 in the default layout (agent pane open), I clicked the `○ 8` pill.
- **What happened.** The grid showed Status, Date, Direction, Classification and Amount, and nothing else. Description and Counterparty are scrolled out of view under the sticky left columns, and nothing tells you they are there (`scratchpad/reviews/ux/shots/20a-1280-agent-pill.png`).
- **At 1440 with the agent hidden.** The same flow sets `scrollLeft` to 33. Every description then loses its first letters ("ription", "A HOGAR ALBOR", "NSFERENCIA TALLERES"), because the scrolled text runs under the sticky Date column with no edge (`scratchpad/reviews/ux/shots/03c-ten-selected.png`, `scratchpad/reviews/ux/shots/04d-staged.png`). The header geometry confirms it: Date spans 216–288 (sticky) and Description starts at 255.
- **Why it matters.** You classify a bank movement by what it is. Here the grid hides exactly that, in the flow built for classifying. With the agent pane open at 1280, the grid is also only 591 px wide once the inspector opens, below the 40rem minimum that M6 promises (`scratchpad/reviews/ux/shots/05-1280-agent-inspector.png`).
- **Proposed change.**
  - Make Description part of the sticky identity group (Status · Date · Description, minimum 12rem), and never scroll horizontally to reveal the active cell when that would push the identity group out of view.
  - When the grid is narrower than the preset needs, the preset drops its lowest-priority columns first (Group, then Direction folded into the Amount cell as ↗/↙). Hidden columns get a `+2 ›` cue in the header row.
  - Give sticky columns the theme's edge shadow whenever content is scrolled under them.
  - When the agent pane and the inspector are both open below 1440, either collapse the agent pane to its rail or open the inspector at `--inspector-min`, so the grid keeps its 40rem.

### UX · unknown-titled-nothing-saved | critical | When a save's outcome is unknown, the dialog is titled "Nothing saved"

- **What I did.** I staged 3 changes, set `nextWrites(["unknown"])` and pressed Save.
- **What happened.** The title says "Nothing saved". The body says "One save has an unknown outcome · It may or may not have saved" (`scratchpad/reviews/ux/shots/09d-unknown-after-save.png`). The title is a factual claim the app cannot make, and it is the line a person reads.
- **After closing, in the grid.** The fixture landed the write, so the rows read "→ Personal · changed, not saved, was Personal": a staged change equal to the stored value (`scratchpad/reviews/ux/shots/09e-unknown-closed.png`).
- **The paused-writes banner.** It renders "Re-read" as a black bar about 1,320 px wide, which looks like a hand-built element rather than an Alert action.
- **Proposed change.**
  - Title the result by its worst outcome: `◌ Outcome unknown · 2` / `⊘ Not sent · 1`, with "Saved" used only when every part settled.
  - The banner uses the Alert pattern with the action at its end ("Outcome unknown · writes paused · [Re-read]"), within the 8-word budget.
  - After the re-read, a staged change whose value now equals the stored value is dropped, with the persistent "was saved" note R11 asks for, instead of staying as "changed, was the same".

### UX · business-on-income-forces-expense-category | high | Bulk "Business" on income makes you pick an expense category and stages it with no warning

- **What I did.** I selected 6 incoming client transfers (Talleres Ondara, all "In") and chose Classify as Business.
- **What happened.**
  - The category step offered only expense families: Social security, Premises, Vehicle, Meals and so on.
  - It accepted "Vehicle fuel" and staged "Business · Vehicle fuel" on all six income rows.
  - The review listed it without comment (`scratchpad/reviews/ux/shots/19a-income-fuel.png`, `scratchpad/reviews/ux/shots/19c-review-income-fuel.png`).
  - Task 1 did the same with Software subscriptions on a mixed In/Out selection (`scratchpad/reviews/ux/shots/04d-staged.png`).
- **Why it matters.** This is a filing-relevant miscategorisation that the UI invites. M4's "Business always asks for a category" was written for expenses.
- **Proposed change.**
  - The Business step counts directions first: "Business · 4 out · 2 in". It asks for an expense category for the out rows only, and gives the in rows the income list where one exists, or "no category needed".
  - A selection made only of income skips the category step.
  - The review adds a mismatch chip, "Expense category on income · 6", in the M1 chip idiom.

### UX · alt-b-dead-after-checkbox-selection | high | The classify chords do nothing after a checkbox selection, and keyboard range selection selects 1 row while showing 10

- **What I did, with the mouse.** I ticked row 1, Shift-ticked row 10 ("10 selected") and pressed Alt+B. Nothing happened, because focus sits on the row checkbox (`tabindex=-1`). The same happens after the header tick. I had to use the inspector segment or Ctrl+K "Classify as Business" (`scratchpad/reviews/ux/shots/04b2-altb.png`).
- **What I did, with the keyboard.** I pressed Shift+Space, then Shift+↓ nine times. That drew a 10-row cell range, but the selection stayed at 1. Alt+B then opened "Business · 1 movements" while 10 rows were visibly outlined (`scratchpad/reviews/ux/shots/03c-ten-selected.png`, `scratchpad/reviews/ux/shots/03e-typed.png`). Shift+Space after a range does select the range, but a spreadsheet user does it the other way round.
- **Proposed change.**
  - Handle Alt+B/P/M once at page level, as M2 already does for Alt+I, so they work wherever focus is in the Ledger page and outside text fields.
  - After Shift+Space, Shift+↑/↓ extends the row selection (Excel's row mode).
  - The M4 dialog title always counts the selection the command will act on. When a cell range and the row selection differ, it says so ("1 selected · range covers 10 · Select range").

### UX · document-no-preview | high | You confirm a scanned receipt without ever seeing it

- **What I did.** I opened `ticket-plenoil-1015.jpg`. It asks "Two possible identities · Two tax ids are printed on the ticket" and "The totals do not add up".
- **What happened.** Nothing in the Documents panel shows the image or the PDF. Answering "which NIF is the supplier's" means opening the file elsewhere (`scratchpad/reviews/ux/shots/12b-ticket.png`, `scratchpad/reviews/ux/shots/12a-documents.png`).
- **More problems on the same panel.**
  - The questions sit below 14 full-width fields. The flagged fields (Supplier NIF, Taxable base, Total) carry a ⚠ but don't link to their question.
  - Every input is 646 px wide for values like "21" or "2026-10-01".
- **Proposed change.**
  - Split the right panel into a document viewer (fit-width, zoom, page ‹ ›) above or beside "What was read".
  - Focusing a field highlights where it was read, when the reader gives a box.
  - Each ⚠ glyph is a button that scrolls to its question.
  - Fields are sized by kind: amounts and rates 8rem, dates 10rem.

### UX · import-duplicates-unmarked | high | Possible duplicates are imported with no marker on the row, and the preview cannot compare them

- **What I did.** I imported two statements. The preview says "Possible duplicates: 2. They are imported and flagged; compare them after importing." It has no popover or side-by-side view (`scratchpad/reviews/ux/shots/10c-preview-1440.png`). That falls short of R12 ("the preview shows each duplicate next to the existing movement, in a popover inside the dialog").
- **After import.** The result step lists them with "Compare" (`scratchpad/reviews/ux/shots/10d-result-1440.png`). In the grid, "CARGO EXTRACTO-CUENTA-ES 01 · 77.44" and "… 02 · 294.00" show only `○` in Status. No row's text or accessible name contains "duplicate", and there is no "Archive as duplicate / Keep both" (`scratchpad/reviews/ux/shots/10e-shown-1440.png`). Once you click Done, nothing tells you that 77.44 and 294.00 are now in the quarter twice.
- **Detected accounts.** An account "detected from the file" shows as plain text with no way to change it, so a wrong detection is a dead end.
- **Proposed change.**
  - In the preview, a `⚠ 2` chip on the file card opens the R12 popover pairing each new row with the existing movement.
  - After import, give the row a `copy` glyph in the Status cell (named "Possible duplicate"), a readiness-strip chip "Duplicates 2", and the two R12 actions in the row's ⋯ menu and the inspector header.
  - The detected account stays the same Select, prefilled, with "detected from the file" as its hint.

### UX · rule-matches-zero | high | A rule made from 8 matching movements says "Matches 0 loaded", and it can only match on the description

- **What I did.** I searched "farmacia", ticked the header, chose "Make a rule…" and accepted the prefill (Description contains "FARMACIA NUBE BLANCA" → Personal).
- **What happened.** It showed "Matches 0 loaded", with "Also classify them now" disabled (`scratchpad/reviews/ux/shots/14a-rule-dialog.png`). The count includes only unclassified rows (`setupModel.ts:144-158`), and the copy doesn't say so. To a person it reads as "this rule is broken".
- **Missing matchers.** R8 asks for counterparty and amount-range matching. The dialog only has description, plus a regex switch.
- **The Category field.** It is a native select over about 45 categories, ungrouped and unsearchable. Everywhere else, categories use the grouped Combobox.
- **Getting to it.** "Make a rule…" is only reachable from the bottom of the selection inspector, below the fold at 900 px, and the inspector doesn't open when you select with the header tick.
- **Proposed change.**
  - Show the count as two numbers: `Matches 8 · 0 to classify`.
  - Add a "Match on" segmented control (Description · Counterparty · Amount), prefilled from what the selection shares. Use the Combobox primitive for Category.
  - Add "Make a rule…" to the selection's toolbar actions, the `⋯` that appears when more than one row is selected, as well as the inspector.

### UX · focus-lost-after-dialogs | high | Focus drops to `<body>` after six common commits

Measured with `document.activeElement`. Focus fell to `<body>` after:

- Enter in the Mixed share dialog (`scratchpad/reviews/ux/shots/07c-after-enter.png`);
- "Done" on the save result (twice);
- "As read: ES";
- "Confirm as invoice";
- "Link · permanent".

Each time a keyboard user has to Tab through the shell from the top. R10 and V-05 require focus to return to the active cell.

**Proposed change:**

- Every dialog that the grid opens returns focus to the active cell on close.
- In Documents, after a commit, focus goes to the next action in the flow: after "As read", to Confirm; after Confirm, to "Link · permanent"; after linking, to the next document in the list.
- Add a test per dialog that asserts `activeElement` after close.

### UX · export-footer-offscreen | medium | At 1280×800 the Export button is below the fold, and the dialog says everything twice

- **What happened.** The dialog's content scrolls with its footer. At 1280×800, "Export (40)" sits outside the visible dialog, and at 1440×900 it is clipped at the edge (`scratchpad/reviews/ux/shots/11b-chosen-1280.png`, `scratchpad/reviews/ux/shots/11a-export-1440.png`).
- **Repeated text.**
  - "Movements to export: 40." repeats the button label.
  - "Chosen last, in the system's save dialog, which asks before replacing a file. Changing the format or period clears it." is 22 words of inline help (R22: help goes behind ⓘ).
  - "Export without them" changes nothing visible apart from its pressed state.
- **Proposed change.**
  - A sticky dialog footer, from the Dialog primitive, on every Ledger dialog: Export, Import, Review.
  - Move the save-as and "nothing is sent to the AEAT" notes behind ⓘ.
  - When "Export without them" is pressed, collapse the staged-changes alert to one line ("1 unsaved · not in this file").

### UX · readiness-counts-disagree | medium | Three surfaces count readiness three different ways

- The page strip shows `⚠ 2 ○ 8 ⊘ 1`.
- Export says "Not ready for calculation · Readiness issues: 10" (`scratchpad/reviews/ux/shots/11a-export-1440.png`).
- Health lists "⚠ Classification 8 · ⚠ EUR figures 1 · ⚠ Category 1", using ⚠ for to-classify where M3 reserves ○ (`scratchpad/reviews/ux/shots/15c-health-checked-1440.png`).
- Health also says "Not checked in this window yet" while the strip on the same page already shows a check result (`scratchpad/reviews/ux/shots/15b-health-1440.png`).

M3 and M8 ask for one unit and one glyph per state.

**Proposed change.** Export and Health reuse the strip's pills and chips as the same component: `⚠ 2 ○ 8 ⊘ 1`, then "Category 1", "EUR figures 1". Health opens on the strip's last check, with its time in the tooltip, and offers "Check again".

### UX · category-search-fuzzy | medium | Category search ranks letter scatter above words, so Enter picks the wrong category

- **What I did.** In the Business dialog, I typed "soft". The first and highlighted option was "Professional association fees", followed by "Self-employed social security…", "Utilities…" and "Home-office water". "Software subscriptions" wasn't in the visible results (`scratchpad/reviews/ux/shots/03e-typed.png`), and Enter staged "Professional association fees".
- **The popup.** It is narrower than its trigger (220 vs 344 px), so names are cut off ("Professional association f…", "Alternative mutual-insurance c…"), and it overlaps the dialog's Cancel button.
- **Proposed change.**
  - Rank exact word-prefix matches first, then word-contains, and show scattered-letter matches only when nothing matches by word.
  - The popover is at least as wide as its trigger, up to the dialog width, and wraps long names instead of truncating them (R16).

### UX · enter-reopens-combobox | medium | In the Business dialog, Enter after choosing a category reopens the list instead of staging

After you pick with Enter, focus returns to the combobox trigger, and the next Enter opens the list again (`scratchpad/reviews/ux/shots/03g-staged.png`). To stage from the keyboard you need Tab, Tab, Enter.

**Proposed change.** After a pick, move focus to the primary "Stage for n" button, or make the dialog a form so Enter submits once its required field is filled.

### UX · mixed-without-category | medium | Alt+M asks only for the share, so the row comes back "Needs fixing"

"Mixed · 1 movements" asks for the business share only (`scratchpad/reviews/ux/shots/07a-altm.png`). After saving, RECIBO TELEFONIA reads `⚠ 1 · Needs fixing` (`scratchpad/reviews/ux/shots/09d-ok-after-save.png`), so it needs a second pass. M4 requires a share for Mixed, and nothing stops the same step from asking for a category as well.

**Proposed change.** The Mixed step asks for the share and the category together, with the category filtered to the families that allow a share. The toast reads "Mixed · 30% · Mobile phone · 1 movement staged".

### UX · refused-raw-code | medium | A refusal shows the raw code

The refused save reads "BAZAR EL FARO COMPRA: Counterparty · Refused: precondition_failed. It stays staged." (`scratchpad/reviews/ux/shots/09d-refused-after-save.png`). R18 keeps codes under "Technical details".

**Proposed change.** "Not saved: changed elsewhere · stays staged · [Re-read]", with the code under Technical details.

### UX · review-repeats-itself | medium | The review and its result say everything twice

- **Before saving.** The review shows a Summary table and then the full per-movement list, which, for a bulk change, is 8 identical "Classification: To classify → Personal" rows (`scratchpad/reviews/ux/shots/20b-1280-review.png`).
- **After saving.** The result repeats "Saved" under every movement (`scratchpad/reviews/ux/shots/09d-ok-after-save.png`).
- **False affordance.** Each change row starts with a pencil glyph that looks like an edit button but isn't one.
- **The time estimate.** "1 one by one (about 1 min)" for a single link is not believable.

R22 asks for one summary line, with details expanding per kind.

**Proposed change.**

- Lead with the summary line, then the per-kind table. The per-movement list starts collapsed: "8 movements ›".
- On success, show only "✓ 3 saved". List rows only for parts that did not save.
- Drop the decorative pencil.
- Show the time estimate only when it is more than a minute.

### UX · hidden-columns-no-cue | medium | With the inspector open at 1280, Category and Group sit under the sticky Amount with no cue

At 1280 with the inspector open, the Review preset's Category and Group columns are pushed under the sticky Amount column, and nothing in the header shows that there are more columns (`scratchpad/reviews/ux/shots/05-1280-noagent-inspector.png`, `scratchpad/reviews/ux/shots/01-home-1280-dark.png` with "Categ", "Bank", "Hom").

**Proposed change.** The same fix as the first finding: an edge shadow on the sticky right group, and a `+2 ›` header cue that scrolls to them. The preset should also prefer Category over Group when space is short.

### UX · group-header-actions | medium | Group-header actions look like plain text, are cut off, and leave out "Make a rule"

- The group header's actions, "Business…  Personal  Mixed…  Category  Select 6", are ghost text with ellipses. They read as labels, not buttons.
- R8's "Make a rule from this group" is missing (`scratchpad/reviews/ux/shots/08c-grouped.png`).
- The Group ▾ menu stays open after you choose a grouping.

**Proposed change.**

- Use the toolbar's small outline buttons, with the M4 commands as one `Classify ▾` split button: Business · Personal · Mixed.
- Add a `⋯` menu holding Category ▾, Make a rule from this group and Select 6.
- The Group menu closes when you choose.

### UX · selection-inspector-repeats | low | The selection inspector says "To classify" three times and the currency twice

The selection inspector shows:

- "To classify 8" twice, once from the classification counts and once from the status counts (`SelectionInspector.tsx:451-468`);
- "Classification: To classify" again under Common values;
- "In · EUR 2,226.00 EUR", with the currency in both the label and the value (`scratchpad/reviews/ux/shots/02c-selected-all.png`).

Under "Set for all", "Category · 8 skipped / Set for 0" on unclassified rows reads like a refusal.

**Proposed change.**

- Show one status line of glyph counts (`○ 8`).
- Write totals as "In 2,226.00 EUR".
- While the rows are unclassified, replace the disabled tax-field selects with one line: "Classify first · Business… sets a category".

### UX · plural-grammar | low | Singular counts get plural nouns throughout

Examples:

- "Business · 1 movements"
- "Mixed · 30% · 1 movements staged"
- "1 unsaved: 1 actions"
- "1 changes are kept only in this window"

They appear in dialog titles, toasts, the tray tooltip and the leave guard (`scratchpad/reviews/ux/shots/07a-altm.png`, `scratchpad/reviews/ux/shots/21b-leave-close.png`).

**Proposed change.** Use ICU plural forms in the `dev.locales` catalogue for every count string, in all four locales.

### UX · paste-refused-no-reason | low | A paste that is all refused gives no reason and still offers "Paste 0 cells"

Pasting three text lines into Amount shows "Refused 3" with no reason, and "Paste 0 cells" focused as the primary button (`scratchpad/reviews/ux/shots/16e-paste.png`).

**Proposed change.** Show the first refusal reason inline ("Amount: 'Proyecto A' is not an amount"), disable the primary button when no cell would change, and name the target column in the title.

### UX · amount-comma-refusal | low | The decimal-comma refusal makes you retype

Typing `77,45` is refused with '"77,45" uses a decimal comma: write 77.45.' (`scratchpad/reviews/ux/shots/18d-amount-comma.png`). That is correct under R3, but every Spanish bank statement uses a comma, so this refusal will come up all the time.

**Proposed change.** Keep the grammar, and add the documents panel's one-click suggestion idiom to the refusal: `Use 77.45`. Nothing is guessed silently.

### UX · usd-decimal-alignment | low | A currency suffix breaks the decimal column

"1,800.00 USD" pushes its decimals left of the EUR rows above and below it (`scratchpad/reviews/ux/shots/01-home-1440-light.png`).

**Proposed change.** Give the currency code its own fixed-width trailing slot in the Amount cell, empty for EUR, so the decimals line up down the column.

### UX · status-column-wasted | low | The Status column is 7.5rem wide for a glyph

In compact density the Status column holds only a glyph and a count, yet it takes 7.5rem (120 px) at every width. At 1280 that width is taken from Description.

R17 set 7.5rem before R22 made the status word appear only in comfortable density. This proposal changes the R17 width table, so it needs the owner's ruling.

**Proposed change.** Status is 2.75rem in compact density and 7.5rem in comfortable.

### UX · small-copy-and-chrome | low | Smaller copy and chrome defects

- The Import dialog says "A preview writes nothing" twice, in the subtitle and the info box (`scratchpad/reviews/ux/shots/10c-preview-1440.png`).
- The import-period banner is 12 words, over the 8-word budget: "Showing the period of your import: Oct 1, 2026 to Oct 26, 2026. Dismiss".
- An unreadable file card uses the destructive red border. An unreadable file is a refusal, not a danger.
- The palette shows "No pages match 'classify'" above matching actions, and the Classify actions carry no Alt+B/P/M hints, while the shell entries do show theirs (`scratchpad/reviews/ux/shots/16d-ctrlk-classify.png`).
- Accessible names repeat the count: "Movements88 to classify", "1818 to classify · 10 staged · 10 unsaved changes not included" (V-28).
- "Transf…" is truncated in the 5rem Direction column. Use the ⇆ glyph and put the word in the tooltip.
- Health's Status table spreads label and number across 680 px. Also, Active 40 ≠ To classify 8 + Reviewed 31 + Skipped 0, and nothing shows the missing one.
- "Saved changes can't be undone here" gives no next step. Add "· edit the cell to change it back".

### UX · deferred-contract-gaps | medium | Two parts of the usability fixes need product contract changes

- **Duplicate pairing in the import preview (R12).** The dry run names only the ids of the rows it would import, with no date or amount, so the window cannot pair a new row with the stored movement. The `⚠ n` chip and its note ship; pairing needs the import preview to return those row facts.
- **"Keep both" for a possible duplicate.** No product operation clears an import's likely-duplicate diagnostic, and the TUI offers only filtering and lifecycle actions. The page offers "Archive as duplicate" (`ledger.archive` with the reason prefilled) and nothing for keep-both.
- **Seeing a document before confirming it** moved to P03.S19, under the 2026-10-24 amendment to `2026-10-23-desktop-ledger-editor-adr`.

## P03 re-review, 2026-10-24

Changes from 2ee7b77c63 to d7311a0669. No critical or high finding: the two P03 highs and the two usability criticals are resolved. Six medium and eight low findings follow; the mediums are fixed under the reopened affected Steps.

#### Status of the earlier findings

### P03 phase-close review

- **setup-unknown-not-held (high):** resolved for the binding constraint. There is now one page pause (`WritePause.tsx`) that every Setup, Invoices, Import, Documents, model-ask and staged-apply writer checks and records into. `saved_unread` is mapped to its own outcome (`setupModel.ts:65`, `invoiceWrites.ts:49`) and worded as saved. Every ledger write route I traced is behind `WriteHold`, or returns early on `held`.
  - What remains: the re-read does not settle the forms' own outcome (P03R generic-settle-resolves-nothing). Document imports still fold `saved_unread` into unknown (low). Export is outside the pause (low).
- **approval-after-corrections (high):** resolved.
  - `checkRow` holds an approval on any field edit or m210 (`ledgerPlan.ts:708`), and on a rules apply that names the movement (`ledgerPlan.ts:713-722`, `ruleApplyClashes` 550-563).
  - The review offers "Drop the edits", "Drop the rules apply" and "Drop the approval" (`ReviewDialog.tsx:436-475`).
  - Plan tests: `ledger-plan.spec.ts:433, 467`.
  - Link and attach on the same row are not held. That is correct: answers rank 0 and link/attach rank 1 (`ledgerPlan.ts:401-418`), so the approval commits first.
- **sealed-never-supplied (medium):** partly resolved. A sealed set now reaches the grid, both inspectors, `ActionDialog` and the review's `planApply`. Above its bound, or after a failed read, an unread movement is still treated as unsealed (P03R sealed-unread-claimed-unsealed).
- **redundant-share-clear (medium):** resolved. `clearedBy` (`ledgerPlan.ts:138-154`) sends the clears on the classification's own route (`ledgerPlan.ts:596-609`). This matches `_command_from_patch` (`src/cadrumo/application/ledger/actions_manual.py:1451-1465`). `bulkRow` puts no cell for a clear (`ledgerPlan.ts:855-860`). Tests: `ledger-plan.spec.ts:505, 549`.
- **status-done-unchecked (medium):** resolved in the grid (`MovementsGrid.tsx:143-147, 338-340`, `MovementsSection.tsx:546-551`). It remains in the inspector header and the selection counts (P03R unmeasured-drawn-done-in-inspectors).
- **permanent-link-unknowns (medium):** resolved.
  - A link whose invoice could not be read is held, and a Re-read is offered (`ReviewDialog.tsx:1471-1473`, `useLedgerApply.ts:262-269`).
  - A currency mismatch needs the second tick (`editingModel.ts:951-960`).
- **rule-apply-unknown-finding (low):** resolved. It is keyed by the action id and worded through `actionText` (`ledgerApply.ts:721-726`, `useLedgerApply.ts:335-345`).
- **output-language (low):** resolved (`ReviewDialog.tsx:1355-1359`). `locale` is always a catalogue key (`useLanguage.ts:100`, `strings.ts:10`).
- **superseded-reviews (low):** partly resolved. A review is released only from inside the mounted `ModelSuggestion` (P03R superseded-reviews-partial).
- **readiness-dead-code (low):** resolved. `readinessCurrency` and `readinessAfterSave` are gone from `src` and `tests`.
- **split-followups-silent (low):** resolved.
  - `partsUnnamed` adds a `parts_unnamed` row (`ledgerApply.ts:322-328, 460-461`).
  - `keepAfterApply` skips `follows` rows, so the split is never staged again (`ledgerApply.ts:538-543`).

### P03 usability and design review

- **classify-flow-hides-description (critical):** resolved for the reported failure. Description is in the pinned group (`movementsModel.ts:76-83`), the pinned edges show, and there is a `+n` cue. The narrow layout the review measured is not fixed: the 40rem grid minimum is still not enforced (P03R pinned-group-narrow-band).
- **unknown-titled-nothing-saved (critical):** resolved.
  - The result is titled by its worst outcome (`ReviewDialog.tsx:1692-1708`).
  - The banner uses the Alert pattern with its action at the end (`WritePause.tsx:189-214`).
  - Rows the post-apply read shows as saved are dropped (`useLedgerApply.ts:391-400`).
  - The re-read that follows can drop edits made after the apply (P03R reread-drops-new-edits).
- **business-on-income-forces-expense-category (high):** resolved.
  - `takesExpenseCategory` (`ledgerCommands.ts:69-74`) reproduces `_transaction_needs_expense_category` (`src/cadrumo/application/ledger/preflight.py:479-495`): OUTGOING, or INCOMING with purchase evidence. `INTERNAL_TRANSFER` takes none, and transfers are blocked anyway.
  - The dialog counts and words the split (`ClassifyDialog.tsx:92-106, 219-225`).
  - The review raises an "Expense category on income" chip (`ReviewDialog.tsx:244-259, 1484-1492`).
  - Caveat: the rule reads the stored direction, not a staged one (see the low items below).
- **alt-b-dead-after-checkbox-selection (high):** resolved for the grid, the checkboxes, the toolbar and the inspector.
  - A document-level listener scoped to `.ledger-page` handles the chords (`MovementsSection.tsx:1090-1107`).
  - Shift+Space now starts row mode (`data-grid.tsx:1105-1111`).
  - When the selection and the range differ, the dialog says so (`ClassifyDialog.tsx:145-162`).
  - Remaining gaps are in the low items below.
- **document-no-preview (high):** deferred to P03.S19. Not re-reported.
- **import-duplicates-unmarked (high):** resolved for the marker, the strip chip and "Archive as duplicate" (`MovementsSection.tsx:511-529`, `MovementCells.tsx:85`, `MovementInspector.tsx:362-383`). Pairing in the preview and "Keep both" are deferred. Not re-reported.
- **rule-matches-zero (high):** resolved.
  - The count now reads `Matches {count} · {pending} to classify`.
  - Category uses the Combobox (`RuleDialog.tsx:171-183`).
  - "Make a rule" is in the selection menu and the group menu.
  - Counterparty and amount matchers stay deferred under S14.
- **focus-lost-after-dialogs (high):** resolved for each listed commit:
  - Classify dialog: `onClosed` goes to `backToGrid`.
  - Review: `returnReviewFocus` → `focusActive` (`LedgerEditing.tsx:152-161`, `LedgerPage.tsx:352-356`).
  - "As read": focus goes to Confirm (`DraftReview.tsx:1029-1033`).
  - Confirm: focus goes to "Link · permanent", or to the focusable root (`DraftReview.tsx:395-399, 576-579`).
  - Paste and cost dialogs: focus goes back to the active cell (`MovementEditing.tsx:769-797`).
  - Rule from the grid: focus goes back to the active cell (`LedgerPage.tsx:930-934`).
  - Not verified by a run.
- **Resolved by reading the code:**
  - export-footer-offscreen: sticky `DialogFooter` (`dialog.tsx:139-163`) on Export, Import and Review.
  - readiness-counts-disagree: the shared strip, hidden when the Export period differs (`ExportDialog.tsx:418`).
  - category-search-fuzzy: `optionScore`, plus a popup at least as wide as its trigger that wraps.
  - enter-reopens-combobox: `enterStages`.
  - refused-raw-code.
  - hidden-columns-no-cue.
  - group-header-actions.
  - selection-inspector-repeats.
  - paste-refused-no-reason.
  - usd-decimal-alignment: `currencySlot`.
  - status-column-wasted: amended to 2.75rem compact by the owner ruling.
- **mixed-without-category (medium):** partly resolved. The Mixed step now asks for a category, but against the real product the row still comes back "Needs fixing" (P03R mixed-step-still-needs-fixing).
- **plural-grammar (low):** reworded to a `Label: {count}` form. I sampled 12 new keys and each is present in es, ca and hu. In the English sample no reworded string lost meaning: the paste columns moved into `title_into`, and the batch counts read "Rows · new · already". None of the reworded strings draws an unknown as zero. One pre-existing zero default is listed with the low items.
- **review-repeats-itself, amount-comma-refusal, small-copy-and-chrome:** checked only by the presence of their keys and code paths; not traced in depth.

### P03R · reread-drops-new-edits | medium | The re-read after an unknown save silently drops changes the person staged again while writes were paused

- **Scenario:**
  1. A save's outcome is unknown. The post-apply read already shows row A's category as saved, so A is added to `seen` and its staged category is dropped.
  2. Writes are paused, but grid editing is not. The person stages a new category on A.
  3. The person presses Re-read. `settle` marks every `seen` id as saved again and calls `dropSaved`, which dispatches `revert_cell` for every field the step sent.
  4. A's new staged category is removed with no word. The banner says "A was saved".
- **Other routes:** the same happens for any row the re-read finds saved, and for a re-staged approval. Its action id is the fixed `suggestion:${id}` (`ModelSuggestion.tsx:208`), so `drop_action` removes the new approval too.
- **Evidence:**
  - `components/ledger/editing/useLedgerApply.ts:309-317`: `dropSaved` reverts by field and action id, whatever the current staged value.
  - `components/ledger/editing/useLedgerApply.ts:330-332`: `seen` is re-dropped.
  - `shell/ledgerStage.ts:338-343`: `revert_cell` removes the staged change outright.
- **Fix:** drop a field or action only while its staged value still equals the one the step sent. Compare against the `staged` snapshot that `settle` already closes over.

### P03R · generic-settle-resolves-nothing | medium | A Setup, Rules, Import or Documents write with an unknown outcome is released by any one-movement read, and its form then sends the same document again

- **Scenario:**
  1. In the rule dialog, Save rule (`ledger.rule.add`) comes back unknown, and the page pauses.
  2. Re-read runs the generic settle: `readWindow(port, period, 1)`. That read never looks at rules. If it answers, the hold is removed with "Rules: read again, check what is stored", and `onSettled` clears the dialog's notice.
  3. The dialog is still open with the same pattern. `ready` depends only on `held`, so Save is enabled again. A second press sends the same `ledger.rule.add`, whose outcomes are only `added` or `validation_error` (`shell/ledgerSetup.ts:43`).
  4. If the first save committed, the rule now exists twice.
- **Other routes:** the same happens for Assets create and correct, Inventory, Prorrata, Capital goods, Counterparties, Ratios, Accounts, the invoice-book import and the document confirm. Each holds without a `settle` of its own.
- **Why it matters:** the ADR's "pause until it re-reads" is met to the letter. The earlier fix requirement was "keep each form's send disabled until its re-read resolves the outcome", and here the re-read resolves nothing about what was written.
- **Evidence:**
  - `components/ledger/WritePause.tsx:134-145`: the generic settle.
  - `components/ledger/setup/SetupParts.tsx:489-490`: Setup writes hold with no `settle`.
  - `components/ledger/setup/RuleDialog.tsx:192-199, 219-224`.
  - `components/ledger/setup/AssetsPane.tsx:364`.
  - `components/ledger/transfer/ImportDialog.tsx:637, 648`.
  - `components/ledger/documents/DraftReview.tsx:526-529`.
- **Fix:** give each writer a `settle` that reads what it wrote, as the invoice editor's `landedOf` does (`InvoiceEditor.tsx:258-291`). For example, the rule list for the pattern, the asset list, or `ledger.evidence.review.list` for a confirm. Keep a form's send held until that `settle` answers.

### P03R · unmeasured-drawn-done-in-inspectors | medium | The movement inspector and the selection inspector still draw reviewed movements as "Done" while readiness is unchecked or failed

- **Scenario:** `ledger.preflight` fails, or has not answered yet. The grid now shows `◌` "Not measured". Meanwhile:
  - The single-movement inspector header shows the badge "Done".
  - The selection inspector counts every reviewed row under the success glyph.
- **Why it matters:** both receive an empty `issues` map and take an unknown count as 0, which is the earlier finding on two other surfaces.
- **Evidence:**
  - `components/ledger/inspector/MovementInspector.tsx:274, 408`: `statusWord(row.review_status, issues.length)`.
  - `components/ledger/inspector/inspectorModel.ts:116-119`: `issues.get(...)?.length ?? 0`.
  - `components/ledger/inspector/SelectionInspector.tsx:170`.
  - `components/ledger/inspector/inspectorContext.ts`: the context carries `issues` but not `checked`.
- **Fix:** add `checked` to `SectionInspectorContext`. Pass `null` issue counts while it is false, as `MovementsGrid.tsx:143-147` already does.

### P03R · sealed-unread-claimed-unsealed | medium | Past the 400-read bound, or after a failed `ledger.track`, a movement is planned and counted as unsealed

- **Scenario:**
  1. In a large period the person ticks the header to select all. The selection alone spends the 400 `ledger.track` reads for this window generation.
  2. The person stages a change on a movement outside those 400, then opens the review.
  3. `sealedOf` has no room left, so that movement is never read. The review plans it as "saved together", and "Set for n (k sealed skipped)" counts it as unsealed. The product then refuses it with `finalized_blockers`.
- **Failed reads:** a failed read is cached as `null` for the whole generation and is never asked again at review time.
- **Why it matters:** an unread movement is drawn as not sealed, against R1, R8 and the ADR rule that unknown is never drawn as known. The product's own guard prevents a wrong write.
- **Evidence:**
  - `components/ledger/useSealedMovements.ts:16`: `SEALED_READS = 400`.
  - `components/ledger/useSealedMovements.ts:66-68`: `room` is shared across selection reads and review reads.
  - `components/ledger/useSealedMovements.ts:29-33`: a failure becomes `null`.
  - `components/ledger/useSealedMovements.ts:78`: only `true` counts as sealed.
  - `components/ledger/LedgerPage.tsx:312-323`: the sealed reads are driven by the selection.
- **Fix:**
  - Give the review's `sealedOf` its own budget, and retry `null` entries there.
  - Return the unread ids alongside the sealed ones, and have `planApply` and the selection counts show "sealed state not read · n" instead of counting those rows as savable.

### P03R · mixed-step-still-needs-fixing | medium | Alt+M now asks for a share and a category, but the product still reports the row as needing a proportionality reference, and the scenario host cannot show it

- **Scenario:**
  1. On a telephone bill the person presses Alt+M and enters 30% and Mobile phone.
  2. The Mixed step stages the classification, the share and the category, but no `usage_ratio_id` (`classifyCells`). The bulk passes `usage_ratio_id` through only when supplied (`classify_patch.py:193-194`).
  3. After saving, the product's preflight raises `missing_proportionality_reference` for every MIXED row whose `usage_ratio_id` is None (`preflight.py:578-590`). The row reads "⚠ 1 · Needs fixing" again.
- **Why the tests miss it:**
  - The fixture host never raises that reason. Its `missing_category` rule also ignores INCOMING rows with purchase evidence (`src/dev/ledgerFixture.ts:592-608`).
  - The scenario tests that exercise the Mixed flow therefore pass against looser rules than the host. This is a fidelity gap of the kind P01 · scenario-host-fidelity listed.
- **Evidence:**
  - `src/shell/ledgerCommands.ts:168-215`.
  - `components/ledger/movements/ClassifyDialog.tsx:84-87, 124-127`.
  - `src/cadrumo/application/ledger/preflight.py:578-590`.
  - `src/dev/ledgerFixture.ts:592-608`.
- **Fix:**
  - Where a usage ratio is configured for the chosen category, have the Mixed step stage `usage_ratio_id` = that category, routed by R2 (`ledger.allocate` carries it), and say so otherwise.
  - Make the fixture raise `missing_proportionality_reference` and the product's `missing_category` rule.

### P03R · pinned-group-narrow-band | medium | With Description pinned, the grid widths the review measured leave almost no scrolling band, so the Classification cell the classify flows reveal cannot be shown whole

- **Widths, from the column specs:**
  - Pinned at the start: select 2.25 + status 7.5 (comfortable) or 2.75 (compact) + date 4.5 + description 12 = 26.25rem or 21.5rem.
  - Pinned at the end: amount 6.5 + invoice 3 = 9.5rem.
- **The band left over:**
  - The earlier review measured a 591px grid at 1280 with the agent pane and the inspector open.
  - In comfortable density the pinned width is 35.75rem = 572px, leaving about 19px to scroll in.
  - In compact density the pinned width is 31rem = 496px, leaving about 95px.
- **Effect:** the Classification column (8rem = 128px) can never be fully in view. `reveal` aligns its right edge, so most of the cell sits under the pinned Description, in exactly the flow the critical was about.
- **Why it is unfixed:** the earlier finding's 40rem guarantee was not implemented. `GRID_MIN_REM` limits only resizing, and the panel is `shrink-0 w-inspector`.
- **Evidence:**
  - `components/ledger/movements/movementsModel.ts:71-92, 106, 122-123`.
  - `components/ledger/inspector/RightPanel.tsx:18, 56-65, 116`.
  - `components/ui/data-grid.tsx:652-660`.
- **Fix:** when both the agent pane and the inspector are open, either open the inspector at `--inspector-min` or collapse the agent pane to its rail, so the grid keeps 40rem. Below a minimum scrolling band, unpin Description or let it shrink to its minimum.

### P03R · superseded-reviews-partial | low | A staged approval dropped outside its movement's inspector leaves its review pending

- **What is fixed:** a review is now released when it is asked again, when the inspector moves to another movement, or when the staged answer is dropped while `ModelSuggestion` is mounted for that movement.
- **What is not:** dropping the approval while that inspector is not mounted leaves the review paused at its review step. That covers:
  - the review dialog's "Drop the approval", which the new hold now offers;
  - the per-row ×;
  - the tray's Discard;
  - the leave guard's Discard.
- **Evidence:**
  - `components/ledger/inspector/ModelSuggestion.tsx:101-126`: the only callers of `releaseReview`.
  - `components/ledger/editing/ReviewDialog.tsx:444-449`.
  - `components/ledger/editing/LedgerEditing.tsx:201, 233`.
- **Fix:** release in one place that watches the stage, for example in `useLedgerEditing`: compare the suggestion actions before and after each `drop_action`, `revert_movement` or `discard`, and release every operation that disappears.

### P03R · documents-saved-unread-as-unknown | low | Adding documents folds `saved_unread` into unknown, so a batch that saved is shown as "Outcome unknown"

- **Evidence:**
  - `components/ledger/transfer/importModel.ts:440-441` maps `saved_unread` to `"unknown"`.
  - `components/ledger/transfer/ImportDialog.tsx:648-652` then holds it as unknown.
  - Bank and book imports keep the distinction (`importModel.ts:368-369`, `ImportDialog.tsx:637`).
- **Fix:** carry the code through `stopped.code`, and hold with `outcome: "saved_unread"` when it is that.

### P03R · export-unknown-not-held | low | An export with an unknown outcome is not recorded in the page pause, so reopening Export sends it again with no re-read

- **Why it matters:** R11 says an unknown export is never retried before a re-read. The dialog disables Send only in its own instance, and a new instance starts at idle.
- **Evidence:** `components/ledger/transfer/ExportDialog.tsx:204-227, 592-599`. There is no `useWritePause` in that file.
- **Fix:** hold the pause on an unknown export, and wrap Send in `WriteHold`.

### P03R · chords-skip-the-header | low | Alt+B/P/M do nothing while focus is in the Ledger header (tabs, period, Import or Export)

- **Why it happens:** the listener requires `closest(".ledger-page")`. That class is on the content `<section>`, and `LedgerHeader` is its sibling, outside it.
- **Evidence:** `components/ledger/movements/MovementsSection.tsx:1101`, `components/ledger/LedgerPage.tsx:790-832`.
- **Fix:** mark the page's root, header included, and test for that mark, or put the class on a wrapper around both.

### P03R · shift-space-stale-anchor | low | Shift+Space selects from an old anchor, so row mode can again draw a range that differs from the selection

- **Scenario:**
  1. Click row 3, then press ↓ five times. The selection anchor stays on row 3.
  2. Press Shift+Space. It selects rows 3 to 8, not the active row.
  3. Press Shift+↓ twice. The cell range covers rows 8 to 10, while the selection covers rows 3 to 10.
  4. Alt+B then shows "Selected: 8 · range: 3".
- **Expected:** a spreadsheet selects only the current row on Shift+Space.
- **Evidence:** `components/ui/data-grid.tsx:774-786` (range from `selectionAnchor`) and `1105-1111`.
- **Fix:** on Shift+Space, set `selectionAnchor` to the active row and select that row only.

### P03R · compact-status-glyphs | low | In compact density the 2.75rem Status column clips the lifecycle badge, and its header reuses the Done glyph

- **The badge:**
  - `StatusCell` also draws the lifecycle word as a `Badge` (Archived, Set aside, Split), the duplicate mark and a two-digit count. These cannot fit in 44px, so a non-active row's state is cut off.
  - Evidence: `components/ledger/movements/MovementCells.tsx:54-87`, `movementsModel.ts:122-123`.
- **The header glyph:**
  - The compact header is the `check` glyph, which is also `STATUS_ICONS.done`. One glyph then means two things (DS-12).
  - Evidence: `components/ledger/movements/MovementsGrid.tsx:280`, `MovementCells.tsx:27`.
- **Fix:** draw the lifecycle state as a glyph with its name, for example the `lifecycle` column's glyph. Give the header a glyph that is not a state glyph.

### P03R · text-tip-stale-anchor | low | The shared grid tooltip keeps the position it had when it opened, so a focused cell's tip floats over other rows while the grid scrolls

- **Why it happens:** `box` is measured only when `GridTextTip` renders. The anchor is `position: fixed` outside the scroller, so the foundation's close-on-scroll does not fire for the grid's own scroll. A focused, cut-short cell that is scrolled within the overscan keeps its tip at the old coordinates.
- **Evidence:** `components/ui/data-grid.tsx:247-299`, especially line 267.
- **Fix:** hide the tip on the scroller's `onScroll`, which `syncView` already handles, or re-measure on scroll.

### P03R · lower-points | low | Four smaller items

- **Stored, not staged, values:**
  - `takesExpenseCategory` and `incomeWithCategory` read the stored direction and evidence. A movement whose direction is staged to change is counted on its old direction. Evidence: `shell/ledgerCommands.ts:69-74`, `components/ledger/editing/ReviewDialog.tsx:255`.
  - The selection inspector's `undecided` reads stored classifications, so the tax fields stay hidden after Business is staged for the whole selection (R8). Evidence: `SelectionInspector.tsx:172-174`.
  - Use effective staged facts in all three.
- **The review's "needs classification" fix:** its Business ▾ always asks for a category, even for income rows, which take none (`ReviewDialog.tsx:333-356`). It also bypasses the M4 command. Route it through `classifyCells` with the category step skipped for income.
- **A failed duplicates read:** if the read fails, every duplicate mark and the strip chip disappear without a word (`MovementsSection.tsx:518-520`). Show the failure as the filter-membership read already does.
- **Pre-existing, not introduced here:**
  - The rules dry run draws a null `skipped_already_classified` or `no_match` as 0 (`components/ledger/setup/RulesSection.tsx:343-344`).
  - The combobox ranking is not accent-insensitive, so "telefonia" does not match "Telefonía" as a word.

## P04.S17 integrated review, 2026-10-24

Plan-close review of P01.S01 to P04.S16: revision required, with 2 high, 1 medium and 4 low findings and no critical one. Every earlier P01, P02 and P03 finding marked fixed is fixed. The highs reopen P01.S01 and P03.S10. They are decided by the 2026-10-24 amendment "a model review is held per movement and can be let go" to `2026-10-23-desktop-ledger-editor-adr`.

### P04 · model-review-subject-lease | high | The runtime allows one model review per profile at a time, and the page leaves reviews pending that it cannot cancel. Re-asking, rejecting, "Ask the model for each" and staging a second suggestion are all refused `subject_busy` by the real runtime.

**Failure scenario.**

1. In the inspector the person asks the model about movement A.
2. They press Reject and enter a reason. R5 requires a reason for a rejection, so the page asks a second time, with `origin: classify_llm_reject`.
3. The runtime refuses that second `ledger.classify.review` with `subject_busy`, because A's first review is still paused.

The same refusal hits these flows:

- re-asking a Mixed suggestion with a share;
- asking about movement B while A's suggestion is shown or staged;
- every ask after the first in "Ask the model for each".

R5 and M5 therefore work only for one ask per profile, until that review is answered or expires. The refusal shows the raw `subject_busy` code. The scenario tests pass because the scenario host keeps any number of reviews pending at once, and nothing in it models `subject_busy`.

**Evidence.**

- The review's contract sets `conflict_scope: definition_subject`, makes the subject the profile, and sets `cancellation: unsupported` (`src/cadrumo/_data/operations/contract_manifest.json`, entry `ledger.classify.review`).
- A subject held by an operation that has not settled is refused: `src/cadrumo/application/operations/_supervisor_lease.py:192-233`.
- The lease is released only at settlement: `_supervisor_settlement.py:219-223`.
- The same rule is tested: `src/cadrumo_runtime/host/tests/test_operation_admitting_frontend_release.py:649-664`.
- The page asks in a loop and never answers or releases in between: `native/desktop/frontend/src/components/ledger/inspector/SelectionInspector.tsx:327-366`.
- Re-asking abandons the shown review (`inspector/ModelSuggestion.tsx:136-151`). `releaseReview` returns without cancelling because the review is not cancellable (`src/shell/ledgerApply.ts:652-659`).
- The scenario host starts reviews without limit: `src/dev/ledgerFixture.ts:1987-2003`.
- The rejection scenario that passes only against that looser host: `tests/scenarios/ledger-inspector.spec.ts:436`.

**Fix.** This needs a product-contract follow-on decision: make a paused model review cancellable, or scope its lease to the transaction. Until then, give the scenario host the runtime's lease, keep one review open at a time, and word `subject_busy`.

### P04 · tracked-ring-evicts-reviews | high | The host's 64-entry follow list counts every read, so ordinary browsing forgets a staged approval's operation. Its answer is then refused `not_admitted`, and the review is stranded.

**Failure scenario.**

1. The person stages a model approval.
2. They select a large range of movements. That starts up to 400 `ledger.track` sealed reads, and opening the review re-reads the period page by page.
3. They press Save. The answer is sent after the bulk and single writes (`ledgerPlan.ts` order).
4. By then more than 64 submissions have been tracked since the ask, so `operations.find` fails. The approval is reported refused (`not_admitted`) and stays staged, and it can never be sent.
5. The review stays paused at the runtime. `releaseReview`'s observe fails the same way, so under the finding above every later model ask on the profile is also refused until the review expires.

**Evidence.**

- Every submission, reads included, is tracked: `native/desktop/src-tauri/src/shell/ledger/mod.rs:251-253`.
- The oldest entry is evicted at 64: `src/shell/settle.rs:17, 182-190`.
- An answer must find the tracked operation: `ledger/mod.rs:428-436`.
- The sealed-read budget is 400 per window read: `frontend/src/components/ledger/useSealedMovements.ts:19, 22`.
- A thrown `not_admitted` becomes a refusal: `src/shell/ledgerApply.ts:263-276`.
- No test sends an answer after more than 64 other submissions, and the scenario host has no bound.

**Fix.** Track only operations the window can still follow: ones paused at review, running, or of unknown outcome. Never evict one paused at review. Add a host test that answers a review after 64 reads.

### P04 · rules-dry-run-zero | medium | The rules dry run always reads "0 already classified · 0 without a match", because the product never sends those counts in a dry run.

**Failure scenario.** The person runs Setup, Rules, dry run. The product's preview has `skipped_already_classified` and `no_match` set to null, and the page draws each as 0. The person is told that no movement was skipped and every movement matched a rule, whatever is true. This breaks the ADR rule "Unknown is never drawn as zero". It is ranked medium, as the audit ranked status-done-unchecked.

**Evidence.**

- The product's dry run requires both fields to be None: `src/cadrumo/application/ledger/rule_contracts.py:208-225`.
- The page substitutes 0 for each missing count: `native/desktop/frontend/src/components/ledger/setup/RulesSection.tsx:366-370`.
- The scenario host returns live counts in a dry run, so the scenario test (`ledger-setup.spec.ts:160`) cannot see this: `src/dev/ledgerSetupFixture.ts:314-337`.

The audit had filed this as "pre-existing". It is not: `RulesSection.tsx` was created by this plan (67c2d154d1).

**Fix.** Show only "would classify n" for a dry run, or show the other counts as not measured. Make the fixture omit them as the product does.

### P04 · crlf-breaks-check | low | `useSealedMovements.ts` was committed with CRLF line endings against `eol=lf`, so `prettier --check` fails and `npm run check` cannot pass.

**Evidence.** `git ls-files --eol` reports `i/crlf ... eol=lf` for `native/desktop/frontend/src/components/ledger/useSealedMovements.ts`, committed in b965c1d394. `prettier --check` flags only this file among the feature's files.

**Fix.** Renormalise the file to LF.

### P04 · documents-saved-unread-still-unknown | low | P03R documents-saved-unread-as-unknown is still open: a documents batch that saved is shown as "Outcome unknown".

**Evidence.**

- `components/ledger/transfer/importModel.ts:470-473` still folds `saved_unread` into `"unknown"`.
- `ImportDialog.tsx:690-694` and `documents/DocumentPanels.tsx:294-297` then hold it as `unknown`.

**Fix.** Carry `saved_unread` through `stopped.code` and hold it with that outcome.

### P04 · stored-direction-still-read | low | The P03R lower point is still open: the expense-category rule reads the stored direction and evidence, not the staged ones.

**Evidence.**

- `src/shell/ledgerCommands.ts:69-74`.
- `components/ledger/editing/ReviewDialog.tsx:255` calls `takesExpenseCategory(row)` on the stored row, although the same function builds `effectiveFacts` at line 251.

**Fix.** Pass the effective staged facts.

### P04 · answer-no-post-settle-recheck | low | An answered review is not rechecked against the session after it settles, as a submission is.

**Failure scenario.** The person signs out, or switches profile, while an approval's answer settles. The host returns `settled` with the result instead of `unknown`. The P01 unknown-after-settle fix covers this case for submissions only.

**Evidence.**

- `native/desktop/src-tauri/src/shell/ledger/mod.rs:428-447`: `answer` returns `settle::answer_on` directly.
- Compare `mod.rs:381`, where `relay` calls `settle::still_held`.

**Fix.** Wrap the answer's outcome in `settle::still_held(..., true)`.

## P04.S17 usability re-walk, 2026-10-24

The same ten tasks re-walked after the P03 fixes. Of the 25 earlier findings, 16 are fixed, 2 mostly fixed, 5 partly fixed, 1 still open (the narrow-grid critical) and 1 deferred. The re-walk adds 1 critical, 4 high, 5 medium and 12 low findings.

#### Tasks

| # | Task | Before: steps · s (≈) · result | Now: steps · s (≈) · result | Notes |
| --- | --- | --- | --- | --- |
| 1 | Bulk-classify 10 as Business with a category | 11 · 6.3 (≈24) · **trap** | 10 · 6.7 (≈12) · **pass at 1440, trap at 1280** | Alt+B works after a checkbox selection. The dialog splits "Expenses 6 · Income 4". Typing "soft" and pressing Enter picks Software subscriptions, and the next Enter stages. At 1280, with the agent pane and the inspector open, Description and Counterparty scroll out of view again (UX2 · narrow-grid-hides-description). |
| 2 | Mixed at 30 %, with the usage ratio | 4 · 1.3 (≈5) · pass with trap | 8 · 3.4 (≈8) · pass | The step now asks for the share and a category, and stages the usage ratio. After saving, the row reads Done. Defect: the ratio line says only "Usage ratio: 1", and the review shows the raw id `telefonia_movil` (UX2 · usage-ratio-copy). |
| 3 | One counterparty, grouped by category | 5 · 3.6 (≈9) · pass | 5 · 4.0 (≈7) · pass | The Group menu closes on choice. The group header has Classify ▾ and ⋯. There is still no counterparty filter: search also matches descriptions. |
| 4 | Fix and undo a typo | 6 · 1.4 (≈6) · pass | 6 · 1.5 (≈5) · pass | Ctrl+Z / Ctrl+Y work. The toast reads "Undone: edit". |
| 5a | Review and save | 3 · 1.5 (≈7) · pass (focus lost) | 3 · ≈1.9 (≈6) · pass | Focus returns to the active cell. The result reads "Saved · 3". |
| 5b | Unknown outcome, pause, Re-read | 3 · 1.9 · **trap** | 3 + Re-read · ≈2.1 · pass, with a bulk trap | The title is "Outcome unknown · 2" and the pause covers the whole page. Edits staged again while paused survive the Re-read. A 10-row Re-read banner lists every name over three lines (UX2 · reread-banner-lists-every-name). |
| 5c | Refused | 3 · 1.7 · pass with copy defect | 3 · ≈2.3 · pass | "Not saved: changed elsewhere · stays staged". The code sits under Technical details. |
| 6 | Import a statement | 6 · 7.1 (≈20) · pass with gaps | 6 · 8.0 (≈12) · pass | Duplicates carry a copy glyph, the strip has a "Duplicates 2" chip, the detected account is an editable Select, and the import-period banner is short. The preview `⚠ 2` uses the wrong glyph (UX2 · duplicate-glyph-mismatch). |
| 7 | Export the quarter | 5 · 3.3 (≈12) · pass | 5 · 4.1 (≈9) · pass | The footer is sticky and Export (40) is in view at 1280×800. The Save-as row is clipped (UX2 · export-saveas-clipped). |
| 8a | Confirm a received PDF and link it | 9 · 6.3 (≈28) · pass | 9 · 7.5 (≈14) · pass | Focus moves from Confirm to "Link · permanent" and then to the next document. |
| 8b | Confirm the **scanned** ticket and link it | could not be judged | 20 · ≈13 (≈30, plus finding the movement) · **trap** | The viewer scrolls away from the questions (UX2 · viewer-scrolls-away). No link step is offered (UX2 · ticket-no-link-path). The attested total is not what is stored (UX2 · total-answer-not-kept). |
| 9 | Make a rule from a selection | 6 · 3.2 (≈15) · **trap** | 5 · 3.7 (≈10) · pass | "Make a rule…" is in the selection ⋯ menu, and the count reads "Matches 8 · 0 to classify". After Save rule nothing says it was saved (UX2 · rule-saved-silently). |
| 10 | Health for a quarter | 3 · 2.7 (≈6) · pass | 3 · 2.5 (≈5) · **pass for the open quarter, trap for any other** | Health opens on the strip's last check and uses the same pills. On another quarter it shows the previous quarter's pills (UX2 · health-other-period-stale). |

Scale check, 5000 rows: the ○ pill, the header tick, Alt+P on 1,000 rows (the tray appears in 0.4–0.6 s) and Review all respond. Review holds back 284–343 movements as "Sealed state not read", and the count varies between identical runs (UX2 · sealed-holdback-rounds).

Keyboard re-checks: Alt+B/P/M work from the checkbox, the header and the period button. Shift+Space then Shift+↓ selects the row range. Enter stages from the Classify dialog. The paste preview's "Paste 0" is disabled and the first refusal reason is shown. "Use 77.45" fixes a decimal comma in one click. A reason chip moves focus to the marked cell.

#### Status of the earlier findings

- **classify-flow-hides-description (critical): still open; the earlier fix regressed at narrow widths.**
  - At a grid width of about 700 px or more, Description is pinned and stays in view.
  - At 1280 with the agent pane and the inspector open, the grid is 616 px wide. Description is then unpinned, and the ○ pill and reason-chip flows scroll it entirely out of view.
  - At 1440 in the default layout, Counterparty is hidden under the pinned Description, and no cue points to it.
  - The 40rem minimum is not enforced.
- **unknown-titled-nothing-saved (critical): fixed.** The title follows the worst outcome, the banner uses the Alert pattern with its action, and a saved row's staged change is dropped. One new problem: the long banner after a bulk Re-read.
- **business-on-income-forces-expense-category (high): fixed.** The dialog says "Expenses 6 · Income 4 · no category needed", and income rows stage no category.
- **alt-b-dead-after-checkbox-selection (high): fixed.** This covers the checkbox, the header, the period button and Shift+Space row mode. The dialog title counts the selection.
- **document-no-preview (high): partly fixed.** A viewer now exists, with page ‹ ›, zoom and fit. It is stacked above the reading, scrolls away from the questions, highlights nothing, and disappears after Confirm.
- **import-duplicates-unmarked (high): fixed for the parts that were not deferred.** The copy glyph, the strip chip and "Archive as duplicate" ship. Pairing in the preview stays deferred.
- **rule-matches-zero (high): fixed.** The count reads "Matches 8 · 0 to classify", Category is a Combobox, and "Make a rule…" is in the selection and group menus. New: no feedback after saving.
- **focus-lost-after-dialogs (high): fixed for all six listed commits.** Pressing the Duplicates chip at "All periods" once left focus on `<body>`.
- **export-footer-offscreen (medium): fixed.** The footer is sticky and Export is in view at 1280×800. The help text moved behind ⓘ. "Export without them" collapses to "Unsaved: 1 · not in this file". New: the body clips the Save-as row.
- **readiness-counts-disagree (medium): partly fixed.**
  - Export and Health reuse the strip for the open period.
  - Export for another period falls back to "Readiness issues: 20", a different unit from the strip's movements.
  - Health for another period shows the old period's pills.
  - The strip's ⚠ count depends on which rows are loaded or filtered (UX2 · countless-warning-zero-to-fix).
- **category-search-fuzzy (medium): partly fixed.** "soft" now finds Software subscriptions. Scattered-letter matches are still listed beside word matches, and they win Enter: "phone" puts "Depreciation of home…" above Mobile phone, "office" highlights Home-office electricity, and "tele" highlights "Alternative mutual-insurance contribution".
- **enter-reopens-combobox (medium): fixed.**
- **mixed-without-category (medium): fixed.** The step asks for the share and the category and stages the usage ratio. The row is Done after saving, and the fixture now raises "Mixed without a usage ratio".
- **refused-raw-code (medium): fixed.**
- **review-repeats-itself (medium): partly fixed.**
  - The summary table and the collapsed "Movements · n ›" list work, the result reads "Saved · n", and the pencil is gone.
  - The 676-row save progress lists every row as "Saved".
  - The review's first line, "Saved together: 1 · One by one: 1", describes how the save is sent rather than what changes.
- **hidden-columns-no-cue (medium): mostly fixed.** The `+1 ›` cue and the pinned edges ship. The column that sits under the pinned Amount shows fragments ("→ O", "Bank", "Vehic"), and nothing marks columns hidden on the left.
- **group-header-actions (medium): fixed.**
- **selection-inspector-repeats (low): fixed.** It shows one glyph-count line and "In 4,377.80 EUR". New: wrong "Hidden" counts after a failed readiness read.
- **plural-grammar (low): partly fixed.** The plural bugs are gone, but the replacement "Label: n" fragments read like a data dump: "Mixed · Movements: 1", "Personal · Staged: 1", "Undone: edit". There is also a new grammar error, "Classification rules was saved".
- **paste-refused-no-reason (low): fixed.**
- **amount-comma-refusal (low): fixed.**
- **usd-decimal-alignment (low): fixed.**
- **status-column-wasted (low): fixed.** Compact density uses 2.75rem with a non-state header glyph. Comfortable density shows the word.
- **small-copy-and-chrome (low): mostly fixed.**
  - Fixed: the import duplicate copy, the import banner, the unreadable-file border, the palette hints, the tab names, the ⇆ glyph and the Health sum (40 = 8 + 31 + 0 + 1).
  - Still open: the reason chips' accessible names repeat the label and count.
  - Not re-checked: "Saved changes can't be undone here".
- **deferred-contract-gaps:** not re-reported.

P03 re-review items with a UX surface, re-checked live:

- **reread-drops-new-edits: fixed.** A counterparty and Business staged again on a row the read showed as saved both survived Re-read.
- **generic-settle-resolves-nothing: fixed for Rules.** An unknown Save rule blocks Save, its "Read again" reads the rule list, and the dialog closes as saved.
- **unmeasured-drawn-done-in-inspectors: fixed.** When readiness fails, the selection counts show `◌ 94`. The new "Hidden" defect is below.
- **sealed-unread-claimed-unsealed: fixed in substance.** The review says "Sealed state not read: 343 · Re-read". The UX cost is below.
- **export-unknown-not-held: fixed.** An unknown export pauses the page and clears its file.
- **chords-skip-the-header: fixed.**
- **shift-space-stale-anchor: fixed.**
- **compact-status-glyphs: header fixed.** The lifecycle badge was not re-checked.
- **pinned-group-narrow-band: still open.** The fix unpins Description instead of keeping the grid wide enough. See the first finding.

### UX2 · narrow-grid-hides-description | critical | At 1280 with the agent pane and inspector open, the "to classify" and reason-chip flows again leave no Description or Counterparty on screen

- **What I did.** At 1280×800 in the default layout (agent pane open), I clicked `○ 8`, then the "Category 1" chip. I did the same at 1440×900.
- **What happened.**
  - The inspector opens and the grid becomes 616 px wide, under the 40rem minimum.
  - Description loses its pinned position, and the reveal scrolls it off to the left: the header spans 116–308 against a pinned Date ending at 508.
  - The grid then shows Status, Date, Classification, Category and Amount, plus a sliver of Counterparty ("ty", "Trazo", "Ireland Ltd").
  - At 1440 in the default layout, Description stays pinned, but Counterparty (577–721) sits entirely under it, "Direction" is clipped to "rection", and nothing tells you a column is hidden on the left.
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\07b-1280-light-toclassify.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\07c-1280-light-reason-chip.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\07c-1280-dark-reason-chip.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\36-1440-agent-pill.png`
- **Change.**
  - Keep the M6 promise structurally. When the inspector opens and the grid would drop below 40rem, collapse the agent pane to its rail, the way the shell already collapses panes, or open the inspector at `--inspector-min`.
  - Never unpin Description. Let it shrink to its 12rem minimum instead.
  - When `reveal` would push a column out of view on the left, show the same `‹ +1` header cue the right edge already has.

### UX2 · health-other-period-stale | high | Health for another quarter shows the previous quarter's readiness pills under the new quarter's heading, even after "Check"

- **What I did.** I opened Setup ▾ → Health at 2026 · 4T, pressed ‹ to move to 3T, waited 6 s, and then pressed Check.
- **What happened.**
  - "Status · 2026 · 3T" correctly shows To classify 10 and Foreign without a rate 0.
  - "What's still missing · 2026 · 3T" shows `◌ ○ 8 ⊘ 1`. These are the 4T values.
  - After Check it shows `○ 8 ⊘ 1` with no ⚠ pill, although Movements for 3T shows `⚠ 10 ○ 10` and no ⊘.
  - The Movements tab badge also keeps saying 8 while Health is open.
  - The strip counts the page's old loaded rows against the new period's check, which R1 forbids ("every count shows stored state").
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\24c-health-3T-1440.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\25b-health-3T-checked.png`
- **Change.** Health's strip, the tab badge and Export's strip must count from the rows of the period they are titled with. Until those rows are read, show only the muted `◌` pill, with the tooltip "3T not checked yet · Check". Health's Status table already reads its own period, so feed the strip from the same read.

### UX2 · countless-warning-zero-to-fix | high | The strip says "Not ready for calculation · 0 to fix" while 30 movements need fixing, and at scale its counts change with the sort order

- **What I did.**
  - I chose Period ▾ → All periods, then pressed the "Duplicates 1" chip. This is the flagged "warning pill with no count".
  - In the 5000-row scenario at All periods, I changed the sort from date ascending to descending.
- **What happened.**
  - With the duplicates filter on, the `○` and `⊘` pills vanish. The ⚠ pill becomes a solid warning capsule with no number, no longer a button, whose tooltip and accessible name read "Not ready for calculation · 0 to fix". The period has 30.
  - The cause is that `readinessSets` intersects the check's issues with the rows currently loaded (`movementsModel.ts:369-408`). The duplicates filter is read from the ledger, so only one row is loaded. `ReadinessStrip.tsx:85-99` then draws the deliberate count-less pill.
  - At 5000 rows, the same intersection makes `⚠ 95 ○ 143 ⊘ 16` become `⚠ 101 ○ 202 ⊘ 25` when only the sort changes. "loaded rows only" appears only in the tooltip.
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\05a-all-duplicates.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\06-dup-all-hover.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\04-all_ledgerRows_5000-dark.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\04-all-desc_ledgerRows_5000-dark.png`
- **Change.**
  - The ⚠ count is the number of distinct movements in the check's own issue list for the period, never the part of it that is loaded.
  - ○ and ⊘ come from the period counts the status read already returns: `pending_review_count`, and `unconverted_currency_count` for EUR rates.
  - A grid filter never changes the strip.
  - Where only a window-local count exists, draw `⚠ ≥ 95`, with "in the loaded rows" in the tooltip.
  - The count-less ⚠ is allowed only when the check reports not ready with zero movement-level issues. Its tooltip then names the period-level reason, never "0 to fix".

### UX2 · preflight-failure-hides-selection | high | When readiness can't be read, every selected row on screen is reported "Hidden", and bulk classify is disabled

- **What I did.** In 3T, I made `ledger.preflight` unavailable (`nextReads("ledger.preflight", 50)`), opened the inspector on a row with Alt+I, and ticked the header to select all 106 shown movements.
- **What happened.**
  - The selection inspector says "Hidden: 106 of 106 selected · Show them · Keep only visible", although every row is drawn and ticked.
  - Business, Personal and Mixed are disabled.
  - The set buttons read "Set for 0 visible + 37 hidden" and "Set for 0 visible + 106 hidden".
  - With readiness readable, the same steps give no hidden note and "Set for 37".
  - A transient readiness failure therefore blocks the page's main bulk action, with a false reason.
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\28d-preflight-failed-selection.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\29-selectall-3T-failed.png`
- **Change.**
  - Derive "visible" only from the grid's drawn rows (`MovementsSection.tsx:692`). It currently reaches the inspector through the context built at `MovementsSection.tsx:1213` and read at `SelectionInspector.tsx:167`.
  - Make sure no readiness state can empty that set.
  - A failed readiness read should change only the strip, to `◌` with "Couldn't check · Check again".
  - Add a scenario test: preflight unavailable, select all, assert no hidden note.

### UX2 · viewer-scrolls-away | high | The scanned ticket is never on screen next to the question it is needed for

- **What I did.** In Documents I opened `ticket-plenoil-1015.jpg` at 1440×900 and pressed the Supplier NIF `⚠`, which is the "Go to the question" button.
- **What happened.**
  - The viewer is a fixed box of about 380 px at the top of the right panel, at 100 % zoom on a 902×1278 image, above 14 reading rows.
  - At the question "Two tax ids are printed on the ticket", the image is scrolled above the viewport (its top is at −194 px), so the one thing you need to look at is gone.
  - The two readings, "B87000001 · top of the ticket" and "B87000007 · footer", don't point into the image.
  - Focusing a field highlights nothing.
  - After Confirm the viewer disappears, so you can't check what you just confirmed.
  - The document list keeps 463 px for three file names.
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\19b-ticket-1440.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\20a-question-1440.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\20b-choose-reading-1440.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\20d-confirmed-1440.png`
- **Change.**
  - With a document open, collapse the list to the shell's narrow rail, keeping the `⚠ 2` badges.
  - Split the panel into two ResizeHandle columns: a sticky viewer on the left, and "What was read" with the questions scrolling on the right.
  - Choosing a reading, or focusing a field, scrolls the viewer to that reading's location. Use the reader's box when it gives one, and "top" or "footer" otherwise.
  - Keep the viewer, read-only, under the "Confirmed as invoice" card.
  - The scenario's synthetic ticket should print the two NIFs, so this flow can be judged at all.

### UX2 · ticket-no-link-path | medium | After confirming a ticket with no matching movement, the panel offers no way to link it

- **What I did.** I confirmed the ticket (10 steps), then looked for a way to link it.
- **What happened.**
  - The panel shows only "Confirmed as invoice T-1015-0042 · Pending".
  - The PDF path offers "Link it to its movement? … Link · permanent". The ticket path, with no automatic match, offers nothing.
  - Linking took ten more steps: Movements → find the fuel row by eye → Alt+I → Invoice → "Link another invoice" → pick → Review → two ticks → Save.
  - The picker's popover is 220 px wide and wraps every entry onto two lines.
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\20d-confirmed-1440.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\21b-picker.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\21d-review.png`
- **Change.**
  - When no movement settles the invoice, the confirmed card says "No movement matches · Find its movement…".
  - That action opens the M1 picker turned around: movements within ±10 days and a similar amount, sorted "Settles this amount" first.
  - It stages through the same permanent-link review.
  - Size the popover to at least its trigger's width plus the dialog's width, as the Combobox already does.

### UX2 · total-answer-not-kept | medium | Answering "It is right as read" for the printed total 58.40 still stores the invoice at 58.39

- **What I did.** For "The totals do not add up · Base plus IVA is 58.39; the ticket prints 58.40", I chose "It is right as read", typed the reason "Rounding" and confirmed.
- **What happened.** The link picker, the permanent-link review ("T-1015-0042 · 58.39") and the Invoices tab ("… 48.26 10.13 EUR … 58.39") all carry 58.39, the value the person declined.
- **Caveat.** This is seen against the scenario host. Its catalogue entry is built from base plus IVA, so check what the product's confirm stores.
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\20c-before-confirm-1440.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\21d-review.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\21f-invoices.png`
- **Change.** Do one of the following:
  - store the attested printed total;
  - or, if the catalogue always derives the total, replace the "It is right as read" segment for derived fields with one plain line: "Saved as 58.39 (base + IVA) · ticket prints 58.40".

### UX2 · reread-banner-lists-every-name | medium | After a bulk unknown save, the Re-read alert names every movement, over three lines

- **What I did.** I bulk-staged Personal on 10 movements, saved with `nextWrites(["unknown"])`, and pressed Re-read.
- **What happened.**
  - The persistent alert reads "FIBRA HOGAR ALBOR was saved · PAPELERIA TRAZO was saved · GASOLINERA RUTA 7 was saved · … SOFTNUBE IRELAND SUSCRIPCION was saved". That is 10 names, about 60 words, wrapping to three lines, against R22's 8-word banner budget.
  - Names are ambiguous: the quarter has several "PAPELERIA TRAZO" movements.
  - Before the Re-read, the ten classified rows vanish from the "To classify" view, and the inspector says "Hidden: 10 of 10 selected". The rows are correct, but nothing says that is why.
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\14a-bulk-unknown.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\14b-after-reread.png`
- **Change.**
  - The alert reads `✓ 10 saved · ↺ 0 staged again · Show them`, where "Show them" applies a filter chip naming the ids.
  - Per-row detail goes to each row's History, which R11 already asks for.
  - The unknown banner's trailing fragment "· Staged changes" should name what is unknown, for example "Outcome unknown · 10 movements · writes paused".

### UX2 · category-ranking-scatter | medium | Scattered-letter matches still sit beside word matches and win Enter

- **What I did.** In the Business step I typed each of these queries and read the highlighted option: "office", "phone", "tele", "telefono", "gasolina".
- **What happened.**
  - "office" highlights Home-office electricity. Office supplies is fifth.
  - "phone" lists Landline phone, then Depreciation of home used for business, then Property tax (IBI) on home used for business, then Mobile phone.
  - "tele" highlights "Alternative mutual-insurance contribution".
  - The Spanish words a person reads on their statement ("telefono", "gasolina", "coche") find nothing in the English catalogue.
  - The cause: `optionScore` (`combobox.tsx:66-80`) returns 0.1 for a scatter match even when word matches exist. The family groups are also ordered by their best member, so a scatter item in an earlier group outranks a word match in a later one.
- **Screenshot.** `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\15a-office.png`
- **Change.**
  - Rank in this order: the name starts with the query, then a word starts with it, then the name contains it.
  - Drop scatter matches whenever any of those exist.
  - Order groups by their best score, and the items inside a group by score.
  - Fold accents.
  - Add the Spanish statement words to each category's `keywords` through the `dev.locales` catalogue.

### UX2 · sealed-holdback-rounds | medium | Saving 1,000 movements holds back a different number each time as "Sealed state not read", and Re-read seems to do nothing twice

- **What I did.** At 5000 rows I selected all 1,000 to classify, pressed Alt+P, then Review.
- **What happened.**
  - Across three identical runs, Review said "Saved together: 657 · Held back: 343", then 676/324, then 716/284, each under "Sealed state not read: n · Re-read".
  - In the last run, the first two Re-read presses left the counts unchanged, with no progress shown. The third cleared the hold to "Saved together: 1000".
  - "Sealed state" is jargon to a self-employed person.
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\33b-scale-review.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\34-sealed-rounds.png`
- **Change.**
  - The review reads the lock state of every staged movement with its own budget, as P03R asked, before it shows Save.
  - While it reads, it shows a progress line ("Checking which movements are locked · 412 of 1,000").
  - Use the plain word "locked" (R1's "Verified (sealed)" stays as the state name).
  - Re-read shows its spinner, and the held count visibly falls.

### UX2 · export-other-period-sentence | low | Export for another period swaps the strip for a sentence in a different unit

- **What I did.** I opened Export and pressed ‹ to move to 3T.
- **What happened.** The pills are replaced by "Not ready for calculation · Readiness issues: 20. The file shows what the ledger holds now." The 20 counts issues; the strip for 3T counts `⚠ 10 ○ 10` movements.
- **Screenshot.** `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\26a-export-3T.png`
- **Change.** Read that period's check and draw the same strip component. Until then, draw `◌` with "3T not checked · Check".

### UX2 · usage-ratio-copy | low | The Mixed step's ratio line is a bare count, and the review shows a raw id

- **What happened.**
  - The Mixed step says "Usage ratio: 1" when a ratio exists, and "No usage ratio for this category: 1 · Business-use ratios" when none does, on a one-movement dialog.
  - The review row reads "Usage ratio · empty → telefonia_movil".
  - The share hint reads "Percent of business use: 50 for 50%."
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\08b-mixed-filled.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\08d-mixed-review.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\09a-mixed-fuel.png`
- **Change.**
  - Write the line as `✓ Usage ratio · Mobile phone` or `⚠ No usage ratio for Vehicle fuel · Business-use ratios ›`.
  - The review shows the ratio's display name; the id goes under Technical details.
  - The hint reads "Write 30 for 30 %", as R3 words it.

### UX2 · colon-count-copy | low | The plural fix replaced grammar with "Label: n" fragments, and one action has two names

- **Examples.**
  - "Mixed · Movements: 1"
  - "Business · Software subscriptions · Staged: 10"
  - "Undone: edit"
  - "Rows: 3 · nothing is staged until you paste."
  - "Classification rules was saved", which is a grammar error
- **The same action under two names.** The page banner says "Re-read" and the rule dialog says "Read again".
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\08a-mixed-dialog.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\11c-amount-comma.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\30b-rule-after-reread.png`
- **Change.**
  - Use ICU plural messages in the `dev.locales` catalogue: "Mixed · 1 movement", "10 staged", "Undone · counterparty", "Rules saved".
  - Use one verb, "Re-read", everywhere.

### UX2 · rule-saved-silently | low | Save rule closes with no confirmation, and focus lands on an empty checkbox cell

- **What happened.** After Save rule, the dialog closes. There is no toast and no change in the grid, because the rows were already Personal. Focus is on the first row's checkbox cell.
- **Screenshot.** `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\23b-saved-1440.png`
- **Change.** Show the toast "Rule saved · runs 4th · Rules ›", and return focus to the active cell, as the other grid dialogs do.

### UX2 · bulk-chord-overwrites-silently | low | Alt+P on a select-all reclassifies Business and Mixed rows and clears their categories, with a toast that says only "Personal · Staged: 19"

- **What I did.** I ticked the header (40 movements) and pressed Alt+P.
- **What happened.** 19 movements were staged with 21 edits, including Business and Mixed rows whose category and share are cleared. Nothing said that classified rows were being changed. The review catches it, but only if read.
- **Change.** The toast and the tray tooltip say what was overwritten: "Personal · 19 · 11 were Business or Mixed · Undo". Above a small threshold, Alt+B/P/M on already-classified rows asks once, in the M4 dialog.

### UX2 · partial-column-fragments | low | The column under the pinned Amount shows word fragments, and a staged category there is unreadable

- **What happened.** At 1280 with the inspector open, the Category column is cut mid-word under the pinned Amount ("→ O", "Bank", "Home", "Vehic"). The `+1 ›` cue is there, but the staged "→ Office supplies" can't be read.
- **Screenshot.** `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\27c-dark-1280-inspector.png`
- **Change.** Snap horizontal scrolling to column boundaries, so a column is either whole or counted in the `+n` cue.

### UX2 · duplicate-glyph-mismatch | low | The import preview marks possible duplicates with ⚠, while the grid and the strip use the copy glyph

- **What happened.** The preview's file card shows `⚠ 2`. The grid's Status cell and the strip's "Duplicates 2" chip use `copy`. M3 reserves ⚠ for readiness issues, and DS-12 holds that no glyph means two things.
- **Screenshot.** `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\16c-preview-1440.png`
- **Change.** Use the copy glyph on the preview chip, with the tooltip "Possible duplicates: 2 · imported and flagged".

### UX2 · export-saveas-clipped | low | The Export body clips the Save-as row behind the sticky footer, with spare height below the dialog

- **What happened.** At 1440×900, the file name and "Change…" are cut at the footer edge. The dialog ends at y=658, leaving 240 px of viewport unused.
- **Screenshot.** `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\17c-chosen-1440.png`
- **Change.** Let the Dialog body grow to the dialog's max-height before it scrolls.

### UX2 · reason-chip-names-repeat | low | Reason chips' accessible names say the label and count twice

- **What happened.** The names read 'Usage ratio 25 Mixed without a usage ratio: 25. Show them and how to fix them' and 'Category 4 Category missing: 4. …'. The pills and tabs are already fixed.
- **Change.** The name is the sentence only ("Mixed without a usage ratio: 25"). "Shows them and how to fix them" goes in `aria-description`.

### UX2 · unknown-pill-shape | low | The muted "not checked" pill renders as an empty, squashed capsule

- **What happened.** In Health on a new period, and in the strip when readiness fails, the `◌` pill is drawn as a short grey capsule with the glyph off-centre, and it reads as a broken control.
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\24c-health-3T-1440.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\28d-preflight-failed-selection.png`
- **Change.** Give it the same Badge size and padding as the counted pills, drawn as the glyph alone.

### UX2 · period-years-late | low | "Years with movements" arrives about a second after the dropdown opens, so the dropdown grows under the pointer

- **What happened.** At 300 ms the list is empty. At 1.5 s it shows 2003 · 2011 · 2019 · 2024 · 2025 · 2026, because the list costs two sequential reads per year. On the first run of the session, choosing "Year" also left focus on `<body>`; later runs returned focus to the trigger.
- **Screenshots.**
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\01a-period-open.png`
  - `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\02a-period-open-wait.png`
- **Change.** Read the years when the page opens, not when the dropdown opens. Reserve the row's height while it loads. Always return focus to the trigger after a choice.

### UX2 · unknown-export-reread | low | An unknown export's banner offers only "Re-read", which reads the ledger, not the file

- **What happened.** The alert reads "Outcome unknown: writes paused · ledger-2026-4T.csv [Re-read]". The dialog itself says "check the file before exporting once more", but the banner's one action cannot tell whether the file was written.
- **Screenshot.** `<local-home>\AppData\Local\Temp\claude\Y--code-cadrumo-worktrees-tui\19757641-734b-4c55-93a9-baed20b872a4\scratchpad\reviews\ux2\shots\18b-after-close.png`
- **Change.** Keep the R11 hold. Word the banner for the file: "Export outcome unknown · ledger-2026-4T.csv · [Show in folder] [I've checked it]". The second action releases the hold.

### UX2R · viewer-reading-place | low | The document viewer cannot scroll to where a reading was found, because a reading carries no position

- **What happened.** viewer-scrolls-away is fixed in `5c1b42b6bd`: the viewer sits beside the reading and its questions, the list folds to a rail, and the viewer stays after Confirm. Scrolling the viewer to the place a reading came from is not done.
- **Why.** A reading's candidates (`AmbiguityCandidate`: value, anchor, note) carry no page, box or offset. Inferring one from the note's text would be a heuristic second route beside the extractor's own provenance.
- **Recommendation.** A follow-on decision on the reading contract: whether extractors report a page and a box for each candidate, and how a box from an image or a PDF is expressed. The viewer then scrolls to it. Until then the person reads the page beside the questions.
- **Also deferred and listed with it:** rule matching on counterparty or amount range (S14), and import duplicate pairing in the preview and "Keep both" (`deferred-contract-gaps`).

## P04.S17 plan-close re-review, 2026-10-25

Independent static review of every ledger commit from `9e4f9b9eb0` to `15cd032f4b` against the P04.S17 integrated-review and usability re-walk findings and `2026-10-23-desktop-ledger-editor-adr` with both 2026-10-24 amendments. No critical or high finding; no Step is reopened. All seven P04.S17 findings are fixed. Of the UX2 findings, all are fixed except two partial ones below; `viewer-scrolls-away` keeps its recorded deferral `viewer-reading-place`, and `total-answer-not-kept` is fixed by wording because the product derives the total by design (`domain/invoices/models.py:755-759`). The reveal resolves only this session's export token once the file exists, and no path reaches the window.

Pending verification, apart from defects: the packaged-window privacy check (`294041c3f0`) has not run in a real window; the full scenario suite is running; nothing covers a review ask longer than the host's follow against the real runtime, the 1280 and 1440 layouts with agent and inspector after the floor change, or a visual check of `unknown-pill-shape` and `export-saveas-clipped`.

### P04R · review-ask-in-flight-not-released | medium | A model ask that outlasts the host's follow, or is still in flight when the next ask is made, is never cancelled, so the movement is refused `subject_busy` again

- **Failure scenario.** A local model takes longer than the host's settle bound (`relay.rs:12`). The review is a mutation, so the page gets `unknown` with an `operation_id` (`settle.rs:449-455`), but the catch paths in `ModelSuggestion.tsx:146-148,184-186` and `SelectionInspector.tsx:415-437` record the operation only from a returned review, so nothing is released. The review later pauses holding the movement, and every further ask about it is refused. Separately, asking about A, moving to B and back while A's ask is running, then asking again, is refused: `askReview` waits only for releases already registered (`ledgerApply.ts:726`), and `cancelReview` cancels only an observed review, not a running one (`ledgerApply.ts:669`), though the executor accepts a cancel after the model answers (`llm_review_execution.py:343`).
- **Fix.** Release by the failure's `operation_id` in both catch paths; cancel a cancellable running outcome; register an ask in flight so the next ask waits for it.

### P04R · grid-least-includes-growth | low | The grid's least width counts the growth its columns take from spare room, so the page floor follows the current width

- **Failure scenario.** `dataGridModel.ts:120,142-149` computes `least` from the narrowed placement, which still shares the spare width among growing columns. With spare room the floor is about the current width, so opening the agent at 1440 or wider clamps it for a render before it reaches its remembered width, and the agent's and the split's limits land short until the next render.
- **Fix.** Compute `least` from the widths before growth, as its comment says.

### P04R · follow-ring-unbounded-residents | low | Unknown writes and unanswered reviews stay in the host's follow list for the session, and the ceiling check is apart from tracking

- **Failure scenario.** A write that ended in an error stays open (`settle.rs:194`) unless the window follows it again; the page re-reads the ledger instead. After 256 such entries every submission is refused `unavailable` (`settle.rs:228-243`). `room()` and `track()` take the lock separately with the submit between them (`ledger/mod.rs:273-276`), so concurrent submissions can pass the ceiling. Neither is likely in practice.
- **Recommendation.** Re-observe open entries when the page re-reads, or bound their age; take the room check inside tracking.

### P04R · derived-fields-hand-list | low | The page's list of fields the product works out is a hand copy of the domain rule

- **Evidence.** `documentsModel.ts:283` lists `grand_total`, restating `domain/invoices/models.py:755-759`. A change to the domain rule would leave the page's wording wrong without a failing test.
- **Fix.** Take it from a product contract field, or pin it to the domain rule with a test.

### P04R · partial-fixes | low | Two re-walk fixes are partial

- `partial-column-fragments`: scrolling now settles on a column start at the pinned start group (`dataGridModel.ts:52-76`), but the reported symptom was the end group: a column cut under the pinned Amount is still drawn as a fragment (`data-grid.tsx:1458-1463`). Masking it blank broke clicks on cells under the end group, so it was kept and counted by the `+n ›` cue.
- `reread-banner-lists-every-name`: "Show them" selects the movements (`LedgerPage.tsx` `onShow`) but applies no filter, so rows the current view hides stay hidden.
- `colon-count-copy`: the cited strings are fixed; other "Label: {count}" strings remain, such as "Saved together: {count}" and "Held back: {count}".

Recommendation for a follow-on decision, not a finding: a cancel of a waiting review settles at once only when its executor ran under the current supervisor (`_supervisor_settlement.py:113-129`); after a runtime restart it waits for the lease to lapse and ends interrupted with an unknown effect.
